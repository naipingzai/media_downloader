"""执行日志输出。"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget


class ResultView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Panel")
        self.setAttribute(Qt.WA_StyledBackground, True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(0)

        # 标题栏 + 清除按钮
        hdr = QHBoxLayout()
        hdr.setContentsMargins(14, 10, 14, 4)
        hdr.setSpacing(6)
        title = QLabel("执行日志")
        title.setObjectName("SectionTitle")
        title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        hdr.addWidget(title)
        hdr.addStretch()
        clear_btn = QPushButton("清除")
        clear_btn.setObjectName("SubtleButton")
        clear_btn.clicked.connect(self.clear)
        hdr.addWidget(clear_btn)
        layout.addLayout(hdr)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMinimumHeight(0)
        self._log.setStyleSheet(
            "background: #0f172a; color: #e2e8f0; font-family: monospace; "
            "font-size: 12px; border: 1px solid #334155; border-radius: 4px;"
        )
        layout.addWidget(self._log)

    def append(self, text, color=None):
        if color:
            self._log.append(f'<span style="color:{color}">{text}</span>')
        else:
            # 默认颜色为浅灰（正常日志）
            self._log.append(f'<span style="color:#e2e8f0">{text}</span>')

    def clear(self):
        self._log.clear()

    def set_result(self, result):
        success = result.get("success", False)
        msg = result.get("message", "")
        if success:
            self.append(f"✓ {msg}", "#22c55e")
        else:
            self.append(f"✗ {msg}", "#ef4444")
        for line in result.get("log", []):
            # 根据内容自动判断颜色
            if "✓" in line:
                self.append(line, "#22c55e")
            elif "✗" in line or "失败" in line:
                self.append(line, "#ef4444")
            elif "⚠" in line:
                self.append(line, "#f59e0b")
            else:
                self.append(line)
        if result.get("files"):
            self.append(f"\n下载文件 ({len(result['files'])}个):", "#38bdf8")
            for f in result["files"]:
                self.append(f"  {f}")
        if result.get("data") and not result.get("files"):
            self.append(f"\n数据条目: {len(result['data'])}条", "#facc15")
