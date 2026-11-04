"""日志面板 —— 只读日志条 (下载进度条)。

样式由主题 QSS 提供 (`#LogPanel` / `#LogPanelTitle` / `#DownloadProgress`),
组件内不写死颜色, 暗/亮主题切换与字号缩放均可生效。
外层已有「执行日志」标题。
"""
from __future__ import annotations

import html

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QProgressBar,
    QTextEdit, QVBoxLayout,
)


class LogPanel(QFrame):
    """日志显示 (下载进度条), 高度可随容器伸缩。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("LogPanel")
        self.setMinimumHeight(96)

        v = QVBoxLayout(self)
        v.setContentsMargins(10, 6, 10, 8)
        v.setSpacing(4)

        # ---- 顶部工具行: 可选标题 + 右侧按钮 ----
        hdr = QHBoxLayout()
        hdr.setSpacing(6)
        self._title = QLabel("")
        self._title.setObjectName("LogPanelTitle")
        self._title.setVisible(False)
        hdr.addWidget(self._title)
        hdr.addStretch()
        v.addLayout(hdr)

        # ---- 进度条 (下载进度, 空闲时隐藏) ----
        self._progress = QProgressBar()
        self._progress.setObjectName("DownloadProgress")
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(True)
        self._progress.setFormat("下载 %p%")
        self._progress.setFixedHeight(16)
        self._progress.setVisible(False)
        v.addWidget(self._progress)

        # ---- 日志文本 ----
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setTextInteractionFlags(Qt.TextSelectableByMouse)
        v.addWidget(self._log, 1)

        # 进度节流: 200ms 内不重复刷新
        self._last_prog_at = 0.0

    # ===== 主题感知的文字颜色 =====
    @staticmethod
    def _default_color() -> str:
        app = QApplication.instance()
        theme = (app.property("theme") if app is not None else "") or "dark"
        return "#e2e8f0" if theme == "dark" else "#0f172a"

    # ===== 公开 API =====

    def set_title(self, text: str):
        """可选: 面板内部显示标题 (默认隐藏, 由外层 SectionPanel 承担)。"""
        self._title.setText(text)
        self._title.setVisible(bool(text))

    def append(self, text: str, color: str | None = None):
        text = html.escape(str(text))  # 防日志含 <> 破坏渲染
        color = color or self._default_color()
        self._log.append(f'<span style="color:{color}">{text}</span>')
        sb = self._log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def set_progress(self, current: int, total: int):
        """更新下载进度条 (0,0 = 隐藏)。"""
        import time
        if total <= 0:
            self._progress.setVisible(False)
            return
        self._progress.setVisible(True)
        pct = min(100, int(current * 100 / total))
        now = time.monotonic()
        if pct >= 100 or now - self._last_prog_at > 0.2:
            self._progress.setValue(pct)
            self._last_prog_at = now
        if pct >= 100:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(1500, lambda: self._progress.setVisible(False))

    def clear(self):
        self._log.clear()
        self._progress.setVisible(False)
        self._progress.setValue(0)

    def append_files(self, files: list[str]):
        if not files:
            return
        self.append(f"✓ 下载完成: {len(files)} 个文件", "#22c55e")
        for f in files:
            self.append(f"  • {f}", "#94a3b8")

    def append_data(self, data: list):
        if not data:
            return
        self.append(f"✓ 采集完成: {len(data)} 条数据", "#22c55e")
        for i, d in enumerate(data[:50], 1):
            self.append(f"  {i}. {d}", "#94a3b8")
        if len(data) > 50:
            self.append(f"  ... (剩余 {len(data) - 50} 条)", "#64748b")

    def set_result(self, result: dict):
        success = result.get("success", False)
        msg = result.get("message", "")
        self.append(f"✓ {msg}" if success else f"✗ {msg}",
                    "#22c55e" if success else "#ef4444")
        # 日志行已由 worker 经 log_line 实时/补发推送, 此处不再重放 (避免重复)
        files = result.get("files") or []
        if files:
            self.append_files(files)
        data = result.get("data")
        if isinstance(data, list) and data and not files:
            self.append_data(data)
        self._progress.setVisible(False)

    def set_expanded(self, v: bool):
        """兼容旧 API (不再支持折叠, 保留方法)。"""
        pass
