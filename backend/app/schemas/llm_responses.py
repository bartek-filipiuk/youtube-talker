"""
Pydantic Schemas for LLM Structured Outputs

Defines schemas for structured JSON responses from LLM calls.
Used with OpenRouter's response_format for Gemini models.
"""

from typing import Literal

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
    Schema for intent classification (Router Node).

    Used with Gemini 2.5 Flash to classify user intent into one of seven categories.
    Determines which LangGraph flow to execute.
    """

    intent: Literal["chitchat", "qa", "linkedin", "metadata", "metadata_search", "metadata_search_and_summarize", "video_load"] = Field(
        description="Classified user intent: chitchat (casual), qa (question-answering), linkedin (post generation), metadata (system info/list all videos), metadata_search (find videos by subject), metadata_search_and_summarize (find video AND get info from it), video_load (YouTube URL detected)"
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
                "intent": "qa",
                "confidence": 0.95,
                "reasoning": "User is asking a specific factual question about FastAPI that requires retrieving information from the knowledge base."
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
