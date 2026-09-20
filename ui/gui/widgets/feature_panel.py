"""功能选择 + URL + 输出格式 + 编码 + 存储模式 + 执行。"""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QWidget,
)
from shared.core.ops import PlatformBus
from shared.core.formats import (
    ContainerFormat, VIDEO_CODECS, AUDIO_CODECS, OUTPUT_PROFILES,
)

VIDEO_FEATURES = {"download", "account", "mix", "collection", "col_music", "collects",
                  "tk_download", "tk_account", "tk_mix", "ks_download", "ks_account", "xhs_download"}
AUDIO_FEATURES = {"live", "tk_live"}
COLLECT_FEATURES = {"hot", "search", "comment", "user"}


class FeaturePanel(QWidget):
    execute_clicked = Signal(str, str, str, str)
    preview_clicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Panel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title = QLabel("功能与参数")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        # 功能选择
        r1 = QHBoxLayout()
        r1.addWidget(QLabel("功能:"))
        self.fn_combo = QComboBox()
        self.fn_combo.currentIndexChanged.connect(self._on_feature_changed)
        r1.addWidget(self.fn_combo, 1)
        layout.addLayout(r1)

        # URL 输入
        r2 = QHBoxLayout()
        r2.addWidget(QLabel("链接:"))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("粘贴链接/关键词")
        r2.addWidget(self.url_input, 1)
        self.preview_btn = QPushButton("解析预览")
        self.preview_btn.clicked.connect(lambda: self.preview_clicked.emit(self.url_input.text()))
        r2.addWidget(self.preview_btn)
        layout.addLayout(r2)

        # 输出预设
        r3 = QHBoxLayout()
        r3.addWidget(QLabel("预设:"))
        self.profile_combo = QComboBox()
        for key, prof in OUTPUT_PROFILES.items():
            self.profile_combo.addItem(prof.name, key)
        r3.addWidget(self.profile_combo, 1)
        layout.addLayout(r3)

        # 编码选择
        r4 = QHBoxLayout()
        r4.addWidget(QLabel("视频:"))
        self.video_codec = QComboBox()
        for key, vc in VIDEO_CODECS.items():
            self.video_codec.addItem(vc.name, key)
        r4.addWidget(self.video_codec, 1)
        r4.addWidget(QLabel("音频:"))
        self.audio_codec = QComboBox()
        for key, ac in AUDIO_CODECS.items():
            self.audio_codec.addItem(ac.name, key)
        r4.addWidget(self.audio_codec, 1)
        layout.addLayout(r4)

        # 存储模式
        r5 = QHBoxLayout()
        r5.addWidget(QLabel("存储:"))
        self.storage_combo = QComboBox()
        self.storage_combo.addItem("直接存储", "flat")
        self.storage_combo.addItem("按作者分目录", "by_author")
        self.storage_combo.addItem("按日期分目录", "by_date")
        self.storage_combo.addItem("按类型分目录", "by_type")
        r5.addWidget(self.storage_combo)
        r5.addStretch()
        layout.addLayout(r5)

        # 执行按钮
        r6 = QHBoxLayout()
        self.exec_btn = QPushButton("执行")
        self.exec_btn.setObjectName("PrimaryButton")
        self.exec_btn.clicked.connect(self._on_execute)
        r6.addWidget(self.exec_btn)
        r6.addStretch()
        layout.addLayout(r6)

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
        if fid in COLLECT_FEATURES:
            self.profile_combo.setVisible(False)
            self.video_codec.setVisible(False)
            self.audio_codec.setVisible(False)
        elif fid in AUDIO_FEATURES:
            self.profile_combo.setVisible(True)
            self.video_codec.setVisible(False)
            self.audio_codec.setVisible(True)
        else:
            self.profile_combo.setVisible(True)
            self.video_codec.setVisible(True)
            self.audio_codec.setVisible(True)

    def _on_execute(self):
        fid = self.fn_combo.currentData()
        if fid:
            self.execute_clicked.emit(
                fid, self.url_input.text(),
                self.profile_combo.currentData(),
                self.storage_combo.currentData(),
            )

    def _current_platform(self):
        w = self.window()
        return getattr(w, '_current_platform', '') if w else ''
