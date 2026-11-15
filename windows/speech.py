"""Small Windows runtime for selected-text-speech."""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

APP = "selected-text-speech"
ROOT = Path(os.environ.get("LOCALAPPDATA", Path.home())) / APP
STATE = ROOT / "state"
CONFIG = Path(os.environ.get("APPDATA", Path.home())) / APP / "config.env"
PID = STATE / "worker.pid"
LOG = STATE / "tts.log"


def settings() -> dict[str, str]:
    values = {
        "EDGE_TTS_VOICE": "ru-RU-SvetlanaNeural", "EDGE_TTS_RATE": "+0%",
        "EDGE_TTS_VOLUME": "+0%", "EDGE_TTS_PITCH": "+0Hz",
        "MPV_PLAYBACK_SPEED": "1.35", "MPV_PLAYBACK_VOLUME": "100",
        "API_MAX_ATTEMPTS": "3", "API_RETRY_BASE_SECONDS": "1.5",
        "API_RETRY_MAX_SECONDS": "8", "MPV_PATH": "mpv",
    }
    try:
        for line in CONFIG.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip("\"'")
    except FileNotFoundError:
        pass
    values.update({k: v for k, v in os.environ.items() if k in values})
    return values


def active_pid() -> int | None:
    try:
        pid = int(PID.read_text().strip())
        os.kill(pid, 0)
        return pid
    except (OSError, ValueError):
        PID.unlink(missing_ok=True)
        return None


def start(text: str) -> int:
    text = text.strip()
    if not text:
        raise ValueError("Выдели текст или передай его команде speak")
    STATE.mkdir(parents=True, exist_ok=True)
    try:
        with PID.open("x", encoding="ascii") as reservation:
            reservation.write(str(os.getpid()))
    except FileExistsError:
        if active_pid():
            raise RuntimeError("Озвучивание уже запущено; используй stop-speech")
        with PID.open("x", encoding="ascii") as reservation:
            reservation.write(str(os.getpid()))
    try:
        with LOG.open("a", encoding="utf-8") as log:
            proc = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--worker"],
                                    stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
        PID.write_text(str(proc.pid), encoding="ascii")
    except Exception:
        PID.unlink(missing_ok=True)
        raise
    assert proc.stdin is not None
    proc.stdin.write(text.encode("utf-8")); proc.stdin.close()
    print(f"Озвучивание запущено (PID {proc.pid})")
    return proc.pid


async def worker(text: str) -> int:
    import edge_tts
    import pygame

    cfg = settings()
    max_attempts = max(1, min(8, int(cfg["API_MAX_ATTEMPTS"])))
    for attempt in range(1, max_attempts + 1):
        audio = bytearray()
        try:
            communicate = edge_tts.Communicate(
                text, voice=cfg["EDGE_TTS_VOICE"], rate=cfg["EDGE_TTS_RATE"],
                volume=cfg["EDGE_TTS_VOLUME"], pitch=cfg["EDGE_TTS_PITCH"])
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio.extend(chunk["data"])
            if not audio:
                raise RuntimeError("Edge TTS не вернул аудио")
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as out:
                out.write(audio); audio_path = Path(out.name)
            try:
                pygame.mixer.init()
                pygame.mixer.music.load(str(audio_path))
                pygame.mixer.music.set_volume(max(0, min(100, int(cfg["MPV_PLAYBACK_VOLUME"]))) / 100)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    await asyncio.sleep(0.15)
            finally:
                pygame.mixer.quit(); audio_path.unlink(missing_ok=True)
            return 0
        except Exception as exc:
            with LOG.open("a", encoding="utf-8") as log:
                log.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} ATTEMPT {attempt} {type(exc).__name__}: {exc}\n")
            if attempt >= max_attempts:
                return 1
            await asyncio.sleep(min(float(cfg["API_RETRY_MAX_SECONDS"]), float(cfg["API_RETRY_BASE_SECONDS"]) * 2 ** (attempt - 1)))
    return 1


def selection() -> int:
    # Ctrl+C is used only on explicit hotkey; restore clipboard text afterwards.
    import keyboard
    import tkinter as tk
    root = tk.Tk(); root.withdraw()
    try:
        try: previous = root.clipboard_get()
        except tk.TclError: previous = ""
        keyboard.press_and_release("ctrl+c")
        time.sleep(0.18)
        try: text = root.clipboard_get()
        except tk.TclError: text = ""
        if previous:
            root.clipboard_clear(); root.clipboard_append(previous); root.update()
    finally:
        root.destroy()
    if not text.strip():
        print("Не удалось получить выделенный текст", file=sys.stderr); return 1
    start(text); return 0


def hotkey() -> None:
    import keyboard
    print("Горячая клавиша активна: Ctrl+Alt+S (выход: Ctrl+Alt+Q)")
    keyboard.add_hotkey("ctrl+alt+s", selection)
    keyboard.wait("ctrl+alt+q")


def main() -> int:
    args = sys.argv[1:]
    if args == ["--worker"]:
        text = sys.stdin.buffer.read().decode("utf-8", errors="replace")
        try: return asyncio.run(worker(text))
        finally:
            try:
                if PID.read_text(encoding="ascii").strip() == str(os.getpid()): PID.unlink()
            except (OSError, ValueError):
                pass
    if args == ["stop"]:
        pid = active_pid()
        if pid is None: print("Озвучивание не запущено"); return 0
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
        PID.unlink(missing_ok=True); print("Озвучивание остановлено"); return 0
    if args == ["status"]:
        pid = active_pid(); print(f"Озвучивание запущено (PID {pid})" if pid else "Озвучивание не запущено")
        return 0 if pid else 1
    if args == ["selection"]: return selection()
    if args == ["hotkey"]: hotkey(); return 0
    if args and args[0] == "speak": args = args[1:]
    if not args: print("Использование: speak TEXT | stop | status | selection | hotkey"); return 2
    return 0 if start(" ".join(args)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
