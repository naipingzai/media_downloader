"""PyWebView GUI backend - pure bus calls, all methods return JSON strings."""
import asyncio, json
from threading import Event, Thread
from shared.core import __VERSION__, PROJECT_NAME, VOLUME, REPOSITORY
from shared.core.ops import PlatformBus
from shared.core.cookies import CookieManager
from platforms import load_all_platforms


class GuiBackend:
    def __init__(self):
        self._window = None; self._loop = None; self._thread = None; self._ready = Event()
        load_all_platforms()
        self.cm = CookieManager()

    def _bind_window(self, window):
        self._window = window; self._loop = asyncio.new_event_loop()
        self._thread = Thread(target=self._run_loop, daemon=True)
        self._thread.start(); self._ready.wait(timeout=10)

    def _run_loop(self):
        asyncio.set_event_loop(self._loop); self._ready.set(); self._loop.run_forever()

    def stop(self):
        if self._loop: self._loop.call_soon_threadsafe(self._loop.stop)

    def get_version(self):
        return __VERSION__

    def get_platforms(self):
        return json.dumps(PlatformBus.list_platforms())

    def get_features(self):
        result = {}
        for pid, features in PlatformBus.get_all_features().items():
            result[pid] = [{"id": f.id, "name": f.name, "need_link": f.need_url} for f in features]
        return json.dumps(result, ensure_ascii=False)

    def get_cookie_hint(self, platform):
        ops = PlatformBus.get_ops(platform)
        return ops.cookie_hint if ops else ""

    def get_cookie(self, platform):
        cookie = self.cm.get(platform)
        return json.dumps({"status": f"\u5df2\u8bbe\u7f6e ({len(cookie)}\u5b57\u7b26)" if cookie else "\u672a\u8bbe\u7f6e", "length": len(cookie)})

    def save_cookie(self, platform, cookie):
        self.cm.set(platform, cookie)
        return json.dumps({"success": True, "message": f"Cookie saved: {platform}"})

    def execute(self, platform, feature, url=""):
        future = asyncio.run_coroutine_threadsafe(
            self._do_execute(platform, feature, url), self._loop)
        return future.result(timeout=300)

    async def _do_execute(self, platform, feature, url):
        cookie = self.cm.get(platform)
        save_dir = VOLUME / platform
        save_dir.mkdir(parents=True, exist_ok=True)
        result = await PlatformBus.run(platform, feature, url, cookie, save_dir)
        return json.dumps({
            "success": result.success, "message": result.message,
            "data": result.data, "log": result.log, "files": result.files
        }, ensure_ascii=False)

    def open_download_folder(self):
        import subprocess, platform as pf
        path = str(VOLUME)
        if pf.system() == "Darwin": subprocess.Popen(["open", path])
        elif pf.system() == "Windows": subprocess.Popen(["explorer", path])
        else: subprocess.Popen(["xdg-open", path])
