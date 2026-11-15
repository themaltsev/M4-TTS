from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path


def config_file() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "selected-text-speech" / "config.env"


def _load_env_file() -> None:
    path = config_file()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", key):
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(key, value)


def _int(name: str, default: int, minimum: int, maximum: int) -> int:
    value = int(os.environ.get(name, str(default)))
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def _float(name: str, default: float, minimum: float, maximum: float) -> float:
    value = float(os.environ.get(name, str(default)))
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


@dataclass(frozen=True)
class Config:
    voice: str
    rate: str
    tts_volume: str
    pitch: str
    playback_speed: float
    playback_volume: int
    cue_volume: int
    tick_volume_db: float
    connect_timeout: int
    receive_timeout: int
    max_attempts: int
    retry_base_seconds: float
    retry_max_seconds: float
    start_sound: str
    cancel_sound: str
    tick_sound: str
    sound_dir: Path
    edge_python: Path

    @classmethod
    def load(cls) -> "Config":
        _load_env_file()
        home = Path.home()
        data_home = Path(os.environ.get("XDG_DATA_HOME", home / ".local/share"))
        edge_python = data_home / "pipx/venvs/edge-tts/bin/python"
        if not edge_python.exists():
            # Older installations used the literal ~/.local/share path.
            edge_python = home / ".local/share/pipx/venvs/edge-tts/bin/python"
        return cls(
            voice=os.environ.get("EDGE_TTS_VOICE", "ru-RU-SvetlanaNeural"),
            rate=os.environ.get("EDGE_TTS_RATE", "+0%"),
            tts_volume=os.environ.get("EDGE_TTS_VOLUME", "+0%"),
            pitch=os.environ.get("EDGE_TTS_PITCH", "+0Hz"),
            playback_speed=_float("MPV_PLAYBACK_SPEED", 1.35, 0.25, 4.0),
            playback_volume=_int("MPV_PLAYBACK_VOLUME", 100, 0, 100),
            cue_volume=_int("CUE_VOLUME", 100, 0, 100),
            tick_volume_db=float(os.environ.get("TICK_VOLUME_DB", "-12.0")),
            connect_timeout=_int("EDGE_TTS_CONNECT_TIMEOUT", 10, 1, 120),
            receive_timeout=_int("EDGE_TTS_RECEIVE_TIMEOUT", 60, 1, 600),
            max_attempts=_int("API_MAX_ATTEMPTS", 3, 1, 8),
            retry_base_seconds=_float("API_RETRY_BASE_SECONDS", 1.5, 0.1, 30.0),
            retry_max_seconds=_float("API_RETRY_MAX_SECONDS", 8.0, 0.1, 120.0),
            start_sound=os.environ.get("START_SOUND", "speech-start.oga"),
            cancel_sound=os.environ.get("CANCEL_SOUND", "speech-cancel.oga"),
            tick_sound=os.environ.get("TICK_SOUND", "openclaw-soft-tick.wav"),
            sound_dir=data_home / "selected-text-speech/sounds",
            edge_python=edge_python,
        )

    def sound_path(self, value: str) -> Path:
        path = Path(value).expanduser()
        return path if path.is_absolute() else self.sound_dir / path
