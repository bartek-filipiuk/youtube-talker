"""
System Operation Router Node for LangGraph

Routes system operations to appropriate handlers:
- YouTube URLs → video_load_flow
- List/show commands → metadata_flow
"""

import re
from typing import Any, Dict

from loguru import logger

from app.rag.utils.state import GraphState
from app.rag.graphs.flows.metadata_flow import compiled_metadata_flow
from app.rag.graphs.flows.video_load_flow import compiled_video_load_flow

# Regex pattern for YouTube URLs
YOUTUBE_URL_PATTERN = re.compile(
    r'(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})'
)


async def route_system_operation(state: GraphState) -> Dict[str, Any]:
    """
    Routes system operations to correct handler.

    System operations include:
    1. YouTube URL pasting → video_load_flow
    2. List/show videos → metadata_flow

    Args:
        state: Current graph state containing:
            - user_query: The user's input text
            - user_id: User identifier
            - conversation_history: List of previous messages

    Returns:
        Updated state with response from appropriate flow

    Example:
        # YouTube URL
        state = {"user_query": "https://www.youtube.com/watch?v=abc123", ...}
        result = await route_system_operation(state)
        # Routes to video_load_flow

        # List command
        state = {"user_query": "show my videos", ...}
        result = await route_system_operation(state)
        # Routes to metadata_flow
    """
    user_query = state.get("user_query", "")

    logger.info(f"System router processing: '{user_query[:50]}...'")

    # Check for YouTube URL
    youtube_match = YOUTUBE_URL_PATTERN.search(user_query)
    if youtube_match:
        video_id = youtube_match.group(1)
        logger.info(f"Detected YouTube URL (video_id={video_id}) - routing to video_load_flow")

        result = await compiled_video_load_flow.ainvoke(state)

        # Add system router metadata
        result["metadata"]["system_router"] = {
            "operation": "video_load",
            "video_id_detected": video_id
        }

        return result

    # Default: List/show videos → metadata_flow
    logger.info("No YouTube URL detected - routing to metadata_flow (list videos)")

    result = await compiled_metadata_flow.ainvoke(state)

    # Add system router metadata
    result["metadata"]["system_router"] = {
        "operation": "metadata_list"
    }

    return result
