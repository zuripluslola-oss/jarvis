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

## ESI — the galaxy brain

ESI is Jarvis's counterpart: same brain, tools, and memory — but she lives in
your browser as a full second-brain visualizer with voice.

```bash
python esi.py         # opens http://localhost:8765 — press F11 for full screen
python esi.py --lan   # ALSO reachable from your tablet on the same WiFi
                      # (prints the tablet URL; anyone on your WiFi can connect)
```

**The galaxy** — every node is something she knows: your notes and files
(green/grey), your 293 skills (blue), agents (pink), commands (yellow),
toolkits (purple), and her memories (teal), all orbiting the ESI core.
Click a node to focus it and read it in the inspector; search the brain from
the sidebar; toggle **2D/3D** with one button (or open `/?2d` directly —
handy on tablets); filter node types from the legend. Ask her to
*"pull up my notes about X"* and she flies the camera there herself.

**Feeding her brain** — edit `esi_config.json`:

```json
"brain": {
  "include_skills": true,
  "include_memory": true,
  "folders": ["~/Documents/MyVault", "~/Projects"]
}
```

Markdown `[[wikilinks]]` between notes become edges (Obsidian vaults work
out of the box). Hit the ↻ button to re-index after adding files.

**Her voice** — install [voicebox](https://github.com/jamiepine/voicebox)
(desktop app, `vendor/voicebox`), create a voice profile named `ESI`, and she
automatically speaks through it. Without voicebox she falls back to the
browser's built-in voice. Mic input works best in Chrome.

**The orb** (docked right) breathes when idle, spins while she thinks, and
pulses while she speaks. Shell commands still require your approval.

**Morning briefing (Gmail + Calendar)** — click the 🔔 or say
*"good morning"* and she reads you today's events and unread mail.
One-time setup:

1. [console.cloud.google.com](https://console.cloud.google.com) → create a
   project → enable the **Gmail API** and **Google Calendar API** → OAuth
   consent screen (External, add yourself as test user) → Credentials →
   **OAuth client ID → Desktop app** → Download JSON.
2. Save the downloaded file next to `esi.py` as `credentials.json`
   (gitignored — it never leaves your computer).
3. First briefing opens a Google page — click **Allow**. Access is
   read-only and revocable at
   [myaccount.google.com/permissions](https://myaccount.google.com/permissions).

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

## Vendored agent toolkits

Six community toolkits live in this repo as git submodules under `vendor/`,
pinned at exact versions. Clone with them included:

```bash
git clone --recurse-submodules https://github.com/zuripluslola-oss/jarvis.git
# or, in an existing clone:
git submodule update --init --depth 1
```

| Toolkit | What it is | How it runs here |
|---|---|---|
| [superpowers](https://github.com/obra/superpowers) | Software-development methodology as composable Claude Code skills (TDD, debugging, code review, ...) | Its 14 skills are installed in `.claude/skills/` and load automatically in Claude Code sessions in this repo |
| [ECC](https://github.com/affaan-m/ECC) | "Everything Claude Code" — a large agent-harness collection | 277 skills, 67 subagents, and 93 slash commands installed in `.claude/` |
| [andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills) | Karpathy-inspired coding guidelines for Claude Code | Installed as the `karpathy-guidelines` skill; referenced from `CLAUDE.md` |
| [Obsidian-CLI-skill](https://github.com/pablo-mano/Obsidian-CLI-skill) | Control Obsidian vaults from Claude Code | Installed as the `obsidian-cli` skill; activates when you have Obsidian (v1.12+) and its CLI on your machine |
| [ruflo](https://github.com/ruvnet/ruflo) | AI agent orchestration platform (claude-flow v3) | CLI: `npx -y ruflo --help` (verified working, v3.25.6) |
| [open-design](https://github.com/nexu-io/open-design) | Open-source "Claude Design" desktop app | Desktop GUI — run on your own machine with Node 24 + pnpm 10.33: see `vendor/open-design/QUICKSTART.md` |

## Safety notes

- Shell commands are never run without your explicit approval.
- Memory is a plain markdown file at `~/.jarvis/memory.md` — inspect or edit
  it any time; delete it to wipe Jarvis's memory.
