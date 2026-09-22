"""封面加载器 — 使用 curl_cffi 后台下载封面图（兼容 PyInstaller，带缓存）。

Qt 的 QNetworkAccessManager 在 PyInstaller 冻结包中常因缺少 SSL 证书或
TLS 指纹被 CDN 拒绝而失败。这里统一改用项目已有的 curl_cffi（支持浏览器
指纹模拟），通过线程池后台下载，主线程只接收信号更新 UI。
"""
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from PySide6.QtGui import QImage, QPixmap

__all__ = ["CoverLoader"]


def _cover_headers(url: str) -> dict:
    u = url.lower()
    if "douyin" in u or "douyinpic" in u:
        return {"Referer": "https://www.douyin.com/"}
    if "bilibili" in u or "hdslb" in u:
        return {"Referer": "https://www.bilibili.com/"}
    if "kuaishou" in u or "ksurl" in u:
        return {"Referer": "https://www.kuaishou.com/"}
    if "xiaohongshu" in u or "xhscdn" in u or "rednote" in u:
        return {"Referer": "https://www.xiaohongshu.com/"}
    return {}


class _CoverSignals(QObject):
    loaded = Signal(str, QPixmap)
    failed = Signal(str)


class _CoverTask(QRunnable):
    def __init__(self, url: str, signals: _CoverSignals):
        super().__init__()
        self.url = url
        self.signals = signals
        self.setAutoDelete(True)

    def run(self):
        try:
            from curl_cffi import requests as cffi_requests
            h = _cover_headers(self.url)
            h["User-Agent"] = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
            )
            r = cffi_requests.get(
                self.url, headers=h, timeout=12, impersonate="chrome146",
                allow_redirects=True,
            )
            if r.status_code == 200 and r.content:
                img = QImage.fromData(r.content)
                if not img.isNull():
                    self._emit("loaded", self.url, QPixmap.fromImage(img))
                    return
            self._emit("failed", self.url)
        except Exception:
            self._emit("failed", self.url)

    def _emit(self, kind: str, *args):
        # 程序退出时信号源可能已销毁，安全忽略避免后台线程报错
        try:
            getattr(self.signals, kind).emit(*args)
        except RuntimeError:
            pass


class CoverLoader(QObject):
    """全局单例：请求封面 → 后台下载 → 发出 cover_ready(url, pixmap) 信号。"""

    cover_ready = Signal(str, QPixmap)

    _instance: "CoverLoader | None" = None

    def __init__(self):
        super().__init__()
        self._pool = QThreadPool()
        self._pool.setMaxThreadCount(4)
        self._cache: dict[str, QPixmap] = {}
        self._failed: set[str] = set()
        self._pending: set[str] = set()
        self._signals = _CoverSignals()
        self._signals.loaded.connect(self._on_loaded)
        self._signals.failed.connect(self._on_failed)

    @classmethod
    def instance(cls) -> "CoverLoader":
        if cls._instance is None:
            cls._instance = CoverLoader()
        return cls._instance

    def request(self, url: str) -> QPixmap | None:
        """请求封面。

        若已缓存则立即返回 QPixmap；否则后台下载并在完成后发 cover_ready 信号，
        等待期间返回 None。
        """
        if not url:
            return None
        # 修正 http → https，部分 CDN 只允许 https
        if url.startswith("http://"):
            url = "https://" + url[len("http://"):]
        if url in self._cache:
            return self._cache[url]
        if url in self._failed:
            return None
        if url not in self._pending:
            self._pending.add(url)
            self._pool.start(_CoverTask(url, self._signals))
        return None

    def _on_loaded(self, url: str, pixmap: QPixmap):
        self._pending.discard(url)
        self._cache[url] = pixmap
        self.cover_ready.emit(url, pixmap)

    def _on_failed(self, url: str):
        self._pending.discard(url)
        self._failed.add(url)
