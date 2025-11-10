"""
Pydantic Schemas for LLM Structured Outputs

Defines schemas for structured JSON responses from LLM calls.
Used with OpenRouter's response_format for Gemini models.
"""

from typing import Literal, List

from pydantic import BaseModel, ConfigDict, Field


class RelevanceGrade(BaseModel):
    """
    Schema for chunk relevance grading (Grader Node).

    Used with Gemini 2.5 Flash to determine if a chunk is relevant to the user's query.
    Binary classification: relevant or not relevant.
    """

    is_relevant: bool = Field(
        description="Whether the chunk is relevant to the user's query"
    )
    reasoning: str = Field(
        max_length=500,
        description="Brief explanation (1-2 sentences, max 500 characters) of why the chunk is/isn't relevant"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "is_relevant": True,
                "reasoning": "The chunk directly discusses FastAPI's dependency injection system, which the user asked about."
            }
        }
    )


class IntentClassification(BaseModel):
    """
    Schema for intent classification (Router Node V2 - Simplified 3-Intent System).

    Used with Claude Haiku 4.5 to classify user intent into one of three categories.
    Determines which handler to route to.
    """

    intent: Literal["system", "linkedin", "content"] = Field(
        description="Classified user intent: system (YouTube URLs, list commands), linkedin (LinkedIn post creation - must explicitly mention 'LinkedIn'), content (everything else - questions, searches, chitchat)"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score for the classification (0.0 to 1.0)"
    )
    reasoning: str = Field(
        max_length=300,
        description="Brief explanation of why this intent was chosen"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "intent": "content",
                "confidence": 0.92,
                "reasoning": "User is requesting content about a topic. Content handler will perform semantic search and route accordingly."
            }
        }
    )


class SubjectExtraction(BaseModel):
    """
    Schema for extracting subject/topic from user query (Subject Extractor Node).

    Used with Gemini 2.5 Flash to extract the main subject/topic when user
    wants to filter videos by subject (e.g., "show videos about Claude Code").
    """

    subject: str = Field(
        min_length=1,
        max_length=200,
        description="The extracted subject/topic from the user's query"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score for the extraction (0.0 to 1.0)"
    )
    reasoning: str = Field(
        max_length=300,
        description="Brief explanation of why this subject was extracted"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "subject": "Claude Code",
                "confidence": 0.95,
                "reasoning": "User explicitly asked to 'show videos about Claude Code', making the subject clear and unambiguous."
            }
        }
    )


class QueryAnalysis(BaseModel):
    """
    Schema for intelligent query analysis (Query Analyzer Node - Phase 1).

    Used to extract search signals from user queries for intelligent search pipeline.
    Analyzes user intent and extracts keywords to optimize search strategy.
    """

    title_keywords: List[str] = Field(
        default_factory=list,
        description="Keywords/phrases extracted from video title mentions (e.g., 'Miliony nowych komórek' from user mentioning that title)"
    )
    topic_keywords: List[str] = Field(
        default_factory=list,
        description="Main subject/concept keywords for semantic search (e.g., ['cursor', 'AI', 'code editor'] from 'czym jest cursor')"
    )
    alternative_phrasings: List[str] = Field(
        max_length=3,
        description="2-3 alternative ways to phrase the query for better search recall"
    )
    query_intent: Literal["summary", "question", "comparison", "search", "other"] = Field(
        description="Type of query: summary (wants video summary), question (asking about topic), comparison (comparing videos), search (finding videos), other (unclear)"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score for the analysis (0.0 to 1.0)"
    )
    reasoning: str = Field(
        max_length=400,
        description="Brief explanation of the analysis (what was extracted and why)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title_keywords": ["Miliony nowych komórek", "demencji"],
                "topic_keywords": ["neurogeneza", "mózg", "demencja"],
                "alternative_phrasings": [
                    "podsumowanie filmu o nowych komórkach mózgu",
                    "streszczenie wideo o neurogenezie",
                    "film o redukcji ryzyka demencji"
                ],
                "query_intent": "summary",
                "confidence": 0.93,
                "reasoning": "User wants summary of specific video with title keywords extracted. Topic keywords identified for semantic search backup."
            }
        }
    )


class VideoRelevance(BaseModel):
    """
    Schema for individual video relevance assessment (Result Ranker Node - Phase 3).

    Used by LLM to assess how relevant each video is to the user's query.
    Provides explainability for ranking decisions.
    """

    youtube_video_id: str = Field(
        description="The YouTube video ID being assessed"
    )
    relevance_score: float = Field(
        ge=0.0,
        le=1.0,
        description="LLM-assessed relevance score (0.0 = not relevant, 1.0 = perfectly relevant)"
    )
    reasoning: str = Field(
        max_length=300,
        description="Explanation of why this video is relevant (or not) to the query"
    )
    key_matches: List[str] = Field(
        max_length=5,
        description="Key aspects that match the query (e.g., ['title match', 'topic coverage', 'specific examples'])"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "youtube_video_id": "abc123xyz",
                "relevance_score": 0.95,
                "reasoning": "Video directly discusses Claude Code in CI/CD with GitHub Actions examples, perfectly matching the user's query for a summary.",
                "key_matches": ["exact title match", "CI/CD topic", "GitHub Actions examples"]
            }
        }
    )


class ResultRanking(BaseModel):
    """
    Schema for LLM-based result ranking (Result Ranker Node - Phase 3).

    Used to re-rank search results using LLM understanding of relevance.
    Provides ordered list with explainability for each video.
    """

    ranked_videos: List[VideoRelevance] = Field(
        max_length=10,
        description="Videos ranked by relevance (most relevant first), max 10"
    )
    overall_confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Overall confidence in the ranking (0.0 to 1.0)"
    )
    ranking_strategy: str = Field(
        max_length=400,
        description="Explanation of the ranking strategy used (which factors were prioritized)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "ranked_videos": [
                    {
                        "youtube_video_id": "abc123",
                        "relevance_score": 0.95,
                        "reasoning": "Exact title match and comprehensive coverage of the topic",
                        "key_matches": ["title match", "topic coverage"]
                    },
                    {
                        "youtube_video_id": "def456",
                        "relevance_score": 0.72,
                        "reasoning": "Related topic but focuses on different aspect",
                        "key_matches": ["related topic", "partial coverage"]
                    }
                ],
                "overall_confidence": 0.88,
                "ranking_strategy": "Prioritized exact title matches first, then semantic relevance to query topic. Videos with specific examples ranked higher than general discussions."
            }
        }
    )
