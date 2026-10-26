# Phase status

## Done in v0.3.0

- [x] Everything in v0.2.0 (OTA, dual-bind, WS, audio state machine)
- [x] **Doorway turn loop** — transcript → Portunus → voice_stage → optional TTS
- [x] **Simulate path** — `narthex say --mock`, `POST /device/v1/turn`, `POST /device/v1/wake`
- [x] Display backends: noop / dpms / cec / auto (graceful degrade)
- [x] TTS: null + piper CLI when present
- [x] **Hub client** `narthex.hub_client.NarthexClient` for Portunus tools

## Still later (no Pi install required to keep coding)

- [ ] Live mic runner (OWW + Silero + faster-whisper) — needs HW or mocked PCM fixtures
- [ ] Piper model pack + ALSA device selection
- [ ] Production OTA channel hosting
- [ ] Portunus profile creation + skill wrapping hub_client
- [ ] VoxMetrica badge

## Headless dev loop

```bash
pip install -e ".[dev]"
narthex say "good morning" --mock
narthexd -c config.example.yaml --dry-run
# run API only and curl turn:
# narthexd -c config.example.yaml --api-only
```
