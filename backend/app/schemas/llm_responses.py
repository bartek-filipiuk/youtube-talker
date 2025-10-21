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
        max_length=200,
        description="Brief explanation (1-2 sentences) of why the chunk is/isn't relevant"
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

    Used with Gemini 2.5 Flash to classify user intent into one of three categories.
    Determines which LangGraph flow to execute.
    """

    intent: Literal["chitchat", "qa", "linkedin"] = Field(
        description="Classified user intent: chitchat (casual), qa (question-answering), linkedin (post generation)"
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
