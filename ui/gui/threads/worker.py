"""FeatureWorker - 后台执行线程，调用 PlatformBus。"""
import asyncio
from pathlib import Path
from PySide6.QtCore import QObject, QRunnable, Signal


class WorkerSignals(QObject):
    log_line = Signal(str)
    work_info = Signal(dict)
    progress = Signal(int, int)
    finished = Signal(dict)
    error = Signal(str)


class FeatureWorker(QRunnable):
    def __init__(self, platform, feature_id, url, cookie, save_dir):
        super().__init__()
        self.platform = platform
        self.feature_id = feature_id
        self.url = url
        self.cookie = cookie
        self.save_dir = Path(save_dir)
        self.signals = WorkerSignals()
        self.setAutoDelete(True)

    def run(self):
        from shared.core.ops import PlatformBus
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                PlatformBus.run(self.platform, self.feature_id,
                              self.url, self.cookie, self.save_dir)
            )
            for line in result.log:
                self.signals.log_line.emit(line)
            if result.data and len(result.data) > 0:
                self.signals.work_info.emit(result.data[0])
            self.signals.finished.emit({
                "success": result.success,
                "message": result.message,
                "data": result.data,
                "files": result.files,
                "log": result.log,
            })
        except Exception as e:
            self.signals.error.emit(str(e))
        finally:
            loop.close()
