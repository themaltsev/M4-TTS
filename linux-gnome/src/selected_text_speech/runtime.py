from __future__ import annotations

import fcntl
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


def state_dir() -> Path:
    # Keep runtime state beside the project source; the directory is git-ignored.
    root = Path(__file__).resolve().parents[3]
    directory = root / ".runtime"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        directory.chmod(0o700)
    except OSError:
        pass
    return directory


@contextmanager
def launch_lock() -> Iterator[None]:
    path = state_dir() / "lock"
    with path.open("a") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def worker_pid() -> int | None:
    path = state_dir() / "worker.pid"
    try:
        pid = int(path.read_text(encoding="ascii").strip())
        if pid <= 1:
            raise ValueError
        os.kill(pid, 0)
        cmdline = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ")
        new_worker = b"selected_text_speech.worker" in cmdline
        legacy_worker = b"speak-selection" in cmdline and b"--worker" in cmdline
        if not (new_worker or legacy_worker) or os.getpgid(pid) != pid:
            raise ValueError
        return pid
    except (FileNotFoundError, ProcessLookupError, PermissionError, ValueError, OSError):
        path.unlink(missing_ok=True)
        return None


def write_worker_pid(pid: int) -> None:
    path = state_dir() / "worker.pid"
    temp = path.with_suffix(".pid.tmp")
    temp.write_text(f"{pid}\n", encoding="ascii")
    temp.chmod(0o600)
    os.replace(temp, path)


def clear_worker_pid(pid: int) -> None:
    path = state_dir() / "worker.pid"
    try:
        if int(path.read_text(encoding="ascii").strip()) == pid:
            path.unlink(missing_ok=True)
    except (FileNotFoundError, ValueError):
        pass


def package_environment() -> dict[str, str]:
    env = os.environ.copy()
    package_root = str(Path(__file__).resolve().parent.parent)
    env["PYTHONPATH"] = package_root + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env["PATH"] = env.get("PATH", "/usr/bin:/bin")
    env["PYTHONUNBUFFERED"] = "1"
    for name in ("DESKTOP_STARTUP_ID", "GIO_LAUNCHED_DESKTOP_FILE", "GIO_LAUNCHED_DESKTOP_FILE_PID"):
        env.pop(name, None)
    return env


def system_python() -> str:
    candidate = Path("/usr/bin/python3")
    return str(candidate) if candidate.is_file() else sys.executable
