"""封面加载器 — 使用 curl_cffi 后台下载封面图（兼容 PyInstaller，带缓存）。

Qt 的 QNetworkAccessManager 在 PyInstaller 冻结包中常因缺少 SSL 证书或
TLS 指纹被 CDN 拒绝而失败。这里统一改用项目已有的 curl_cffi（支持浏览器
指纹模拟），通过线程池后台下载，主线程只接收信号更新 UI。

关键约束（曾导致"封面/头像随机不显示"）：
1. QPixmap 只能在 GUI 线程创建。后台线程一律传 QImage，
   由 GUI 线程的槽转换为 QPixmap。
2. 跨线程信号要求接收方对象所属线程有事件循环。这里强制把内部
   信号对象移动到 QApplication 主线程，避免单例在后台线程被首次创建时
   （如批量任务里）槽函数永远得不到执行。
"""
from __future__ import annotations

import time

from PySide6.QtCore import QCoreApplication, QObject, QRunnable, QThreadPool, Signal
from PySide6.QtGui import QImage, QPixmap

__all__ = ["CoverLoader"]

# 浏览器指纹候选：不同 curl_cffi 版本支持的档位不同，
# 逐个尝试，全部失败时退回不模拟指纹的普通请求。
_IMPERSONATE_CANDIDATES = ("chrome146", "chrome136", "chrome124", "chrome120", "")

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36")


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
    # 后台线程只传 QImage: QPixmap 必须在 GUI 线程创建,
    # 否则 Qt 拒绝绘制 (表现为封面/头像不显示)。
    loaded = Signal(str, QImage)
    failed = Signal(str, str)   # (url, 失败原因)


def _download(url: str) -> tuple[QImage | None, str]:
    """后台下载图片，返回 (QImage 或 None, 失败原因)。"""
    from curl_cffi import requests as cffi_requests

    h = _cover_headers(url)
    h["User-Agent"] = _UA
    last_err = ""
    for imp in _IMPERSONATE_CANDIDATES:
        try:
            kwargs = {
                "headers": h,
                "timeout": 15,
                "allow_redirects": True,
            }
            if imp:
                kwargs["impersonate"] = imp
            r = cffi_requests.get(url, **kwargs)
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
            continue
        if r.status_code != 200:
            last_err = f"HTTP {r.status_code}"
            continue
        if not r.content:
            last_err = "响应为空"
            continue
        img = QImage.fromData(bytes(r.content))
        if img.isNull():
            last_err = "图片数据无法解码"
            continue
        return img, ""
    return None, last_err or "未知错误"


class _CoverTask(QRunnable):

    def __init__(self, url: str, signals: _CoverSignals):
        super().__init__()
        self.url = url
        self.signals = signals
        self.setAutoDelete(False)

    def run(self):
        try:
            image, err = _download(self.url)
        except Exception as e:      # 兜底：任何异常都不让线程崩溃
            image, err = None, f"{type(e).__name__}: {e}"
        if image is not None and not image.isNull():
            self._emit("loaded", self.url, image)
        else:
            self._emit("failed", self.url, err or "下载失败")

    def _emit(self, kind: str, *args):
        # 程序退出时信号源可能已销毁，安全忽略避免后台线程报错
        try:
            getattr(self.signals, kind).emit(*args)
        except RuntimeError:
            pass


class CoverLoader(QObject):
    """全局单例：请求封面 → 后台下载 → 发出 cover_ready(url, pixmap) 信号。"""

    cover_ready = Signal(str, QPixmap)
    cover_failed = Signal(str, str)   # (url, 原因) 供日志面板展示

    _instance: "CoverLoader | None" = None

    # 同一 URL 的最多尝试次数（失败后隔一段时间可再次尝试）
    MAX_RETRY = 3
    # 失败冷却时间（秒）：超过后可重新发起，避免瞬时故障导致本次会话永久无图
    RETRY_COOLDOWN = 20.0

    def __init__(self):
        super().__init__()
        self._pool = QThreadPool()
        self._pool.setMaxThreadCount(4)
        self._cache: dict[str, QPixmap] = {}
        self._retry: dict[str, int] = {}        # url → 尝试次数
        self._failed_at: dict[str, float] = {}  # url → 最后一次失败时间
        self._pending: set[str] = set()
        self._signals = _CoverSignals()
        self._signals.loaded.connect(self._on_loaded)
        self._signals.failed.connect(self._on_failed)
        # 关键：确保信号对象与自身都归属 GUI 主线程的事件循环。
        # 若单例是在后台线程首次创建，槽函数将永远收不到信号。
        app = QCoreApplication.instance()
        if app is not None:
            self._signals.moveToThread(app.thread())
            self.moveToThread(app.thread())

    @classmethod
    def instance(cls) -> "CoverLoader":
        if cls._instance is None:
            cls._instance = CoverLoader()
        return cls._instance

    @staticmethod
    def normalize_url(url: str) -> str:
        """统一图片 URL（http → https，部分 CDN 仅允许 https）。

        调用方在保存/比对 URL 时也必须使用此结果，确保与 cover_ready 信号携带的
        URL 一致；否则异步回调会因 URL 不等而丢弃图片（头像/封面不显示）。
        """
        if not url:
            return ""
        if url.startswith("http://"):
            return "https://" + url[len("http://"):]
        return url

    def invalidate(self, url: str):
        """清除某 URL 的失败计数（重新解析同一作品时调用，允许再次尝试）。"""
        u = self.normalize_url(url)
        if not u:
            return
        self._retry.pop(u, None)
        self._failed_at.pop(u, None)

    @classmethod
    def cached(cls, url: str) -> QPixmap | None:
        """只查缓存，不触发下载（类方法，可在任意控件里直接调用）。"""
        if not url:
            return None
        return cls.instance()._cache.get(cls.normalize_url(url))

    def request(self, url: str) -> QPixmap | None:
        """请求封面。

        若已缓存则立即返回 QPixmap；否则后台下载并在完成后发 cover_ready 信号，
        等待期间返回 None。
        """
        if not url:
            return None
        url = self.normalize_url(url)
        if url in self._cache:
            return self._cache[url]
        if url in self._pending:
            return None
        attempts = self._retry.get(url, 0)
        if attempts >= self.MAX_RETRY:
            # 冷却期过后允许再试，避免一次网络抖动导致整个会话都没有图
            failed_at = self._failed_at.get(url, 0.0)
            if time.time() - failed_at < self.RETRY_COOLDOWN:
                return None
            self._retry[url] = 0
        self._pending.add(url)
        self._pool.start(_CoverTask(url, self._signals))
        return None

    def _on_loaded(self, url: str, image: QImage):
        # 本槽运行在 GUI 线程 (跨线程信号自动排队), 此处才可安全创建 QPixmap
        self._pending.discard(url)
        self._retry.pop(url, None)
        self._failed_at.pop(url, None)
        if image is None or image.isNull():
            self.cover_failed.emit(url, "图片为空")
            return
        pixmap = QPixmap.fromImage(image)
        self._cache[url] = pixmap
        self.cover_ready.emit(url, pixmap)

    def _on_failed(self, url: str, reason: str):
        self._pending.discard(url)
        self._retry[url] = self._retry.get(url, 0) + 1
        self._failed_at[url] = time.time()
        # 上报失败原因，便于日志定位（例如指纹不受支持 / CDN 拒绝）
        try:
            self.cover_failed.emit(url, reason)
        except RuntimeError:
            pass
