"""
Video Search Node for LangGraph

Performs semantic search to find videos matching a subject.
Uses Qdrant for chunk retrieval and PostgreSQL for video metadata.
"""

from typing import Dict, Any
from collections import defaultdict
from uuid import UUID

from loguru import logger
from sqlalchemy import select

from app.rag.utils.state import GraphState
from app.services.embedding_service import EmbeddingService
from app.services.qdrant_service import QdrantService
from app.db.session import AsyncSessionLocal
from app.db.models import Transcript


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
    user_query = state.get("user_query", "")

    logger.info(f"Searching videos for subject: '{subject}' (user_id={user_id_str})")

    try:
        # Convert user_id string to UUID
        user_id = UUID(user_id_str)

        # Step 1: Generate embedding for subject
        embedding_service = EmbeddingService()
        embeddings = await embedding_service.generate_embeddings([subject], user_id=user_id_str)
        query_vector = embeddings[0]
        logger.debug(f"Generated subject embedding (dim={len(query_vector)})")

        # Step 2: Search Qdrant for matching chunks (top 100 to ensure enough unique videos)
        qdrant_service = QdrantService()
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

        # Step 4: Sort videos by score and get top 20 youtube_video_ids
        sorted_video_ids = sorted(
            video_avg_scores.keys(),
            key=lambda vid: video_avg_scores[vid],
            reverse=True  # Highest scores first
        )[:20]  # Limit to top 20

        if not sorted_video_ids:
            # No matching videos found
            async with AsyncSessionLocal() as session:
                # Get total video count for user
                count_query = select(Transcript).where(Transcript.user_id == user_id)
                count_result = await session.execute(count_query)
                total_videos = len(list(count_result.scalars().all()))

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

        # Step 5: Query database for transcript details
        async with AsyncSessionLocal() as session:
            # Query transcripts by youtube_video_ids, ordered by created_at DESC
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
        )[:20]  # Ensure limit of 20

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

        response = (
            f"<p>Found <strong>{len(transcripts_sorted)} video(s)</strong> "
            f"matching <strong>\"{subject}\"</strong>:</p>"
            f"<ol>{videos_html}</ol>"
            f"<p>You can ask me questions about any of these videos!</p>"
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

    except ValueError as e:
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
