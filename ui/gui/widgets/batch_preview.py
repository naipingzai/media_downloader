"""批量下载预览 — 卡片式布局：封面 + 描述 + 勾选。"""
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QVBoxLayout, QWidget,
)
from shared.core.i18n import t

__all__ = ["BatchPreviewDialog"]


def _fmt_duration(sec) -> str:
    try:
        sec = int(sec or 0)
    except (TypeError, ValueError):
        return ""
    if sec <= 0:
        return ""
    h, m, s = sec // 3600, (sec % 3600) // 60, sec % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _cover_referer(url: str) -> str:
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


class CardWidget(QFrame):
    """单个作品卡片：封面 + 标题/作者 + 勾选。"""

    def __init__(self, item: dict, parent=None):
        super().__init__(parent)
        self._work_id = str(item.get("work_id", ""))
        self._item = item
        self.setObjectName("CardWidget")
        self.setFixedWidth(176)
        self.setStyleSheet(
            "#CardWidget { background: #1e293b; border: 1px solid #334155; "
            "border-radius: 8px; }"
            "#CardWidget:hover { border: 1px solid #475569; }")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # 封面
        self._cover = QLabel()
        self._cover.setFixedSize(164, 100)
        self._cover.setAlignment(Qt.AlignCenter)
        self._cover.setStyleSheet("background: #0f172a; border-radius: 4px;")
        layout.addWidget(self._cover)

        # 标题
        title = str(item.get("title") or "").replace("\n", " ").strip()
        self._title = QLabel(title[:25] + "..." if len(title) > 25 else (title or "-"))
        self._title.setStyleSheet("color: #e2e8f0; font-size: 11px;")
        self._title.setWordWrap(True)
        self._title.setMaximumHeight(28)
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
        if extra:
            parts.insert(0, f"[{extra}]")
        sub = " · ".join(parts)
        self._sub = QLabel(sub[:40] if sub else "")
        self._sub.setStyleSheet("color: #94a3b8; font-size: 10px;")
        self._sub.setMaximumHeight(16)
        layout.addWidget(self._sub)

        # 勾选按钮 - 选中显示蓝色对勾，未选中显示空框
        self._checked = True
        self._check_btn = QPushButton("✓")
        self._check_btn.setFixedSize(22, 22)
        self._check_btn.setCursor(Qt.PointingHandCursor)
        self._check_btn.clicked.connect(self._toggle_check)
        self._update_check_style()
        layout.addWidget(self._check_btn, 0, Qt.AlignRight)

    def _toggle_check(self):
        self._checked = not self._checked
        self._update_check_style()

    def _update_check_style(self):
        if self._checked:
            self._check_btn.setText("✓")
            self._check_btn.setStyleSheet(
                "QPushButton { background: transparent; color: #3b82f6; "
                "border: 2px solid #3b82f6; border-radius: 4px; "
                "font-size: 14px; font-weight: bold; }"
                "QPushButton:hover { border-color: #2563eb; color: #2563eb; }")
        else:
            self._check_btn.setText("")
            self._check_btn.setStyleSheet(
                "QPushButton { background: transparent; color: transparent; "
                "border: 2px solid #475569; border-radius: 4px; }"
                "QPushButton:hover { border-color: #64748b; }")

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
        scaled = pix.scaled(164, 100, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        x = max(0, (scaled.width() - 164) // 2)
        y = max(0, (scaled.height() - 100) // 2)
        cropped = scaled.copy(x, y, min(164, scaled.width()), min(100, scaled.height()))
        self._cover.setPixmap(cropped)
        self._cover.setStyleSheet("border-radius: 4px;")


class BatchPreviewDialog(QDialog):
    """卡片式批量下载预览。"""

    def __init__(self, items, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("batch_preview_title"))
        self.resize(840, 600)
        self.setStyleSheet("QDialog { background: #0f172a; }")
        self._items = [it for it in (items or []) if it.get("work_id")]
        self._cards: list[CardWidget] = []
        self._net = QNetworkAccessManager(self)

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
                "QPushButton { background: #334155; color: #e2e8f0; border: none; "
                "border-radius: 4px; padding: 6px 12px; }"
                "QPushButton:hover { background: #475569; }")
            btn.clicked.connect(fn)
            top.addWidget(btn)
        root.addLayout(top)

        # 滚动 + 网格
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        self._grid = QGridLayout(container)
        self._grid.setSpacing(10)
        self._grid.setContentsMargins(4, 4, 4, 4)

        cols = max(1, (self.width() - 40) // 186)
        for idx, it in enumerate(self._items):
            card = CardWidget(it)
            self._cards.append(card)
            row, col = divmod(idx, cols)
            self._grid.addWidget(card, row, col)
            cover = str(it.get("cover") or "")
            if cover:
                self._load_cover(card, cover)

        scroll.setWidget(container)
        root.addWidget(scroll, 1)

        # 底栏
        bottom = QHBoxLayout()
        bottom.addStretch()
        cancel_btn = QPushButton(t("cancel"))
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet(
            "QPushButton { background: #334155; color: #e2e8f0; border: none; "
            "border-radius: 6px; padding: 8px 16px; }")
        self._dl_btn = QPushButton()
        self._dl_btn.setStyleSheet(
            "QPushButton { background: #3b82f6; color: white; border: none; "
            "border-radius: 6px; padding: 8px 16px; }"
            "QPushButton:hover { background: #2563eb; }")
        self._dl_btn.clicked.connect(self.accept)
        bottom.addWidget(cancel_btn)
        bottom.addWidget(self._dl_btn)
        root.addLayout(bottom)

        self._refresh_count()

    def _load_cover(self, card: CardWidget, url: str):
        req = QNetworkRequest(QUrl(url))
        referer = _cover_referer(url)
        if referer:
            req.setRawHeader(b"Referer", referer.encode())
        req.setRawHeader(b"User-Agent",
                         b"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        req.setTransferTimeout(10000)
        reply = self._net.get(req)
        reply.finished.connect(lambda r=reply, c=card: self._on_cover(r, c))

    def _on_cover(self, reply, card: CardWidget):
        try:
            if reply.error() == reply.NoError:
                img = QImage.fromData(reply.readAll())
                if not img.isNull():
                    card.set_cover_pixmap(QPixmap.fromImage(img))
        except Exception:
            pass
        finally:
            reply.deleteLater()

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
        n_all = len(self._cards)
        self._count_label.setText(t("batch_select_hint").format(count=n_all, selected=n_sel))
        self._dl_btn.setText(t("batch_download_selected").format(count=n_sel))
        self._dl_btn.setEnabled(n_sel > 0)

    def selected_ids(self) -> list[str]:
        return [c.work_id for c in self._cards if c.is_checked]
