from __future__ import annotations

"""Mic / simulate runners. Device HW optional — simulate works headless."""


import threading
import time
from collections.abc import Callable
from typing import Any

from narthex.audio import AudioPipeline, AudioState, build_pipeline
from narthex.doorway import Doorway


class SimulateRunner:
    """Inject wake + transcript without a microphone (CI and desk dev)."""

    def __init__(self, doorway: Doorway, pipeline: AudioPipeline | None = None):
        self.doorway = doorway
        self.pipeline = pipeline or build_pipeline(doorway.runtime.bus)
        self.pipeline.arm()

    def wake(self) -> dict[str, Any]:
        self.pipeline.on_wake_detected()
        return self.doorway.handle_wake()

    def utter(self, text: str, *, speak: bool = False) -> dict[str, Any]:
        self.wake()
        # pretend STT finished
        self.pipeline.set_state(AudioState.STT)
        self.doorway.runtime.bus.publish("stt", {"text": text, "simulated": True})
        return self.doorway.handle_user_text(text, speak=speak)


class MicRunner:
    """Background loop placeholder for real capture.

    When audio extras + HW are present, swap null backends via
    ``narthex.audio.backends``. Until then, ``tick_simulate`` remains the path.
    """

    def __init__(
        self,
        doorway: Doorway,
        pipeline: AudioPipeline | None = None,
        on_text: Callable[[str], None] | None = None,
    ):
        self.doorway = doorway
        self.pipeline = pipeline or build_pipeline(doorway.runtime.bus)
        self.pipeline.arm()
        self.on_text = on_text
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self.mode = "simulate"  # or "live" when mic wired

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="narthex-mic", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _loop(self) -> None:
        # Live capture lands here (PyAudio + OWW). Idle sleep keeps thread cheap in simulate mode.
        while not self._stop.is_set():
            time.sleep(0.25)

    def inject_utterance(self, text: str, *, speak: bool = False) -> dict[str, Any]:
        sim = SimulateRunner(self.doorway, self.pipeline)
        result = sim.utter(text, speak=speak)
        if self.on_text:
            self.on_text(text)
        return result
