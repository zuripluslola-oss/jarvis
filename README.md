# J.A.R.V.I.S.

A real-life JARVIS from Iron Man — a personal AI assistant powered by
[Claude](https://claude.com). Talk to it in your terminal (or out loud), and it
can search the web, run commands on your machine, read and write files, and
remember things about you across sessions.

## Quick start

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...   # from https://platform.claude.com
python jarvis.py
```

```
J.A.R.V.I.S. online. Type your request, or 'exit' to power down.
You: what's on my machine's disk?
Jarvis: One moment, sir.

Jarvis wants to run:  df -h
Allow? [y/N] y
...
```

## Voice mode

```bash
pip install -r requirements-voice.txt   # needs PortAudio, see file for notes
python jarvis.py --voice
```

Speak after the `(listening...)` prompt; Jarvis replies out loud.

## What Jarvis can do

| Capability | How |
|---|---|
| Answer questions with current information | Anthropic's server-side web search tool |
| Run shell commands | `run_command` tool — **every command requires your y/N approval** |
| Read and write files | `read_file` / `write_file` tools |
| Know the time and date | `get_current_datetime` tool |
| Remember you between sessions | `remember` tool → `~/.jarvis/memory.md`, loaded into every new session |

## How it works

`jarvis.py` runs a streaming agentic loop against the Claude API
(`claude-opus-4-8` with adaptive thinking): Claude's reply streams to your
terminal; when it requests a tool, Jarvis executes it locally (or Anthropic
runs it server-side for web search), feeds the result back, and continues
until the answer is complete. The persona and long-term memory live in a
prompt-cached system prompt, so multi-turn conversations stay fast and cheap.

- `jarvis.py` — entry point, conversation and agent loop
- `tools.py` — tool definitions and local execution
- `memory.py` — persistent memory file handling
- `voice.py` — optional microphone input and text-to-speech output

## Safety notes

- Shell commands are never run without your explicit approval.
- Memory is a plain markdown file at `~/.jarvis/memory.md` — inspect or edit
  it any time; delete it to wipe Jarvis's memory.
