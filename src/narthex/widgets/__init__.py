from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Widget(BaseModel):
    id: str
    type: str
    x: float = 0
    y: float = 0
    w: float = 100
    h: float = 100
    z: int = 0
    props: dict[str, Any] = Field(default_factory=dict)
    effect: str | None = None
    ttl_s: float | None = None


class Scene(BaseModel):
    id: str
    chrome: dict[str, Any] = Field(default_factory=lambda: {"cursor": False, "voice_layer": "overlay"})
    display: dict[str, Any] = Field(default_factory=lambda: {"preferred": "on"})
    widgets: list[Widget] = Field(default_factory=list)
    on_expiry: str | None = "home"
    ttl_s: float | None = None

    def widget_map(self) -> dict[str, Widget]:
        return {w.id: w for w in self.widgets}

    def upsert_widget(self, widget: Widget) -> None:
        widgets = [w for w in self.widgets if w.id != widget.id]
        widgets.append(widget)
        widgets.sort(key=lambda w: w.z)
        self.widgets = widgets

    def remove_widget(self, widget_id: str) -> bool:
        before = len(self.widgets)
        self.widgets = [w for w in self.widgets if w.id != widget_id]
        return len(self.widgets) < before

    def move_widget(
        self,
        widget_id: str,
        *,
        x: float | None = None,
        y: float | None = None,
        w: float | None = None,
        h: float | None = None,
        z: int | None = None,
        props: dict[str, Any] | None = None,
        effect: str | None = None,
    ) -> Widget:
        found = self.widget_map().get(widget_id)
        if not found:
            raise KeyError(widget_id)
        data = found.model_dump()
        if x is not None:
            data["x"] = x
        if y is not None:
            data["y"] = y
        if w is not None:
            data["w"] = w
        if h is not None:
            data["h"] = h
        if z is not None:
            data["z"] = z
        if props is not None:
            data["props"] = {**(data.get("props") or {}), **props}
        if effect is not None:
            data["effect"] = effect
        updated = Widget.model_validate(data)
        self.upsert_widget(updated)
        return updated
