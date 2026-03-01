# Ollama Setup Guide

This guide walks you through installing and configuring Ollama as Gedos's default local LLM provider.

---

## Why Ollama?

Ollama is Gedos's **default LLM provider** because:
- **Privacy**: runs locally, no data sent to cloud
- **Free**: no API costs, no rate limits
- **Fast**: optimized for macOS M-series chips
- **Flexible**: easily switch between models

---

## Installation

### Step 1: Install Ollama

Download and install from [ollama.com](https://ollama.com/download):

```bash
# Or via Homebrew
brew install ollama
```

Verify installation:

```bash
ollama --version
```

### Step 2: Start Ollama Server

Ollama runs as a background service on `http://localhost:11434`:

```bash
ollama serve
```

**Tip**: Ollama auto-starts on macOS after installation. You only need to run `ollama serve` manually if the service stops.

### Step 3: Pull Recommended Models

Download models Gedos works best with:

```bash
# Recommended for most tasks (4.7 GB)
ollama pull llama3.3

# Alternative: smaller, faster (4.1 GB)
ollama pull mistral

# For code-heavy tasks (3.8 GB)
ollama pull codellama
```

Verify models are installed:

```bash
ollama list
```

---

## Configuring Gedos for Ollama

Gedos uses Ollama by default. No configuration needed if you installed `llama3.3`.

To use a different model, edit `.env`:

```bash
LLM_PROVIDER=ollama
OLLAMA_MODEL=mistral  # or codellama, llama3.3, etc
```

---

## Testing

Test your Ollama setup directly:

```bash
ollama run llama3.3
```

Then ask a question:
```
>>> What is Python?
```

Exit with `/bye`.

---

## Switching Models

Gedos can use any Ollama model. Popular choices:

| Model | Size | Best For |
|-------|------|----------|
| `llama3.3` | 4.7 GB | General tasks, reasoning |
| `mistral` | 4.1 GB | Faster responses, concise |
| `codellama` | 3.8 GB | Code generation, debugging |
| `deepseek-coder` | 6.7 GB | Advanced code tasks |
| `qwen2.5` | 4.4 GB | Multilingual support |

To switch models:

```bash
# Pull new model
ollama pull mistral

# Update .env
LLM_PROVIDER=ollama
OLLAMA_MODEL=mistral

# Restart Gedos
python gedos.py
```

---

## Troubleshooting

### "Connection refused" or "Ollama not responding"

**Cause**: Ollama server not running.

**Fix**:
```bash
ollama serve
```

Wait 5 seconds, then restart Gedos.

---

### Model generation is slow

**Cause**: Model too large for your Mac's RAM.

**Fix**: Switch to a smaller model:
```bash
ollama pull mistral  # 4.1 GB vs llama3.3's 4.7 GB
```

Update `.env`:
```bash
OLLAMA_MODEL=mistral
```

---

### "Model not found"

**Cause**: Model not pulled.

**Fix**:
```bash
ollama pull llama3.3
```

---

### Ollama uses too much memory

**Cause**: Large model context window.

**Fix**: Set lower context in Ollama:
```bash
# ~/.ollama/config.json
{
  "context_length": 2048
}
```

Or use a smaller model like `mistral`.

---

## Advanced: Custom Models

To use a custom Ollama model:

1. Create a Modelfile:
```bash
FROM llama3.3
PARAMETER temperature 0.7
SYSTEM "You are a helpful coding assistant."
```

2. Build the model:
```bash
ollama create my-custom-model -f Modelfile
```

3. Update `.env`:
```bash
OLLAMA_MODEL=my-custom-model
```

---

## Using Cloud LLMs Instead

If you prefer Claude or OpenAI over Ollama, see [Cloud LLM Configuration](../README.md#llm-configuration) in the main README.

---

**Next**: [Usage Examples](examples.md)
