"""
LangGraph State Definition

Defines the state schema used across all RAG graph nodes.
State is passed between nodes and modified as the graph executes.
"""

from typing import Dict, List, Optional, TypedDict


class GraphState(TypedDict, total=False):
    """
    State schema for LangGraph RAG flows.

    Attributes:
        user_query: The original user question/request
        user_id: UUID of the user making the request (for data isolation)
        conversation_history: Last N messages for context (list of dicts with role, content)
        intent: Classified intent ("chitchat" | "qa" | "linkedin")
        retrieved_chunks: Raw chunks from Qdrant search (before grading)
        graded_chunks: Filtered chunks after relevance grading
        response: Final generated response text
        metadata: Additional metadata (sources used, confidence, etc.)

    Notes:
        - total=False allows partial state updates (not all fields required)
        - State is mutable and passed by reference through the graph
        - Each node reads from state and updates it
    """

    # Input fields (set before graph execution)
    user_query: str
    user_id: str
    conversation_history: List[Dict[str, str]]

    # Intermediate fields (set during graph execution)
    intent: Optional[str]
    retrieved_chunks: Optional[List[Dict]]
    graded_chunks: Optional[List[Dict]]

    # Output fields (set at graph completion)
    response: Optional[str]
    metadata: Optional[Dict]
