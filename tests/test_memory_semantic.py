from unittest.mock import MagicMock, patch

from core import memory_semantic


def test_unavailable_returns_empty_search() -> None:
    with patch.object(memory_semantic, "SEMANTIC_MEMORY_AVAILABLE", False):
        mem = memory_semantic.SemanticMemory("user1")
        assert mem.search("anything") == []


def test_unavailable_returns_empty_context() -> None:
    with patch.object(memory_semantic, "SEMANTIC_MEMORY_AVAILABLE", False):
        mem = memory_semantic.SemanticMemory("user1")
        assert mem.get_relevant_context("anything") == ""


def test_add_calls_ollama_and_chromadb() -> None:
    mock_collection = MagicMock()
    mock_client = MagicMock()
    mock_client.get_or_create_collection.return_value = mock_collection
    mock_chromadb = MagicMock()
    mock_chromadb.PersistentClient.return_value = mock_client
    mock_ollama = MagicMock()
    mock_ollama.embeddings.return_value = {"embedding": [0.1, 0.2]}

    with patch.object(memory_semantic, "SEMANTIC_MEMORY_AVAILABLE", True), patch.object(
        memory_semantic, "chromadb", mock_chromadb
    ), patch.object(memory_semantic, "ollama", mock_ollama):
        mem = memory_semantic.SemanticMemory("user1")
        mem.add("test text")

    mock_chromadb.PersistentClient.assert_called_once()
    mock_ollama.embeddings.assert_called_once_with(model="nomic-embed-text", prompt="test text")
    mock_collection.add.assert_called_once()


def test_search_returns_documents() -> None:
    mock_collection = MagicMock()
    mock_collection.query.return_value = {"documents": [["result1", "result2"]]}
    mock_client = MagicMock()
    mock_client.get_or_create_collection.return_value = mock_collection
    mock_chromadb = MagicMock()
    mock_chromadb.PersistentClient.return_value = mock_client
    mock_ollama = MagicMock()
    mock_ollama.embeddings.return_value = {"embedding": [0.1]}

    with patch.object(memory_semantic, "SEMANTIC_MEMORY_AVAILABLE", True), patch.object(
        memory_semantic, "chromadb", mock_chromadb
    ), patch.object(memory_semantic, "ollama", mock_ollama):
        mem = memory_semantic.SemanticMemory("user1")
        assert mem.search("query") == ["result1", "result2"]


def test_add_exception_does_not_raise() -> None:
    mock_collection = MagicMock()
    mock_client = MagicMock()
    mock_client.get_or_create_collection.return_value = mock_collection
    mock_chromadb = MagicMock()
    mock_chromadb.PersistentClient.return_value = mock_client
    mock_ollama = MagicMock()
    mock_ollama.embeddings.side_effect = RuntimeError("boom")

    with patch.object(memory_semantic, "SEMANTIC_MEMORY_AVAILABLE", True), patch.object(
        memory_semantic, "chromadb", mock_chromadb
    ), patch.object(memory_semantic, "ollama", mock_ollama):
        mem = memory_semantic.SemanticMemory("user1")
        mem.add("text")


def test_get_relevant_context_joins_results() -> None:
    with patch.object(memory_semantic.SemanticMemory, "search", return_value=["a", "b"]):
        mem = memory_semantic.SemanticMemory("user1")
        assert mem.get_relevant_context("q") == "a\n---\nb"
