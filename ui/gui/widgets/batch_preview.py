"""批量下载预览 — 卡片式布局：封面 + 描述 + 勾选。"""
from PySide6.QtCore import Qt, QUrl, QSize, Signal
from PySide6.QtGui import QIcon, QImage, QPixmap, QFont
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QDialog, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QPushButton, QScrollArea, QSizePolicy,
    QVBoxLayout, QWidget,
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


class CardWidget(QFrame):
    """单个作品卡片：封面 + 描述 + 勾选。"""
    toggled = Signal(str, bool)  # work_id, checked

    def __init__(self, item: dict, parent=None):
        super().__init__(parent)
        self._work_id = str(item.get("work_id", ""))
        self._checked = True
        self.setObjectName("CardWidget")
        self.setFixedSize(180, 240)
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # 封面区域
        cover_frame = QFrame()
        cover_frame.setFixedSize(172, 130)
        cover_frame.setObjectName("CoverFrame")
        cover_layout = QVBoxLayout(cover_frame)
        cover_layout.setContentsMargins(0, 0, 0, 0)
        self._cover_label = QLabel()
        self._cover_label.setAlignment(Qt.AlignCenter)
        self._cover_label.setFixedSize(172, 130)
        self._cover_label.setStyleSheet("background: #0f172a; border-radius: 4px;")
        self._cover_label.setText("🎬")
        self._cover_label.setFont(QFont("", 24))
        cover_layout.addWidget(self._cover_label)
        layout.addWidget(cover_frame)

        # 描述区
        desc_layout = QHBoxLayout()
        desc_layout.setSpacing(4)
        desc_layout.setContentsMargins(0, 0, 0, 0)

        # 标题 + 作者 + 时长
        info_layout = QVBoxLayout()
        info_layout.setSpacing(1)
        title = str(item.get("title") or "").replace("\n", " ").strip()
        self._title_label = QLabel(title[:30] if title else "-")
        self._title_label.setWordWrap(True)
        self._title_label.setStyleSheet("font-size: 11px; color: #e2e8f0;")
        self._title_label.setMaximumHeight(30)
        info_layout.addWidget(self._title_label)

        author = str(item.get("author_name") or "").strip()
        extra = str(item.get("extra") or "").strip()
        bits = []
        if author:
            bits.append(author)
        dur = _fmt_duration(item.get("duration"))
        if dur:
            bits.append(dur)
        digg = item.get("digg_count")
        if digg:
            bits.append(f"👍{digg}")
        sub = " · ".join(bits)
        if extra:
            sub = f"[{extra}] {sub}" if sub else f"[{extra}]"
        self._sub_label = QLabel(sub[:50] if sub else "")
        self._sub_label.setStyleSheet("font-size: 10px; color: #94a3b8;")
        self._sub_label.setMaximumHeight(16)
        info_layout.addWidget(self._sub_label)
        info_layout.addStretch()
        desc_layout.addLayout(info_layout, 1)

        # 勾选按钮（对勾图标）
        self._check_btn = QPushButton("✓")
        self._check_btn.setFixedSize(28, 28)
        self._check_btn.setCursor(Qt.PointingHandCursor)
        self._check_btn.clicked.connect(self._toggle)
        self._update_style()
        desc_layout.addWidget(self._check_btn, 0, Qt.AlignTop)

        layout.addLayout(desc_layout)

    def _toggle(self):
        self._checked = not self._checked
        self._update_style()
        self.toggled.emit(self._work_id, self._checked)

    def _update_style(self):
        if self._checked:
            self._check_btn.setStyleSheet(
                "QPushButton { background: #3b82f6; color: white; border: none; "
                "border-radius: 14px; font-size: 16px; font-weight: bold; }"
                "QPushButton:hover { background: #2563eb; }")
            self.setStyleSheet(
                "#CardWidget { background: #1e293b; border: 2px solid #3b82f6; border-radius: 8px; }")
        else:
            self._check_btn.setStyleSheet(
                "QPushButton { background: #334155; color: #64748b; border: 1px solid #475569; "
                "border-radius: 14px; font-size: 16px; }"
                "QPushButton:hover { background: #475569; }")
            self.setStyleSheet(
                "#CardWidget { background: #1e293b; border: 2px solid #334155; border-radius: 8px; }")

    @property
    def work_id(self):
        return self._work_id

    @property
    def is_checked(self):
        return self._checked

    def set_checked(self, v: bool):
        self._checked = v
        self._update_style()

    def set_cover(self, pixmap: QPixmap):
        scaled = pixmap.scaled(170, 128, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        # 居中裁剪
        x = (scaled.width() - 170) // 2
        y = (scaled.height() - 128) // 2
        cropped = scaled.copy(x, y, 170, 128)
        self._cover_label.setPixmap(cropped)
        self._cover_label.setStyleSheet("border-radius: 4px;")


class BatchPreviewDialog(QDialog):
    """卡片式批量下载预览：封面 + 描述 + 勾选按钮。"""

    def __init__(self, items, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("batch_preview_title"))
        self.resize(820, 600)
        self.setStyleSheet("QDialog { background: #0f172a; }")
        self._items = [it for it in (items or []) if it.get("work_id")]
        self._cards: list[CardWidget] = []
        self._net = QNetworkAccessManager(self)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        # ── 顶栏 ──
        top = QHBoxLayout()
        self._count_label = QLabel()
        self._count_label.setObjectName("Caption")
        top.addWidget(self._count_label)
        top.addStretch()
        btn_all = QPushButton(t("batch_select_all"))
        btn_none = QPushButton(t("batch_select_none"))
        btn_invert = QPushButton(t("batch_select_invert"))
        for b in (btn_all, btn_none, btn_invert):
            b.setObjectName("SubtleButton")
            top.addWidget(b)
        root.addLayout(top)

        # ── 滚动区域 + 网格卡片 ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        self._grid = QGridLayout(container)
        self._grid.setSpacing(10)
        self._grid.setContentsMargins(4, 4, 4, 4)

        self._fill_cards()

        scroll.setWidget(container)
        root.addWidget(scroll, 1)

        # ── 底栏 ──
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

        btn_all.clicked.connect(lambda: self._check_all(True))
        btn_none.clicked.connect(lambda: self._check_all(False))
        btn_invert.clicked.connect(self._invert)
        self._refresh_count()

    def _fill_cards(self):
        cols = max(1, (self.width() - 40) // 190)
        for idx, it in enumerate(self._items):
            card = CardWidget(it)
            card.toggled.connect(self._on_card_toggled)
            self._cards.append(card)
            row, col = divmod(idx, cols)
            self._grid.addWidget(card, row, col)

            cover = str(it.get("cover") or "")
            if cover:
                self._load_cover(card, cover)

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
                data = reply.readAll()
                img = QImage.fromData(data)
                if not img.isNull():
                    card.set_cover(QPixmap.fromImage(img))
        except Exception:
            pass
        finally:
            reply.deleteLater()

    def _on_card_toggled(self, work_id: str, checked: bool):
        self._refresh_count()

    def _check_all(self, state: bool):
        for card in self._cards:
            card.set_checked(state)
        self._refresh_count()

    def _invert(self):
        for card in self._cards:
            card.set_checked(not card.is_checked)
        self._refresh_count()

    def _refresh_count(self):
        n_sel = sum(1 for c in self._cards if c.is_checked)
        n_all = len(self._cards)
        self._count_label.setText(
            t("batch_select_hint").format(count=n_all, selected=n_sel))
        self._dl_btn.setText(
            t("batch_download_selected").format(count=n_sel))
        self._dl_btn.setEnabled(n_sel > 0)

    def selected_ids(self) -> list[str]:
        """按列表原顺序返回勾选的 work_id。"""
        return [c.work_id for c in self._cards if c.is_checked]
