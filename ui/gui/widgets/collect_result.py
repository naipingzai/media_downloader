"""输出结果展示 — 下载状态/来源/路径 或 采集数据。"""
from PySide6.QtCore import Qt
from shared.core.i18n import t
from PySide6.QtWidgets import (
    QHeaderView, QLabel, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
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
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setAlignment(Qt.AlignTop)
        self._title = QLabel(t("output_result"))
        self._title.setObjectName("SectionTitle")
        self._title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout.addWidget(self._title)
        self._table = QTableWidget(self)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.verticalHeader().setVisible(False)
        self._table.setWordWrap(True)
        self._table.setColumnCount(3)
        self._table.setRowCount(0)
        self._table.setHorizontalHeaderLabels([t("status_col"), t("source_col"), t("path_col")])
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
        self._table.setItem(row, 2, QTableWidgetItem(path))

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
                self._table.setItem(i, j, QTableWidgetItem(str(val)))

    def show_hot_list(self, data):
        self.show_data(t("hot_list"), [t("rank"), t("keyword"), t("hot_value")],
                       [[d["rank"], d["word"], d["hot_value"]] for d in data])

    def show_comments(self, data):
        self.show_data(t("comment_data"), [t("user"), t("content"), t("likes")],
                       [[d["user"], d["text"][:50], d["digg_count"]] for d in data])

    def show_search(self, data):
        self.show_data(t("search_result"), [t("title_field"), t("author"), t("likes")],
                       [[d["title"][:40], d["author"], d["digg_count"]] for d in data])

    def show_user(self, data):
        self.show_data(t("account_info"), [t("title_field"), t("yes")], [
            [t("nickname"), data.get("nickname", "")],
            ["UID", data.get("uid", "")],
            [t("followers"), data.get("follower_count", 0)],
            [t("works"), data.get("aweme_count", 0)],
            [t("signature"), data.get("signature", "")],
        ])
