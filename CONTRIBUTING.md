# Contributing to Gedos

Thanks for your interest in contributing! This guide covers how to set up the environment, code rules, and how to submit a Pull Request.

---

## 1. Clone and run locally

```bash
git clone https://github.com/g-dos/gedos.git
cd gedos
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### Set up environment variables

```bash
cp .env.example .env
```

Edit `.env` and set at least `TELEGRAM_BOT_TOKEN` (get one from [@BotFather](https://t.me/BotFather)).

### Run

```bash
python gedos.py
```

### Run the tests

```bash
pytest tests/ -v
```

All 22 tests must pass before submitting any PR.

### Ollama (optional)

To use the local LLM, install and start Ollama:

```bash
brew install ollama
ollama pull llama3.3
ollama serve
```

See the full guide at [docs/setup-ollama.md](docs/setup-ollama.md).

---

## 2. Code rules

### Python

- **Python 3.12+**
- **Type hints** on all functions and methods
- **Docstrings** on all public methods
- No unused imports
- No hardcoded values — everything goes through `config.py`

### Structure

```
core/          — config, memory, orchestrator, LLM, copilot
agents/        — terminal, GUI, web
interfaces/    — telegram bot
tools/         — AX tree, mouse, keyboard
tests/         — pytest smoke tests
docs/          — additional documentation
```

### Formatting

- 4 spaces indentation
- Lines up to 120 characters
- Double-quoted strings
- f-strings when appropriate

---

## 3. Semantic Commits

All commits must follow the semantic commit convention:

| Prefix | When to use | Example |
|---|---|---|
| `feat` | New feature | `feat: add /screenshot command` |
| `fix` | Bug fix | `fix: terminal timeout not respected` |
| `docs` | Documentation | `docs: add Ollama setup guide` |
| `refactor` | Refactor without behavior change | `refactor: extract routing logic` |
| `test` | Tests | `test: add orchestrator routing tests` |
| `chore` | Maintenance, deps, version | `chore: bump to v0.5.0` |

### Format

```
<type>: <short description>

<optional body — explain the "why", not the "what">
```

### Examples

```
feat: add web scraping to /web command

Playwright now extracts page title and text content,
returning a summary instead of just confirming navigation.
```

```
fix: copilot sending duplicate suggestions

Added throttling dict to prevent same message type
from being sent to same user within 60 seconds.
```

---

## 4. How to submit a Pull Request

### Step by step

1. **Fork** the repository on GitHub
2. **Clone** your fork:
   ```bash
   git clone https://github.com/YOUR-USER/gedos.git
   cd gedos
   ```
3. **Create a branch** from `main`:
   ```bash
   git checkout -b feat/my-feature
   ```
4. **Make your changes** following the code rules above
5. **Run the tests**:
   ```bash
   pytest tests/ -v
   ```
6. **Commit** with a semantic message:
   ```bash
   git commit -m "feat: my new feature"
   ```
7. **Push** to your fork:
   ```bash
   git push origin feat/my-feature
   ```
8. **Open a PR** on GitHub targeting `main`

### PR checklist

- [ ] Tests passing (`pytest tests/ -v`)
- [ ] Semantic commit message
- [ ] Type hints on new functions
- [ ] Docstrings on public methods
- [ ] No secrets in code (API keys go in `.env`)
- [ ] Does not break Pilot Mode or Copilot Mode

### What to avoid

- Don't add cloud dependencies to core — Gedos is local first
- Don't use screenshots as the primary screen reading method — AX Tree first
- Don't hardcode values — use `config.py`
- Don't commit `.env` or credentials

---

## 5. Reporting bugs

Open an [issue](https://github.com/g-dos/gedos/issues) with:

1. What you did (command/action)
2. What you expected to happen
3. What actually happened
4. Gedos version (`python gedos.py --version` or check `gedos.py`)
5. macOS version

---

## Questions?

Open an issue or reach out via Telegram.

---

*Built by [@g-dos](https://github.com/g-dos)*
