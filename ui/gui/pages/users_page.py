"""内嵌用户表格页 —— 替代 UserTableDialog。

显示关注列表 / 收藏用户: 圆头像 + 昵称 + ID + 粉丝 + 签名。
"""
from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget,
)
from ..cover_loader import CoverLoader


def _fmt(n) -> str:
    try:
        n = int(n or 0)
    except (TypeError, ValueError):
        return "0"
    if n >= 100_000_000:
        return f"{n / 100_000_000:.1f}亿"
    if n >= 10_000:
        return f"{n / 10_000:.1f}万"
    return str(n)


def _rounded_pixmap(pix: QPixmap, size: int = 44) -> QPixmap:
    scaled = pix.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    rounded = QPixmap(size, size)
    rounded.fill(Qt.transparent)
    p = QPainter(rounded)
    p.setRenderHint(QPainter.Antialiasing)
    path = QPainterPath()
    path.addEllipse(0, 0, size, size)
    p.setClipPath(path)
    p.drawPixmap((size - scaled.width()) // 2,
                 (size - scaled.height()) // 2, scaled)
    p.end()
    return rounded


class _UserRow(QFrame):
    """单行: 头像 | 昵称 + ID + 粉丝 + 签名。"""

    def __init__(self, user: dict, odd: bool, parent=None):
        super().__init__(parent)
        self.setObjectName("UserTableRow")
        self._avatar_url = user.get("avatar") or ""
        bg = "#16213a" if odd else "#1e293b"
        self.setStyleSheet(
            f"QFrame#UserTableRow {{ background: {bg};"
            " border: 1px solid #334155; border-radius: 6px; }"
            "QLabel { background: transparent; border: none; }")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(12)

        # 头像
        self._avatar = QLabel()
        self._avatar.setFixedSize(40, 40)
        self._avatar.setAlignment(Qt.AlignCenter)
        nick = user.get("nickname") or "?"
        self._avatar.setText(nick[0].upper() if nick else "?")
        self._avatar.setStyleSheet(
            "color: #475569; font-size: 16px; font-weight: bold;"
            " background: #0f172a; border-radius: 20px;"
            " border: 1px solid #334155;")
        if self._avatar_url:
            CoverLoader.instance().cover_ready.connect(self._on_avatar_ready)
            cached = CoverLoader.instance().request(self._avatar_url)
            if cached is not None and not cached.isNull():
                self._on_avatar_ready(self._avatar_url, cached)
        lay.addWidget(self._avatar, 0, Qt.AlignVCenter)

        # 信息
        info = QVBoxLayout()
        info.setSpacing(2)
        top = QHBoxLayout()
        top.setSpacing(8)
        name_lbl = QLabel(nick)
        name_lbl.setStyleSheet(
            "color: #f1f5f9; font-size: 15px; font-weight: bold;")
        top.addWidget(name_lbl)
        uid = user.get("user_id") or user.get("sec_user_id") or ""
        if uid:
            uid_lbl = QLabel(f"ID: {uid[:24]}")
            uid_lbl.setStyleSheet(
                "color: #64748b; font-size: 12px;")
            top.addWidget(uid_lbl)
        top.addStretch()
        fans = QLabel(f"粉丝 {_fmt(user.get('follower_count', 0))}")
        fans.setStyleSheet("color: #38bdf8; font-size: 12px;")
        top.addWidget(fans)
        info.addLayout(top)
        sig = (user.get("signature") or "").strip()
        if sig:
            sig_lbl = QLabel(sig[:60])
            sig_lbl.setStyleSheet("color: #64748b; font-size: 12px;")
            info.addWidget(sig_lbl)
        lay.addLayout(info, 1)

    def _on_avatar_ready(self, url: str, pix: QPixmap):
        if url == self._avatar_url and not pix.isNull():
            self._avatar.setPixmap(_rounded_pixmap(pix, size=40))


class UsersPage(QWidget):
    """用户列表内嵌页 (关注列表 / 收藏等)。"""

    def __init__(self, title: str = "用户列表", parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        self._title_label = QLabel(title)
        self._title_label.setObjectName("PageTitle")
        root.addWidget(self._title_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        container = QWidget()
        self._v = QVBoxLayout(container)
        self._v.setContentsMargins(0, 0, 0, 0)
        self._v.setSpacing(6)
        self._v.addStretch()
        scroll.setWidget(container)
        root.addWidget(scroll, 1)

    def set_users(self, users: list[dict], title: str | None = None):
        if title is not None:
            self._title_label.setText(f"{title} · 共 {len(users)} 人")
        while self._v.count():
            it = self._v.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()
        self._v.addStretch()
        for i, u in enumerate(users):
            self._v.insertWidget(self._v.count() - 1,
                                 _UserRow(u, odd=(i % 2 == 1)))
