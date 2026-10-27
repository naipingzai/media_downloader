"""FeatureWorker - 后台执行线程，调用 PlatformBus。"""
from __future__ import annotations

import asyncio
import threading
import uuid
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Signal


class WorkerSignals(QObject):
    log_line = Signal(str)
    work_info = Signal(dict)
    progress = Signal(int, int)
    finished = Signal(dict)
    error = Signal(str)


class FeatureWorker(QRunnable):
    def __init__(self, platform, feature_id, url, cookie, save_dir, selected=None):
        super().__init__()
        self.platform = platform
        self.feature_id = feature_id
        self.url = url
        self.cookie = cookie
        self.save_dir = Path(save_dir)
        self.selected = selected  # 批量预览后用户勾选的 work_id 列表
        self.signals = WorkerSignals()
        self.stop_event = threading.Event()  # 用于通知录制停止
        # 任务唯一标识: FileDownloader 以此注册到 DownloadQueue,
        # UI 停止按钮 → stop() → 队列按 task_key 前缀停止所有下载
        self.task_key = f"{platform}:{feature_id}:{uuid.uuid4().hex[:8]}"
        self.setAutoDelete(True)

    def stop(self):
        """外部调用：通知录制停止 + 停止队列中本任务的下载。"""
        self.stop_event.set()
        try:
            from shared.flow.queue import get_queue
            get_queue().stop_task(self.task_key)
        except Exception:
            pass

    def run(self):
        from shared.core.logger import get_logger
        from shared.core.ops import PlatformBus
        log = get_logger("gui.worker")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        def _emit_log(msg):
            try:
                self.signals.log_line.emit(str(msg))
            except Exception:
                pass

        try:
            result = loop.run_until_complete(
                PlatformBus.run(self.platform, self.feature_id,
                                self.url, self.cookie, self.save_dir,
                                on_log=_emit_log, selected=self.selected,
                                stop_event=self.stop_event,
                                task_key=self.task_key)
            )
            # emit remaining log lines that weren't streamed
            for line in result.log:
                self.signals.log_line.emit(line)
            # 是否更新作品资料卡: 由 FeatureMeta.emits_work_info 声明驱动
            # (UI 零硬编码功能名单; 批量预览 data 是待选列表, 不作单作品资料)
            meta = PlatformBus.get_feature(self.platform, self.feature_id)
            emits_work_info = bool(meta and meta.emits_work_info)
            if (result.data and len(result.data) > 0
                    and emits_work_info
                    and not result.preview):
                self.signals.work_info.emit(result.data[0])
            self.signals.finished.emit({
                "success": result.success,
                "message": result.message,
                "data": result.data,
                "files": result.files,
                "log": result.log,
                "preview": result.preview,
            })
        except Exception as e:
            log.exception("功能执行异常: %s/%s", self.platform, self.feature_id)
            self.signals.error.emit(str(e))
        finally:
            # 注销本任务在队列中的句柄
            try:
                from shared.flow.queue import get_queue
                get_queue().stop_task(self.task_key)  # 置停止, 防悬挂
                q = get_queue()
                with q._lock:
                    for k in [k for k in q._handles
                              if str(k).startswith(self.task_key)]:
                        q._handles.pop(k, None)
            except Exception:
                pass
            loop.close()
