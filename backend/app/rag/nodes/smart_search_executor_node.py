"""
Smart Search Executor Node for LangGraph (Phase 2 - Intelligent Search Pipeline)

Executes intelligent search using query analysis results.
Implements multi-strategy search: fuzzy title matching + semantic search with query variations.
"""

from collections import defaultdict
from difflib import SequenceMatcher
from typing import Dict, Any, List
from uuid import UUID

from loguru import logger
from sqlalchemy import select

from app.db.models import Transcript
from app.db.session import AsyncSessionLocal
from app.db.repositories.channel_video_repo import ChannelVideoRepository
from app.rag.utils.state import GraphState
from app.schemas.llm_responses import QueryAnalysis
from app.services.embedding_service import EmbeddingService
from app.services.qdrant_service import QdrantService


# Configuration
FUZZY_TITLE_THRESHOLD = 0.40  # 40% similarity for title matching (lowered from 0.70 for partial keyword matches)
SEMANTIC_SEARCH_TOP_K = 10    # Increased from 5 to get more candidates


def fuzzy_match_score(query: str, title: str) -> float:
    """
    Calculate fuzzy match score between query and title.

    Uses token set ratio approach: splits both strings into words,
    compares them in any order to handle reordering.

    Args:
        query: User's search query or title keywords
        title: Video title

    Returns:
        Similarity score from 0.0 to 1.0
    """
    query_lower = query.lower().strip()
    title_lower = title.lower().strip()

    # Direct similarity
    direct_score = SequenceMatcher(None, query_lower, title_lower).ratio()

    # Token set ratio (compare words in any order)
    query_tokens = set(query_lower.split())
    title_tokens = set(title_lower.split())

    if not query_tokens or not title_tokens:
        return direct_score

    # Calculate intersection ratio
    intersection = query_tokens & title_tokens
    union = query_tokens | title_tokens
    token_score = (len(intersection) / len(union)) if union else 0

    # Return the higher of the two scores
    return max(direct_score, token_score)


async def execute_smart_search(state: GraphState) -> Dict[str, Any]:
    """
    Smart search executor that uses query analysis to find best matching videos.

    Strategy selection based on query_analysis:
    1. If title_keywords present → Try fuzzy title matching first
    2. Always try semantic search with original query + alternative phrasings
    3. Merge and deduplicate results

    Args:
        state: Current graph state containing:
            - query_analysis: QueryAnalysis object with extracted signals
            - user_query: Original user query
            - user_id: UUID string for the user
            - channel_id (optional): Channel context
            - collection_name (optional): Qdrant collection

    Returns:
        Updated state with:
            - search_results: List of dicts with video info and scores
            - metadata: Search strategy metadata

    Example:
        state = {
            "user_query": "napisz streszczenie dla 5 mitów programowania z AI",
            "query_analysis": QueryAnalysis(...),
            "user_id": "user123"
        }
        result = await execute_smart_search(state)
        # result["search_results"] contains matched videos with scores
    """
    query_analysis: QueryAnalysis = state.get("query_analysis")
    user_query = state.get("user_query", "")
    user_id_str = state.get("user_id", "")
    user_id = UUID(user_id_str)

    # Extract channel context if present
    channel_id_str = state.get("channel_id")
    collection_name = state.get("collection_name")
    channel_id = UUID(channel_id_str) if channel_id_str else None

    logger.info(
        f"Smart search executor processing: title_keywords={query_analysis.title_keywords}, "
        f"topic_keywords={query_analysis.topic_keywords[:3]}..."
    )

    # Track which strategies were used
    strategies_used = []
    all_results = {}  # youtube_video_id -> {score, title, strategy}

    try:
        # STRATEGY 1: Fuzzy Title Matching (if title keywords present)
        if query_analysis.title_keywords:
            logger.info(f"Attempting fuzzy title matching with keywords: {query_analysis.title_keywords}")
            strategies_used.append("fuzzy_title_match")

            # Get all transcripts for title matching
            async with AsyncSessionLocal() as session:
                if channel_id:
                    channel_video_repo = ChannelVideoRepository(session)
                    channel_videos, _ = await channel_video_repo.list_by_channel(
                        channel_id=channel_id,
                        limit=1000,
                        offset=0
                    )
                    transcripts = [cv.transcript for cv in channel_videos if cv.transcript]
                else:
                    query = select(Transcript).where(Transcript.user_id == user_id)
                    result = await session.execute(query)
                    transcripts = list(result.scalars().all())

            # Try to match each title keyword against video titles
            for title_keyword in query_analysis.title_keywords:
                for transcript in transcripts:
                    if transcript.title:
                        score = fuzzy_match_score(title_keyword, transcript.title)
                        if score >= FUZZY_TITLE_THRESHOLD:
                            video_id = transcript.youtube_video_id
                            # Keep best score if video already found
                            if video_id not in all_results or score > all_results[video_id]["score"]:
                                all_results[video_id] = {
                                    "score": score,
                                    "title": transcript.title,
                                    "strategy": "fuzzy_title_match",
                                    "transcript": transcript
                                }
                                logger.info(
                                    f"Title match: '{transcript.title}' "
                                    f"(score: {score:.2f}, keyword: '{title_keyword}')"
                                )

        # STRATEGY 2: Multi-Query Semantic Search
        logger.info("Executing semantic search with query variations")
        strategies_used.append("semantic_search")

        # Prepare queries: original + alternative phrasings
        search_queries = [user_query] + query_analysis.alternative_phrasings
        logger.debug(f"Searching with {len(search_queries)} query variations")

        # Generate embeddings for all queries
        embedding_service = EmbeddingService()
        embeddings = await embedding_service.generate_embeddings(search_queries, user_id=user_id_str)

        # Search with each query variation
        qdrant_service = QdrantService()
        semantic_results = []

        for idx, (query_text, query_vector) in enumerate(zip(search_queries, embeddings)):
            logger.debug(f"Search variation {idx+1}/{len(search_queries)}: '{query_text[:50]}...'")

            if channel_id and collection_name:
                results = await qdrant_service.search(
                    query_vector=query_vector,
                    user_id=user_id_str,
                    channel_id=channel_id_str,
                    collection_name=collection_name,
                    top_k=SEMANTIC_SEARCH_TOP_K
                )
            else:
                results = await qdrant_service.search(
                    query_vector=query_vector,
                    user_id=user_id_str,
                    top_k=SEMANTIC_SEARCH_TOP_K
                )

            semantic_results.extend(results)

        # Process semantic search results
        video_semantic_scores = defaultdict(list)
        for result in semantic_results:
            payload = result.get("payload", {})
            youtube_video_id = payload.get("youtube_video_id")
            score = result.get("score", 0.0)
            if youtube_video_id:
                video_semantic_scores[youtube_video_id].append(score)

        # Calculate average semantic score per video
        for video_id, scores in video_semantic_scores.items():
            avg_score = sum(scores) / len(scores)

            # Merge with title match results (boost score if both strategies found it)
            if video_id in all_results:
                # Video found by both strategies - combine scores (weighted average)
                title_score = all_results[video_id]["score"]
                combined_score = (title_score * 0.6) + (avg_score * 0.4)  # Favor title matches
                all_results[video_id]["score"] = combined_score
                all_results[video_id]["strategy"] = "title+semantic"
                logger.debug(
                    f"Combined score for {video_id}: "
                    f"title={title_score:.2f}, semantic={avg_score:.2f}, combined={combined_score:.2f}"
                )
            else:
                # Only found by semantic search
                all_results[video_id] = {
                    "score": avg_score,
                    "title": None,  # Will fetch from DB later
                    "strategy": "semantic_search",
                    "transcript": None
                }

        # Fetch transcript details for semantic-only results
        semantic_only_video_ids = [
            vid for vid, data in all_results.items()
            if data["transcript"] is None
        ]

        if semantic_only_video_ids:
            async with AsyncSessionLocal() as session:
                if channel_id:
                    channel_video_repo = ChannelVideoRepository(session)
                    channel_videos, _ = await channel_video_repo.list_by_channel(
                        channel_id=channel_id,
                        limit=100,
                        offset=0
                    )
                    transcripts = [
                        cv.transcript for cv in channel_videos
                        if cv.transcript and cv.transcript.youtube_video_id in semantic_only_video_ids
                    ]
                else:
                    query = select(Transcript).where(
                        Transcript.user_id == user_id,
                        Transcript.youtube_video_id.in_(semantic_only_video_ids)
                    )
                    result = await session.execute(query)
                    transcripts = list(result.scalars().all())

                # Update results with transcript data
                for transcript in transcripts:
                    video_id = transcript.youtube_video_id
                    if video_id in all_results:
                        all_results[video_id]["title"] = transcript.title
                        all_results[video_id]["transcript"] = transcript

        # Sort results by score (descending)
        sorted_results = sorted(
            [
                {"youtube_video_id": vid, **data}
                for vid, data in all_results.items()
            ],
            key=lambda x: x["score"],
            reverse=True
        )

        logger.info(
            f"Smart search found {len(sorted_results)} unique videos "
            f"(strategies: {', '.join(strategies_used)})"
        )

        # Log top 3 results
        for idx, result in enumerate(sorted_results[:3], 1):
            logger.info(
                f"  {idx}. {result['title']} "
                f"(score: {result['score']:.2f}, strategy: {result['strategy']})"
            )

        return {
            **state,
            "search_results": sorted_results,
            "metadata": {
                **(state.get("metadata", {})),
                "search_strategies_used": strategies_used,
                "total_videos_found": len(sorted_results),
                "top_score": sorted_results[0]["score"] if sorted_results else 0.0,
                "title_match_count": sum(1 for r in sorted_results if "title" in r["strategy"]),
                "semantic_only_count": sum(1 for r in sorted_results if r["strategy"] == "semantic_search")
            }
        }

    except Exception as e:
        logger.exception(f"Error in smart search executor: {e}")
        return {
            **state,
            "search_results": [],
            "metadata": {
                **(state.get("metadata", {})),
                "search_error": str(e),
                "search_strategies_used": strategies_used
            }
        }
