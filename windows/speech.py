"""Small Windows runtime for selected-text-speech."""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import tempfile
import time
import wave
from pathlib import Path

APP = "selected-text-speech"
APP_DIR = (Path(sys.executable).resolve().parent if getattr(sys, "frozen", False)
           else Path(__file__).resolve().parents[1])
ROOT = Path(os.environ.get("LOCALAPPDATA", Path.home())) / APP
STATE = ROOT / "state"
CONFIG = Path(os.environ.get("APPDATA", Path.home())) / APP / "config.env"
PID = STATE / "worker.pid"
TRAY_PID = STATE / "tray.pid"
STARTED = STATE / "started-at"
PLAYING = STATE / "playing"
LOG = STATE / "tts.log"


def settings() -> dict[str, str]:
    values = {
        "TTS_ENGINE": "piper",
        "PIPER_MODEL": str(APP_DIR / "models" / "ru_RU-irina-medium.onnx"),
        "PIPER_LENGTH_SCALE": "",
        "PIPER_VOLUME": "1.0",
        "EDGE_TTS_VOICE": "ru-RU-SvetlanaNeural", "EDGE_TTS_RATE": "+0%",
        "EDGE_TTS_VOLUME": "+0%", "EDGE_TTS_PITCH": "+0Hz",
        "MPV_PLAYBACK_SPEED": "1.35", "MPV_PLAYBACK_VOLUME": "100",
        "API_MAX_ATTEMPTS": "3", "API_RETRY_BASE_SECONDS": "1.5",
        "API_RETRY_MAX_SECONDS": "8", "MPV_PATH": "mpv",
        "HOTKEY": "alt+esc",
    }
    try:
        for line in CONFIG.read_text(encoding="utf-8").splitlines():
            line = line.strip().lstrip("\ufeff")
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip("\"'")
    except FileNotFoundError:
        pass
    values.update({k: v for k, v in os.environ.items() if k in values})
    model_path = Path(values["PIPER_MODEL"]).expanduser()
    if not model_path.is_absolute():
        model_path = APP_DIR / model_path
    values["PIPER_MODEL"] = str(model_path)
    if not values["PIPER_LENGTH_SCALE"].strip():
        values["PIPER_LENGTH_SCALE"] = str(1.0 / float(values["MPV_PLAYBACK_SPEED"]))
    return values


def active_pid() -> int | None:
    try:
        pid = int(PID.read_text().strip())
        os.kill(pid, 0)
        return pid
    except (OSError, ValueError):
        PID.unlink(missing_ok=True)
        return None


def stop_speech() -> bool:
    pid = active_pid()
    if pid is None:
        return False
    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
    PID.unlink(missing_ok=True)
    PLAYING.unlink(missing_ok=True)
    STARTED.unlink(missing_ok=True)
    return True


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
    STARTED.write_text(str(time.time()), encoding="ascii")
    PLAYING.unlink(missing_ok=True)
    try:
        worker_command = ([sys.executable, "--worker"] if getattr(sys, "frozen", False)
                          else [sys.executable, str(Path(__file__).resolve()), "--worker"])
        with LOG.open("a", encoding="utf-8") as log:
            proc = subprocess.Popen(worker_command,
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


def piper_audio_file(text: str, cfg: dict[str, str]) -> Path:
    from piper import PiperVoice, SynthesisConfig

    model = Path(cfg["PIPER_MODEL"])
    if not model.is_file():
        raise FileNotFoundError(f"Модель Piper не найдена: {model}")
    voice = PiperVoice.load(str(model))
    syn_config = SynthesisConfig(
        length_scale=float(cfg["PIPER_LENGTH_SCALE"]),
        volume=float(cfg["PIPER_VOLUME"]),
    )
    fd, name = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    path = Path(name)
    try:
        with wave.open(str(path), "wb") as wav_file:
            voice.synthesize_wav(text, wav_file, syn_config=syn_config)
        return path
    except Exception:
        path.unlink(missing_ok=True)
        raise


async def worker(text: str) -> int:
    import pygame

    cfg = settings()
    max_attempts = max(1, min(8, int(cfg["API_MAX_ATTEMPTS"])))
    for attempt in range(1, max_attempts + 1):
        audio_path: Path | None = None
        try:
            engine = cfg["TTS_ENGINE"].strip().lower()
            if engine == "piper":
                audio_path = piper_audio_file(text, cfg)
            elif engine == "edge":
                import edge_tts
                audio = bytearray()
                communicate = edge_tts.Communicate(
                    text, voice=cfg["EDGE_TTS_VOICE"], rate=cfg["EDGE_TTS_RATE"],
                    volume=cfg["EDGE_TTS_VOLUME"], pitch=cfg["EDGE_TTS_PITCH"])
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        audio.extend(chunk["data"])
                if not audio:
                    raise RuntimeError("Edge TTS не вернул аудио")
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as out:
                    out.write(audio)
                    audio_path = Path(out.name)
            else:
                raise ValueError("TTS_ENGINE должен быть piper или edge")

            pygame.mixer.init()
            pygame.mixer.music.load(str(audio_path))
            pygame.mixer.music.set_volume(max(0, min(100, int(cfg["MPV_PLAYBACK_VOLUME"]))) / 100)
            PLAYING.write_text(str(time.time()), encoding="ascii")
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                await asyncio.sleep(0.15)
            pygame.mixer.quit()
            return 0
        except Exception as exc:
            PLAYING.unlink(missing_ok=True)
            try:
                pygame.mixer.quit()
            except Exception:
                pass
            with LOG.open("a", encoding="utf-8") as log:
                log.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} ATTEMPT {attempt} {type(exc).__name__}: {exc}\n")
            if attempt >= max_attempts:
                return 1
            await asyncio.sleep(min(float(cfg["API_RETRY_MAX_SECONDS"]), float(cfg["API_RETRY_BASE_SECONDS"]) * 2 ** (attempt - 1)))
        finally:
            if audio_path is not None:
                audio_path.unlink(missing_ok=True)
    return 1


def selection(notify_empty=None) -> int:
    # Ctrl+C is used only on explicit hotkey; restore clipboard text afterwards.
    import keyboard
    import tkinter as tk
    root = tk.Tk(); root.withdraw()
    try:
        try: previous = root.clipboard_get()
        except tk.TclError: previous = ""
        root.clipboard_clear(); root.update()
        keyboard.press_and_release("ctrl+c")
        time.sleep(0.18)
        try: text = root.clipboard_get()
        except tk.TclError: text = ""
        root.clipboard_clear()
        if previous:
            root.clipboard_append(previous)
        root.update()
    finally:
        root.destroy()
    if not text.strip():
        if notify_empty is not None:
            notify_empty()
        else:
            print("Сначала выдели текст", file=sys.stderr)
        return 0
    start(text); return 0


def hotkey() -> None:
    import keyboard
    shortcut = settings()["HOTKEY"].strip()
    if not shortcut:
        raise ValueError("HOTKEY не может быть пустым")
    print(f"Горячая клавиша активна: {shortcut}")
    keyboard.add_hotkey(shortcut, selection)
    keyboard.wait()


def tray() -> None:
    import keyboard
    import pystray
    from PIL import Image, ImageDraw, ImageFont

    STATE.mkdir(parents=True, exist_ok=True)
    try:
        with TRAY_PID.open("x", encoding="ascii") as tray_file:
            tray_file.write(str(os.getpid()))
    except FileExistsError:
        try:
            old_pid = int(TRAY_PID.read_text(encoding="ascii"))
            os.kill(old_pid, 0)
            raise RuntimeError("Значок утилиты уже запущен")
        except (OSError, ValueError):
            TRAY_PID.unlink(missing_ok=True)
            TRAY_PID.write_text(str(os.getpid()), encoding="ascii")
    cfg = settings()

    def make_icon(mode: str, elapsed: int) -> Image.Image:
        image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        color = (255, 174, 65, 255) if mode == "waiting" else (65, 210, 145, 255)
        if mode == "waiting":
            draw.ellipse((10, 5, 54, 49), outline=color, width=5)
            draw.line((32, 14, 32, 28, 41, 33), fill=color, width=4)
        else:
            for x, height in zip((14, 24, 34, 44, 54), (14, 28, 20, 34, 17)):
                draw.rounded_rectangle((x - 3, 40 - height, x + 3, 40), radius=2, fill=color)
        try:
            font = ImageFont.truetype("arial.ttf", 28)
        except OSError:
            font = ImageFont.load_default()
        # The shell downsamples tray icons to 16x16; use large digits here and
        # expose the full elapsed time in the tooltip.
        label = f"{elapsed % 100:02d}"
        draw.rounded_rectangle((7, 39, 57, 63), radius=4, fill=(30, 34, 42, 245))
        box = draw.textbbox((0, 0), label, font=font)
        text_x = (64 - (box[2] - box[0])) / 2 - box[0]
        text_y = (39 + 64 - (box[3] - box[1])) / 2 - box[1]
        draw.text((text_x, text_y), label, font=font, fill=(245, 245, 245, 255))
        return image

    def stop_item(_icon: object, _item: object) -> None:
        stop_speech()

    def quit_item(icon: object, _item: object) -> None:
        keyboard.unhook_all_hotkeys()
        icon.stop()

    icon = pystray.Icon(
        "selected-text-speech", make_icon("waiting", 0), "Озвучивание: готово",
        menu=pystray.Menu(
            pystray.MenuItem("Остановить озвучивание", stop_item),
            pystray.MenuItem(f"Хоткей: {cfg['HOTKEY']}", None, enabled=False),
            pystray.MenuItem("Выход", quit_item),
        ),
    )

    def on_hotkey() -> None:
        try:
            selection(lambda: icon.notify("Сначала выдели текст", "Озвучивание"))
        except Exception as exc:
            with LOG.open("a", encoding="utf-8") as log:
                log.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} HOTKEY_ERROR {type(exc).__name__}: {exc}\n")

    keyboard.add_hotkey(cfg["HOTKEY"], on_hotkey)

    def update_status() -> None:
        while True:
            if not icon.visible:
                time.sleep(0.2)
                continue
            pid = active_pid()
            if pid:
                try:
                    started = float(STARTED.read_text(encoding="ascii"))
                except (OSError, ValueError):
                    started = time.time()
                elapsed = max(0, int(time.time() - started))
                playing = PLAYING.exists()
                icon.icon = make_icon("playing" if playing else "waiting", elapsed)
                icon.title = f"{'Идёт озвучивание' if playing else 'Ожидание TTS'} • {elapsed} с"
            else:
                icon.icon = make_icon("waiting", 0)
                icon.title = "Озвучивание текста • готово"
            time.sleep(1)

    import threading
    threading.Thread(target=update_status, daemon=True).start()
    try:
        icon.run()
    finally:
        keyboard.unhook_all_hotkeys()
        try:
            if TRAY_PID.read_text(encoding="ascii").strip() == str(os.getpid()): TRAY_PID.unlink()
        except (OSError, ValueError):
            pass


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
            PLAYING.unlink(missing_ok=True)
            STARTED.unlink(missing_ok=True)
    if args == ["stop"]:
        stopped = stop_speech()
        print("Озвучивание остановлено" if stopped else "Озвучивание не запущено")
        return 0
    if args == ["status"]:
        pid = active_pid(); print(f"Озвучивание запущено (PID {pid})" if pid else "Озвучивание не запущено")
        return 0 if pid else 1
    if args == ["selection"]: return selection()
    if args == ["hotkey"]: hotkey(); return 0
    if args == ["tray"]: tray(); return 0
    if args and args[0] == "speak": args = args[1:]
    if not args: print("Использование: speak TEXT | stop | status | selection | hotkey"); return 2
    return 0 if start(" ".join(args)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
