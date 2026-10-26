from __future__ import annotations

import threading
from collections import defaultdict
from collections.abc import Callable
from typing import Any


class Bus:
    """Simple in-process pub/sub for daemon ↔ API ↔ UI."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subs: dict[str, list[Callable[[dict[str, Any]], None]]] = defaultdict(list)

    def subscribe(self, topic: str, fn: Callable[[dict[str, Any]], None]) -> None:
        with self._lock:
            self._subs[topic].append(fn)

    def publish(self, topic: str, payload: dict[str, Any] | None = None) -> None:
        data = dict(payload or {})
        data.setdefault("topic", topic)
        with self._lock:
            listeners = list(self._subs.get(topic, []))
            listeners += list(self._subs.get("*", []))
        for fn in listeners:
            try:
                fn(data)
            except Exception:  # noqa: BLE001, S110 — isolate subscriber faults
                pass
