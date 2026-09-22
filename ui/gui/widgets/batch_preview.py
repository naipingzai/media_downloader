"""批量下载预览 — 封面/标题/基础信息 + 勾选后下载。"""
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QIcon, QImage, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QHBoxLayout, QHeaderView, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)
from shared.core.i18n import t

__all__ = ["BatchPreviewDialog"]


def _fmt_duration(sec) -> str:
    """秒 → h:mm:ss / m:ss。"""
    try:
        sec = int(sec or 0)
    except (TypeError, ValueError):
        return ""
    if sec <= 0:
        return ""
    h, m, s = sec // 3600, (sec % 3600) // 60, sec % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _cover_referer(url: str) -> str:
    """按封面域名设置防盗链 Referer。"""
    u = url.lower()
    if "douyin" in u or "douyinpic" in u:
        return "https://www.douyin.com/"
    if "kuaishou" in u or "ksurl" in u:
        return "https://www.kuaishou.com/"
    if "bilibili" in u or "hdslb" in u:
        return "https://www.bilibili.com/"
    if "xiaohongshu" in u or "xhscdn" in u or "rednote" in u:
        return "https://www.xiaohongshu.com/"
    return ""


class BatchPreviewDialog(QDialog):
    """展示批量抓取的作品列表（封面+标题+作者+时长+点赞），勾选后确认下载。

    items 每项至少含: work_id, title；可选 author_name, cover, duration,
    digg_count, extra(附加说明，如所属专辑)。
    """

    COL_CHECK, COL_COVER, COL_TITLE, COL_AUTHOR, COL_EXTRA = range(5)

    def __init__(self, items, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("batch_preview_title"))
        self.resize(880, 560)
        self._items = [it for it in (items or []) if it.get("work_id")]
        self._selected: set[str] = {str(it["work_id"]) for it in self._items}
        self._net = QNetworkAccessManager(self)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        # ── 顶栏：计数 + 快捷选择 ──
        top = QHBoxLayout()
        self._count_label = QLabel()
        self._count_label.setObjectName("Caption")
        top.addWidget(self._count_label)
        top.addStretch()
        btn_all = QPushButton(t("batch_select_all"))
        btn_none = QPushButton(t("batch_select_none"))
        btn_invert = QPushButton(t("batch_select_invert"))
        for b in (btn_all, btn_none, btn_invert):
            top.addWidget(b)
        root.addLayout(top)

        # ── 列表 ──
        self._table = QTableWidget(self)
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels([
            "", t("cover"), t("title_field"), t("author"), t("duration_col"),
        ])
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setShowGrid(False)
        self._table.setAlternatingRowColors(False)
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(self.COL_CHECK, QHeaderView.Fixed)
        hdr.setSectionResizeMode(self.COL_COVER, QHeaderView.Fixed)
        hdr.setSectionResizeMode(self.COL_TITLE, QHeaderView.Stretch)
        hdr.setSectionResizeMode(self.COL_AUTHOR, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(self.COL_EXTRA, QHeaderView.ResizeToContents)
        self._table.setColumnWidth(self.COL_CHECK, 36)
        self._table.setColumnWidth(self.COL_COVER, 110)
        root.addWidget(self._table, 1)

        # ── 底栏：确认下载 ──
        bottom = QHBoxLayout()
        bottom.addStretch()
        cancel_btn = QPushButton(t("cancel"))
        cancel_btn.clicked.connect(self.reject)
        self._dl_btn = QPushButton()
        self._dl_btn.setObjectName("PrimaryButton")
        self._dl_btn.clicked.connect(self.accept)
        bottom.addWidget(cancel_btn)
        bottom.addWidget(self._dl_btn)
        root.addLayout(bottom)

        btn_all.clicked.connect(lambda: self._check_all(Qt.Checked))
        btn_none.clicked.connect(lambda: self._check_all(Qt.Unchecked))
        btn_invert.clicked.connect(self._invert)
        self._table.itemChanged.connect(self._on_item_changed)

        self._fill()

    # ── 数据填充 ──

    def _fill(self):
        self._table.setRowCount(len(self._items))
        for row, it in enumerate(self._items):
            check = QTableWidgetItem()
            check.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            check.setCheckState(
                Qt.Checked if str(it["work_id"]) in self._selected else Qt.Unchecked)
            check.setData(Qt.UserRole, str(it["work_id"]))
            self._table.setItem(row, self.COL_CHECK, check)

            cover_item = QTableWidgetItem()
            cover_item.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(row, self.COL_COVER, cover_item)

            title = str(it.get("title") or "").replace("\n", " ")
            title_item = QTableWidgetItem(title or "-")
            tip = " / ".join(x for x in (
                str(it.get("extra") or ""), str(it.get("author_name") or "")) if x)
            if tip:
                title_item.setToolTip(tip)
            self._table.setItem(row, self.COL_TITLE, title_item)
            self._table.setItem(row, self.COL_AUTHOR,
                                QTableWidgetItem(str(it.get("author_name") or "")))

            bits = []
            dur = _fmt_duration(it.get("duration"))
            if dur:
                bits.append(dur)
            digg = it.get("digg_count")
            if digg:
                bits.append(f"👍{digg}")
            extra = str(it.get("extra") or "")
            if extra and not bits:
                bits.append(extra)
            self._table.setItem(row, self.COL_EXTRA, QTableWidgetItem("  ".join(bits)))

            cover = str(it.get("cover") or "")
            if cover:
                self._load_cover(row, cover)
        self._refresh_count()

    def _load_cover(self, row: int, url: str):
        req = QNetworkRequest(QUrl(url))
        referer = _cover_referer(url)
        if referer:
            req.setRawHeader(b"Referer", referer.encode())
        req.setRawHeader(b"User-Agent", b"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        req.setTransferTimeout(8000)
        reply = self._net.get(req)
        reply.finished.connect(lambda r=reply, rw=row: self._on_cover(r, rw))

    def _on_cover(self, reply, row: int):
        try:
            if reply.error() == reply.NoError and row < self._table.rowCount():
                img = QImage.fromData(reply.readAll())
                if not img.isNull():
                    pix = QPixmap.fromImage(img).scaled(
                        96, 54, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                    self._table.item(row, self.COL_COVER).setIcon(QIcon(pix))
        except Exception:
            pass
        finally:
            reply.deleteLater()

    # ── 选择逻辑 ──

    def _on_item_changed(self, item):
        if item.column() != self.COL_CHECK:
            return
        wid = item.data(Qt.UserRole)
        if not wid:
            return
        if item.checkState() == Qt.Checked:
            self._selected.add(str(wid))
        else:
            self._selected.discard(str(wid))
        self._refresh_count()

    def _check_all(self, state: int):
        self._table.blockSignals(True)
        for row in range(self._table.rowCount()):
            it = self._table.item(row, self.COL_CHECK)
            if it:
                it.setCheckState(state)
        self._table.blockSignals(False)
        if state == Qt.Checked:
            self._selected = {str(x["work_id"]) for x in self._items}
        else:
            self._selected = set()
        self._refresh_count()

    def _invert(self):
        self._table.blockSignals(True)
        for row in range(self._table.rowCount()):
            it = self._table.item(row, self.COL_CHECK)
            if it:
                it.setCheckState(
                    Qt.Unchecked if it.checkState() == Qt.Checked else Qt.Checked)
        self._table.blockSignals(False)
        self._selected = {
            str(self._table.item(r, self.COL_CHECK).data(Qt.UserRole))
            for r in range(self._table.rowCount())
            if self._table.item(r, self.COL_CHECK)
            and self._table.item(r, self.COL_CHECK).checkState() == Qt.Checked
        }
        self._refresh_count()

    def _refresh_count(self):
        n_sel, n_all = len(self._selected), len(self._items)
        self._count_label.setText(t("batch_select_hint").format(count=n_all, selected=n_sel))
        self._dl_btn.setText(t("batch_download_selected").format(count=n_sel))
        self._dl_btn.setEnabled(n_sel > 0)

    def selected_ids(self) -> list[str]:
        """按列表原顺序返回勾选的 work_id。"""
        return [str(it["work_id"]) for it in self._items
                if str(it["work_id"]) in self._selected]
