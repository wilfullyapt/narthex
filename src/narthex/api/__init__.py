from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from narthex import __version__
from narthex.display import Display
from narthex.ota import OtaManager
from narthex.runtime import Runtime
from narthex.widgets import Widget


class ConfigPatch(BaseModel):
    patch: dict = Field(default_factory=dict)


class ScenePut(BaseModel):
    scene: dict


class ScenePush(BaseModel):
    scene: dict
    ttl_s: float | None = 300


class DisplayBody(BaseModel):
    state: str
    level: int | None = None


class OtaApplyBody(BaseModel):
    version: str


class NotifyBody(BaseModel):
    text: str
    ttl_s: float | None = 8


def create_app(runtime: Runtime) -> FastAPI:
    app = FastAPI(title="Narthex", version=__version__)
    display = Display(runtime.cfg.display.backend)
    ota = OtaManager(
        require_signature=runtime.cfg.ota.require_signature,
        channel=runtime.cfg.ota.channel,
    )
    runtime.display_state = display.state
    runtime.ota_job = ota.job

    def require_token(authorization: str | None = Header(default=None)) -> None:
        expected = runtime.cfg.server.device_token
        if not expected:
            # Dev mode: allow if no token configured
            return
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="missing bearer token")
        got = authorization.removeprefix("Bearer ").strip()
        if got != expected:
            raise HTTPException(status_code=403, detail="invalid token")

    # --- Device API ---
    api = FastAPI()

    @api.get("/v1/status")
    def status(_: None = Depends(require_token)):
        st = runtime.status()
        st["display"] = display.state
        st["ota"] = ota.job
        return st

    @api.get("/v1/config")
    def config_get(_: None = Depends(require_token)):
        return {"ok": True, "config": runtime.store.as_public_dict()}

    @api.patch("/v1/config")
    def config_patch(body: ConfigPatch, _: None = Depends(require_token)):
        try:
            runtime.store.patch(body.patch)
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e)) from e
        return {"ok": True, "config": runtime.store.as_public_dict()}

    @api.get("/v1/scene")
    def scene_get(_: None = Depends(require_token)):
        return {"ok": True, "scene": runtime.scene.model_dump()}

    @api.put("/v1/scene")
    def scene_put(body: ScenePut, _: None = Depends(require_token)):
        from narthex.widgets import Scene

        scene = Scene.model_validate(body.scene)
        runtime.set_scene(scene)
        return {"ok": True, "scene": runtime.scene.model_dump()}

    @api.post("/v1/scene/push")
    def scene_push(body: ScenePush, _: None = Depends(require_token)):
        from narthex.widgets import Scene

        scene = Scene.model_validate(body.scene)
        if body.ttl_s is not None:
            scene.ttl_s = body.ttl_s
        runtime.set_scene(scene)
        return {"ok": True, "scene": runtime.scene.model_dump()}

    @api.get("/v1/widgets")
    def widgets_list(_: None = Depends(require_token)):
        return {"ok": True, "widgets": [w.model_dump() for w in runtime.scene.widgets]}

    @api.put("/v1/widgets/{widget_id}")
    def widget_upsert(widget_id: str, body: dict, _: None = Depends(require_token)):
        data = dict(body)
        data["id"] = widget_id
        w = Widget.model_validate(data)
        runtime.upsert_widget(w)
        return {"ok": True, "widget": w.model_dump()}

    @api.patch("/v1/widgets/{widget_id}")
    def widget_patch(widget_id: str, body: dict, _: None = Depends(require_token)):
        try:
            w = runtime.scene.move_widget(widget_id, **{k: body[k] for k in body if k in (
                "x", "y", "w", "h", "z", "props", "effect"
            )})
        except KeyError:
            raise HTTPException(status_code=404, detail="widget not found") from None
        runtime.bus.publish("scene", {"scene": runtime.scene.model_dump()})
        return {"ok": True, "widget": w.model_dump()}

    @api.delete("/v1/widgets/{widget_id}")
    def widget_delete(widget_id: str, _: None = Depends(require_token)):
        ok = runtime.scene.remove_widget(widget_id)
        if not ok:
            raise HTTPException(status_code=404, detail="widget not found")
        runtime.bus.publish("scene", {"scene": runtime.scene.model_dump()})
        return {"ok": True}

    @api.post("/v1/display")
    def display_set(body: DisplayBody, _: None = Depends(require_token)):
        try:
            result = display.set_state(body.state, body.level)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        runtime.display_state = display.state
        runtime.bus.publish("display", result)
        return result

    @api.post("/v1/ota/check")
    def ota_check(_: None = Depends(require_token)):
        return ota.check()

    @api.post("/v1/ota/apply")
    def ota_apply(body: OtaApplyBody, _: None = Depends(require_token)):
        return ota.apply(body.version)

    @api.get("/v1/ota/status")
    def ota_status(_: None = Depends(require_token)):
        return ota.status()

    @api.post("/v1/notify")
    def notify(body: NotifyBody, _: None = Depends(require_token)):
        runtime.bus.publish("notify", {"text": body.text, "ttl_s": body.ttl_s})
        return {"ok": True}

    app.mount("/device", api)

    # --- Local UI ---
    web_root = Path(__file__).resolve().parents[3] / "web"
    if (web_root / "index.html").exists():
        @app.get("/")
        def index():
            return FileResponse(web_root / "index.html")

        app.mount("/static", StaticFiles(directory=str(web_root)), name="static")

    @app.get("/api/state")
    def ui_state():
        return {
            "ok": True,
            "version": __version__,
            "style": runtime.cfg.style.model_dump(),
            "stage": runtime.cfg.scene.stage.model_dump(),
            "scene": runtime.scene.model_dump(),
            "display": display.state,
        }

    return app
