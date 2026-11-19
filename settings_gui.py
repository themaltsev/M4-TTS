"""Small native settings window shared by the desktop launchers."""
from __future__ import annotations

import os
import platform
import subprocess
import sys
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

APP = "selected-text-speech"


def config_path() -> Path:
    system = platform.system()
    if system == "Windows":
        return Path(os.environ.get("APPDATA", Path.home())) / APP / "config.env"
    if system == "Darwin":
        return Path.home() / "Library/Application Support" / APP / "config.env"
    if system == "Linux":
        return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / APP / "config.env"
    return Path.home() / ".config" / APP / "config.env"


def current_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip("\"'")
    except FileNotFoundError:
        pass
    return values


def autostart_path() -> Path:
    if platform.system() == "Windows":
        return Path(os.environ.get("APPDATA", Path.home())) / "Microsoft/Windows/Start Menu/Programs/Startup/M4-TTS.lnk"
    if platform.system() == "Darwin":
        return Path.home() / "Library/LaunchAgents/com.themaltsev.selected-text-speech.plist"
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "autostart/selected-text-speech.desktop"


def enabled_at_startup() -> bool:
    return autostart_path().exists()


def set_autostart(enabled: bool) -> None:
    target = autostart_path()
    if not enabled:
        if platform.system() == "Darwin":
            subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}", str(target)], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        target.unlink(missing_ok=True)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    if platform.system() == "Linux":
        root = Path(__file__).resolve().parent
        tray = root / "linux-gnome/bin/speak-tray"
        target.write_text(f"[Desktop Entry]\nType=Application\nName=M4-TTS\nExec={tray}\nX-GNOME-Autostart-enabled=true\n", encoding="utf-8")
    elif platform.system() == "Darwin":
        import plistlib
        script = Path(__file__).resolve().parent / "speech.py"
        target.write_bytes(plistlib.dumps({"Label": "com.themaltsev.selected-text-speech", "ProgramArguments": [sys.executable, str(script), "tray"], "RunAtLoad": True, "ProcessType": "Interactive", "EnvironmentVariables": {"PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"}}))
        subprocess.run(["launchctl", "bootstrap", f"gui/{os.getuid()}", str(target)], check=False)
    else:
        command = "$w=New-Object -ComObject WScript.Shell; $s=$w.CreateShortcut($env:APPDATA + '\\Microsoft\\Windows\\Start Menu\\Programs\\Startup\\M4-TTS.lnk'); $s.TargetPath=$env:WINDIR + '\\System32\\wscript.exe'; $s.Arguments='\"' + $env:SELECTED_TEXT_SPEECH_VBS + '\" \"' + $env:SELECTED_TEXT_SPEECH_EXE + '\"'; $s.Save()"
        app_dir = Path(sys.executable).resolve().parent
        env = dict(os.environ, SELECTED_TEXT_SPEECH_EXE=str(app_dir / "selected-text-speech.exe"), SELECTED_TEXT_SPEECH_VBS=str(app_dir / "run-tray.vbs"))
        subprocess.run(["powershell.exe", "-NoProfile", "-Command", command], check=True, env=env)


def apply_linux_hotkey(shortcut: str) -> None:
    aliases = {"super": "Super", "meta": "Super", "ctrl": "Control", "control": "Control",
               "alt": "Alt", "shift": "Shift", "escape": "Escape", "esc": "Escape",
               "space": "space", "enter": "Return"}
    parts = [item.strip().lower() for item in shortcut.split("+") if item.strip()]
    if len(parts) < 2:
        raise ValueError("Хоткей должен содержать модификатор и клавишу")
    binding = "".join(f"<{aliases.get(part, part.title())}>" for part in parts[:-1]) + aliases.get(parts[-1], parts[-1].upper() if len(parts[-1]) == 1 else parts[-1].title())
    schema = "org.gnome.settings-daemon.plugins.media-keys.custom-keybinding"
    root_schema = "org.gnome.settings-daemon.plugins.media-keys"
    raw = subprocess.run(["gsettings", "get", root_schema, "custom-keybindings"], check=True, capture_output=True, text=True).stdout
    import ast
    paths = ast.literal_eval(raw.removeprefix("@as "))
    for item in paths:
        full = f"{schema}:{item}"
        command = subprocess.run(["gsettings", "get", full, "command"], capture_output=True, text=True).stdout
        if "speak-selection" in command:
            subprocess.run(["gsettings", "set", full, "binding", binding], check=True)
            return


def main() -> None:
    path = config_path()
    values = current_values(path)
    root = tk.Tk()
    root.title("Настройки — M4-TTS")
    root.resizable(False, False)
    frame = ttk.Frame(root, padding=18)
    frame.grid(sticky="nsew")
    ttk.Label(frame, text="Озвучивание выделенного текста", font=("TkDefaultFont", 14, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 14))

    engine = tk.StringVar(value=values.get("TTS_ENGINE", "piper"))
    hotkey = tk.StringVar(value=values.get("HOTKEY", "alt+esc" if platform.system() == "Windows" else "cmd+esc" if platform.system() == "Darwin" else "super+escape"))
    ttk.Label(frame, text="Движок").grid(row=1, column=0, sticky="w", padx=(0, 16), pady=5)
    ttk.Combobox(frame, textvariable=engine, values=("piper", "edge"), state="readonly", width=24).grid(row=1, column=1, sticky="ew", pady=5)
    ttk.Label(frame, text="Глобальный хоткей").grid(row=2, column=0, sticky="w", padx=(0, 16), pady=5)
    ttk.Entry(frame, textvariable=hotkey, width=27).grid(row=2, column=1, sticky="ew", pady=5)
    speed = tk.StringVar(value=values.get("MPV_PLAYBACK_SPEED", "1.35"))
    ttk.Label(frame, text="Скорость речи").grid(row=3, column=0, sticky="w", padx=(0, 16), pady=5)
    ttk.Entry(frame, textvariable=speed, width=27).grid(row=3, column=1, sticky="ew", pady=5)
    startup = tk.BooleanVar(value=enabled_at_startup())
    ttk.Checkbutton(frame, text="Запускать вместе с системой", variable=startup).grid(row=4, column=0, columnspan=2, sticky="w", pady=(12, 8))

    def save() -> None:
        if engine.get() not in {"piper", "edge"} or not hotkey.get().strip():
            messagebox.showerror("Проверь настройки", "Выбери движок и задай сочетание клавиш.", parent=root)
            return
        try:
            parsed_speed = float(speed.get())
            if not 0.25 <= parsed_speed <= 4:
                raise ValueError
        except ValueError:
            messagebox.showerror("Проверь настройки", "Скорость должна быть от 0.25 до 4.0.", parent=root)
            return
        values.update(TTS_ENGINE=engine.get(), HOTKEY=hotkey.get().strip(), MPV_PLAYBACK_SPEED=str(parsed_speed))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Настройки M4-TTS\n" + "".join(f"{k}={v}\n" for k, v in values.items()), encoding="utf-8")
        try:
            if platform.system() == "Linux":
                apply_linux_hotkey(hotkey.get().strip())
            set_autostart(startup.get())
        except Exception as error:
            messagebox.showerror("Не удалось сохранить автозапуск", str(error), parent=root)
            return
        messagebox.showinfo("Сохранено", "Настройки сохранены. Перезапусти приложение, чтобы применить новый хоткей.", parent=root)
        root.destroy()

    buttons = ttk.Frame(frame)
    buttons.grid(row=5, column=0, columnspan=2, sticky="e", pady=(14, 0))
    ttk.Button(buttons, text="Закрыть", command=root.destroy).pack(side="right", padx=(8, 0))
    ttk.Button(buttons, text="Сохранить", command=save).pack(side="right")
    root.mainloop()


if __name__ == "__main__":
    main()
