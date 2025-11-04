"""
OpenRouter LLM Client (LangChain Integration)

Unified client for LLM calls via OpenRouter API using LangChain ChatOpenAI.
Provides automatic LangSmith tracking, usage metadata, and cost tracking.
"""

import json
from loguru import logger
from typing import Type, TypeVar, Optional
from uuid import UUID

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, ValidationError

from app.config import settings


T = TypeVar("T", bound=BaseModel)


class LLMClient:
    """
    OpenRouter LLM client with dual model support and LangSmith integration.

    Models:
        - Claude Haiku 4.5: Text generation, Q&A, content generation
        - Gemini 2.5 Flash: Structured JSON output, intent classification, grading

    Features:
        - Automatic LangSmith cost tracking
        - Per-user usage tracking via user_id metadata
        - Token counting and usage_metadata in responses

    Usage:
        client = LLMClient()

        # Text generation with Claude (tracks user_id)
        response = await client.ainvoke_claude(
            prompt="What is FastAPI?",
            user_id=user.id
        )

        # Structured output with Gemini
        grade = await client.ainvoke_gemini_structured(
            prompt="Is this relevant: ...",
            schema=RelevanceGrade,
            user_id=user.id
        )
    """

    def __init__(self):
        """
        Initialize OpenRouter client with LangChain ChatOpenAI.

        Configuration is loaded from app.config.settings:
            - OPENROUTER_API_KEY
            - OPENROUTER_CLAUDE_MODEL
            - OPENROUTER_GEMINI_MODEL
            - OPENROUTER_SITE_URL (optional, for rankings)
            - OPENROUTER_SITE_NAME (optional, for rankings)
            - LANGSMITH_API_KEY (for cost tracking)
            - LANGSMITH_PROJECT (project name)
            - LANGSMITH_TRACING (enable/disable)
        """
        # Claude Haiku 4.5 for text generation
        self.claude = ChatOpenAI(
            model=settings.OPENROUTER_CLAUDE_MODEL,
            openai_api_key=settings.OPENROUTER_API_KEY,
            openai_api_base="https://openrouter.ai/api/v1",
            temperature=0.7,
            max_tokens=2000,
            timeout=30.0,
            default_headers={
                "HTTP-Referer": settings.OPENROUTER_SITE_URL,
                "X-Title": settings.OPENROUTER_SITE_NAME,
            },
        )

        # Claude Haiku 4.5 for structured output (intent classification, grading)
        self.claude_structured = ChatOpenAI(
            model=settings.OPENROUTER_CLAUDE_MODEL,
            openai_api_key=settings.OPENROUTER_API_KEY,
            openai_api_base="https://openrouter.ai/api/v1",
            temperature=0.3,  # Lower temp for structured output
            timeout=30.0,
            model_kwargs={"response_format": {"type": "json_object"}},
            default_headers={
                "HTTP-Referer": settings.OPENROUTER_SITE_URL,
                "X-Title": settings.OPENROUTER_SITE_NAME,
            },
        )

        # Gemini 2.5 Flash for structured output
        self.gemini = ChatOpenAI(
            model=settings.OPENROUTER_GEMINI_MODEL,
            openai_api_key=settings.OPENROUTER_API_KEY,
            openai_api_base="https://openrouter.ai/api/v1",
            temperature=0.3,  # Lower temp for structured output
            timeout=30.0,
            model_kwargs={"response_format": {"type": "json_object"}},
            default_headers={
                "HTTP-Referer": settings.OPENROUTER_SITE_URL,
                "X-Title": settings.OPENROUTER_SITE_NAME,
            },
        )

        self.claude_model = settings.OPENROUTER_CLAUDE_MODEL
        self.gemini_model = settings.OPENROUTER_GEMINI_MODEL

    async def ainvoke_claude(
        self,
        prompt: str,
        user_id: Optional[UUID] = None,
        max_tokens: int = 2000,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
    ) -> str:
        """
        Invoke Claude Haiku 4.5 for text generation with LangSmith tracking.

        Args:
            prompt: User prompt or question
            user_id: User UUID for cost tracking (passed as LangSmith metadata)
            max_tokens: Maximum tokens in response (default 2000)
            temperature: Sampling temperature 0.0-1.0 (default 0.7)
            system_prompt: Optional system prompt for context

        Returns:
            Generated text response

        Raises:
            Exception: If API request fails

        Example:
            response = await client.ainvoke_claude(
                prompt="Explain FastAPI dependency injection",
                user_id=user.id,
                system_prompt="You are a helpful Python expert"
            )

        LangSmith Tracking:
            - Automatically tracks token usage (input_tokens, output_tokens)
            - Tracks cost per call (when pricing is configured in LangSmith UI)
            - Tags calls with user_id for per-user filtering
        """
        messages = []

        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))

        messages.append(HumanMessage(content=prompt))

        logger.debug(
            f"Calling Claude {self.claude_model} with prompt length: {len(prompt)}"
            f"{f' for user_id={user_id}' if user_id else ''}"
        )

        try:
            # Configure call with user_id metadata for LangSmith
            config = {}
            if user_id:
                config = {
                    "tags": [str(user_id)],
                    "metadata": {"user_id": str(user_id)},
                }

            # Override temperature and max_tokens if different from default
            claude_with_config = self.claude
            if temperature != 0.7 or max_tokens != 2000:
                claude_with_config = self.claude.bind(
                    temperature=temperature,
                    max_tokens=max_tokens,
                )

            # Invoke Claude with LangSmith tracking
            response = await claude_with_config.ainvoke(messages, config=config)

            content = response.content

            # Log usage metadata (if available)
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                logger.debug(
                    f"Claude usage: input={response.usage_metadata.get('input_tokens', 0)} "
                    f"output={response.usage_metadata.get('output_tokens', 0)} tokens"
                )

            logger.debug(f"Claude response length: {len(content)}")

            return content

        except Exception as e:
            logger.exception(f"Claude API call failed: {e}")
            raise

    async def ainvoke_claude_structured(
        self,
        prompt: str,
        schema: Type[T],
        user_id: Optional[UUID] = None,
        temperature: float = 0.3,
    ) -> T:
        """
        Invoke Claude Haiku 4.5 with structured JSON output and LangSmith tracking.

        Uses response_format={"type": "json_object"} + Pydantic validation.
        Lower temperature (0.3) for more deterministic structured outputs.

        Args:
            prompt: Prompt that includes instructions to return JSON
            schema: Pydantic model class for validation
            user_id: User UUID for cost tracking (passed as LangSmith metadata)
            temperature: Sampling temperature (default 0.3 for structured output)

        Returns:
            Validated Pydantic model instance

        Raises:
            ValidationError: If response doesn't match schema
            Exception: If API request fails
            ValueError: If response is not valid JSON

        Example:
            classification = await client.ainvoke_claude_structured(
                prompt="Classify this query intent: ...",
                schema=IntentClassification,
                user_id=user.id
            )
            print(classification.intent, classification.confidence)

        LangSmith Tracking:
            - Automatically tracks token usage (input_tokens, output_tokens)
            - Tracks cost per call (when pricing is configured in LangSmith UI)
            - Tags calls with user_id for per-user filtering
        """
        # Create system prompt with schema instructions
        schema_json = json.dumps(schema.model_json_schema(), indent=2)
        system_prompt = f"""You are a data extraction assistant.
Respond with valid JSON only that matches this exact schema:

{schema_json}

Do not include explanations or additional text. Only output the JSON object."""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt),
        ]

        logger.debug(
            f"Calling Claude {self.claude_model} for {schema.__name__} structured output"
            f"{f' for user_id={user_id}' if user_id else ''}"
        )

        try:
            # Configure call with user_id metadata for LangSmith
            config = {}
            if user_id:
                config = {
                    "tags": [str(user_id)],
                    "metadata": {"user_id": str(user_id)},
                }

            # Override temperature if different from default
            claude_with_config = self.claude_structured
            if temperature != 0.3:
                claude_with_config = self.claude_structured.bind(temperature=temperature)

            # Invoke Claude with LangSmith tracking
            response = await claude_with_config.ainvoke(messages, config=config)

            content = response.content

            # Log usage metadata (if available)
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                usage = response.usage_metadata
                logger.debug(
                    f"Claude usage: input={usage.get('input_tokens', 0)} "
                    f"output={usage.get('output_tokens', 0)} tokens"
                )

            logger.debug(f"Claude raw response: {content[:200]}...")

            # Strip markdown code blocks if present (Claude sometimes wraps JSON in ```json ... ```)
            content_stripped = content.strip()
            if content_stripped.startswith("```json"):
                content_stripped = content_stripped[7:]  # Remove ```json
            if content_stripped.startswith("```"):
                content_stripped = content_stripped[3:]  # Remove ```
            if content_stripped.endswith("```"):
                content_stripped = content_stripped[:-3]  # Remove closing ```
            content_stripped = content_stripped.strip()

            # Parse JSON
            try:
                data = json.loads(content_stripped)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON from Claude: {content}")
                raise ValueError(f"Claude returned invalid JSON: {e}")

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
                logger.exception(f"Claude API call failed: {e}")
            raise

    async def ainvoke_gemini_structured(
        self,
        prompt: str,
        schema: Type[T],
        user_id: Optional[UUID] = None,
        temperature: float = 0.3,
    ) -> T:
        """
        Invoke Gemini 2.5 Flash with structured JSON output and LangSmith tracking.

        Uses response_format={"type": "json_object"} + Pydantic validation.
        Lower temperature (0.3) for more deterministic structured outputs.

        Args:
            prompt: Prompt that includes instructions to return JSON
            schema: Pydantic model class for validation
            user_id: User UUID for cost tracking (passed as LangSmith metadata)
            temperature: Sampling temperature (default 0.3 for structured output)

        Returns:
            Validated Pydantic model instance

        Raises:
            ValidationError: If response doesn't match schema
            Exception: If API request fails
            ValueError: If response is not valid JSON

        Example:
            grade = await client.ainvoke_gemini_structured(
                prompt="Is this chunk relevant? Respond with JSON: ...",
                schema=RelevanceGrade,
                user_id=user.id
            )
            print(grade.is_relevant, grade.reasoning)

        LangSmith Tracking:
            - Automatically tracks token usage (input_tokens, output_tokens)
            - Tracks cost per call (when pricing is configured in LangSmith UI)
            - Tags calls with user_id for per-user filtering
            - Includes cache usage if cache_discount is applied
        """
        # Create system prompt with schema instructions
        schema_json = json.dumps(schema.model_json_schema(), indent=2)
        system_prompt = f"""You are a data extraction assistant.
Respond with valid JSON only that matches this exact schema:

{schema_json}

Do not include explanations or additional text. Only output the JSON object."""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt),
        ]

        logger.debug(
            f"Calling Gemini {self.gemini_model} for {schema.__name__} structured output"
            f"{f' for user_id={user_id}' if user_id else ''}"
        )

        try:
            # Configure call with user_id metadata for LangSmith
            config = {}
            if user_id:
                config = {
                    "tags": [str(user_id)],
                    "metadata": {"user_id": str(user_id)},
                }

            # Override temperature if different from default
            gemini_with_config = self.gemini
            if temperature != 0.3:
                gemini_with_config = self.gemini.bind(temperature=temperature)

            # Invoke Gemini with LangSmith tracking
            response = await gemini_with_config.ainvoke(messages, config=config)

            content = response.content

            # Log usage metadata (if available)
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                usage = response.usage_metadata
                logger.debug(
                    f"Gemini usage: input={usage.get('input_tokens', 0)} "
                    f"output={usage.get('output_tokens', 0)} tokens"
                )
                # Log cache hits if present
                if "cache_read_tokens" in usage:
                    logger.debug(f"Cache hits: {usage['cache_read_tokens']} tokens")

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
                logger.exception(f"Gemini API call failed: {e}")
            raise
