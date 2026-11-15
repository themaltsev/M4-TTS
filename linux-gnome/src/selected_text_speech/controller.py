from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path

from .config import Config
from .runtime import clear_worker_pid, launch_lock, package_environment, state_dir, system_python, worker_pid, write_worker_pid


def _notify(title: str, body: str) -> None:
    try:
        subprocess.run(["notify-send", title, body], check=False, timeout=3)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass


def _play_sound(config: Config, sound: str) -> None:
    path = config.sound_path(sound)
    if not path.is_file():
        return
    log_path = state_dir() / "cues.log"
    try:
        with log_path.open("ab") as log:
            subprocess.run(
                ["mpv", "--no-video", "--really-quiet", f"--volume={config.cue_volume}", "--", str(path)],
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=False,
                timeout=12,
            )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass


def _launch_locked(text: str) -> int:
    log = (state_dir() / "tts.log").open("ab", buffering=0)
    env = package_environment()
    env["SELECTED_TEXT_STARTED_MONOTONIC"] = str(time.monotonic())
    try:
        process = subprocess.Popen(
            [system_python(), "-m", "selected_text_speech.worker"],
            stdin=subprocess.PIPE,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            env=env,
        )
    finally:
        log.close()
    write_worker_pid(process.pid)
    assert process.stdin is not None
    try:
        process.stdin.write(text.encode("utf-8"))
        process.stdin.close()
    except BrokenPipeError:
        clear_worker_pid(process.pid)
        raise RuntimeError("Не удалось передать текст процессу озвучивания")
    return process.pid


def start_text(text: str) -> int:
    text = text.strip()
    if not text:
        raise ValueError("Передай текст: speak 'текст для озвучивания' или используй speak-selection")
    config = Config.load()
    with launch_lock():
        active = worker_pid()
        if active is not None:
            raise RuntimeError(f"Озвучивание уже запущено (PID {active}); остановить: stop-speech")
        return _launch_locked(text)


def _stop_locked() -> bool:
    pid = worker_pid()
    if pid is None:
        return False
    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    deadline = time.monotonic() + 0.5
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
    clear_worker_pid(pid)
    return True


def stop_speech() -> bool:
    with launch_lock():
        stopped = _stop_locked()
    if stopped:
        try:
            config = Config.load()
            _play_sound(config, config.cancel_sound)
        except (ValueError, OSError):
            pass
    return stopped


def toggle_selection() -> str:
    with launch_lock():
        if _stop_locked():
            action = "stopped"
        else:
            try:
                config = Config.load()
            except (ValueError, OSError) as error:
                _notify("Ошибка конфигурации озвучивания", str(error))
                return "error"
            from .selection import selected_text

            try:
                text = selected_text()
            except (RuntimeError, subprocess.TimeoutExpired) as error:
                _notify("Озвучивание", str(error))
                return "error"
            if not text:
                _notify("Озвучивание", "Сначала выдели текст")
                return "empty"
            _launch_locked(text)
            action = "started"
    if action == "stopped":
        try:
            config = Config.load()
            _play_sound(config, config.cancel_sound)
        except (ValueError, OSError):
            pass
    return action


def status() -> int | None:
    return worker_pid()
