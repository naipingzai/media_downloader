"""内嵌浏览器 —— App 式浏览窗口 (MVP: 我的 → 用户作品 → 下载)。

按 docs/APP_BROWSER_PLAN.md 最小可行方案实现:
  ① 顶部作者卡 (当前登录用户, 复用 AuthorProfilePanel 数据)
  ② 三入口页签: 我的作品 / 收藏列表 / 关注列表
  ③ 关注列表 → 点「查看作品」→ 该用户作品网格 → 勾选下载
  ④ 全部复用 WorkGridPage / UsersPage 渲染 + DownloadQueue 下载

数据通过后台 QRunnable 拉取 (复用 main_window 的后台任务模式),
Cookie 未配置时显示引导提示 (CookieGuard 防呆)。
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Qt, QRunnable, QThreadPool, Signal
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QTabWidget, QVBoxLayout, QWidget,
)

from shared.core import CookieManager, platform_name as _pn
from .author_profile_panel import AuthorProfilePanel
from .tool_window import ToolWindow
from ..pages.work_grid_page import WorkGridPage


# ================= 后台拉取任务 =================


class _BrowseSignals(QObject):
    done = Signal(object)
    failed = Signal(str)
    log = Signal(str)


class _BrowseTask(QRunnable):
    """后台拉取: my_works / favorites / following / user_works。"""

    def __init__(self, kind: str, sec_uid: str, cookie: str, platform: str):
        super().__init__()
        self.kind = kind
        self.sec_uid = sec_uid
        self.cookie = cookie
        self.platform = platform or "douyin"
        self.signals = _BrowseSignals()
        self.setAutoDelete(False)

    def run(self):
        import asyncio
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(self._fetch())
            finally:
                loop.close()
            try:
                self.signals.done.emit(result or [])
            except RuntimeError:
                pass
        except Exception as e:
            try:
                self.signals.failed.emit(f"{type(e).__name__}: {e}")
            except RuntimeError:
                pass

    async def _fetch(self) -> list:
        from shared.core.adapter import PlatformConfig, norm_work, norm_user
        from platforms import get_platform
        cls = get_platform(self.platform)
        if not cls:
            return []
        a = cls(config=PlatformConfig(
            name=self.platform, display_name=self.platform,
            domains=[], cookie=self.cookie))
        try:
            if self.kind in ("user_works", "my_works"):
                # 我的作品 = 用当前登录用户的 sec_uid 拉作品列表 (同款分页)
                return await self._user_works(a, norm_work)
            if self.kind == "following":
                return await self._following(a, norm_user)
            if self.kind == "favorites":
                return await self._favorites(a, norm_work)
            return []
        finally:
            await a.close()

    async def _user_works(self, a, norm_work) -> list:
        """复用 main_window._fetch_works 同款分页逻辑 (5 页×20)。"""
        items: list = []
        cursor = "0"
        for _page in range(5):
            data = await a.fetch_user_posts(
                self.sec_uid, count=20, max_cursor=cursor)
            if not data:
                break
            if isinstance(data, list):
                items.extend(norm_work(aw, self.platform) for aw in data)
                break
            awemes = data.get("aweme_list") or data.get("data") or []
            if isinstance(awemes, dict):
                awemes = awemes.get("aweme_list") or []
            if not awemes:
                break
            items.extend(norm_work(aw, self.platform) for aw in awemes)
            if not data.get("has_more"):
                break
            cursor = str(data.get("max_cursor") or "0")
            if cursor == "0":
                break
        return items

    async def _following(self, a, norm_user) -> list:
        users: list = []
        max_time = "0"
        for _page in range(3):
            data = await a.fetch_user_following(
                self.sec_uid, count=20, max_time=max_time)
            if not data:
                break
            if isinstance(data, list):
                users.extend(norm_user(u, self.platform) for u in data)
                break
            fl = (data.get("followings") or data.get("follow_list")
                  or (data.get("data") or {}).get("followings") or [])
            if not fl:
                break
            users.extend(norm_user(u, self.platform) for u in fl)
            if not data.get("has_more"):
                break
            max_time = str(data.get("max_time") or "0")
            if max_time == "0":
                break
        return users

    async def _favorites(self, a, norm_work) -> list:
        items: list = []
        cursor = "0"
        for _page in range(3):
            if hasattr(a, "fetch_favorites"):
                data = await a.fetch_favorites(cursor=cursor, count=20)
            elif hasattr(a, "fetch_collection"):
                data = await a.fetch_collection(cursor=cursor, count=20)
            else:
                break
            if not data:
                break
            if isinstance(data, list):
                items.extend(norm_work(aw, self.platform) for aw in data)
                break
            awemes = (data.get("aweme_list")
                      or (data.get("data") or {}).get("aweme_list") or [])
            if not awemes:
                break
            items.extend(norm_work(aw, self.platform) for aw in awemes)
            if not data.get("has_more"):
                break
            cursor = str(data.get("cursor") or "0")
            if cursor == "0":
                break
        return items


# ================= 用户行 (可点「查看作品」) =================


class _BrowseUserRow(QWidget):
    """关注列表行: 头像+昵称+粉丝+签名+「查看作品」按钮。"""

    open_works = Signal(dict)

    def __init__(self, user: dict, odd: bool, parent=None):
        super().__init__(parent)
        from ..cover_loader import CoverLoader
        from ..widgets.cover_label import RoundAvatarLabel
        from shared.core.format import format_count as _fmt
        self.setObjectName("UserTableRow")
        self.setProperty("zebra", "odd" if odd else "even")
        self._user = dict(user)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(12)
        nick = user.get("nickname") or "?"
        self._avatar = RoundAvatarLabel(size=40, object_name="UserAvatar")
        self._avatar.set_user(
            CoverLoader.normalize_url(user.get("avatar") or ""), nick)
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
            uid_lbl = QLabel(f"ID: {str(uid)[:24]}")
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
        btn = QPushButton("查看作品")
        btn.setObjectName("PageGhostButton")
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(lambda: self.open_works.emit(self._user))
        lay.addWidget(btn, 0, Qt.AlignVCenter)


# ================= 浏览窗口 =================


class BrowseWindow(ToolWindow):
    """内嵌浏览器: 平台登录态下的「我的作品/收藏/关注 → 用户作品」浏览。"""

    download_requested = Signal(list)   # 转发给主窗口执行下载

    def __init__(self, parent=None):
        super().__init__("内嵌浏览器", QWidget(), size=(960, 720), parent=parent)
        self._cm = CookieManager()
        self._platform = ""
        self._sec_uid = ""
        self._pool = QThreadPool()
        self._pool.setMaxThreadCount(1)
        self._tasks: list = []          # 持有任务引用防 GC
        self._build_ui()
        # 内容替换: ToolWindow.set_content 会重新挂布局, 需要补挂信号容器
        self.set_content(self._root, "内嵌浏览器")

    # ---------------- UI ----------------

    def _build_ui(self):
        root = QWidget()
        v = QVBoxLayout(root)
        v.setContentsMargins(12, 10, 12, 10)
        v.setSpacing(8)

        # ① 顶部: 平台作者卡 (当前登录用户)
        self._author = AuthorProfilePanel()
        self._author.setMaximumHeight(150)
        v.addWidget(self._author)

        # ② 页签: 我的作品 / 收藏 / 关注
        self._tabs = QTabWidget()
        self._tabs.setObjectName("BrowseTabs")
        # 我的作品页: WorkGridPage (自带勾选+下载按钮)
        self._my_works_page = WorkGridPage()
        self._my_works_page.download_requested.connect(self._download)
        self._tabs.addTab(self._my_works_page, "我的作品")
        # 收藏页: 同为作品网格
        self._fav_page = WorkGridPage()
        self._fav_page.download_requested.connect(self._download)
        self._tabs.addTab(self._fav_page, "收藏列表")
        v.addWidget(self._tabs, 1)

        # 底部: 状态 + 返回按钮
        bottom = QHBoxLayout()
        self._back_btn = QPushButton("← 返回关注列表")
        self._back_btn.setObjectName("PageGhostButton")
        self._back_btn.setCursor(Qt.PointingHandCursor)
        self._back_btn.clicked.connect(self._back_to_follows)
        self._back_btn.setVisible(False)
        bottom.addWidget(self._back_btn)
        self._status = QLabel("")
        self._status.setObjectName("PageStatus")
        bottom.addWidget(self._status, 1)
        refresh = QPushButton("刷新")
        refresh.setObjectName("PageGhostButton")
        refresh.setCursor(Qt.PointingHandCursor)
        refresh.clicked.connect(self.refresh)
        bottom.addWidget(refresh)
        v.addLayout(bottom)

        self._root = root
        # 关注列表: 带按钮的用户行容器 + 滚动
        from PySide6.QtWidgets import QScrollArea
        self._follow_host = QWidget()
        self._follow_lay = QVBoxLayout(self._follow_host)
        self._follow_lay.setContentsMargins(0, 0, 0, 0)
        self._follow_lay.setSpacing(6)
        self._follow_lay.addStretch()
        self._follow_scroll = QScrollArea()
        self._follow_scroll.setWidgetResizable(True)
        self._follow_scroll.setFrameShape(QScrollArea.NoFrame)
        self._follow_scroll.setWidget(self._follow_host)
        self._follow_tab_idx = self._tabs.addTab(
            self._follow_scroll, "关注列表")
        # 用户作品页签 (从关注行「查看作品」进入, 平时隐藏)
        self._user_works_page = WorkGridPage()
        self._user_works_page.download_requested.connect(self._download)
        self._user_works_tab_idx = self._tabs.addTab(
            self._user_works_page, "用户作品")
        self._tabs.setTabVisible(self._user_works_tab_idx, False)
        self._tabs.setCurrentIndex(0)
        # 页签切换 → 自动按需加载
        self._tabs.currentChanged.connect(lambda _i: self.refresh())

    # ---------------- 数据入口 ----------------

    def open_platform(self, platform: str, sec_uid: str = "",
                      profile: dict | None = None):
        """切换平台并刷新 (主窗口在 _select_platform 时调用)。"""
        self._platform = platform
        self._sec_uid = sec_uid
        if profile:
            self._author.show_current_user(profile)
        self.setWindowTitle(f"内嵌浏览器 · {_pn(platform)}")
        self._back_to_follows()
        self._tabs.setCurrentIndex(0)
        self.refresh()

    def refresh(self):
        """按当前页签拉取对应数据。"""
        cookie = self._cm.get(self._platform)
        if not (cookie and cookie.strip()):
            hint = f"{_pn(self._platform)} 未配置 Cookie, 请先登录"
            self._status.setText(hint)
            self._author.show_placeholder(
                _pn(self._platform), "未配置 Cookie (请先登录)")
            self._my_works_page.set_works([], title="我的作品")
            self._fav_page.set_works([], title="收藏列表")
            self._set_follows([])
            return
        idx = self._tabs.currentIndex()
        if idx == 0:
            self._load(self._my_works_page, "my_works")
        elif idx == self._follow_tab_idx:
            self._load(None, "following")
        elif idx == self._user_works_tab_idx and self._sec_uid:
            self._load(self._user_works_page, "user_works")

    # ---------------- 加载 ----------------

    def _load(self, page, kind: str):
        self._status.setText("加载中...")
        task = _BrowseTask(kind, self._sec_uid,
                           self._cm.get(self._platform) or "", self._platform)
        task.signals.done.connect(
            lambda items, p=page, k=kind: self._on_loaded(items, p, k))
        task.signals.failed.connect(
            lambda err: self._status.setText(f"✗ {err[:80]}"))
        self._tasks.append(task)
        self._pool.start(task)

    def _on_loaded(self, items: list, page, kind: str):
        self._status.setText("")
        if kind == "following":
            self._set_follows(items)
            return
        if page is None:
            return
        titles = {"my_works": "我的作品", "user_works": "用户作品",
                  "favorites": "收藏列表"}
        page.set_works(items, title=titles.get(kind, "作品列表"))

    # ---------------- 关注列表 ----------------

    def _set_follows(self, users: list):
        while self._follow_lay.count():
            it = self._follow_lay.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()
        self._follow_lay.addStretch()
        if not users:
            empty = QLabel("暂无关注数据 (需要登录 Cookie, 且平台支持关注列表)")
            empty.setObjectName("EmptyState")
            empty.setWordWrap(True)
            empty.setAlignment(Qt.AlignCenter)
            self._follow_lay.insertWidget(0, empty)
            return
        for i, u in enumerate(users):
            row = _BrowseUserRow(u, odd=(i % 2 == 1))
            row.open_works.connect(self._open_user_works)
            self._follow_lay.insertWidget(self._follow_lay.count() - 1, row)

    def _open_user_works(self, user: dict):
        sec = user.get("sec_user_id") or user.get("user_id") or ""
        if not sec:
            self._status.setText("✗ 该用户缺少 sec_user_id, 无法拉取作品")
            return
        self._sec_uid = sec
        self._tabs.setTabVisible(self._user_works_tab_idx, True)
        self._tabs.setCurrentIndex(self._user_works_tab_idx)
        self._back_btn.setVisible(True)
        self._user_works_page.set_works(
            [], title=f"{user.get('nickname', '?')} 的作品")
        self._load(self._user_works_page, "user_works")

    def _back_to_follows(self):
        self._sec_uid = ""
        self._tabs.setTabVisible(self._user_works_tab_idx, False)
        self._tabs.setCurrentIndex(self._follow_tab_idx)
        self._back_btn.setVisible(False)

    # ---------------- 下载 ----------------

    def _download(self, ids: list):
        if ids:
            self.download_requested.emit(ids)
