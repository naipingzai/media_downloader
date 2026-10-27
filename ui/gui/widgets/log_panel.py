"""日志面板 —— 只读日志条 (可复制 / 可清空 / HTML 转义 / 下载进度条)。"""
from __future__ import annotations

import html

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton, QTextEdit,
    QVBoxLayout,
)


class LogPanel(QFrame):
    """固定日志显示 (高度固定, 只读可选复制, 支持清空 + 进度条)。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("LogPanel")
        self.setFixedHeight(168)
        v = QVBoxLayout(self)
        v.setContentsMargins(10, 4, 10, 6)
        v.setSpacing(2)
        hdr = QHBoxLayout()
        hdr.setSpacing(6)
        title = QLabel("执行日志")
        title.setObjectName("LogPanelTitle")
        hdr.addWidget(title)
        hdr.addStretch()
        for text, slot in (("清空", self.clear), ("复制全部", self._copy_all)):
            btn = QPushButton(text)
            btn.setObjectName("PageGhostButton")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(22)
            btn.clicked.connect(slot)
            hdr.addWidget(btn)
        v.addLayout(hdr)
        # 进度条 (下载进度, 空闲时隐藏)
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(True)
        self._progress.setFormat("下载 %p%")
        self._progress.setFixedHeight(16)
        self._progress.setVisible(False)
        self._progress.setStyleSheet(
            "QProgressBar { background: #0f172a; border: 1px solid #334155;"
            " border-radius: 4px; color: #e2e8f0; font-size: 11px;"
            " text-align: center; }"
            "QProgressBar::chunk { background: #38bdf8; border-radius: 3px; }")
        v.addWidget(self._progress)
        self._log = QTextEdit()
        # 只读: 防止用户误改日志; 仍支持选择复制
        self._log.setReadOnly(True)
        self._log.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._log.setStyleSheet(
            "QTextEdit { background: transparent; color: #e2e8f0;"
            " font-family: monospace; font-size: 14px; border: none;"
            " selection-background-color: #475569;"
            " selection-color: #ffffff; }")
        v.addWidget(self._log)
        # 进度节流: 200ms 内不重复刷新
        self._last_prog_at = 0.0

    # ===== 公开 API =====
    def append(self, text: str, color: str | None = None):
        text = html.escape(str(text))  # 防日志含 <> 破坏渲染
        if color:
            self._log.append(f'<span style="color:{color}">{text}</span>')
        else:
            self._log.append(f'<span style="color:#e2e8f0">{text}</span>')
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
            # 完成后短暂显示再隐藏
            from PySide6.QtCore import QTimer
            QTimer.singleShot(1500, lambda: self._progress.setVisible(False))

    def clear(self):
        self._log.clear()
        self._progress.setVisible(False)
        self._progress.setValue(0)

    def _copy_all(self):
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(self._log.toPlainText())

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
        for line in result.get("log", []):
            if "✓" in line:
                self.append(line, "#22c55e")
            elif "✗" in line or "失败" in line:
                self.append(line, "#ef4444")
            elif "⚠" in line:
                self.append(line, "#f59e0b")
            else:
                self.append(line)
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
