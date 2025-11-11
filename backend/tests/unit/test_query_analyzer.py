"""Unit tests for Query Analyzer node (Phase 1 - Intelligent Search)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from app.rag.nodes.query_analyzer_node import analyze_query
from app.rag.utils.state import GraphState
from app.schemas.llm_responses import QueryAnalysis


# Override the autouse database fixture to do nothing for these tests
# Query analyzer tests don't need database access (only mock LLM calls)
@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_test_db():
    """Override global DB fixture - query analyzer tests don't need database."""
    yield


# Mark all tests in this file as async
pytestmark = pytest.mark.asyncio


class TestQueryAnalyzerNode:
    """Unit tests for analyze_query() node."""

    async def test_analyze_title_query_polish(self):
        """Analyzer correctly extracts title keywords from Polish query."""
        state: GraphState = {
            "user_query": "napisz streszczenie dla Miliony nowych komórek MÓZGU i mniejsze ryzyko DEMENCJI",
            "user_id": "user123",
            "conversation_history": [],
            "config": {}
        }

        # Mock LLM client to return query analysis
        mock_llm_client = MagicMock()
        mock_llm_client.ainvoke_structured = AsyncMock(
            return_value=QueryAnalysis(
                title_keywords=["Miliony nowych komórek MÓZGU", "mniejsze ryzyko DEMENCJI"],
                topic_keywords=["neurogeneza", "mózg", "demencja", "zdrowie"],
                alternative_phrasings=[
                    "podsumowanie filmu o nowych komórkach mózgu",
                    "streszczenie wideo o neurogenezie i demencji",
                    "film o redukcji ryzyka demencji"
                ],
                query_intent="summary",
                confidence=0.95,
                reasoning="User wants summary of specific video with clear title mention."
            )
        )

        with patch("app.rag.nodes.query_analyzer_node.LLMClient", return_value=mock_llm_client):
            result_state = await analyze_query(state)

        # Verify query analysis
        analysis = result_state["query_analysis"]
        assert isinstance(analysis, QueryAnalysis)
        assert analysis.title_keywords == ["Miliony nowych komórek MÓZGU", "mniejsze ryzyko DEMENCJI"]
        assert "neurogeneza" in analysis.topic_keywords
        assert len(analysis.alternative_phrasings) == 3
        assert analysis.query_intent == "summary"
        assert analysis.confidence == 0.95

        # Verify metadata
        assert result_state["metadata"]["query_analysis_confidence"] == 0.95
        assert result_state["metadata"]["query_analysis_intent"] == "summary"
        assert result_state["metadata"]["has_title_keywords"] is True
        assert result_state["metadata"]["has_topic_keywords"] is True

        # Verify LLM called correctly
        mock_llm_client.ainvoke_structured.assert_called_once()
        call_args = mock_llm_client.ainvoke_structured.call_args
        assert call_args.kwargs["schema"] == QueryAnalysis
        assert call_args.kwargs["temperature"] == 0.3

    @pytest.mark.asyncio
    async def test_analyze_topic_question_polish(self):
        """Analyzer correctly extracts topic keywords from Polish question."""
        state: GraphState = {
            "user_query": "czym jest cursor i jak działa?",
            "user_id": "user123",
            "conversation_history": [],
            "config": {}
        }

        # Mock LLM client
        mock_llm_client = MagicMock()
        mock_llm_client.ainvoke_structured = AsyncMock(
            return_value=QueryAnalysis(
                title_keywords=[],  # No title mentioned
                topic_keywords=["cursor", "AI", "edytor kodu", "narzędzie programistyczne"],
                alternative_phrasings=[
                    "co to jest cursor",
                    "jak używać cursor",
                    "cursor AI code editor funkcjonalność"
                ],
                query_intent="question",
                confidence=0.88,
                reasoning="Topic question about Cursor - no specific video title mentioned."
            )
        )

        with patch("app.rag.nodes.query_analyzer_node.LLMClient", return_value=mock_llm_client):
            result_state = await analyze_query(state)

        # Verify query analysis
        analysis = result_state["query_analysis"]
        assert analysis.title_keywords == []  # No title keywords for topic query
        assert "cursor" in analysis.topic_keywords
        assert "AI" in analysis.topic_keywords
        assert analysis.query_intent == "question"
        assert analysis.confidence == 0.88

        # Verify metadata flags
        assert result_state["metadata"]["has_title_keywords"] is False
        assert result_state["metadata"]["has_topic_keywords"] is True

    @pytest.mark.asyncio
    async def test_analyze_title_query_english(self):
        """Analyzer correctly extracts title keywords from English query."""
        state: GraphState = {
            "user_query": "summarize the video about Claude Code in CI/CD",
            "user_id": "user123",
            "conversation_history": [],
            "config": {}
        }

        # Mock LLM client
        mock_llm_client = MagicMock()
        mock_llm_client.ainvoke_structured = AsyncMock(
            return_value=QueryAnalysis(
                title_keywords=["Claude Code", "CI/CD"],
                topic_keywords=["Claude Code", "CI/CD", "GitHub Actions", "code review"],
                alternative_phrasings=[
                    "overview of Claude Code in continuous integration",
                    "Claude Code CI/CD integration summary",
                    "automated code review with Claude Code"
                ],
                query_intent="summary",
                confidence=0.90,
                reasoning="User wants video summary with title keywords mentioned."
            )
        )

        with patch("app.rag.nodes.query_analyzer_node.LLMClient", return_value=mock_llm_client):
            result_state = await analyze_query(state)

        # Verify query analysis
        analysis = result_state["query_analysis"]
        assert "Claude Code" in analysis.title_keywords
        assert "CI/CD" in analysis.title_keywords
        assert analysis.query_intent == "summary"

    @pytest.mark.asyncio
    async def test_analyze_search_query(self):
        """Analyzer correctly identifies search intent."""
        state: GraphState = {
            "user_query": "find videos about programming with AI",
            "user_id": "user123",
            "conversation_history": [],
            "config": {}
        }

        # Mock LLM client
        mock_llm_client = MagicMock()
        mock_llm_client.ainvoke_structured = AsyncMock(
            return_value=QueryAnalysis(
                title_keywords=[],
                topic_keywords=["programming", "AI", "artificial intelligence", "coding"],
                alternative_phrasings=[
                    "AI assisted programming videos",
                    "coding with artificial intelligence",
                    "AI tools for developers"
                ],
                query_intent="search",
                confidence=0.85,
                reasoning="Broad search query - no specific title."
            )
        )

        with patch("app.rag.nodes.query_analyzer_node.LLMClient", return_value=mock_llm_client):
            result_state = await analyze_query(state)

        # Verify search intent classification
        analysis = result_state["query_analysis"]
        assert analysis.query_intent == "search"
        assert analysis.title_keywords == []
        assert len(analysis.topic_keywords) > 0

    @pytest.mark.asyncio
    async def test_analyze_comparison_query(self):
        """Analyzer correctly identifies comparison intent."""
        state: GraphState = {
            "user_query": "porównaj cursor i github copilot",
            "user_id": "user123",
            "conversation_history": [],
            "config": {}
        }

        # Mock LLM client
        mock_llm_client = MagicMock()
        mock_llm_client.ainvoke_structured = AsyncMock(
            return_value=QueryAnalysis(
                title_keywords=[],
                topic_keywords=["cursor", "github copilot", "AI", "code editor", "porównanie"],
                alternative_phrasings=[
                    "różnice między cursor a copilot",
                    "cursor vs github copilot",
                    "który lepszy cursor czy copilot"
                ],
                query_intent="comparison",
                confidence=0.92,
                reasoning="User wants to compare two AI coding tools."
            )
        )

        with patch("app.rag.nodes.query_analyzer_node.LLMClient", return_value=mock_llm_client):
            result_state = await analyze_query(state)

        # Verify comparison intent
        analysis = result_state["query_analysis"]
        assert analysis.query_intent == "comparison"
        assert "cursor" in analysis.topic_keywords
        assert "github copilot" in analysis.topic_keywords

    @pytest.mark.asyncio
    async def test_analyze_with_conversation_history(self):
        """Analyzer uses conversation history for context."""
        state: GraphState = {
            "user_query": "napisz streszczenie",
            "user_id": "user123",
            "conversation_history": [
                {"role": "user", "content": "jakie filmy mam?"},
                {"role": "assistant", "content": "Masz 3 filmy o AI..."}
            ],
            "config": {}
        }

        # Mock LLM client
        mock_llm_client = MagicMock()
        mock_llm_client.ainvoke_structured = AsyncMock(
            return_value=QueryAnalysis(
                title_keywords=[],
                topic_keywords=["AI", "artificial intelligence"],
                alternative_phrasings=[
                    "podsumowanie filmów o AI",
                    "streszczenie wideo o sztucznej inteligencji"
                ],
                query_intent="summary",
                confidence=0.75,
                reasoning="User wants summary, likely referring to previously discussed AI videos."
            )
        )

        with patch("app.rag.nodes.query_analyzer_node.LLMClient", return_value=mock_llm_client):
            result_state = await analyze_query(state)

        # Verify analyzer works with conversation history
        analysis = result_state["query_analysis"]
        assert analysis.query_intent == "summary"
        # LLM should have received conversation history in prompt
        mock_llm_client.ainvoke_structured.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_with_custom_model(self):
        """Analyzer respects custom model selection from config."""
        state: GraphState = {
            "user_query": "test query",
            "user_id": "user123",
            "conversation_history": [],
            "config": {"model": "gemini-2.5-flash"}  # Custom model
        }

        # Mock LLM client
        mock_llm_client = MagicMock()
        mock_llm_client.ainvoke_structured = AsyncMock(
            return_value=QueryAnalysis(
                title_keywords=[],
                topic_keywords=["test"],
                alternative_phrasings=["test query alt"],
                query_intent="other",
                confidence=0.8,
                reasoning="Test query."
            )
        )

        with patch("app.rag.nodes.query_analyzer_node.LLMClient", return_value=mock_llm_client):
            result_state = await analyze_query(state)

        # Verify custom model was used
        call_args = mock_llm_client.ainvoke_structured.call_args
        assert call_args.kwargs["model"] == "gemini-2.5-flash"

        # Verify analysis completed successfully
        assert result_state["query_analysis"] is not None
        assert result_state["query_analysis"].topic_keywords == ["test"]
        assert result_state["query_analysis"].query_intent == "other"
