from __future__ import annotations

import argparse

import uvicorn

from narthex.api import create_app
from narthex.config import load_config
from narthex.runtime import Runtime


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="narthexd", description="Narthex appliance daemon")
    parser.add_argument("--config", "-c", default=None, help="Config YAML path")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Load config + home scene and exit",
    )
    parser.add_argument("--ui-only", action="store_true", help="Bind UI server only")
    args = parser.parse_args(argv)

    store = load_config(args.config)
    runtime = Runtime(store)

    if args.dry_run:
        print(
            f"narthexd dry-run ok versioned scene={runtime.scene.id} "
            f"widgets={len(runtime.scene.widgets)} "
            f"wake={store.cfg.wake.phrase!r} "
            f"cold_listen={store.cfg.wake.cold_listen_when_asleep}"
        )
        return

    app = create_app(runtime)
    # Mount device API routes are under /device; also expose bare for tools convenience
    # by running two binds in future. For scaffold: single process, UI host + device via path.
    host = store.cfg.server.ui_host if args.ui_only else store.cfg.server.api_host
    port = store.cfg.server.ui_port if args.ui_only else store.cfg.server.api_port
    # Serve both UI and /device on the chosen port for early dev simplicity.
    print(f"narthexd listening on http://{host}:{port} (UI / and device /device/v1/*)")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
