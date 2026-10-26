from __future__ import annotations

"""Display backends — DPMS/CEC wired on device; noop for dev."""


class Display:
    def __init__(self, backend: str = "noop"):
        self.backend = backend
        self.state = "on"

    def set_state(self, state: str, level: int | None = None) -> dict:
        if state not in ("on", "off", "dim"):
            raise ValueError(f"invalid display state: {state}")
        self.state = state
        # Real DPMS/CEC hooks land in phase 5
        return {"ok": True, "state": self.state, "level": level, "backend": self.backend}
