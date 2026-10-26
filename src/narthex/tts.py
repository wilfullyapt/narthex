from __future__ import annotations

"""TTS backends — null (dev) and piper CLI when installed."""


import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Protocol


class TtsBackend(Protocol):
    def speak(self, text: str) -> dict[str, Any]: ...


class NullTts:
    def speak(self, text: str) -> dict[str, Any]:
        return {"ok": True, "backend": "null", "text": text, "spoken": False}


class PiperTts:
    """Invoke `piper` CLI if present; otherwise report unavailable."""

    def __init__(self, voice: str = "en_US-lessac-medium", model_path: str | None = None):
        self.voice = voice
        self.model_path = model_path

    def speak(self, text: str) -> dict[str, Any]:
        if not text.strip():
            return {"ok": True, "backend": "piper", "spoken": False, "note": "empty"}
        if not shutil.which("piper"):
            return {"ok": False, "backend": "piper", "spoken": False, "error": "piper not on PATH"}
        with tempfile.TemporaryDirectory(prefix="narthex-tts-") as tmp:
            wav = Path(tmp) / "out.wav"
            cmd = ["piper", "--output_file", str(wav)]
            if self.model_path:
                cmd.extend(["--model", self.model_path])
            try:
                p = subprocess.run(
                    cmd,
                    input=text,
                    text=True,
                    capture_output=True,
                    timeout=120,
                    check=False,
                )
                if p.returncode != 0:
                    return {
                        "ok": False,
                        "backend": "piper",
                        "spoken": False,
                        "error": (p.stderr or p.stdout or "piper failed").strip(),
                    }
                # playback
                player = None
                for cand in ("aplay", "paplay", "ffplay"):
                    if shutil.which(cand):
                        player = cand
                        break
                if player == "ffplay":
                    subprocess.run(
                        ["ffplay", "-nodisp", "-autoexit", str(wav)],
                        capture_output=True,
                        timeout=120,
                        check=False,
                    )
                elif player:
                    subprocess.run([player, str(wav)], capture_output=True, timeout=120, check=False)
                else:
                    return {
                        "ok": True,
                        "backend": "piper",
                        "spoken": False,
                        "wav": str(wav),
                        "note": "no aplay/paplay/ffplay",
                    }
                return {"ok": True, "backend": "piper", "spoken": True, "voice": self.voice}
            except Exception as e:  # noqa: BLE001
                return {"ok": False, "backend": "piper", "spoken": False, "error": str(e)}


def build_tts(engine: str | None = "null", voice: str = "en_US-lessac-medium") -> TtsBackend:
    eng = (engine or "null").lower()
    if eng in ("null", "none", "off", ""):
        return NullTts()
    if eng == "piper":
        return PiperTts(voice=voice)
    return NullTts()
