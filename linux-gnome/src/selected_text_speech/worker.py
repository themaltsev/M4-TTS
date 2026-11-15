from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from .config import Config
from .runtime import clear_worker_pid, package_environment, state_dir


class Cancelled(Exception):
    pass


def _handle_signal(_signum: int, _frame: object) -> None:
    raise Cancelled


def _log(log_path: Path, message: str) -> None:
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    with log_path.open("a", encoding="utf-8") as log:
        print(f"{stamp} {message}", file=log, flush=True)


def _play(config: Config, sound: str, log_path: Path) -> None:
    path = config.sound_path(sound)
    if not path.is_file():
        _log(log_path, f"CUE_MISSING path={path}")
        return
    with (state_dir() / "cues.log").open("ab") as log:
        try:
            result = subprocess.run(
                ["mpv", "--no-video", "--really-quiet", f"--volume={config.cue_volume}", "--", str(path)],
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=False,
                timeout=12,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as error:
            _log(log_path, f"CUE_ERROR {type(error).__name__}")
            return
    if result.returncode:
        _log(log_path, f"CUE_ERROR mpv_exit={result.returncode}")


def _notify(body: str) -> None:
    try:
        subprocess.run(["notify-send", "Озвучивание", body], check=False, timeout=3)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass


def _run_stream(text: str, config: Config, tick: subprocess.Popen[bytes], indicator: subprocess.Popen[bytes], attempt: int) -> tuple[int, int, bool]:
    paths = state_dir()
    marker = paths / "first-audio.marker"
    marker.unlink(missing_ok=True)
    env = package_environment()
    env.update(
        {
            "TTS_TICK_PID": str(tick.pid),
            "TTS_INDICATOR_PID": str(indicator.pid),
            "TTS_FIRST_AUDIO_MARKER": str(marker),
            "EDGE_TTS_VOICE": config.voice,
            "EDGE_TTS_RATE": config.rate,
            "EDGE_TTS_VOLUME": config.tts_volume,
            "EDGE_TTS_PITCH": config.pitch,
            "EDGE_TTS_CONNECT_TIMEOUT": str(config.connect_timeout),
            "EDGE_TTS_RECEIVE_TIMEOUT": str(config.receive_timeout),
        }
    )
    log_path = paths / "tts.log"
    _log(log_path, f"API_ATTEMPT_START n={attempt} voice={config.voice}")
    started = time.monotonic()
    with log_path.open("ab", buffering=0) as log:
        streamer = subprocess.Popen(
            [str(config.edge_python), "-m", "selected_text_speech.streamer"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=log,
            env=env,
        )
        assert streamer.stdin is not None and streamer.stdout is not None
        try:
            player = subprocess.Popen(
                [
                    "mpv", "--no-video", f"--speed={config.playback_speed}",
                    f"--volume={config.playback_volume}", "--really-quiet", "--cache=no", "-",
                ],
                stdin=streamer.stdout,
                stdout=subprocess.DEVNULL,
                stderr=log,
            )
        except Exception:
            streamer.terminate()
            streamer.wait(timeout=2)
            raise
        finally:
            streamer.stdout.close()
        try:
            streamer.stdin.write(text.encode("utf-8"))
            streamer.stdin.close()
        except BrokenPipeError:
            pass
        player_code = player.wait()
        streamer_code = streamer.wait()
    first_audio = marker.exists()
    elapsed = time.monotonic() - started
    _log(
        log_path,
        f"API_ATTEMPT_END n={attempt} elapsed={elapsed:.2f}s first_audio={str(first_audio).lower()} "
        f"stream_exit={streamer_code} player_exit={player_code}",
    )
    return streamer_code, player_code, first_audio


def run() -> int:
    text = sys.stdin.read()
    if not text.strip():
        _log(state_dir() / "tts.log", "WORKER_ERROR empty_input")
        return 2
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)
    log_path = state_dir() / "tts.log"
    indicator: subprocess.Popen[bytes] | None = None
    tick: subprocess.Popen[bytes] | None = None
    try:
        config = Config.load()
        # Keep the prior punctuation timing adjustment while avoiding shell-based text munging.
        text = text.replace(",", " ").replace(".", ",").replace("\n", " ")
        indicator_env = package_environment()
        indicator_env["SELECTED_TEXT_STARTED_MONOTONIC"] = os.environ.get(
            "SELECTED_TEXT_STARTED_MONOTONIC", str(time.monotonic())
        )
        with (state_dir() / "indicator.log").open("ab") as indicator_log:
            indicator = subprocess.Popen(
                [sys.executable, "-m", "selected_text_speech.indicator"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=indicator_log,
                start_new_session=True,
                env=indicator_env,
            )
        _log(log_path, f"WORKER_START voice={config.voice} speed={config.playback_speed}")
        _play(config, config.start_sound, log_path)
        with (state_dir() / "tick.log").open("ab") as tick_log:
            tick = subprocess.Popen(
                [sys.executable, "-m", "selected_text_speech.tick"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=tick_log,
                env=package_environment(),
            )
        for attempt in range(1, config.max_attempts + 1):
            assert tick is not None and indicator is not None
            stream_code, player_code, first_audio = _run_stream(text, config, tick, indicator, attempt)
            if stream_code == 0 and player_code == 0:
                _log(log_path, "WORKER_SUCCESS")
                return 0
            if first_audio:
                _log(log_path, "WORKER_ERROR stream_interrupted_after_audio; not replaying speech")
                _notify("Аудиопоток прервался после начала; смотри tts.log")
                return 1
            if attempt < config.max_attempts:
                delay = min(config.retry_max_seconds, config.retry_base_seconds * (2 ** (attempt - 1)))
                _log(log_path, f"API_RETRY n={attempt} delay={delay:.1f}s")
                time.sleep(delay)
        _log(log_path, f"WORKER_ERROR no_audio attempts={config.max_attempts}")
        _notify(f"Edge TTS не прислал аудио после {config.max_attempts} попыток; смотри tts.log")
        return 1
    except Cancelled:
        _log(log_path, "WORKER_CANCELLED")
        return 143
    except Exception as error:
        _log(log_path, f"WORKER_ERROR {type(error).__name__}: {error}")
        _notify("Ошибка запуска озвучивания; смотри tts.log")
        return 1
    finally:
        if tick is not None and tick.poll() is None:
            tick.terminate()
            try:
                tick.wait(timeout=2)
            except subprocess.TimeoutExpired:
                tick.kill()
        if indicator is not None and indicator.poll() is None:
            indicator.terminate()
            try:
                indicator.wait(timeout=2)
            except subprocess.TimeoutExpired:
                indicator.kill()
        (state_dir() / "first-audio.marker").unlink(missing_ok=True)
        clear_worker_pid(os.getpid())


if __name__ == "__main__":
    raise SystemExit(run())
