from __future__ import annotations

import sys
from pathlib import Path


def add_package_paths(script: str) -> None:
    script_path = Path(script).resolve()
    source_root = script_path.parents[1] / "src"
    installed_root = Path.home() / ".local/lib"
    for root in (source_root, installed_root):
        if (root / "selected_text_speech").is_dir():
            sys.path.insert(0, str(root))
            return
    raise SystemExit("Не найдены файлы приложения; повтори установку через ./install.sh")
