"""作品资料卡 — 封面在左 + 信息在右。

布局:
  ┌──────────────────────────────────────────────────┐
  │  标题 + 摘要 + 状态                               │
  ├────────────────────┬─────────────────────────────┤
  │      封面          │  详细资料 (滚动行列表)        │
  └────────────────────┴─────────────────────────────┘

样式全部由主题 QSS 提供 (`#VideoTitle` / `#VideoSubtitle` / `#VideoState` /
`#InfoRow*`), 组件内不写死颜色, 暗/亮主题与字号缩放均可生效。
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget,
)
from ..cover_loader import CoverLoader
from shared.core.format import format_count
from .cover_label import CoverLabel
from .work_card import InfoRow, build_full_work_rows


class VideoInfoWidget(QFrame):
    """作品资料卡 — 整个区域无边框 (外层卡片提供边框)。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("VideoInfoPanel")
        self._cur_url = ""
        self._author_url = ""
        self._work: dict = {}
        CoverLoader.instance().cover_ready.connect(self._on_cover_ready)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(8)

        # ===== 标题区: 大标题 + 摘要行 + 状态 =====
        self._title_label = QLabel("")
        self._title_label.setObjectName("VideoTitle")
        self._title_label.setWordWrap(True)
        self._title_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self._subtitle = QLabel("")
        self._subtitle.setObjectName("VideoSubtitle")
        self._subtitle.setWordWrap(True)
        self._subtitle.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self._state = QLabel("")
        self._state.setObjectName("VideoState")

        self._header_wrapped = QWidget()
        _hl = QVBoxLayout(self._header_wrapped)
        _hl.setContentsMargins(0, 0, 0, 0)
        _hl.setSpacing(3)
        _hl.addWidget(self._title_label)
        _hl.addWidget(self._subtitle)
        _hl.addWidget(self._state)
        outer.addWidget(self._header_wrapped)

        # ===== 主体: 左封面 + 右资料 =====
        self._body = QHBoxLayout()
        self._body.setContentsMargins(0, 0, 0, 0)
        self._body.setSpacing(12)

        # ---- 左: 封面 (随窗口缩放) ----
        self._cover = CoverLabel("")
        self._cover.setFixedSize(240, 320)
        self._body.addWidget(self._cover, 0, Qt.AlignTop)

        # ---- 右: 纯文本信息 (无详情行时的兜底) ----
        self._info = QLabel("")
        self._info.setObjectName("VideoMeta")
        self._info.setWordWrap(True)
        self._info.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._info.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self._info.setVisible(False)
        self._body.addWidget(self._info, 1)

        # ---- 右: 详情边框行 (滚动) ----
        self._detail_scroll = QScrollArea()
        self._detail_scroll.setWidgetResizable(True)
        self._detail_scroll.setFrameShape(QScrollArea.NoFrame)
        self._detail_container = QWidget()
        self._detail = QVBoxLayout(self._detail_container)
        self._detail.setContentsMargins(0, 0, 0, 0)
        self._detail.setSpacing(4)
        self._detail.addStretch()
        self._detail_scroll.setWidget(self._detail_container)
        self._detail_scroll.setVisible(False)
        self._body.addWidget(self._detail_scroll, 1)

        self._body_widget = QWidget()
        self._body_widget.setLayout(self._body)
        outer.addWidget(self._body_widget, 1)
        self._body_widget.setVisible(False)

    # ---------------- 封面 ----------------

    def _reset_cover(self):
        """清空封面显示 (不残留占位文字/背景)。"""
        self._cover.clear_cover()
        self._cover.setVisible(False)

    def _set_cover_url(self, url: str):
        # 与 CoverLoader 同源规范化，保证异步回调比对一致
        self._cur_url = CoverLoader.normalize_url(url)
        if not self._cur_url:
            self._reset_cover()
            return
        self._cover.setVisible(True)
        # set_source_url 内部自带缓存命中 + paintEvent 兜底，不依赖信号时机
        self._cover.set_source_url(self._cur_url)

    def _on_cover_ready(self, url: str, pix: QPixmap):
        if url == self._cur_url and not pix.isNull():
            self._cover.setVisible(True)
            self._cover.set_source_pixmap(pix)

    # ---------------- 对外属性 ----------------
    @property
    def author_url(self) -> str:
        return self._author_url

    @property
    def work(self) -> dict:
        """当前显示的作品 (无作品时为空 dict)。"""
        return self._work

    @property
    def cover_url(self) -> str:
        """当前封面地址 (无封面时为空串)。"""
        return self._cur_url

    # ---------------- 状态 ----------------

    def show_work(self, work):
        self._work = work or {}
        title = (work.get("title") or work.get("desc") or "").strip()
        self._title_label.setText(title or "未命名作品")
        self._title_label.setVisible(True)

        # 摘要行: 作者 · 时长 · 统计
        parts = []
        author = work.get("author_name") or ""
        if author:
            parts.append(f"作者 {author}")
        dur = work.get("duration") or 0
        try:
            dur = int(dur)
            if dur > 10000:
                dur //= 1000
        except (TypeError, ValueError):
            dur = 0
        if dur:
            parts.append(f"时长 {dur}s")
        for key, label in (("digg_count", "赞"), ("comment_count", "评"),
                           ("view_count", "播放")):
            v = work.get(key)
            if v not in (None, "", 0, "0"):
                parts.append(f"{label} {format_count(v)}")
        self._subtitle.setText(" · ".join(parts))
        self._subtitle.setVisible(bool(parts))
        self._state.setText("✓ 已解析")

        cover_url = (work.get("cover_url") or work.get("cover")
                     or work.get("pic") or "")
        if not cover_url:
            video = work.get("video") or {}
            for key in ("cover", "origin_cover", "dynamic_cover"):
                c = video.get(key)
                if isinstance(c, dict):
                    urls = c.get("url_list") or []
                    if urls:
                        cover_url = urls[0]
                        break
        self._set_cover_url(cover_url)

        # 重建详情行
        while self._detail.count():
            it = self._detail.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()
        self._detail.addStretch()
        for label, value in build_full_work_rows(work):
            self._detail.insertWidget(self._detail.count() - 1,
                                      InfoRow(label, value))
        self._detail_scroll.setVisible(True)
        self._info.setVisible(False)
        self._header_wrapped.setVisible(True)
        self._body_widget.setVisible(True)

        self._author_url = (work.get("author_url")
                            or work.get("author_share_url") or "")
        sec_uid = work.get("sec_user_id") or work.get("author_id", "")
        platform = work.get("platform", "")
        if not self._author_url and sec_uid:
            if platform == "douyin":
                self._author_url = f"https://www.douyin.com/user/{sec_uid}"
            elif platform == "bilibili" and work.get("author_mid"):
                self._author_url = f"https://space.bilibili.com/{work['author_mid']}"

    def show_empty(self):
        """空状态: 区域内不显示内容, 仅保留外层卡片。"""
        self._work = {}
        self._title_label.setVisible(False)
        self._subtitle.setVisible(False)
        self._state.setText("")
        self._detail_scroll.setVisible(False)
        self._info.setVisible(False)
        self._info.setText("")
        self._header_wrapped.setVisible(False)
        self._body_widget.setVisible(False)
        self._cur_url = ""
        self._author_url = ""
        self._reset_cover()

    def show_error(self, msg):
        """错误状态: 不显示错误文字, 错误信息走日志。"""
        self.show_empty()
