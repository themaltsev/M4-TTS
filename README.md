# Озвучивание выделенного текста для Ubuntu GNOME

Проект целиком запускается из этого checkout на MacBook с Ubuntu: выдели текст и нажми **Super (⌘ на клавиатуре Mac) + Escape**. GNOME вызывает `linux-gnome/bin/speak-selection` напрямую из репозитория. Код, Piper, модель, локальные настройки и журнал не копируются в `~/.local/bin` или `~/.local/lib`.

По умолчанию используется **локальный Piper** с русским голосом Irina. После первоначальной установки синтез работает офлайн. Модель и виртуальное окружение находятся в игнорируемых Git каталогах `models/` и `.venv/`, а потому не попадают в GitHub; установщик скачивает модель с проверкой SHA-256. Локальные пользовательские настройки хранятся в игнорируемом `config.local.env`; `config.env` — версионный шаблон.

## Установка

Запусти команды в Терминале внутри графического сеанса Ubuntu:

```bash
cd /home/user/ozvuchka-videlenogo-teksta
./install.sh
```

Установщик ставит системные аудио- и GNOME-зависимости через `sudo apt`, подготавливает `.venv`, получает Piper-модель в `models/` и назначает хоткей напрямую на скрипт в checkout. Запускай `install.sh` обычным пользователем, **не** через `sudo`.

## Команды

Запускай из корня репозитория:

```bash
./linux-gnome/bin/speak "текст для озвучивания"
cat article.txt | ./linux-gnome/bin/speak
./linux-gnome/bin/speak-selection   # toggle: озвучить выделение / остановить
./linux-gnome/bin/stop-speech
./linux-gnome/bin/speak-status
```

## Настройка

Редактируй `config.local.env` в корне проекта (он не попадёт в Git). Поддерживаются:

- `TTS_ENGINE=piper` — локальный голос по умолчанию; `TTS_ENGINE=edge` — прежний онлайн-движок.
- `PIPER_MODEL` — путь к ONNX-модели относительно корня проекта или абсолютный.
- `PIPER_LENGTH_SCALE` — скорость Piper; если не задана, рассчитывается из `MPV_PLAYBACK_SPEED` с сохранением высоты голоса.
- `MPV_PLAYBACK_VOLUME`, `CUE_VOLUME`, `TICK_VOLUME_DB` — громкость речи и сигналов.
- `START_SOUND`, `CANCEL_SOUND`, `TICK_SOUND` — файлы сигналов из каталога проекта `linux-gnome/share/sounds/`.
- Параметры `EDGE_TTS_*` применяются, только если явно выбран `TTS_ENGINE=edge`.

Чтобы включить Edge TTS, создай `.venv-edge` и установи `requirements-edge.txt`:

```bash
python3 -m venv .venv-edge
.venv-edge/bin/python -m pip install -r requirements-edge.txt
```

Журнал, PID-файл и временные маркеры находятся в `.runtime/`; эта директория игнорируется Git.

## Структура

- `linux-gnome/bin/` — команды, запускаемые непосредственно из checkout.
- `linux-gnome/src/selected_text_speech/` — логика приложения и потоковая озвучка Piper/Edge.
- `linux-gnome/share/sounds/` — звуковые сигналы.
- `install.sh` — системные зависимости, локальное окружение и привязка GNOME.
- `requirements-piper.txt` — фиксированная версия Piper.
- `requirements-edge.txt` — необязательный Edge TTS.
- `THIRD_PARTY.md` — лицензии движка и голосовой модели.
