"""
Video Load Flow

LangGraph flow for handling video loading requests.
Triggered when router classifies intent as "video_load".
"""

from typing import Dict, Any
from loguru import logger

from langgraph.graph import StateGraph, END
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import WebSocket

from app.rag.utils.state import GraphState
from app.utils.url_detector import detect_youtube_url, is_youtube_url


async def handle_video_load_node(state: GraphState) -> GraphState:
    """
    Node: Handle video loading request.

    Extracts YouTube URL from user query and prepares response.
    Actual loading will be handled by WebSocket video_loader module.

    This node just validates the URL and returns a response instructing
    the user that loading will be handled separately.

    Args:
        state: Current graph state

    Returns:
        Updated state with response and metadata
    """
    user_query = state.get("user_query", "")

    logger.info(f"Video load flow: processing query: {user_query[:100]}...")

    # Extract YouTube URL
    video_id = detect_youtube_url(user_query)

    if not video_id:
        # URL not found - return error
        state["response"] = (
            "<p>I couldn't find a valid YouTube URL in your message.</p>"
            "<p>Please paste a YouTube link like:</p>"
            "<ul>"
            "<li>https://www.youtube.com/watch?v=VIDEO_ID</li>"
            "<li>https://youtu.be/VIDEO_ID</li>"
            "</ul>"
        )
        state["metadata"] = {
            **state.get("metadata", {}),
            "response_type": "video_load_error",
            "error": "NO_URL_FOUND",
        }
        return state

    # URL found - this message signals the WebSocket handler to take over
    state["response"] = f"VIDEO_LOAD_REQUEST:{video_id}"
    state["metadata"] = {
        **state.get("metadata", {}),
        "response_type": "video_load_request",
        "video_id": video_id,
        "requires_websocket_handling": True,
    }

    logger.info(f"Video load flow: extracted video_id={video_id}")

    return state


# Build the graph
workflow = StateGraph(dict)
workflow.add_node("handle_video_load", handle_video_load_node)
workflow.set_entry_point("handle_video_load")
workflow.add_edge("handle_video_load", END)

# Compile the graph
compiled_video_load_flow = workflow.compile()

logger.info("Video load flow compiled successfully")
