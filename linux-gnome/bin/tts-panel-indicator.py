#!/usr/bin/python3
import signal
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("AyatanaAppIndicator3", "0.1")
from gi.repository import Gtk, AyatanaAppIndicator3

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

signal.signal(signal.SIGTERM, lambda *_: Gtk.main_quit())
signal.signal(signal.SIGINT, lambda *_: Gtk.main_quit())
Gtk.main()
