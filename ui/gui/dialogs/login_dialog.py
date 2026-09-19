"""登录对话框 - Cookie 输入。"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QTextEdit, QVBoxLayout,
)
from shared.core.cookies import CookieManager


class LoginDialog(QDialog):
    def __init__(self, platform, cookie_hint, current_cookie, parent=None):
        super().__init__(parent)
        self._platform = platform
        self._cm = CookieManager()
        self.setWindowTitle(f"设置 {platform} Cookie")
        self.setMinimumWidth(500)
        self.setMinimumHeight(350)
        self._setup_ui(cookie_hint, current_cookie)

    def _setup_ui(self, hint, current):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        title = QLabel(f"{self._platform} 登录")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #facc15;")
        layout.addWidget(title)

        if hint:
            h = QLabel(hint)
            h.setStyleSheet("color: #94a3b8; font-size: 12px;")
            layout.addWidget(h)

        status = "已设置" if current else "未设置"
        color = "#22c55e" if current else "#ef4444"
        self._status = QLabel(f"当前状态: {status} ({len(current)}字符)")
        self._status.setStyleSheet(f"color: {color}; font-weight: bold;")
        layout.addWidget(self._status)

        layout.addWidget(QLabel("粘贴 Cookie 字符串:"))
        self._input = QTextEdit()
        self._input.setPlaceholderText("从浏览器 DevTools → Application → Cookies 复制整个 Cookie 字符串...")
        self._input.setMaximumHeight(120)
        layout.addWidget(self._input)

        btns = QHBoxLayout()
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self._save)
        btns.addWidget(save_btn)
        clear_btn = QPushButton("清除")
        clear_btn.clicked.connect(self._clear)
        btns.addWidget(clear_btn)
        btns.addStretch()
        layout.addLayout(btns)

    def _save(self):
        text = self._input.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "提示", "请输入 Cookie")
            return
        self._cm.set(self._platform, text)
        self._status.setText(f"当前状态: 已设置 ({len(text)}字符)")
        self._status.setStyleSheet("color: #22c55e; font-weight: bold;")
        QMessageBox.information(self, "成功", "Cookie 已保存")

    def _clear(self):
        self._cm.set(self._platform, "")
        self._input.clear()
        self._status.setText("当前状态: 未设置")
        self._status.setStyleSheet("color: #ef4444; font-weight: bold;")
