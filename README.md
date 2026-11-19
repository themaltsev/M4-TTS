# M4-TTS — озвучивание выделенного текста для Linux, Windows и macOS

Одна логика приложения для трёх платформ: выдели текст и нажми настроенное сочетание клавиш. Поведение одинаковое по сути — выбранный движок озвучивает выделение, повторное нажатие останавливает речь, а при пустом выделении показывается системное уведомление. Хоткеи, чтение clipboard, tray и уведомления подключены нативно для каждой ОС.

## Установка

Готовые версии и загрузки: [GitHub Releases](https://github.com/themaltsev/M4-TTS/releases/latest).

| Платформа | Установщик |
|---|---|
| Ubuntu GNOME | `./install-linux.sh` |
| Windows 10/11 x64 | `install-windows.exe` |
| macOS | `./install-mac.sh` |

На Linux запускай установщик из графического сеанса и от обычного пользователя. macOS требует Homebrew; Windows-инсталлятор включает приложение и Piper-voice runtime. Выбор движка хранится в пользовательском конфиге платформы.

Установщики не включают приложение в автозапуск. После установки запусти его из меню «Пуск» (Windows), командой `selected-text-speech-tray` (macOS) или меню приложений GNOME (Ubuntu), чтобы появился значок. В меню значка открой **Настройки…**. Чекбокс «Запускать вместе с системой» включает и выключает автозапуск; на Linux в меню приложений также создаётся отдельный ярлык настроек.

Windows удаляется через «Параметры → Приложения → Установленные приложения» или через ярлык «Удалить M4-TTS» в меню «Пуск». В каталоге установки также есть `uninstall-windows.cmd`.

## Движок и конфигурация

На всех платформах используются одинаковые значения:

```ini
TTS_ENGINE=piper
# либо
TTS_ENGINE=edge
```

- `piper` — локальный синтез русским голосом Irina. После первоначальной установки работает без интернета.
- `edge` — Edge TTS, требует интернет и отправляет текст в сервис Microsoft.

Остальные основные ключи тоже общие: `PIPER_MODEL`, `PIPER_LENGTH_SCALE`, `PIPER_VOLUME`, `EDGE_TTS_VOICE`, `EDGE_TTS_RATE`, `EDGE_TTS_VOLUME`, `EDGE_TTS_PITCH`, `MPV_PLAYBACK_SPEED`, `MPV_PLAYBACK_VOLUME` и `HOTKEY`. Примеры и значения по умолчанию находятся в `config.env`.

Расположение пользовательского конфига:

- Linux checkout: `config.local.env` в корне проекта (не коммитится).
- macOS: `~/Library/Application Support/selected-text-speech/config.env`.
- Windows: `%APPDATA%\selected-text-speech\config.env`.

## Поведение платформ

- **Linux/GNOME:** `Super+Escape` по умолчанию; выбор выделения через Wayland clipboard или X11 clipboard; пустое выделение сообщает через `notify-send`.
- **macOS:** `cmd+esc`; menu-bar приложение и системное уведомление Notification Center; для чтения выделения нужны разрешения Accessibility/Input Monitoring.
- **Windows:** `alt+esc` (Alt+Escape); tray-приложение, clipboard возвращается после чтения; уведомление показывается через системный tray notification.

Глобальный хоткей и системные API имеют платформенные реализации, но движок, параметры голоса, остановка и сценарий пустого выделения одинаковы.

Окно настроек позволяет выбрать `piper`/`edge`, изменить хоткей и скорость речи. Новое сочетание на macOS/Windows начинает действовать после перезапуска значка приложения; на GNOME сочетание обновляется сразу.

## Команды Linux

Из корня checkout:

```bash
./linux-gnome/bin/speak "текст для озвучивания"
cat article.txt | ./linux-gnome/bin/speak
./linux-gnome/bin/speak-selection   # озвучить выделение / повторно нажать для остановки
./linux-gnome/bin/stop-speech
./linux-gnome/bin/speak-status
```

На Linux хоткей запускает приложение прямо из `linux-gnome/bin/speak-selection` в текущем checkout. Python-окружение, модель, настройки, журналы и временное состояние располагаются внутри checkout в игнорируемых Git каталогах.

Чтобы отключить Linux-установку, запусти `./uninstall-linux.sh`. Скрипт удалит только хоткей этого checkout и спросит, перемещать ли `.venv`, `.runtime` и `models` в Корзину. Исходники, `config.local.env` и системные пакеты сохраняются.

## Структура проекта

- `linux-gnome/` — команды, GTK/tray indicator, clipboard и потоковая выдача аудио в Linux.
- `macos/speech.py` — menu-bar runtime, глобальный хоткей и Notification Center.
- `windows/speech.py` — Windows tray runtime и системные уведомления.
- `install-linux.sh`, `install-mac.sh`, `uninstall-linux.sh`, `windows/installer.iss`, `windows/uninstall-windows.cmd` — platform installers and cleanup.
- `requirements-piper.txt`, `requirements-edge.txt` — фиксируемые зависимости движков.
- `scripts/download_voice.py` — загрузка голоса с проверкой SHA-256.
- `THIRD_PARTY.md` — лицензии Piper и модели голоса.
