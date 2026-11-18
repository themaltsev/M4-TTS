#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
model_name="ru_RU-irina-medium"
model_dir="$repo_dir/models"
model_path="$model_dir/$model_name.onnx"
model_json="$model_path.json"
model_sha256="8ff38212d23da300bbe3705c645e6e5b9475f0bfde01558eb17813e22acaaaaa"
model_base_url="https://huggingface.co/rhasspy/piper-voices/resolve/main/ru/ru_RU/irina/medium"

if [[ "$(id -u)" -eq 0 ]]; then
  echo "Запусти ./install.sh от своего пользователя из графического сеанса, не через sudo." >&2
  exit 1
fi
if [[ ! -f /etc/os-release ]] || ! . /etc/os-release || [[ "${ID:-}" != ubuntu ]]; then
  echo "Этот установщик рассчитан на Ubuntu с GNOME." >&2
  exit 1
fi
if ! command -v gsettings >/dev/null || ! gsettings get org.gnome.settings-daemon.plugins.media-keys custom-keybindings >/dev/null 2>&1; then
  echo "Не вижу активный сеанс GNOME. Запусти ./install.sh из Терминала на рабочем столе Ubuntu." >&2
  exit 1
fi
if ! command -v sudo >/dev/null; then
  echo "Нужен sudo для установки системных пакетов." >&2
  exit 1
fi

sudo apt-get update
sudo apt-get install -y --no-remove --no-upgrade \
  gir1.2-ayatanaappindicator3-0.1 \
  gir1.2-gtk-3.0 \
  gnome-session-canberra \
  libnotify-bin \
  libcanberra-gtk3-module \
  mpv \
  curl \
  python3-venv \
  python3-gi \
  wl-clipboard \
  xclip \
  yaru-theme-sound

# Keep Python dependencies, voice model, user config and runtime state in this checkout.
mkdir -p "$repo_dir/.runtime" "$model_dir"
if [[ ! -x "$repo_dir/.venv/bin/python" ]]; then
  python3 -m venv "$repo_dir/.venv"
fi
"$repo_dir/.venv/bin/python" -m pip install -r "$repo_dir/requirements-piper.txt"

model_valid=false
if [[ -f "$model_path" ]]; then
  actual_sha="$(sha256sum "$model_path" | cut -d ' ' -f 1)"
  [[ "$actual_sha" == "$model_sha256" ]] && model_valid=true
fi
if [[ "$model_valid" != true ]]; then
  model_tmp="$(mktemp "$model_dir/.$model_name.XXXXXX")"
  trap 'rm -f "$model_tmp"' EXIT
  curl --fail --location --retry 3 --output "$model_tmp" "$model_base_url/$model_name.onnx"
  actual_sha="$(sha256sum "$model_tmp" | cut -d ' ' -f 1)"
  if [[ "$actual_sha" != "$model_sha256" ]]; then
    echo "Хеш Piper-модели не совпал; скачанный файл оставлен вне установки." >&2
    exit 1
  fi
  mv "$model_tmp" "$model_path"
  trap - EXIT
  curl --fail --location --retry 3 --output "$model_json" "$model_base_url/$model_name.onnx.json"
fi

# Reuse the current GNOME binding but make it launch source directly from this checkout.
custom_schema="org.gnome.settings-daemon.plugins.media-keys.custom-keybinding"
key_list="$(gsettings get org.gnome.settings-daemon.plugins.media-keys custom-keybindings)"
key_candidates="$(python3 - "$key_list" <<'PY'
import ast
import sys
raw = sys.argv[1]
if raw.startswith("@as"):
    raw = raw[3:].strip()
for path in ast.literal_eval(raw):
    print(path)
PY
)"
key_path=""
while IFS= read -r candidate; do
  [[ -n "$candidate" ]] || continue
  candidate_command="$(gsettings get "$custom_schema:$candidate" command 2>/dev/null | python3 -c 'import ast,sys; print(ast.literal_eval(sys.stdin.read()))' 2>/dev/null || true)"
  if [[ "$candidate_command" == *"speak-selection"* ]]; then
    key_path="$candidate"
    break
  fi
done <<< "$key_candidates"

if [[ -z "$key_path" ]]; then
  key_path="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/selected-text-speech/"
  new_key_list="$(python3 - "$key_list" "$key_path" <<'PY'
import ast
import sys
raw, new_path = sys.argv[1:]
if raw.startswith("@as"):
    raw = raw[3:].strip()
paths = ast.literal_eval(raw)
if new_path not in paths:
    paths.append(new_path)
print("[" + ", ".join(repr(path) for path in paths) + "]")
PY
)"
  gsettings set org.gnome.settings-daemon.plugins.media-keys custom-keybindings "$new_key_list"
fi

if [[ "$key_path" != /* ]]; then
  echo "Не удалось определить путь GNOME-сочетания клавиш." >&2
  exit 1
fi
key_schema="$custom_schema:$key_path"
gsettings set "$key_schema" name "'Selected text speech'"
gsettings set "$key_schema" command "'$repo_dir/linux-gnome/bin/speak-selection'"
gsettings set "$key_schema" binding "'<Super>Escape'"

indicator_extension="ubuntu-appindicators@ubuntu.com"
if [[ -d "/usr/share/gnome-shell/extensions/$indicator_extension" ]] && command -v gnome-extensions >/dev/null; then
  if ! gnome-extensions enable "$indicator_extension"; then
    echo "Предупреждение: не удалось включить AppIndicator extension; проверь GNOME Extensions." >&2
  fi
fi

echo
echo "Установка завершена. Хоткей запускает исходники прямо из: $repo_dir"
echo "Горячая клавиша: Super (⌘ на клавиатуре Mac) + Escape"
echo "Piper, модель, конфиг и журнал находятся внутри проекта; после установки озвучивание работает офлайн."
