from __future__ import annotations

"""Optional OpenWakeWord / Silero / faster-whisper backends.

Importing this module does not require heavy deps — loaders raise clear errors.
"""


from pathlib import Path
from typing import Any


def try_openwakeword(models_dir: str | Path, hotword: str = "hey_hermes", threshold: float = 0.5) -> Any:
    """Return a WakeBackend using openWakeWord, or raise ImportError/RuntimeError."""
    import numpy as np
    import openwakeword
    from openwakeword.model import Model
    from openwakeword.utils import download_models

    models_dir = Path(models_dir)
    models_dir.mkdir(parents=True, exist_ok=True)

    # Map phrase-ish names to OWW model keys when possible
    key = hotword.replace(" ", "_").lower()
    tflite = list(models_dir.glob(f"*{key}*.tflite"))
    if not tflite and key in getattr(openwakeword, "MODELS", {}):
        download_models(model_names=[key], target_directory=str(models_dir))
        tflite = list(models_dir.glob(f"*{key}*.tflite"))
    if not tflite:
        # fallback: any model in dir
        tflite = list(models_dir.glob("*.tflite"))
    if not tflite:
        raise RuntimeError(
            f"No openWakeWord model for {hotword!r} in {models_dir}. "
            "Install openwakeword and place/download a hey_hermes (or custom) tflite."
        )
    model = Model(wakeword_models=[str(tflite[0])])

    class OWWWake:
        def predict(self, pcm_int16: Any) -> bool:
            audio = np.asarray(pcm_int16, dtype=np.int16)
            model.predict(audio)
            return any(
                model.prediction_buffer[mdl][-1] > threshold for mdl in model.prediction_buffer
            )

        def reset(self) -> None:
            model.reset()

    return OWWWake()


def try_silero_vad(models_dir: str | Path) -> Any:
    import numpy as np
    import torch

    models_dir = Path(models_dir)
    models_dir.mkdir(parents=True, exist_ok=True)
    # Prefer torch.hub silero
    model, utils = torch.hub.load(
        repo_or_dir="snakers4/silero-vad",
        model="silero_vad",
        force_reload=False,
        onnx=False,
        trust_repo=True,
    )
    get_speech_timestamps = utils[0]

    class SileroVad:
        def __init__(self) -> None:
            self._buf: list[Any] = []

        def is_speech(self, pcm_float32: Any) -> bool:
            audio = np.asarray(pcm_float32, dtype=np.float32)
            if audio.ndim > 1:
                audio = audio.reshape(-1)
            # Frame-level: use model probability if available
            try:
                tensor = torch.from_numpy(audio)
                if tensor.dim() == 1:
                    tensor = tensor.unsqueeze(0)
                with torch.no_grad():
                    prob = model(tensor, 16000).item()
                return float(prob) > 0.5
            except Exception:  # noqa: BLE001
                ts = get_speech_timestamps(audio, model, sampling_rate=16000)
                return bool(ts)

        def reset(self) -> None:
            self._buf.clear()

    return SileroVad()


def try_faster_whisper(model_size: str = "base", device: str = "cpu") -> Any:
    import numpy as np
    from faster_whisper import WhisperModel

    model = WhisperModel(model_size, device=device, compute_type="int8")

    class FasterWhisperStt:
        def transcribe(self, pcm_int16: Any, sample_rate: int = 16000) -> str:
            audio = np.asarray(pcm_int16, dtype=np.float32) / 32768.0
            segments, _info = model.transcribe(audio, language="en", vad_filter=True)
            return " ".join(s.text.strip() for s in segments).strip()

    return FasterWhisperStt()
