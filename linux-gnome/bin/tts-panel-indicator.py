#!/usr/bin/python3
import os
from pathlib import Path
import signal
import time
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("AyatanaAppIndicator3", "0.1")
from gi.repository import GLib, Gtk, AyatanaAppIndicator3

started_at = float(os.environ.get("TTS_STARTED_MONOTONIC", time.monotonic()))

icons_dir = Path.home() / ".local/share/icons"
icon = str(icons_dir / "openclaw-tts-waiting.svg")
waveform_icon = str(icons_dir / "openclaw-tts-waveform.svg")
indicator = AyatanaAppIndicator3.Indicator.new(
    "openclaw-tts", icon,
    AyatanaAppIndicator3.IndicatorCategory.APPLICATION_STATUS,
)
indicator.set_icon_full(icon, "Идёт озвучивание текста")
indicator.set_title("Идёт озвучивание текста")
menu = Gtk.Menu()
status = Gtk.MenuItem(label="Идёт озвучивание текста")
status.set_sensitive(False)
menu.append(status)
menu.show_all()
indicator.set_menu(menu)
indicator.set_status(AyatanaAppIndicator3.IndicatorStatus.ACTIVE)


last_seconds = -1
playback_started = False


def update_elapsed():
    global last_seconds
    if playback_started:
        return GLib.SOURCE_REMOVE
    seconds = max(0, int(time.monotonic() - started_at))
    if seconds == last_seconds:
        return GLib.SOURCE_CONTINUE
    last_seconds = seconds
    panel_label = f"{seconds}с"
    indicator.set_label(panel_label, "888с")
    description = f"Идёт озвучивание текста — {seconds} с"
    indicator.set_title(description)
    status.set_label(description)
    return GLib.SOURCE_CONTINUE


def switch_to_playing():
    global playback_started
    if playback_started:
        return GLib.SOURCE_REMOVE
    playback_started = True
    indicator.set_icon_full(waveform_icon, "Идёт озвучивание текста")
    indicator.set_label("", "")
    indicator.set_title("Идёт озвучивание текста")
    status.set_label("Идёт озвучивание текста")
    return GLib.SOURCE_REMOVE


def on_playback_started(*_):
    GLib.idle_add(switch_to_playing)


signal.signal(signal.SIGUSR1, on_playback_started)


update_elapsed()
GLib.timeout_add(250, update_elapsed)

signal.signal(signal.SIGTERM, lambda *_: Gtk.main_quit())
signal.signal(signal.SIGINT, lambda *_: Gtk.main_quit())
Gtk.main()
