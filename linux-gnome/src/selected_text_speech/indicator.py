from __future__ import annotations

import os
import signal
import time
from pathlib import Path
import subprocess
import sys

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("AyatanaAppIndicator3", "0.1")
from gi.repository import AyatanaAppIndicator3, GLib, Gtk


icons_dir = Path(__file__).resolve().parents[3] / "resources"
repo_dir = Path(__file__).resolve().parents[3]
waiting_icon = str(icons_dir / "m4-tts.svg")
waveform_icon = str(icons_dir / "m4-tts-playing.svg")
started_at = float(os.environ.get("SELECTED_TEXT_STARTED_MONOTONIC", time.monotonic()))
indicator = AyatanaAppIndicator3.Indicator.new(
    "m4-tts", waiting_icon, AyatanaAppIndicator3.IndicatorCategory.APPLICATION_STATUS
)
indicator.set_icon_full(waiting_icon, "Ожидание речи")
indicator.set_title("Подготовка озвучивания")
menu = Gtk.Menu()
status = Gtk.MenuItem(label="Подготовка озвучивания")
status.set_sensitive(False)
menu.append(status)
settings_item = Gtk.MenuItem(label="Настройки…")
settings_item.connect("activate", lambda *_: subprocess.Popen([sys.executable, str(repo_dir / "settings_gui.py")]))
menu.append(settings_item)
menu.show_all()
indicator.set_menu(menu)
indicator.set_status(AyatanaAppIndicator3.IndicatorStatus.ACTIVE)

last_seconds = -1
playback_started = False


def update_elapsed() -> bool:
    global last_seconds
    if playback_started:
        return GLib.SOURCE_REMOVE
    seconds = max(0, int(time.monotonic() - started_at))
    if seconds == last_seconds:
        return GLib.SOURCE_CONTINUE
    last_seconds = seconds
    indicator.set_label(f"{seconds}с", "888с")
    description = f"Подготовка озвучивания — {seconds} с"
    indicator.set_title(description)
    status.set_label(description)
    return GLib.SOURCE_CONTINUE


def switch_to_playing() -> bool:
    global playback_started
    if playback_started:
        return GLib.SOURCE_REMOVE
    playback_started = True
    indicator.set_icon_full(waveform_icon, "Идёт озвучивание текста")
    indicator.set_label("", "")
    indicator.set_title("Идёт озвучивание текста")
    status.set_label("Идёт озвучивание текста")
    return GLib.SOURCE_REMOVE


def on_playback_started(*_args: object) -> None:
    GLib.idle_add(switch_to_playing)


def main() -> int:
    signal.signal(signal.SIGUSR1, on_playback_started)
    signal.signal(signal.SIGTERM, lambda *_: Gtk.main_quit())
    signal.signal(signal.SIGINT, lambda *_: Gtk.main_quit())
    update_elapsed()
    GLib.timeout_add(250, update_elapsed)
    Gtk.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
