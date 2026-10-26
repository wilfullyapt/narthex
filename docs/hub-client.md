# Hub client (Portunus → Narthex)

Python helper used by hub tools/skills without SSHing the Pi.

```python
from narthex.hub_client import NarthexClient

n = NarthexClient("http://narthex.lan:7841", token="…")
n.status()
n.display("on")
n.turn("what's the weather", speak=False)  # desk simulate path
n.widget_move("clock_main", x=100, y=40)
n.ota_check()
```

## Suggested Hermes tool names

| Tool | Method |
|------|--------|
| `narthex_status` | `status` |
| `narthex_config_get` / `_patch` | `config_get` / `config_patch` |
| `narthex_scene_set` | `scene_set` |
| `narthex_widget_move` | `widget_move` |
| `narthex_display` | `display` |
| `narthex_ota_check` / `_apply` / `_rollback` | OTA |
| `narthex_notify` | `notify` |
| `narthex_turn` | `turn` (simulate / injected transcript) |

Wire these as a Portunus skill or plugin that reads `NARTHEX_BASE_URL` + `NARTHEX_DEVICE_TOKEN` from the hub profile env.
