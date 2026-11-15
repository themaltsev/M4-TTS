from __future__ import annotations

import subprocess
import sys
import time

from .config import Config


def main() -> int:
    config = Config.load()
    sound = config.sound_path(config.tick_sound)
    if not sound.is_file():
        print(f"Tick sound is missing: {sound}", file=sys.stderr)
        return 1
    command = ["canberra-gtk-play", f"--file={sound}", f"--volume={config.tick_volume_db}"]
    while True:
        try:
            time.sleep(1)
            subprocess.run(command, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except KeyboardInterrupt:
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
