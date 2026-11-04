"""平台总线 —— 注册、发现、调度。所有 UI 的唯一入口。"""
from __future__ import annotations

import inspect
import time
from abc import ABC
from dataclasses import dataclass, field
from pathlib import Path

__all__ = ["FeatureResult", "FeatureMeta", "PlatformOps", "PlatformBus"]


@dataclass
class FeatureResult:
    """所有功能的统一返回。UI 只需要理解这一个结构。"""
    success: bool
    message: str
    data: list[dict] | None = None
    log: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    # "batch" = 批量预览：data 为待选条目（含 work_id/title/cover 等），
    # UI 弹出选择框让用户勾选后，带 selected 再次执行同一功能。
    preview: str = ""


@dataclass(frozen=True)
class FeatureMeta:
    """单个功能的描述。UI 用此渲染菜单。

    Attributes:
        id:              功能标识 (方法名 _do_<id>)。
        name:            中文显示名。
        need_url:        是否需要输入链接。
        emits_work_info: 结果 data[0] 是否为单作品数据 (UI 据此更新作品
                         资料卡, 取代 UI 侧硬编码功能名单)。
        group:           功能分组标签 (UI 按组渲染: work/user/platform)。
    """
    id: str
    name: str
    need_url: bool
    emits_work_info: bool = False
    group: str = "platform"   # work / user / platform


class PlatformOps(ABC):
    """平台操作表接口。每个平台继承并实现 _do_xxx。"""
    platform_id: str = ""
    display_name: str = ""
    cookie_hint: str = ""
    features: list[FeatureMeta] = []

    _on_log = None
    task_key = ""  # 当前功能执行的唯一标识 (FileDownloader 队列注册用)

    async def execute(self, feature_id: str, url: str,
                      cookie: str, save_dir: Path,
                      on_log=None, selected: list[str] | None = None,
                      stop_event=None, task_key: str = "") -> FeatureResult:
        self._on_log = on_log
        self.task_key = task_key
        method = getattr(self, f"_do_{feature_id}", None)
        if method is None:
            return FeatureResult(False, f"功能 {feature_id} 未实现")
        # 透传 stop_event/selected/task_key（仅当 _do_xxx 声明了该参数）
        try:
            params = inspect.signature(method).parameters
        except (TypeError, ValueError):
            params = {}
        kwargs = {}
        if stop_event is not None and "stop_event" in params:
            kwargs["stop_event"] = stop_event
        if selected is not None and "selected" in params:
            kwargs["selected"] = selected
        if task_key and "task_key" in params:
            kwargs["task_key"] = task_key
        if kwargs:
            return await method(url, cookie, save_dir, **kwargs)
        return await method(url, cookie, save_dir)

    def log(self, msg: str):
        """实时推送日志行。"""
        if self._on_log:
            self._on_log(msg)

    # ==================== 批量列表缓存 ====================
    # 预览→选择→下载 是两阶段流程, 缓存作品列表避免二次翻页。
    _CACHE_TTL = 1800  # 秒

    def _cache_get(self, key: str):
        """读取缓存的列表; 过期或不存在返回 None。"""
        ent = getattr(self, "_list_cache", {}).get(key)
        if ent and time.time() - ent[0] < self._CACHE_TTL:
            return ent[1]
        return None

    def _cache_put(self, key: str, items: list):
        """写入列表缓存 (带时间戳)。"""
        if not hasattr(self, "_list_cache"):
            self._list_cache = {}
        self._list_cache[key] = (time.time(), items)

    # ==================== 下载记录 (GUI/TUI 共用) ====================

    def _record_history(self, work: dict, file_path: str = "",
                        log: list | None = None) -> None:
        """下载成功后写入全局下载记录。

        work: 任意平台作品 dict (兼容 norm_work 或原始结构)。
        失败静默 (记录不影响下载主流程)。
        """
        try:
            from .download_history import get_history
            get_history().add(
                platform=work.get("platform") or self.platform_id,
                work_id=str(work.get("work_id")
                             or work.get("aweme_id")
                             or work.get("id") or ""),
                title=work.get("title") or work.get("desc")
                      or work.get("caption") or "",
                author_name=work.get("author_name", ""),
                author_home=self._author_home(work),
                share_url=work.get("share_url") or work.get("video_url") or "",
                publish_date=self._publish_date(work),
                file_path=file_path,
                log=log or [],
            )
        except Exception:
            pass

    def _author_home(self, work: dict) -> str:
        """作者主页链接 (有 sec_user_id/user_id 时拼接)。"""
        from .download_history import DownloadHistory
        aid = (work.get("sec_user_id") or work.get("author_id")
               or work.get("uid") or "")
        return DownloadHistory.author_home_of(self.platform_id, aid)

    @staticmethod
    def _publish_date(work: dict) -> str:
        """发布日期 (create_time/publish_time 时间戳 → 字符串)。"""
        from .download_history import DownloadHistory
        ts = (work.get("create_time") or work.get("publish_time")
              or work.get("create_timestamp") or 0)
        return DownloadHistory.format_date(ts)

    def stopped(self) -> bool:
        """任务是否已被 UI 停止 (批量循环据此提前退出)。

        每个文件新建 FileDownloader 时都注册到 DownloadQueue, 停止信号
        跨实例可见; 此方法供循环体在每轮开始前快速判断。
        """
        if not self.task_key:
            return False
        try:
            from .queue import get_queue
            return get_queue().is_task_stopped(self.task_key)
        except Exception:
            return False


class PlatformBus:
    """平台总线 — 全局单例。"""
    _registry: dict[str, PlatformOps] = {}

    @classmethod
    def register(cls, ops: PlatformOps):
        cls._registry[ops.platform_id] = ops

    @classmethod
    def get_ops(cls, platform: str) -> PlatformOps | None:
        return cls._registry.get(platform)

    @classmethod
    def list_platforms(cls) -> list[str]:
        return list(cls._registry.keys())

    @classmethod
    def display_name_of(cls, platform: str) -> str:
        ops = cls._registry.get(platform)
        return ops.display_name if ops else platform

    @classmethod
    def get_feature(cls, platform: str, feature_id: str) -> FeatureMeta | None:
        """按 id 查找单个功能元数据。"""
        for f in cls.get_features(platform):
            if f.id == feature_id:
                return f
        return None

    @classmethod
    def get_features(cls, platform: str) -> list[FeatureMeta]:
        ops = cls._registry.get(platform)
        return list(ops.features) if ops else []

    @classmethod
    def get_all_features(cls) -> dict[str, list[FeatureMeta]]:
        return {pid: list(o.features) for pid, o in cls._registry.items()}

    @classmethod
    def get_cookie_hints(cls) -> dict[str, str]:
        return {pid: ops.cookie_hint for pid, ops in cls._registry.items()}

    @classmethod
    async def run(cls, platform: str, feature_id: str,
                  url: str, cookie: str, save_dir: Path,
                  on_log=None, selected: list[str] | None = None,
                  stop_event=None, task_key: str = "") -> FeatureResult:
        ops = cls._registry.get(platform)
        if ops is None:
            return FeatureResult(False, f"平台 {platform} 未注册")
        return await ops.execute(feature_id, url, cookie, save_dir,
                                 on_log=on_log, selected=selected,
                                 stop_event=stop_event, task_key=task_key)
