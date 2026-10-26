# Narthex

**LAN voice doorway** for [Hermes Agent](https://hermes-agent.nousresearch.com/): a Magic Mirror–class Pi surface that cold-listens for **hey Hermes**, runs STT on-device, talks to a dedicated hub profile (**Portunus**), and renders a **golden-node** glass UI.

> Pre-alpha skeleton. Contracts first; full appliance path is incremental.

## Roles

| Name | Role |
|------|------|
| **narthex** (this repo) | Edge appliance: wake, STT, TTS, kiosk scene graph, local config, device API, OTA target |
| **portunus** | Hermes profile on the hub — mind + tools *into* narthex |
| **[voxmetrica](https://github.com/wilfullyapt/voxmetrica)** | Who / may — separate repo; narthex depends later |

## Design docs

- [DESIGN.md](./DESIGN.md) — architecture, scenes, device API, OTA, phases
- [docs/device-api.md](./docs/device-api.md) — Portunus-facing HTTP surface
- [docs/scenes.md](./docs/scenes.md) — widget + scene model
- [docs/phase-1.md](./docs/phase-1.md) — next vertical slice

## Quick start (dev smoke)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
narthex version
narthexd --config config.example.yaml --dry-run
```

Kiosk + real audio require a Pi (or Linux box with mic) — see DESIGN phases.

## License

MIT — see [LICENSE](./LICENSE).

## Security

- Never commit `config.yaml`, device tokens, or Hermes API keys.
- Device API is **authenticated** and intended **LAN-only** (firewall hub → node).
- OTA requires **signed** artifacts when `ota.require_signature: true` (default).
