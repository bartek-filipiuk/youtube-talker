"""
Result Ranker Node for LangGraph (Phase 3 - Intelligent Search Pipeline)

Re-ranks search results using LLM understanding of relevance.
Provides explainability for ranking decisions.
"""

from typing import Any, Dict

from loguru import logger

from app.rag.utils.llm_client import LLMClient
from app.rag.utils.prompt_loader import render_prompt
from app.rag.utils.state import GraphState
from app.schemas.llm_responses import ResultRanking


async def rank_search_results(state: GraphState) -> Dict[str, Any]:
    """
    Result ranker node that re-ranks search results using LLM.

    Takes search results from smart search executor and re-ranks them
    using LLM understanding of:
    - Exact title matches vs semantic matches
    - Topic relevance and coverage
    - Query intent alignment
    - Content specificity

    Args:
        state: Current graph state containing:
            - user_query: The user's input text
            - search_results: List of search results from smart search
            - query_analysis: QueryAnalysis object (optional but recommended)
            - config: Optional configuration (model selection)
            - user_id: User ID for cost tracking

    Returns:
        Updated state with:
            - search_results: Re-ranked list (most relevant first)
            - metadata: Updated with ranking metadata

    Example:
        state = {
            "user_query": "napisz streszczenie dla Claude Code w CI/CD",
            "search_results": [{"youtube_video_id": "abc", "title": "...", "score": 0.48, ...}, ...],
            "query_analysis": QueryAnalysis(...),
            "user_id": "user123"
        }
        updated_state = await rank_search_results(state)
        # updated_state["search_results"] is now LLM-ranked
    """
    user_query = state.get("user_query", "")
    user_id = state.get("user_id")
    search_results = state.get("search_results", [])
    query_analysis = state.get("query_analysis")
    config = state.get("config", {})
    model = config.get("model", "claude-haiku-4.5")

    # Skip ranking if no results or only 1 result
    if len(search_results) <= 1:
        logger.info(f"Skipping LLM re-ranking: {len(search_results)} result(s) (no need to rank)")
        return {
            **state,
            "metadata": {
                **(state.get("metadata", {})),
                "ranking_skipped": True,
                "ranking_reason": "1 or fewer results"
            }
        }

    logger.info(
        f"Re-ranking {len(search_results)} search results using LLM "
        f"for query: '{user_query[:50]}...' (model={model})"
    )

    # Render prompt template
    prompt = render_prompt(
        "result_ranker.jinja2",
        user_query=user_query,
        search_results=search_results,
        query_analysis=query_analysis
    )

    # Call LLM for structured ranking output
    llm_client = LLMClient()
    ranking = await llm_client.ainvoke_structured(
        prompt=prompt,
        schema=ResultRanking,
        model=model,
        user_id=user_id,
        temperature=0.2  # Low temperature for consistent ranking
    )

    logger.info(
        f"LLM ranking completed: {len(ranking.ranked_videos)} videos ranked, "
        f"overall_confidence={ranking.overall_confidence:.2f}"
    )
    logger.debug(f"Ranking strategy: {ranking.ranking_strategy}")

    # Log top 3 ranked results
    for idx, video in enumerate(ranking.ranked_videos[:3], 1):
        logger.info(
            f"  {idx}. {video.youtube_video_id} "
            f"(LLM score: {video.relevance_score:.2f}, "
            f"matches: {video.key_matches})"
        )
        logger.debug(f"     Reasoning: {video.reasoning}")

    # Re-order search_results based on LLM ranking and enrich with LLM metadata
    ranked_search_results = []
    for video_ranking in ranking.ranked_videos:
        # Find the original search result
        original_result = next(
            (r for r in search_results if r["youtube_video_id"] == video_ranking.youtube_video_id),
            None
        )
        if original_result:
            # Enrich with LLM ranking metadata
            enriched_result = {
                **original_result,
                "llm_relevance_score": video_ranking.relevance_score,
                "llm_reasoning": video_ranking.reasoning,
                "llm_key_matches": video_ranking.key_matches,
                "original_score": original_result["score"],  # Preserve smart search score
                "score": video_ranking.relevance_score  # Use LLM score as new score
            }
            ranked_search_results.append(enriched_result)

    # Log results if we have any
    if ranked_search_results:
        logger.info(
            f"Search results re-ranked: {len(ranked_search_results)} videos "
            f"(top LLM score: {ranked_search_results[0]['llm_relevance_score']:.2f})"
        )
    else:
        logger.warning("LLM re-ranking produced empty results - returning original search results")
        return {
            **state,
            "metadata": {
                **(state.get("metadata", {})),
                "llm_ranking_applied": False,
                "llm_ranking_error": "Empty ranking from LLM"
            }
        }

    # Update state
    return {
        **state,
        "search_results": ranked_search_results,
        "metadata": {
            **(state.get("metadata", {})),
            "llm_ranking_applied": True,
            "llm_ranking_confidence": ranking.overall_confidence,
            "llm_ranking_strategy": ranking.ranking_strategy,
            "videos_re_ranked": len(ranked_search_results)
        }
    }
