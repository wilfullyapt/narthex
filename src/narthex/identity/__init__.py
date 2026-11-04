"""Optional VoxMetrica client — local badge / claim; hub Portunus enforces caps."""

from __future__ import annotations

import logging
import tempfile
import wave
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class IdentityClient:
    """Thin adapter over voxmetrica.EdgeClient when installed and enabled."""

    def __init__(
        self,
        *,
        enabled: bool = False,
        voxmetrica_root: str | Path | None = None,
        ingress: str = "narthex",
        device_id: str | None = None,
        session_id: str = "default",
    ):
        self.enabled = bool(enabled)
        self.root = Path(voxmetrica_root).expanduser() if voxmetrica_root else None
        self.ingress = ingress
        self.device_id = device_id
        self.session_id = session_id
        self._client = None
        self.last_claim: dict[str, Any] | None = None
        if self.enabled:
            self._try_load()

    def _try_load(self) -> None:
        try:
            from voxmetrica import EdgeClient  # type: ignore

            self._client = EdgeClient(
                self.root if self.root else None,
                ingress=self.ingress,
            )
            logger.info("VoxMetrica EdgeClient ready (root=%s)", self.root or "default")
        except Exception as e:  # noqa: BLE001
            logger.warning("identity enabled but voxmetrica unavailable: %s", e)
            self._client = None
            self.enabled = False

    @property
    def available(self) -> bool:
        return bool(self.enabled and self._client is not None)

    def badge(self, claim: dict[str, Any] | None = None) -> str:
        claim = claim if claim is not None else self.last_claim
        if not self.available or not claim:
            return ""
        try:
            return str(self._client.badge(claim))
        except Exception:  # noqa: BLE001
            return ""

    def identify_file(self, audio_path: str | Path) -> dict[str, Any]:
        if not self.available:
            return {"ok": False, "error": "identity not available", "outcome": "unknown"}
        claim = self._client.identify(
            audio_path,
            session_id=self.session_id,
            device_id=self.device_id,
        )
        self.last_claim = claim
        return claim

    def identify_pcm_int16(
        self,
        pcm: Any,
        *,
        sample_rate: int = 16000,
    ) -> dict[str, Any]:
        """Write temp mono 16-bit wav and identify (EdgeClient expects a file path)."""
        if not self.available:
            return {"ok": False, "error": "identity not available", "outcome": "unknown"}
        import numpy as np

        audio = np.asarray(pcm, dtype=np.int16).reshape(-1)
        if audio.size < sample_rate // 2:
            return {
                "ok": True,
                "outcome": "unknown",
                "speaker_id": "guest",
                "reason": "clip too short",
            }
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            path = Path(tmp.name)
        try:
            with wave.open(str(path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(audio.tobytes())
            return self.identify_file(path)
        finally:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass

    def resolve_clarify(self, choice: str, *, adapt: bool = True) -> dict[str, Any]:
        if not self.available:
            return {"ok": False, "error": "identity not available"}
        out = self._client.resolve_clarify(self.session_id, choice, adapt=adapt)
        self.last_claim = out
        return out


def build_identity(cfg) -> IdentityClient:
    """Build from AppConfig.identity (+ node id as device)."""
    id_cfg = getattr(cfg, "identity", None)
    if id_cfg is None:
        return IdentityClient(enabled=False)
    node = getattr(cfg, "node", None)
    device_id = getattr(node, "id", None) if node else None
    return IdentityClient(
        enabled=bool(getattr(id_cfg, "enabled", False)),
        voxmetrica_root=getattr(id_cfg, "voxmetrica_root", None),
        ingress=str(getattr(id_cfg, "ingress", "narthex") or "narthex"),
        device_id=device_id,
        session_id=str(getattr(id_cfg, "session_id", None) or device_id or "narthex"),
    )
