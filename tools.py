"""Jarvis's tools: local tools executed on this machine, plus Anthropic's
server-side web search."""

import platform
import subprocess
from datetime import datetime
from pathlib import Path

from memory import remember_fact

LOCAL_TOOLS = [
    {
        "name": "get_current_datetime",
        "description": "Get the current local date, time, and day of the week.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "remember",
        "description": (
            "Save a fact to Jarvis's long-term memory so it persists across "
            "sessions. Call this whenever the user shares a preference, a "
            "recurring detail about themselves, or explicitly asks you to "
            "remember something."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "fact": {
                    "type": "string",
                    "description": "The fact to remember, phrased as a standalone statement.",
                }
            },
            "required": ["fact"],
        },
    },
    {
        "name": "read_file",
        "description": "Read a text file from the local filesystem and return its contents.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file to read."}
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write text content to a file on the local filesystem, creating parent directories as needed.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to write to."},
                "content": {"type": "string", "description": "The full file contents to write."},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "run_command",
        "description": (
            "Run a shell command on the user's machine and return its output. "
            "The user is asked to approve every command before it runs, so "
            "prefer a single clear command over many small ones."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The shell command to run."}
            },
            "required": ["command"],
        },
    },
]

# Server-side tool — runs on Anthropic's infrastructure, no local execution.
SERVER_TOOLS = [
    {"type": "web_search_20260209", "name": "web_search", "max_uses": 5},
]

TOOL_DEFINITIONS = LOCAL_TOOLS + SERVER_TOOLS


def _run_command(command: str) -> tuple[str, bool]:
    print(f"\n\033[33mJarvis wants to run:\033[0m  {command}")
    answer = input("Allow? [y/N] ").strip().lower()
    if answer not in ("y", "yes"):
        return "The user declined to run this command.", True
    try:
        proc = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=120
        )
    except subprocess.TimeoutExpired:
        return "Command timed out after 120 seconds.", True
    output = (proc.stdout + proc.stderr).strip() or "(no output)"
    if len(output) > 20_000:
        output = output[:20_000] + "\n... (output truncated)"
    if proc.returncode != 0:
        return f"Exit code {proc.returncode}:\n{output}", True
    return output, False


def execute_tool(name: str, tool_input: dict) -> tuple[str, bool]:
    """Execute a local tool. Returns (result_text, is_error)."""
    try:
        if name == "get_current_datetime":
            now = datetime.now()
            return (
                f"{now.strftime('%A, %B %d %Y, %H:%M:%S')} "
                f"(local time on {platform.node() or 'this machine'})",
                False,
            )
        if name == "remember":
            return remember_fact(tool_input["fact"]), False
        if name == "read_file":
            path = Path(tool_input["path"]).expanduser()
            if not path.is_file():
                return f"No such file: {path}", True
            text = path.read_text(encoding="utf-8", errors="replace")
            if len(text) > 50_000:
                text = text[:50_000] + "\n... (file truncated)"
            return text, False
        if name == "write_file":
            path = Path(tool_input["path"]).expanduser()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(tool_input["content"], encoding="utf-8")
            return f"Wrote {len(tool_input['content'])} characters to {path}", False
        if name == "run_command":
            return _run_command(tool_input["command"])
        return f"Unknown tool: {name}", True
    except Exception as exc:  # surface the failure to the model so it can adapt
        return f"Tool error: {exc}", True
