# Gedos MCP Mode

## What is MCP mode?

Running `gedos --mcp` starts Gedos as an MCP server.
Any MCP-compatible LLM can then use your Mac as a tool.

If you are running from source instead of an installed CLI, use:

```bash
python gedos.py --mcp
```

## Claude Desktop integration

Add this to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "gedos": {
      "command": "python",
      "args": ["/path/to/gedos/gedos.py", "--mcp"]
    }
  }
}
```

Replace `/path/to/gedos/gedos.py` with the absolute path to your local checkout.

## Cursor integration

Add this to `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "gedos": {
      "command": "python",
      "args": ["/path/to/gedos/gedos.py", "--mcp"]
    }
  }
}
```

Replace `/path/to/gedos/gedos.py` with the absolute path to your local checkout.

## Available tools

### `run_terminal_command(command: str) -> str`

Executes a shell command on the local Mac and returns stdout and stderr.

Example:

```text
Use gedos.run_terminal_command with command="pytest -v --timeout=30"
```

### `open_application(app_name: str) -> str`

Opens a macOS application by its visible app name with `open -a`.

Example:

```text
Use gedos.open_application with app_name="Visual Studio Code"
```

### `browse_web(url: str) -> str`

Navigates to a URL through the browser automation agent and returns a page summary.

Example:

```text
Use gedos.browse_web with url="https://github.com/g-dos/gedos"
```

### `read_screen() -> str`

Reads the current Accessibility Tree and returns the screen state as structured text.

Example:

```text
Use gedos.read_screen to inspect the current Mac UI state
```

### `ask_llm(question: str) -> str`

Sends a question to the configured Gedos LLM and returns the response text.

Example:

```text
Use gedos.ask_llm with question="Summarize the current repository structure"
```

### `get_task_history() -> str`

Returns recent Gedos task history from the shared memory database.

Example:

```text
Use gedos.get_task_history to see the last tasks Gedos executed
```

## Example prompts (in Claude/Cursor)

- "Use gedos to run the tests in my project"
- "Use gedos to open VS Code and create a new file"
- "Use gedos to check what's on my screen right now"
