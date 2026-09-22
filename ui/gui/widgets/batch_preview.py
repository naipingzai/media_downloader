"""批量下载预览 — 卡片式布局：封面 + 描述 + 勾选。"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)
from shared.core.i18n import t
from ..cover_loader import CoverLoader

__all__ = ["BatchPreviewDialog"]

CARD_W = 172
COVER_W = 160
COVER_H = 96


def _fmt_duration(sec) -> str:
    try:
        sec = int(sec or 0)
    except (TypeError, ValueError):
        return ""
    if sec <= 0:
        return ""
    h, m, s = sec // 3600, (sec % 3600) // 60, sec % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


class CardWidget(QFrame):
    """单个作品卡片：封面 + 标题/作者 + 勾选按钮。"""

    def __init__(self, item: dict, parent=None):
        super().__init__(parent)
        self._work_id = str(item.get("work_id", ""))
        self._cover_url = str(item.get("cover") or "")
        self._checked = True
        self.setObjectName("CardWidget")
        self.setFixedWidth(CARD_W)
        self.setStyleSheet(
            "#CardWidget { background: #1e293b; border: 1px solid #334155;"
            " border-radius: 8px; }")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(5)

        # 封面区域（固定尺寸，占位）
        self._cover = QLabel()
        self._cover.setFixedSize(COVER_W, COVER_H)
        self._cover.setAlignment(Qt.AlignCenter)
        self._cover.setText("加载中")
        self._cover.setStyleSheet(
            "background: #0f172a; color: #475569; border-radius: 6px; font-size: 11px;")
        layout.addWidget(self._cover)

        # 标题
        title = str(item.get("title") or "").replace("\n", " ").strip()
        self._title = QLabel(title or "(无标题)")
        self._title.setStyleSheet("color: #e2e8f0; font-size: 12px;")
        self._title.setWordWrap(False)
        self._title.setFixedWidth(COVER_W)
        # 超长标题省略
        fm = self._title.fontMetrics()
        elided = fm.elidedText(title or "(无标题)", Qt.ElideRight, COVER_W)
        self._title.setText(elided)
        self._title.setToolTip(title)
        layout.addWidget(self._title)

        # 作者 + 时长 + 点赞
        parts = []
        author = str(item.get("author_name") or "").strip()
        if author:
            parts.append(author)
        dur = _fmt_duration(item.get("duration"))
        if dur:
            parts.append(dur)
        digg = item.get("digg_count")
        if digg:
            parts.append(f"👍{digg}")
        extra = str(item.get("extra") or "").strip()
        sub = " · ".join(parts)
        if extra:
            sub = f"[{extra}] {sub}" if sub else f"[{extra}]"
        self._sub = QLabel(fm.elidedText(sub, Qt.ElideRight, COVER_W) if sub else " ")
        self._sub.setStyleSheet("color: #94a3b8; font-size: 11px;")
        self._sub.setToolTip(sub)
        layout.addWidget(self._sub)

        # 勾选按钮
        row = QHBoxLayout()
        row.setContentsMargins(0, 2, 0, 0)
        self._check_btn = QPushButton()
        self._check_btn.setFixedSize(24, 24)
        self._check_btn.setCursor(Qt.PointingHandCursor)
        self._check_btn.clicked.connect(self._toggle_check)
        self._update_check_style()
        row.addStretch()
        row.addWidget(self._check_btn)
        layout.addLayout(row)

    def _toggle_check(self):
        self._checked = not self._checked
        self._update_check_style()

    def _update_check_style(self):
        if self._checked:
            # 灰色边框 + 内部蓝色对勾（不填充）
            self._check_btn.setText("✓")
            self._check_btn.setStyleSheet(
                "QPushButton { background: transparent; color: #3b82f6;"
                " border: 2px solid #64748b; border-radius: 4px;"
                " font-size: 15px; font-weight: bold; }")
        else:
            self._check_btn.setText("")
            self._check_btn.setStyleSheet(
                "QPushButton { background: transparent;"
                " border: 2px solid #64748b; border-radius: 4px; }")

    @property
    def work_id(self):
        return self._work_id

    @property
    def is_checked(self):
        return self._checked

    def set_checked(self, v: bool):
        self._checked = v
        self._update_check_style()

    def set_cover_pixmap(self, pix: QPixmap):
        scaled = pix.scaled(COVER_W, COVER_H, Qt.KeepAspectRatioByExpanding,
                            Qt.SmoothTransformation)
        x = max(0, (scaled.width() - COVER_W) // 2)
        y = max(0, (scaled.height() - COVER_H) // 2)
        cropped = scaled.copy(x, y, COVER_W, COVER_H)
        self._cover.setPixmap(cropped)
        self._cover.setStyleSheet("border-radius: 6px;")


class BatchPreviewDialog(QDialog):
    """卡片式批量下载预览：封面 + 描述 + 勾选按钮。"""

    def __init__(self, items, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("batch_preview_title"))
        self.resize(860, 620)
        self._items = [it for it in (items or []) if it.get("work_id")]
        self._cards: dict[str, CardWidget] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        # 顶栏
        top = QHBoxLayout()
        self._count_label = QLabel()
        self._count_label.setStyleSheet("color: #94a3b8;")
        top.addWidget(self._count_label)
        top.addStretch()
        for text, fn in [(t("batch_select_all"), lambda: self._check_all(True)),
                         (t("batch_select_none"), lambda: self._check_all(False)),
                         (t("batch_select_invert"), self._invert)]:
            btn = QPushButton(text)
            btn.setStyleSheet(
                "QPushButton { background: #334155; color: #e2e8f0; border: none;"
                " border-radius: 4px; padding: 6px 12px; }"
                "QPushButton:hover { background: #475569; }")
            btn.clicked.connect(fn)
            top.addWidget(btn)
        root.addLayout(top)

        # 滚动 + 网格
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        container = QWidget()
        self._grid = QGridLayout(container)
        self._grid.setSpacing(10)
        self._grid.setContentsMargins(4, 4, 4, 4)

        self._cols = max(1, (self.width() - 40) // (CARD_W + 12))

        loader = CoverLoader.instance()
        loader.cover_ready.connect(self._on_cover_ready)

        cover_urls = []
        for idx, it in enumerate(self._items):
            card = CardWidget(it)
            self._cards[card.work_id] = card
            row, col = divmod(idx, self._cols)
            self._grid.addWidget(card, row, col)
            cover = str(it.get("cover") or "")
            if cover:
                cover_urls.append((card, cover))

        scroll.setWidget(container)
        root.addWidget(scroll, 1)

        # 底栏
        bottom = QHBoxLayout()
        bottom.addStretch()
        cancel_btn = QPushButton(t("cancel"))
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet(
            "QPushButton { background: #334155; color: #e2e8f0; border: none;"
            " border-radius: 6px; padding: 8px 16px; }")
        self._dl_btn = QPushButton()
        self._dl_btn.setStyleSheet(
            "QPushButton { background: #3b82f6; color: white; border: none;"
            " border-radius: 6px; padding: 8px 16px; }"
            "QPushButton:hover { background: #2563eb; }")
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
