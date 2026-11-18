#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
target_command="$repo_dir/linux-gnome/bin/speak-selection"
schema="org.gnome.settings-daemon.plugins.media-keys.custom-keybinding"
global_schema="org.gnome.settings-daemon.plugins.media-keys"
runtime_mode=prompt

case "${1:-}" in
  "") ;;
  --keep-runtime) runtime_mode=keep ;;
  --remove-runtime) runtime_mode=remove ;;
  -h|--help)
    cat <<'USAGE'
Usage: ./uninstall-linux.sh [--keep-runtime|--remove-runtime]

Removes this checkout's GNOME hotkey. By default, asks whether to move the
checkout-local .venv, .runtime and models directories to the user's Trash.
The source checkout and config.local.env are always kept. System packages
installed by install-linux.sh are not removed because they may be shared.
USAGE
    exit 0
    ;;
  *)
    echo "Неизвестный аргумент: $1 (см. --help)." >&2
    exit 2
    ;;
esac

if command -v gsettings >/dev/null 2>&1; then
  key_list="$(gsettings get "$global_schema" custom-keybindings 2>/dev/null || true)"
  if [[ -n "$key_list" ]]; then
    mapfile -t matching_paths < <(python3 - "$key_list" "$schema" "$target_command" <<'PY'
import ast
import subprocess
import sys

raw, schema, target = sys.argv[1:]
if raw.startswith("@as"):
    raw = raw[3:].strip()
for path in ast.literal_eval(raw):
    try:
        value = subprocess.check_output(
            ["gsettings", "get", f"{schema}:{path}", "command"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        if ast.literal_eval(value) == target:
            print(path)
    except (OSError, ValueError, SyntaxError, subprocess.CalledProcessError):
        continue
PY
)
    if ((${#matching_paths[@]})); then
      for key_path in "${matching_paths[@]}"; do
        gsettings reset "$schema:$key_path" name >/dev/null 2>&1 || true
        gsettings reset "$schema:$key_path" command >/dev/null 2>&1 || true
        gsettings reset "$schema:$key_path" binding >/dev/null 2>&1 || true
      done
      new_key_list="$(python3 - "$key_list" "${matching_paths[@]}" <<'PY'
import ast
import sys

raw, *remove_paths = sys.argv[1:]
if raw.startswith("@as"):
    raw = raw[3:].strip()
paths = [path for path in ast.literal_eval(raw) if path not in remove_paths]
print("[" + ", ".join(repr(path) for path in paths) + "]")
PY
)"
      if gsettings set "$global_schema" custom-keybindings "$new_key_list"; then
        echo "Хоткей этого checkout удалён из GNOME."
      else
        echo "Не удалось удалить хоткей из GNOME; проверь активный сеанс пользователя." >&2
      fi
    else
      echo "Хоткей этого checkout не найден; другие сочетания клавиш не менялись."
    fi
  else
    echo "Не удалось прочитать настройки GNOME; хоткей не менялся." >&2
  fi
else
  echo "gsettings не найден; пропускаю удаление GNOME-хоткея." >&2
fi

if [[ "$runtime_mode" == prompt ]]; then
  if [[ -r /dev/tty ]]; then
    runtime_mode=keep
    read -r -p "Переместить .venv, .runtime и models этого checkout в Корзину? [y/N] " answer </dev/tty || answer=n
    if [[ "$answer" =~ ^[YyДд]$ ]]; then runtime_mode=remove; fi
  else
    runtime_mode=keep
    echo "Терминал недоступен: runtime и модели оставлены без изменений."
  fi
fi

if [[ "$runtime_mode" == remove ]]; then
  if ! command -v gio >/dev/null 2>&1; then
    echo "gio не найден; runtime оставлен без изменений." >&2
    exit 1
  fi
  for item in .venv .runtime models; do
    if [[ -e "$repo_dir/$item" ]]; then
      gio trash "$repo_dir/$item"
      echo "Перемещено в Корзину: $item"
    fi
  done
else
  echo "Локальные зависимости и модели оставлены."
fi

echo "Исходники и config.local.env сохранены. Системные пакеты не удалялись."
