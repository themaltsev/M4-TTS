#!/usr/bin/env bash
set -euo pipefail

keep_config=0
if [[ "${1:-}" == "--keep-config" ]]; then keep_config=1; fi
label="com.themaltsev.selected-text-speech"
launch_agent="$HOME/Library/LaunchAgents/$label.plist"
app_dir="$HOME/Library/Application Support/selected-text-speech"
config_dir="$HOME/Library/Application Support/selected-text-speech"
bin_dir="$HOME/.local/bin"
trash_dir="$HOME/.Trash/selected-text-speech-$(date +%Y%m%d-%H%M%S)"

launchctl bootout "gui/$(id -u)" "$launch_agent" >/dev/null 2>&1 || true
if [[ -x "$app_dir/venv/bin/python" && -f "$app_dir/speech.py" ]]; then
  "$app_dir/venv/bin/python" "$app_dir/speech.py" stop >/dev/null 2>&1 || true
fi
mkdir -p "$trash_dir"
for command_name in speak speak-selection stop-speech speak-status; do
  if [[ -e "$bin_dir/$command_name" ]]; then mv "$bin_dir/$command_name" "$trash_dir/$command_name"; fi
done
if [[ -e "$launch_agent" ]]; then mv "$launch_agent" "$trash_dir/$(basename "$launch_agent")"; fi
if (( keep_config )); then
  config_backup="$(mktemp -d)"
  if [[ -f "$config_dir/config.env" ]]; then cp "$config_dir/config.env" "$config_backup/config.env"; fi
  if [[ -d "$app_dir" ]]; then mv "$app_dir" "$trash_dir/application-support"; fi
  mkdir -p "$config_dir"
  if [[ -f "$config_backup/config.env" ]]; then mv "$config_backup/config.env" "$config_dir/config.env"; fi
  rmdir "$config_backup"
else
  if [[ -d "$app_dir" ]]; then mv "$app_dir" "$trash_dir/application-support"; fi
fi
echo "Утилита перемещена в Корзину. Homebrew/mpv и Python не удалялись."
