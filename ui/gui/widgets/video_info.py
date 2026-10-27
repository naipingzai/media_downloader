"""作品资料卡 — 封面在左 + 信息在右。

布局:
  ┌──────────────────────────────────────────────────┐  ← 大框 (1 个)
  │  标题 + 状态                                     │
  ├────────────────────┬─────────────────────────────┤
  │                    │                             │
  │       封面         │  详细资料                    │
  │     (左侧, 无框)  │   (右侧, 无框)               │
  │                    │                             │
  └────────────────────┴─────────────────────────────┘
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
    """作品资料卡 — 整个区域有边框, 内部封面/信息无边框。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("VideoInfoPanel")
        # 无边框 (由外层 SectionPanel 提供)
        self.setStyleSheet(
            "#VideoInfoPanel { background: transparent; border: none; }")
        self._cur_url = ""
        self._author_url = ""
        self._work: dict = {}
        loader = CoverLoader.instance()
        loader.cover_ready.connect(self._on_cover_ready)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(8)

        # ===== 标题区: 大标题 + 摘要行 + 状态 (有作品时才显示) =====
        self._title_label = QLabel("")
        self._title_label.setWordWrap(True)
        self._title_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._title_label.setStyleSheet(
            "color: #e2e8f0; font-size: 15px; font-weight: bold;"
            " background: transparent; border: none;")
        self._subtitle = QLabel("")
        self._subtitle.setWordWrap(True)
        self._subtitle.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._subtitle.setStyleSheet(
            "color: #94a3b8; font-size: 12px;"
            " background: transparent; border: none;")
        self._state = QLabel("")
        self._state.setStyleSheet(
            "color: #22c55e; font-weight: bold;"
            " background: transparent; border: none;")
        self._header_wrapped = QWidget()
        _hl = QVBoxLayout(self._header_wrapped)
        _hl.setContentsMargins(0, 0, 0, 0)
        _hl.setSpacing(3)
        _hl.addWidget(self._title_label)
        _hl.addWidget(self._subtitle)
        _hl.addWidget(self._state)
        outer.addWidget(self._header_wrapped)

        # ===== 主体: 左侧封面 + 右侧资料 (内部均无边框) =====
        self._body = QHBoxLayout()
        self._body.setContentsMargins(0, 0, 0, 0)
        self._body.setSpacing(12)

        # ---- 左: 封面 (无边框/无背景) ----
        self._cover = CoverLabel("")
        self._cover.setFixedSize(260, 340)
        self._cover.setStyleSheet("background: transparent; border: none;")
        self._body.addWidget(self._cover, 0, Qt.AlignTop)

        # ---- 右: 信息 (无边框/无背景) ----
        self._info = QLabel("")
        self._info.setWordWrap(True)
        self._info.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._info.setStyleSheet(
            "color: #94a3b8; font-size: 14px;"
            " background: transparent; border: none;")
        self._info.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self._info.setVisible(False)
        self._body.addWidget(self._info, 1)

        # 详情: 边框行列表 (滚动)
        self._detail_scroll = QScrollArea()
        self._detail_scroll.setWidgetResizable(True)
        self._detail_scroll.setFrameShape(QScrollArea.NoFrame)
        self._detail_scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }")
        self._detail_container = QWidget()
        self._detail_container.setStyleSheet("background: transparent;")
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

    def _set_cover_url(self, url: str):
        self._cur_url = url or ""
        if not url:
            # 无封面: 不显示任何文字/边框/背景
            self._cover.setStyleSheet("background: transparent; border: none;")
            self._cover.setText("")
            self._cover.show_placeholder("")
            return
        cached = CoverLoader.instance().request(url)
        if cached is not None:
            self._apply_cover(cached)
        else:
            self._cover.setText("")

    def _apply_cover(self, pix: QPixmap):
        self._cover.setStyleSheet("background: transparent; border: none;")

    def _on_cover_ready(self, url: str, pix: QPixmap):
        if url == self._cur_url:
            self._apply_cover(pix)
            self._cover.set_source_pixmap(pix)

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


    def show_work(self, work):
        self._work = work or {}
        # 大标题 (完整, 可选中复制)
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
        self._state.setStyleSheet("color: #22c55e; font-weight: bold;"
                                  " background: transparent; border: none;")
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
        # 重建详情边框行
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
        """空状态: 整个大框内什么都不显示, 仅保留框本身。"""
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
        self._cover.setStyleSheet("background: transparent; border: none;")
        self._cover.setText("")
        self._cover.show_placeholder("")

    def show_error(self, msg):
        """错误状态: 不显示任何错误文字, 错误信息走日志。"""
        self._title_label.setVisible(False)
        self._subtitle.setVisible(False)
        self._state.setText("")
        self._info.setVisible(False)
        self._detail_scroll.setVisible(False)
        self._header_wrapped.setVisible(False)
        self._body_widget.setVisible(False)
        self._cur_url = ""
        self._cover.setStyleSheet("background: transparent; border: none;")
        self._cover.setText("")
        self._cover.show_placeholder("")
        self._info.setVisible(False)
