# Gedos Usage Examples

5 real-world examples showing what Gedos can do.

---

## Example 1: Run Git Commands

**Task**: Check repository status

**Telegram message**:
```
/task git status
```

**Gedos response**:
```
On branch main
Your branch is up to date with 'origin/main'.

nothing to commit, working tree clean
```

**How it works**: Gedos routes the command to Terminal Agent, executes `git status`, and reports back.

---

## Example 2: Open an Application

**Task**: Launch Visual Studio Code

**Telegram message**:
```
/task open -a "Visual Studio Code"
```

**Gedos response**:
```
✓ Command completed successfully.
```

**How it works**: Terminal Agent runs the macOS `open` command. GUI Agent can also interact with the app once opened.

---

## Example 3: Search the Web

**Task**: Find Python documentation

**Telegram message**:
```
/task search Python 3.12 documentation
```

**Gedos response**:
```
Page loaded.
Title: Welcome to Python.org
URL: https://docs.python.org/3.12/

The official home of the Python Programming Language. Python 3.12 documentation...
```

**How it works**: Web Agent uses Playwright to search Google and navigate to the result.

---

## Example 4: Click a Button in an App

**Task**: Click "OK" button in a dialog

**Telegram message**:
```
/task click OK
```

**Gedos response**:
```
Clicked the button.
```

**How it works**: GUI Agent reads the screen via AX Tree, locates the "OK" button, and clicks it using macOS Accessibility APIs.

**Requirements**: 
- Accessibility permissions enabled for Terminal (System Settings > Privacy & Security > Accessibility)
- The target app must be the frontmost window

---

## Example 5: Ask the LLM a Question

**Task**: Explain recursion

**Telegram message**:
```
/ask what is recursion?
```

**Gedos response**:
```
Recursion is a programming technique where a function calls itself to solve a problem by breaking it down into smaller, similar subproblems. It consists of two parts: a base case (stopping condition) and a recursive case (where the function calls itself with modified input).

Example in Python:
def factorial(n):
    if n == 0:  # base case
        return 1
    return n * factorial(n - 1)  # recursive case
```

**How it works**: Orchestrator routes `/ask` commands to the LLM Agent (Ollama by default). The LLM generates a response locally without sending data to the cloud.

---

## Advanced: Copilot Mode

**Scenario**: You're coding in VS Code. Gedos detects you're in the editor and proactively suggests:

**Gedos (unprompted)**:
```
💡 Want me to commit, run tests, or search for something?
```

**You reply**:
```
run tests
```

**Gedos**:
```
Running: pytest
=== 22 passed in 1.84s ===
✓ All tests passing.
```

**How it works**: Copilot Mode monitors your active app via AX Tree every 10 seconds (configurable in `config.yaml`). When it detects VS Code, it offers relevant suggestions.

**Enable Copilot Mode**:
```
/copilot on
```

---

## Tips for Best Results

1. **Be specific**: Instead of "open browser", say `/task open -a Safari`
2. **Use natural language**: Gedos understands both commands and requests
3. **Check logs**: If something fails, Gedos logs the error. Use `/status` for details
4. **Grant permissions**: macOS Accessibility permissions are required for GUI control
5. **Start simple**: Try terminal commands first, then move to GUI and web tasks

---

**Next**: [Contributing Guide](../CONTRIBUTING.md)
