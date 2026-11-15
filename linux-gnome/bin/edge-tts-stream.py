#!/usr/bin/env python3
import asyncio
import os
import signal
import sys

import edge_tts


async def main():
    text = sys.argv[1]
    tick_pid = int(os.environ.get("TTS_TICK_PID", "0"))
    indicator_pid = int(os.environ.get("TTS_INDICATOR_PID", "0"))
    ticks_stopped = False
    communicate = edge_tts.Communicate(text, voice="ru-RU-SvetlanaNeural")
    async for chunk in communicate.stream():
        if chunk["type"] != "audio":
            continue
        sys.stdout.buffer.write(chunk["data"])
        sys.stdout.buffer.flush()
        if not ticks_stopped:
            print("TTS_FIRST_AUDIO", file=sys.stderr, flush=True)
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
            ticks_stopped = True


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except BrokenPipeError:
        sys.exit(1)
