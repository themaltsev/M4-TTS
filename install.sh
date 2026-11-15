#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
user_bin="$HOME/.local/bin"
user_lib="$HOME/.local/lib"
user_data="$HOME/.local/share"
user_config="${XDG_CONFIG_HOME:-$HOME/.config}/selected-text-speech"

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
  pipx \
  python3-gi \
  wl-clipboard \
  xclip \
  yaru-theme-sound

mkdir -p "$user_bin" "$user_lib/selected_text_speech" "$user_data/icons" "$user_data/selected-text-speech/sounds" "$user_config"
for command_file in _bootstrap.py speak speak-selection speak-status stop-speech; do
  install -m 0755 "$repo_dir/linux-gnome/bin/$command_file" "$user_bin/$command_file"
done
for module_file in "$repo_dir"/linux-gnome/src/selected_text_speech/*.py; do
  install -m 0644 "$module_file" "$user_lib/selected_text_speech/$(basename "$module_file")"
done
install -m 0644 "$repo_dir/linux-gnome/share/icons/openclaw-tts-waveform.svg" "$user_data/icons/openclaw-tts-waveform.svg"
install -m 0644 "$repo_dir/linux-gnome/share/icons/openclaw-tts-waiting.svg" "$user_data/icons/openclaw-tts-waiting.svg"
install -m 0644 "$repo_dir/linux-gnome/share/sounds/openclaw-soft-tick.wav" "$user_data/selected-text-speech/sounds/openclaw-soft-tick.wav"
install -m 0644 "$repo_dir/linux-gnome/share/sounds/speech-start.oga" "$user_data/selected-text-speech/sounds/speech-start.oga"
install -m 0644 "$repo_dir/linux-gnome/share/sounds/speech-cancel.oga" "$user_data/selected-text-speech/sounds/speech-cancel.oga"
if [[ ! -e "$user_config/config.env" ]]; then
  install -m 0644 "$repo_dir/config.env" "$user_config/config.env"
fi

edge_python="$user_data/pipx/venvs/edge-tts/bin/python"
if [[ -x "$edge_python" ]]; then
  pipx upgrade edge-tts
else
  pipx install edge-tts
fi

# Preserve other GNOME custom shortcuts while adding/updating our own binding.
key_path="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/selected-text-speech/"
key_list="$(gsettings get org.gnome.settings-daemon.plugins.media-keys custom-keybindings)"
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
key_schema="org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:$key_path"
gsettings set "$key_schema" name "'Selected text speech'"
gsettings set "$key_schema" command "'$user_bin/speak-selection'"
gsettings set "$key_schema" binding "'<Super>Escape'"

indicator_extension="ubuntu-appindicators@ubuntu.com"
if [[ -d "/usr/share/gnome-shell/extensions/$indicator_extension" ]] && command -v gnome-extensions >/dev/null; then
  if ! gnome-extensions enable "$indicator_extension"; then
    echo "Предупреждение: не удалось включить AppIndicator extension; проверь GNOME Extensions." >&2
  fi
else
  echo "Предупреждение: системное расширение AppIndicator не найдено; значок в панели может не отображаться." >&2
fi

echo
echo "Установка завершена. Горячая клавиша: Super (⌘ на клавиатуре Mac) + Escape."
echo "Команды: speak 'текст' | speak-selection | stop-speech | speak-status"
echo "Проверь, что ~/.local/bin находится в PATH; после установки можно перелогиниться, если сочетание не сработало сразу."
