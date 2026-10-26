# Device API (Portunus → Narthex)

LAN HTTP API served by `narthexd` (default `:7841`).  
Auth: `Authorization: Bearer <NARTHEX_DEVICE_TOKEN>`.

All successful bodies are JSON. Errors: `{ "ok": false, "error": "..." }` with suitable HTTP status.

## Endpoints (v0 contract)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/v1/status` | version, scene, display, audio, ota job |
| GET | `/v1/config` | redacted config snapshot |
| PATCH | `/v1/config` | JSON-merge patch (honors `protected_keys`) |
| GET | `/v1/scene` | current scene graph |
| PUT | `/v1/scene` | replace current scene |
| POST | `/v1/scene/push` | ephemeral scene `{ scene, ttl_s }` |
| GET | `/v1/widgets` | list widgets in current scene |
| PUT | `/v1/widgets/{id}` | upsert widget |
| PATCH | `/v1/widgets/{id}` | move/resize/props (`x,y,w,h,z,props,effect`) |
| DELETE | `/v1/widgets/{id}` | remove widget |
| POST | `/v1/display` | `{ "state": "on"\|"off"\|"dim", "level"?: 0-100 }` |
| POST | `/v1/ota/check` | check channel for update |
| POST | `/v1/ota/apply` | `{ "version": "..." }` start apply job |
| GET | `/v1/ota/status` | job state |
| POST | `/v1/notify` | glass toast `{ "text", "ttl_s"? }` |
| POST | `/v1/speak` | optional local TTS `{ "text" }` |

## Hermes tools (hub)

Portunus should expose thin tools mapping 1:1 (names indicative):

- `narthex_status`, `narthex_config_get`, `narthex_config_patch`
- `narthex_scene_set`, `narthex_scene_push`
- `narthex_widget_upsert`, `narthex_widget_move`, `narthex_widget_remove`
- `narthex_display`, `narthex_ota_check`, `narthex_ota_apply`, `narthex_notify`

Implementation options later: Hermes plugin, skill+httpx, or MCP wrapper. **Contract lives here** regardless of wrapper.

## Security

- Firewall: only hub (or WG) to `api_port`
- Token rotation via ops; protected key `server.device_token` not patchable to empty via API
- No arbitrary command execution endpoint
