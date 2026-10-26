from __future__ import annotations

"""Audio doorway pipeline.

AMI ``listener.py`` (vad_quest) lessons — keep the good, drop the rest:

What AMI got right
- OpenWakeWord for on-device hotword
- Silero VAD to bound the utterance after wake
- 16 kHz mono int16 chunks (~80 ms @ 1280 samples)
- Explicit state enum (IDLE / WAITING_HOTWORD / LISTENING)

What we do better in Narthex
- **Local STT** (faster-whisper), never Google cloud as the control path
- **Continuous loop**: after one turn, return to WAITING — AMI set ``running=False``
  after capture and required an external restart
- **Single mic owner**: one capture lifecycle; AMI ``capture_audio`` called
  ``capture_speech`` without required args (broken path)
- **Event bus**, not a grab-bag callback: wake / stt / audio state / error
- **No last-minute ring buffer** of raw PCM (RAM + privacy); only post-wake capture
- **Pluggable backends** so unit tests run without mic/models (``Null*``)
- Display cold-listen is orthogonal: audio stays armed while panel sleeps

State machine::

    IDLE/WAITING_WAKE --wake--> LISTENING --vad end--> STT --text--> WAITING_WAKE
"""


import threading
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Protocol

from narthex.bus import Bus


class AudioState(Enum):
    IDLE = auto()
    WAITING_WAKE = auto()
    LISTENING = auto()
    STT = auto()
    ERROR = auto()


@dataclass
class Utterance:
    text: str
    duration_s: float | None = None
    backend: str = "unknown"


class WakeBackend(Protocol):
    def predict(self, pcm_int16: Any) -> bool: ...

    def reset(self) -> None: ...


class SttBackend(Protocol):
    def transcribe(self, pcm_int16: Any, sample_rate: int = 16000) -> str: ...


class VadBackend(Protocol):
    def is_speech(self, pcm_float32: Any) -> bool: ...

    def reset(self) -> None: ...


class NullWake:
    def predict(self, pcm_int16: Any) -> bool:
        return False

    def reset(self) -> None:
        return None


class NullVad:
    def is_speech(self, pcm_float32: Any) -> bool:
        return False

    def reset(self) -> None:
        return None


class NullStt:
    def transcribe(self, pcm_int16: Any, sample_rate: int = 16000) -> str:
        return ""


@dataclass
class AudioPipeline:
    """Orchestrates wake → VAD capture → STT. Mic I/O injected by device runner."""

    bus: Bus
    wake: WakeBackend = field(default_factory=NullWake)
    vad: VadBackend = field(default_factory=NullVad)
    stt: SttBackend = field(default_factory=NullStt)
    sample_rate: int = 16000
    chunk: int = 1280
    silence_end_s: float = 1.2
    listen_timeout_s: float = 12.0
    state: AudioState = AudioState.IDLE
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def set_state(self, state: AudioState, **extra: Any) -> None:
        with self._lock:
            self.state = state
        self.bus.publish("audio", {"state": state.name, **extra})

    def arm(self) -> None:
        """Enter continuous cold-listen / wait-wake."""
        self.wake.reset()
        self.set_state(AudioState.WAITING_WAKE)

    def on_wake_detected(self) -> None:
        self.wake.reset()
        self.vad.reset()
        self.set_state(AudioState.LISTENING)
        self.bus.publish("wake", {"phrase": "hey hermes"})

    def finish_utterance(self, pcm_chunks: list[Any]) -> Utterance:
        self.set_state(AudioState.STT)
        if not pcm_chunks:
            self.set_state(AudioState.WAITING_WAKE)
            self.bus.publish("stt", {"text": "", "empty": True})
            return Utterance(text="", backend=type(self.stt).__name__)
        import numpy as np

        audio = np.concatenate(pcm_chunks)
        text = (self.stt.transcribe(audio, sample_rate=self.sample_rate) or "").strip()
        utt = Utterance(
            text=text,
            duration_s=float(len(audio)) / float(self.sample_rate),
            backend=type(self.stt).__name__,
        )
        self.bus.publish("stt", {"text": text, "duration_s": utt.duration_s})
        self.set_state(AudioState.WAITING_WAKE)
        return utt

    def process_wake_chunk(self, pcm_int16: Any) -> bool:
        """Return True if wake fired. Safe no-op unless WAITING_WAKE/IDLE."""
        if self.state == AudioState.IDLE:
            self.set_state(AudioState.WAITING_WAKE)
        if self.state != AudioState.WAITING_WAKE:
            return False
        hit = bool(self.wake.predict(pcm_int16))
        if hit:
            self.on_wake_detected()
        return hit


def build_pipeline(bus: Bus, cfg: Any | None = None) -> AudioPipeline:
    """Factory — real OWW/Silero/Whisper attach when extras installed (device)."""
    return AudioPipeline(bus=bus)
