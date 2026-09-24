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
from PySide6.QtGui import QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
    QVBoxLayout, QWidget,
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
        # 仅背景色 (外框由 SectionPanel 提供, 不再叠加内边框)
        self.setStyleSheet(
            "#AuthorProfilePanel { background: transparent; border: none; }")
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

        self._avatar = QLabel()
        self._avatar.setFixedSize(48, 48)
        self._avatar.setAlignment(Qt.AlignCenter)
        self._avatar.setStyleSheet(
            "background: #0f172a; color: #475569; border-radius: 24px;"
            " border: 2px solid #334155; font-size: 18px; font-weight: bold;")
        top.addWidget(self._avatar, 0, Qt.AlignTop)

        center = QVBoxLayout()
        center.setSpacing(2)
        self._nick = QLabel("(未登录)")
        self._nick.setStyleSheet(
            "color: #f1f5f9; font-size: 15px; font-weight: bold;"
            " background: transparent; border: none;")
        center.addWidget(self._nick)
        self._sig = QLabel("")
        self._sig.setWordWrap(True)
        self._sig.setStyleSheet(
            "color: #94a3b8; font-size: 12px;"
            " background: transparent; border: none;")
        center.addWidget(self._sig)
        # 统计行: 4 个独立边框小块 (粉丝/关注/获赞/作品)
        stats_row = QHBoxLayout()
        stats_row.setSpacing(6)
        self._stat_labels: dict[str, QLabel] = {}
        for key, name in (("follower_count", "粉丝"), ("following_count", "关注"),
                          ("total_favorited", "获赞"), ("aweme_count", "作品")):
            box = QFrame()
            box.setStyleSheet(
                "QFrame { background: #1e293b; border: 1px solid #334155;"
                " border-radius: 4px; }")
            bl = QVBoxLayout(box)
            bl.setContentsMargins(8, 4, 8, 4)
            bl.setSpacing(0)
            num = QLabel("0")
            num.setAlignment(Qt.AlignCenter)
            num.setStyleSheet(
                "color: #38bdf8; font-size: 14px; font-weight: bold;"
                " background: transparent; border: none;")
            cap = QLabel(name)
            cap.setAlignment(Qt.AlignCenter)
            cap.setStyleSheet(
                "color: #64748b; font-size: 12px;"
                " background: transparent; border: none;")
            bl.addWidget(num)
            bl.addWidget(cap)
            self._stat_labels[key] = num
            stats_row.addWidget(box, 1)
        self._stats = None   # 旧单行统计移除, 由 4 个小块呈现
        center.addLayout(stats_row)
        top.addLayout(center, 1)
        outer.addLayout(top)
        # 5 个功能按钮已移出到「功能」区, 这里不再放任何按钮

    # ===== 按钮点击 → 发信号给 main_window (全部已实现) =====
    def _on_fetch_works(self):
        self.fetch_works_clicked.emit()

    def _on_follow_list(self):
        self.follow_list_clicked.emit()

    def _on_collect_list(self):
        self.collect_list_clicked.emit()

    def _on_download_avatar(self):
        self.download_avatar_clicked.emit(self._profile.get("avatar", ""))

    def _on_open_home(self):
        home = (self._profile.get("home_url") or "").strip()
        if not home:
            sec = (self._profile.get("sec_user_id") or self._profile.get("sec_uid")
                   or self._profile.get("user_id") or "")
            if sec:
                p = self._profile.get("platform", "")
                if p == "bilibili":
                    home = f"https://space.bilibili.com/{sec}"
                elif p == "kuaishou":
                    home = f"https://www.kuaishou.com/profile/{sec}"
                elif p == "xiaohongshu":
                    home = f"https://www.xiaohongshu.com/user/profile/{sec}"
                else:
                    home = f"https://www.douyin.com/user/{sec}"
        self.open_home_clicked.emit(home)

    def _set_buttons_enabled(self, enabled: bool):
        """兼容旧调用 (按钮已移除, 无操作)。"""
        pass

    @property
    def profile(self) -> dict:
        return self._profile or {}

    # ===== 状态切换 =====
    def show_placeholder(self, nick: str, hint: str):
        self._profile = {}
        self._avatar.setPixmap(QPixmap())
        self._avatar.setText("👤")
        self._nick.setText(nick)
        self._nick.setStyleSheet(
            "color: #94a3b8; font-size: 15px;"
            " background: transparent; border: none;")
        self._sig.setText(hint)
        self._sig.setStyleSheet(
            "color: #64748b; font-size: 14px;"
            " background: transparent; border: none;")
        self._build_stats({})
        self._set_buttons_enabled(False)

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
        self._nick.setText(f"{profile.get('nickname', '?')}{suffix}")
        self._nick.setStyleSheet(
            f"color: {color}; font-size: 15px; font-weight: bold;"
            " background: transparent; border: none;")
        sig = (profile.get("signature") or "").strip() or "(无签名)"
        self._sig.setText(sig)
        self._sig.setStyleSheet(
            "color: #cbd5e1; font-size: 14px;"
            " background: transparent; border: none;")
        self._build_stats(profile)
        self._set_buttons_enabled(True)

    def _build_stats(self, p: dict):
        """填充 4 个统计小块。"""
        for key, lbl in self._stat_labels.items():
            lbl.setText(_fmt(p.get(key, 0)))

    # ===== 头像 =====
    def _set_avatar(self, url: str, fallback: str):
        self._avatar.setPixmap(QPixmap())
        if fallback:
            self._avatar.setText(fallback[0].upper())
        if url:
            self._avatar_url = url
            CoverLoader.instance().cover_ready.connect(self._on_avatar_ready)
            cached = CoverLoader.instance().request(url)
            if cached is not None:
                self._on_avatar_ready(url, cached)

    def _on_avatar_ready(self, url: str, pix: QPixmap):
        if url != getattr(self, "_avatar_url", ""):
            return
        target_size = self._avatar.size()
        scaled = pix.scaled(target_size, Qt.KeepAspectRatio,
                            Qt.SmoothTransformation)
        rounded = QPixmap(target_size)
        rounded.fill(Qt.transparent)
        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addEllipse(0, 0, target_size.width(), target_size.height())
        painter.setClipPath(path)
        x = (target_size.width() - scaled.width()) // 2
        y = (target_size.height() - scaled.height()) // 2
        painter.drawPixmap(x, y, scaled)
        painter.end()
        self._avatar.setPixmap(rounded)
        self._avatar.setText("")
