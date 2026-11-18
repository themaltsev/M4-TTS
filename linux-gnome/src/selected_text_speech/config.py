from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def config_files() -> tuple[Path, Path]:
    root = project_root()
    return root / "config.local.env", root / "config.env"


def _load_env_file() -> None:
    for path in config_files():
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            continue
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


def _project_path(value: str | Path, root: Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else root / path


@dataclass(frozen=True)
class Config:
    engine: str
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
    piper_python: Path
    piper_model: Path
    piper_sample_rate: int
    piper_channels: int
    piper_length_scale: float
    piper_volume: float

    @classmethod
    def load(cls) -> "Config":
        _load_env_file()
        root = project_root()
        playback_speed = _float("MPV_PLAYBACK_SPEED", 1.35, 0.25, 4.0)
        engine = os.environ.get("TTS_ENGINE", "piper").strip().lower()
        if engine not in {"piper", "edge"}:
            raise ValueError("TTS_ENGINE must be 'piper' or 'edge'")

        piper_python = _project_path(os.environ.get("PIPER_PYTHON", ".venv/bin/python"), root)
        piper_model = _project_path(
            os.environ.get("PIPER_MODEL", "models/ru_RU-irina-medium.onnx"), root
        )
        piper_config = Path(f"{piper_model}.json")
        sample_rate = 22050
        try:
            sample_rate = int(json.loads(piper_config.read_text(encoding="utf-8"))["audio"]["sample_rate"])
        except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            pass

        edge_python = _project_path(os.environ.get("EDGE_TTS_PYTHON", ".venv/bin/python"), root)
        return cls(
            engine=engine,
            voice=os.environ.get("EDGE_TTS_VOICE", "ru-RU-SvetlanaNeural"),
            rate=os.environ.get("EDGE_TTS_RATE", "+0%"),
            tts_volume=os.environ.get("EDGE_TTS_VOLUME", "+0%"),
            pitch=os.environ.get("EDGE_TTS_PITCH", "+0Hz"),
            playback_speed=playback_speed,
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
            sound_dir=root / "linux-gnome/share/sounds",
            edge_python=edge_python,
            piper_python=piper_python,
            piper_model=piper_model,
            piper_sample_rate=_int("PIPER_SAMPLE_RATE", sample_rate, 8000, 96000),
            piper_channels=_int("PIPER_CHANNELS", 1, 1, 2),
            piper_length_scale=_float(
                "PIPER_LENGTH_SCALE", 1.0 / playback_speed, 0.25, 4.0
            ),
            piper_volume=_float("PIPER_VOLUME", 1.0, 0.1, 4.0),
        )

    def sound_path(self, value: str) -> Path:
        path = Path(value).expanduser()
        return path if path.is_absolute() else self.sound_dir / path
