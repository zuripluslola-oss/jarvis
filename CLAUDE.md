# Jarvis repo — Claude Code notes

This repo contains two things:

1. **Jarvis** — a Claude-powered personal AI assistant (`jarvis.py`, `tools.py`,
   `memory.py`, `voice.py`). See README.md.
2. **Vendored agent toolkits** under `vendor/` (git submodules), with their
   skills/agents/commands installed into `.claude/` so Claude Code loads them
   when working in this repo:
   - `.claude/skills/` — 294 skills from superpowers, ECC,
     Obsidian-CLI-skill, and andrej-karpathy-skills
   - `.claude/agents/` — 67 subagents from ECC
   - `.claude/commands/` — 94 slash commands from ECC

Follow the `karpathy-guidelines` skill for coding style: simple, direct code;
no overengineering; no speculative abstractions.

To update the vendored toolkits: `git submodule update --remote vendor/<name>`,
then re-copy its `skills/` into `.claude/skills/`.
