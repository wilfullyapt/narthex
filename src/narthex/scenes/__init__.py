from __future__ import annotations

from narthex.widgets import Scene, Widget


def home_scene() -> Scene:
    """Default magic-mirror ambient face with Hermes gold node."""
    return Scene(
        id="home",
        chrome={"cursor": False, "voice_layer": "overlay"},
        display={"preferred": "on"},
        widgets=[
            Widget(
                id="clock_main",
                type="clock",
                x=250,
                y=36,
                w=500,
                h=140,
                z=10,
                props={"format": "HH:mm", "seconds": False},
            ),
            Widget(
                id="date_line",
                type="text",
                x=250,
                y=170,
                w=500,
                h=40,
                z=11,
                props={"content": "", "role": "date", "align": "center", "size": "md"},
            ),
            Widget(
                id="gold_node",
                type="gold_node",
                x=460,
                y=820,
                w=80,
                h=80,
                z=20,
                props={"mode": "idle"},
                effect="gold_pulse",
            ),
            Widget(
                id="voice_stage",
                type="voice_stage",
                x=80,
                y=520,
                w=840,
                h=260,
                z=500,
                props={
                    "state": "idle",
                    "user_text": "",
                    "assistant_text": "",
                    "partial": "",
                    "visible": False,
                },
            ),
        ],
        on_expiry="home",
    )


SCENES = {
    "home": home_scene,
}


def get_scene(scene_id: str) -> Scene:
    factory = SCENES.get(scene_id, home_scene)
    return factory()
