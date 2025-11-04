"""
Video Search Node for LangGraph

Performs semantic search to find videos matching a subject.
Uses Qdrant for chunk retrieval and PostgreSQL for video metadata.
Includes fuzzy title matching for more precise results.
"""

from collections import defaultdict
from difflib import SequenceMatcher
from typing import Any, Dict
from uuid import UUID

from loguru import logger
from sqlalchemy import select

from app.db.models import Transcript
from app.db.session import AsyncSessionLocal
from app.db.repositories.channel_video_repo import ChannelVideoRepository
from app.rag.utils.state import GraphState
from app.services.embedding_service import EmbeddingService
from app.services.qdrant_service import QdrantService


def fuzzy_match_score(query: str, title: str) -> float:
    """
    Calculate fuzzy match score between query and title using SequenceMatcher.

    Uses token set ratio approach: splits both strings into words,
    compares them in any order to handle reordering.

    Args:
        query: User's search query
        title: Video title

    Returns:
        Similarity score from 0.0 to 100.0
    """
    query_lower = query.lower().strip()
    title_lower = title.lower().strip()

    # Direct similarity
    direct_score = SequenceMatcher(None, query_lower, title_lower).ratio() * 100

    # Token set ratio (compare words in any order)
    query_tokens = set(query_lower.split())
    title_tokens = set(title_lower.split())

    if not query_tokens or not title_tokens:
        return direct_score

    # Calculate intersection ratio
    intersection = query_tokens & title_tokens
    union = query_tokens | title_tokens
    token_score = (len(intersection) / len(union)) * 100 if union else 0

    # Return the higher of the two scores
    return max(direct_score, token_score)


async def search_videos_by_subject(state: GraphState) -> Dict[str, Any]:
    """
    Video search node that finds videos matching a subject using semantic search.

    Flow:
        1. Extract subject and user_id from state
        2. Generate embedding for subject query
        3. Search Qdrant for matching chunks (top 100 to get enough unique videos)
        4. Group chunks by youtube_video_id and calculate average relevance score
        5. Query database for top 20 videos by score
        6. Sort by created_at DESC and format as HTML list
        7. Handle empty results

    Args:
        state: Current graph state containing:
            - subject: The extracted subject/topic to search for
            - user_id: UUID of the user (for data isolation)
            - user_query: The original query (for logging)

    Returns:
        Updated state with:
            - response: HTML-formatted list of matching videos
            - metadata: Dict with video count, search subject, and response type

    Example:
        state = {
            "user_query": "Show me videos about Claude Code",
            "user_id": "user-uuid-here",
            "subject": "Claude Code",
            "intent": "metadata_search"
        }
        updated_state = await search_videos_by_subject(state)
        # updated_state["response"] contains HTML list of matching videos
    """
    subject = state.get("subject", "")
    user_id_str = state.get("user_id", "")

    # Extract channel context if present
    channel_id_str = state.get("channel_id")
    collection_name = state.get("collection_name")

    if channel_id_str:
        logger.info(f"Searching videos in CHANNEL for subject: '{subject}' (channel_id={channel_id_str})")
    else:
        logger.info(f"Searching videos in PERSONAL chat for subject: '{subject}' (user_id={user_id_str})")

    try:
        # Convert user_id string to UUID
        user_id = UUID(user_id_str)

        # Convert channel_id to UUID if present
        channel_id = UUID(channel_id_str) if channel_id_str else None

        # Step 0: Try fuzzy title matching first (faster than embedding search)
        logger.debug("Attempting fuzzy title matching before semantic search")
        title_matches = []

        async with AsyncSessionLocal() as session:
            if channel_id:
                # Get all channel videos for title matching
                channel_video_repo = ChannelVideoRepository(session)
                channel_videos, _ = await channel_video_repo.list_by_channel(
                    channel_id=channel_id,
                    limit=1000,  # Get all videos for title matching
                    offset=0
                )
                # Calculate fuzzy match scores for each video title
                for cv in channel_videos:
                    if cv.transcript and cv.transcript.title:
                        score = fuzzy_match_score(subject, cv.transcript.title)
                        if score > 80.0:  # High similarity threshold (80%)
                            title_matches.append((cv.transcript, score))
                            logger.info(
                                f"Strong title match: '{cv.transcript.title}' "
                                f"(score: {score:.1f}%)"
                            )
            else:
                # Get all user transcripts for title matching
                query = select(Transcript).where(Transcript.user_id == user_id)
                result = await session.execute(query)
                transcripts = list(result.scalars().all())

                for transcript in transcripts:
                    if transcript.title:
                        score = fuzzy_match_score(subject, transcript.title)
                        if score > 80.0:
                            title_matches.append((transcript, score))
                            logger.info(
                                f"Strong title match: '{transcript.title}' "
                                f"(score: {score:.1f}%)"
                            )

        # If strong title matches found, return them directly (skip expensive embedding search)
        if title_matches:
            logger.info(
                f"Found {len(title_matches)} strong title matches (>80% similarity), "
                f"skipping embedding search"
            )

            # Sort by fuzzy match score descending, limit to top 3
            title_matches.sort(key=lambda x: x[1], reverse=True)
            matched_transcripts = [t for t, score in title_matches[:3]]

            # Format response
            video_items = []
            for idx, transcript in enumerate(matched_transcripts, 1):
                duration_min = transcript.duration // 60 if transcript.duration else 0
                language = transcript.meta_data.get("language", "Unknown")
                channel = transcript.channel_name or "Unknown channel"
                match_score = next(score for t, score in title_matches if t.id == transcript.id)

                video_items.append(
                    f"<li>"
                    f"<strong>{transcript.title or 'Untitled Video'}</strong><br>"
                    f"<small>Channel: {channel} | "
                    f"Duration: {duration_min} min | "
                    f"Language: {language} | "
                    f"Match: {match_score:.0f}%</small>"
                    f"</li>"
                )

            videos_html = "\n".join(video_items)

            # Check if this is a compound query (find + summarize)
            intent = state.get("intent", "")
            if intent == "metadata_search_and_summarize":
                # User wants to find AND get info - router will auto-trigger summary
                if len(matched_transcripts) == 1:
                    cta_message = (
                        f"<p><strong>Great! I found the video you're looking for.</strong></p>"
                        f"<p><em>Generating summary...</em></p>"
                    )
                else:
                    cta_message = (
                        f"<p><strong>I found {len(matched_transcripts)} matching videos.</strong></p>"
                        f"<p>Let me know which one you're interested in, and I'll help you with your questions!</p>"
                    )
            else:
                # Regular search - standard message
                cta_message = (
                    f"<p>You can ask me questions about "
                    f"{'this video' if len(matched_transcripts) == 1 else 'any of these videos'}!</p>"
                )

            response = (
                f"<p>Found <strong>{len(matched_transcripts)} video(s)</strong> "
                f"matching <strong>\"{subject}\"</strong>:</p>"
                f"<ol>{videos_html}</ol>"
                f"{cta_message}"
            )

            return {
                **state,
                "response": response,
                "metadata": {
                    **(state.get("metadata", {})),
                    "response_type": "metadata_search",
                    "video_count": len(matched_transcripts),
                    "search_subject": subject,
                    "search_method": "fuzzy_title_match",
                    "avg_match_score": sum(s for _, s in title_matches[:3]) / len(title_matches[:3])
                }
            }

        logger.info("No strong title matches found, proceeding with semantic search")

        # Step 1: Generate embedding for subject
        embedding_service = EmbeddingService()
        embeddings = await embedding_service.generate_embeddings([subject], user_id=user_id_str)
        query_vector = embeddings[0]
        logger.debug(f"Generated subject embedding (dim={len(query_vector)})")

        # Step 2: Search Qdrant for matching chunks (conditional based on context)
        qdrant_service = QdrantService()

        if channel_id and collection_name:
            # Channel conversation - search channel collection
            logger.info(f"Searching channel collection: {collection_name}")
            qdrant_results = await qdrant_service.search(
                query_vector=query_vector,
                user_id=user_id_str,
                channel_id=channel_id_str,
                collection_name=collection_name,
                top_k=100,  # High limit to get many potential matching videos
            )
        else:
            # Personal conversation - search user collection
            qdrant_results = await qdrant_service.search(
                query_vector=query_vector,
                user_id=user_id_str,
                top_k=100,  # High limit to get many potential matching videos
            )

        logger.info(f"Qdrant returned {len(qdrant_results)} chunks")

        # Step 3: Group chunks by youtube_video_id and calculate average scores
        video_scores = defaultdict(list)
        for result in qdrant_results:
            payload = result.get("payload", {})
            youtube_video_id = payload.get("youtube_video_id")
            score = result.get("score", 0.0)

            if youtube_video_id:
                video_scores[youtube_video_id].append(score)

        # Calculate average score per video
        video_avg_scores = {
            video_id: sum(scores) / len(scores)
            for video_id, scores in video_scores.items()
        }

        logger.info(f"Found {len(video_avg_scores)} unique videos matching subject")

        # Step 4: Sort videos by score and get top 7 youtube_video_ids
        sorted_video_ids = sorted(
            video_avg_scores.keys(),
            key=lambda vid: video_avg_scores[vid],
            reverse=True  # Highest scores first
        )[:7]  # Limit to top 7 for focused results

        if not sorted_video_ids:
            # No matching videos found
            async with AsyncSessionLocal() as session:
                if channel_id:
                    # Count channel videos
                    channel_video_repo = ChannelVideoRepository(session)
                    total_videos = await channel_video_repo.count_by_channel(channel_id)
                else:
                    # Get total video count for user
                    count_query = select(Transcript).where(Transcript.user_id == user_id)
                    count_result = await session.execute(count_query)
                    total_videos = len(list(count_result.scalars().all()))

            if channel_id:
                response = (
                    f"<p>No videos found in this channel matching <strong>\"{subject}\"</strong>.</p>"
                    f"<p>This channel has {total_videos} video(s) in total. "
                    f"Try rephrasing your search or browsing all channel videos.</p>"
                )
            else:
                response = (
                    f"<p>No videos found matching <strong>\"{subject}\"</strong>.</p>"
                    f"<p>You have {total_videos} video(s) in total. "
                    f"Try rephrasing your search or browsing all videos.</p>"
                )

            return {
                **state,
                "response": response,
                "metadata": {
                    **(state.get("metadata", {})),
                    "response_type": "metadata_search",
                    "video_count": 0,
                    "total_videos": total_videos,
                    "search_subject": subject
                }
            }

        # Step 5: Query database for transcript details (conditional based on context)
        async with AsyncSessionLocal() as session:
            if channel_id:
                # Channel context - query via ChannelVideoRepository
                channel_video_repo = ChannelVideoRepository(session)
                channel_videos, _ = await channel_video_repo.list_by_channel(
                    channel_id=channel_id,
                    limit=100,  # Get all to filter by sorted_video_ids
                    offset=0
                )
                # Extract transcripts from channel videos and filter by sorted_video_ids
                transcripts = [
                    cv.transcript
                    for cv in channel_videos
                    if cv.transcript and cv.transcript.youtube_video_id in sorted_video_ids
                ]
            else:
                # Personal context - query transcripts by user_id
                query = (
                    select(Transcript)
                    .where(
                        Transcript.user_id == user_id,
                        Transcript.youtube_video_id.in_(sorted_video_ids)
                    )
                    .order_by(Transcript.created_at.desc())
                )
                result = await session.execute(query)
                transcripts = list(result.scalars().all())

        logger.info(f"Retrieved {len(transcripts)} transcript details from database")

        # Step 6: Re-sort transcripts by relevance score (from Qdrant)
        # (created_at DESC is just a tiebreaker for equal scores)
        transcripts_sorted = sorted(
            transcripts,
            key=lambda t: video_avg_scores.get(t.youtube_video_id, 0.0),
            reverse=True
        )[:7]  # Ensure limit of 7 for focused results

        # Step 7: Format response as HTML list
        video_items = []
        for transcript in transcripts_sorted:
            # Format duration (seconds to minutes)
            duration_min = transcript.duration // 60 if transcript.duration else 0

            # Get language from meta_data
            language = transcript.meta_data.get("language", "Unknown")

            # Get channel name
            channel = transcript.channel_name or "Unknown channel"

            # Get relevance score
            relevance_score = video_avg_scores.get(transcript.youtube_video_id, 0.0)

            video_items.append(
                f"<li>"
                f"<strong>{transcript.title or 'Untitled Video'}</strong><br>"
                f"<small>Channel: {channel} | "
                f"Duration: {duration_min} min | "
                f"Language: {language} | "
                f"Relevance: {relevance_score:.2f}</small>"
                f"</li>"
            )

        videos_html = "\n".join(video_items)

        # Check if this is a compound query (find + summarize)
        intent = state.get("intent", "")
        if intent == "metadata_search_and_summarize":
            # User wants to find AND get info - router will auto-trigger summary
            if len(transcripts_sorted) == 1:
                cta_message = (
                    f"<p><strong>Great! I found the video you're looking for.</strong></p>"
                    f"<p><em>Generating summary...</em></p>"
                )
            else:
                cta_message = (
                    f"<p><strong>I found {len(transcripts_sorted)} matching videos.</strong></p>"
                    f"<p>Let me know which one you're interested in, and I'll help you with your questions!</p>"
                )
        else:
            # Regular search - standard message
            cta_message = f"<p>You can ask me questions about any of these videos!</p>"

        response = (
            f"<p>Found <strong>{len(transcripts_sorted)} video(s)</strong> "
            f"matching <strong>\"{subject}\"</strong>:</p>"
            f"<ol>{videos_html}</ol>"
            f"{cta_message}"
        )

        # Update state
        return {
            **state,
            "response": response,
            "metadata": {
                **(state.get("metadata", {})),
                "response_type": "metadata_search",
                "video_count": len(transcripts_sorted),
                "search_subject": subject,
                "avg_relevance_score": sum(video_avg_scores.values()) / len(video_avg_scores) if video_avg_scores else 0.0
            }
        }

    except ValueError:
        logger.error(f"Invalid user_id format: {user_id_str}")
        return {
            **state,
            "response": "<p>Error: Invalid user ID format.</p>",
            "metadata": {
                **(state.get("metadata", {})),
                "response_type": "metadata_search_error",
                "error": "invalid_user_id"
            }
        }

    except Exception as e:
        logger.exception(f"Error searching videos by subject: {e}")
        return {
            **state,
            "response": f"<p>Sorry, I encountered an error while searching for videos about \"{subject}\". Please try again.</p>",
            "metadata": {
                **(state.get("metadata", {})),
                "response_type": "metadata_search_error",
                "error": str(e)
            }
        }
