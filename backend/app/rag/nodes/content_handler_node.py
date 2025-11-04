"""
Content Handler Node for LangGraph

Unified handler that replaces 4 separate intents (qa, chitchat, metadata_search, metadata_search_and_summarize).
Always performs semantic search first, then routes based on relevance scores.

Architecture:
- High score (>0.75): Generate content from matched videos
- Medium score (0.5-0.75): Show options with preview
- Low score (<0.5): Chitchat fallback

This eliminates the need to predict user intent upfront - semantic search guides the response.
"""

from collections import defaultdict
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
from app.rag.graphs.flows.qa_flow import compiled_qa_flow
from app.rag.graphs.flows.chitchat_flow import compiled_chitchat_flow

# Configuration for content routing
CONTENT_SCORE_THRESHOLD = 0.4  # If ANY relevant content found (score >= 0.4) → generate
CONTENT_SEARCH_TOP_K = 5       # Quick search limit


async def handle_content_query(state: GraphState) -> Dict[str, Any]:
    """
    Unified content handler - replaces qa, chitchat, and metadata_search intents.

    Flow:
    1. Always perform semantic search (top_k=5)
    2. Route based on top score (two outcomes only):
       - score >= 0.4: Content found → Generate from videos (QA flow)
       - score < 0.4: No content → Chitchat response

    Args:
        state: Current graph state containing:
            - user_query: The user's input text
            - user_id: UUID string for the user
            - conversation_history: List of previous messages
            - channel_id (optional): Channel context
            - collection_name (optional): Qdrant collection

    Returns:
        Updated state with:
            - response: Generated HTML response
            - metadata: Routing decision metadata

    Example:
        # "napisz cos o mitach programowania z AI"
        # → search finds myths video (score 0.74)
        # → auto-generates summary via QA flow

        # "tell me about FastAPI"
        # → search finds videos (score 0.62)
        # → auto-generates answer from top videos

        # "hello how are you?"
        # → search finds nothing relevant (score 0.15)
        # → chitchat: "Hi! I'm here to help with your YouTube videos"
    """
    user_query = state.get("user_query", "")
    user_id_str = state.get("user_id", "")
    user_id = UUID(user_id_str)

    # Extract channel context if present
    channel_id_str = state.get("channel_id")
    collection_name = state.get("collection_name")
    channel_id = UUID(channel_id_str) if channel_id_str else None

    logger.info(
        f"Content handler processing query: '{user_query[:50]}...' "
        f"(channel={channel_id_str or 'personal'})"
    )

    try:
        # STEP 1: Always perform semantic search first
        embedding_service = EmbeddingService()
        embeddings = await embedding_service.generate_embeddings([user_query], user_id=user_id_str)
        query_vector = embeddings[0]
        logger.debug(f"Generated embedding (dim={len(query_vector)})")

        # Perform quick semantic search
        qdrant_service = QdrantService()
        if channel_id and collection_name:
            logger.debug(f"Searching channel collection: {collection_name}")
            results = await qdrant_service.search(
                query_vector=query_vector,
                user_id=user_id_str,
                channel_id=channel_id_str,
                collection_name=collection_name,
                top_k=CONTENT_SEARCH_TOP_K
            )
        else:
            logger.debug(f"Searching personal collection for user: {user_id_str}")
            results = await qdrant_service.search(
                query_vector=query_vector,
                user_id=user_id_str,
                top_k=CONTENT_SEARCH_TOP_K
            )

        # STEP 2: Route based on top score (two outcomes only: generate or chitchat)
        top_score = results[0].get("score", 0.0) if results else 0.0
        logger.info(f"Content search top score: {top_score:.3f}")

        if top_score >= CONTENT_SCORE_THRESHOLD:
            # CONTENT FOUND: Generate from videos (always generate if content exists)
            logger.info(
                f"Content found (score={top_score:.3f}) - routing to QA generation"
            )

            # Group by video and calculate average scores
            video_scores = defaultdict(list)
            for result in results:
                payload = result.get("payload", {})
                youtube_video_id = payload.get("youtube_video_id")
                score = result.get("score", 0.0)
                if youtube_video_id:
                    video_scores[youtube_video_id].append(score)

            video_avg_scores = {
                video_id: sum(scores) / len(scores)
                for video_id, scores in video_scores.items()
            }

            sorted_video_ids = sorted(
                video_avg_scores.keys(),
                key=lambda vid: video_avg_scores[vid],
                reverse=True
            )

            logger.info(f"Found {len(sorted_video_ids)} relevant videos for generation")

            # Route to QA flow for generation
            qa_state = {
                **state,
                "intent": "qa"  # QA flow will handle generation
            }
            result = await compiled_qa_flow.ainvoke(qa_state)

            # Add content handler metadata
            result["metadata"]["content_handler"] = {
                "routing_decision": "generate",
                "top_score": top_score,
                "videos_found": len(sorted_video_ids)
            }

            return result

        else:
            # NO CONTENT: Score too low → Chitchat
            logger.info(
                f"Low score (score={top_score:.3f}) - routing to chitchat"
            )

            chitchat_state = {
                **state,
                "intent": "chitchat"
            }
            result = await compiled_chitchat_flow.ainvoke(chitchat_state)

            # Add content handler metadata
            result["metadata"]["content_handler"] = {
                "routing_decision": "chitchat",
                "top_score": top_score,
                "threshold_used": "low"
            }

            return result

    except Exception as e:
        logger.exception(f"Error in content handler: {e}")

        # Fallback to chitchat on error
        try:
            chitchat_state = {
                **state,
                "intent": "chitchat"
            }
            result = await compiled_chitchat_flow.ainvoke(chitchat_state)
            result["metadata"]["content_handler_error"] = str(e)
            return result
        except Exception as fallback_error:
            logger.exception(f"Chitchat fallback also failed: {fallback_error}")
            return {
                **state,
                "response": "<p>Sorry, I encountered an error processing your request. Please try again.</p>",
                "metadata": {
                    **(state.get("metadata", {})),
                    "response_type": "error",
                    "error": str(e),
                    "fallback_error": str(fallback_error)
                }
            }
