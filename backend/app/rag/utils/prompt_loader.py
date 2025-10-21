"""
Jinja2 Prompt Template Loader

Centralized utility for loading and rendering Jinja2 prompt templates.
All RAG node prompts are stored in app/rag/prompts/ as .jinja2 files.
"""

import logging
from pathlib import Path
from typing import Dict, Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

logger = logging.getLogger(__name__)

# Get the prompts directory path
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


class PromptLoader:
    """
    Jinja2 template loader for RAG prompts.

    Provides a centralized way to load and render prompt templates with
    automatic escaping disabled (since we're generating LLM prompts, not HTML).

    Usage:
        loader = PromptLoader()
        prompt = loader.render("query_router.jinja2", user_query="What is FastAPI?")
    """

    def __init__(self):
        """Initialize Jinja2 environment with FileSystemLoader."""
        self.env = Environment(
            loader=FileSystemLoader(str(PROMPTS_DIR)),
            autoescape=select_autoescape(enabled_extensions=()),  # Disable autoescaping
            trim_blocks=True,
            lstrip_blocks=True,
        )
        logger.debug(f"Initialized PromptLoader with templates from: {PROMPTS_DIR}")

    def render(self, template_name: str, **context: Dict[str, Any]) -> str:
        """
        Render a Jinja2 template with the given context.

        Args:
            template_name: Name of the template file (e.g., "query_router.jinja2")
            **context: Keyword arguments to pass to the template

        Returns:
            Rendered prompt as a string

        Raises:
            jinja2.TemplateNotFound: If template file doesn't exist
            jinja2.TemplateError: If template rendering fails

        Example:
            prompt = loader.render(
                "chunk_grader.jinja2",
                user_query="What is FastAPI?",
                chunk_text="FastAPI is a modern web framework..."
            )
        """
        template = self.env.get_template(template_name)
        rendered = template.render(**context)
        logger.debug(f"Rendered template: {template_name} (length: {len(rendered)})")
        return rendered


# Singleton instance for global use
_prompt_loader = PromptLoader()


def render_prompt(template_name: str, **context: Dict[str, Any]) -> str:
    """
    Convenience function to render a prompt template.

    This is a shortcut to the singleton PromptLoader instance.

    Args:
        template_name: Name of the template file
        **context: Template variables

    Returns:
        Rendered prompt string

    Example:
        from app.rag.utils.prompt_loader import render_prompt

        prompt = render_prompt("query_router.jinja2", user_query="Hello!")
    """
    return _prompt_loader.render(template_name, **context)
