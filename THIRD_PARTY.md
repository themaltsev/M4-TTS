# Third-party speech components

- **Piper engine**: `piper-tts==1.8.0`, GPL-3.0-or-later. Installed into the ignored `.venv/` directory by `install.sh`; not vendored into this repository. Source: https://github.com/OHF-Voice/piper1-gpl
- **Default Russian voice**: `ru_RU-irina-medium`, MIT-licensed voice model. The model and sidecar metadata are downloaded into ignored `models/` by `install.sh`, verified by SHA-256, and are not committed. Source: https://huggingface.co/rhasspy/piper-voices/tree/main/ru/ru_RU/irina/medium
- **Optional online engine**: `edge-tts` can be selected via `TTS_ENGINE=edge`; its output is sent to Microsoft Edge TTS. Piper is the default and works offline after setup.
