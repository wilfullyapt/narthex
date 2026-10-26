from __future__ import annotations

"""OTA scaffold — signed check/apply/rollback in later phase."""

from typing import Any


class OtaManager:
    def __init__(self, require_signature: bool = True, channel: str = "stable"):
        self.require_signature = require_signature
        self.channel = channel
        self.job: dict[str, Any] = {"state": "idle"}

    def check(self) -> dict[str, Any]:
        self.job = {"state": "checked", "channel": self.channel, "update": None}
        return {"ok": True, "channel": self.channel, "update": None, "note": "no channel configured"}

    def apply(self, version: str) -> dict[str, Any]:
        if self.require_signature:
            # Refuse blind apply until signing path exists
            self.job = {"state": "refused", "version": version, "reason": "signature_path_pending"}
            return {
                "ok": False,
                "error": "OTA apply requires signed channel (phase 6); refused by design",
                "job": self.job,
            }
        self.job = {"state": "would_apply", "version": version}
        return {"ok": False, "error": "unsigned apply disabled in scaffold", "job": self.job}

    def status(self) -> dict[str, Any]:
        return {"ok": True, "job": self.job}
