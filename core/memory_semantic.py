"""
GEDOS semantic memory layer (ChromaDB + Ollama embeddings).

This module adds semantic retrieval memory using local ChromaDB persistence
and Ollama embeddings. It coexists with the structured SQLite memory in
`core/memory.py` and does not replace it.

Requirements:
    pip install chromadb ollama

Runtime prerequisites:
    - Ollama running locally
    - Embedding model pulled (recommended): nomic-embed-text
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

try:
    import chromadb
    import ollama

    SEMANTIC_MEMORY_AVAILABLE = True
except ImportError:
    chromadb = None  # type: ignore[assignment]
    ollama = None  # type: ignore[assignment]
    SEMANTIC_MEMORY_AVAILABLE = False

logger = logging.getLogger(__name__)


class SemanticMemory:
    """Semantic memory store backed by ChromaDB and Ollama embeddings."""

    def __init__(self, user_id: str, persist_dir: str = "~/.gedos/semantic_memory") -> None:
        self.user_id = str(user_id)
        self.persist_dir = str(Path(persist_dir).expanduser())
        self.client: Optional[Any] = None
        self.collection: Optional[Any] = None
        if not SEMANTIC_MEMORY_AVAILABLE:
            return

        try:
            self.client = chromadb.PersistentClient(path=self.persist_dir)
            self.collection = self.client.get_or_create_collection(name=f"gedos_{self.user_id}")
        except Exception:
            logger.exception("Failed to initialize semantic memory for user_id=%s", self.user_id)
            self.client = None
            self.collection = None

    @staticmethod
    def _embedding_for(text: str) -> Optional[list[float]]:
        """Generate an embedding using local Ollama."""
        if not SEMANTIC_MEMORY_AVAILABLE:
            return None
        try:
            response = ollama.embeddings(model="nomic-embed-text", prompt=text)
            embedding = response.get("embedding") if isinstance(response, dict) else None
            if isinstance(embedding, list) and embedding:
                return embedding
        except Exception:
            logger.exception("Failed to generate embedding with Ollama")
        return None

    def add(self, text: str, metadata: Optional[dict[str, Any]] = None) -> None:
        """Add one semantic document to the user's collection."""
        if not SEMANTIC_MEMORY_AVAILABLE or not self.collection or not text:
            return
        try:
            embedding = self._embedding_for(text)
            if not embedding:
                return
            self.collection.add(
                documents=[text],
                embeddings=[embedding],
                ids=[f"{self.user_id}_{uuid4().hex[:8]}"],
                metadatas=[metadata or {}],
            )
        except Exception:
            logger.exception("Failed to add semantic memory entry")

    def search(self, query: str, n_results: int = 5) -> list[str]:
        """Search semantic memory and return matching document strings."""
        if not SEMANTIC_MEMORY_AVAILABLE or not self.collection or not query:
            return []
        try:
            embedding = self._embedding_for(query)
            if not embedding:
                return []
            result = self.collection.query(query_embeddings=[embedding], n_results=max(int(n_results), 1))
            documents = result.get("documents") if isinstance(result, dict) else None
            if not documents:
                return []
            first_batch = documents[0] if isinstance(documents, list) and documents else []
            return [str(item) for item in first_batch if item]
        except Exception:
            logger.exception("Failed to search semantic memory")
            return []

    def add_conversation(self, role: str, content: str, extra: Optional[dict[str, Any]] = None) -> None:
        """Add a conversation message into semantic memory."""
        meta = {"role": role, "type": "conversation", **(extra or {})}
        self.add(content, metadata=meta)

    def add_task(self, task: str, result: str, extra: Optional[dict[str, Any]] = None) -> None:
        """Add a task/result pair into semantic memory."""
        payload = f"Task: {task}\nResult: {result}"
        meta = {"type": "task", **(extra or {})}
        self.add(payload, metadata=meta)

    def get_relevant_context(self, query: str, n_results: int = 5) -> str:
        """Return concatenated relevant context chunks for a query."""
        matches = self.search(query, n_results=n_results)
        if not matches:
            return ""
        return "\n---\n".join(matches)
