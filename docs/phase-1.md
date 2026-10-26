# Phase 1 — vertical slice

After skeleton (Phase 0):

## Goals

1. Installable package: `pip install -e .`
2. `narthex version` / `narthexd --dry-run` load config + home scene
3. Device API: `GET /v1/status`, `GET /v1/scene`, `GET|PATCH /v1/config` with bearer token
4. Hermes client: optional `narthex ping-hermes` against Portunus API (skip if unreachable)
5. UI: serve static home stage on `:7840` with WS scene push (even if audio is stub)

## Non-goals this phase

- Real openWakeWord / whisper / piper
- Signed OTA against production channel
- VoxMetrica
- Full Portunus tool plugin (document mapping only)

## Done when

- [ ] `pytest` green in CI
- [ ] Dry-run daemon prints loaded scene id `home`
- [ ] curl status with token returns version `0.1.0`
- [ ] Browser/kiosk can open UI and see black stage + gold node (static OK)
