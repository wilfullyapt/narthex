# Phase 1 — vertical slice (status)

## Done in v0.2.0

- [x] Installable package + CI
- [x] `narthex version` / `narthexd --dry-run`
- [x] Device API status/config/scene/widgets/display
- [x] Dual-bind daemon (UI `:7840` + API `:7841`)
- [x] WebSocket `/ws` + stage client
- [x] **Signed OTA** check/apply/rollback (Ed25519) + CLI pack/keygen
- [x] Audio pipeline design + state machine (AMI lessons) with null backends
- [x] Hermes client `ping-hermes` (optional)

## Remaining toward full doorway

- [ ] Real mic runner: openWakeWord + Silero + faster-whisper on device
- [ ] Piper TTS playback
- [ ] DPMS/CEC display backends
- [ ] Production OTA channel URL (GH Releases or Stronghold store)
- [ ] Portunus profile + tool wrappers
- [ ] VoxMetrica badge path

## Device bootstrap (existing Pi)

```bash
git clone https://github.com/wilfullyapt/narthex.git
cd narthex && python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
# optional: pip install -e ".[audio]"
cp config.example.yaml /etc/narthex/config.yaml
# set NARTHEX_DEVICE_TOKEN, NARTHEX_HERMES_API_KEY, ota.check_url, ota public key
narthexd -c /etc/narthex/config.yaml
```
