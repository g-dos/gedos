# Semantic Memory

## Overview

Gedos already stores structured history in SQLite (`core/memory.py`) for tasks, preferences, and patterns.
Semantic memory adds meaning-based retrieval using embeddings, so Gedos can recall relevant past context even when wording differs.

## Requirements

- `chromadb`
- `ollama`
- Ollama embedding model: `nomic-embed-text`

## Setup

```bash
pip install chromadb ollama
ollama pull nomic-embed-text
```

## How it works

Semantic memory complements existing memory with three practical layers:

1. Session
- Recent interactions in the current flow.
- Used to keep immediate continuity.

2. Episodic
- Conversation and task outcomes stored as vectorized documents.
- Queried by semantic similarity before LLM calls.

3. Patterns
- Behavioral patterns remain in SQLite pattern tables.
- Semantic retrieval enriches context while pattern logic handles proactive behavior.

## Privacy

- Data stays local at `~/.gedos/semantic_memory`.
- Collections are separated per `user_id`.
- No semantic memory content is sent to cloud services by this layer.

## How to disable

No extra switch is required:
- If `chromadb` or `ollama` is not installed (or unavailable), Gedos silently falls back to SQLite memory only.
