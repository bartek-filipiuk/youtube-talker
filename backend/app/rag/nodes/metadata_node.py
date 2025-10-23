"""
Metadata Node for LangGraph

Handles metadata queries about available videos and system information.
Queries database for user's transcripts and returns formatted list.
"""

import logging
from typing import Dict, Any
from uuid import UUID

from app.rag.utils.state import GraphState
from app.db.session import AsyncSessionLocal
from app.db.repositories.transcript_repo import TranscriptRepository

logger = logging.getLogger(__name__)


async def get_user_videos(state: GraphState) -> Dict[str, Any]:
    """
    Metadata node that lists user's available videos.

    Queries the database for all transcripts belonging to the user
    and formats them into an HTML response with video details.

    Args:
        state: Current graph state containing:
            - user_id: UUID of the user (for data isolation)
            - user_query: The original query (for logging)
            - intent: Should be "metadata"

    Returns:
        Updated state with:
            - response: HTML-formatted list of videos
            - metadata: Dict with video count and response type

    Example:
        state = {
            "user_query": "What videos do I have?",
            "user_id": "user-uuid-here",
            "intent": "metadata"
        }
        updated_state = await get_user_videos(state)
        # updated_state["response"] contains HTML list of videos
    """
    user_id_str = state.get("user_id", "")
    user_query = state.get("user_query", "")

    logger.info(f"Fetching video metadata for user {user_id_str}")

    try:
        # Convert user_id string to UUID
        user_id = UUID(user_id_str)

        # Create database session
        async with AsyncSessionLocal() as session:
            transcript_repo = TranscriptRepository(session)

            # Query user's transcripts
            transcripts = await transcript_repo.list_by_user(user_id)

            logger.info(f"Found {len(transcripts)} transcript(s) for user {user_id}")

            # Format response
            if not transcripts:
                response = (
                    "<p>You don't have any videos loaded yet.</p>"
                    "<p>To get started, use the <strong>transcript ingestion API</strong> "
                    "to add YouTube videos to your knowledge base.</p>"
                )
            else:
                # Build HTML list
                video_items = []
                for transcript in transcripts:
                    # Format duration (seconds to minutes)
                    duration_min = transcript.duration // 60 if transcript.duration else 0

                    # Get chunk count from meta_data if available
                    chunk_count = transcript.meta_data.get("chunk_count", "N/A")

                    # Get language from meta_data
                    language = transcript.meta_data.get("language", "Unknown")

                    # Get channel name
                    channel = transcript.channel_name or "Unknown channel"

                    video_items.append(
                        f"<li>"
                        f"<strong>{transcript.title or 'Untitled Video'}</strong><br>"
                        f"<small>Channel: {channel} | "
                        f"Duration: {duration_min} min | "
                        f"Language: {language} | "
                        f"Chunks: {chunk_count}</small>"
                        f"</li>"
                    )

                videos_html = "\n".join(video_items)

                response = (
                    f"<p>You have <strong>{len(transcripts)} video(s)</strong> "
                    f"loaded in your knowledge base:</p>"
                    f"<ol>{videos_html}</ol>"
                    f"<p>You can ask me questions about any of these videos!</p>"
                )

            # Update state
            return {
                **state,
                "response": response,
                "metadata": {
                    **(state.get("metadata", {})),
                    "response_type": "metadata",
                    "video_count": len(transcripts)
                }
            }

    except ValueError as e:
        logger.error(f"Invalid user_id format: {user_id_str}")
        return {
            **state,
            "response": "<p>Error: Invalid user ID format.</p>",
            "metadata": {
                **(state.get("metadata", {})),
                "response_type": "metadata_error",
                "error": "invalid_user_id"
            }
        }

    except Exception as e:
        logger.error(f"Error fetching video metadata: {e}", exc_info=True)
        return {
            **state,
            "response": "<p>Sorry, I encountered an error while fetching your videos. Please try again.</p>",
            "metadata": {
                **(state.get("metadata", {})),
                "response_type": "metadata_error",
                "error": str(e)
            }
        }
