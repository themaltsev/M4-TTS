from __future__ import annotations

import hashlib
import os
import sys
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen

BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main/ru/ru_RU/irina/medium"
FILES = {
    "ru_RU-irina-medium.onnx": "8ff38212d23da300bbe3705c645e6e5b9475f0bfde01558eb17813e22acaaaaa",
    "ru_RU-irina-medium.onnx.json": "c2ec28bb38e2b59e93b959b3e40348c1afebbd272f30fed5d41205d08e98a9d7",
}


def digest(path: Path) -> str:
    checksum = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


def fetch(name: str, expected: str, directory: Path) -> None:
    destination = directory / name
    if destination.is_file() and digest(destination) == expected:
        print(f"OK {destination}")
        return
    request = Request(f"{BASE}/{name}", headers={"User-Agent": "selected-text-speech-installer"})
    fd, temporary_name = tempfile.mkstemp(prefix=f".{name}.", dir=directory)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as output, urlopen(request, timeout=120) as response:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        actual = digest(temporary)
        if actual != expected:
            raise RuntimeError(f"SHA-256 mismatch for {name}: {actual}")
        temporary.replace(destination)
        print(f"Installed {destination}")
    finally:
        temporary.unlink(missing_ok=True)


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: download_voice.py DESTINATION_DIR", file=sys.stderr)
        return 2
    destination = Path(sys.argv[1]).expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    for name, expected in FILES.items():
        fetch(name, expected, destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
