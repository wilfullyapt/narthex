from __future__ import annotations

"""Doorway turn: STT text → Portunus → voice_stage update → optional TTS + display on."""


from typing import Any

from narthex.hermes import HermesClient
from narthex.runtime import Runtime
from narthex.tts import NullTts, TtsBackend
from narthex.widgets import Widget

DEFAULT_SYSTEM = (
    "You are Portunus, the household voice doorway mind speaking through Narthex. "
    "Answer briefly for spoken playback (1–3 short sentences unless asked for detail). "
    "No markdown tables. Prefer plain speech."
)


def _extract_assistant_text(payload: dict[str, Any]) -> str:
    try:
        choices = payload.get("choices") or []
        if not choices:
            return ""
        msg = choices[0].get("message") or {}
        content = msg.get("content") or ""
        if isinstance(content, list):
            # multimodal content parts
            parts = []
            for p in content:
                if isinstance(p, dict) and p.get("type") == "text":
                    parts.append(p.get("text") or "")
                elif isinstance(p, str):
                    parts.append(p)
            return " ".join(parts).strip()
        return str(content).strip()
    except Exception:  # noqa: BLE001
        return ""


class Doorway:
    def __init__(
        self,
        runtime: Runtime,
        hermes: HermesClient | None = None,
        tts: TtsBackend | None = None,
        system_prompt: str = DEFAULT_SYSTEM,
    ):
        self.runtime = runtime
        self.hermes = hermes or HermesClient(runtime.cfg.hermes, session_id=runtime.cfg.node.id)
        self.tts = tts or NullTts()
        self.system_prompt = system_prompt
        self.last_turn: dict[str, Any] = {}

    def set_voice_stage(
        self,
        *,
        state: str,
        user_text: str = "",
        assistant_text: str = "",
        partial: str = "",
        visible: bool = True,
    ) -> None:
        scene = self.runtime.scene
        props = {
            "state": state,
            "user_text": user_text,
            "assistant_text": assistant_text,
            "partial": partial,
            "visible": visible,
        }
        try:
            scene.move_widget("voice_stage", props=props)
        except KeyError:
            scene.upsert_widget(
                Widget(
                    id="voice_stage",
                    type="voice_stage",
                    x=80,
                    y=520,
                    w=840,
                    h=260,
                    z=500,
                    props=props,
                )
            )
        # gold node mode
        try:
            mode = "listen" if state in ("listening", "wake", "stt") else "idle"
            if state in ("brain", "thinking"):
                mode = "listen"
            if state == "error":
                mode = "degraded"
            scene.move_widget("gold_node", props={"mode": mode})
        except KeyError:
            pass
        self.runtime.bus.publish("scene", {"scene": scene.model_dump()})
        self.runtime.audio_state = state

    def force_display_on(self) -> None:
        # logical on; HW via display service if attached on runtime
        display = getattr(self.runtime, "display", None)
        if display is not None:
            display.set_state("on")
            self.runtime.display_state = "on"
        else:
            self.runtime.display_state = "on"
        self.runtime.bus.publish("display", {"state": "on", "reason": "wake_or_turn"})

    def handle_user_text(self, text: str, *, speak: bool = True) -> dict[str, Any]:
        text = (text or "").strip()
        self.force_display_on()
        if not text:
            self.set_voice_stage(state="error", user_text="", assistant_text="I didn't catch that.", visible=True)
            result = {"ok": False, "error": "empty transcript"}
            self.last_turn = result
            return result

        self.set_voice_stage(state="brain", user_text=text, assistant_text="", visible=True)
        self.runtime.bus.publish("turn", {"phase": "brain", "user_text": text})

        try:
            raw = self.hermes.chat(text, system=self.system_prompt)
            assistant = _extract_assistant_text(raw) or "(no reply)"
            hermes_ok = True
            hermes_err = None
        except Exception as e:  # noqa: BLE001
            assistant = "I can't reach Portunus right now."
            raw = {}
            hermes_ok = False
            hermes_err = str(e)

        self.set_voice_stage(state="speaking", user_text=text, assistant_text=assistant, visible=True)
        tts_result: dict[str, Any] = {"ok": True, "spoken": False, "backend": "skipped"}
        if speak:
            tts_result = self.tts.speak(assistant)

        self.set_voice_stage(state="idle", user_text=text, assistant_text=assistant, visible=True)
        result = {
            "ok": hermes_ok,
            "user_text": text,
            "assistant_text": assistant,
            "hermes": raw if hermes_ok else {"error": hermes_err},
            "tts": tts_result,
        }
        self.last_turn = result
        self.runtime.bus.publish("turn", {"phase": "done", **{k: result[k] for k in ("user_text", "assistant_text", "ok")}})
        return result

    def handle_wake(self) -> dict[str, Any]:
        self.force_display_on()
        self.set_voice_stage(state="listening", user_text="", assistant_text="", visible=True)
        self.runtime.bus.publish("wake", {"phrase": self.runtime.cfg.wake.phrase})
        return {"ok": True, "state": "listening"}
