"""登录对话框 — QR码登录 + Cookie输入（全平台支持）。"""
from io import BytesIO

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QTabWidget, QTextEdit, QVBoxLayout, QWidget,
)
from shared.core.i18n import t, platform_name
from shared.core.cookies import CookieManager

# 平台 → login 模块路径
LOGIN_MODULES = {
    "douyin": "platforms.douyin.login",
    "kuaishou": "platforms.kuaishou.login",
    "xiaohongshu": "platforms.xiaohongshu.login",
    "bilibili": "platforms.bilibili.login",
}
LOGIN_MANAGERS = {
    "douyin": "DouyinLoginManager",
    "kuaishou": "KuaishouLoginManager",
    "xiaohongshu": "XiaohongshuLoginManager",
    "bilibili": "BilibiliLoginManager",
}


class LoginDialog(QDialog):
    def __init__(self, platform, cookie_hint, current_cookie, parent=None):
        super().__init__(parent)
        self._platform = platform
        self._cm = CookieManager()
        self._qr_key = ""
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_qr)
        self.setWindowTitle(f"{platform.title()} 登录")
        self.setMinimumWidth(520)
        self.setMinimumHeight(420)
        self._setup_ui(cookie_hint, current_cookie)

    def _setup_ui(self, hint, current):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        title = QLabel(t("login_title", platform=platform_name(self._platform)))
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #facc15;")
        layout.addWidget(title)

        status = t("status_set") if current else t("status_unset")
        color = "#22c55e" if current else "#ef4444"
        self._status = QLabel(t("current_status", status=status, count=len(current)))
        self._status.setStyleSheet(f"color: {color}; font-weight: bold;")
        layout.addWidget(self._status)

        tabs = QTabWidget()

        # Tab 1: QR code (all platforms)
        qr_tab = QWidget()
        qr_layout = QVBoxLayout(qr_tab)
        qr_layout.addWidget(QLabel(t("qr_scan_hint", platform=platform_name(self._platform))))
        self._qr_label = QLabel(t("click_to_generate"))
        self._qr_label.setAlignment(Qt.AlignCenter)
        self._qr_label.setMinimumHeight(200)
        self._qr_label.setStyleSheet("background: white; border-radius: 8px; padding: 10px;")
        qr_layout.addWidget(self._qr_label)
        qr_btns = QHBoxLayout()
        self._qr_gen_btn = QPushButton(t("generate_qr"))
        self._qr_gen_btn.clicked.connect(self._generate_qr)
        qr_btns.addWidget(self._qr_gen_btn)
        self._qr_refresh_btn = QPushButton(t("refresh"))
        self._qr_refresh_btn.clicked.connect(self._generate_qr)
        self._qr_refresh_btn.setEnabled(False)
        qr_btns.addWidget(self._qr_refresh_btn)
        qr_layout.addLayout(qr_btns)
        self._qr_status = QLabel("")
        qr_layout.addWidget(self._qr_status)
        tabs.addTab(qr_tab, "QR码登录")

        # Tab 2: Cookie input (all platforms)
        cookie_tab = QWidget()
        cookie_layout = QVBoxLayout(cookie_tab)
        if hint:
            cookie_layout.addWidget(QLabel(hint))
        cookie_layout.addWidget(QLabel("从浏览器 DevTools > Application > Cookies 复制, 或直接粘贴 Cookie 字符串"))

        self._cookie_input = QTextEdit()
        self._cookie_input.setPlaceholderText("粘贴 Cookie 字符串...")
        self._cookie_input.setMaximumHeight(100)
        cookie_layout.addWidget(self._cookie_input)
        cookie_btns = QHBoxLayout()
        save_btn = QPushButton(t("save_cookie"))
        save_btn.clicked.connect(self._save_cookie)
        cookie_btns.addWidget(save_btn)
        clear_btn = QPushButton(t("clear"))
        clear_btn.clicked.connect(self._clear_cookie)
        cookie_btns.addWidget(clear_btn)
        cookie_layout.addLayout(cookie_btns)
        tabs.addTab(cookie_tab, "Cookie 输入")

        layout.addWidget(tabs)

    def _get_manager(self):
        mod_path = LOGIN_MODULES.get(self._platform)
        mgr_name = LOGIN_MANAGERS.get(self._platform)
        if not mod_path or not mgr_name:
            raise RuntimeError(f"{self._platform} 不支持QR登录")
        import importlib
        mod = importlib.import_module(mod_path)
        return getattr(mod, mgr_name)()

    def _generate_qr(self):
        try:
            mgr = self._get_manager()
            url, key, img = mgr.generate_qr()
            mgr.close()
            self._qr_key = key
            buf = BytesIO()
            img.save(buf, format="PNG")
            pixmap = QPixmap()
            pixmap.loadFromData(buf.getvalue())
            self._qr_label.setPixmap(pixmap.scaled(200, 200, Qt.KeepAspectRatio))
            self._qr_status.setText(t("qr_scanning", platform=platform_name(self._platform)))
            self._qr_status.setStyleSheet("color: #22d3ee;")
            self._qr_gen_btn.setEnabled(False)
            self._qr_refresh_btn.setEnabled(True)
            self._poll_timer.start(3000)
        except Exception as e:
            self._qr_status.setText(f"生成失败: {e}")
            self._qr_status.setStyleSheet("color: #ef4444;")

    def _poll_qr(self):
        if not self._qr_key:
            self._poll_timer.stop()
            return
        try:
            mgr = self._get_manager()
            result = mgr.check_qr_status(self._qr_key)
            mgr.close()
            status_code = result.get("code", -1)
            if status_code == 0:  # 登录成功
                self._poll_timer.stop()
                cookies = result.get("cookies", {})
                cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items()) if cookies else ""
                if cookie_str:
                    self._cm.set(self._platform, cookie_str)
                    self._status.setText(f"当前状态: 已设置 ({len(cookie_str)}字符)")
                    self._status.setStyleSheet("color: #22c55e; font-weight: bold;")
                    self._qr_status.setText(t("qr_success"))
                    self._qr_status.setStyleSheet("color: #22c55e; font-weight: bold;")
                else:
                    self._qr_status.setText("登录成功但未获取到Cookie")
            elif status_code == 86090:  # 等待确认
                self._qr_status.setText(t("qr_scanned"))
                self._qr_status.setStyleSheet("color: #facc15;")
            elif status_code == 86038:  # 过期
                self._poll_timer.stop()
                self._qr_status.setText(t("qr_expired"))
                self._qr_status.setStyleSheet("color: #ef4444;")
                self._qr_gen_btn.setEnabled(True)
        except Exception as e:
            self._poll_timer.stop()
            self._qr_status.setText(f"轮询失败: {e}")

    def _save_cookie(self):
        text = self._cookie_input.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, t("ok"), t("cookie_empty_warn"))
            return
        self._cm.set(self._platform, text)
        self._status.setText(f"当前状态: 已设置 ({len(text)}字符)")
        self._status.setStyleSheet("color: #22c55e; font-weight: bold;")
        QMessageBox.information(self, t("ok"), t("cookie_saved"))

    def _clear_cookie(self):
        self._cm.set(self._platform, "")
        self._cookie_input.clear()
        self._status.setText(t("current_status", status=t("status_unset"), count=0))
        self._status.setStyleSheet("color: #ef4444; font-weight: bold;")

    def closeEvent(self, event):
        self._poll_timer.stop()
        super().closeEvent(event)
