"""内嵌数据表格页 —— 评论/搜索结果等任意数据 (继承 ListPageBase 公共设计)。"""
from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel
from .base_page import ListPageBase


class _Row(QFrame):
    """单行: 多列单元格 (斑马纹经 zebra 属性由主题控制)。"""

    def __init__(self, cells: list, odd: bool, weights: list | None = None,
                 parent=None):
        super().__init__(parent)
        self.setObjectName("TableRow")
        self.setProperty("zebra", "odd" if odd else "even")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(12)
        for i, text in enumerate(cells):
            cell = QLabel(str(text))
            cell.setObjectName("TableCell")
            cell.setWordWrap(True)
            cell.setTextInteractionFlags(Qt.TextSelectableByMouse)
            w = (weights[i] if weights and i < len(weights) else 1)
            lay.addWidget(cell, w)


class DataTablePage(ListPageBase):
    """通用数据表格内嵌页 (支持 CSV/JSON 导出)。"""

    def __init__(self, title: str = "数据", parent=None):
        super().__init__(title=title, parent=parent)
        self._weights: list | None = None
        self._headers: list[str] = []
        self._rows: list[list] = []
        # 表头 (固定在内容区顶部)
        self._header = QHBoxLayout()
        self._header.setContentsMargins(12, 6, 12, 6)
        self._header.setSpacing(12)
        hdr_w = QFrame()
        hdr_w.setObjectName("TableHeader")
        hdr_w.setLayout(self._header)
        self.add_content(hdr_w)

    def set_rows(self, headers: list, rows: list,
                 weights: list | None = None, title: str | None = None):
        if title is not None:
            self.set_title(title)
        self._weights = weights
        self._headers = [str(h) for h in headers]
        self._rows = [list(r) for r in rows]
        # 表头
        while self._header.count():
            it = self._header.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()
        for i, h in enumerate(headers):
            lbl = QLabel(str(h))
            lbl.setObjectName("TableHeaderText")
            wgt = (weights[i] if weights and i < len(weights) else 1)
            self._header.addWidget(lbl, wgt)
        # 行 (先清掉旧行, 保留表头控件)
        for i in range(self._content.count() - 1, 0, -1):
            it = self._content.itemAt(i)
            w = it.widget()
            if w and w.objectName() != "TableHeader":
                self._content.takeAt(i)
                w.deleteLater()
        for i, cells in enumerate(rows):
            self.add_content(_Row(list(cells), odd=(i % 2 == 1),
                                  weights=weights))
        self.set_count(f"共 {len(rows)} 条 · 可导出")

    # ---------------- 导出 ----------------

    def _export(self):
        """导出当前表格数据 (CSV/JSON, 系统保存对话框)。"""
        if not self._rows:
            return
        from shared.flow.export import export_dialog
        export_dialog(self, self._headers, self._rows,
                      suggested_name=(self._title.text() if hasattr(self, "_title")
                                      else "export") or "export")
