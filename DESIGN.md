# Narthex — DESIGN

**Status:** v0.1 skeleton (2026-10-26)  
**License:** MIT  
**Hub profile:** `portunus`  
**Identity sibling:** [voxmetrica](https://github.com/wilfullyapt/voxmetrica) (separate — do not absorb)

## Thesis

Narthex is a **controllable room surface**: default face is a black glass **magic-mirror home** with a **Hermes gold node**; long arc is a **dialectic teacher** (lesson → elicit → check → expire) orchestrated by Portunus via tool calls — not a MagicMirror² fork and not a second Hermes brain on the Pi.

```
Family voice ──► narthex (cold-listen wake, STT on Pi)
                    │
                    ▼
              portunus (Hermes API server)
                    │ tools
                    ▼
              narthex device API
              (config, widgets, scenes, display, OTA)
```

## Locked decisions

| Topic | Choice |
|-------|--------|
| Wake | `hey Hermes` / openWakeWord-class |
| STT | On device (faster-whisper class) |
| Brain | Hub Hermes **API server** on profile **portunus** |
| Asleep | **Cold listen** — panel off, wake armed |
| Shell | Chromium kiosk + narthexd localhost UI |
| Style | Void black + **Hermes gold** `#C9A227` (see config.style) |
| Layout | Widgets: **absolute x,y,w,h + z-index** |
| Config | Local durable SoR; Portunus patches via API |
| OTA | Signed artifacts, rollback, tool-triggerable |
| VoxMetrica | Depend later; hub authoritative for caps |

## Process architecture

```
narthexd
  ├── config     load/validate/patch (protected keys)
  ├── bus        in-proc state events
  ├── audio      wake · VAD · STT · TTS   (device)
  ├── hermes     OpenAI-compatible client → portunus
  ├── identity   optional voxmetrica client (badge only)
  ├── display    DPMS/CEC/noop + cold-listen policy
  ├── scenes     scene graph + expiry
  ├── widgets    types + absolute geometry
  ├── ota        check / apply / rollback
  ├── api        device API :7841 (Portunus tools)
  └── ui         FastAPI :7840 localhost + WS → kiosk
```

## Style defaults

| Token | Hex | Use |
|-------|-----|-----|
| void | `#000000` | Stage background |
| text | `#F2EDE4` | Primary type |
| gold | `#C9A227` | Node, wake, focus |
| gold_dim | `#8A7019` | Idle heartbeat |
| mist | `#A8A29A` | Secondary labels |

**Gold node:** widget type `gold_node` — living link indicator (idle pulse / listen bright / link degraded dim).

## Scene + widget model

See [docs/scenes.md](./docs/scenes.md).

Runtime truth is a **scene** = list of widgets with absolute geometry on a normalized stage (default 1000×1000), scaled to the panel. Grid layouts are authoring sugar only.

z bands: ambient 0–99 · content 100–499 · voice 500–799 · system 800–999.

Default scene id: **`home`**.

## Device API

See [docs/device-api.md](./docs/device-api.md).

Portunus holds tools that HTTP-call the node (`NARTHEX_DEVICE_TOKEN`). Narthex does not rely on SSH/`terminal` as the control plane.

## OTA

See [docs/ota.md](./docs/ota.md). Signed Ed25519 channel; CLI `narthex ota pack|check|apply|rollback`.

## Audio

See [docs/audio.md](./docs/audio.md). AMI vad_quest listener lessons applied; local STT continuous loop.

## Phases

| Phase | Outcome |
|-------|---------|
| **0** | Skeleton + CI + public repo |
| **1 / 0.2** | Dual bind, WS, **working signed OTA**, audio state machine |
| **1.5 / 0.3** | Doorway turn loop, simulate say/turn, display backends, hub_client |
| **2** | Device mic: OWW + VAD + faster-whisper + Piper |
| **3** | DPMS/CEC + cold-listen policy on glass |
| **4** | Portunus tools + production channel |
| **5** | VoxMetrica |
| **6** | Dialectic scene packs |

## Non-goals

- MagicMirror² as runtime core  
- Full Hermes agent on the Pi  
- Cloud STT / cloud UI accounts  
- Absorbing VoxMetrica  
- Unsigned OTA  

## Estate notes (operators)

- Checkout path: `/root/seneschal/repos/narthex`  
- Hub profile id: `portunus`  
- Code owner: Hephaestus · Pi deploy later with Lamassu as needed  
