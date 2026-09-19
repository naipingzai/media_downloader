"""Web API — 纯总线调用。"""
from fastapi import FastAPI
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from shared.core import __VERSION__, PROJECT_NAME, REPOSITORY, ROOT, VOLUME
from shared.core.ops import PlatformBus
from shared.core.cookies import CookieManager
from shared.translation import _
from platforms import load_all_platforms


class DownloadRequest(BaseModel):
    platform: str
    url: str = ""
    feature: str = ""


class CookieRequest(BaseModel):
    platform: str
    cookie: str


class APIResponse(BaseModel):
    message: str
    data: dict | list | None = None


def create_web_app() -> FastAPI:
    load_all_platforms()
    cm = CookieManager()
    app = FastAPI(title=PROJECT_NAME, version=__VERSION__)
    static_dir = ROOT / "ui" / "web" / "static"
    if static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/")
    async def index():
        f = ROOT / "ui" / "web" / "templates" / "index.html"
        return HTMLResponse(content=f.read_text(encoding="utf-8")) if f.is_file() else RedirectResponse(url=REPOSITORY)

    @app.get("/api/platforms")
    async def api_platforms():
        return PlatformBus.list_platforms()

    @app.get("/api/features/{platform}")
    async def api_features(platform: str):
        return [{"id": f.id, "name": f.name, "need_url": f.need_url}
                for f in PlatformBus.get_features(platform)]

    @app.get("/api/cookie_hint/{platform}")
    async def api_cookie_hint(platform: str):
        ops = PlatformBus.get_ops(platform)
        return {"hint": ops.cookie_hint if ops else ""}

    @app.get("/api/storage")
    async def api_storage():
        from shared.core.config import ConfigManager
        config = ConfigManager.load()
        return {"mode": config.storage_mode, "format": config.storage_format,
                "dedup": config.dedup, "modes": [
                    {"id": "flat", "name": "直接存储"},
                    {"id": "by_author", "name": "按作者分目录"},
                    {"id": "by_date", "name": "按日期分目录"},
                    {"id": "by_type", "name": "按类型分目录"}]}

    @app.post("/api/storage")
    async def api_set_storage(req: CookieRequest):
        from shared.core.config import ConfigManager, AppConfig
        config = ConfigManager.load()
        config.storage_mode = req.platform  # reuse field
        ConfigManager.save(config)
        return {"success": True, "mode": config.storage_mode}

    @app.get("/api/cookie")
    async def get_cookie():
        return APIResponse(message="ok", data={
            "status": cm.status_text(), "profiles": cm.get_profile_names(),
            "active": cm.get_active(),
            "cookies": {p: {k: bool(v) for k, v in cm.get_platforms(p).items()}
                         for p in cm.get_profile_names()}})

    @app.post("/api/cookie")
    async def set_cookie(req: CookieRequest):
        cm.set(req.platform, req.cookie)
        return APIResponse(message=_("Cookie 已保存: {p}").format(p=req.platform))

    @app.post("/api/download")
    async def download(req: DownloadRequest):
        if not req.feature:
            return APIResponse(message=_("请选择功能"))
        cookie = cm.get(req.platform)
        save_dir = VOLUME / req.platform
        save_dir.mkdir(parents=True, exist_ok=True)
        result = await PlatformBus.run(req.platform, req.feature, req.url, cookie, save_dir)
        return APIResponse(
            message=result.message,
            data={"success": result.success, "log": result.log, "files": result.files, "data": result.data})

    return app
