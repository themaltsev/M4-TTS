"""macOS menu-bar runtime for selected-text-speech."""
from __future__ import annotations

import asyncio
import fcntl
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

APP = "selected-text-speech"
SUPPORT = Path.home() / "Library" / "Application Support" / APP
CONFIG = SUPPORT / "config.env"
STATE = SUPPORT / "state"
PID = STATE / "worker.pid"
STARTED = STATE / "started-at"
PLAYING = STATE / "playing"
LOG = STATE / "tts.log"


def settings() -> dict[str, str]:
    values = {
        "EDGE_TTS_VOICE": "ru-RU-SvetlanaNeural", "EDGE_TTS_RATE": "+0%",
        "EDGE_TTS_VOLUME": "+0%", "EDGE_TTS_PITCH": "+0Hz",
        "EDGE_TTS_CONNECT_TIMEOUT": "10", "EDGE_TTS_RECEIVE_TIMEOUT": "60",
        "MPV_PLAYBACK_SPEED": "1.35", "MPV_PLAYBACK_VOLUME": "100",
        "API_MAX_ATTEMPTS": "3", "API_RETRY_BASE_SECONDS": "1.5",
        "API_RETRY_MAX_SECONDS": "8", "HOTKEY": "cmd+esc",
    }
    try:
        for line in CONFIG.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                if key.strip() in values:
                    values[key.strip()] = value.strip().strip("\"'")
    except FileNotFoundError:
        pass
    values.update({key: value for key, value in os.environ.items() if key in values})
    return values


def state_dir() -> None:
    STATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        STATE.chmod(0o700)
    except OSError:
        pass


def active_pid() -> int | None:
    try:
        pid = int(PID.read_text(encoding="ascii").strip())
        os.kill(pid, 0)
        if os.getpgid(pid) != pid:
            raise ValueError("not an isolated speech process")
        cmd = subprocess.run(["ps", "-p", str(pid), "-o", "command="], capture_output=True, text=True, timeout=2).stdout
        if str(Path(__file__).resolve()) not in cmd:
            raise ValueError("PID no longer belongs to speech process")
        return pid
    except (OSError, ValueError, subprocess.TimeoutExpired):
        PID.unlink(missing_ok=True)
        return None


def start(text: str) -> int:
    text = text.strip()
    if not text:
        raise ValueError("Выдели текст или передай его команде speak")
    state_dir()
    with (STATE / "lock").open("a") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        if active_pid():
            raise RuntimeError("Озвучивание уже запущено; останови текущую речь")
        STARTED.write_text(str(time.time()), encoding="ascii")
        PLAYING.unlink(missing_ok=True)
        with LOG.open("a", encoding="utf-8") as log:
            proc = subprocess.Popen(
                [sys.executable, str(Path(__file__).resolve()), "--worker"],
                stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        PID.write_text(str(proc.pid), encoding="ascii")
        PID.chmod(0o600)
        assert proc.stdin is not None
        try:
            proc.stdin.write(text.encode("utf-8"))
            proc.stdin.close()
        except BrokenPipeError as error:
            PID.unlink(missing_ok=True)
            raise RuntimeError("Не удалось запустить процесс озвучивания") from error
    return proc.pid


def stop() -> bool:
    pid = active_pid()
    if pid is None:
        return False
    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.05)
    else:
        try:
            os.killpg(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    PID.unlink(missing_ok=True)
    PLAYING.unlink(missing_ok=True)
    STARTED.unlink(missing_ok=True)
    return True


class Cancelled(Exception):
    pass


def _cancel(_signum: int, _frame: object) -> None:
    raise Cancelled


async def worker(text: str) -> int:
    import edge_tts

    cfg = settings()
    attempts = max(1, min(8, int(cfg["API_MAX_ATTEMPTS"])))
    log_path = LOG
    for attempt in range(1, attempts + 1):
        audio_started = False
        player: subprocess.Popen[bytes] | None = None
        try:
            client = edge_tts.Communicate(
                text, voice=cfg["EDGE_TTS_VOICE"], rate=cfg["EDGE_TTS_RATE"],
                volume=cfg["EDGE_TTS_VOLUME"], pitch=cfg["EDGE_TTS_PITCH"],
                connect_timeout=int(cfg["EDGE_TTS_CONNECT_TIMEOUT"]),
                receive_timeout=int(cfg["EDGE_TTS_RECEIVE_TIMEOUT"]),
            )
            async for chunk in client.stream():
                if chunk["type"] != "audio":
                    continue
                if player is None:
                    with log_path.open("ab") as player_log:
                        player = subprocess.Popen(
                            ["mpv", "--no-video", "--really-quiet",
                             f"--speed={cfg['MPV_PLAYBACK_SPEED']}",
                             f"--volume={cfg['MPV_PLAYBACK_VOLUME']}", "--cache=no", "-"],
                            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                            stderr=player_log,
                        )
                assert player.stdin is not None
                player.stdin.write(chunk["data"])
                player.stdin.flush()
                if not audio_started:
                    audio_started = True
                    PLAYING.write_text(str(time.time()), encoding="ascii")
            if player is None:
                raise RuntimeError("Edge TTS did not return audio")
            assert player.stdin is not None
            player.stdin.close()
            player.stdin = None
            player_code = player.wait()
            if player_code == 0:
                return 0
            raise RuntimeError(f"mpv exited with status {player_code}")
        except Cancelled:
            raise
        except Exception as error:
            if player is not None and player.poll() is None:
                player.terminate()
                try:
                    player.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    player.kill()
            with log_path.open("a", encoding="utf-8") as log:
                log.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} ATTEMPT {attempt} "
                          f"audio_started={audio_started} {type(error).__name__}: {error}\n")
            if audio_started or attempt >= attempts:
                return 1
            PLAYING.unlink(missing_ok=True)
            delay = min(float(cfg["API_RETRY_MAX_SECONDS"]), float(cfg["API_RETRY_BASE_SECONDS"]) * 2 ** (attempt - 1))
            await asyncio.sleep(delay)
    return 1


def selection() -> None:
    import pynput.keyboard

    previous = subprocess.run(["pbpaste"], capture_output=True, check=False).stdout
    controller = pynput.keyboard.Controller()
    with controller.pressed(pynput.keyboard.Key.cmd):
        controller.press("c")
        controller.release("c")
    time.sleep(0.18)
    selected = subprocess.run(["pbpaste"], capture_output=True, check=False).stdout.decode("utf-8", errors="replace")
    subprocess.run(["pbcopy"], input=previous, check=False)
    if selected.strip():
        start(selected)


def hotkey_listener(shortcut: str) -> None:
    from pynput import keyboard

    aliases = {"cmd": "cmd", "command": "cmd", "ctrl": "ctrl", "control": "ctrl",
               "alt": "alt", "option": "alt", "shift": "shift", "esc": "esc",
               "escape": "esc", "space": "space", "return": "enter"}
    parts = [part.strip().lower() for part in shortcut.split("+") if part.strip()]
    if len(parts) < 2:
        raise ValueError("HOTKEY должен содержать минимум модификатор и клавишу, например cmd+esc")
    normalized = [aliases.get(part, part) for part in parts]
    hotkey = "+".join(token if len(token) == 1 and token.isalnum() else f"<{token}>"
                       for token in normalized)
    listener = keyboard.GlobalHotKeys({hotkey: selection})
    listener.daemon = True
    listener.start()


def tray() -> None:
    import rumps

    cfg = settings()
    try:
        hotkey_listener(cfg["HOTKEY"])
    except Exception as error:
        with LOG.open("a", encoding="utf-8") as log:
            log.write(f"HOTKEY_ERROR {type(error).__name__}: {error}\n")

    class SpeechApp(rumps.App):
        def __init__(self) -> None:
            super().__init__("◷", title="◷", quit_button=None)
            self.stop_item = rumps.MenuItem("Остановить озвучивание", callback=self.stop_speech)
            self.hotkey_item = rumps.MenuItem(f"Хоткей: {cfg['HOTKEY']}")
            self.hotkey_item.set_callback(None)
            self.quit_item = rumps.MenuItem("Выход", callback=lambda _sender: rumps.quit_application())
            self.menu = [self.stop_item, self.hotkey_item, None, self.quit_item]
            self.timer = rumps.Timer(self.update_status, 1)
            self.timer.start()

        def update_status(self, _timer: object) -> None:
            pid = active_pid()
            if pid is None:
                self.title = "◷"
                self.stop_item.set_callback(None)
                return
            try:
                elapsed = max(0, int(time.time() - float(STARTED.read_text(encoding="ascii"))))
            except (OSError, ValueError):
                elapsed = 0
            if PLAYING.exists():
                self.title = f"▂▅▃ {elapsed}s"
            else:
                self.title = f"◷ {elapsed}s"
            self.stop_item.set_callback(self.stop_speech)

        def stop_speech(self, _sender: object) -> None:
            stop()
            self.title = "◷"

    SpeechApp().run()


def main() -> int:
    args = sys.argv[1:]
    state_dir()
    if args == ["--worker"]:
        text = sys.stdin.buffer.read().decode("utf-8", errors="replace")
        signal.signal(signal.SIGTERM, _cancel)
        signal.signal(signal.SIGINT, _cancel)
        try:
            return asyncio.run(worker(text))
        except Cancelled:
            return 143
        finally:
            try:
                if PID.read_text(encoding="ascii").strip() == str(os.getpid()):
                    PID.unlink()
            except (OSError, ValueError):
                pass
            PLAYING.unlink(missing_ok=True)
            STARTED.unlink(missing_ok=True)
    if args == ["tray"]:
        tray()
        return 0
    if args == ["stop"]:
        print("Озвучивание остановлено" if stop() else "Озвучивание не запущено")
        return 0
    if args == ["status"]:
        pid = active_pid()
        print(f"Озвучивание запущено (PID {pid})" if pid else "Озвучивание не запущено")
        return 0 if pid else 1
    if args == ["selection"]:
        selection()
        return 0
    if args and args[0] == "speak":
        args = args[1:]
    if args:
        print(f"Озвучивание запущено (PID {start(' '.join(args))})")
        return 0
    if not sys.stdin.isatty():
        print(f"Озвучивание запущено (PID {start(sys.stdin.read())})")
        return 0
    print("Использование: speak TEXT | speak-selection | stop-speech | speak-status", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
