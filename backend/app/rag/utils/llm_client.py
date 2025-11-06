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
    OpenRouter LLM client with dynamic model support and LangSmith integration.

    Supports per-conversation model selection with on-demand instance creation.

    Models:
        - claude-haiku-4.5: Text generation, Q&A, content generation
        - gemini-2.5-flash: Structured JSON output, intent classification, grading

    Features:
        - Dynamic model creation based on conversation settings
        - Automatic LangSmith cost tracking
        - Per-user usage tracking via user_id metadata
        - Token counting and usage_metadata in responses

    Usage:
        client = LLMClient()

        # Text generation with specified model (tracks user_id)
        response = await client.ainvoke(
            prompt="What is FastAPI?",
            model="claude-haiku-4.5",
            user_id=user.id
        )

        # Structured output with Gemini
        grade = await client.ainvoke_structured(
            prompt="Is this relevant: ...",
            schema=RelevanceGrade,
            model="gemini-2.5-flash",
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

        Note: Model instances are now created on-demand via _create_llm() factory.
        """
        # Store model IDs for mapping
        self.claude_model = settings.OPENROUTER_CLAUDE_MODEL
        self.gemini_model = settings.OPENROUTER_GEMINI_MODEL

        # Model name mapping
        self._model_map = {
            "claude-haiku-4.5": settings.OPENROUTER_CLAUDE_MODEL,
            "gemini-2.5-flash": settings.OPENROUTER_GEMINI_MODEL,
        }

    def _create_llm(
        self,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        structured: bool = False,
    ) -> ChatOpenAI:
        """
        Factory method to create ChatOpenAI instances on-demand.

        Args:
            model: Model identifier ("claude-haiku-4.5" or "gemini-2.5-flash")
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens in response
            structured: If True, use JSON mode for structured output

        Returns:
            Configured ChatOpenAI instance

        Raises:
            ValueError: If model is not supported
        """
        # Map friendly names to OpenRouter model IDs
        model_id = self._model_map.get(model)
        if not model_id:
            raise ValueError(
                f"Unsupported model: {model}. "
                f"Supported models: {list(self._model_map.keys())}"
            )

        kwargs = {
            "model": model_id,
            "openai_api_key": settings.OPENROUTER_API_KEY,
            "openai_api_base": "https://openrouter.ai/api/v1",
            "temperature": temperature,
            "timeout": 30.0,
            "default_headers": {
                "HTTP-Referer": settings.OPENROUTER_SITE_URL,
                "X-Title": settings.OPENROUTER_SITE_NAME,
            },
        }

        # Add max_tokens for text generation (not for structured output)
        if not structured:
            kwargs["max_tokens"] = max_tokens

        # Add JSON mode for structured output
        if structured:
            kwargs["model_kwargs"] = {"response_format": {"type": "json_object"}}

        return ChatOpenAI(**kwargs)

    async def ainvoke(
        self,
        prompt: str,
        model: str = "claude-haiku-4.5",
        user_id: Optional[UUID] = None,
        max_tokens: int = 2000,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
    ) -> str:
        """
        Invoke LLM for text generation with LangSmith tracking.

        Supports dynamic model selection per conversation.

        Args:
            prompt: User prompt or question
            model: Model identifier (default "claude-haiku-4.5")
            user_id: User UUID for cost tracking (passed as LangSmith metadata)
            max_tokens: Maximum tokens in response (default 2000)
            temperature: Sampling temperature 0.0-1.0 (default 0.7)
            system_prompt: Optional system prompt for context

        Returns:
            Generated text response

        Raises:
            ValueError: If model is not supported
            Exception: If API request fails

        Example:
            response = await client.ainvoke(
                prompt="Explain FastAPI dependency injection",
                model="claude-haiku-4.5",
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
            f"Calling {model} with prompt length: {len(prompt)}"
            f"{f' for user_id={user_id}' if user_id else ''}"
        )

        try:
            # Create LLM instance on-demand
            llm = self._create_llm(
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                structured=False,
            )

            # Configure call with user_id metadata for LangSmith
            config = {}
            if user_id:
                config = {
                    "tags": [str(user_id)],
                    "metadata": {"user_id": str(user_id)},
                }

            # Invoke LLM with LangSmith tracking
            response = await llm.ainvoke(messages, config=config)

            content = response.content

            # Log usage metadata (if available)
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                logger.debug(
                    f"{model} usage: input={response.usage_metadata.get('input_tokens', 0)} "
                    f"output={response.usage_metadata.get('output_tokens', 0)} tokens"
                )

            logger.debug(f"{model} response length: {len(content)}")

            return content

        except Exception as e:
            logger.exception(f"{model} API call failed: {e}")
            raise

    async def ainvoke_claude(
        self,
        prompt: str,
        user_id: Optional[UUID] = None,
        max_tokens: int = 2000,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
    ) -> str:
        """
        Backward compatibility wrapper for ainvoke_claude().

        Deprecated: Use ainvoke() with model parameter instead.

        This method is kept for backward compatibility with existing RAG nodes.
        """
        return await self.ainvoke(
            prompt=prompt,
            model="claude-haiku-4.5",
            user_id=user_id,
            max_tokens=max_tokens,
            temperature=temperature,
            system_prompt=system_prompt,
        )

    async def ainvoke_structured(
        self,
        prompt: str,
        schema: Type[T],
        model: str = "gemini-2.5-flash",
        user_id: Optional[UUID] = None,
        temperature: float = 0.3,
    ) -> T:
        """
        Invoke LLM with structured JSON output and LangSmith tracking.

        Supports dynamic model selection per conversation.
        Uses response_format={"type": "json_object"} + Pydantic validation.
        Lower temperature (0.3) for more deterministic structured outputs.

        Args:
            prompt: Prompt that includes instructions to return JSON
            schema: Pydantic model class for validation
            model: Model identifier (default "gemini-2.5-flash")
            user_id: User UUID for cost tracking (passed as LangSmith metadata)
            temperature: Sampling temperature (default 0.3 for structured output)

        Returns:
            Validated Pydantic model instance

        Raises:
            ValueError: If model is not supported or response is not valid JSON
            ValidationError: If response doesn't match schema
            Exception: If API request fails

        Example:
            classification = await client.ainvoke_structured(
                prompt="Classify this query intent: ...",
                schema=IntentClassification,
                model="gemini-2.5-flash",
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
            f"Calling {model} for {schema.__name__} structured output"
            f"{f' for user_id={user_id}' if user_id else ''}"
        )

        try:
            # Create LLM instance on-demand with structured mode
            llm = self._create_llm(
                model=model,
                temperature=temperature,
                structured=True,
            )

            # Configure call with user_id metadata for LangSmith
            config = {}
            if user_id:
                config = {
                    "tags": [str(user_id)],
                    "metadata": {"user_id": str(user_id)},
                }

            # Invoke LLM with LangSmith tracking
            response = await llm.ainvoke(messages, config=config)

            content = response.content

            # Log usage metadata (if available)
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                usage = response.usage_metadata
                logger.debug(
                    f"{model} usage: input={usage.get('input_tokens', 0)} "
                    f"output={usage.get('output_tokens', 0)} tokens"
                )
                # Log cache hits if present (Gemini)
                if "cache_read_tokens" in usage:
                    logger.debug(f"Cache hits: {usage['cache_read_tokens']} tokens")

            logger.debug(f"{model} raw response: {content[:200]}...")

            # Strip markdown code blocks if present (Claude sometimes wraps JSON)
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
                logger.error(f"Invalid JSON from {model}: {content}")
                raise ValueError(f"{model} returned invalid JSON: {e}")

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
                logger.exception(f"{model} API call failed: {e}")
            raise

    async def ainvoke_claude_structured(
        self,
        prompt: str,
        schema: Type[T],
        user_id: Optional[UUID] = None,
        temperature: float = 0.3,
    ) -> T:
        """
        Backward compatibility wrapper for ainvoke_claude_structured().

        Deprecated: Use ainvoke_structured() with model parameter instead.

        This method is kept for backward compatibility with existing RAG nodes.
        """
        return await self.ainvoke_structured(
            prompt=prompt,
            schema=schema,
            model="claude-haiku-4.5",
            user_id=user_id,
            temperature=temperature,
        )

    async def ainvoke_gemini_structured(
        self,
        prompt: str,
        schema: Type[T],
        user_id: Optional[UUID] = None,
        temperature: float = 0.3,
    ) -> T:
        """
        Backward compatibility wrapper for ainvoke_gemini_structured().

        Deprecated: Use ainvoke_structured() with model parameter instead.

        This method is kept for backward compatibility with existing RAG nodes.
        """
        return await self.ainvoke_structured(
            prompt=prompt,
            schema=schema,
            model="gemini-2.5-flash",
            user_id=user_id,
            temperature=temperature,
        )
