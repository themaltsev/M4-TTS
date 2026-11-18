#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != Darwin ]]; then
  echo "Этот установщик рассчитан на macOS." >&2
  exit 1
fi
if ! command -v brew >/dev/null 2>&1; then
  echo "Сначала установи Homebrew: https://brew.sh/" >&2
  exit 1
fi

repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
app_dir="$HOME/Library/Application Support/selected-text-speech"
config_dir="$HOME/Library/Application Support/selected-text-speech"
venv="$app_dir/venv"
bin_dir="$HOME/.local/bin"
launch_agent="$HOME/Library/LaunchAgents/com.themaltsev.selected-text-speech.plist"
label="com.themaltsev.selected-text-speech"

brew list --formula mpv >/dev/null 2>&1 || brew install mpv
python_bin="$(command -v python3 || true)"
if [[ -z "$python_bin" ]]; then
  brew install python
  python_bin="$(brew --prefix python)/bin/python3"
fi
mkdir -p "$app_dir/state" "$config_dir" "$bin_dir" "$HOME/Library/LaunchAgents"
if [[ ! -x "$venv/bin/python" ]]; then
  "$python_bin" -m venv "$venv"
fi
"$venv/bin/python" -m pip install --upgrade edge-tts rumps pynput
install -m 0644 "$repo_dir/macos/speech.py" "$app_dir/speech.py"

if [[ ! -e "$config_dir/config.env" ]]; then
  cat > "$config_dir/config.env" <<'EOF'
EDGE_TTS_VOICE=ru-RU-SvetlanaNeural
EDGE_TTS_RATE=+0%
EDGE_TTS_VOLUME=+0%
EDGE_TTS_PITCH=+0Hz
EDGE_TTS_CONNECT_TIMEOUT=10
EDGE_TTS_RECEIVE_TIMEOUT=60
MPV_PLAYBACK_SPEED=1.35
MPV_PLAYBACK_VOLUME=100
API_MAX_ATTEMPTS=3
API_RETRY_BASE_SECONDS=1.5
API_RETRY_MAX_SECONDS=8
HOTKEY=cmd+esc
EOF
elif ! grep -Eq '^[[:space:]]*HOTKEY[[:space:]]*=' "$config_dir/config.env"; then
  printf '\nHOTKEY=cmd+esc\n' >> "$config_dir/config.env"
fi

for command_name in speak speak-selection stop-speech speak-status selected-text-speech-tray; do
  case "$command_name" in
    speak) mode=speak ;;
    speak-selection) mode=selection ;;
    stop-speech) mode=stop ;;
    speak-status) mode=status ;;
    selected-text-speech-tray) mode=tray ;;
  esac
  cat > "$bin_dir/$command_name" <<EOF
#!/usr/bin/env bash
exec "$venv/bin/python" "$app_dir/speech.py" "$mode" "\$@"
EOF
  chmod 0755 "$bin_dir/$command_name"
done

mpv_dir="$(dirname "$(command -v mpv)")"
"$venv/bin/python" - "$launch_agent" "$venv/bin/python" "$app_dir/speech.py" "$app_dir/state/tray.stdout.log" "$app_dir/state/tray.stderr.log" "$mpv_dir:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin" "$label" <<'PY'
import plistlib
import sys
from pathlib import Path

plist_path, python, script, stdout_path, stderr_path, path, label = sys.argv[1:]
data = {
    "Label": label,
    "ProgramArguments": [python, script, "tray"],
    "RunAtLoad": True,
    "ProcessType": "Interactive",
    "EnvironmentVariables": {"PATH": path},
    "StandardOutPath": stdout_path,
    "StandardErrorPath": stderr_path,
}
target = Path(plist_path)
target.parent.mkdir(parents=True, exist_ok=True)
target.write_bytes(plistlib.dumps(data))
PY

launchctl bootout "gui/$(id -u)" "$launch_agent" >/dev/null 2>&1 || true
autostart_answer=n
if [[ -r /dev/tty ]]; then
  read -r -p "Добавить приложение в автозапуск macOS при входе? [y/n] " autostart_answer </dev/tty || autostart_answer=n
else
  echo "Терминал недоступен: автозапуск не включён."
fi
if [[ "$autostart_answer" =~ ^[YyДд]$ ]]; then
  launchctl bootstrap "gui/$(id -u)" "$launch_agent"
  launchctl kickstart -k "gui/$(id -u)/$label"
  echo "Автозапуск включён."
else
  rm -f "$launch_agent"
  echo "Автозапуск не включён. Чтобы запустить значок вручную: selected-text-speech-tray"
fi

echo "Установка завершена. Хоткей: смотри $config_dir/config.env (по умолчанию cmd+esc)."
echo "Команды установлены в $bin_dir; добавь этот каталог в PATH, если он ещё не добавлен."
echo "Для хоткея выделения разреши Accessibility/Input Monitoring для Python в System Settings → Privacy & Security."
