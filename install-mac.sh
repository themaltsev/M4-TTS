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
bin_dir="$app_dir/bin"
launch_agent="$HOME/Library/LaunchAgents/com.themaltsev.selected-text-speech.plist"
label="com.themaltsev.selected-text-speech"

brew list --formula mpv >/dev/null 2>&1 || brew install mpv
python_bin="$(command -v python3 || true)"
if [[ -z "$python_bin" ]]; then
  brew install python
  python_bin="$(brew --prefix python)/bin/python3"
fi
mkdir -p "$app_dir/state" "$config_dir" "$app_dir/resources" "$bin_dir" "$HOME/Library/LaunchAgents"
if [[ ! -x "$venv/bin/python" ]]; then
  "$python_bin" -m venv "$venv"
fi
"$venv/bin/python" -m pip install -r "$repo_dir/requirements-piper.txt" -r "$repo_dir/requirements-edge.txt" rumps pynput
install -m 0644 "$repo_dir/macos/speech.py" "$app_dir/speech.py"
install -m 0644 "$repo_dir/settings_gui.py" "$app_dir/settings_gui.py"
install -m 0644 "$repo_dir/resources/m4-tts.png" "$app_dir/resources/m4-tts.png"
"$venv/bin/python" "$repo_dir/scripts/download_voice.py" "$app_dir/models"

if [[ ! -e "$config_dir/config.env" ]]; then
  cp "$repo_dir/config.env" "$config_dir/config.env"
  printf '\nHOTKEY=cmd+esc\n' >> "$config_dir/config.env"
else
  if ! grep -Eq '^[[:space:]]*TTS_ENGINE[[:space:]]*=' "$config_dir/config.env"; then
    cat >> "$config_dir/config.env" <<'EOF'

# Выбор синтеза: piper — локально, edge — онлайн через интернет.
# Переключение: поменяй TTS_ENGINE и сохрани конфиг.
TTS_ENGINE=piper
PIPER_MODEL=models/ru_RU-irina-medium.onnx
EOF
  fi
  if ! grep -Eq '^[[:space:]]*HOTKEY[[:space:]]*=' "$config_dir/config.env"; then
    printf '\nHOTKEY=cmd+esc\n' >> "$config_dir/config.env"
  fi
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

echo "Автозапуск по умолчанию выключен; управляется чекбоксом в Настройках приложения."
echo "Запуск значка вручную: selected-text-speech-tray"
nohup "$venv/bin/python" "$app_dir/speech.py" tray >> "$app_dir/state/tray.stdout.log" 2>> "$app_dir/state/tray.stderr.log" </dev/null &
echo "Значок приложения запущен в строке меню."

echo "Установка завершена. Хоткей: смотри $config_dir/config.env (по умолчанию cmd+esc)."
echo "Команды размещены внутри приложения: $bin_dir (PATH и ~/.local/bin не меняются)."
echo "Для хоткея выделения разреши Accessibility/Input Monitoring для Python в System Settings → Privacy & Security."
