from __future__ import annotations

import asyncio
import os
import re
import signal
import subprocess
import sys
import time
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


def _first_audio(marker: str | None, tick_pid: int, indicator_pid: int) -> None:
    if marker:
        Path(marker).touch()
    print(f"TTS_FIRST_AUDIO {time.time():.3f}", file=sys.stderr, flush=True)
    if indicator_pid > 0:
        try:
            os.kill(indicator_pid, signal.SIGUSR1)
        except ProcessLookupError:
            pass
    if tick_pid > 0:
        try:
            os.kill(tick_pid, signal.SIGTERM)
        except ProcessLookupError:
            pass


async def stream_edge(text: str) -> int:
    import edge_tts

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
        if not first_audio:
            first_audio = True
            _first_audio(marker, tick_pid, indicator_pid)
    return 0


def stream_piper(text: str) -> int:
    model = Path(os.environ.get("PIPER_MODEL", ""))
    if not model.is_file():
        print(f"PIPER_MODEL_NOT_FOUND {model}", file=sys.stderr, flush=True)
        return 2
    python = os.environ.get("PIPER_PYTHON", sys.executable)
    command = [
        python, "-m", "piper", "--model", str(model), "--output-raw",
        "--length-scale", os.environ.get("PIPER_LENGTH_SCALE", "1.0"),
        "--volume", os.environ.get("PIPER_VOLUME", "1.0"),
    ]
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=sys.stderr,
    )
    assert process.stdin is not None and process.stdout is not None
    try:
        process.stdin.write(text.encode("utf-8"))
        process.stdin.close()
    except BrokenPipeError:
        pass

    tick_pid = int(os.environ.get("TTS_TICK_PID", "0"))
    indicator_pid = int(os.environ.get("TTS_INDICATOR_PID", "0"))
    marker = os.environ.get("TTS_FIRST_AUDIO_MARKER")
    first_audio = False
    while block := process.stdout.read(65536):
        sys.stdout.buffer.write(block)
        sys.stdout.buffer.flush()
        if not first_audio:
            first_audio = True
            _first_audio(marker, tick_pid, indicator_pid)
    return process.wait()


def main() -> int:
    text = sys.stdin.read()
    if not text.strip():
        print("TTS_INPUT_ERROR empty text", file=sys.stderr)
        return 2
    engine = os.environ.get("TTS_ENGINE", "piper").strip().lower()
    started = time.monotonic()
    if engine == "piper":
        try:
            client_version = version("piper-tts")
        except PackageNotFoundError:
            client_version = "unknown"
        print(f"TTS_ENGINE piper-tts {client_version}", file=sys.stderr, flush=True)
        try:
            return stream_piper(text)
        except Exception as error:
            print(f"TTS_PIPER_ERROR {type(error).__name__} after {time.monotonic() - started:.2f}s: {error}", file=sys.stderr)
            return 1
    if engine != "edge":
        print(f"TTS_ENGINE_ERROR unsupported engine: {engine}", file=sys.stderr)
        return 2
    try:
        client_version = version("edge-tts")
    except PackageNotFoundError:
        client_version = "unknown"
    print(f"TTS_CLIENT_VERSION {client_version}", file=sys.stderr, flush=True)
    try:
        return asyncio.run(stream_edge(text))
    except Exception as error:
        elapsed = time.monotonic() - started
        detail = re.sub(r"(?i)(wss?://[^\s?]+)\?[^\s]+", r"\1?<query-redacted>", str(error))
        print(f"TTS_API_ERROR {type(error).__name__} after {elapsed:.2f}s: {detail[:300]}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
