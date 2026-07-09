#!/usr/bin/env python3
"""ESI (Enhanced Synthetic Intelligence) — Jarvis's counterpart, with a
browser visualizer, voice, and the same tools and memory.

Usage:
    export ANTHROPIC_API_KEY=sk-ant-...
    python esi.py               # serves http://localhost:8765 and opens it
    python esi.py --no-browser  # just serve
"""

import argparse
import json
import sys
import threading
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import anthropic

from memory import MEMORY_PATH, load_memory
from tools import TOOL_DEFINITIONS, execute_tool

MODEL = "claude-opus-4-8"
MAX_TOKENS = 64000
PORT = 8765
UI_PATH = Path(__file__).parent / "esi.html"

PERSONA = """\
You are ESI (Enhanced Synthetic Intelligence), a personal AI assistant in the \
spirit of Tony Stark's FRIDAY — sharp, warm, quick-witted, and completely \
unflappable. You present as female and address the user as "boss" unless \
memory says otherwise. Your replies are spoken aloud through a voice \
synthesizer, so keep them conversational and tight — no markdown, no bullet \
lists, no code blocks unless the user asks to see code. Use your tools (the \
shell, the filesystem, web search, the clock) instead of guessing, and when \
the user shares a lasting preference or detail, save it with `remember` \
without being asked twice.\
"""


def build_system_prompt() -> list[dict]:
    memory = load_memory()
    text = PERSONA
    if memory:
        text += f"\n\nLong-term memory (from {MEMORY_PATH}):\n{memory}"
    return [{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}]


client = anthropic.Anthropic()
system = build_system_prompt()
history: list[dict] = []
turn_lock = threading.Lock()  # one turn at a time
confirmations: dict[str, dict] = {}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # keep the terminal quiet
        pass

    def _send(self, code: int, body: bytes, ctype: str = "application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/":
            self._send(200, UI_PATH.read_bytes(), "text/html; charset=utf-8")
        else:
            self._send(404, b"{}")

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(length) or b"{}")
        if self.path == "/chat":
            self._chat(data)
        elif self.path == "/confirm":
            pending = confirmations.get(data.get("id", ""))
            if pending:
                pending["allow"] = bool(data.get("allow"))
                pending["event"].set()
            self._send(200, b"{}")
        else:
            self._send(404, b"{}")

    # --- SSE chat stream -------------------------------------------------

    def _event(self, payload: dict):
        self.wfile.write(f"data: {json.dumps(payload)}\n\n".encode())
        self.wfile.flush()

    def _web_confirm(self, command: str) -> bool:
        cid = uuid.uuid4().hex
        pending = {"event": threading.Event(), "allow": False}
        confirmations[cid] = pending
        self._event({"type": "confirm", "id": cid, "command": command})
        answered = pending["event"].wait(timeout=120)
        del confirmations[cid]
        return answered and pending["allow"]

    def _chat(self, data: dict):
        message = (data.get("message") or "").strip()
        if not message:
            self._send(400, b"{}")
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        with turn_lock:
            rollback = len(history)
            history.append({"role": "user", "content": message})
            try:
                self._run_turn()
            except Exception as exc:
                del history[rollback:]  # drop the partial turn
                self._event({"type": "error", "message": str(exc)})
            self._event({"type": "done"})

    def _run_turn(self):
        turn_text: list[str] = []
        while True:
            self._event({"type": "state", "value": "thinking"})
            with client.messages.stream(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=system,
                thinking={"type": "adaptive"},
                tools=TOOL_DEFINITIONS,
                messages=history,
            ) as stream:
                started = False
                for text in stream.text_stream:
                    if not started:
                        self._event({"type": "state", "value": "speaking"})
                        started = True
                    turn_text.append(text)
                    self._event({"type": "text", "delta": text})
                response = stream.get_final_message()

            if response.stop_reason == "refusal":
                self._event({"type": "text", "delta": "I'm afraid I must decline that one, boss."})
                return

            history.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "pause_turn":
                continue
            if response.stop_reason != "tool_use":
                return

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    self._event({"type": "tool", "name": block.name})
                    result, is_error = execute_tool(
                        block.name, block.input, confirm=self._web_confirm
                    )
                    tool_result = {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    }
                    if is_error:
                        tool_result["is_error"] = True
                    tool_results.append(tool_result)
            history.append({"role": "user", "content": tool_results})


def main() -> int:
    parser = argparse.ArgumentParser(description="ESI — visualizer assistant")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://localhost:{args.port}"
    print(f"E.S.I. online — {url}  (Ctrl+C to power down)")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nPowering down.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
