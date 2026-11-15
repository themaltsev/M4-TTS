#!/usr/bin/python3
import os
import signal
import time
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("AyatanaAppIndicator3", "0.1")
from gi.repository import GLib, Gtk, AyatanaAppIndicator3

started_at = float(os.environ.get("TTS_STARTED_MONOTONIC", time.monotonic()))

icon = "/home/user/.local/share/icons/openclaw-tts-waveform.svg"
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


def update_elapsed():
    global last_seconds
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


update_elapsed()
GLib.timeout_add(250, update_elapsed)

signal.signal(signal.SIGTERM, lambda *_: Gtk.main_quit())
signal.signal(signal.SIGINT, lambda *_: Gtk.main_quit())
Gtk.main()
