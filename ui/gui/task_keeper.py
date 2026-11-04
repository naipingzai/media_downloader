"""后台任务生命周期管理 —— 修复 QRunnable + setAutoDelete 导致的段错误。

问题根因 (已用 diag_stress.py 压测复现, RC=139):
    QRunnable 子类若调用 setAutoDelete(True), QThreadPool 在 run() 结束后
    会 delete 掉 C++ 对象; 但 Python 侧的 wrapper 仍在, GC 回收时又 delete
    一次 → double-free → 段错误。快速连发任务 (如反复切换平台) 时必现。

正确做法:
    1. setAutoDelete(False) —— 让 Python 成为唯一所有者;
    2. 在任务完成前持有 Python 强引用, 完成后释放。
"""
from __future__ import annotations

from PySide6.QtCore import QObject

__all__ = ["TaskKeeper"]


class TaskKeeper(QObject):
    """持有后台任务的强引用, 直到其终止信号触发后释放。

    用法:
        keeper = TaskKeeper()
        task = SomeRunnable()
        keeper.keep(task, task.signals.done, task.signals.failed)
        pool.start(task)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._alive: dict[int, tuple] = {}   # id(task) -> (task, [unsub, ...])

    def keep(self, task, *end_signals) -> None:
        """持有 task 强引用, 任一 end_signals 触发后自动释放。

        task 必须先 setAutoDelete(False) (本方法会兜底设置)。
        """
        try:
            task.setAutoDelete(False)   # 关键: 禁止 QThreadPool 删除 C++ 对象
        except Exception:
            pass
        key = id(task)
        # 先占位, 防止信号在 keep() 返回前同步触发造成递归
        self._alive[key] = (task, [])

        def _release(*_args, **_kwargs):
            self._alive.pop(key, None)

        unsubs = []
        for sig in end_signals:
            if sig is None:
                continue
            try:
                sig.connect(_release)
                unsubs.append((sig, _release))
            except Exception:
                pass
        self._alive[key] = (task, unsubs)

    @property
    def alive_count(self) -> int:
        return len(self._alive)

    def clear(self) -> None:
        """丢弃全部强引用 (窗口关闭时调用)。"""
        self._alive.clear()
