"""执行日志输出。"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QTextEdit, QVBoxLayout, QWidget


class ResultView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Panel")
        self.setAttribute(Qt.WA_StyledBackground, True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        title = QLabel("执行日志")
        title.setObjectName("SectionTitle")
        title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout.addWidget(title)
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
            self._log.append(text)

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
            self.append(line)
        if result.get("files"):
            self.append(f"\n下载文件 ({len(result['files'])}个):", "#38bdf8")
            for f in result["files"]:
                self.append(f"  {f}")
        if result.get("data") and not result.get("files"):
            self.append(f"\n数据条目: {len(result['data'])}条", "#facc15")
