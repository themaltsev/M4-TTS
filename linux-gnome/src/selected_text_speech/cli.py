from __future__ import annotations

import argparse
import sys

from . import controller


def speak_main() -> int:
    parser = argparse.ArgumentParser(prog="speak", description="Озвучить переданный текст через Edge TTS")
    parser.add_argument("text", nargs="*", help="Текст; если аргументы не заданы, читает stdin")
    parser.add_argument("--stdin", action="store_true", help="явно читать текст из stdin")
    args = parser.parse_args()
    if args.stdin and args.text:
        parser.error("передай либо позиционный текст, либо --stdin")
    if args.text:
        text = " ".join(args.text)
    elif args.stdin or not sys.stdin.isatty():
        text = sys.stdin.read()
    else:
        parser.error("передай текст аргументом или через stdin")
    try:
        pid = controller.start_text(text)
    except (OSError, ValueError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(f"Озвучивание запущено (PID {pid})")
    return 0


def stop_main() -> int:
    stopped = controller.stop_speech()
    print("Озвучивание остановлено" if stopped else "Озвучивание не запущено")
    return 0


def selection_main() -> int:
    try:
        action = controller.toggle_selection()
    except (OSError, ValueError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        return 1
    if action == "started":
        print("Озвучивание выделения запущено")
    elif action == "stopped":
        print("Озвучивание остановлено")
    return 0 if action in ("started", "stopped", "empty") else 1


def status_main() -> int:
    pid = controller.status()
    if pid is None:
        print("Озвучивание не запущено")
        return 1
    print(f"Озвучивание запущено (PID {pid})")
    return 0
