from __future__ import annotations

import json
from pathlib import Path

from narthex import __version__
from narthex.audio import AudioPipeline, AudioState, NullWake
from narthex.bus import Bus
from narthex.config import ConfigStore, load_config
from narthex.ota import OtaManager, keygen, sha256_file, sign_entry, verify_entry
from narthex.runtime import Runtime
from narthex.scenes import home_scene


def test_version():
    assert __version__ == "0.2.0"


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


def test_runtime_status():
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

    store = ConfigStore(
        raw={"server": {"device_token": "test-token"}, "data_dir": "/tmp/narthex-test-data"}
    )
    app = create_app(Runtime(store))
    client = TestClient(app)
    r = client.get("/device/v1/status")
    assert r.status_code == 401
    r = client.get("/device/v1/status", headers={"Authorization": "Bearer test-token"})
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == "0.2.0"
    assert body["scene_id"] == "home"
    assert "ota" in body


def test_ui_state():
    from fastapi.testclient import TestClient

    from narthex.api import create_app

    app = create_app(Runtime(ConfigStore(raw={"data_dir": "/tmp/narthex-test-data2"})))
    client = TestClient(app)
    r = client.get("/api/state")
    assert r.status_code == 200
    data = r.json()
    assert data["style"]["gold"] == "#C9A227"
    assert data["scene"]["id"] == "home"


def test_audio_pipeline_state_machine():
    bus = Bus()
    events: list[str] = []
    bus.subscribe("*", lambda p: events.append(p.get("topic", "")))

    class AlwaysWake(NullWake):
        def predict(self, pcm_int16):
            return True

    pipe = AudioPipeline(bus=bus, wake=AlwaysWake())
    pipe.arm()
    assert pipe.state == AudioState.WAITING_WAKE
    assert pipe.process_wake_chunk([0] * 1280) is True
    assert pipe.state == AudioState.LISTENING
    assert "wake" in events


def test_ota_sign_verify_and_apply(tmp_path: Path):
    priv, pub = keygen()
    assert verify_entry(pub, "0.2.1", "abc", "file:///x", sign_entry(priv, "0.2.1", "abc", "file:///x"))

    src = tmp_path / "pkg"
    src.mkdir()
    (src / "VERSION").write_text("0.2.1\n", encoding="utf-8")
    (src / "README.txt").write_text("narthex ota test\n", encoding="utf-8")

    dist = tmp_path / "dist"
    dist.mkdir()
    import tarfile

    tarball = dist / "narthex-0.2.1.tar.gz"
    with tarfile.open(tarball, "w:gz") as tar:
        tar.add(src, arcname="pkg")
    digest = sha256_file(tarball)
    url = str(tarball.resolve())
    sig = sign_entry(priv, "0.2.1", digest, url)
    manifest = {
        "channel": "stable",
        "versions": [{"version": "0.2.1", "url": url, "sha256": digest, "signature": sig}],
    }
    man = dist / "manifest.json"
    man.write_text(json.dumps(manifest), encoding="utf-8")

    data = tmp_path / "data"
    mgr = OtaManager(
        data,
        require_signature=True,
        check_url=str(man),
        current_version="0.2.0",
        public_key_b64=pub,
        keep_versions=2,
    )
    checked = mgr.check()
    assert checked["ok"] is True
    assert checked["update"]["version"] == "0.2.1"

    bad = OtaManager(
        data / "bad",
        require_signature=True,
        check_url=str(man),
        current_version="0.2.0",
        public_key_b64=pub,
    )
    manifest2 = json.loads(man.read_text())
    manifest2["versions"][0]["signature"] = sign_entry(priv, "0.2.1", "0" * 64, url)
    man2 = dist / "manifest-bad.json"
    man2.write_text(json.dumps(manifest2), encoding="utf-8")
    bad.check_url = str(man2)
    refused = bad.apply("0.2.1")
    assert refused["ok"] is False

    applied = mgr.apply("0.2.1")
    assert applied["ok"] is True, applied
    assert mgr.current_version == "0.2.1"
    assert (data / "ota" / "current").exists()
    assert (data / "ota" / "versions" / "0.2.1").exists()

    src2 = tmp_path / "pkg2"
    src2.mkdir()
    (src2 / "VERSION").write_text("0.2.2\n", encoding="utf-8")
    t2 = dist / "narthex-0.2.2.tar.gz"
    with tarfile.open(t2, "w:gz") as tar:
        tar.add(src2, arcname="pkg2")
    d2 = sha256_file(t2)
    u2 = str(t2.resolve())
    s2 = sign_entry(priv, "0.2.2", d2, u2)
    man3 = dist / "manifest2.json"
    man3.write_text(
        json.dumps(
            {
                "channel": "stable",
                "versions": [
                    {"version": "0.2.2", "url": u2, "sha256": d2, "signature": s2},
                    {"version": "0.2.1", "url": url, "sha256": digest, "signature": sig},
                ],
            }
        ),
        encoding="utf-8",
    )
    mgr.check_url = str(man3)
    assert mgr.apply("0.2.2")["ok"] is True
    rb = mgr.rollback()
    assert rb["ok"] is True
    assert mgr.current_version == "0.2.1"


def test_ota_api_apply(tmp_path: Path):
    from fastapi.testclient import TestClient

    from narthex.api import create_app

    priv, pub = keygen()
    src = tmp_path / "rel"
    src.mkdir()
    (src / "VERSION").write_text("9.9.9\n", encoding="utf-8")
    import tarfile

    tb = tmp_path / "narthex-9.9.9.tar.gz"
    with tarfile.open(tb, "w:gz") as tar:
        tar.add(src, arcname="rel")
    digest = sha256_file(tb)
    url = str(tb.resolve())
    sig = sign_entry(priv, "9.9.9", digest, url)
    man = tmp_path / "m.json"
    man.write_text(
        json.dumps(
            {
                "channel": "stable",
                "versions": [{"version": "9.9.9", "url": url, "sha256": digest, "signature": sig}],
            }
        ),
        encoding="utf-8",
    )
    data = tmp_path / "d"
    store = ConfigStore(
        raw={
            "server": {"device_token": "tok"},
            "data_dir": str(data),
            "ota": {"require_signature": True, "check_url": str(man), "channel": "stable"},
        }
    )
    rt = Runtime(store)
    app = create_app(rt)
    rt.ota.write_public_key(pub)  # type: ignore[attr-defined]
    client = TestClient(app)
    h = {"Authorization": "Bearer tok"}
    r = client.post("/device/v1/ota/check", headers=h)
    assert r.status_code == 200 and r.json()["ok"] is True
    r = client.post("/device/v1/ota/apply", headers=h, json={"version": "9.9.9"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["version"] == "9.9.9"
