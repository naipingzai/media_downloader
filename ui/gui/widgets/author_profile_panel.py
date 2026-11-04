"""作者信息卡 (顶部常驻区)。

布局:
  上行: 头像 + 昵称/签名/统计
  下行: 一整行 5 个等宽功能按钮 (点击即触发, 全部已实现)

按钮信号 (main_window 处理):
  fetch_works_clicked      获取作者所有作品
  follow_list_clicked      查看关注列表
  collect_list_clicked     查看收藏列表
  download_avatar_clicked  下载头像 (avatar url)
  open_home_clicked        获取主页链接 (home url)
"""
from __future__ import annotations
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel,
    QSizePolicy, QVBoxLayout, QWidget,
)
from ..cover_loader import CoverLoader
from .cover_label import RoundAvatarLabel


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


class AuthorProfilePanel(QFrame):
    """主页顶部作者信息卡。"""

    # ===== 对外信号 (main_window 连接) =====
    fetch_works_clicked = Signal()        # 获取作者所有作品
    follow_list_clicked = Signal()        # 查看关注列表
    collect_list_clicked = Signal()       # 查看收藏列表
    download_avatar_clicked = Signal(str)  # 下载头像 (avatar url)
    open_home_clicked = Signal(str)        # 获取主页链接 (home url)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("AuthorProfilePanel")
        self._profile = {}
        self._build_ui()
        self.show_placeholder("未登录 / 暂未显示", "请先在左侧选择平台并登录")

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 10, 14, 10)
        outer.setSpacing(6)

        # ===== 上行: 头像 + 作者信息 =====
        top = QHBoxLayout()
        top.setSpacing(10)

        self._avatar = RoundAvatarLabel(
            size=52, object_name="AuthorAvatar")
        top.addWidget(self._avatar, 0, Qt.AlignTop)

        center = QVBoxLayout()
        center.setSpacing(2)
        self._nick = QLabel("(未登录)")
        self._nick.setObjectName("AuthorNick")
        # 缩放容忍: 不以文本宽度抬高最小宽度 → 窄窗口时省略显示而非压坏
        self._nick.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self._nick.setMinimumWidth(0)
        center.addWidget(self._nick)
        # 保存原始昵称全文, resize 时重新 elide
        self._nick_original = ""
        self._sig = QLabel("")
        self._sig.setObjectName("AuthorSig")
        # 固定 2 行: wordwrap 自动换行, 超出部分裁剪 (不撑高外框遮挡统计)
        self._sig.setWordWrap(True)
        self._sig.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self._sig.setMinimumWidth(0)
        self._sig.setMaximumHeight(
            QFontMetrics(self._sig.font()).height() * 2 + 2)
        center.addWidget(self._sig)
        # 统计行: 单行 4 个等宽边框小块 (压缩高度, 避免外层裁切)
        stats_row = QHBoxLayout()
        stats_row.setSpacing(6)
        self._stat_labels: dict[str, QLabel] = {}
        for key, name in (
                ("follower_count", "粉丝"), ("following_count", "关注"),
                ("total_favorited", "获赞"), ("aweme_count", "作品")):
            box = QFrame()
            box.setObjectName("AuthorStatBox")
            # Ignored: 统计块可被压缩到任意宽度, 不撑爆左栏
            box.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            box.setMinimumWidth(0)
            bl = QVBoxLayout(box)
            bl.setContentsMargins(4, 2, 4, 2)
            bl.setSpacing(0)
            num = QLabel("0")
            num.setObjectName("AuthorStatNum")
            num.setAlignment(Qt.AlignCenter)
            num.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            num.setMinimumWidth(0)
            cap = QLabel(name)
            cap.setObjectName("AuthorStatCap")
            cap.setAlignment(Qt.AlignCenter)
            cap.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            cap.setMinimumWidth(0)
            bl.addWidget(num)
            bl.addWidget(cap)
            self._stat_labels[key] = num
            stats_row.addWidget(box, 1)
        self._stats = None   # 旧单行统计移除, 由 4 个小块呈现
        center.addLayout(stats_row)
        top.addLayout(center, 1)
        # 展开按钮: 弹窗查看完整资料 (长签名在卡内只显示 2 行)
        self._expand_btn = QLabel("▸")
        self._expand_btn.setObjectName("AuthorExpandBtn")
        self._expand_btn.setFixedSize(22, 22)
        self._expand_btn.setAlignment(Qt.AlignCenter)
        self._expand_btn.setCursor(Qt.PointingHandCursor)
        self._expand_btn.setToolTip("查看完整资料")
        self._expand_btn.mouseReleaseEvent = lambda _ev: self._show_detail()
        top.addWidget(self._expand_btn, 0, Qt.AlignTop)
        outer.addLayout(top)
        # 5 个功能按钮已移出到「功能」区, 这里不再放任何按钮

    @property
    def profile(self) -> dict:
        return self._profile or {}

    # ===== 状态切换 =====

    def show_placeholder(self, nick: str, hint: str):
        self._profile = {}
        # clear_user 同时清空内部 URL: 若只清图, paintEvent 兜底会把
        # 上一平台头像从缓存重新画回来 (跨平台头像残留)。
        self._avatar.clear_user()
        self._nick_original = ""
        self._nick.setText(nick)
        self._sig_original = ""
        self._sig.setText(hint)
        self._build_stats({})

    def show_current_user(self, profile: dict):
        if not profile:
            self.show_placeholder("当前用户未获取", "Cookie 可能未配置")
            return
        self._show_profile(profile, "  ▸ 当前登录", "#3b82f6")

    def show_work_author(self, profile: dict):
        if not profile:
            self.show_placeholder("作者未获取", "请检查链接或 Cookie")
            return
        self._show_profile(profile, "", "#f1f5f9")

    def _show_profile(self, profile: dict, suffix: str, color: str):
        self._profile = dict(profile)
        self._set_avatar(profile.get("avatar", ""), profile.get("nickname", "?"))
        nick = f"{profile.get('nickname', '?')}{suffix}"
        self._nick_original = nick
        self._elide_nick()
        sig = (profile.get("signature") or "").strip() or "(无签名)"
        self._sig_original = sig      # 全文保留 (供展开弹窗显示)
        self._sig.setText(sig)        # wordwrap 自动 2 行换行, 超出裁剪
        self._build_stats(profile)

    def _elide_nick(self):
        """昵称过长时按可用宽度省略。"""
        from PySide6.QtGui import QFontMetrics
        nick = getattr(self, "_nick_original", "")
        fm = QFontMetrics(self._nick.font())
        self._nick.setText(fm.elidedText(
            nick, Qt.ElideRight, max(40, self.width() - 120)))

    def _show_detail(self):
        """弹窗显示完整作者资料 (签名全文 + 统计)。"""
        if not self._profile:
            return
        p = self._profile
        dlg = QDialog(self)
        dlg.setWindowTitle(f"作者资料 · {p.get('nickname', '?')}")
        dlg.setMinimumWidth(420)
        v = QVBoxLayout(dlg)
        v.setContentsMargins(18, 14, 18, 14)
        v.setSpacing(10)
        title = QLabel(str(p.get("nickname", "?")))
        title.setObjectName("DialogTitle")
        title.setWordWrap(True)
        v.addWidget(title)
        uid = str(p.get("user_id") or p.get("sec_user_id") or "")
        if uid:
            uid_lbl = QLabel(f"ID: {uid}")
            uid_lbl.setObjectName("DialogSub")
            uid_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
            v.addWidget(uid_lbl)
        sig_lbl = QLabel(str(p.get("signature") or "(无签名)"))
        sig_lbl.setObjectName("DialogBody")
        sig_lbl.setWordWrap(True)
        sig_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        v.addWidget(sig_lbl, 1)
        stats = QLabel(" · ".join(
            f"{name} {_fmt(p.get(key, 0))}" for key, name in (
                ("follower_count", "粉丝"), ("following_count", "关注"),
                ("total_favorited", "获赞"), ("aweme_count", "作品"))))
        stats.setObjectName("DialogSub")
        stats.setWordWrap(True)
        v.addWidget(stats)
        dlg.resize(460, 300)
        dlg.exec()

    def _build_stats(self, p: dict):
        """填充 4 个统计小块。"""
        for key, lbl in self._stat_labels.items():
            lbl.setText(_fmt(p.get(key, 0)))

    # ===== 头像 =====

    def _set_avatar(self, url: str, fallback: str):
        # RoundAvatarLabel 内部自带缓存命中 + paintEvent 兜底
        self._avatar_url = CoverLoader.normalize_url(url)
        self._avatar.set_user(self._avatar_url, fallback or "?")

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        # 宽度变化时重新按可用宽度省略昵称 (签名已改为 wordwrap 2 行)
        if getattr(self, "_nick_original", ""):
            self._elide_nick()
