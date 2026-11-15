from __future__ import annotations

import asyncio
from importlib.metadata import PackageNotFoundError, version
import os
import re
import signal
import sys
import time
from pathlib import Path

import edge_tts


async def stream(text: str) -> None:
    tick_pid = int(os.environ.get("TTS_TICK_PID", "0"))
    indicator_pid = int(os.environ.get("TTS_INDICATOR_PID", "0"))
    marker = os.environ.get("TTS_FIRST_AUDIO_MARKER")
    communicate = edge_tts.Communicate(
        text,
        voice=os.environ.get("EDGE_TTS_VOICE", "ru-RU-SvetlanaNeural"),
        rate=os.environ.get("EDGE_TTS_RATE", "+0%"),
        volume=os.environ.get("EDGE_TTS_VOLUME", "+0%"),
        pitch=os.environ.get("EDGE_TTS_PITCH", "+0Hz"),
        connect_timeout=int(os.environ.get("EDGE_TTS_CONNECT_TIMEOUT", "10")),
        receive_timeout=int(os.environ.get("EDGE_TTS_RECEIVE_TIMEOUT", "60")),
    )
    first_audio = False
    async for chunk in communicate.stream():
        if chunk["type"] != "audio":
            continue
        sys.stdout.buffer.write(chunk["data"])
        sys.stdout.buffer.flush()
        if first_audio:
            continue
        first_audio = True
        if marker:
            Path(marker).touch()
        print(f"TTS_FIRST_AUDIO {time.time():.3f}", file=sys.stderr, flush=True)
        for pid in (indicator_pid,):
            if pid > 0:
                try:
                    os.kill(pid, signal.SIGUSR1)
                except ProcessLookupError:
                    pass
        if tick_pid > 0:
            try:
                os.kill(tick_pid, signal.SIGTERM)
            except ProcessLookupError:
                pass


def main() -> int:
    text = sys.stdin.read()
    if not text.strip():
        print("TTS_INPUT_ERROR empty text", file=sys.stderr)
        return 2
    try:
        client_version = version("edge-tts")
    except PackageNotFoundError:
        client_version = "unknown"
    print(f"TTS_CLIENT_VERSION {client_version}", file=sys.stderr, flush=True)
    started = time.monotonic()
    try:
        asyncio.run(stream(text))
    except Exception as error:
        elapsed = time.monotonic() - started
        detail = re.sub(r"(?i)(wss?://[^\s?]+)\?[^\s]+", r"\1?<query-redacted>", str(error))
        print(f"TTS_API_ERROR {type(error).__name__} after {elapsed:.2f}s: {detail[:300]}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
