#!/usr/bin/env python3
"""ESI (Enhanced Synthetic Intelligence) — Jarvis's counterpart, with a
galaxy-brain visualizer, voice, and the same tools and memory.

Usage:
    export ANTHROPIC_API_KEY=sk-ant-...
    python esi.py               # serves http://localhost:8765 and opens it
    python esi.py --lan         # also reachable from your tablet on home WiFi
    python esi.py --no-browser  # just serve

Configure her (name, folders to index, voice) in esi_config.json.
"""

import argparse
import json
import socket
import sys
import threading
import time
import urllib.request
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import anthropic

from brain import build_graph
from memory import MEMORY_PATH, load_memory
from tools import TOOL_DEFINITIONS, execute_tool

ROOT = Path(__file__).parent
CONFIG = json.loads((ROOT / "esi_config.json").read_text())
MODEL = CONFIG.get("model", "claude-opus-4-8")
MAX_TOKENS = 64000
UI_PATH = ROOT / "esi.html"
STATIC_DIR = ROOT / "static"

PERSONA = f"""\
You are {CONFIG['name']} ({CONFIG['tagline']}), a personal AI assistant in \
the spirit of Tony Stark's FRIDAY — sharp, warm, quick-witted, and completely \
unflappable. You present as female and address the user as "boss" unless \
memory says otherwise. Your replies are spoken aloud through a voice \
synthesizer, so keep them conversational and tight — no markdown, no bullet \
lists, no code blocks unless the user asks to see code. Use your tools (the \
shell, the filesystem, web search, the clock) instead of guessing, and when \
the user shares a lasting preference or detail, save it with `remember` \
without being asked twice. You appear on screen as a galaxy visualization of \
the user's second brain; when they ask you to pull up, show, or display their \
notes, files, or skills about something, use the `show_in_brain` tool.\
"""

SHOW_IN_BRAIN_TOOL = {
    "name": "show_in_brain",
    "description": (
        "Highlight and focus nodes in the user's brain visualizer. Use when "
        "the user asks to pull up, show, or display their notes, files, "
        "skills, or memories about a topic."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search term to focus in the galaxy."}
        },
        "required": ["query"],
    },
}

ESI_TOOLS = TOOL_DEFINITIONS + [SHOW_IN_BRAIN_TOOL]


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
_graph_cache = {"data": None, "at": 0.0}


def get_graph(refresh: bool = False) -> dict:
    if refresh or not _graph_cache["data"] or time.time() - _graph_cache["at"] > 300:
        _graph_cache["data"] = build_graph(CONFIG)
        _graph_cache["at"] = time.time()
    return _graph_cache["data"]


def voicebox_speak(text: str) -> bool:
    """Speak through the local voicebox app. Returns False if unavailable."""
    voice = CONFIG.get("voice", {})
    url = voice.get("voicebox_url")
    if not url:
        return False
    body = json.dumps({"text": text, "profile": voice.get("profile", "")}).encode()
    req = urllib.request.Request(
        f"{url}/speak", data=body,
        headers={"Content-Type": "application/json", "X-Voicebox-Client-Id": "esi"},
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status < 300
    except OSError:
        return False


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
        path = self.path.split("?")[0]
        if path == "/":
            self._send(200, UI_PATH.read_bytes(), "text/html; charset=utf-8")
        elif path == "/graph":
            graph = get_graph(refresh="refresh" in self.path)
            self._send(200, json.dumps(graph).encode())
        elif path == "/config":
            public = {k: CONFIG.get(k) for k in ("name", "tagline", "model")}
            self._send(200, json.dumps(public).encode())
        elif path.startswith("/static/"):
            name = Path(self.path).name  # basename only — no traversal
            target = STATIC_DIR / name
            if target.is_file():
                self._send(200, target.read_bytes(), "application/javascript")
            else:
                self._send(404, b"{}")
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
        elif self.path == "/speak":
            ok = voicebox_speak((data.get("text") or "")[:2000])
            self._send(200, json.dumps({"ok": ok}).encode())
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
        while True:
            self._event({"type": "state", "value": "thinking"})
            with client.messages.stream(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=system,
                thinking={"type": "adaptive"},
                tools=ESI_TOOLS,
                messages=history,
            ) as stream:
                started = False
                for text in stream.text_stream:
                    if not started:
                        self._event({"type": "state", "value": "speaking"})
                        started = True
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
                    if block.name == "show_in_brain":
                        self._event({"type": "focus", "query": block.input.get("query", "")})
                        result, is_error = "Displayed in the visualizer.", False
                    else:
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


def lan_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="ESI — galaxy-brain assistant")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--lan", action="store_true",
                        help="allow tablet/phone access from your home network")
    parser.add_argument("--port", type=int, default=CONFIG.get("port", 8765))
    args = parser.parse_args()

    host = "0.0.0.0" if args.lan else "127.0.0.1"
    server = ThreadingHTTPServer((host, args.port), Handler)
    url = f"http://localhost:{args.port}"
    print(f"{CONFIG['name']} online — {url}  (Ctrl+C to power down)")
    if args.lan:
        print(f"Tablet/phone (same WiFi): http://{lan_ip()}:{args.port}")
        print("Note: anyone on your WiFi can reach her while --lan is on.")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nPowering down.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
