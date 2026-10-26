# Scenes and widgets

## Stage

Normalized coordinate space from config `scene.stage` (default **1000×1000**).  
Renderer maps to panel pixels preserving aspect (letterbox if needed).

## Scene

```json
{
  "id": "home",
  "chrome": { "cursor": false, "voice_layer": "overlay" },
  "display": { "preferred": "on" },
  "widgets": [],
  "on_expiry": "home",
  "ttl_s": null
}
```

## Widget

```json
{
  "id": "clock_main",
  "type": "clock",
  "x": 250,
  "y": 40,
  "w": 500,
  "h": 140,
  "z": 10,
  "props": { "format": "HH:mm" },
  "effect": null,
  "ttl_s": null
}
```

### z bands

| Band | Range |
|------|-------|
| ambient | 0–99 |
| content | 100–499 |
| voice | 500–799 |
| system | 800–999 |

### Types (v0)

| type | props (initial) |
|------|-----------------|
| `clock` | format, seconds |
| `text` | content, align, size |
| `markdown` | content |
| `gold_node` | mode: idle\|listen\|degraded |
| `voice_stage` | state, user_text, assistant_text, partial |
| `weather` | line |
| `image` | src (local/allowlisted) |
| `progress` | value 0–1, label |
| `toast` | text |

### Effects

Optional string: `gold_pulse`, `veil`, `strike`, … — CSS class on the widget root.

## Default home (bundled)

See `src/narthex/scenes/home.py` — clock, gold_node, voice_stage (hidden until active).
