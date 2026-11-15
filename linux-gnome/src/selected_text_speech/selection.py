from __future__ import annotations

import os
import shutil
import subprocess


def selected_text() -> str:
    if os.environ.get("WAYLAND_DISPLAY") and shutil.which("wl-paste"):
        command = ["wl-paste", "--primary", "--no-newline"]
    elif shutil.which("xclip"):
        command = ["xclip", "-o", "-selection", "primary"]
    elif shutil.which("xsel"):
        command = ["xsel", "--output", "--primary"]
    else:
        raise RuntimeError("Не найден wl-paste, xclip или xsel для чтения выделения")
    result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=3)
    return result.stdout.strip() if result.returncode == 0 else ""
