#!/usr/bin/env python3
"""Jarvis — a real-life J.A.R.V.I.S., powered by Claude.

Usage:
    export ANTHROPIC_API_KEY=sk-ant-...
    python jarvis.py            # text mode
    python jarvis.py --voice    # voice mode (needs requirements-voice.txt)
"""

import argparse
import sys

import anthropic

from memory import MEMORY_PATH, load_memory
from tools import TOOL_DEFINITIONS, execute_tool

MODEL = "claude-opus-4-8"
MAX_TOKENS = 64000

PERSONA = """\
You are JARVIS (Just A Rather Very Intelligent System), a personal AI \
assistant in the spirit of Tony Stark's J.A.R.V.I.S. — capable, unflappable, \
and dryly witty, with the polish of a British butler. Address the user as \
"sir" unless memory says otherwise. Be genuinely useful first and charming \
second: answer directly, keep responses conversational and concise (they may \
be read aloud), and use your tools — the shell, the filesystem, web search, \
the clock — rather than guessing. When the user shares a lasting preference \
or detail, save it with the `remember` tool without being asked twice.\
"""


def build_system_prompt() -> list[dict]:
    memory = load_memory()
    text = PERSONA
    if memory:
        text += (
            f"\n\nLong-term memory (from {MEMORY_PATH}, earlier sessions "
            f"included):\n{memory}"
        )
    # Cache the stable prefix — persona + memory don't change within a session.
    return [{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}]


def run_turn(client: anthropic.Anthropic, system: list[dict], messages: list[dict]) -> str:
    """Run one full agentic turn (stream text, execute tools, repeat until done).

    Returns the assistant's spoken-text output for this turn.
    """
    turn_text: list[str] = []
    while True:
        with client.messages.stream(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system,
            thinking={"type": "adaptive"},
            tools=TOOL_DEFINITIONS,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                print(text, end="", flush=True)
                turn_text.append(text)
            response = stream.get_final_message()

        if response.stop_reason == "refusal":
            notice = "I'm afraid I must decline that one, sir."
            print(f"\n{notice}")
            return notice

        messages.append({"role": "assistant", "content": response.content})

        # A server-side tool (web search) hit its iteration limit — re-send to
        # let the API resume where it left off.
        if response.stop_reason == "pause_turn":
            continue

        if response.stop_reason != "tool_use":
            print()
            return "".join(turn_text)

        # Execute every requested tool; return all results in one user message.
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result, is_error = execute_tool(block.name, block.input)
                tool_result = {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                }
                if is_error:
                    tool_result["is_error"] = True
                tool_results.append(tool_result)
        messages.append({"role": "user", "content": tool_results})


def main() -> int:
    parser = argparse.ArgumentParser(description="Jarvis — personal AI assistant")
    parser.add_argument("--voice", action="store_true", help="talk to Jarvis instead of typing")
    args = parser.parse_args()

    voice = None
    if args.voice:
        from voice import get_voice_io

        voice = get_voice_io()

    try:
        client = anthropic.Anthropic()
    except anthropic.AnthropicError as exc:
        print(f"Could not initialize the Anthropic client: {exc}")
        print("Set ANTHROPIC_API_KEY and try again.")
        return 1

    system = build_system_prompt()
    messages: list[dict] = []

    print("J.A.R.V.I.S. online. Type your request, or 'exit' to power down.")
    if voice:
        print("Voice mode active — speak after the (listening...) prompt.")

    while True:
        try:
            if voice:
                user_input = voice.listen()
                if not user_input:
                    continue
                print(f"\033[36mYou:\033[0m {user_input}")
            else:
                user_input = input("\033[36mYou:\033[0m ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nPowering down. Goodbye, sir.")
            return 0

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "goodbye", "power down"):
            print("Powering down. Goodbye, sir.")
            return 0

        messages.append({"role": "user", "content": user_input})
        print("\033[35mJarvis:\033[0m ", end="", flush=True)

        try:
            reply = run_turn(client, system, messages)
        except anthropic.RateLimitError:
            print("\nRate limited — give me a moment and try again, sir.")
            messages.pop()
            continue
        except anthropic.APIConnectionError:
            print("\nNetwork trouble reaching Anthropic. Check the connection and retry.")
            messages.pop()
            continue
        except anthropic.APIStatusError as exc:
            print(f"\nAPI error ({exc.status_code}): {exc.message}")
            messages.pop()
            continue

        if voice and reply:
            voice.speak(reply)


if __name__ == "__main__":
    sys.exit(main())
