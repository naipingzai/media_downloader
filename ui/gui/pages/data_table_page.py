"""内嵌数据表格页 —— 替代 DataTableDialog。

显示评论 / 搜索结果 / 热榜 / 账号资料 等任意 dict / list 结构数据。
"""
from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget,
)


class _Row(QFrame):
    """单行: 多列单元格。"""

    def __init__(self, cells: list, odd: bool, weights: list | None = None,
                 parent=None):
        super().__init__(parent)
        self.setObjectName("TableRow")
        bg = "#16213a" if odd else "#1e293b"
        self.setStyleSheet(
            f"QFrame#TableRow {{ background: {bg};"
            " border: 1px solid #334155; border-radius: 6px; }"
            "QLabel { background: transparent; border: none; }")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(12)
        for i, text in enumerate(cells):
            cell = QLabel(str(text))
            cell.setWordWrap(True)
            cell.setTextInteractionFlags(Qt.TextSelectableByMouse)
            cell.setStyleSheet(
                "color: #cbd5e1; font-size: 14px;")
            w = (weights[i] if weights and i < len(weights) else 1)
            lay.addWidget(cell, w)


class DataTablePage(QWidget):
    """通用数据表格内嵌页。"""

    def __init__(self, title: str = "数据", parent=None):
        super().__init__(parent)
        self._weights: list | None = None
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        hdr = QHBoxLayout()
        self._title = QLabel(title)
        self._title.setObjectName("PageTitle")
        hdr.addWidget(self._title)
        hdr.addStretch()
        self._count = QLabel("")
        self._count.setObjectName("PageStatus")
        hdr.addWidget(self._count)
        root.addLayout(hdr)

        # 表头
        self._header = QWidget()
        self._header_lay = QHBoxLayout(self._header)
        self._header_lay.setContentsMargins(12, 6, 12, 6)
        self._header_lay.setSpacing(12)
        root.addWidget(self._header)

        # 行
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        container = QWidget()
        self._rows_lay = QVBoxLayout(container)
        self._rows_lay.setContentsMargins(0, 0, 0, 0)
        self._rows_lay.setSpacing(6)
        self._rows_lay.addStretch()
        scroll.setWidget(container)
        root.addWidget(scroll, 1)

    def set_rows(self, headers: list, rows: list,
                 weights: list | None = None, title: str | None = None):
        if title is not None:
            self._title.setText(title)
        self._weights = weights
        # 表头
        while self._header_lay.count():
            it = self._header_lay.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()
        for i, h in enumerate(headers):
            lbl = QLabel(str(h))
            lbl.setStyleSheet(
                "color: #38bdf8; font-size: 14px; font-weight: bold;")
            wgt = (weights[i] if weights and i < len(weights) else 1)
            self._header_lay.addWidget(lbl, wgt)
        # 行
        while self._rows_lay.count():
            it = self._rows_lay.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()
        self._rows_lay.addStretch()
        for i, cells in enumerate(rows):
            self._rows_lay.insertWidget(
                self._rows_lay.count() - 1,
                _Row(list(cells), odd=(i % 2 == 1), weights=weights))
        self._count.setText(f"共 {len(rows)} 条")
