"""内嵌用户列表页 —— 关注列表/收藏用户 (继承 ListPageBase 公共设计)。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from ..cover_loader import CoverLoader
from ..widgets.cover_label import RoundAvatarLabel
from shared.core.format import format_count as _fmt
from .base_page import ListPageBase






class _UserRow(QFrame):
    """单行: 头像 | 昵称 + ID + 粉丝 + 签名。"""

    def __init__(self, user: dict, odd: bool, parent=None):
        super().__init__(parent)
        self.setObjectName("UserTableRow")
        self._avatar_url = CoverLoader.normalize_url(user.get("avatar") or "")
        # 斑马纹经 property 提供, 颜色由主题 QSS [zebra="odd"] 控制
        self.setProperty("zebra", "odd" if odd else "even")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(12)
        nick = user.get("nickname") or "?"
        self._avatar = RoundAvatarLabel(size=40, object_name="UserAvatar")
        self._avatar.set_user(self._avatar_url, nick)
        lay.addWidget(self._avatar, 0, Qt.AlignVCenter)
        info = QVBoxLayout()
        info.setSpacing(2)
        top = QHBoxLayout()
        top.setSpacing(8)
        name_lbl = QLabel(nick)
        name_lbl.setObjectName("UserNick")
        top.addWidget(name_lbl)
        uid = user.get("user_id") or user.get("sec_user_id") or ""
        if uid:
            uid_lbl = QLabel(f"ID: {uid[:24]}")
            uid_lbl.setObjectName("UserID")
            top.addWidget(uid_lbl)
        top.addStretch()
        fans = QLabel(f"粉丝 {_fmt(user.get('follower_count', 0))}")
        fans.setObjectName("UserFans")
        top.addWidget(fans)
        info.addLayout(top)
        sig = (user.get("signature") or "").strip()
        if sig:
            sig_lbl = QLabel(sig[:60])
            sig_lbl.setObjectName("UserSig")
            info.addWidget(sig_lbl)
        lay.addLayout(info, 1)



class UsersPage(ListPageBase):
    """用户列表内嵌页 (关注列表/收藏等)。"""

    def __init__(self, title: str = "用户列表", parent=None):
        super().__init__(title=title, parent=parent)

    def set_users(self, users: list, title: str | None = None):
        if title is not None:
            self.set_title(f"{title} · 共 {len(users)} 人")
        self.clear_content()
        if not users:
            self.show_empty("暂无用户", "关注列表 / 收藏列表需要先登录并配置 Cookie")
            self.set_count("共 0 人")
            return
        for i, u in enumerate(users):
            self.add_content(_UserRow(u, odd=(i % 2 == 1)))
        self.set_count(f"共 {len(users)} 人")
