"""内嵌登录页 —— 替代 LoginDialog。

QR 码登录 (支持的平台) + Cookie 手动设置。

- 内容放在 QScrollArea 中, 避免在可用高度不足时被压缩变形。
- Cookie 采用多行输入 (Cookie 很长, 单行不便查看/编辑)。
- CookieManager 为单例, 保存后立即落盘, 切页/切平台再回来仍可读回。
"""
from __future__ import annotations
from io import BytesIO

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QScrollArea,
    QVBoxLayout, QWidget,
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
        self._qr_label = None
        self._qr_status = None
        self._qr_refresh_btn = None
        self._cookie_input = None
        self._cookie_status = None
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_qr)
        self._manager = None

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        # 顶部: 平台名 + 状态徽章 (固定, 不随滚动移动)
        head = QHBoxLayout()
        self._title = QLabel("登录")
        self._title.setObjectName("PageTitle")
        head.addWidget(self._title)
        head.addStretch()
        self._badge = QLabel()
        self._badge.setObjectName("PageBadge")
        head.addWidget(self._badge)
        root.addLayout(head)

        # 内容区: 放进滚动区 (防止被压缩变形)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        self._cards = QVBoxLayout(container)
        self._cards.setContentsMargins(0, 0, 0, 0)
        self._cards.setSpacing(12)
        self._cards.addStretch()
        scroll.setWidget(container)
        root.addWidget(scroll, 1)

    # ================= 对外: 重建内容 =================
    def setup(self, platform: str, cookie_hint: str, current_cookie: str):
        """配置页面内容 (切换平台时由 main_window 调用)。"""
        self._platform = platform
        self._cm = CookieManager()
        # 清空旧卡片 (保留末尾 stretch)
        while self._cards.count():
            it = self._cards.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()
        self._title.setText(f"登录 · {_pn(platform)}")

        # 以磁盘为准, 重新读取当前平台 Cookie (避免显示过期值)
        cookie = self._cm.get(platform) or current_cookie or ""
        self._set_badge(cookie)

        # QR 码登录卡片
        has_qr = LoginBus.has_qr(platform)
        self._qr_label = None
        self._qr_status = None
        self._qr_refresh_btn = None
        if has_qr:
            self._cards.addWidget(self._build_qr_card(platform))

        # Cookie 卡片
        self._cards.addWidget(
            self._build_cookie_card(platform, cookie_hint, cookie))
        self._cards.addStretch()

    # ================= QR 卡片 =================
    def _build_qr_card(self, platform: str) -> QWidget:
        card = QFrame()
        card.setObjectName("PageCard")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 16)
        lay.setSpacing(10)

        title = QLabel("扫码登录")
        title.setObjectName("CardTitle")
        lay.addWidget(title)
        hint = QLabel(f"使用 {_pn(platform)} App 扫描下方二维码")
        hint.setObjectName("CardHint")
        lay.addWidget(hint)

        # 白底圆角容器
        holder = QFrame()
        holder.setObjectName("QRHolder")
        hlay = QHBoxLayout(holder)
        hlay.setContentsMargins(14, 14, 14, 14)
        self._qr_label = QLabel("点击生成二维码")
        self._qr_label.setAlignment(Qt.AlignCenter)
        self._qr_label.setFixedSize(190, 190)
        self._qr_label.setCursor(Qt.PointingHandCursor)
        self._qr_label.mousePressEvent = lambda ev: self._generate_qr()
        hlay.addWidget(self._qr_label)
        lay.addWidget(holder, 0, Qt.AlignHCenter)

        row = QHBoxLayout()
        row.setSpacing(8)
        self._qr_status = QLabel("尚未生成")
        self._qr_status.setObjectName("QRStatus")
        row.addWidget(self._qr_status, 1)
        self._qr_refresh_btn = QPushButton("刷新二维码")
        self._qr_refresh_btn.setObjectName("PageGhostButton")
        self._qr_refresh_btn.setCursor(Qt.PointingHandCursor)
        self._qr_refresh_btn.clicked.connect(self._generate_qr)
        row.addWidget(self._qr_refresh_btn)
        lay.addLayout(row)
        return card

    # ================= Cookie 卡片 =================
    def _build_cookie_card(self, platform: str, hint: str,
                           current: str) -> QWidget:
        card = QFrame()
        card.setObjectName("PageCard")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 16)
        lay.setSpacing(10)

        # 标题行: 标题 + 实时状态
        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        title = QLabel("Cookie 设置")
        title.setObjectName("CardTitle")
        title_row.addWidget(title)
        title_row.addStretch()
        self._cookie_status = QLabel("")
        self._cookie_status.setObjectName("CardStatus")
        title_row.addWidget(self._cookie_status)
        lay.addLayout(title_row)

        # 说明
        desc = QLabel(
            "浏览器打开平台网页 → 按 F12 → Application → Cookies，"
            "复制整行 Cookie 粘贴到下方。")
        desc.setObjectName("CardHint")
        desc.setWordWrap(True)
        lay.addWidget(desc)
        if hint:
            need = QLabel(f"建议包含: {hint}")
            need.setObjectName("CardHint")
            need.setWordWrap(True)
            lay.addWidget(need)

        # 多行输入
        self._cookie_input = QPlainTextEdit()
        self._cookie_input.setObjectName("CookieInput")
        self._cookie_input.setPlaceholderText(
            "在此粘贴 Cookie 字符串…")
        self._cookie_input.setPlainText(current or "")
        self._cookie_input.setMinimumHeight(120)
        self._cookie_input.textChanged.connect(self._on_cookie_text_changed)
        lay.addWidget(self._cookie_input)

        # 操作按钮
        btns = QHBoxLayout()
        btns.setSpacing(8)
        self._clear_btn = QPushButton("清除")
        self._clear_btn.setObjectName("PageGhostButton")
        self._clear_btn.setCursor(Qt.PointingHandCursor)
        self._clear_btn.clicked.connect(self._clear_cookie)
        btns.addWidget(self._clear_btn)
        btns.addStretch()
        save_btn = QPushButton("保存 Cookie")
        save_btn.setObjectName("PagePrimaryButton")
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.clicked.connect(self._save_cookie)
        btns.addWidget(save_btn)
        lay.addLayout(btns)

        self._update_cookie_status(current or "")
        return card

    def _on_cookie_text_changed(self):
        self._update_cookie_status(self._cookie_input.toPlainText())

    def _update_cookie_status(self, cookie: str):
        """更新卡片右上角的实时状态。"""
        if self._cookie_status is None:
            return
        cookie = (cookie or "").strip()
        if cookie:
            self._cookie_status.setText(f"已填写 · {len(cookie)} 字符")
            self._cookie_status.setStyleSheet(
                "color: #22c55e; font-size: 12px;"
                " background: transparent; border: none;")
        else:
            self._cookie_status.setText("未填写")
            self._cookie_status.setStyleSheet(
                "color: #94a3b8; font-size: 12px;"
                " background: transparent; border: none;")

    # ================= 状态徽章 =================
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

    # ================= QR 逻辑 =================
    def _generate_qr(self):
        if not self._platform:
            return
        try:
            mgr = LoginBus.get_manager(self._platform)
            if not mgr:
                if self._qr_status:
                    self._qr_status.setText(f"{self._platform} 不支持扫码登录")
                return
            url, key, img = mgr.generate_qr()
            self._manager = mgr
            self._qr_key = key
            buf = BytesIO()
            img.save(buf, format="PNG")
            pixmap = QPixmap()
            pixmap.loadFromData(buf.getvalue())
            self._qr_label.setPixmap(pixmap.scaled(
                190, 190, Qt.KeepAspectRatio))
            self._qr_status.setText("请使用 App 扫描二维码")
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
                        self._cookie_input.setPlainText(cookie_str)
                    if self._qr_status:
                        self._qr_status.setText("登录成功!")
                    self.cookie_changed.emit()
                else:
                    if self._qr_status:
                        self._qr_status.setText("登录成功但未获取到 Cookie")
            elif status_code == 86090:
                if self._qr_status:
                    self._qr_status.setText("已扫码, 请在 App 中确认…")
            elif status_code == 86038:
                self._poll_timer.stop()
                if self._qr_status:
                    self._qr_status.setText("二维码已过期, 请刷新")
        except Exception as e:
            self._poll_timer.stop()
            if self._qr_status:
                self._qr_status.setText(f"轮询失败: {e}")

    # ================= Cookie 保存/清除 =================
    def _save_cookie(self):
        if self._cookie_input is None:
            return
        text = self._cookie_input.toPlainText().strip()
        if not text:
            self._update_cookie_status("")
            self._cookie_status.setText("✗ 请先粘贴 Cookie 内容")
            self._cookie_status.setStyleSheet(
                "color: #ef4444; font-size: 12px;"
                " background: transparent; border: none;")
            return
        self._cm.set(self._platform, text)
        # 从磁盘回读确认已保存
        saved = self._cm.get(self._platform)
        if saved:
            self._set_badge(saved)
            self._update_cookie_status(saved)
            self.cookie_changed.emit()
        else:
            self._cookie_status.setText("✗ 保存失败")
            self._cookie_status.setStyleSheet(
                "color: #ef4444; font-size: 12px;"
                " background: transparent; border: none;")

    def _clear_cookie(self):
        self._cm.set(self._platform, "")
        if self._cookie_input is not None:
            self._cookie_input.setPlainText("")
        self._set_badge("")
        self._update_cookie_status("")
        self.cookie_changed.emit()

    # ================= 生命周期 =================
    def stop_polling(self):
        self._poll_timer.stop()
        if self._manager:
            self._manager.close()
            self._manager = None

    def shutdown(self):
        self.stop_polling()
