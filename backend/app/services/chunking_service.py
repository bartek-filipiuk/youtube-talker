"""Chunking service for splitting text into token-based overlapping segments."""

from typing import List, Dict
import tiktoken


class ChunkingService:
    """Service for chunking text with token-based sliding window."""

    def __init__(
        self,
        chunk_size: int = 700,
        overlap_percent: int = 20,
        min_chunk_size: int = 150,
    ):
        """
        Initialize chunking service with configuration.

        Args:
            chunk_size: Target chunk size in tokens (default: 700)
            overlap_percent: Overlap percentage between chunks (default: 20%)
            min_chunk_size: Minimum viable chunk size (default: 150 tokens)
        """
        self.chunk_size = chunk_size
        self.overlap_tokens = int(chunk_size * overlap_percent / 100)
        self.min_chunk_size = min_chunk_size
        self.encoding = tiktoken.get_encoding("cl100k_base")  # GPT-4 encoding

    def chunk_text(self, text: str) -> List[Dict]:
        """
        Chunk text into overlapping segments using token-based sliding window.

        Args:
            text: Full transcript text

        Returns:
            List of dicts with keys:
                - text: str (chunk content)
                - token_count: int (actual token count)
                - index: int (sequential 0, 1, 2, ...)

            Example:
                [
                    {"text": "First chunk...", "token_count": 700, "index": 0},
                    {"text": "Second chunk...", "token_count": 685, "index": 1}
                ]

        Behavior:
            - If total_tokens <= chunk_size: Return single chunk
            - If last chunk < min_chunk_size: Merge with previous chunk
            - Window slides by (chunk_size - overlap_tokens)
        """
        # Handle empty text
        if not text or not text.strip():
            return []

        # Encode full text to tokens
        tokens = self.encoding.encode(text)
        total_tokens = len(tokens)

        # Check if text fits in single chunk (< 700 tokens)
        if total_tokens <= self.chunk_size:
            return [
                {
                    "text": text,
                    "token_count": total_tokens,
                    "index": 0,
                }
            ]

        # Sliding window chunking
        chunks = []
        index = 0
        start = 0

        while start < total_tokens:
            # Take next chunk_size tokens
            end = min(start + self.chunk_size, total_tokens)
            chunk_tokens = tokens[start:end]
            chunk_text = self.encoding.decode(chunk_tokens)

            # Check if this is the last chunk and it's too small
            if end == total_tokens and len(chunk_tokens) < self.min_chunk_size and chunks:
                # Merge with previous chunk by re-decoding the combined tokens
                # This ensures accurate token count after merging
                # Previous chunk started at: start - slide_distance
                slide_distance = self.chunk_size - self.overlap_tokens
                prev_chunk_start = start - slide_distance
                merged_tokens = tokens[prev_chunk_start:end]
                merged_text = self.encoding.decode(merged_tokens)
                chunks[-1]["text"] = merged_text
                chunks[-1]["token_count"] = len(merged_tokens)
            else:
                # Add as separate chunk
                chunks.append(
                    {
                        "text": chunk_text,
                        "token_count": len(chunk_tokens),
                        "index": index,
                    }
                )
                index += 1

            # Move start forward (with overlap)
            # slide_distance = chunk_size - overlap_tokens
            start += self.chunk_size - self.overlap_tokens

        return chunks
