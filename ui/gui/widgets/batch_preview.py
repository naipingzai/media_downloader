"""批量下载预览 — 与作品资料卡一致的卡片式布局：左封面 + 右资料，点击卡片切换选中。"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)
from shared.core.i18n import t
from ..cover_loader import CoverLoader
from .work_card import WorkCardWidget

__all__ = ["BatchPreviewDialog"]


class BatchPreviewDialog(QDialog):
    """卡片式批量下载预览：每个作品一张卡片（左封面 + 右资料，与作品资料卡一致）。

    选中逻辑：
    - 点击卡片任意位置即可切换选中/取消（复选框同步）
    - 选中卡片显示高亮边框 + 右上角对勾角标
    - 顶栏提供 全选 / 全不选 / 反选 三个快捷按钮
    """

    def __init__(self, items, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("batch_preview_title"))
        self.resize(820, 680)
        self._items = [it for it in (items or []) if it.get("work_id")]
        self._cards: dict[str, WorkCardWidget] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        # 顶栏：统计 + 快捷选择按钮
        top = QHBoxLayout()
        top.setSpacing(8)
        self._count_label = QLabel()
        self._count_label.setStyleSheet("color: #94a3b8; font-size: 13px;")
        top.addWidget(self._count_label)
        top.addStretch()
        for text, fn in [(t("batch_select_all"), lambda: self._check_all(True)),
                         (t("batch_select_none"), lambda: self._check_all(False)),
                         (t("batch_select_invert"), self._invert)]:
            btn = QPushButton(text)
            btn.setObjectName("SubtleButton")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton { background: #334155; color: #e2e8f0; border: none;"
                " border-radius: 5px; padding: 6px 14px; font-size: 12px; }"
                "QPushButton:hover { background: #475569; }")
            btn.clicked.connect(fn)
            top.addWidget(btn)
        root.addLayout(top)

        # 提示语
        hint = QLabel("💡 点击卡片任意位置即可选中/取消，右上角对勾表示已选中")
        hint.setStyleSheet("color: #64748b; font-size: 12px;")
        root.addWidget(hint)

        # 滚动 + 卡片列表（与作品资料卡一致的卡片）
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        container = QWidget()
        self._list = QVBoxLayout(container)
        self._list.setSpacing(10)
        self._list.setContentsMargins(4, 4, 4, 4)

        loader = CoverLoader.instance()
        loader.cover_ready.connect(self._on_cover_ready)

        cover_urls = []
        for it in self._items:
            card = WorkCardWidget(it, checked=True)
            card.checked_changed.connect(lambda _id, _v: self._refresh_count())
            self._cards[card.work_id] = card
            self._list.addWidget(card)
            if card.cover_url:
                cover_urls.append((card, card.cover_url))
        self._list.addStretch()

        scroll.setWidget(container)
        root.addWidget(scroll, 1)

        # 底栏
        bottom = QHBoxLayout()
        bottom.setSpacing(10)
        bottom.addStretch()
        cancel_btn = QPushButton(t("cancel"))
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setStyleSheet(
            "QPushButton { background: #334155; color: #e2e8f0; border: none;"
            " border-radius: 6px; padding: 8px 18px; }"
            "QPushButton:hover { background: #475569; }")
        cancel_btn.clicked.connect(self.reject)
        self._dl_btn = QPushButton()
        self._dl_btn.setCursor(Qt.PointingHandCursor)
        self._dl_btn.setStyleSheet(
            "QPushButton { background: #3b82f6; color: white; border: none;"
            " border-radius: 6px; padding: 8px 18px; font-weight: bold; }"
            "QPushButton:hover { background: #2563eb; }"
            "QPushButton:disabled { background: #334155; color: #64748b; }")
        self._dl_btn.clicked.connect(self.accept)
        bottom.addWidget(cancel_btn)
        bottom.addWidget(self._dl_btn)
        root.addLayout(bottom)

        # 触发封面下载
        self._cover_map: dict[str, list[str]] = {}
        for card, url in cover_urls:
            self._cover_map.setdefault(url, []).append(card.work_id)
            cached = loader.request(url)
            if cached is not None:
                card.set_cover_pixmap(cached)

        self._refresh_count()

    def _on_cover_ready(self, url: str, pixmap: QPixmap):
        for wid in self._cover_map.get(url, []):
            card = self._cards.get(wid)
            if card:
                card.set_cover_pixmap(pixmap)

    def _check_all(self, state: bool):
        for c in self._cards.values():
            c.set_checked(state)
        self._refresh_count()

    def _invert(self):
        for c in self._cards.values():
            c.set_checked(not c.is_checked)
        self._refresh_count()

    def _refresh_count(self):
        n_sel = sum(1 for c in self._cards.values() if c.is_checked)
        n_all = len(self._cards)
        self._count_label.setText(t("batch_select_hint").format(count=n_all, selected=n_sel))
        self._dl_btn.setText(t("batch_download_selected").format(count=n_sel))
        self._dl_btn.setEnabled(n_sel > 0)

    def selected_ids(self) -> list[str]:
        return [it["work_id"] for it in self._items
                if self._cards.get(it["work_id"]) and self._cards[it["work_id"]].is_checked]
