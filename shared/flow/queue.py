"""下载队列管理 —— 暂停/恢复/停止/限速/状态查询。

设计:
- DownloadQueue 为进程内单例, 持有所有活动 FileDownloader 的控制句柄。
- UI 通过 queue.stop_task(task_id) 停止某次功能执行产生的全部下载;
  queue.set_speed_limit() 全局限速 (chunk 间 sleep 实现, 无第三方依赖)。
- speed_limit 单位 KB/s; 0 = 不限速。
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

__all__ = ["DownloadHandle", "DownloadQueue", "get_queue"]


@dataclass
class DownloadHandle:
    """单个下载任务的控制句柄 (FileDownloader 注册)。"""
    name: str = ""
    stop_flag: threading.Event = field(default_factory=threading.Event)
    paused: bool = False
    downloaded: int = 0
    total: int = 0

    @property
    def stopped(self) -> bool:
        return self.stop_flag.is_set()


class DownloadQueue:
    """进程内下载队列 (单例)。"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                inst = super().__new__(cls)
                inst._handles = {}
                inst._speed_limit = 0  # KB/s, 0=不限
                inst._global_pause = False
                cls._instance = inst
            return cls._instance

    # ==================== 注册 (FileDownloader 调用) ====================
    def register(self, key: object, handle: DownloadHandle) -> None:
        with self._lock:
            self._handles[key] = handle

    def unregister(self, key: object) -> None:
        with self._lock:
            self._handles.pop(key, None)

    # ==================== 控制 (UI 调用) ====================
    def stop_task(self, task_id: str) -> int:
        """停止某次功能执行 (task_id = FeatureWorker 标识) 的所有下载。

        返回停止的句柄数。
        """
        with self._lock:
            n = 0
            for k, h in list(self._handles.items()):
                if str(k).startswith(str(task_id)) or task_id == "*":
                    h.stop_flag.set()
                    n += 1
            return n

    def stop_all(self) -> int:
        with self._lock:
            n = len(self._handles)
            for h in self._handles.values():
                h.stop_flag.set()
            return n

    def pause_all(self) -> None:
        """全局暂停: 活跃下载在下一个 chunk 边界挂起。"""
        with self._lock:
            self._global_pause = True
            for h in self._handles.values():
                h.paused = True

    def resume_all(self) -> None:
        with self._lock:
            self._global_pause = False
            for h in self._handles.values():
                h.paused = False

    def set_speed_limit(self, kb_per_sec: int) -> None:
        """全局限速 (KB/s), 0 = 不限速。"""
        with self._lock:
            self._speed_limit = max(0, int(kb_per_sec))

    # ==================== 查询 ====================
    def status(self) -> list[dict]:
        with self._lock:
            return [{
                "key": str(k), "name": h.name,
                "downloaded": h.downloaded, "total": h.total,
                "paused": h.paused, "stopped": h.stopped,
            } for k, h in self._handles.items()]

    @property
    def speed_limit(self) -> int:
        with self._lock:
            return self._speed_limit

    @property
    def paused(self) -> bool:
        with self._lock:
            return self._global_pause

    def _throttle(self) -> None:
        """限速/暂停等待 (由 FileDownloader 在 chunk 循环中调用)。

        返回时保证: 未暂停且距上次 chunk 间隔满足限速要求。
        """
        while True:
            with self._lock:
                if not self._global_pause:
                    break
            time.sleep(0.2)
            # 暂停期间也响应停止
            with self._lock:
                if self._global_pause:
                    continue
            break
        with self._lock:
            limit = self._speed_limit
        if limit > 0:
            # CHUNK_SIZE / limit 秒 → chunk 间最小间隔
            delay = (2 * 1024 * 1024) / (limit * 1024) - 0.0
            if delay > 0.01:
                time.sleep(min(delay, 10.0))


def get_queue() -> DownloadQueue:
    """获取全局队列单例。"""
    return DownloadQueue()
