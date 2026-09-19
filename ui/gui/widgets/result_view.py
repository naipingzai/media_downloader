"""执行日志输出。"""
from PySide6.QtWidgets import QLabel, QTextEdit, QVBoxLayout, QWidget


class ResultView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Panel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        title = QLabel("执行日志")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setStyleSheet("background: #0f172a; color: #e2e8f0; font-family: monospace; font-size: 12px; border: 1px solid #334155; border-radius: 4px;")
        layout.addWidget(self._log)

    def append(self, text, color=None):
        if color:
            self._log.append(f'<span style="color:{color}">{text}</span>')
        else:
            self._log.append(text)

    def clear(self):
        self._log.clear()

    def set_result(self, result):
        color = "#22c55e" if result.get("success") else "#ef4444"
        self.append(f"--- {result.get('message', '')} ---", color)
        for line in result.get("log", []):
            self.append(line)
        if result.get("files"):
            self.append(f"\n下载文件:", "#38bdf8")
            for f in result["files"]:
                self.append(f"  {f}")
