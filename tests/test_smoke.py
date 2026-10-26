from __future__ import annotations

from pathlib import Path

from narthex import __version__
from narthex.config import ConfigStore, load_config
from narthex.runtime import Runtime
from narthex.scenes import home_scene


def test_version():
    assert __version__ == "0.1.0"


def test_home_scene_has_gold_node():
    scene = home_scene()
    assert scene.id == "home"
    ids = {w.id for w in scene.widgets}
    assert "gold_node" in ids
    assert "clock_main" in ids
    assert "voice_stage" in ids
    node = next(w for w in scene.widgets if w.id == "gold_node")
    assert node.z == 20
    assert node.type == "gold_node"


def test_widget_move_absolute():
    scene = home_scene()
    w = scene.move_widget("clock_main", x=10, y=20, z=15)
    assert w.x == 10 and w.y == 20 and w.z == 15


def test_config_defaults_gold():
    store = ConfigStore(raw={})
    assert store.cfg.style.gold == "#C9A227"
    assert store.cfg.wake.cold_listen_when_asleep is True
    assert store.cfg.wake.phrase == "hey hermes"
    assert store.cfg.ota.require_signature is True


def test_protected_key_patch_blocked():
    store = ConfigStore(raw={"ota": {"require_signature": True}})
    try:
        store.patch({"ota": {"require_signature": False}})
        assert False, "expected PermissionError"
    except PermissionError:
        pass


def test_runtime_status(tmp_path: Path):
    example = Path(__file__).resolve().parents[1] / "config.example.yaml"
    store = load_config(example)
    rt = Runtime(store)
    st = rt.status()
    assert st["ok"] is True
    assert st["scene_id"] == "home"
    assert st["wake"]["cold_listen"] is True


def test_api_status():
    from fastapi.testclient import TestClient

    from narthex.api import create_app

    store = ConfigStore(raw={"server": {"device_token": "test-token"}})
    app = create_app(Runtime(store))
    client = TestClient(app)
    r = client.get("/device/v1/status")
    assert r.status_code == 401
    r = client.get("/device/v1/status", headers={"Authorization": "Bearer test-token"})
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == "0.1.0"
    assert body["scene_id"] == "home"


def test_ui_state():
    from fastapi.testclient import TestClient

    from narthex.api import create_app

    app = create_app(Runtime(ConfigStore(raw={})))
    client = TestClient(app)
    r = client.get("/api/state")
    assert r.status_code == 200
    data = r.json()
    assert data["style"]["gold"] == "#C9A227"
    assert data["scene"]["id"] == "home"
