"""功能选择 + URL + 下载选项 + 执行。"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QVBoxLayout, QWidget,
)
from shared.core.ops import PlatformBus

COLLECT_FEATURES = {"hot", "search", "comment", "user"}
LIVE_FEATURES = {"live", "tk_live"}


class FeaturePanel(QWidget):
    execute_clicked = Signal(str, str, dict)
    preview_clicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Panel")
        self.setAttribute(Qt.WA_StyledBackground, True)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        hdr = QHBoxLayout()
        hdr.setContentsMargins(16, 12, 16, 6)
        title = QLabel("功能与参数")
        title.setObjectName("SectionTitle")
        title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        hdr.addWidget(title)
        hdr.addStretch()
        outer.addLayout(hdr)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(16, 4, 16, 12)
        layout.setSpacing(8)

        r1 = QHBoxLayout()
        r1.addWidget(QLabel("功能:"))
        self.fn_combo = QComboBox()
        self.fn_combo.currentIndexChanged.connect(self._on_feature_changed)
        r1.addWidget(self.fn_combo, 1)
        layout.addLayout(r1)

        r2 = QHBoxLayout()
        r2.addWidget(QLabel("链接:"))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("粘贴链接/关键词")
        r2.addWidget(self.url_input, 1)
        self.preview_btn = QPushButton("解析预览")
        self.preview_btn.clicked.connect(lambda: self.preview_clicked.emit(self.url_input.text()))
        r2.addWidget(self.preview_btn)
        layout.addLayout(r2)

        r_opts = QHBoxLayout()
        r_opts.addWidget(QLabel("选项:"))
        self.danmaku_cb = QCheckBox("弹幕")
        self.subtitle_cb = QCheckBox("字幕")
        self.cover_cb = QCheckBox("封面")
        self.metadata_cb = QCheckBox("元数据")
        for cb in (self.danmaku_cb, self.subtitle_cb, self.cover_cb, self.metadata_cb):
            cb.setChecked(True)
            r_opts.addWidget(cb)
        r_opts.addStretch()
        layout.addLayout(r_opts)

        r6 = QHBoxLayout()
        self.exec_btn = QPushButton("执行")
        self.exec_btn.setObjectName("PrimaryButton")
        self.exec_btn.clicked.connect(self._on_execute)
        r6.addWidget(self.exec_btn)
        r6.addStretch()
        layout.addLayout(r6)

        layout.addStretch()
        scroll.setWidget(inner)
        outer.addWidget(scroll)

    def set_features(self, features):
        self.fn_combo.blockSignals(True)
        self.fn_combo.clear()
        for f in features:
            self.fn_combo.addItem(f.name, f.id)
        self.fn_combo.blockSignals(False)
        if features:
            self.fn_combo.setCurrentIndex(0)

    def _on_feature_changed(self, index):
        fid = self.fn_combo.currentData()
        if not fid:
            return
        features = PlatformBus.get_features(self._current_platform())
        meta = next((f for f in features if f.id == fid), None)
        if meta:
            self.url_input.setVisible(meta.need_url)
            self.preview_btn.setVisible(meta.need_url)
        is_collect = fid in COLLECT_FEATURES
        is_live = fid in LIVE_FEATURES
        for w in (self.danmaku_cb, self.subtitle_cb, self.cover_cb, self.metadata_cb):
            w.setVisible(not is_collect and not is_live)

    def _on_execute(self):
        fid = self.fn_combo.currentData()
        if fid:
            opts = {
                "danmaku": self.danmaku_cb.isChecked(),
                "subtitle": self.subtitle_cb.isChecked(),
                "cover": self.cover_cb.isChecked(),
                "metadata": self.metadata_cb.isChecked(),
            }
            self.execute_clicked.emit(fid, self.url_input.text(), opts)

    def _current_platform(self):
        w = self.window()
        return getattr(w, '_current_platform', '') if w else ''
