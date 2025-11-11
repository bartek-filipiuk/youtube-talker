"""Unit tests for Smart Search Executor node (Phase 2 - Intelligent Search)."""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4

from app.rag.nodes.smart_search_executor_node import execute_smart_search, fuzzy_match_score
from app.rag.utils.state import GraphState
from app.schemas.llm_responses import QueryAnalysis


# Override the autouse database fixture
@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_test_db():
    """Override global DB fixture - smart search tests use mocked DB."""
    yield


# Mark all tests as async
pytestmark = pytest.mark.asyncio


class TestFuzzyMatchScore:
    """Unit tests for fuzzy_match_score() helper function."""

    def test_exact_match(self):
        """Fuzzy match returns 1.0 for exact matches."""
        score = fuzzy_match_score("5 mitów programowania z AI", "5 mitów programowania z AI")
        assert score == 1.0

    def test_case_insensitive(self):
        """Fuzzy match is case-insensitive."""
        score = fuzzy_match_score("Cursor Setup", "cursor setup")
        assert score == 1.0

    def test_word_reorder(self):
        """Fuzzy match handles word reordering via token set ratio."""
        score = fuzzy_match_score("programowania AI mity", "mity programowania AI")
        assert score > 0.8  # High score despite different order

    def test_partial_match(self):
        """Fuzzy match scores partial matches."""
        score = fuzzy_match_score("5 mitów programowania", "5 mitów programowania z AI")
        assert 0.6 < score < 1.0  # Partial but high similarity

    def test_no_match(self):
        """Fuzzy match returns low score for unrelated strings."""
        score = fuzzy_match_score("hello world", "completely different text")
        assert score < 0.3


class TestSmartSearchExecutor:
    """Unit tests for execute_smart_search() node."""

    async def test_title_keywords_fuzzy_match(self):
        """Executor finds videos via fuzzy title matching when title keywords present."""
        # Mock transcript
        mock_transcript = MagicMock()
        mock_transcript.youtube_video_id = "video123"
        mock_transcript.title = "5 mitów programowania z AI | Podcast 10xDevs"
        mock_transcript.user_id = uuid4()

        state: GraphState = {
            "query_analysis": QueryAnalysis(
                title_keywords=["5 mitów programowania z AI"],
                topic_keywords=["mity", "programowanie", "AI"],
                alternative_phrasings=["mity AI w programowaniu"],
                query_intent="summary",
                confidence=0.92,
                reasoning="Test"
            ),
            "user_query": "napisz streszczenie dla 5 mitów programowania z AI",
            "user_id": str(uuid4()),
            "conversation_history": [],
            "config": {}
        }

        # Mock database session
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_transcript]
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()

        # Mock embedding service (won't be used if title match succeeds)
        mock_embedding_service = MagicMock()
        mock_embedding_service.generate_embeddings = AsyncMock(return_value=[[0.1] * 1536])

        # Mock Qdrant service
        mock_qdrant_service = MagicMock()
        mock_qdrant_service.search = AsyncMock(return_value=[])

        with patch("app.rag.nodes.smart_search_executor_node.AsyncSessionLocal", return_value=mock_session), \
             patch("app.rag.nodes.smart_search_executor_node.EmbeddingService", return_value=mock_embedding_service), \
             patch("app.rag.nodes.smart_search_executor_node.QdrantService", return_value=mock_qdrant_service):

            result = await execute_smart_search(state)

        # Verify title match found the video
        assert len(result["search_results"]) >= 1
        assert result["search_results"][0]["youtube_video_id"] == "video123"
        assert result["search_results"][0]["strategy"] in ["fuzzy_title_match", "title+semantic"]
        assert result["search_results"][0]["score"] >= 0.7

        # Verify metadata
        assert "fuzzy_title_match" in result["metadata"]["search_strategies_used"]
        assert result["metadata"]["total_videos_found"] >= 1

    async def test_semantic_search_no_title_keywords(self):
        """Executor uses semantic search when no title keywords present."""
        state: GraphState = {
            "query_analysis": QueryAnalysis(
                title_keywords=[],  # No title keywords
                topic_keywords=["cursor", "AI", "code editor"],
                alternative_phrasings=["co to jest cursor", "cursor AI editor"],
                query_intent="question",
                confidence=0.88,
                reasoning="Test"
            ),
            "user_query": "czym jest cursor?",
            "user_id": str(uuid4()),
            "conversation_history": [],
            "config": {}
        }

        # Mock transcript for semantic search results
        mock_transcript = MagicMock()
        mock_transcript.youtube_video_id = "cursor_video"
        mock_transcript.title = "This Cursor Setup Changes Everything"

        # Mock embedding service
        mock_embedding_service = MagicMock()
        mock_embedding_service.generate_embeddings = AsyncMock(
            return_value=[[0.1] * 1536, [0.2] * 1536, [0.3] * 1536]  # 3 queries
        )

        # Mock Qdrant service
        mock_qdrant_service = MagicMock()
        mock_qdrant_service.search = AsyncMock(
            return_value=[
                {
                    "payload": {"youtube_video_id": "cursor_video"},
                    "score": 0.75
                }
            ]
        )

        # Mock database for fetching transcript details
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_transcript]
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()

        with patch("app.rag.nodes.smart_search_executor_node.EmbeddingService", return_value=mock_embedding_service), \
             patch("app.rag.nodes.smart_search_executor_node.QdrantService", return_value=mock_qdrant_service), \
             patch("app.rag.nodes.smart_search_executor_node.AsyncSessionLocal", return_value=mock_session):

            result = await execute_smart_search(state)

        # Verify semantic search found the video
        assert len(result["search_results"]) >= 1
        assert result["search_results"][0]["youtube_video_id"] == "cursor_video"
        assert result["search_results"][0]["strategy"] == "semantic_search"

        # Verify multiple query variations were used
        assert mock_embedding_service.generate_embeddings.call_count == 1
        call_args = mock_embedding_service.generate_embeddings.call_args
        queries = call_args[0][0]
        assert len(queries) == 3  # Original + 2 alternative phrasings

        # Verify metadata
        assert "semantic_search" in result["metadata"]["search_strategies_used"]

    async def test_combined_title_and_semantic_search(self):
        """Executor combines title matching and semantic search scores."""
        mock_transcript = MagicMock()
        mock_transcript.youtube_video_id = "video_combined"
        mock_transcript.title = "5 mitów programowania z AI"

        state: GraphState = {
            "query_analysis": QueryAnalysis(
                title_keywords=["5 mitów programowania"],
                topic_keywords=["mity", "AI"],
                alternative_phrasings=["mity programowania AI"],
                query_intent="summary",
                confidence=0.90,
                reasoning="Test"
            ),
            "user_query": "streszczenie mitów AI",
            "user_id": str(uuid4()),
            "conversation_history": [],
            "config": {}
        }

        # Mock database
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_transcript]
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()

        # Mock embedding
        mock_embedding_service = MagicMock()
        mock_embedding_service.generate_embeddings = AsyncMock(
            return_value=[[0.1] * 1536, [0.2] * 1536]
        )

        # Mock Qdrant (same video found by semantic search)
        mock_qdrant_service = MagicMock()
        mock_qdrant_service.search = AsyncMock(
            return_value=[
                {
                    "payload": {"youtube_video_id": "video_combined"},
                    "score": 0.65
                }
            ]
        )

        with patch("app.rag.nodes.smart_search_executor_node.AsyncSessionLocal", return_value=mock_session), \
             patch("app.rag.nodes.smart_search_executor_node.EmbeddingService", return_value=mock_embedding_service), \
             patch("app.rag.nodes.smart_search_executor_node.QdrantService", return_value=mock_qdrant_service):

            result = await execute_smart_search(state)

        # Verify video found with combined strategy
        assert len(result["search_results"]) >= 1
        assert result["search_results"][0]["youtube_video_id"] == "video_combined"
        assert result["search_results"][0]["strategy"] == "title+semantic"

        # Combined score should be between title score and semantic score
        combined_score = result["search_results"][0]["score"]
        assert 0.6 < combined_score < 1.0

    async def test_no_results_returns_empty(self):
        """Executor returns empty results when no videos match."""
        state: GraphState = {
            "query_analysis": QueryAnalysis(
                title_keywords=[],
                topic_keywords=["nonexistent"],
                alternative_phrasings=["nothing"],
                query_intent="search",
                confidence=0.5,
                reasoning="Test"
            ),
            "user_query": "nonexistent video",
            "user_id": str(uuid4()),
            "conversation_history": [],
            "config": {}
        }

        # Mock empty results
        mock_embedding_service = MagicMock()
        mock_embedding_service.generate_embeddings = AsyncMock(return_value=[[0.1] * 1536])

        mock_qdrant_service = MagicMock()
        mock_qdrant_service.search = AsyncMock(return_value=[])  # No results

        with patch("app.rag.nodes.smart_search_executor_node.EmbeddingService", return_value=mock_embedding_service), \
             patch("app.rag.nodes.smart_search_executor_node.QdrantService", return_value=mock_qdrant_service):

            result = await execute_smart_search(state)

        # Verify empty results
        assert result["search_results"] == []
        assert result["metadata"]["total_videos_found"] == 0
        assert result["metadata"]["top_score"] == 0.0

    async def test_results_sorted_by_score(self):
        """Executor returns results sorted by score (descending)."""
        # Mock multiple transcripts
        transcript1 = MagicMock()
        transcript1.youtube_video_id = "video1"
        transcript1.title = "Low relevance video"

        transcript2 = MagicMock()
        transcript2.youtube_video_id = "video2"
        transcript2.title = "High relevance video"

        state: GraphState = {
            "query_analysis": QueryAnalysis(
                title_keywords=[],
                topic_keywords=["test"],
                alternative_phrasings=["test query"],
                query_intent="search",
                confidence=0.8,
                reasoning="Test"
            ),
            "user_query": "test",
            "user_id": str(uuid4()),
            "conversation_history": [],
            "config": {}
        }

        # Mock embedding
        mock_embedding_service = MagicMock()
        mock_embedding_service.generate_embeddings = AsyncMock(return_value=[[0.1] * 1536])

        # Mock Qdrant with multiple results
        mock_qdrant_service = MagicMock()
        mock_qdrant_service.search = AsyncMock(
            return_value=[
                {"payload": {"youtube_video_id": "video1"}, "score": 0.3},  # Low score
                {"payload": {"youtube_video_id": "video2"}, "score": 0.9},  # High score
            ]
        )

        # Mock database
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [transcript1, transcript2]
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()

        with patch("app.rag.nodes.smart_search_executor_node.EmbeddingService", return_value=mock_embedding_service), \
             patch("app.rag.nodes.smart_search_executor_node.QdrantService", return_value=mock_qdrant_service), \
             patch("app.rag.nodes.smart_search_executor_node.AsyncSessionLocal", return_value=mock_session):

            result = await execute_smart_search(state)

        # Verify results are sorted by score (highest first)
        assert len(result["search_results"]) == 2
        assert result["search_results"][0]["youtube_video_id"] == "video2"  # High score first
        assert result["search_results"][1]["youtube_video_id"] == "video1"  # Low score second
        assert result["search_results"][0]["score"] > result["search_results"][1]["score"]
