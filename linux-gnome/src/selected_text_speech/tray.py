from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("AyatanaAppIndicator3", "0.1")
from gi.repository import AyatanaAppIndicator3, GLib, Gtk

from .config import Config
from .controller import stop_speech
from .runtime import worker_pid

ROOT = Path(__file__).resolve().parents[3]
IDLE_ICON = ROOT / "resources/m4-tts.svg"
PLAYING_ICON = ROOT / "resources/m4-tts-playing.svg"
indicator = AyatanaAppIndicator3.Indicator.new(
    "m4-tts", str(IDLE_ICON), AyatanaAppIndicator3.IndicatorCategory.APPLICATION_STATUS
)
indicator.set_status(AyatanaAppIndicator3.IndicatorStatus.ACTIVE)
menu = Gtk.Menu()
status = Gtk.MenuItem(label="Озвучивание: готово")
status.set_sensitive(False)
menu.append(status)
stop_item = Gtk.MenuItem(label="Остановить озвучивание")
stop_item.connect("activate", lambda *_: stop_speech())
menu.append(stop_item)
settings_item = Gtk.MenuItem(label="Настройки…")
settings_item.connect("activate", lambda *_: subprocess.Popen([sys.executable, str(ROOT / "settings_gui.py")]))
menu.append(settings_item)
menu.append(Gtk.SeparatorMenuItem())
quit_item = Gtk.MenuItem(label="Закрыть значок")
quit_item.connect("activate", lambda *_: Gtk.main_quit())
menu.append(quit_item)
menu.show_all()
indicator.set_menu(menu)


def update() -> bool:
    pid = worker_pid()
    stop_item.set_sensitive(pid is not None)
    active_icon = PLAYING_ICON if pid is not None else IDLE_ICON
    indicator.set_icon_full(str(active_icon), "M4-TTS — озвучивание" if pid is not None else "M4-TTS — готово")
    if pid is None:
        description = f"Готово • {Config.load().engine}"
    else:
        description = f"Озвучивание выполняется • PID {pid}"
    status.set_label(description)
    indicator.set_title(description)
    return GLib.SOURCE_CONTINUE


def main() -> int:
    signal.signal(signal.SIGTERM, lambda *_: Gtk.main_quit())
    signal.signal(signal.SIGINT, lambda *_: Gtk.main_quit())
    update()
    GLib.timeout_add_seconds(1, update)
    Gtk.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
