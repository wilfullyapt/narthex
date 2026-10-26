from __future__ import annotations

"""Mic / simulate runners. Live path: capture → OWW → VAD → faster-whisper → Doorway."""


import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from narthex.audio import AudioPipeline, AudioState, build_pipeline
from narthex.audio.backends import build_audio_stack
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
        self.pipeline.set_state(AudioState.STT)
        self.doorway.runtime.bus.publish("stt", {"text": text, "simulated": True})
        return self.doorway.handle_user_text(text, speak=speak)


class LiveMicRunner:
    """Continuous live capture: mic → OWW → VAD → faster-whisper → Doorway.

    Install: ``pip install -e '.[audio]'``
    Capture: sounddevice preferred, else PyAudio.
    """

    def __init__(
        self,
        doorway: Doorway,
        *,
        models_dir: str | Path | None = None,
        device_index: int | None = None,
        speak: bool = True,
        on_text: Callable[[str], None] | None = None,
        pipeline: AudioPipeline | None = None,
    ):
        self.doorway = doorway
        cfg = doorway.runtime.cfg
        data = Path(cfg.data_dir)
        self.models_dir = Path(models_dir) if models_dir else data / "models"
        self.device_index = device_index
        self.speak = speak
        self.on_text = on_text
        self.sample_rate = 16000
        self.chunk = 1280
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.last_error: str | None = None
        self.mode = "live"
        self.stack_notes: list[str] = []

        if pipeline is not None:
            self.pipeline = pipeline
            self.mode = "injected"
            self.stack_notes = ["pipeline=provided"]
        else:
            stack = build_audio_stack(
                models_dir=self.models_dir,
                wake_phrase=cfg.wake.phrase,
                wake_model_path=getattr(cfg.wake, "model_path", None),
                stt_model_size=cfg.audio.stt.model_size,
                stt_device=cfg.audio.stt.device,
            )
            self.stack_notes = list(stack.get("notes") or [])
            self.pipeline = AudioPipeline(
                bus=doorway.runtime.bus,
                wake=stack["wake"],
                vad=stack["vad"],
                stt=stack["stt"],
                sample_rate=self.sample_rate,
                chunk=self.chunk,
                silence_end_s=float(getattr(cfg.audio, "silence_end_s", 1.2) or 1.2),
                listen_timeout_s=float(getattr(cfg.audio, "listen_timeout_s", 12.0) or 12.0),
            )
        self.pipeline.arm()

    def inject_utterance(self, text: str, *, speak: bool | None = None) -> dict[str, Any]:
        sp = self.speak if speak is None else speak
        result = SimulateRunner(self.doorway, self.pipeline).utter(text, speak=sp)
        if self.on_text:
            self.on_text(text)
        return result

    def start(self) -> None:
        if self.mode == "injected":
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="narthex-live-mic", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)

    def status(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "running": bool(self._thread and self._thread.is_alive()),
            "audio_state": self.pipeline.state.name,
            "notes": self.stack_notes,
            "last_error": self.last_error,
            "models_dir": str(self.models_dir),
        }

    def _open_stream(self):
        try:
            import numpy as np
            import sounddevice as sd

            q: list[Any] = []

            def callback(indata, frames, time_info, status):
                q.append(indata.copy())

            stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="int16",
                blocksize=self.chunk,
                device=self.device_index,
                callback=callback,
            )
            stream.start()

            def read():
                while not q and not self._stop.is_set():
                    time.sleep(0.005)
                if not q:
                    return np.zeros(self.chunk, dtype=np.int16)
                block = q.pop(0).reshape(-1)
                if block.size < self.chunk:
                    block = np.pad(block, (0, self.chunk - block.size))
                return block[: self.chunk].astype(np.int16)

            def close():
                stream.stop()
                stream.close()

            return read, close, "sounddevice"
        except Exception:  # noqa: BLE001, S110
            pass

        import numpy as np
        import pyaudio

        pa = pyaudio.PyAudio()
        kwargs = {
            "format": pyaudio.paInt16,
            "channels": 1,
            "rate": self.sample_rate,
            "input": True,
            "frames_per_buffer": self.chunk,
        }
        if self.device_index is not None:
            kwargs["input_device_index"] = self.device_index
        stream = pa.open(**kwargs)

        def read():
            raw = stream.read(self.chunk, exception_on_overflow=False)
            return np.frombuffer(raw, dtype=np.int16)

        def close():
            stream.stop_stream()
            stream.close()
            pa.terminate()

        return read, close, "pyaudio"

    def _loop(self) -> None:
        try:
            read, close, backend = self._open_stream()
            self.stack_notes.append(f"capture={backend}")
            self.doorway.runtime.bus.publish(
                "audio", {"state": "live_start", "notes": self.stack_notes}
            )
        except Exception as e:  # noqa: BLE001
            self.last_error = f"mic_open_failed: {e}"
            self.doorway.runtime.bus.publish("audio", {"state": "error", "error": self.last_error})
            return

        try:
            while not self._stop.is_set():
                if self.pipeline.state in (AudioState.IDLE, AudioState.WAITING_WAKE):
                    pcm = read()
                    if self.pipeline.process_wake_chunk(pcm):
                        self.doorway.handle_wake()
                        self._capture_utterance(read)
                    continue
                self.pipeline.arm()
                time.sleep(0.01)
        except Exception as e:  # noqa: BLE001
            self.last_error = str(e)
            self.pipeline.set_state(AudioState.ERROR, error=str(e))
            self.doorway.runtime.bus.publish("audio", {"state": "error", "error": str(e)})
        finally:
            try:
                close()
            except Exception:  # noqa: BLE001, S110
                pass
            self.pipeline.arm()

    def _capture_utterance(self, read) -> None:
        import numpy as np

        chunks: list[Any] = []
        silence_s = 0.0
        heard_speech = False
        start = time.time()
        chunk_s = self.chunk / float(self.sample_rate)
        vad = self.pipeline.vad

        while not self._stop.is_set():
            pcm = read()
            chunks.append(pcm)
            audio_f = pcm.astype(np.float32) / 32768.0
            speech = bool(vad.is_speech(audio_f))
            if speech:
                heard_speech = True
                silence_s = 0.0
            elif heard_speech:
                silence_s += chunk_s
            if heard_speech and silence_s >= self.pipeline.silence_end_s:
                break
            if time.time() - start > self.pipeline.listen_timeout_s:
                break

        utt = self.pipeline.finish_utterance(chunks)
        text = (utt.text or "").strip()
        if self.on_text:
            self.on_text(text)
        if text:
            self.doorway.handle_user_text(text, speak=self.speak)
        else:
            self.doorway.set_voice_stage(
                state="error",
                user_text="",
                assistant_text="I didn't catch that.",
                visible=True,
            )
            self.pipeline.arm()


MicRunner = LiveMicRunner
