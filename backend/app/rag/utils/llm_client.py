"""
OpenRouter LLM Client

Unified client for LLM calls via OpenRouter API using OpenAI SDK.
Supports both text generation (Claude) and structured output (Gemini).
"""

import json
import logging
from typing import Type, TypeVar

from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

from app.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMClient:
    """
    OpenRouter LLM client with dual model support.

    Models:
        - Claude Haiku 4.5: Text generation, Q&A, content generation
        - Gemini 2.5 Flash: Structured JSON output, intent classification, grading

    Usage:
        client = LLMClient()

        # Text generation with Claude
        response = await client.ainvoke_claude("What is FastAPI?")

        # Structured output with Gemini
        grade = await client.ainvoke_gemini_structured(
            prompt="Is this relevant: ...",
            schema=RelevanceGrade
        )
    """

    def __init__(self):
        """
        Initialize OpenRouter client with OpenAI SDK.

        Configuration is loaded from app.config.settings:
            - OPENROUTER_API_KEY
            - OPENROUTER_CLAUDE_MODEL
            - OPENROUTER_GEMINI_MODEL
            - OPENROUTER_SITE_URL (optional, for rankings)
            - OPENROUTER_SITE_NAME (optional, for rankings)
        """
        self.client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=settings.OPENROUTER_API_KEY,
        )
        self.claude_model = settings.OPENROUTER_CLAUDE_MODEL
        self.gemini_model = settings.OPENROUTER_GEMINI_MODEL
        self.timeout = 30.0  # Timeout for LLM calls (seconds)

    async def ainvoke_claude(
        self,
        prompt: str,
        max_tokens: int = 2000,
        temperature: float = 0.7,
        system_prompt: str = None,
    ) -> str:
        """
        Invoke Claude Haiku 4.5 for text generation.

        Args:
            prompt: User prompt or question
            max_tokens: Maximum tokens in response (default 2000)
            temperature: Sampling temperature 0.0-1.0 (default 0.7)
            system_prompt: Optional system prompt for context

        Returns:
            Generated text response

        Raises:
            httpx.HTTPError: If API request fails
            httpx.TimeoutException: If request times out

        Example:
            response = await client.ainvoke_claude(
                prompt="Explain FastAPI dependency injection",
                system_prompt="You are a helpful Python expert"
            )
        """
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        logger.debug(
            f"Calling Claude {self.claude_model} with prompt length: {len(prompt)}"
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.claude_model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                timeout=self.timeout,
                extra_headers={
                    "HTTP-Referer": settings.OPENROUTER_SITE_URL,
                    "X-Title": settings.OPENROUTER_SITE_NAME,
                },
            )

            content = response.choices[0].message.content
            logger.debug(f"Claude response length: {len(content)}")

            return content

        except Exception as e:
            logger.error(f"Claude API call failed: {e}", exc_info=True)
            raise

    async def ainvoke_gemini_structured(
        self,
        prompt: str,
        schema: Type[T],
        temperature: float = 0.3,
    ) -> T:
        """
        Invoke Gemini 2.5 Flash with structured JSON output.

        Uses response_format={"type": "json_object"} + Pydantic validation.
        Lower temperature (0.3) for more deterministic structured outputs.

        Args:
            prompt: Prompt that includes instructions to return JSON
            schema: Pydantic model class for validation
            temperature: Sampling temperature (default 0.3 for structured output)

        Returns:
            Validated Pydantic model instance

        Raises:
            ValidationError: If response doesn't match schema
            httpx.HTTPError: If API request fails
            ValueError: If response is not valid JSON

        Example:
            grade = await client.ainvoke_gemini_structured(
                prompt="Is this chunk relevant? Respond with JSON: ...",
                schema=RelevanceGrade
            )
            print(grade.is_relevant, grade.reasoning)
        """
        # Create system prompt with schema instructions
        schema_json = json.dumps(schema.model_json_schema(), indent=2)
        system_prompt = f"""You are a data extraction assistant.
Respond with valid JSON only that matches this exact schema:

{schema_json}

Do not include explanations or additional text. Only output the JSON object."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]

        logger.debug(
            f"Calling Gemini {self.gemini_model} for {schema.__name__} structured output"
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.gemini_model,
                messages=messages,
                response_format={"type": "json_object"},  # Force JSON output
                temperature=temperature,
                timeout=self.timeout,
                extra_headers={
                    "HTTP-Referer": settings.OPENROUTER_SITE_URL,
                    "X-Title": settings.OPENROUTER_SITE_NAME,
                },
            )

            content = response.choices[0].message.content
            logger.debug(f"Gemini raw response: {content[:200]}...")

            # Parse JSON
            try:
                data = json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON from Gemini: {content}")
                raise ValueError(f"Gemini returned invalid JSON: {e}")

            # Validate against Pydantic schema
            try:
                validated = schema.model_validate(data)
                logger.debug(f"Successfully validated {schema.__name__}")
                return validated
            except ValidationError as e:
                logger.error(f"Schema validation failed for {schema.__name__}: {e}")
                logger.error(f"Received data: {data}")
                raise

        except Exception as e:
            if not isinstance(e, (ValidationError, ValueError)):
                logger.error(f"Gemini API call failed: {e}", exc_info=True)
            raise
