from __future__ import annotations

import sys
from pathlib import Path


def add_package_paths(script: str) -> None:
    script_path = Path(script).resolve()
    source_root = script_path.parents[1] / "src"
    if source_root.is_dir():
        sys.path.insert(0, str(source_root))
        return
    raise SystemExit("Исходники приложения не найдены рядом со скриптом; проверь checkout проекта")
