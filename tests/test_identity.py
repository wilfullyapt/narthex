"""Identity client — optional VoxMetrica without hard dep."""

from __future__ import annotations

from narthex.config import ConfigStore
from narthex.identity import IdentityClient, build_identity


def test_build_identity_disabled_by_default():
    store = ConfigStore(raw={"data_dir": "/tmp/narthex-id-off"})
    client = build_identity(store.cfg)
    assert client.enabled is False
    assert client.available is False
    assert client.badge(None) == ""


def test_identity_client_graceful_without_voxmetrica(monkeypatch, tmp_path):
    # Force enabled but import will fail or package missing — should not crash
    c = IdentityClient(enabled=True, voxmetrica_root=tmp_path, ingress="narthex", session_id="t")
    # If voxmetrica not installed in CI env, available is False
    assert c.enabled is False or c.available is True
    out = c.identify_file(tmp_path / "missing.wav")
    assert out.get("outcome") in ("unknown", None) or out.get("ok") is False


def test_doorway_accepts_claim_without_identity_pkg():
    from narthex.doorway import Doorway
    from narthex.runtime import Runtime
    from narthex.tts import NullTts

    class MockHermes:
        def chat(self, user_text, *, system=None):
            assert "Alex" in (system or "")
            return {"choices": [{"message": {"content": "hi Alex"}}]}

    store = ConfigStore(raw={"data_dir": "/tmp/narthex-id-claim"})
    rt = Runtime(store)
    door = Doorway(rt, hermes=MockHermes(), tts=NullTts())
    claim = {
        "outcome": "matched",
        "speaker_id": "alex",
        "display_name": "Alex",
        "confidence": 0.9,
        "matched": True,
    }
    result = door.handle_user_text("hello", speak=False, claim=claim)
    assert result["ok"] is True
    assert result["claim"]["speaker_id"] == "alex"
    assert result["assistant_text"] == "hi Alex"
