"""Retriever node for RAG pipeline.

Generates query embedding and searches Qdrant for top-k semantically similar chunks.
Chunk text is read directly from Qdrant payload (no PostgreSQL fetch needed).
"""

from typing import Dict, List

from loguru import logger

from app.rag.utils.state import GraphState
from app.services.embedding_service import EmbeddingService
from app.services.qdrant_service import QdrantService


async def retrieve_chunks(state: GraphState) -> GraphState:
    """
    Retriever node: Generate query embedding and search Qdrant.

    Flow:
        1. Extract user_query and user_id from state
        2. Generate embedding for user_query (1536-dim vector)
        3. Search Qdrant (semantic search, top-12, user_id filtered)
        4. Extract chunk_text from Qdrant payload (no PostgreSQL fetch)
        5. Format as minimal dicts and store in state["retrieved_chunks"]

    Args:
        state: Current graph state with user_query and user_id

    Returns:
        Updated state with retrieved_chunks field:
        [
            {
                "chunk_id": str,
                "chunk_text": str,  # Read from Qdrant payload
                "chunk_index": int,
                "youtube_video_id": str,
                "score": float
            },
            ...
        ]

    State Updates:
        - state["retrieved_chunks"]: List of chunk dicts (top-12)
        - state["metadata"]["retrieval_count"]: Number of chunks retrieved

    Edge Cases:
        - Empty results: Sets retrieved_chunks=[], continues gracefully
        - No user_id: Logs warning, returns empty chunks
    """
    user_query = state.get("user_query")
    user_id = state.get("user_id")

    if not user_query or not user_id:
        logger.warning(
            f"Missing required fields: user_query={bool(user_query)}, user_id={bool(user_id)}"
        )
        state["retrieved_chunks"] = []
        if "metadata" not in state:
            state["metadata"] = {}
        state["metadata"]["retrieval_count"] = 0
        return state

    logger.info(f"Retrieving chunks for query: '{user_query[:50]}...' (user_id={user_id})")

    # Step 1: Generate query embedding
    embedding_service = EmbeddingService()
    embeddings = await embedding_service.generate_embeddings([user_query])
    query_vector = embeddings[0]  # Extract single embedding (1536-dim)
    logger.debug(f"Generated query embedding (dim={len(query_vector)})")

    # Step 2: Search Qdrant (user_id filtered)
    # Load top_k from config (loaded from database via ConfigService), fallback to 12
    config = state.get("config", {})
    top_k = config.get("top_k", 12)

    qdrant_service = QdrantService()
    qdrant_results = await qdrant_service.search(
        query_vector=query_vector,
        user_id=user_id,
        top_k=top_k,
    )
    logger.info(f"Qdrant returned {len(qdrant_results)} chunks (top_k={top_k})")

    # Step 3: Format results (chunk_text already in Qdrant payload - no PostgreSQL fetch!)
    # Defensive: Skip chunks with missing required payload fields (handles legacy data)
    retrieved_chunks = []
    for result in qdrant_results:
        payload = result.get("payload", {})

        # Check for required fields
        if not all(
            key in payload
            for key in ["chunk_text", "chunk_index", "youtube_video_id"]
        ):
            logger.warning(
                f"Skipping chunk {result.get('chunk_id', 'unknown')} - missing required payload fields"
            )
            continue

        retrieved_chunks.append(
            {
                "chunk_id": result["chunk_id"],
                "chunk_text": payload["chunk_text"],
                "chunk_index": payload["chunk_index"],
                "youtube_video_id": payload["youtube_video_id"],
                "score": result["score"],
            }
        )

    # Step 4: Update state
    state["retrieved_chunks"] = retrieved_chunks
    if "metadata" not in state:
        state["metadata"] = {}
    state["metadata"]["retrieval_count"] = len(retrieved_chunks)

    logger.info(f"Retrieved {len(retrieved_chunks)} chunks for grading")

    return state
