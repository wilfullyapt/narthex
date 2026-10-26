# Live audio (OWW + VAD + Whisper)

## What “WAV without hardware” meant

A **desk fixture path**: feed a recorded `.wav` (or synthetic PCM) through the same
wake → VAD → STT functions the mic uses, so CI/dev can test the stack without a
USB mic. That is **not** a substitute for live capture — it only proves the
pipeline math. Live mode opens a real input device.

## Live stack

```
mic (sounddevice|pyaudio)
  → openWakeWord (wake)
  → Silero VAD or energy VAD (endpoint)
  → faster-whisper (STT)
  → Doorway → Portunus → Piper TTS (optional)
```

## Install

```bash
pip install -e ".[audio]"
# models download on first use into $data_dir/models
```

## Run

```bash
# Live listen until Ctrl-C (mock Portunus if hub down)
narthex listen --mock-hermes
narthex listen --speak          # real Piper if installed
narthexd -c config.yaml --live-audio
```

Config:

```yaml
wake:
  phrase: hey hermes
  model_path: null   # set to custom hey_hermes.tflite when you have one
  threshold: 0.5
audio:
  live: true
  device_index: null
  stt:
    engine: faster-whisper
    model_size: base   # tiny|base|small…
    device: cpu
  tts:
    engine: piper      # or "null"
```

## hey Hermes model note

Stock openWakeWord bundles often **lack** a true `hey_hermes` phrase. Until a
custom tflite is trained/placed at `wake.model_path`, the stack may fall back to
a bundled stand-in (e.g. `hey_jarvis`) for bring-up — **replace before family use**.

## Device API

- `POST /device/v1/wake` — chrome only  
- `POST /device/v1/turn` — inject transcript (simulate)  
- Live loop is process-local (`narthex listen` / `narthexd --live-audio`)
