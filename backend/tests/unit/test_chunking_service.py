"""Unit tests for ChunkingService."""

import pytest
from app.services.chunking_service import ChunkingService


class TestChunkingService:
    """Unit tests for ChunkingService."""

    def test_chunk_empty_text(self):
        """Empty text returns empty list."""
        service = ChunkingService()
        chunks = service.chunk_text("")
        assert chunks == []

    def test_chunk_whitespace_only_text(self):
        """Whitespace-only text returns empty list."""
        service = ChunkingService()
        chunks = service.chunk_text("   \n\t  ")
        assert chunks == []

    def test_chunk_short_text_single_chunk(self):
        """Text shorter than chunk_size stays as single chunk."""
        service = ChunkingService(chunk_size=700)
        text = "Short text. " * 10  # ~30-40 tokens (well under 700)

        chunks = service.chunk_text(text)

        assert len(chunks) == 1
        assert chunks[0]["index"] == 0
        assert chunks[0]["token_count"] < 700
        assert chunks[0]["text"] == text

    def test_chunk_exact_chunk_size(self):
        """Text exactly at chunk_size is single chunk."""
        service = ChunkingService(chunk_size=100)

        # Create text of approximately 100 tokens
        # "word" is typically 1 token, " " is 1 token, so "word " ~= 2 tokens
        text = "word " * 50  # ~100 tokens

        chunks = service.chunk_text(text)

        # Should be 1 chunk since it fits
        assert len(chunks) == 1
        assert chunks[0]["index"] == 0

    def test_chunk_long_text_creates_multiple_chunks(self):
        """Long text creates multiple overlapping chunks."""
        service = ChunkingService(chunk_size=100, overlap_percent=20)

        # Create text of ~500 tokens
        text = "word " * 250

        chunks = service.chunk_text(text)

        # Should have multiple chunks
        assert len(chunks) > 1

        # Each chunk (except possibly the last) should be ~100 tokens
        for chunk in chunks[:-1]:  # All but last
            assert 90 <= chunk["token_count"] <= 110  # Allow some variance

    def test_chunk_indices_sequential(self):
        """Chunk indices are sequential starting from 0."""
        service = ChunkingService(chunk_size=100)

        text = "word " * 500  # ~1000 tokens

        chunks = service.chunk_text(text)

        # Verify sequential indices
        for i, chunk in enumerate(chunks):
            assert chunk["index"] == i

    def test_chunk_overlap_implementation(self):
        """Test that overlap is implemented correctly."""
        service = ChunkingService(chunk_size=100, overlap_percent=20)

        text = "word " * 300  # Actually ~301 tokens due to tokenization

        chunks = service.chunk_text(text)

        # With 301 tokens, chunk_size=100, 20% overlap (slide by 80):
        # Chunks: 0-100, 80-180, 160-260, then 240-301 (61 tokens) merged with previous
        # Result: 3 chunks
        assert len(chunks) == 3
        assert chunks[-1]["token_count"] > 100  # Last chunk is merged

    def test_chunk_last_small_merges_with_previous(self):
        """Last chunk smaller than min_chunk_size merges with previous."""
        service = ChunkingService(chunk_size=100, min_chunk_size=50)

        # Create text that will result in a very small last chunk
        # We want slightly more than 100 tokens but less than 150
        # So the last chunk would be < 50 tokens
        text = "word " * 55  # ~110 tokens

        chunks = service.chunk_text(text)

        # Should merge into 1 chunk since last would be too small
        # OR if chunked, all chunks should meet min size
        if len(chunks) > 1:
            # If multiple chunks, all should be >= min_chunk_size
            for chunk in chunks:
                assert chunk["token_count"] >= 50
        else:
            # Or it's just one chunk
            assert len(chunks) == 1

    def test_chunk_custom_chunk_size(self):
        """Test with custom chunk size."""
        service = ChunkingService(chunk_size=50, overlap_percent=10)

        text = "word " * 200  # ~400 tokens

        chunks = service.chunk_text(text)

        # Should have multiple chunks
        assert len(chunks) > 1

        # Each chunk should be ~50 tokens (except possibly last)
        for chunk in chunks[:-1]:
            assert 40 <= chunk["token_count"] <= 60

    def test_chunk_custom_overlap(self):
        """Test with custom overlap percentage."""
        service = ChunkingService(chunk_size=100, overlap_percent=50)

        text = "word " * 300  # Actually ~301 tokens due to tokenization

        chunks = service.chunk_text(text)

        # With 50% overlap, window slides by 50 tokens each time
        # With 301 tokens: 0-100, 50-150, 100-200, 150-250, 200-300, 250-301 (merged)
        # Result: 5 chunks (more than 20% overlap which gives 3)
        assert len(chunks) >= 5

    def test_chunk_zero_overlap(self):
        """Test with zero overlap."""
        service = ChunkingService(chunk_size=100, overlap_percent=0)

        text = "word " * 300  # Actually ~301 tokens due to tokenization

        chunks = service.chunk_text(text)

        # With 0% overlap, window slides by 100 tokens
        # With 301 tokens: 0-100, 100-200, 200-300, 300-301 (1 token, merged with previous)
        # Result: 3 chunks
        assert len(chunks) == 3
        assert chunks[-1]["token_count"] > 100  # Last chunk is merged

    def test_chunk_preserves_text_content(self):
        """Chunks preserve original text content."""
        service = ChunkingService(chunk_size=50)

        original_text = "This is a test. " * 50

        chunks = service.chunk_text(original_text)

        # Verify chunks cover the original text by checking:
        # 1. All chunks are non-empty
        assert all(chunk["text"].strip() for chunk in chunks)

        # 2. First chunk starts with content from the beginning
        assert original_text.strip().startswith(chunks[0]["text"].strip())

        # 3. Last chunk ends with content from the end
        assert original_text.strip().endswith(chunks[-1]["text"].strip())

    def test_chunk_token_count_matches_actual(self):
        """Token count in chunk dict matches actual tokens."""
        service = ChunkingService(chunk_size=100)

        text = "word " * 200

        chunks = service.chunk_text(text)

        for chunk in chunks:
            # Verify token count by re-encoding
            actual_tokens = service.encoding.encode(chunk["text"])
            assert chunk["token_count"] == len(actual_tokens)

    def test_chunk_with_special_characters(self):
        """Chunking works with special characters."""
        service = ChunkingService(chunk_size=100)

        text = "Hello! This has special chars: @#$%^&*() 🎉 " * 50

        chunks = service.chunk_text(text)

        # Should create chunks without errors
        assert len(chunks) > 0
        assert all(chunk["text"] for chunk in chunks)  # All non-empty

    def test_chunk_with_newlines(self):
        """Chunking works with text containing newlines."""
        service = ChunkingService(chunk_size=100)

        text = "Line one.\nLine two.\nLine three.\n" * 50

        chunks = service.chunk_text(text)

        assert len(chunks) > 0
        # Should preserve newlines
        assert any("\n" in chunk["text"] for chunk in chunks)

    def test_chunk_multilingual_text(self):
        """Chunking works with non-English text."""
        service = ChunkingService(chunk_size=100)

        # Mix of languages
        text = (
            "Hello world. Hola mundo. Bonjour le monde. こんにちは世界。你好世界。" * 20
        )

        chunks = service.chunk_text(text)

        assert len(chunks) > 0
        assert all(chunk["token_count"] > 0 for chunk in chunks)

    def test_chunk_very_long_text(self):
        """Chunking works with very long text."""
        service = ChunkingService(chunk_size=700, overlap_percent=20)

        # Simulate a long transcript (~5000 tokens)
        text = "This is a sentence in a very long transcript. " * 500

        chunks = service.chunk_text(text)

        # Should have multiple chunks
        assert len(chunks) > 5

        # All chunks should have reasonable size
        for chunk in chunks:
            assert chunk["token_count"] > 0
            assert chunk["token_count"] <= 800  # Allow some variance above 700

    def test_chunk_realistic_transcript(self):
        """Test with realistic transcript-like text."""
        service = ChunkingService(chunk_size=700, overlap_percent=20)

        # Simulate realistic transcript with varied sentence lengths
        transcript = """
        Welcome to this video about machine learning. In this tutorial, we'll explore
        the fundamentals of neural networks and how they work. Neural networks are
        inspired by the human brain and consist of interconnected nodes called neurons.

        Let's start with the basics. A neural network has three main components: the input
        layer, hidden layers, and the output layer. The input layer receives the data,
        the hidden layers process it, and the output layer produces the result.

        Training a neural network involves adjusting weights and biases through a process
        called backpropagation. This iterative process helps the network learn from data
        and improve its predictions over time.
        """ * 50  # Repeat to make it longer

        chunks = service.chunk_text(transcript)

        # Should create chunks
        assert len(chunks) > 0

        # Verify structure
        assert all("text" in chunk for chunk in chunks)
        assert all("token_count" in chunk for chunk in chunks)
        assert all("index" in chunk for chunk in chunks)

        # Indices should be sequential
        for i, chunk in enumerate(chunks):
            assert chunk["index"] == i
