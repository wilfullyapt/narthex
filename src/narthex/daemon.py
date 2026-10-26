from __future__ import annotations

import argparse
import threading

import uvicorn

from narthex.api import create_app
from narthex.audio import build_pipeline
from narthex.config import load_config
from narthex.runtime import Runtime


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="narthexd", description="Narthex appliance daemon")
    parser.add_argument("--config", "-c", default=None, help="Config YAML path")
    parser.add_argument("--dry-run", action="store_true", help="Load config + home scene and exit")
    parser.add_argument("--ui-only", action="store_true", help="Bind UI host/port only")
    parser.add_argument("--api-only", action="store_true", help="Bind device API host/port only")
    args = parser.parse_args(argv)

    store = load_config(args.config)
    runtime = Runtime(store)
    runtime.audio = build_pipeline(runtime.bus)  # type: ignore[attr-defined]
    runtime.audio.arm()
    runtime.audio_state = runtime.audio.state.name.lower()

    if args.dry_run:
        print(
            f"narthexd dry-run ok versioned scene={runtime.scene.id} "
            f"widgets={len(runtime.scene.widgets)} "
            f"wake={store.cfg.wake.phrase!r} "
            f"cold_listen={store.cfg.wake.cold_listen_when_asleep} "
            f"audio={runtime.audio_state}"
        )
        return

    app = create_app(runtime)
    ui_host, ui_port = store.cfg.server.ui_host, store.cfg.server.ui_port
    api_host, api_port = store.cfg.server.api_host, store.cfg.server.api_port

    if args.ui_only:
        print(f"narthexd UI http://{ui_host}:{ui_port}/")
        uvicorn.run(app, host=ui_host, port=ui_port, log_level="info")
        return

    if args.api_only:
        print(f"narthexd device API http://{api_host}:{api_port}/device/v1/")
        uvicorn.run(app, host=api_host, port=api_port, log_level="info")
        return

    # Dual bind: API on LAN port, UI on localhost port (if different)
    if (ui_host, ui_port) == (api_host, api_port):
        print(f"narthexd combined http://{api_host}:{api_port}/ (UI + /device + /ws)")
        uvicorn.run(app, host=api_host, port=api_port, log_level="info")
        return

    def run_ui() -> None:
        uvicorn.run(app, host=ui_host, port=ui_port, log_level="info", log_config=None)

    t = threading.Thread(target=run_ui, name="narthex-ui", daemon=True)
    t.start()
    print(f"narthexd UI http://{ui_host}:{ui_port}/")
    print(f"narthexd device API http://{api_host}:{api_port}/device/v1/")
    uvicorn.run(app, host=api_host, port=api_port, log_level="info")


if __name__ == "__main__":
    main()
