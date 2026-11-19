#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
model_dir="$repo_dir/models"
install_system_packages=1
if [[ "${1:-}" == "--skip-system-packages" ]]; then install_system_packages=0; fi

if [[ "$(id -u)" -eq 0 ]]; then
  echo "Запусти ./install-linux.sh от своего пользователя из графического сеанса, не через sudo." >&2
  exit 1
fi
if [[ ! -f /etc/os-release ]] || ! . /etc/os-release || [[ "${ID:-}" != ubuntu ]]; then
  echo "Этот установщик рассчитан на Ubuntu с GNOME." >&2
  exit 1
fi
if ! command -v gsettings >/dev/null || ! gsettings get org.gnome.settings-daemon.plugins.media-keys custom-keybindings >/dev/null 2>&1; then
  echo "Не вижу активный сеанс GNOME. Запусти ./install-linux.sh из Терминала на рабочем столе Ubuntu." >&2
  exit 1
fi
if ! command -v sudo >/dev/null; then
  echo "Нужен sudo для установки системных пакетов." >&2
  exit 1
fi

if (( install_system_packages )); then
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
    python3-tk \
    wl-clipboard \
    xclip \
    yaru-theme-sound
fi

# Keep Python dependencies, voice model, user config and runtime state in this checkout.
mkdir -p "$repo_dir/.runtime" "$model_dir"
chmod 0755 "$repo_dir/linux-gnome/bin/speak-tray"
if [[ ! -x "$repo_dir/.venv/bin/python" ]]; then
  python3 -m venv "$repo_dir/.venv"
fi
"$repo_dir/.venv/bin/python" -m pip install -r "$repo_dir/requirements-piper.txt" -r "$repo_dir/requirements-edge.txt"

"$repo_dir/.venv/bin/python" "$repo_dir/scripts/download_voice.py" "$model_dir"

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
gsettings set "$key_schema" name "'M4-TTS'"
gsettings set "$key_schema" command "'$repo_dir/linux-gnome/bin/speak-selection'"
gsettings set "$key_schema" binding "'<Super>Escape'"

indicator_extension="ubuntu-appindicators@ubuntu.com"
if [[ -d "/usr/share/gnome-shell/extensions/$indicator_extension" ]] && command -v gnome-extensions >/dev/null; then
  if ! gnome-extensions enable "$indicator_extension"; then
    echo "Предупреждение: не удалось включить AppIndicator extension; проверь GNOME Extensions." >&2
  fi
fi

applications_dir="$HOME/.local/share/applications"
mkdir -p "$applications_dir"
cat > "$applications_dir/selected-text-speech.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=M4-TTS
Comment=Озвучивание выделенного текста
Exec=$repo_dir/linux-gnome/bin/speak-tray
Icon=$repo_dir/resources/m4-tts.svg
Terminal=false
Categories=Utility;Accessibility;
EOF
cat > "$applications_dir/selected-text-speech-settings.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=M4-TTS — Настройки
Exec=/usr/bin/python3 $repo_dir/settings_gui.py
Icon=preferences-system
Terminal=false
Categories=Utility;Accessibility;
EOF

echo
echo "Установка завершена. Хоткей: Super (⌘ на клавиатуре Mac) + Escape."
echo "Автозапуск выключен; его можно переключить в Настройках приложения."
echo "Открой M4-TTS через меню приложений, чтобы появился значок в верхней панели."
echo "Движок выбирается через TTS_ENGINE=piper или TTS_ENGINE=edge в config.local.env."
echo "Код, модели, настройки и журнал остаются внутри checkout."
