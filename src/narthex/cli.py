from __future__ import annotations

import argparse
import json

from narthex import __version__
from narthex.config import load_config
from narthex.hermes import HermesClient
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

    args = parser.parse_args(argv)
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
