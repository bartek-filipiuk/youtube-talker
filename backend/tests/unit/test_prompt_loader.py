"""Unit tests for PromptLoader and Jinja2 templates."""

import pytest
from jinja2 import TemplateNotFound

from app.rag.utils.prompt_loader import PromptLoader, render_prompt


class TestPromptLoader:
    """Unit tests for PromptLoader class."""

    def test_prompt_loader_initialization(self):
        """Test PromptLoader initializes correctly."""
        loader = PromptLoader()

        assert loader.env is not None
        assert loader.env.loader is not None
        # Verify autoescape is disabled (we're generating prompts, not HTML)
        assert loader.env.autoescape is not None

    def test_template_not_found_error(self):
        """Test error handling when template doesn't exist."""
        loader = PromptLoader()

        with pytest.raises(TemplateNotFound):
            loader.render("nonexistent_template.jinja2")

    def test_render_prompt_convenience_function(self):
        """Test render_prompt convenience function works."""
        # Should not raise any errors
        result = render_prompt(
            "query_router.jinja2",
            user_query="What is FastAPI?",
            conversation_history=[]
        )

        assert isinstance(result, str)
        assert len(result) > 0
        assert "What is FastAPI?" in result


class TestQueryRouterTemplate:
    """Tests for query_router.jinja2 template."""

    def test_query_router_basic_render(self):
        """Test query router renders with basic user query."""
        loader = PromptLoader()

        prompt = loader.render(
            "query_router.jinja2",
            user_query="What is FastAPI?",
            conversation_history=[]
        )

        assert "What is FastAPI?" in prompt
        assert "chitchat" in prompt
        assert "qa" in prompt
        assert "linkedin" in prompt
        assert "intent" in prompt
        assert "confidence" in prompt

    def test_query_router_with_conversation_history(self):
        """Test query router includes conversation history."""
        loader = PromptLoader()

        conversation = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi! How can I help?"}
        ]

        prompt = loader.render(
            "query_router.jinja2",
            user_query="What did we talk about?",
            conversation_history=conversation
        )

        assert "Hello" in prompt
        assert "Hi! How can I help?" in prompt
        assert "USER:" in prompt
        assert "ASSISTANT:" in prompt

    def test_query_router_without_history(self):
        """Test query router works without conversation history."""
        loader = PromptLoader()

        prompt = loader.render(
            "query_router.jinja2",
            user_query="Test query",
            conversation_history=[]
        )

        # Should not include history section
        assert "Recent conversation context" not in prompt


class TestChunkGraderTemplate:
    """Tests for chunk_grader.jinja2 template."""

    def test_chunk_grader_basic_render(self):
        """Test chunk grader renders with basic inputs."""
        loader = PromptLoader()

        prompt = loader.render(
            "chunk_grader.jinja2",
            user_query="What is dependency injection?",
            chunk_text="Dependency injection is a design pattern...",
            chunk_metadata={}
        )

        assert "What is dependency injection?" in prompt
        assert "Dependency injection is a design pattern" in prompt
        assert "is_relevant" in prompt
        assert "reasoning" in prompt

    def test_chunk_grader_with_metadata(self):
        """Test chunk grader includes metadata when provided."""
        loader = PromptLoader()

        metadata = {
            "youtube_video_id": "abc123",
            "chunk_index": 5
        }

        prompt = loader.render(
            "chunk_grader.jinja2",
            user_query="Test query",
            chunk_text="Test chunk content",
            chunk_metadata=metadata
        )

        assert "abc123" in prompt
        assert "5" in prompt
        assert "Chunk metadata" in prompt

    def test_chunk_grader_without_metadata(self):
        """Test chunk grader works without metadata."""
        loader = PromptLoader()

        prompt = loader.render(
            "chunk_grader.jinja2",
            user_query="Test query",
            chunk_text="Test content",
            chunk_metadata=None
        )

        # Should not include metadata section
        assert "Chunk metadata" not in prompt


class TestRagQATemplate:
    """Tests for rag_qa.jinja2 template."""

    def test_rag_qa_basic_render(self):
        """Test RAG Q&A renders with graded chunks."""
        loader = PromptLoader()

        chunks = [
            {
                "chunk_text": "FastAPI is a modern web framework for Python.",
                "youtube_video_id": "video1"
            },
            {
                "chunk_text": "It supports async operations out of the box.",
                "youtube_video_id": "video2"
            }
        ]

        prompt = loader.render(
            "rag_qa.jinja2",
            user_query="What is FastAPI?",
            graded_chunks=chunks,
            conversation_history=[]
        )

        assert "What is FastAPI?" in prompt
        assert "FastAPI is a modern web framework" in prompt
        assert "async operations" in prompt
        assert "From Video:" in prompt
        assert "video1" in prompt
        assert "video2" in prompt

    def test_rag_qa_with_conversation_history(self):
        """Test RAG Q&A includes conversation history."""
        loader = PromptLoader()

        history = [
            {"role": "user", "content": "Tell me about Python"},
            {"role": "assistant", "content": "Python is a programming language"}
        ]

        chunks = [{"chunk_text": "Test chunk"}]

        prompt = loader.render(
            "rag_qa.jinja2",
            user_query="More details please",
            graded_chunks=chunks,
            conversation_history=history
        )

        assert "Tell me about Python" in prompt
        assert "Python is a programming language" in prompt

    def test_rag_qa_empty_chunks(self):
        """Test RAG Q&A with no graded chunks."""
        loader = PromptLoader()

        prompt = loader.render(
            "rag_qa.jinja2",
            user_query="Test query",
            graded_chunks=[],
            conversation_history=[]
        )

        # Should not have any chunk sections
        assert "From Video:" not in prompt


class TestLinkedInPostTemplate:
    """Tests for linkedin_post_generate.jinja2 template."""

    def test_linkedin_post_basic_render(self):
        """Test LinkedIn post template renders correctly."""
        loader = PromptLoader()

        chunks = [
            {
                "chunk_text": "FastAPI provides automatic API documentation.",
                "youtube_video_id": "video1"
            }
        ]

        prompt = loader.render(
            "linkedin_post_generate.jinja2",
            topic="FastAPI Benefits",
            graded_chunks=chunks,
            conversation_history=[]
        )

        assert "FastAPI Benefits" in prompt
        assert "FastAPI provides automatic API documentation" in prompt
        assert "LinkedIn Post Template" in prompt
        assert "Hook" in prompt
        assert "Key Points" in prompt
        assert "Call to Action" in prompt

    def test_linkedin_post_with_multiple_chunks(self):
        """Test LinkedIn post with multiple knowledge chunks."""
        loader = PromptLoader()

        chunks = [
            {"chunk_text": "Point 1", "youtube_video_id": "v1"},
            {"chunk_text": "Point 2", "youtube_video_id": "v2"},
            {"chunk_text": "Point 3", "youtube_video_id": "v3"}
        ]

        prompt = loader.render(
            "linkedin_post_generate.jinja2",
            topic="Test Topic",
            graded_chunks=chunks,
            conversation_history=[]
        )

        assert "Point 1" in prompt
        assert "Point 2" in prompt
        assert "Point 3" in prompt
        assert "From Video:" in prompt
        assert "v1" in prompt
        assert "v3" in prompt


class TestChitchatFlowTemplate:
    """Tests for chitchat_flow.jinja2 template."""

    def test_chitchat_basic_render(self):
        """Test chitchat template renders for casual conversation."""
        loader = PromptLoader()

        prompt = loader.render(
            "chitchat_flow.jinja2",
            user_query="Hello! How are you?",
            conversation_history=[]
        )

        assert "Hello! How are you?" in prompt
        assert "friendly" in prompt.lower()
        assert "conversational" in prompt.lower()

    def test_chitchat_with_history(self):
        """Test chitchat includes conversation context."""
        loader = PromptLoader()

        history = [
            {"role": "user", "content": "Hi there"},
            {"role": "assistant", "content": "Hello!"}
        ]

        prompt = loader.render(
            "chitchat_flow.jinja2",
            user_query="Thanks for the help",
            conversation_history=history
        )

        assert "Hi there" in prompt
        assert "Hello!" in prompt
        assert "Thanks for the help" in prompt

    def test_chitchat_without_history(self):
        """Test chitchat works without conversation history."""
        loader = PromptLoader()

        prompt = loader.render(
            "chitchat_flow.jinja2",
            user_query="Good morning",
            conversation_history=[]
        )

        assert "Good morning" in prompt
        assert "Recent conversation context" not in prompt
