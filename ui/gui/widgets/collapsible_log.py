"""可折叠日志条 — 内嵌主窗口底部 (替代 LogDialog 弹窗)。

折叠态: 一行 (▸ 日志 + 最新一条日志摘要 + 清除按钮)
展开态: 5 行滚动日志 (▾ 日志 + 清除按钮)
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout,
)


class CollapsibleLog(QFrame):
    """可折叠日志条。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CollapsibleLog")
        self._expanded = False
        self._last_line = ""
        self.setStyleSheet(
            "#CollapsibleLog { background: #0f172a; border: 1px solid #334155;"
            " border-radius: 6px; }")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 4, 10, 6)
        outer.setSpacing(4)

        # ===== 标题行 =====
        hdr = QHBoxLayout()
        hdr.setSpacing(8)
        self._toggle_btn = QPushButton("▸ 日志")
        self._toggle_btn.setCursor(Qt.PointingHandCursor)
        self._toggle_btn.setToolTip("点击展开/折叠日志")
        self._toggle_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #94a3b8;"
            " border: none; padding: 4px 6px; font-size: 14px; font-weight: bold; }"
            "QPushButton:hover { color: #e2e8f0; }")
        self._toggle_btn.clicked.connect(self.toggle)
        hdr.addWidget(self._toggle_btn)

        self._summary = QLabel("")
        self._summary.setStyleSheet(
            "color: #64748b; font-size: 12px;"
            " background: transparent; border: none;")
        self._summary.setToolTip("最新一条日志 (点击展开查看全部)")
        self._summary.setCursor(Qt.PointingHandCursor)
        self._summary.mousePressEvent = lambda ev: self.toggle()
        hdr.addWidget(self._summary, 1)

        clear_btn = QPushButton("清除")
        clear_btn.setObjectName("SubtleButton")
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.setStyleSheet(
            "QPushButton { background: #334155; color: #e2e8f0; border: none;"
            " border-radius: 4px; padding: 3px 12px; font-size: 12px; }"
            "QPushButton:hover { background: #475569; }")
        clear_btn.clicked.connect(self.clear)
        hdr.addWidget(clear_btn)
        outer.addLayout(hdr)

        # ===== 日志正文 (默认折叠) =====
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setStyleSheet(
            "QTextEdit { background: transparent; color: #e2e8f0;"
            " font-family: monospace; font-size: 14px;"
            " border: none; padding: 2px; }")
        self._log.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._log.setVisible(False)
        outer.addWidget(self._log)

    # ===== 展开/折叠 =====
    def toggle(self):
        self.set_expanded(not self._expanded)

    def set_expanded(self, v: bool):
        self._expanded = bool(v)
        self._log.setVisible(self._expanded)
        self._toggle_btn.setText("▾ 日志" if self._expanded else "▸ 日志")
        # 展开时固定高度 (不挤压其他区域)
        self._log.setFixedHeight(150 if self._expanded else 0)

    # ===== 日志 API (与 LogPanel 兼容) =====
    def append(self, text: str, color: str = None):
        text = str(text)
        self._last_line = text
        self._summary.setText(text[:80])
        if color:
            self._log.append(f'<span style="color:{color}">{text}</span>')
        else:
            self._log.append(f'<span style="color:#e2e8f0">{text}</span>')
        # 自动滚到底部
        sb = self._log.verticalScrollBar()
        sb.setValue(sb.maximum())

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
        if success:
            self.append(f"✓ {msg}", "#22c55e")
        else:
            self.append(f"✗ {msg}", "#ef4444")
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

    def clear(self):
        self._log.clear()
        self._last_line = ""
        self._summary.setText("")
