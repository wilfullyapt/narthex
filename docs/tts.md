# Local / open-source TTS options for Narthex

Narthex speaks through a pluggable TTS backend (`audio.tts.engine`). Default for
desk dev is `"null"` (no audio). On the Pi, prefer fully local engines.

## Recommended

| Engine | License / notes | Pi 5 fit | Wire-up |
|--------|-----------------|----------|---------|
| **[Piper](https://github.com/rhasspy/piper)** | MIT | **Best default** — fast ONNX, many voices | `audio.tts.engine: piper` + install `piper` binary + `.onnx` voice; already in `narthex.tts.PiperTts` |
| **[Kokoro](https://github.com/hexgrad/kokoro)** / style-tts family | varies | Good quality, heavier | future backend |
| **eSpeak-NG** | GPL | Tiny CPU, robotic | fallback only |
| **Festival** | MIT-ish | Old, weak quality | avoid |
| **Coqui XTTS / TTS** | MPL / CPML | Heavy; GPU happier | optional later |
| **OpenAI / Edge cloud TTS** | proprietary | Easy but not sovereign | **not** default for Narthex |

## Piper install (device)

```bash
# binary + voice example (paths vary by arch)
pip install piper-tts   # or download release binary
# voices: https://github.com/rhasspy/piper/blob/master/VOICES.md
# e.g. en_US-lessac-medium.onnx + .json
```

Config:

```yaml
audio:
  tts:
    engine: piper
    voice: en_US-lessac-medium
```

Playback uses `aplay` / `paplay` / `ffplay` if present.

## Hermes Tool Gateway TTS

Hub Hermes can also synthesize via Tool Gateway and stream audio back — useful as
a **fallback** when the Pi has no voice model, but LAN-local Piper keeps the
doorway offline-capable.

## Decision

**v1 on Pi: Piper.** Null on CI. Cloud TTS only if Wil explicitly opts in.
