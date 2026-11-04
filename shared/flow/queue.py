"""下载队列管理 —— 暂停/恢复/停止/限速/状态查询。

设计:
- DownloadQueue 为进程内单例, 持有所有活动 FileDownloader 的控制句柄。
- UI 通过 queue.stop_task(task_id) 停止某次功能执行产生的全部下载;
  queue.set_speed_limit() 全局限速 (chunk 间 sleep 实现, 无第三方依赖)。
- speed_limit 单位 KB/s; 0 = 不限速。
"""
from __future__ import annotations

import threading
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
        return bool(self.stop_flag and self.stop_flag.is_set())


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
                inst._stopped_tasks = set()  # 已停止的 task_key (批量循环据此退出)
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
            self._stopped_tasks.add(str(task_id))
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

    def is_task_stopped(self, task_id: str) -> bool:
        """本任务是否已被停止 (批量下载中每个文件新建下载器, 也应立即退出)。"""
        with self._lock:
            return str(task_id) in self._stopped_tasks

    def clear_task(self, task_id: str) -> None:
        """任务结束: 清除停止标记并移除遗留句柄 (下次执行不受影响)。"""
        with self._lock:
            self._stopped_tasks.discard(str(task_id))
            for k in [k for k in self._handles
                      if str(k).startswith(str(task_id))]:
                self._handles.pop(k, None)

    def has_stopped(self) -> bool:
        """是否存在被停止的活动句柄 (批量循环据此提前退出)。

        批量下载中每个文件可能新建 FileDownloader, 但停止信号打在
        DownloadQueue 句柄上, 跨实例可见; 句柄注销后不再计入, 因此
        不会误判历史任务。
        """
        with self._lock:
            return any(h.stopped for h in self._handles.values())

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


def get_queue() -> DownloadQueue:
    """获取全局队列单例。"""
    return DownloadQueue()
