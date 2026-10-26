from __future__ import annotations

"""HTTP helpers Portunus (or any hub agent) can call against a Narthex node.

This module is importable on the hub without the full edge stack extras.
"""


from typing import Any

import httpx


class NarthexClient:
    def __init__(self, base_url: str, token: str = "", timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        # accept either http://host:7841 or http://host:7841/device
        root = self.base_url
        if root.endswith("/device"):
            return root + path
        return root + "/device" + path

    def request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as client:
            r = client.request(method, self._url(path), headers=self._headers(), **kwargs)
            r.raise_for_status()
            return r.json()

    def status(self) -> dict[str, Any]:
        return self.request("GET", "/v1/status")

    def config_get(self) -> dict[str, Any]:
        return self.request("GET", "/v1/config")

    def config_patch(self, patch: dict[str, Any]) -> dict[str, Any]:
        return self.request("PATCH", "/v1/config", json={"patch": patch})

    def scene_get(self) -> dict[str, Any]:
        return self.request("GET", "/v1/scene")

    def scene_set(self, scene: dict[str, Any]) -> dict[str, Any]:
        return self.request("PUT", "/v1/scene", json={"scene": scene})

    def widget_move(self, widget_id: str, **fields: Any) -> dict[str, Any]:
        return self.request("PATCH", f"/v1/widgets/{widget_id}", json=fields)

    def display(self, state: str, level: int | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {"state": state}
        if level is not None:
            body["level"] = level
        return self.request("POST", "/v1/display", json=body)

    def ota_check(self) -> dict[str, Any]:
        return self.request("POST", "/v1/ota/check")

    def ota_apply(self, version: str, restart: bool = False) -> dict[str, Any]:
        return self.request("POST", "/v1/ota/apply", json={"version": version, "restart": restart})

    def ota_rollback(self) -> dict[str, Any]:
        return self.request("POST", "/v1/ota/rollback")

    def notify(self, text: str, ttl_s: float = 8) -> dict[str, Any]:
        return self.request("POST", "/v1/notify", json={"text": text, "ttl_s": ttl_s})

    def turn(self, text: str, speak: bool = False) -> dict[str, Any]:
        """Simulate a spoken user turn on the node (desk/dev without mic)."""
        return self.request("POST", "/v1/turn", json={"text": text, "speak": speak})

    def wake(self) -> dict[str, Any]:
        return self.request("POST", "/v1/wake")
