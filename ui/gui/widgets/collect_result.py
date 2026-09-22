"""输出结果展示 — 下载状态/来源/路径 或 采集数据。"""
from PySide6.QtCore import Qt
from shared.core.i18n import t
from PySide6.QtWidgets import (
    QHBoxLayout, QHeaderView, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget, QAbstractItemView,
)


class OutputResultView(QWidget):
    """输出结果面板：
    - 下载: 显示 状态/来源/路径
    - 采集: 显示采集数据表格
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Panel")
        self.setAttribute(Qt.WA_StyledBackground, True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(0)

        # 标题栏 + 清除按钮
        hdr = QHBoxLayout()
        hdr.setContentsMargins(14, 10, 14, 4)
        hdr.setSpacing(6)
        self._title = QLabel(t("output_result"))
        self._title.setObjectName("SectionTitle")
        self._title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        hdr.addWidget(self._title)
        hdr.addStretch()
        clear_btn = QPushButton("清除")
        clear_btn.setObjectName("SubtleButton")
        clear_btn.clicked.connect(self.show_empty)
        hdr.addWidget(clear_btn)
        layout.addLayout(hdr)

        self._table = QTableWidget(self)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.verticalHeader().setVisible(False)
        self._table.setWordWrap(True)
        self._table.setAlternatingRowColors(True)
        self._table.setColumnCount(3)
        self._table.setRowCount(0)
        self._table.setHorizontalHeaderLabels([t("status_col"), t("source_col"), t("path_col")])
        # 列宽模式：状态列固定，来源列自适应，路径列拉伸
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        # 允许水平滚动（防止内容被截断）
        self._table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self._table.setSizeAdjustPolicy(QAbstractItemView.AdjustToContents)
        layout.addWidget(self._table)

    def show_empty(self):
        self._title.setText(t("output_result"))
        self._table.setRowCount(0)
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels([t("status_col"), t("source_col"), t("path_col")])

    def append_download(self, status, source, path=""):
        """追加一条下载结果。"""
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setItem(row, 0, QTableWidgetItem(status))
        self._table.setItem(row, 1, QTableWidgetItem(source))
        path_item = QTableWidgetItem(path)
        path_item.setToolTip(path)
        self._table.setItem(row, 2, path_item)

    def set_download_results(self, files, title=t("download_ok")):
        """批量设置下载结果。"""
        self._title.setText(title)
        self._table.setRowCount(0)
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels([t("status_col"), t("source_col"), t("path_col")])
        for f in files:
            self.append_download("✓ 完成", "", f)

    def set_download_log(self, log_lines, title=t("download_ok")):
        """从下载日志中提取结果。"""
        self._title.setText(title)
        self._table.setRowCount(0)
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels([t("status_col"), t("source_col"), t("path_col")])
        for line in log_lines:
            if "✓" in line:
                self.append_download("✓ 完成", "", line.strip())
            elif "✗" in line:
                self.append_download("✗ 失败", "", line.strip())

    def show_data(self, title, headers, rows):
        self._title.setText(title)
        self._table.setRowCount(0)
        self._table.setColumnCount(len(headers))
        self._table.setHorizontalHeaderLabels(headers)
        self._table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, val in enumerate(row):
                item = QTableWidgetItem(str(val))
                item.setToolTip(str(val))
                self._table.setItem(i, j, item)
        # 根据列数动态设置列宽模式
        header = self._table.horizontalHeader()
        for c in range(len(headers)):
            header.setSectionResizeMode(c, QHeaderView.ResizeToContents)
        if len(headers) > 0:
            header.setSectionResizeMode(len(headers) - 1, QHeaderView.Stretch)

    def show_hot_list(self, data):
        self.show_data(t("hot_list"), [t("rank"), t("keyword"), t("hot_value")],
                       [[d["rank"], d["word"], d["hot_value"]] for d in data])

    def show_comments(self, data):
        self.show_data(t("comment_data"), [t("user"), t("content"), t("likes")],
                       [[d["user"], d["text"][:80], d["digg_count"]] for d in data])

    def show_search(self, data):
        self.show_data(t("search_result"), [t("title_field"), t("author"), t("likes")],
                       [[d["title"][:60], d["author"], d["digg_count"]] for d in data])

    def show_user(self, data):
        self.show_data(t("account_info"), [t("title_field"), t("yes")], [
            [t("nickname"), data.get("nickname", "")],
            ["UID", data.get("uid", "")],
            [t("followers"), data.get("follower_count", 0)],
            [t("works"), data.get("aweme_count", 0)],
            [t("signature"), data.get("signature", "")],
        ])
