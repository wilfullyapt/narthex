from __future__ import annotations

from typing import Any

from narthex import __version__
from narthex.bus import Bus
from narthex.config import ConfigStore
from narthex.scenes import get_scene
from narthex.widgets import Scene, Widget


class Runtime:
    """In-memory appliance runtime: config + active scene + bus."""

    def __init__(self, store: ConfigStore):
        self.store = store
        self.bus = Bus()
        self.scene: Scene = get_scene(store.cfg.scene.default)
        self.display_state: str = "on"
        self.audio_state: str = "idle"
        self.ota_job: dict[str, Any] = {"state": "idle"}

    @property
    def cfg(self):
        return self.store.cfg

    def status(self) -> dict[str, Any]:
        return {
            "ok": True,
            "version": __version__,
            "node": self.cfg.node.model_dump(),
            "scene_id": self.scene.id,
            "display": self.display_state,
            "audio": self.audio_state,
            "wake": {
                "phrase": self.cfg.wake.phrase,
                "cold_listen": self.cfg.wake.cold_listen_when_asleep,
            },
            "ota": self.ota_job,
        }

    def set_scene(self, scene: Scene) -> Scene:
        self.scene = scene
        self.bus.publish("scene", {"scene": scene.model_dump()})
        return scene

    def load_scene(self, scene_id: str) -> Scene:
        return self.set_scene(get_scene(scene_id))

    def upsert_widget(self, widget: Widget) -> Widget:
        self.scene.upsert_widget(widget)
        self.bus.publish("scene", {"scene": self.scene.model_dump()})
        return widget
