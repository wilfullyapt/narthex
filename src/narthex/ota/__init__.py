from __future__ import annotations

"""Signed OTA: check → verify → stage → switch → healthgate → rollback.

Manifest entry is signed with Ed25519 over the canonical line:
  ``{version}\\n{sha256}\\n{url}``

Public key path: ``{data_dir}/ota/ota_public.pem`` (PEM raw 32-byte or OpenSSH not required —
we store raw base64 pubkey in ``ota_public.key`` for simplicity).
"""


import hashlib
import json
import os
import shutil
import tarfile
import tempfile
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any

from narthex import __version__

# cryptography is optional at import for environments without it during docs-only;
# tests install it via project deps.
try:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )

    _HAS_CRYPTO = True
except ImportError:  # pragma: no cover
    _HAS_CRYPTO = False
    InvalidSignature = Exception  # type: ignore[misc, assignment]


def _b64(data: bytes) -> str:
    import base64

    return base64.b64encode(data).decode("ascii")


def _b64d(s: str) -> bytes:
    import base64

    return base64.b64decode(s.encode("ascii"))


def canonical_payload(version: str, sha256: str, url: str) -> bytes:
    return f"{version}\n{sha256}\n{url}".encode()


def keygen() -> tuple[str, str]:
    """Return (private_b64, public_b64) Ed25519 keypair."""
    if not _HAS_CRYPTO:
        raise RuntimeError("cryptography package required for OTA keys")
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()
    priv_bytes = priv.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_bytes = pub.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return _b64(priv_bytes), _b64(pub_bytes)


def sign_entry(private_b64: str, version: str, sha256: str, url: str) -> str:
    if not _HAS_CRYPTO:
        raise RuntimeError("cryptography package required for OTA sign")
    priv = Ed25519PrivateKey.from_private_bytes(_b64d(private_b64))
    sig = priv.sign(canonical_payload(version, sha256, url))
    return _b64(sig)


def verify_entry(public_b64: str, version: str, sha256: str, url: str, signature_b64: str) -> bool:
    if not _HAS_CRYPTO:
        raise RuntimeError("cryptography package required for OTA verify")
    pub = Ed25519PublicKey.from_public_bytes(_b64d(public_b64))
    try:
        pub.verify(_b64d(signature_b64), canonical_payload(version, sha256, url))
        return True
    except InvalidSignature:
        return False


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch_bytes(url: str, timeout: float = 60.0) -> bytes:
    if url.startswith("file://"):
        p = Path(url[7:])
        return p.read_bytes()
    if url.startswith("/") or (len(url) > 2 and url[1] == ":"):
        return Path(url).read_bytes()
    req = urllib.request.Request(url, headers={"User-Agent": f"narthex-ota/{__version__}"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def fetch_json(url: str, timeout: float = 30.0) -> dict[str, Any]:
    raw = fetch_bytes(url, timeout=timeout)
    return json.loads(raw.decode("utf-8"))


class OtaManager:
    def __init__(
        self,
        data_dir: str | Path,
        *,
        require_signature: bool = True,
        channel: str = "stable",
        check_url: str | None = None,
        keep_versions: int = 2,
        public_key_b64: str | None = None,
        current_version: str | None = None,
    ):
        self.data_dir = Path(data_dir)
        self.ota_root = self.data_dir / "ota"
        self.versions_dir = self.ota_root / "versions"
        self.stage_dir = self.ota_root / "stage"
        self.current_link = self.ota_root / "current"
        self.public_key_path = self.ota_root / "ota_public.key"
        self.require_signature = require_signature
        self.channel = channel
        self.check_url = check_url
        self.keep_versions = max(1, keep_versions)
        self._public_key_b64 = public_key_b64
        self.current_version = current_version or __version__
        self.job: dict[str, Any] = {"state": "idle"}
        self._lock = threading.Lock()
        self.ota_root.mkdir(parents=True, exist_ok=True)
        self.versions_dir.mkdir(parents=True, exist_ok=True)

    def public_key(self) -> str | None:
        if self._public_key_b64:
            return self._public_key_b64
        if self.public_key_path.exists():
            return self.public_key_path.read_text(encoding="utf-8").strip()
        env = os.environ.get("NARTHEX_OTA_PUBLIC_KEY", "").strip()
        return env or None

    def write_public_key(self, public_b64: str) -> Path:
        self.public_key_path.parent.mkdir(parents=True, exist_ok=True)
        self.public_key_path.write_text(public_b64.strip() + "\n", encoding="utf-8")
        self._public_key_b64 = public_b64.strip()
        return self.public_key_path

    def status(self) -> dict[str, Any]:
        return {
            "ok": True,
            "job": dict(self.job),
            "current_version": self.current_version,
            "channel": self.channel,
            "require_signature": self.require_signature,
            "check_url": self.check_url,
            "current_path": str(self.current_link.resolve()) if self.current_link.exists() else None,
        }

    def check(self) -> dict[str, Any]:
        if not self.check_url:
            self.job = {
                "state": "checked",
                "channel": self.channel,
                "update": None,
                "note": "no check_url configured",
            }
            return {"ok": True, **self.job}
        try:
            manifest = fetch_json(self.check_url)
        except Exception as e:  # noqa: BLE001
            self.job = {"state": "error", "error": f"manifest fetch failed: {e}"}
            return {"ok": False, "error": str(e), "job": self.job}

        versions = manifest.get("versions") or []
        # pick newest not equal to current (manifest order: latest first preferred)
        update = None
        for entry in versions:
            ver = str(entry.get("version", ""))
            if ver and ver != self.current_version:
                update = entry
                break
        if versions and update is None:
            # already on listed version
            update = None
        self.job = {
            "state": "checked",
            "channel": manifest.get("channel", self.channel),
            "update": update,
            "manifest_count": len(versions),
        }
        return {"ok": True, "channel": self.job["channel"], "update": update, "job": self.job}

    def apply(self, version: str, *, restart: bool = False) -> dict[str, Any]:
        with self._lock:
            return self._apply_locked(version, restart=restart)

    def _apply_locked(self, version: str, *, restart: bool) -> dict[str, Any]:
        self.job = {"state": "applying", "version": version, "started_at": time.time()}
        if not self.check_url:
            self.job = {"state": "error", "error": "no check_url", "version": version}
            return {"ok": False, "error": "no check_url configured", "job": self.job}

        try:
            manifest = fetch_json(self.check_url)
        except Exception as e:  # noqa: BLE001
            self.job = {"state": "error", "error": str(e), "version": version}
            return {"ok": False, "error": str(e), "job": self.job}

        entry = next((v for v in (manifest.get("versions") or []) if str(v.get("version")) == version), None)
        if not entry:
            self.job = {"state": "error", "error": f"version not in manifest: {version}"}
            return {"ok": False, "error": self.job["error"], "job": self.job}

        url = str(entry["url"])
        expect_sha = str(entry["sha256"]).lower()
        signature = entry.get("signature")

        if self.require_signature:
            pub = self.public_key()
            if not pub:
                self.job = {"state": "refused", "reason": "no_public_key", "version": version}
                return {"ok": False, "error": "OTA public key missing", "job": self.job}
            if not signature:
                self.job = {"state": "refused", "reason": "unsigned_entry", "version": version}
                return {"ok": False, "error": "manifest entry missing signature", "job": self.job}
            if not verify_entry(pub, version, expect_sha, url, str(signature)):
                self.job = {"state": "refused", "reason": "bad_signature", "version": version}
                return {"ok": False, "error": "signature verification failed", "job": self.job}

        # Download
        self.job["state"] = "downloading"
        try:
            blob = fetch_bytes(url)
        except Exception as e:  # noqa: BLE001
            self.job = {"state": "error", "error": f"download failed: {e}", "version": version}
            return {"ok": False, "error": str(e), "job": self.job}

        got_sha = hashlib.sha256(blob).hexdigest()
        if got_sha != expect_sha:
            self.job = {
                "state": "error",
                "error": "sha256 mismatch",
                "expected": expect_sha,
                "got": got_sha,
            }
            return {"ok": False, "error": "sha256 mismatch", "job": self.job}

        # Stage extract
        self.job["state"] = "staging"
        target = self.versions_dir / version
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True)

        prev_current: str | None = None
        if self.current_link.exists() or self.current_link.is_symlink():
            try:
                prev_current = str(self.current_link.resolve())
            except OSError:
                prev_current = None

        with tempfile.TemporaryDirectory(prefix="narthex-ota-") as tmp:
            tarball = Path(tmp) / "pkg.tar.gz"
            tarball.write_bytes(blob)
            try:
                with tarfile.open(tarball, "r:gz") as tar:
                    # safe extract — Python 3.12+ has data filter; 3.11 manual
                    self._safe_extract(tar, target)
            except Exception as e:  # noqa: BLE001
                shutil.rmtree(target, ignore_errors=True)
                self.job = {"state": "error", "error": f"extract failed: {e}", "version": version}
                return {"ok": False, "error": str(e), "job": self.job}

        # Healthgate: require marker file VERSION or pyproject/narthex marker
        if not self._healthgate(target, version):
            shutil.rmtree(target, ignore_errors=True)
            self.job = {"state": "error", "error": "healthgate failed", "version": version}
            return {"ok": False, "error": "healthgate failed after extract", "job": self.job}

        # Atomic switch
        self.job["state"] = "switching"
        tmp_link = self.ota_root / f"current.tmp.{os.getpid()}"
        if tmp_link.exists() or tmp_link.is_symlink():
            tmp_link.unlink()
        tmp_link.symlink_to(target.resolve())
        tmp_link.replace(self.current_link)

        self.current_version = version
        self._prune_versions(keep=version)
        self.job = {
            "state": "success",
            "version": version,
            "previous": prev_current,
            "path": str(target),
            "restart_requested": restart,
            "finished_at": time.time(),
        }
        return {"ok": True, "job": self.job, "version": version, "path": str(target)}

    def rollback(self) -> dict[str, Any]:
        """Point current at the newest version dir that is not current_version."""
        with self._lock:
            versions = sorted(
                [p for p in self.versions_dir.iterdir() if p.is_dir()],
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            candidates = [p for p in versions if p.name != self.current_version]
            if not candidates:
                return {"ok": False, "error": "no rollback target"}
            target = candidates[0]
            tmp_link = self.ota_root / f"current.tmp.{os.getpid()}"
            if tmp_link.exists() or tmp_link.is_symlink():
                tmp_link.unlink()
            tmp_link.symlink_to(target.resolve())
            tmp_link.replace(self.current_link)
            old = self.current_version
            self.current_version = target.name
            self.job = {"state": "rolled_back", "from": old, "to": target.name}
            return {"ok": True, "job": self.job}

    def _healthgate(self, root: Path, version: str) -> bool:
        # Accept VERSION file matching, or any of marker paths
        ver_file = root / "VERSION"
        if ver_file.exists():
            return ver_file.read_text(encoding="utf-8").strip() == version
        # tarball may nest one top dir
        kids = [p for p in root.iterdir() if p.is_dir()]
        if len(kids) == 1:
            nested = kids[0] / "VERSION"
            if nested.exists():
                return nested.read_text(encoding="utf-8").strip() == version
            if (kids[0] / "pyproject.toml").exists() or (kids[0] / "src" / "narthex").exists():
                return True
        return bool((root / "pyproject.toml").exists() or (root / "src" / "narthex").exists())

    def _prune_versions(self, keep: str) -> None:
        versions = sorted(
            [p for p in self.versions_dir.iterdir() if p.is_dir()],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        keep_names: set[str] = {keep}
        for p in versions:
            if len(keep_names) >= self.keep_versions:
                break
            keep_names.add(p.name)
        for p in versions:
            if p.name not in keep_names:
                shutil.rmtree(p, ignore_errors=True)

    @staticmethod
    def _safe_extract(tar: tarfile.TarFile, dest: Path) -> None:
        dest = dest.resolve()
        for member in tar.getmembers():
            member_path = (dest / member.name).resolve()
            if not str(member_path).startswith(str(dest)):
                raise RuntimeError(f"unsafe tar path: {member.name}")
        tar.extractall(dest)
