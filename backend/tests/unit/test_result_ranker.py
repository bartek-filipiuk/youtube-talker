"""Unit tests for Result Ranker node (Phase 3 - Intelligent Search)."""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from app.rag.nodes.result_ranker_node import rank_search_results
from app.rag.utils.state import GraphState
from app.schemas.llm_responses import ResultRanking, VideoRelevance, QueryAnalysis


# Override the autouse database fixture to do nothing for these tests
# Result ranker tests don't need database access (only mock LLM calls)
@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_test_db():
    """Override global DB fixture - result ranker tests don't need database."""
    yield


# Mark all tests in this file as async
pytestmark = pytest.mark.asyncio


class TestResultRankerNode:
    """Unit tests for rank_search_results() node."""

    async def test_rank_results_exact_title_match_first(self):
        """Ranker prioritizes exact title match over semantic match."""
        search_results = [
            {
                "youtube_video_id": "semantic_match_id",
                "title": "AI Tools for Developers - Complete Guide",
                "score": 0.72,
                "strategy": "semantic_search"
            },
            {
                "youtube_video_id": "exact_match_id",
                "title": "Claude Code w CI/CD - NEXT-GEN CODE REVIEW",
                "score": 0.48,
                "strategy": "fuzzy_title_match"
            }
        ]

        state: GraphState = {
            "user_query": "napisz streszczenie dla Claude Code w CI/CD",
            "user_id": "user123",
            "search_results": search_results,
            "query_analysis": QueryAnalysis(
                title_keywords=["Claude Code w CI/CD"],
                topic_keywords=["Claude Code", "CI/CD"],
                alternative_phrasings=["podsumowanie Claude Code CI/CD"],
                query_intent="summary",
                confidence=0.94,
                reasoning="User wants summary of specific video"
            ),
            "config": {}
        }

        # Mock LLM client to return ranking that prioritizes exact match
        mock_llm_client = MagicMock()
        mock_llm_client.ainvoke_structured = AsyncMock(
            return_value=ResultRanking(
                ranked_videos=[
                    VideoRelevance(
                        youtube_video_id="exact_match_id",
                        relevance_score=0.95,
                        reasoning="Exact title match with Claude Code w CI/CD",
                        key_matches=["exact title match", "CI/CD topic"]
                    ),
                    VideoRelevance(
                        youtube_video_id="semantic_match_id",
                        relevance_score=0.65,
                        reasoning="Related topic but not specific to query",
                        key_matches=["AI tools", "development"]
                    )
                ],
                overall_confidence=0.88,
                ranking_strategy="Prioritized exact title match first"
            )
        )

        with patch("app.rag.nodes.result_ranker_node.LLMClient", return_value=mock_llm_client):
            result_state = await rank_search_results(state)

        # Verify re-ranking
        ranked_results = result_state["search_results"]
        assert len(ranked_results) == 2
        assert ranked_results[0]["youtube_video_id"] == "exact_match_id"
        assert ranked_results[0]["llm_relevance_score"] == 0.95
        assert ranked_results[0]["score"] == 0.95  # LLM score becomes new score
        assert ranked_results[0]["original_score"] == 0.48  # Preserved
        assert "exact title match" in ranked_results[0]["llm_key_matches"]

        # Verify metadata
        assert result_state["metadata"]["llm_ranking_applied"] is True
        assert result_state["metadata"]["llm_ranking_confidence"] == 0.88
        assert result_state["metadata"]["videos_re_ranked"] == 2

    async def test_rank_results_topic_relevance(self):
        """Ranker correctly ranks by topic relevance when no exact title match."""
        search_results = [
            {
                "youtube_video_id": "video1",
                "title": "General Programming Tips",
                "score": 0.55,
                "strategy": "semantic_search"
            },
            {
                "youtube_video_id": "video2",
                "title": "AI Impact on Programmers - Research Study",
                "score": 0.67,
                "strategy": "semantic_search"
            },
            {
                "youtube_video_id": "video3",
                "title": "Programming Tools Overview",
                "score": 0.49,
                "strategy": "semantic_search"
            }
        ]

        state: GraphState = {
            "user_query": "jak wpływa AI na programistów?",
            "user_id": "user123",
            "search_results": search_results,
            "query_analysis": QueryAnalysis(
                title_keywords=[],
                topic_keywords=["AI", "programiści", "wpływ"],
                alternative_phrasings=["AI impact on developers"],
                query_intent="question",
                confidence=0.89,
                reasoning="Question about AI impact"
            ),
            "config": {}
        }

        # Mock LLM to rank by topic relevance
        mock_llm_client = MagicMock()
        mock_llm_client.ainvoke_structured = AsyncMock(
            return_value=ResultRanking(
                ranked_videos=[
                    VideoRelevance(
                        youtube_video_id="video2",
                        relevance_score=0.91,
                        reasoning="Directly addresses AI impact on programmers with research",
                        key_matches=["AI impact", "programmers", "research data"]
                    ),
                    VideoRelevance(
                        youtube_video_id="video1",
                        relevance_score=0.42,
                        reasoning="General programming tips, not specific to AI",
                        key_matches=["programming"]
                    ),
                    VideoRelevance(
                        youtube_video_id="video3",
                        relevance_score=0.38,
                        reasoning="Overview of tools, tangentially related",
                        key_matches=["programming tools"]
                    )
                ],
                overall_confidence=0.85,
                ranking_strategy="Ranked by topic relevance to AI impact query"
            )
        )

        with patch("app.rag.nodes.result_ranker_node.LLMClient", return_value=mock_llm_client):
            result_state = await rank_search_results(state)

        # Verify video2 ranked first
        ranked_results = result_state["search_results"]
        assert ranked_results[0]["youtube_video_id"] == "video2"
        assert ranked_results[0]["llm_relevance_score"] == 0.91
        assert ranked_results[1]["youtube_video_id"] == "video1"
        assert ranked_results[2]["youtube_video_id"] == "video3"

    async def test_skip_ranking_single_result(self):
        """Ranker skips LLM call when only 1 result (no need to rank)."""
        search_results = [
            {
                "youtube_video_id": "only_video",
                "title": "Single Result",
                "score": 0.85,
                "strategy": "semantic_search"
            }
        ]

        state: GraphState = {
            "user_query": "test query",
            "user_id": "user123",
            "search_results": search_results,
            "config": {}
        }

        # Should NOT call LLM at all
        mock_llm_client = MagicMock()
        mock_llm_client.ainvoke_structured = AsyncMock()

        with patch("app.rag.nodes.result_ranker_node.LLMClient", return_value=mock_llm_client):
            result_state = await rank_search_results(state)

        # Verify LLM NOT called
        mock_llm_client.ainvoke_structured.assert_not_called()

        # Verify ranking skipped
        assert result_state["metadata"]["ranking_skipped"] is True
        assert result_state["metadata"]["ranking_reason"] == "1 or fewer results"

        # Results unchanged
        assert result_state["search_results"] == search_results

    async def test_skip_ranking_no_results(self):
        """Ranker skips LLM call when no results."""
        state: GraphState = {
            "user_query": "test query",
            "user_id": "user123",
            "search_results": [],
            "config": {}
        }

        mock_llm_client = MagicMock()
        mock_llm_client.ainvoke_structured = AsyncMock()

        with patch("app.rag.nodes.result_ranker_node.LLMClient", return_value=mock_llm_client):
            result_state = await rank_search_results(state)

        # LLM NOT called
        mock_llm_client.ainvoke_structured.assert_not_called()

        # Ranking skipped
        assert result_state["metadata"]["ranking_skipped"] is True

    async def test_ranker_preserves_original_scores(self):
        """Ranker preserves original smart search scores."""
        search_results = [
            {
                "youtube_video_id": "vid1",
                "title": "Video 1",
                "score": 0.75,
                "strategy": "semantic_search"
            },
            {
                "youtube_video_id": "vid2",
                "title": "Video 2",
                "score": 0.60,
                "strategy": "fuzzy_title_match"
            }
        ]

        state: GraphState = {
            "user_query": "test query",
            "user_id": "user123",
            "search_results": search_results,
            "config": {}
        }

        mock_llm_client = MagicMock()
        mock_llm_client.ainvoke_structured = AsyncMock(
            return_value=ResultRanking(
                ranked_videos=[
                    VideoRelevance(
                        youtube_video_id="vid2",
                        relevance_score=0.88,
                        reasoning="Better relevance",
                        key_matches=["match"]
                    ),
                    VideoRelevance(
                        youtube_video_id="vid1",
                        relevance_score=0.71,
                        reasoning="Lower relevance",
                        key_matches=["partial"]
                    )
                ],
                overall_confidence=0.82,
                ranking_strategy="Test strategy"
            )
        )

        with patch("app.rag.nodes.result_ranker_node.LLMClient", return_value=mock_llm_client):
            result_state = await rank_search_results(state)

        # Verify original scores preserved
        ranked_results = result_state["search_results"]
        assert ranked_results[0]["original_score"] == 0.60  # vid2 original
        assert ranked_results[1]["original_score"] == 0.75  # vid1 original
        assert ranked_results[0]["score"] == 0.88  # New LLM score
        assert ranked_results[1]["score"] == 0.71

    async def test_ranker_with_custom_model(self):
        """Ranker respects custom model from config."""
        search_results = [
            {"youtube_video_id": "vid1", "title": "Video 1", "score": 0.5, "strategy": "semantic_search"},
            {"youtube_video_id": "vid2", "title": "Video 2", "score": 0.6, "strategy": "semantic_search"}
        ]

        state: GraphState = {
            "user_query": "test query",
            "user_id": "user123",
            "search_results": search_results,
            "config": {"model": "gemini-2.5-flash"}  # Custom model
        }

        mock_llm_client = MagicMock()
        mock_llm_client.ainvoke_structured = AsyncMock(
            return_value=ResultRanking(
                ranked_videos=[
                    VideoRelevance(youtube_video_id="vid1", relevance_score=0.8, reasoning="Good", key_matches=["a"]),
                    VideoRelevance(youtube_video_id="vid2", relevance_score=0.7, reasoning="OK", key_matches=["b"])
                ],
                overall_confidence=0.85,
                ranking_strategy="Test"
            )
        )

        with patch("app.rag.nodes.result_ranker_node.LLMClient", return_value=mock_llm_client):
            await rank_search_results(state)

        # Verify custom model used
        call_args = mock_llm_client.ainvoke_structured.call_args
        assert call_args.kwargs["model"] == "gemini-2.5-flash"

    async def test_ranker_enriches_results_with_llm_metadata(self):
        """Ranker enriches results with LLM reasoning and key matches."""
        search_results = [
            {"youtube_video_id": "vid1", "title": "Video 1", "score": 0.5, "strategy": "semantic_search"}
        ]

        state: GraphState = {
            "user_query": "test",
            "user_id": "user123",
            "search_results": search_results,
            "config": {}
        }

        # Need 2 results to trigger ranking
        search_results.append({"youtube_video_id": "vid2", "title": "Video 2", "score": 0.6, "strategy": "semantic_search"})
        state["search_results"] = search_results

        mock_llm_client = MagicMock()
        mock_llm_client.ainvoke_structured = AsyncMock(
            return_value=ResultRanking(
                ranked_videos=[
                    VideoRelevance(
                        youtube_video_id="vid1",
                        relevance_score=0.92,
                        reasoning="Excellent match with comprehensive coverage",
                        key_matches=["title match", "topic coverage", "examples"]
                    ),
                    VideoRelevance(
                        youtube_video_id="vid2",
                        relevance_score=0.65,
                        reasoning="Partial match only",
                        key_matches=["partial topic"]
                    )
                ],
                overall_confidence=0.87,
                ranking_strategy="Test strategy"
            )
        )

        with patch("app.rag.nodes.result_ranker_node.LLMClient", return_value=mock_llm_client):
            result_state = await rank_search_results(state)

        # Verify enrichment
        ranked_results = result_state["search_results"]
        assert "llm_relevance_score" in ranked_results[0]
        assert "llm_reasoning" in ranked_results[0]
        assert "llm_key_matches" in ranked_results[0]
        assert ranked_results[0]["llm_reasoning"] == "Excellent match with comprehensive coverage"
        assert "title match" in ranked_results[0]["llm_key_matches"]

    async def test_ranker_calls_llm_with_correct_parameters(self):
        """Ranker calls LLM with correct schema and temperature."""
        search_results = [
            {"youtube_video_id": "vid1", "title": "Video 1", "score": 0.5, "strategy": "semantic_search"},
            {"youtube_video_id": "vid2", "title": "Video 2", "score": 0.6, "strategy": "semantic_search"}
        ]

        state: GraphState = {
            "user_query": "test query",
            "user_id": "user123",
            "search_results": search_results,
            "config": {}
        }

        mock_llm_client = MagicMock()
        mock_llm_client.ainvoke_structured = AsyncMock(
            return_value=ResultRanking(
                ranked_videos=[
                    VideoRelevance(youtube_video_id="vid1", relevance_score=0.8, reasoning="Test", key_matches=["a"]),
                    VideoRelevance(youtube_video_id="vid2", relevance_score=0.7, reasoning="Test", key_matches=["b"])
                ],
                overall_confidence=0.85,
                ranking_strategy="Test"
            )
        )

        with patch("app.rag.nodes.result_ranker_node.LLMClient", return_value=mock_llm_client):
            await rank_search_results(state)

        # Verify LLM called correctly
        mock_llm_client.ainvoke_structured.assert_called_once()
        call_args = mock_llm_client.ainvoke_structured.call_args
        assert call_args.kwargs["schema"] == ResultRanking
        assert call_args.kwargs["temperature"] == 0.2  # Low temperature for consistent ranking
        assert call_args.kwargs["user_id"] == "user123"
