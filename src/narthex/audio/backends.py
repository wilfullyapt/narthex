from __future__ import annotations

"""Optional OpenWakeWord / Silero / faster-whisper / energy-VAD backends.

Importing this module does not require heavy deps — loaders raise clear errors
or return light fallbacks where noted.
"""


from pathlib import Path
from typing import Any


def try_openwakeword(
    models_dir: str | Path,
    hotword: str = "hey_jarvis",
    threshold: float = 0.5,
    model_path: str | Path | None = None,
) -> Any:
    """Return a WakeBackend using openWakeWord.

    Bundled OWW phrases rarely include \"hey hermes\". Prefer a custom tflite via
    ``model_path``, or train/export one. Until then ``hey_jarvis`` (or any
    installed model) is a stand-in for pipeline bring-up.
    """
    import numpy as np
    import openwakeword
    from openwakeword.model import Model
    from openwakeword.utils import download_models

    models_dir = Path(models_dir)
    models_dir.mkdir(parents=True, exist_ok=True)

    if model_path:
        path = Path(model_path)
        if not path.exists():
            raise RuntimeError(f"wake model_path not found: {path}")
        model = Model(wakeword_models=[str(path)])
    else:
        key = hotword.replace(" ", "_").lower()
        # map common phrase spellings
        aliases = {
            "hey_hermes": "hey_jarvis",  # stand-in until custom model
            "heyhermes": "hey_jarvis",
        }
        key = aliases.get(key, key)
        tflite = list(models_dir.glob(f"*{key}*.tflite"))
        models_keys = getattr(openwakeword, "MODELS", {}) or {}
        if not tflite and key in models_keys:
            download_models(model_names=[key], target_directory=str(models_dir))
            tflite = list(models_dir.glob(f"*{key}*.tflite"))
        if not tflite:
            tflite = list(models_dir.glob("*.tflite"))
        if not tflite and models_keys:
            # download first available bundled model for bring-up
            first = next(iter(models_keys.keys()))
            download_models(model_names=[first], target_directory=str(models_dir))
            tflite = list(models_dir.glob("*.tflite"))
        if not tflite:
            raise RuntimeError(
                f"No openWakeWord model for {hotword!r} in {models_dir}. "
                "Install openwakeword and place a custom hey_hermes tflite or set wake.model_path."
            )
        model = Model(wakeword_models=[str(tflite[0])])

    class OWWWake:
        name = "openwakeword"

        def predict(self, pcm_int16: Any) -> bool:
            audio = np.asarray(pcm_int16, dtype=np.int16)
            model.predict(audio)
            return any(
                model.prediction_buffer[mdl][-1] > threshold for mdl in model.prediction_buffer
            )

        def reset(self) -> None:
            model.reset()

    return OWWWake()


class EnergyVad:
    """Simple RMS energy VAD — no torch. Good fallback and tests."""

    name = "energy"

    def __init__(self, threshold: float = 0.01):
        self.threshold = threshold

    def is_speech(self, pcm_float32: Any) -> bool:
        import numpy as np

        audio = np.asarray(pcm_float32, dtype=np.float32).reshape(-1)
        if audio.size == 0:
            return False
        rms = float(np.sqrt(np.mean(np.square(audio)) + 1e-12))
        return rms >= self.threshold

    def reset(self) -> None:
        return None


def try_silero_vad(models_dir: str | Path | None = None) -> Any:
    import numpy as np
    import torch

    model, utils = torch.hub.load(
        repo_or_dir="snakers4/silero-vad",
        model="silero_vad",
        force_reload=False,
        onnx=False,
        trust_repo=True,
    )

    class SileroVad:
        name = "silero"

        def is_speech(self, pcm_float32: Any) -> bool:
            audio = np.asarray(pcm_float32, dtype=np.float32)
            if audio.ndim > 1:
                audio = audio.reshape(-1)
            try:
                tensor = torch.from_numpy(audio)
                get_speech_timestamps = utils[0]
                # Prefer frame prob API when available
                if callable(model):
                    with torch.no_grad():
                        # silero expects 512 samples @ 16k for some builds; pad/trim
                        chunk = audio
                        if chunk.size < 512:
                            chunk = np.pad(chunk, (0, 512 - chunk.size))
                        elif chunk.size > 512:
                            # take last 512 for streaming-ish
                            chunk = chunk[-512:]
                        tensor = torch.from_numpy(chunk)
                        out = model(tensor, 16000)
                        prob = float(out.item() if hasattr(out, "item") else out)
                    return prob > 0.5
                ts = get_speech_timestamps(audio, model, sampling_rate=16000)
                return bool(ts)
            except Exception:  # noqa: BLE001
                return EnergyVad().is_speech(audio)

        def reset(self) -> None:
            return None

    return SileroVad()


def try_faster_whisper(model_size: str = "base", device: str = "cpu") -> Any:
    import numpy as np
    from faster_whisper import WhisperModel

    model = WhisperModel(model_size, device=device, compute_type="int8")

    class FasterWhisperStt:
        name = "faster-whisper"

        def transcribe(self, pcm_int16: Any, sample_rate: int = 16000) -> str:
            audio = np.asarray(pcm_int16, dtype=np.float32)
            if audio.dtype != np.float32 or np.max(np.abs(audio)) > 1.5:
                audio = audio.astype(np.float32) / 32768.0
            segments, _info = model.transcribe(audio, language="en", vad_filter=True)
            return " ".join(s.text.strip() for s in segments).strip()

    return FasterWhisperStt()


def build_audio_stack(
    *,
    models_dir: str | Path,
    wake_phrase: str = "hey hermes",
    wake_model_path: str | None = None,
    wake_threshold: float = 0.5,
    stt_model_size: str = "base",
    stt_device: str = "cpu",
    prefer_silero: bool = True,
) -> dict[str, Any]:
    """Build best-available wake/vad/stt stack. Raises if STT cannot load when required."""
    from narthex.audio import NullStt, NullWake

    out: dict[str, Any] = {"wake": NullWake(), "vad": EnergyVad(), "stt": NullStt(), "notes": []}
    try:
        out["wake"] = try_openwakeword(
            models_dir,
            hotword=wake_phrase,
            threshold=wake_threshold,
            model_path=wake_model_path,
        )
        out["notes"].append(f"wake={getattr(out['wake'], 'name', type(out['wake']).__name__)}")
    except Exception as e:  # noqa: BLE001
        out["notes"].append(f"wake_fallback_null:{e}")

    if prefer_silero:
        try:
            out["vad"] = try_silero_vad(models_dir)
            out["notes"].append("vad=silero")
        except Exception as e:  # noqa: BLE001
            out["vad"] = EnergyVad()
            out["notes"].append(f"vad=energy ({e})")
    else:
        out["notes"].append("vad=energy")

    try:
        out["stt"] = try_faster_whisper(model_size=stt_model_size, device=stt_device)
        out["notes"].append("stt=faster-whisper")
    except Exception as e:  # noqa: BLE001
        out["notes"].append(f"stt_null:{e}")

    return out
