"""解析结果卡片（作品资料卡）— 左半封面 + 右半详情。"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from shared.core.i18n import t
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget,
)
from ..cover_loader import CoverLoader
from .cover_label import CoverLabel
from .work_card import build_work_html


class VideoInfoWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Panel")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._cur_url = ""
        loader = CoverLoader.instance()
        loader.cover_ready.connect(self._on_cover_ready)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(2, 2, 2, 2)
        outer.setSpacing(0)
        header = QHBoxLayout()
        header.setContentsMargins(14, 10, 14, 4)
        header.setSpacing(6)
        self._title_label = QLabel(t("video_info"))
        self._title_label.setObjectName("SectionTitle")
        header.addWidget(self._title_label)
        self._state = QLabel("(" + t("waiting_parse") + ")")
        self._state.setObjectName("Caption")
        header.addWidget(self._state)
        header.addStretch()
        outer.addLayout(header)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        self._inner_layout = QHBoxLayout(inner)
        self._inner_layout.setContentsMargins(14, 4, 14, 12)
        self._inner_layout.setSpacing(16)

        # 左半：封面区域（自适应占满左侧一半，按比例完整显示不裁剪）
        cover_wrap = QVBoxLayout()
        cover_wrap.setSpacing(2)
        self._cover = CoverLabel("封面")
        self._cover.setMinimumSize(160, 100)
        cover_wrap.addWidget(self._cover)
        self._inner_layout.addLayout(cover_wrap, 1)

        # 右半：信息文本
        right = QVBoxLayout()
        right.setSpacing(4)
        self._info = QLabel(t("parse_hint"))
        self._info.setWordWrap(True)
        self._info.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._info.setStyleSheet("color: #64748b;")
        self._info.setAlignment(Qt.AlignTop)
        right.addWidget(self._info)
        self._detail = QLabel("")
        self._detail.setWordWrap(True)
        self._detail.setTextFormat(Qt.RichText)
        self._detail.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._detail.setAlignment(Qt.AlignTop)
        self._detail.setVisible(False)
        right.addWidget(self._detail)
        right.addStretch()
        self._inner_layout.addLayout(right, 1)

        scroll.setWidget(inner)
        outer.addWidget(scroll)

    def _set_cover_url(self, url: str):
        self._cur_url = url or ""
        if not url:
            self._cover.show_placeholder("无封面")
            return
        # 尝试缓存
        cached = CoverLoader.instance().request(url)
        if cached is not None:
            self._apply_cover(cached)
        else:
            self._cover.show_placeholder("加载中")

    def _apply_cover(self, pix: QPixmap):
        self._cover.set_source_pixmap(pix)

    def _on_cover_ready(self, url: str, pixmap: QPixmap):
        if url == self._cur_url:
            self._apply_cover(pixmap)

    def show_work(self, work):
        self._state.setText("(" + t("parsed") + ")")
        self._state.setStyleSheet("color: #22c55e; font-weight: bold;")
        # 加载封面
        cover_url = work.get("cover_url") or work.get("cover") or work.get("pic") or ""
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
        self._detail.setText(build_work_html(work))
        self._detail.setVisible(True)
        self._info.setVisible(False)

    def show_empty(self):
        self._state.setText("(" + t("waiting_parse") + ")")
        self._state.setStyleSheet("color: #64748b;")
        self._detail.setVisible(False)
        self._info.setVisible(True)
        self._cur_url = ""
        self._cover.show_placeholder("封面")

    def show_error(self, msg):
        self._state.setText("(" + t("parse_failed") + ")")
        self._state.setStyleSheet("color: #ef4444; font-weight: bold;")
        self._info.setText(msg)
        self._info.setVisible(True)
        self._detail.setVisible(False)
