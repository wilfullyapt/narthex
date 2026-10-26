from __future__ import annotations

import argparse
import json
import tarfile
from pathlib import Path

from narthex import __version__
from narthex.config import load_config
from narthex.hermes import HermesClient
from narthex.ota import OtaManager, keygen, sha256_file, sign_entry
from narthex.runtime import Runtime
from narthex.scenes import get_scene


def cmd_version(_: argparse.Namespace) -> int:
    print(__version__)
    return 0


def cmd_scene(args: argparse.Namespace) -> int:
    store = load_config(args.config)
    scene = get_scene(args.id or store.cfg.scene.default)
    print(json.dumps(scene.model_dump(), indent=2))
    return 0


def cmd_ping_hermes(args: argparse.Namespace) -> int:
    store = load_config(args.config)
    client = HermesClient(store.cfg.hermes, session_id=store.cfg.node.id)
    result = client.ping()
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


def cmd_status(args: argparse.Namespace) -> int:
    store = load_config(args.config)
    rt = Runtime(store)
    print(json.dumps(rt.status(), indent=2))
    return 0


def _ota_mgr(args: argparse.Namespace) -> OtaManager:
    store = load_config(args.config)
    return OtaManager(
        store.cfg.data_dir,
        require_signature=store.cfg.ota.require_signature,
        channel=store.cfg.ota.channel,
        check_url=store.cfg.ota.check_url,
        keep_versions=store.cfg.ota.keep_versions,
        current_version=__version__,
    )


def cmd_ota_keygen(args: argparse.Namespace) -> int:
    priv, pub = keygen()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "ota_private.key").write_text(priv + "\n", encoding="utf-8")
    (out / "ota_public.key").write_text(pub + "\n", encoding="utf-8")
    (out / "ota_private.key").chmod(0o600)
    print(json.dumps({"ok": True, "public": str(out / "ota_public.key"), "private": str(out / "ota_private.key")}))
    return 0


def cmd_ota_pack(args: argparse.Namespace) -> int:
    """Build a signed release tarball + manifest fragment for a versioned tree."""
    src = Path(args.source)
    version = args.version
    priv = Path(args.private_key).read_text(encoding="utf-8").strip()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Ensure VERSION marker
    ver_marker = src / "VERSION"
    if not ver_marker.exists():
        ver_marker.write_text(version + "\n", encoding="utf-8")

    tarball = out_dir / f"narthex-{version}.tar.gz"
    with tarfile.open(tarball, "w:gz") as tar:
        tar.add(src, arcname=src.name)

    digest = sha256_file(tarball)
    url = args.url or str(tarball.resolve())
    signature = sign_entry(priv, version, digest, url)
    entry = {
        "version": version,
        "url": url,
        "sha256": digest,
        "signature": signature,
    }
    manifest = {"channel": args.channel, "versions": [entry]}
    man_path = out_dir / f"manifest-{args.channel}.json"
    man_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "tarball": str(tarball), "manifest": str(man_path), "entry": entry}, indent=2))
    return 0


def cmd_ota_check(args: argparse.Namespace) -> int:
    mgr = _ota_mgr(args)
    if args.check_url:
        mgr.check_url = args.check_url
    print(json.dumps(mgr.check(), indent=2))
    return 0


def cmd_ota_apply(args: argparse.Namespace) -> int:
    mgr = _ota_mgr(args)
    if args.check_url:
        mgr.check_url = args.check_url
    if args.public_key:
        mgr.write_public_key(Path(args.public_key).read_text(encoding="utf-8").strip())
    result = mgr.apply(args.version)
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


def cmd_ota_status(args: argparse.Namespace) -> int:
    print(json.dumps(_ota_mgr(args).status(), indent=2))
    return 0


def cmd_ota_rollback(args: argparse.Namespace) -> int:
    result = _ota_mgr(args).rollback()
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="narthex", description="Narthex CLI")
    parser.add_argument("--config", "-c", default=None, help="Path to config YAML")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ver = sub.add_parser("version", help="Print version")
    p_ver.set_defaults(func=cmd_version)

    p_st = sub.add_parser("status", help="Print runtime status JSON")
    p_st.set_defaults(func=cmd_status)

    p_sc = sub.add_parser("scene", help="Dump a scene graph")
    p_sc.add_argument("--id", default=None)
    p_sc.set_defaults(func=cmd_scene)

    p_ping = sub.add_parser("ping-hermes", help="Ping Portunus API server")
    p_ping.set_defaults(func=cmd_ping_hermes)

    p_ota = sub.add_parser("ota", help="OTA operations")
    ota_sub = p_ota.add_subparsers(dest="ota_cmd", required=True)

    p_kg = ota_sub.add_parser("keygen", help="Generate Ed25519 OTA keypair")
    p_kg.add_argument("--out-dir", default="./ota-keys")
    p_kg.set_defaults(func=cmd_ota_keygen)

    p_pack = ota_sub.add_parser("pack", help="Build signed tarball + manifest")
    p_pack.add_argument("--source", required=True, help="Directory to pack")
    p_pack.add_argument("--version", required=True)
    p_pack.add_argument("--private-key", required=True)
    p_pack.add_argument("--out-dir", default="./ota-dist")
    p_pack.add_argument("--channel", default="stable")
    p_pack.add_argument("--url", default=None, help="Public URL for tarball (default: local path)")
    p_pack.set_defaults(func=cmd_ota_pack)

    p_chk = ota_sub.add_parser("check", help="Check channel for updates")
    p_chk.add_argument("--check-url", default=None)
    p_chk.set_defaults(func=cmd_ota_check)

    p_ap = ota_sub.add_parser("apply", help="Apply a signed version from manifest")
    p_ap.add_argument("version")
    p_ap.add_argument("--check-url", default=None)
    p_ap.add_argument("--public-key", default=None)
    p_ap.set_defaults(func=cmd_ota_apply)

    p_os = ota_sub.add_parser("status", help="OTA job status")
    p_os.set_defaults(func=cmd_ota_status)

    p_rb = ota_sub.add_parser("rollback", help="Rollback to previous version dir")
    p_rb.set_defaults(func=cmd_ota_rollback)

    args = parser.parse_args(argv)
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
