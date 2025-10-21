"""Unit tests for LLMClient."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from app.rag.utils.llm_client import LLMClient
from app.schemas.llm_responses import IntentClassification, RelevanceGrade


class TestLLMClient:
    """Unit tests for LLMClient class."""

    @pytest.mark.asyncio
    async def test_llm_client_initialization(self):
        """Test LLMClient initializes with correct config."""
        client = LLMClient()

        assert client.claude_model == "anthropic/claude-haiku-4.5"
        assert client.gemini_model == "google/gemini-2.5-flash"
        assert client.timeout == 30.0
        assert str(client.client.base_url).rstrip("/") == "https://openrouter.ai/api/v1"

    @pytest.mark.asyncio
    async def test_ainvoke_claude_success(self):
        """Test successful Claude text generation."""
        client = LLMClient()

        # Create mock response
        mock_choice = MagicMock()
        mock_choice.message.content = "FastAPI is a modern web framework for Python."

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        # Mock the AsyncOpenAI client
        with patch.object(client.client.chat.completions, "create", new=AsyncMock(return_value=mock_response)):
            response = await client.ainvoke_claude("What is FastAPI?")

        assert response == "FastAPI is a modern web framework for Python."
        assert isinstance(response, str)

    @pytest.mark.asyncio
    async def test_ainvoke_claude_with_system_prompt(self):
        """Test Claude call with custom system prompt."""
        client = LLMClient()

        mock_choice = MagicMock()
        mock_choice.message.content = "Dependency injection in FastAPI..."

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_create = AsyncMock(return_value=mock_response)

        with patch.object(client.client.chat.completions, "create", new=mock_create):
            response = await client.ainvoke_claude(
                prompt="Explain DI",
                system_prompt="You are a Python expert"
            )

        # Verify system prompt was included
        call_args = mock_create.call_args
        messages = call_args[1]["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are a Python expert"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "Explain DI"

    @pytest.mark.asyncio
    async def test_ainvoke_claude_with_custom_params(self):
        """Test Claude call with custom max_tokens and temperature."""
        client = LLMClient()

        mock_choice = MagicMock()
        mock_choice.message.content = "Response"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_create = AsyncMock(return_value=mock_response)

        with patch.object(client.client.chat.completions, "create", new=mock_create):
            await client.ainvoke_claude(
                prompt="Test",
                max_tokens=1000,
                temperature=0.5
            )

        # Verify parameters were passed
        call_args = mock_create.call_args
        assert call_args[1]["max_tokens"] == 1000
        assert call_args[1]["temperature"] == 0.5
        assert call_args[1]["timeout"] == 30.0

    @pytest.mark.asyncio
    async def test_ainvoke_gemini_structured_success(self):
        """Test successful Gemini structured output with RelevanceGrade."""
        client = LLMClient()

        # Create mock response with valid JSON
        mock_json = json.dumps({
            "is_relevant": True,
            "reasoning": "The chunk discusses FastAPI routing which is relevant to the query."
        })

        mock_choice = MagicMock()
        mock_choice.message.content = mock_json

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch.object(client.client.chat.completions, "create", new=AsyncMock(return_value=mock_response)):
            grade = await client.ainvoke_gemini_structured(
                prompt="Is this chunk relevant?",
                schema=RelevanceGrade
            )

        assert isinstance(grade, RelevanceGrade)
        assert grade.is_relevant is True
        assert "FastAPI routing" in grade.reasoning

    @pytest.mark.asyncio
    async def test_ainvoke_gemini_structured_intent_classification(self):
        """Test Gemini structured output with IntentClassification schema."""
        client = LLMClient()

        mock_json = json.dumps({
            "intent": "qa",
            "confidence": 0.92,
            "reasoning": "User is asking a factual question that requires knowledge retrieval."
        })

        mock_choice = MagicMock()
        mock_choice.message.content = mock_json

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch.object(client.client.chat.completions, "create", new=AsyncMock(return_value=mock_response)):
            intent = await client.ainvoke_gemini_structured(
                prompt="Classify this query",
                schema=IntentClassification
            )

        assert isinstance(intent, IntentClassification)
        assert intent.intent == "qa"
        assert 0.0 <= intent.confidence <= 1.0
        assert len(intent.reasoning) > 0

    @pytest.mark.asyncio
    async def test_ainvoke_gemini_invalid_json(self):
        """Test Gemini handling of invalid JSON response."""
        client = LLMClient()

        # Return invalid JSON
        mock_choice = MagicMock()
        mock_choice.message.content = "This is not JSON {invalid"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch.object(client.client.chat.completions, "create", new=AsyncMock(return_value=mock_response)):
            with pytest.raises(ValueError, match="invalid JSON"):
                await client.ainvoke_gemini_structured(
                    prompt="Test",
                    schema=RelevanceGrade
                )

    @pytest.mark.asyncio
    async def test_ainvoke_gemini_schema_validation_failure(self):
        """Test Gemini handling of JSON that doesn't match schema."""
        client = LLMClient()

        # Return JSON with wrong fields
        mock_json = json.dumps({
            "wrong_field": "value",
            "another_wrong_field": 123
        })

        mock_choice = MagicMock()
        mock_choice.message.content = mock_json

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch.object(client.client.chat.completions, "create", new=AsyncMock(return_value=mock_response)):
            with pytest.raises(ValidationError):
                await client.ainvoke_gemini_structured(
                    prompt="Test",
                    schema=RelevanceGrade
                )

    @pytest.mark.asyncio
    async def test_ainvoke_gemini_uses_json_object_format(self):
        """Test Gemini uses response_format json_object."""
        client = LLMClient()

        mock_json = json.dumps({"is_relevant": False, "reasoning": "Not related"})
        mock_choice = MagicMock()
        mock_choice.message.content = mock_json

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_create = AsyncMock(return_value=mock_response)

        with patch.object(client.client.chat.completions, "create", new=mock_create):
            await client.ainvoke_gemini_structured(
                prompt="Test",
                schema=RelevanceGrade
            )

        # Verify response_format was set
        call_args = mock_create.call_args
        assert call_args[1]["response_format"] == {"type": "json_object"}
        assert call_args[1]["model"] == "google/gemini-2.5-flash"
        assert call_args[1]["temperature"] == 0.3  # Default for structured output

    @pytest.mark.asyncio
    async def test_ainvoke_gemini_includes_schema_in_system_prompt(self):
        """Test Gemini system prompt includes schema definition."""
        client = LLMClient()

        mock_json = json.dumps({"is_relevant": True, "reasoning": "Relevant"})
        mock_choice = MagicMock()
        mock_choice.message.content = mock_json

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_create = AsyncMock(return_value=mock_response)

        with patch.object(client.client.chat.completions, "create", new=mock_create):
            await client.ainvoke_gemini_structured(
                prompt="User query",
                schema=RelevanceGrade
            )

        # Verify system prompt contains schema
        call_args = mock_create.call_args
        messages = call_args[1]["messages"]
        system_message = messages[0]

        assert system_message["role"] == "system"
        assert "valid JSON" in system_message["content"]
        assert "schema" in system_message["content"].lower()
        # Schema JSON should be in the system prompt
        assert "is_relevant" in system_message["content"]
