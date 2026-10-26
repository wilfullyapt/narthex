# Audio design (AMI lessons → Narthex)

Source reviewed: [`ArtificialModularIntelligence` `vad_quest` `ami/ai/listener.py`](https://github.com/wilfullyapt/ArtificialModularIntelligence/blob/vad_quest/ami/ai/listener.py).

## What AMI was doing

| Piece | AMI approach |
|-------|----------------|
| Wake | OpenWakeWord tflite, threshold from config |
| Capture | PyAudio 16 kHz mono, chunk 1280 |
| Endpointing | Silero VAD after hotword; ~2 s silence stop; timeout |
| STT | **Google** via `speech_recognition` (Sphinx commented) |
| Threading | One-shot thread; `running=False` after a single utterance |
| Buffer | Kept ~1 minute PCM before hotword |
| Bugs | `capture_audio()` called `capture_speech` without mic/args |

## Narthex direction

1. **Local STT** — faster-whisper on Pi 5 (sovereign control path; cloud never required).
2. **Continuous arm** — after STT, return to `WAITING_WAKE` (cold listen survives display sleep).
3. **Bus events** — `wake`, `audio`, `stt` for glass + Portunus client; no global EventType soup.
4. **Pluggable backends** — `Null*` in tests; `audio/backends.py` loaders for OWW / Silero / Whisper when `[audio]` extras installed.
5. **No pre-wake PCM ring** — privacy + RAM; only buffer after wake.
6. **Single pipeline owner** — mic stream lifecycle owned by a future `audio.runner` (phase 4 device wire), not mixed into HTTP.

## State machine

```
IDLE → WAITING_WAKE → (wake) → LISTENING → (vad silence) → STT → WAITING_WAKE
```

Display `ASLEEP` does not stop `WAITING_WAKE` when `wake.cold_listen_when_asleep: true`.

## Mapping AMI knobs

| AMI | Narthex |
|-----|---------|
| DETECTION_THRESHOLD | wake backend threshold |
| LISTENING_TIMEOUT | `AudioPipeline.listen_timeout_s` |
| silence 2.0 s | `silence_end_s` (default 1.2 — tune on room) |
| CHUNK 1280 | keep |
| Google STT | **drop** |

## Phase status

- Pipeline + null backends + tests: **done** (v0.2)
- Device mic thread + OWW hey_hermes model + whisper: **next on Pi**
