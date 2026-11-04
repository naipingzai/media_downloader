"""下载任务管理面板 —— 实时进度 / 暂停继续 / 限速 / 单任务停止。

数据源: shared.flow.queue.DownloadQueue (GUI/TUI 共用单例),
每秒由 main_window 的队列定时器驱动刷新 (TaskPanel 自带 QTimer 亦可)。
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QHeaderView, QLabel, QPushButton,
    QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout,
)


def _fmt_mb(n: int) -> str:
    try:
        n = int(n or 0)
    except (TypeError, ValueError):
        n = 0
    mb = n / (1024 * 1024)
    if mb >= 1024:
        return f"{mb / 1024:.2f} GB"
    if mb >= 1:
        return f"{mb:.1f} MB"
    return f"{n / 1024:.0f} KB"


class TaskPanel(QFrame):
    """下载任务表格 + 队列控制 (暂停/继续/限速/全部停止)。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TaskPanel")
        self._paused = False
        v = QVBoxLayout(self)
        v.setContentsMargins(8, 6, 8, 6)
        v.setSpacing(6)

        # ---- 标题行: 标题 + 暂停全部 + 限速 + 全部停止 ----
        head = QHBoxLayout()
        head.setSpacing(8)
        title = QLabel("下载任务")
        title.setObjectName("TaskPanelTitle")
        head.addWidget(title)
        head.addStretch()
        self._pause_btn = QPushButton("⏸ 暂停全部")
        self._pause_btn.setObjectName("PageGhostButton")
        self._pause_btn.setCursor(Qt.PointingHandCursor)
        self._pause_btn.clicked.connect(self._toggle_pause)
        head.addWidget(self._pause_btn)
        lim_lab = QLabel("限速 KB/s")
        lim_lab.setObjectName("DialogSub")
        head.addWidget(lim_lab)
        self._limit_spin = QSpinBox()
        self._limit_spin.setRange(0, 1024 * 1024)
        self._limit_spin.setValue(0)
        self._limit_spin.setSpecialValueText("不限")
        self._limit_spin.setToolTip("0 = 不限速; 需任务重启后生效")
        self._limit_spin.valueChanged.connect(self._on_limit)
        head.addWidget(self._limit_spin)
        stop_all = QPushButton("全部停止")
        stop_all.setObjectName("PageGhostButton")
        stop_all.setCursor(Qt.PointingHandCursor)
        stop_all.clicked.connect(self._on_stop_all)
        head.addWidget(stop_all)
        v.addLayout(head)

        # ---- 任务表格: 任务/进度/已下载/大小/状态 ----
        self._table = QTableWidget(0, 5)
        self._table.setObjectName("TaskTable")
        self._table.setHorizontalHeaderLabels(
            ["任务", "进度", "已下载", "大小", "状态"])
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionMode(QTableWidget.NoSelection)
        self._table.setFocusPolicy(Qt.NoFocus)
        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        for col in (1, 2, 3, 4):
            hh.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        self._table.verticalHeader().setDefaultSectionSize(24)
        v.addWidget(self._table)

        self._empty = QLabel("暂无下载任务")
        self._empty.setObjectName("EmptyState")
        self._empty.setAlignment(Qt.AlignCenter)
        self._empty.setVisible(False)
        v.addWidget(self._empty)

        # 自动刷新
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(1000)
        self.refresh()

    # ================= 队列操作 =================

    def _toggle_pause(self):
        from shared.flow.queue import get_queue
        q = get_queue()
        if self._paused:
            q.resume_all()
            self._paused = False
            self._pause_btn.setText("⏸ 暂停全部")
        else:
            q.pause_all()
            self._paused = True
            self._pause_btn.setText("▶ 继续全部")
        self.refresh()

    def _on_limit(self, val: int):
        from shared.flow.queue import get_queue
        get_queue().set_speed_limit(val)

    def _on_stop_all(self):
        from shared.flow.queue import get_queue
        get_queue().stop_all()

    # ================= 刷新 =================

    def refresh(self):
        """从 DownloadQueue 拉状态并渲染表格。"""
        try:
            from shared.flow.queue import get_queue
            st = get_queue().status()
        except Exception:
            return
        rows = [(s.get("name", "?"), s.get("downloaded", 0),
                 s.get("total", 0)) for s in st]
        self._table.setRowCount(len(rows))
        for r, (name, done, total) in enumerate(rows):
            name_it = QTableWidgetItem(str(name)[:40])
            name_it.setTextAlignment(
                Qt.AlignLeft | Qt.AlignVCenter)
            self._table.setItem(r, 0, name_it)
            if total > 0:
                pct = min(100, int(done * 100 / total))
                pct_it = QTableWidgetItem(f"{pct}%")
            else:
                pct_it = QTableWidgetItem("—")
            pct_it.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(r, 1, pct_it)
            done_it = QTableWidgetItem(_fmt_mb(done))
            done_it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._table.setItem(r, 2, done_it)
            size_it = QTableWidgetItem(
                _fmt_mb(total) if total > 0 else "—")
            size_it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._table.setItem(r, 3, size_it)
            if total > 0 and done >= total > 0:
                state = "✓ 已完成"
            elif self._paused:
                state = "⏸ 已暂停"
            else:
                state = "↓ 下载中"
            st_it = QTableWidgetItem(state)
            st_it.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(r, 4, st_it)
        empty = not rows
        self._table.setVisible(not empty)
        self._empty.setVisible(empty)
