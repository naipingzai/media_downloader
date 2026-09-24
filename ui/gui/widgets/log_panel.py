"""日志面板 —— 静态日志条 (固定高度, 不可折叠)。"""
from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QTextEdit, QVBoxLayout


class LogPanel(QFrame):
    """固定日志显示 (高度固定 ~140px, 不能折叠)。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("LogPanel")
        self.setFixedHeight(140)
        self.setStyleSheet(
            "#LogPanel { background: #0f172a;"
            " border: 1px solid #334155; border-radius: 6px; }")
        v = QVBoxLayout(self)
        v.setContentsMargins(10, 4, 10, 6)
        v.setSpacing(2)
        hdr = QHBoxLayout()
        hdr.setSpacing(6)
        title = QLabel("执行日志")
        title.setObjectName("LogPanelTitle")
        hdr.addWidget(title)
        hdr.addStretch()
        clear_btn = QLabel("(只读)")
        clear_btn.setObjectName("LogPanelHint")
        hdr.addWidget(clear_btn)
        v.addLayout(hdr)
        self._log = QTextEdit()
        # 允许复制/粘贴/全选 (用户可拖选复制, Ctrl+C/V)
        self._log.setReadOnly(False)        # 非只读 · 支持 Ctrl+C / Ctrl+V / Ctrl+A
        # 但监听外部系统节流 (避免第三方误改)
        self._log.setStyleSheet(
            "QTextEdit { background: transparent; color: #e2e8f0;"
            " font-family: monospace; font-size: 14px; border: none;"
            " selection-background-color: #475569;"
            " selection-color: #ffffff; }")
        v.addWidget(self._log)

    # ===== 公开 API =====
    def append(self, text: str, color: str | None = None):
        text = str(text)
        if color:
            self._log.append(f'<span style="color:{color}">{text}</span>')
        else:
            self._log.append(f'<span style="color:#e2e8f0">{text}</span>')
        sb = self._log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def clear(self):
        self._log.clear()

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

    def set_expanded(self, v: bool):
        """兼容旧 API (不再支持折叠, 保留方法)。"""
        pass
