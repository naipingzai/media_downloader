"""内嵌登录页 —— 替代 LoginDialog。

QR 码登录 (支持的平台) + Cookie 手动设置。
"""
from __future__ import annotations
from io import BytesIO

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget,
)
from shared.core import CookieManager, LoginBus, platform_name as _pn


class LoginPage(QWidget):
    """内嵌登录页 (可复用, 切换平台时由外部 rebuild 内容)。"""
    cookie_changed = Signal()  # Cookie 改变时发出 (供 main_window 刷新状态栏)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._platform = ""
        self._cm = CookieManager()
        self._qr_key = ""
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_qr)
        self._manager = None
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        # 顶部: 平台名 + 状态徽章
        head = QHBoxLayout()
        self._title = QLabel("登录")
        self._title.setObjectName("PageTitle")
        head.addWidget(self._title)
        head.addStretch()
        self._badge = QLabel()
        self._badge.setObjectName("PageBadge")
        head.addWidget(self._badge)
        root.addLayout(head)

        self._cards = QVBoxLayout()
        self._cards.setSpacing(10)
        root.addLayout(self._cards)
        root.addStretch()

    def setup(self, platform: str, cookie_hint: str, current_cookie: str):
        """配置页面内容 (切换平台时由 main_window 调用)。"""
        self._platform = platform
        self._cm = CookieManager()
        # 清空旧卡片
        while self._cards.count():
            it = self._cards.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()
        self._title.setText(f"登录 · {_pn(platform)}")
        self._set_badge(current_cookie or "")

        # QR 码登录卡片
        has_qr = LoginBus.has_qr(platform)
        self._qr_label = None
        self._qr_status = None
        self._qr_refresh_btn = None
        if has_qr:
            self._cards.addWidget(self._build_qr_card(platform))

        # Cookie 卡片
        self._cards.addWidget(self._build_cookie_card(platform, cookie_hint,
                                                     current_cookie))

    def _build_qr_card(self, platform: str) -> QWidget:
        card = QFrame()
        card.setObjectName("PageCard")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 12, 14, 14)
        lay.setSpacing(10)
        title = QLabel("QR 码登录")
        title.setObjectName("CardTitle")
        lay.addWidget(title)
        hint = QLabel(f"使用 {_pn(platform)} App 扫描二维码登录")
        hint.setObjectName("CardHint")
        lay.addWidget(hint)
        # 白底圆角
        h = QFrame()
        h.setObjectName("QRHolder")
        hlay = QHBoxLayout(h)
        hlay.setContentsMargins(12, 12, 12, 12)
        self._qr_label = QLabel("点击下方按钮生成二维码")
        self._qr_label.setAlignment(Qt.AlignCenter)
        self._qr_label.setFixedSize(200, 200)
        self._qr_label.setCursor(Qt.PointingHandCursor)
        self._qr_label.mousePressEvent = lambda ev: self._generate_qr()
        hlay.addWidget(self._qr_label)
        lay.addWidget(h, 0, Qt.AlignHCenter)
        # 状态 + 刷新按钮
        row = QHBoxLayout()
        self._qr_status = QLabel("尚未生成")
        self._qr_status.setObjectName("QRStatus")
        row.addWidget(self._qr_status)
        row.addStretch()
        self._qr_refresh_btn = QPushButton("刷新")
        self._qr_refresh_btn.setObjectName("PageGhostButton")
        self._qr_refresh_btn.setCursor(Qt.PointingHandCursor)
        self._qr_refresh_btn.setEnabled(False)
        self._qr_refresh_btn.clicked.connect(self._generate_qr)
        row.addWidget(self._qr_refresh_btn)
        lay.addLayout(row)
        return card

    def _build_cookie_card(self, platform: str, hint: str,
                           current: str) -> QWidget:
        card = QFrame()
        card.setObjectName("PageCard")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 12, 14, 14)
        lay.setSpacing(10)
        title = QLabel("Cookie 手动设置")
        title.setObjectName("CardTitle")
        lay.addWidget(title)
        if hint:
            h = QLabel(hint)
            h.setObjectName("CardHint")
            h.setWordWrap(True)
            lay.addWidget(h)
        for step in ("① 浏览器打开平台网页, 按 F12 打开开发者工具",
                     "② Application → Cookies → 复制整行 Cookie"):
            s = QLabel(step)
            s.setObjectName("CardHint")
            lay.addWidget(s)
        self._cookie_input = QLineEdit(current or "")
        self._cookie_input.setPlaceholderText("粘贴 Cookie 字符串…")
        self._cookie_input.setObjectName("CardInput")
        lay.addWidget(self._cookie_input)
        self._cookie_status = QLabel("")
        self._cookie_status.setObjectName("CardStatus")
        lay.addWidget(self._cookie_status)
        btns = QHBoxLayout()
        btns.setSpacing(8)
        btns.addStretch()
        save_btn = QPushButton("保存 Cookie")
        save_btn.setObjectName("PagePrimaryButton")
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.clicked.connect(self._save_cookie)
        btns.addWidget(save_btn)
        clear_btn = QPushButton("清除")
        clear_btn.setObjectName("PageGhostButton")
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.clicked.connect(self._clear_cookie)
        btns.addWidget(clear_btn)
        lay.addLayout(btns)
        return card

    def _set_badge(self, cookie: str):
        if cookie and cookie.strip():
            n = len(cookie)
            self._badge.setText(f"● 已设置 · {n} 字符")
            self._badge.setStyleSheet(
                "background: rgba(34, 197, 94, 0.18); color: #22c55e;"
                " border-radius: 10px; padding: 3px 12px;"
                " font-size: 12px; font-weight: bold;")
        else:
            self._badge.setText("● 未设置")
            self._badge.setStyleSheet(
                "background: rgba(239, 68, 68, 0.18); color: #ef4444;"
                " border-radius: 10px; padding: 3px 12px;"
                " font-size: 12px; font-weight: bold;")

    def _generate_qr(self):
        if not self._platform:
            return
        try:
            mgr = LoginBus.get_manager(self._platform)
            if not mgr:
                if self._qr_status:
                    self._qr_status.setText(f"{self._platform} 不支持 QR 登录")
                return
            url, key, img = mgr.generate_qr()
            self._manager = mgr
            self._qr_key = key
            buf = BytesIO()
            img.save(buf, format="PNG")
            pixmap = QPixmap()
            pixmap.loadFromData(buf.getvalue())
            self._qr_label.setPixmap(pixmap.scaled(
                200, 200, Qt.KeepAspectRatio))
            self._qr_status.setText(f"请用 {_pn(self._platform)} App 扫描二维码")
            self._qr_refresh_btn.setEnabled(True)
            self._poll_timer.start(3000)
        except Exception as e:
            if self._qr_status:
                self._qr_status.setText(f"生成失败: {e}")

    def _poll_qr(self):
        if not self._qr_key:
            self._poll_timer.stop()
            return
        try:
            mgr = self._manager or LoginBus.get_manager(self._platform)
            if not mgr:
                self._poll_timer.stop()
                return
            result = mgr.check_qr_status(self._qr_key)
            status_code = result.get("code", -1)
            if status_code == 0:
                self._poll_timer.stop()
                cookies = result.get("cookies", {})
                cookie_str = ("; ".join(f"{k}={v}" for k, v in cookies.items())
                              if cookies else "")
                if cookie_str:
                    self._cm.set(self._platform, cookie_str)
                    self._set_badge(cookie_str)
                    if self._cookie_input is not None:
                        self._cookie_input.setText(cookie_str)
                    self._qr_status.setText("登录成功!")
                else:
                    self._qr_status.setText("登录成功但未获取到 Cookie")
            elif status_code == 86090:
                self._qr_status.setText("已扫码, 等待确认...")
            elif status_code == 86038:
                self._poll_timer.stop()
                self._qr_status.setText("二维码已过期, 请刷新")
        except Exception as e:
            self._poll_timer.stop()
            if self._qr_status:
                self._qr_status.setText(f"轮询失败: {e}")

    def _save_cookie(self):
        text = self._cookie_input.text().strip()
        if not text:
            self._cookie_status.setText("✗ 请先粘贴 Cookie 内容")
            return
        self._cm.set(self._platform, text)
        self._set_badge(text)
        self._cookie_status.setText(f"✓ Cookie 已保存 ({len(text)} 字符)")

    def _clear_cookie(self):
        self._cm.set(self._platform, "")
        self._cookie_input.clear()
        self._set_badge("")
        self._cookie_status.setText("Cookie 已清除")

    def stop_polling(self):
        self._poll_timer.stop()
        if self._manager:
            self._manager.close()
            self._manager = None

    def shutdown(self):
        self.stop_polling()
