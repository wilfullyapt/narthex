from __future__ import annotations

"""Display backends: noop (dev), dpms (xset/wlr-randr), cec (cec-client).

All backends degrade gracefully when binaries or sessions are missing.
"""


import shutil
import subprocess
from typing import Any


def _run(cmd: list[str], timeout: float = 5.0) -> tuple[int, str]:
    try:
        p = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        out = (p.stdout or "") + (p.stderr or "")
        return p.returncode, out.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        return 127, str(e)


class DisplayBackend:
    name = "base"

    def apply(self, state: str, level: int | None = None) -> dict[str, Any]:
        raise NotImplementedError


class NoopBackend(DisplayBackend):
    name = "noop"

    def apply(self, state: str, level: int | None = None) -> dict[str, Any]:
        return {"ok": True, "backend": self.name, "applied": True, "note": "noop"}


class DpmsBackend(DisplayBackend):
    """X11 xset DPMS or wlr-randr power when available."""

    name = "dpms"

    def apply(self, state: str, level: int | None = None) -> dict[str, Any]:
        details: list[str] = []
        ok = False
        if shutil.which("xset"):
            if state == "off":
                code, out = _run(["xset", "dpms", "force", "off"])
            elif state == "dim":
                code, out = _run(["xset", "dpms", "force", "standby"])
            else:
                code, out = _run(["xset", "dpms", "force", "on"])
                _run(["xset", "s", "reset"])
            details.append(f"xset:{code}:{out}")
            ok = code == 0
        if shutil.which("wlr-randr"):
            # Best-effort: list outputs then on/off first output name is env-specific;
            # many kiosk images use a helper script instead. Record presence only.
            code, out = _run(["wlr-randr"])
            details.append(f"wlr-randr-present:{code == 0}")
            if not ok and code == 0 and state == "on":
                ok = True  # compositor alive; full off/on needs output name config later
        if not details:
            return {
                "ok": False,
                "backend": self.name,
                "applied": False,
                "error": "no xset/wlr-randr on PATH",
            }
        return {"ok": ok, "backend": self.name, "applied": ok, "details": details, "level": level}


class CecBackend(DisplayBackend):
    name = "cec"

    def apply(self, state: str, level: int | None = None) -> dict[str, Any]:
        if not shutil.which("cec-client"):
            return {
                "ok": False,
                "backend": self.name,
                "applied": False,
                "error": "cec-client not on PATH",
            }
        # cec-client interactive is awkward; echo one-shot commands when supported
        if state == "off":
            cmd = ["cec-client", "-s", "-d", "1"]
            payload = "standby 0"
        else:
            cmd = ["cec-client", "-s", "-d", "1"]
            payload = "on 0"
        try:
            p = subprocess.run(
                cmd,
                input=payload + "\n",
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            )
            return {
                "ok": p.returncode == 0,
                "backend": self.name,
                "applied": p.returncode == 0,
                "details": [(p.stdout or "") + (p.stderr or "")],
                "level": level,
            }
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "backend": self.name, "applied": False, "error": str(e)}


class ChainBackend(DisplayBackend):
    """Try backends in order; first success wins."""

    name = "chain"

    def __init__(self, backends: list[DisplayBackend]):
        self.backends = backends

    def apply(self, state: str, level: int | None = None) -> dict[str, Any]:
        results = []
        for b in self.backends:
            r = b.apply(state, level)
            results.append(r)
            if r.get("ok") and r.get("applied"):
                return {**r, "chain": results}
        return {
            "ok": False,
            "backend": self.name,
            "applied": False,
            "error": "all backends failed",
            "chain": results,
        }


def build_backend(name: str) -> DisplayBackend:
    key = (name or "noop").lower()
    if key == "noop":
        return NoopBackend()
    if key == "dpms":
        return DpmsBackend()
    if key == "cec":
        return CecBackend()
    if key in ("auto", "chain"):
        return ChainBackend([DpmsBackend(), CecBackend(), NoopBackend()])
    return NoopBackend()


class Display:
    def __init__(self, backend: str = "noop"):
        self.backend_name = backend
        self._backend = build_backend(backend)
        self.state = "on"

    def set_state(self, state: str, level: int | None = None) -> dict:
        if state not in ("on", "off", "dim"):
            raise ValueError(f"invalid display state: {state}")
        result = self._backend.apply(state, level)
        # Always update logical state so glass/API stay consistent even if HW fails
        self.state = state
        return {
            "ok": True,
            "state": self.state,
            "level": level,
            "backend": self.backend_name,
            "hw": result,
        }
