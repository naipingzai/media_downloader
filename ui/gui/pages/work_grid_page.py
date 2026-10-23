"""内嵌作品网格页 —— 替代 WorkGridDialog。

显示纵向卡片 (封面 → 描述 → 链接), 一行 3 个, 可勾选 → 触发「下载所选」回调。
"""
from __future__ import annotations
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)
from ..widgets.cover_label import CoverLabel
from ..widgets.work_card import InfoRow, build_work_rows
from ..cover_loader import CoverLoader
from shared.core import norm_work


class _VerticalCard(QFrame):
    """单张作品卡: 封面 + 描述 + 链接。点击切换勾选。"""

    def __init__(self, work: dict, parent=None):
        super().__init__(parent)
        self.setObjectName("VerticalWorkCard")
        work = dict(work or {})
        if not work.get("cover_url"):
            work = {**norm_work(work, work.get("platform", "")), **work}
        self._work_id = str(work.get("work_id", ""))
        self._checked = True
        self._cover_url = (work.get("cover_url") or work.get("cover")
                           or work.get("pic") or "")
        self._refresh_style()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(6)
        # 封面
        self._cover = CoverLabel("封面")
        self._cover.setMinimumSize(230, 155)
        if self._cover_url:
            loader = CoverLoader.instance()
            loader.cover_ready.connect(self._on_cover_ready)
            cached = loader.request(self._cover_url)
            if cached is not None:
                self._cover.set_source_pixmap(cached)
        lay.addWidget(self._cover)
        # 标题 (统一布局: 完整可选中)
        desc = (work.get("title") or work.get("desc") or "(无描述)").strip()
        desc_lbl = QLabel(desc)
        desc_lbl.setWordWrap(True)
        desc_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        desc_lbl.setStyleSheet("color: #e2e8f0; font-weight: bold;"
                               " font-size: 14px;")
        lay.addWidget(desc_lbl)
        # 标准信息行 (与作品资料卡 InfoRow 一致)
        for label, value in build_work_rows(work)[:5]:
            lay.addWidget(InfoRow(label, value))

    def _on_cover_ready(self, url: str, pix: QPixmap):
        if url == self._cover_url:
            self._cover.set_source_pixmap(pix)

    @property
    def work_id(self) -> str:
        return self._work_id

    @property
    def is_checked(self) -> bool:
        return self._checked

    def set_checked(self, v: bool):
        self._checked = bool(v)
        self._refresh_style()

    def _refresh_style(self):
        border = "#38bdf8" if self._checked else "#334155"
        bg = "#22314a" if self._checked else "#1e293b"
        self.setStyleSheet(
            f"QFrame#VerticalWorkCard {{ background: {bg};"
            f" border: 2px solid {border}; border-radius: 8px; }}"
            "QLabel { background: transparent; border: none;"
            " color: #e2e8f0; font-size: 14px; }")

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            self.set_checked(not self._checked)
        super().mousePressEvent(ev)


class WorkGridPage(QWidget):
    """作品网格内嵌页。"""
    download_requested = Signal(list)  # 选中的 work_id 列表

    COLS = 3

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cards: list[_VerticalCard] = []
        self._items: list[dict] = []
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        # 顶部标题
        hdr = QHBoxLayout()
        self._title_label = QLabel("")
        self._title_label.setObjectName("PageTitle")
        hdr.addWidget(self._title_label)
        hdr.addStretch()
        root.addLayout(hdr)

        # 滚动网格
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        container = QWidget()
        self._grid = QGridLayout(container)
        self._grid.setSpacing(10)
        self._grid.setContentsMargins(2, 2, 2, 2)
        for i in range(self.COLS):
            self._grid.setColumnStretch(i, 1)
        scroll.setWidget(container)
        root.addWidget(scroll, 1)

        # 底部按钮
        bottom = QHBoxLayout()
        bottom.setSpacing(8)
        self._status_label = QLabel("就绪")
        self._status_label.setObjectName("PageStatus")
        bottom.addWidget(self._status_label)
        bottom.addStretch()
        for text, slot in (("全选", lambda: self._check_all(True)),
                           ("全不选", lambda: self._check_all(False)),
                           ("反选", self._invert)):
            b = QPushButton(text)
            b.setObjectName("PageGhostButton")
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(slot)
            bottom.addWidget(b)
        self._dl_btn = QPushButton("下载所选 (0)")
        self._dl_btn.setObjectName("PagePrimaryButton")
        self._dl_btn.setCursor(Qt.PointingHandCursor)
        self._dl_btn.setEnabled(False)
        self._dl_btn.clicked.connect(self._on_download)
        bottom.addWidget(self._dl_btn)
        root.addLayout(bottom)

    def set_works(self, items: list[dict], title: str = "作品列表"):
        """填充作品网格。"""
        # 清空
        while self._grid.count():
            it = self._grid.takeAt(0)
            w = it.widget()
            if w:
                w.setParent(None)
                w.deleteLater()
        self._cards.clear()
        self._items = list(items)
        for i, work in enumerate(items):
            card = _VerticalCard(work)
            self._cards.append(card)
            self._grid.addWidget(card, i // self.COLS, i % self.COLS)
        self._title_label.setText(f"{title} · 共 {len(items)} 项")
        self._refresh_count()

    def _check_all(self, state: bool):
        for c in self._cards:
            c.set_checked(state)
        self._refresh_count()

    def _invert(self):
        for c in self._cards:
            c.set_checked(not c.is_checked)
        self._refresh_count()

    def _refresh_count(self):
        n_sel = sum(1 for c in self._cards if c.is_checked)
        self._dl_btn.setText(f"下载所选 ({n_sel})")
        self._dl_btn.setEnabled(n_sel > 0)
        self._status_label.setText(f"已选 {n_sel} / {len(self._cards)}")

    def selected_ids(self) -> list[str]:
        return [c.work_id for c in self._cards if c.is_checked]

    def _on_download(self):
        ids = self.selected_ids()
        if ids:
            self.download_requested.emit(ids)
