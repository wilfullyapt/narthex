from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class NodeConfig(BaseModel):
    id: str = "narthex-1"
    display_name: str = "Narthex"


class ServerConfig(BaseModel):
    ui_host: str = "127.0.0.1"
    ui_port: int = 7840
    api_host: str = "0.0.0.0"
    api_port: int = 7841
    device_token: str = ""


class HermesConfig(BaseModel):
    base_url: str = "http://127.0.0.1:8642/v1"
    model: str = "hermes-agent"
    session_header: str = "X-Hermes-Session-Id"
    timeout_s: float = 120.0
    api_key: str = ""


class WakeConfig(BaseModel):
    phrase: str = "hey hermes"
    engine: str = "openwakeword"
    cold_listen_when_asleep: bool = True
    model_path: str | None = None  # optional custom OWW tflite for hey_hermes
    threshold: float = 0.5


class SttConfig(BaseModel):
    engine: str = "faster-whisper"
    model_size: str = "base"
    device: str = "cpu"


class TtsConfig(BaseModel):
    engine: str = "piper"
    voice: str = "en_US-lessac-medium"


class AudioConfig(BaseModel):
    stt: SttConfig = Field(default_factory=SttConfig)
    tts: TtsConfig = Field(default_factory=TtsConfig)
    silence_end_s: float = 1.2
    listen_timeout_s: float = 12.0
    live: bool = False
    device_index: int | None = None


class DisplayConfig(BaseModel):
    backend: str = "noop"
    idle_sleep_s: int = 1800
    force_on_wake: bool = True


class StageConfig(BaseModel):
    width: int = 1000
    height: int = 1000


class SceneRootConfig(BaseModel):
    default: str = "home"
    stage: StageConfig = Field(default_factory=StageConfig)


class StyleConfig(BaseModel):
    void: str = "#000000"
    text: str = "#F2EDE4"
    gold: str = "#C9A227"
    gold_dim: str = "#8A7019"
    mist: str = "#A8A29A"


class IdentityConfig(BaseModel):
    enabled: bool = False
    voxmetrica_root: str | None = None


class OtaConfig(BaseModel):
    enabled: bool = True
    require_signature: bool = True
    channel: str = "stable"
    check_url: str | None = None
    keep_versions: int = 2


class AppConfig(BaseModel):
    version: int = 1
    node: NodeConfig = Field(default_factory=NodeConfig)
    data_dir: str = "data"
    server: ServerConfig = Field(default_factory=ServerConfig)
    hermes: HermesConfig = Field(default_factory=HermesConfig)
    wake: WakeConfig = Field(default_factory=WakeConfig)
    audio: AudioConfig = Field(default_factory=AudioConfig)
    display: DisplayConfig = Field(default_factory=DisplayConfig)
    scene: SceneRootConfig = Field(default_factory=SceneRootConfig)
    style: StyleConfig = Field(default_factory=StyleConfig)
    identity: IdentityConfig = Field(default_factory=IdentityConfig)
    ota: OtaConfig = Field(default_factory=OtaConfig)
    protected_keys: list[str] = Field(
        default_factory=lambda: ["ota.require_signature", "server.device_token"]
    )


def _deep_set(d: dict[str, Any], dotted: str, value: Any) -> None:
    parts = dotted.split(".")
    cur: dict[str, Any] = d
    for p in parts[:-1]:
        nxt = cur.get(p)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[p] = nxt
        cur = nxt
    cur[parts[-1]] = value


def _deep_get(d: dict[str, Any], dotted: str) -> Any:
    cur: Any = d
    for p in dotted.split("."):
        if not isinstance(cur, dict) or p not in cur:
            return None
        cur = cur[p]
    return cur


class ConfigStore:
    """Local config SoR with protected-key enforcement for patches."""

    def __init__(self, path: Path | None = None, raw: dict[str, Any] | None = None):
        self.path = path
        if raw is None:
            raw = {}
            if path and path.exists():
                raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        self._raw = raw
        self.cfg = self._build(raw)

    def _build(self, raw: dict[str, Any]) -> AppConfig:
        data = copy.deepcopy(raw)
        # Env overlays for secrets
        token = os.environ.get("NARTHEX_DEVICE_TOKEN", "")
        if token:
            data.setdefault("server", {})["device_token"] = token
        key = os.environ.get("NARTHEX_HERMES_API_KEY", "")
        if key:
            data.setdefault("hermes", {})["api_key"] = key
        conf_env = os.environ.get("NARTHEX_CONFIG")
        if conf_env and not self.path:
            p = Path(conf_env)
            if p.exists():
                file_raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
                data = {**file_raw, **data}
        return AppConfig.model_validate(data)

    def reload(self) -> AppConfig:
        if self.path and self.path.exists():
            self._raw = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
        self.cfg = self._build(self._raw)
        return self.cfg

    def as_public_dict(self) -> dict[str, Any]:
        d = self.cfg.model_dump()
        # Redact secrets
        if d.get("server", {}).get("device_token"):
            d["server"]["device_token"] = "***"
        if d.get("hermes", {}).get("api_key"):
            d["hermes"]["api_key"] = "***"
        return d

    def patch(self, patch: dict[str, Any]) -> AppConfig:
        """Shallow-deep merge dict patch; reject protected key clears/changes when locked."""
        new_raw = copy.deepcopy(self._raw)

        def merge(a: dict[str, Any], b: dict[str, Any], prefix: str = "") -> None:
            for k, v in b.items():
                path = f"{prefix}.{k}" if prefix else k
                if path in self.cfg.protected_keys:
                    # Allow same value; block change
                    old = _deep_get(
                        {
                            "server": {"device_token": self.cfg.server.device_token},
                            "ota": {"require_signature": self.cfg.ota.require_signature},
                        },
                        path,
                    )
                    # Evaluate against built cfg paths
                    cur = self.cfg.model_dump()
                    old = _deep_get(cur, path)
                    if v != old:
                        raise PermissionError(f"protected key not patchable: {path}")
                if isinstance(v, dict) and isinstance(a.get(k), dict):
                    merge(a[k], v, path)
                else:
                    a[k] = v

        merge(new_raw, patch)
        self._raw = new_raw
        self.cfg = self._build(new_raw)
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            # Do not write secrets from env-only into file if file lacked them
            to_write = copy.deepcopy(new_raw)
            self.path.write_text(
                yaml.safe_dump(to_write, sort_keys=False, allow_unicode=True),
                encoding="utf-8",
            )
        return self.cfg


def load_config(path: str | Path | None = None) -> ConfigStore:
    if path is None:
        env = os.environ.get("NARTHEX_CONFIG")
        path = env if env else None
    p = Path(path) if path else None
    return ConfigStore(path=p)
