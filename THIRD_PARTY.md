# Third-party speech components

- **Piper engine**: `piper-tts==1.8.0`, GPL-3.0-or-later. Linux/macOS installers and the Windows build install it into an app-local Python environment; it is not vendored into this repository. Source: https://github.com/OHF-Voice/piper1-gpl
- **Default Russian voice**: `ru_RU-irina-medium`, MIT-licensed voice model. The installers download the model and sidecar metadata into the app's `models/` directory and verify SHA-256; model files are not committed. Source: https://huggingface.co/rhasspy/piper-voices/tree/main/ru/ru_RU/irina/medium
- **Online engine**: `edge-tts` can be selected via `TTS_ENGINE=edge`; it sends text to Microsoft Edge TTS and requires internet access. Piper is the default.
