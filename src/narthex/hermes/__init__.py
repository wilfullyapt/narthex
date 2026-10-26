from __future__ import annotations

from typing import Any

import httpx

from narthex.config import HermesConfig


class HermesClient:
    """OpenAI-compatible client aimed at Hermes API server (Portunus)."""

    def __init__(self, cfg: HermesConfig, session_id: str = "narthex-default"):
        self.cfg = cfg
        self.session_id = session_id

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.cfg.api_key:
            h["Authorization"] = f"Bearer {self.cfg.api_key}"
        if self.cfg.session_header:
            h[self.cfg.session_header] = self.session_id
        return h

    def chat(self, user_text: str, *, system: str | None = None) -> dict[str, Any]:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user_text})
        url = self.cfg.base_url.rstrip("/") + "/chat/completions"
        with httpx.Client(timeout=self.cfg.timeout_s) as client:
            r = client.post(
                url,
                headers=self._headers(),
                json={"model": self.cfg.model, "messages": messages},
            )
            r.raise_for_status()
            return r.json()

    def ping(self) -> dict[str, Any]:
        try:
            data = self.chat("ping", system="Reply with the single word pong.")
            return {"ok": True, "data": data}
        except Exception as e:  # noqa: BLE001 — network/API errors become payload
            return {"ok": False, "error": str(e)}
