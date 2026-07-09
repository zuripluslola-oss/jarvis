"""Persistent memory for Jarvis — facts survive across sessions."""

from datetime import datetime
from pathlib import Path

MEMORY_DIR = Path.home() / ".jarvis"
MEMORY_PATH = MEMORY_DIR / "memory.md"


def load_memory() -> str:
    """Return the saved memory file contents, or empty string if none."""
    if MEMORY_PATH.exists():
        return MEMORY_PATH.read_text(encoding="utf-8")
    return ""


def remember_fact(fact: str) -> str:
    """Append a fact to the memory file. Returns a confirmation string."""
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d")
    with MEMORY_PATH.open("a", encoding="utf-8") as f:
        f.write(f"- ({stamp}) {fact}\n")
    return f"Noted. Saved to memory: {fact}"
