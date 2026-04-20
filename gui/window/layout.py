from __future__ import annotations

import copy
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QTextOption
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QStyle,
    QTabWidget,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from gui.config import (
    CLEANUP_OPTIONS,
    FONT_COLOR_SWATCHES,
    FONT_OPTIONS,
    INTRO_TTS_OPTIONS,
    INTRO_VOICE_OPTIONS,
    LANGUAGE_OPTIONS,
    SPEAKER_DETECTION_OPTIONS,
    STROKE_COLOR_SWATCHES,
    SUBTITLE_POSITION_OPTIONS,
    SUBTITLE_VISIBILITY_OPTIONS,
    TARGET_LANGUAGE_OPTIONS,
    TIMING_MODE_OPTIONS,
    UI_THEME_OPTIONS,
    VIDEO_CODEC_OPTIONS,
    VOICE_OPTIONS,
    WATERMARK_POSITION_OPTIONS,
)
from gui.preview_canvas import PreviewCanvas
from gui.utils import APP_STYLESHEET, repair_mojibake_text


class WindowLayoutMixin:
    def _build_ui_legacy(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        container.setObjectName("AppRoot")
        scroll.setWidget(container)
        self.setCentralWidget(scroll)
        self.setStyleSheet(APP_STYLESHEET)

        root = QVBoxLayout(container)
        root.setContentsMargins(22, 22, 22, 28)
        root.setSpacing(18)

        hero_card = QFrame()
        hero_card.setObjectName("HeroCard")
        hero_layout = QVBoxLayout(hero_card)
        hero_layout.setContentsMargins(28, 26, 28, 26)
        hero_layout.setSpacing(12)
        eyebrow = QLabel("CAPCUT MATE · DUB STUDIO")
        eyebrow.setObjectName("HeroEyebrow")
        hero_title = QLabel("Bảng điều khiển lồng tiếng tiếng Việt chuyên nghiệp")
        hero_title.setObjectName("HeroTitle")
        hero_subtitle = QLabel(
            "Tất cả chỉnh sửa teaser, vietsub, nhận diện nhân vật, tốc độ đọc và render đều nằm trong một giao diện Python đồng bộ. "
            "Bạn có thể xem trước ngay trên khung video trước khi xuất file."
        )
        hero_subtitle.setObjectName("HeroSubtitle")
        hero_subtitle.setWordWrap(True)
        hero_layout.addWidget(eyebrow)
        hero_layout.addWidget(hero_title)
        hero_layout.addWidget(hero_subtitle)
        hero_chip_row = QHBoxLayout()
        hero_chip_row.setSpacing(10)
        self.mode_chip = self._make_chip("Chờ phân tích")
        self.subtitle_chip = self._make_chip("Vietsub: Bật")
        self.timing_chip = self._make_chip("Timing: Siêu khít")
        hero_chip_row.addWidget(self.mode_chip)
        hero_chip_row.addWidget(self.subtitle_chip)
        hero_chip_row.addWidget(self.timing_chip)
        hero_chip_row.addStretch(1)
        hero_layout.addLayout(hero_chip_row)
        root.addWidget(hero_card)

        body = QHBoxLayout()
        body.setSpacing(18)
        root.addLayout(body)

        sidebar_col = QVBoxLayout()
        sidebar_col.setSpacing(18)
        left_col = QVBoxLayout()
        left_col.setSpacing(18)
        right_col = QVBoxLayout()
        right_col.setSpacing(18)
        body.addLayout(sidebar_col, 2)
        body.addLayout(left_col, 7)
        body.addLayout(right_col, 5)

        sidebar_card, sidebar_layout = self._make_card(
            "Điều hướng nhanh",
            "Các khu vực chính của app được gom lại ở đây để nhìn tổng thể rõ hơn.",
        )
        self.sidebar_status_chip = self._make_chip("Sẵn sàng")
        sidebar_layout.addWidget(self.sidebar_status_chip)
        for label in [
            "1. Nguồn video",
            "2. Preview",
            "3. Tóm tắt",
            "4. Thiết lập",
            "5. Gán giọng",
            "6. Nhật ký render",
        ]:
            item = QFrame()
            item.setObjectName("StatCard")
            item_layout = QHBoxLayout(item)
            item_layout.setContentsMargins(14, 12, 14, 12)
            item_layout.addWidget(self._make_chip(label.split(".")[0]))
            text_label = QLabel(label.split(". ", 1)[1])
            text_label.setStyleSheet("font-weight: 700; color: #f8fafc;")
            item_layout.addWidget(text_label)
            sidebar_layout.addWidget(item)
        sidebar_layout.addStretch(1)
        sidebar_col.addWidget(sidebar_card)

        input_card, input_layout = self._make_card(
            "Nguồn video",
            "Chọn video gốc, phân tích audio và render nhanh ngay từ giao diện.",
        )
        self.input_path_edit = QLineEdit()
        self.input_path_edit.setReadOnly(True)
        self.input_path_edit.setPlaceholderText("Chưa chọn video nguồn")
        browse_btn = self._make_button("Chọn video", "ghost")
        browse_btn.clicked.connect(self.choose_video)
        analyze_btn = self._make_button("Phân tích video", "primary")
        analyze_btn.clicked.connect(self.start_analysis)
        render_btn = self._make_button("Render bản lồng tiếng", "success")
        render_btn.clicked.connect(self.start_render)
        cancel_btn = self._make_button("Dừng tác vụ", "ghost")
        cancel_btn.clicked.connect(self.controller.cancel_active_job)
        self.analyze_btn = analyze_btn
        self.render_btn = render_btn
        self.cancel_btn = cancel_btn
        input_layout.addWidget(self._field_label("Tệp video đầu vào"))
        input_layout.addWidget(self.input_path_edit)
        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        action_row.addWidget(browse_btn)
        action_row.addWidget(analyze_btn)
        action_row.addWidget(render_btn)
        action_row.addWidget(cancel_btn)
        action_row.addStretch(1)
        input_layout.addLayout(action_row)
        left_col.addWidget(input_card)

        preview_card, preview_layout = self._make_card(
            "Preview trực quan",
            "Xem trước khung hình, vùng xử lý phụ đề cũ và kiểu chữ mới ngay trong app.",
        )
        self.preview_canvas = PreviewCanvas()
        self.preview_canvas.subtitle_dragged.connect(self.on_preview_subtitle_dragged)
        self.preview_canvas.cleanup_region_changed.connect(self.on_cleanup_region_changed)
        self.preview_canvas.watermark_scale_changed.connect(self.on_watermark_scale_dragged)
        preview_layout.addWidget(self.preview_canvas)
        slider_grid = QGridLayout()
        slider_grid.setHorizontalSpacing(16)
        slider_grid.setVerticalSpacing(12)
        self.font_size_slider = self._make_slider(18, 72, 28, self.on_font_size_changed)

        self.blur_slider = self._make_slider(2, 24, 10, self.on_blur_changed)
        self.bottom_offset_slider = self._make_slider(
            12, 180, 54, self.on_bottom_offset_changed
        )
        self.font_size_value = QLabel("28 px")
        self.blur_value = QLabel("10 px")
        self.bottom_offset_value = QLabel("54 px")
        slider_grid.addWidget(self._field_label("Cỡ chữ vietsub"), 0, 0)
        slider_grid.addWidget(self.font_size_slider, 0, 1)
        slider_grid.addWidget(self.font_size_value, 0, 2)
        slider_grid.addWidget(self._field_label("Độ mờ phụ đề cũ"), 1, 0)
        slider_grid.addWidget(self.blur_slider, 1, 1)
        slider_grid.addWidget(self.blur_value, 1, 2)
        slider_grid.addWidget(self._field_label("Độ cao phụ đề mới"), 2, 0)
        slider_grid.addWidget(self.bottom_offset_slider, 2, 1)
        slider_grid.addWidget(self.bottom_offset_value, 2, 2)
        preview_layout.addLayout(slider_grid)
        self.preview_note = QLabel(
            "Khung vàng là vùng dọn phụ đề cũ. Phụ đề mới được dựng thử theo đúng font, màu, viền và vị trí hiện tại."
        )
        self.preview_note.setObjectName("SectionHint")
        self.preview_note.setWordWrap(True)
        preview_layout.addWidget(self.preview_note)
        snap_row = QHBoxLayout()
        snap_row.setSpacing(10)
        for label, preset in [
            ("Đặt trên", "top"),
            ("Căn giữa", "middle"),
            ("Đặt dưới", "bottom"),
        ]:
            button = self._make_button(label, "ghost")
            button.clicked.connect(
                lambda _checked=False, p=preset: self.apply_caption_position(p)
            )
            snap_row.addWidget(button)
        snap_row.addStretch(1)
        preview_layout.addLayout(snap_row)
        left_col.addWidget(preview_card)

        summary_card, summary_layout = self._make_card(
            "Tóm tắt phân tích",
            "Sau khi phân tích, app sẽ hiển thị nhanh nguồn tiếng, dạng audio, số nhân vật và cảnh báo cần chú ý.",
        )
        stats_grid = QGridLayout()
        stats_grid.setHorizontalSpacing(14)
        stats_grid.setVerticalSpacing(14)
        self.summary_labels = {}
        for idx, (title, key) in enumerate(
            [
                ("Ngôn ngữ nguồn", "sourceLanguage"),
                ("Số speaker", "speakers"),
                ("Bố cục audio", "voiceLayout"),
                ("Kiểu cleanup", "cleanupMode"),
            ]
        ):
            card, label = self._make_stat_card(title)
            stats_grid.addWidget(card, idx // 2, idx % 2)
            self.summary_labels[key] = label
        summary_layout.addLayout(stats_grid)
        summary_split = QHBoxLayout()
        summary_split.setSpacing(14)
        warning_col = QVBoxLayout()
        warning_col.addWidget(self._field_label("Cảnh báo"))
        self.warning_box = QPlainTextEdit()
        self.warning_box.setReadOnly(True)
        self.warning_box.setPlaceholderText(
            "Cảnh báo và ghi chú sau khi phân tích sẽ hiện ở đây."
        )
        warning_col.addWidget(self.warning_box)
        timeline_col = QVBoxLayout()
        timeline_col.addWidget(self._field_label("Timeline thoại"))
        self.timeline_box = QPlainTextEdit()
        self.timeline_box.setReadOnly(True)
        self.timeline_box.setPlaceholderText(
            "Các câu thoại đầu tiên sẽ được hiển thị để bạn kiểm tra speaker."
        )
        timeline_col.addWidget(self.timeline_box)
        summary_split.addLayout(warning_col, 4)
        summary_split.addLayout(timeline_col, 5)
        summary_layout.addLayout(summary_split)
        left_col.addWidget(summary_card)

        status_card, status_layout = self._make_card(
            "Tiến trình & nhật ký",
            "Theo dõi phase chạy pipeline, phần trăm hoàn thành và log chi tiết ngay trong ứng dụng.",
        )
        progress_row = QHBoxLayout()
        progress_row.setSpacing(12)
        self.phase_label = self._make_chip("Trạng thái: idle")
        self.step_label = self._make_chip("Bước: chờ")
        progress_row.addWidget(self.phase_label)
        progress_row.addWidget(self.step_label)
        progress_row.addStretch(1)
        status_layout.addLayout(progress_row)
        self.progress_bar = QProgressBar()
        status_layout.addWidget(self.progress_bar)
        self.log_box = QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setPlaceholderText("Log chạy pipeline sẽ hiển thị tại đây.")
        status_layout.addWidget(self.log_box)
        left_col.addWidget(status_card)

        settings_card, settings_layout = self._make_card(
            "Thiết lập thông minh",
            "Điều khiển cách nhận diện audio gốc, nhịp đọc, hiển thị vietsub và lựa chọn font ngay trong app.",
        )
        settings_grid = QGridLayout()
        settings_grid.setHorizontalSpacing(14)
        settings_grid.setVerticalSpacing(12)
        settings_layout.addLayout(settings_grid)
        self.source_language_combo = self._make_combo(
            LANGUAGE_OPTIONS, self.on_basic_settings_changed
        )
        self.speaker_detection_combo = self._make_combo(
            SPEAKER_DETECTION_OPTIONS, self.on_speaker_detection_changed
        )
        self.speaker_count_spin = QSpinBox()
        self.speaker_count_spin.setRange(1, 4)
        self.speaker_count_spin.valueChanged.connect(self.on_basic_settings_changed)
        self.timing_mode_combo = self._make_combo(
            TIMING_MODE_OPTIONS, self.on_basic_settings_changed
        )
        self.video_codec_combo = self._make_combo(
            VIDEO_CODEC_OPTIONS, self.on_basic_settings_changed
        )
        self.ui_theme_combo = self._make_combo(
            UI_THEME_OPTIONS, self.on_theme_preset_changed
        )
        self.cleanup_combo = self._make_combo(
            CLEANUP_OPTIONS, self.on_basic_settings_changed
        )
        self.subtitle_enabled_combo = self._make_combo(
            SUBTITLE_VISIBILITY_OPTIONS, self.on_basic_settings_changed
        )
        self.subtitle_position_combo = self._make_combo(
            SUBTITLE_POSITION_OPTIONS, self.on_basic_settings_changed
        )
        self.font_combo = self._make_combo(
            [(option["value"], option["label"]) for option in FONT_OPTIONS],
            self.on_font_changed,
        )
        self.stroke_width_spin = QSpinBox()
        self.stroke_width_spin.setRange(0, 6)
        self.stroke_width_spin.valueChanged.connect(self.on_basic_settings_changed)
        self.max_words_spin = QSpinBox()
        self.max_words_spin.setRange(2, 8)
        self.max_words_spin.valueChanged.connect(self.on_basic_settings_changed)
        self.font_color_btn = QPushButton("Màu chữ")
        self.font_color_btn.clicked.connect(lambda: self.pick_color("fontColor"))
        self.stroke_color_btn = QPushButton("Màu viền")
        self.stroke_color_btn.clicked.connect(lambda: self.pick_color("strokeColor"))
        self.intro_enabled_check = QCheckBox("Bật teaser")
        self.intro_enabled_check.stateChanged.connect(self.on_basic_settings_changed)
        self.intro_duration_spin = QDoubleSpinBox()
        self.intro_duration_spin.setRange(8.0, 16.0)
        self.intro_duration_spin.setSingleStep(0.5)
        self.intro_duration_spin.valueChanged.connect(self.on_basic_settings_changed)
        self.intro_voice_combo = self._make_combo(
            INTRO_TTS_OPTIONS, self.on_basic_settings_changed
        )
        self.intro_voice_combo.setEditable(True)
        if self.intro_voice_combo.lineEdit() is not None:
            self.intro_voice_combo.lineEdit().setPlaceholderText(
                "Chọn giọng EdgeTTS/VieNeu hoặc nhập Edge voice, ví dụ en-US-AvaNeural"
            )
            self.intro_voice_combo.lineEdit().returnPressed.connect(
                self.on_basic_settings_changed
            )
        self.intro_background_check = QCheckBox("Giữ âm nền teaser")
        self.intro_background_check.stateChanged.connect(self.on_basic_settings_changed)
        self.intro_background_volume_spin = QDoubleSpinBox()
        self.intro_background_volume_spin.setRange(0.0, 0.3)
        self.intro_background_volume_spin.setSingleStep(0.01)
        self.intro_background_volume_spin.valueChanged.connect(
            self.on_basic_settings_changed
        )
        self.keep_original_audio_check = QCheckBox("Giữ audio gốc nhỏ")
        self.keep_original_audio_check.stateChanged.connect(
            self.on_basic_settings_changed
        )
        self.output_mp4_check = QCheckBox("Xuất MP4")
        self.output_mp4_check.stateChanged.connect(self.on_basic_settings_changed)
        self.output_draft_check = QCheckBox("Xuất Draft")
        self.output_draft_check.stateChanged.connect(self.on_basic_settings_changed)
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setPlaceholderText("Ví dụ: C:/Users/.../output")
        self.output_dir_edit.editingFinished.connect(self.on_basic_settings_changed)
        self.draft_dir_edit = QLineEdit()
        self.draft_dir_edit.setPlaceholderText("Ví dụ: C:/Users/.../draft")
        self.draft_dir_edit.editingFinished.connect(self.on_basic_settings_changed)
        output_dir_btn = self._make_button("Chọn", "ghost")
        output_dir_btn.clicked.connect(
            lambda: self.choose_directory(self.output_dir_edit)
        )
        draft_dir_btn = self._make_button("Chọn", "ghost")
        draft_dir_btn.clicked.connect(
            lambda: self.choose_directory(self.draft_dir_edit)
        )
        self.region_x_spin = self._make_region_spin()
        self.region_y_spin = self._make_region_spin()
        self.region_w_spin = self._make_region_spin()
        self.region_h_spin = self._make_region_spin()

        rows = [
            (
                "Ngôn ngữ nguồn",
                self.source_language_combo,
                "Số speaker",
                self.speaker_count_spin,
            ),
            (
                "Nhận diện speaker",
                self.speaker_detection_combo,
                "Chế độ timing",
                self.timing_mode_combo,
            ),
            (
                "Chế độ encode",
                self.video_codec_combo,
                "Preset giao diện",
                self.ui_theme_combo,
            ),
            (
                "Xử lý sub cũ",
                self.cleanup_combo,
                "Bật/Tắt vietsub",
                self.subtitle_enabled_combo,
            ),
            (
                "Vị trí vietsub",
                self.subtitle_position_combo,
                "Font chữ",
                self.font_combo,
            ),
            (
                "Độ dày viền",
                self.stroke_width_spin,
                "Tối đa từ mỗi dòng",
                self.max_words_spin,
            ),
        ]
        for row, (left_label, left_widget, right_label, right_widget) in enumerate(
            rows
        ):
            settings_grid.addWidget(self._field_label(left_label), row, 0)
            settings_grid.addWidget(left_widget, row, 1)
            if right_label and right_widget is not None:
                settings_grid.addWidget(self._field_label(right_label), row, 2)
                settings_grid.addWidget(right_widget, row, 3)
        self.font_color_btn.setObjectName("ColorButton")
        self.stroke_color_btn.setObjectName("ColorButton")
        settings_grid.addWidget(self.font_color_btn, 7, 0, 1, 2)
        settings_grid.addWidget(self.stroke_color_btn, 7, 2, 1, 2)
        settings_grid.addWidget(self._field_label("Palette màu chữ"), 8, 0)
        settings_grid.addLayout(
            self._build_palette_row("fontColor", FONT_COLOR_SWATCHES), 8, 1, 1, 3
        )
        settings_grid.addWidget(self._field_label("Palette màu viền"), 9, 0)
        settings_grid.addLayout(
            self._build_palette_row("strokeColor", STROKE_COLOR_SWATCHES), 9, 1, 1, 3
        )
        settings_grid.addWidget(self.intro_enabled_check, 10, 0, 1, 2)
        settings_grid.addWidget(self.keep_original_audio_check, 10, 2, 1, 2)
        settings_grid.addWidget(self._field_label("Thời lượng teaser"), 11, 0)
        settings_grid.addWidget(self.intro_duration_spin, 11, 1)
        settings_grid.addWidget(self._field_label("Giọng teaser"), 11, 2)
        settings_grid.addWidget(self.intro_voice_combo, 11, 3)
        settings_grid.addWidget(self.intro_background_check, 12, 0, 1, 2)
        settings_grid.addWidget(self._field_label("Âm nền teaser"), 12, 2)
        settings_grid.addWidget(self.intro_background_volume_spin, 12, 3)
        settings_grid.addWidget(self.output_mp4_check, 13, 0)
        settings_grid.addWidget(self.output_draft_check, 13, 1)
        settings_grid.addWidget(self._field_label("Thư mục output"), 14, 0)
        output_row = QWidget()
        output_row_layout = QHBoxLayout(output_row)
        output_row_layout.setContentsMargins(0, 0, 0, 0)
        output_row_layout.addWidget(self.output_dir_edit)
        output_row_layout.addWidget(output_dir_btn)
        settings_grid.addWidget(output_row, 14, 1, 1, 3)
        settings_grid.addWidget(self._field_label("Thư mục draft"), 15, 0)
        draft_row = QWidget()
        draft_row_layout = QHBoxLayout(draft_row)
        draft_row_layout.setContentsMargins(0, 0, 0, 0)
        draft_row_layout.addWidget(self.draft_dir_edit)
        draft_row_layout.addWidget(draft_dir_btn)
        settings_grid.addWidget(draft_row, 15, 1, 1, 3)
        settings_grid.addWidget(self._field_label("Vùng sub cũ X"), 16, 0)
        settings_grid.addWidget(self.region_x_spin, 16, 1)
        settings_grid.addWidget(self._field_label("Vùng sub cũ Y"), 16, 2)
        settings_grid.addWidget(self.region_y_spin, 16, 3)
        settings_grid.addWidget(self._field_label("Vùng sub cũ W"), 17, 0)
        settings_grid.addWidget(self.region_w_spin, 17, 1)
        settings_grid.addWidget(self._field_label("Vùng sub cũ H"), 17, 2)
        settings_grid.addWidget(self.region_h_spin, 17, 3)
        right_col.addWidget(settings_card)

        voice_card, voice_layout_root = self._make_card(
            "Gán giọng theo nhân vật",
            "Giữ ổn định giọng của nhân vật chính và đổi từng speaker ngay sau khi phân tích.",
        )
        self.voice_overview_label = QLabel("Chưa có kết quả phân tích speaker.")
        self.voice_overview_label.setObjectName("SectionHint")
        self.voice_overview_label.setWordWrap(True)
        voice_layout_root.addWidget(self.voice_overview_label)
        self.voice_overview_label = QLabel("Chưa có kết quả phân tích speaker.")
        self.voice_overview_label.setObjectName("SectionHint")
        self.voice_overview_label.setWordWrap(True)
        voice_layout_root.addWidget(self.voice_overview_label)
        self.voice_layout = QVBoxLayout()
        self.voice_layout.setSpacing(10)
        voice_layout_root.addLayout(self.voice_layout)
        right_col.addWidget(voice_card)
        right_col.addStretch(1)
        self.animated_cards = [
            hero_card,
            sidebar_card,
            input_card,
            preview_card,
            summary_card,
            status_card,
            settings_card,
            voice_card,
        ]

    def _build_ui(self) -> None:
        # Keep a single supported UI path without disturbing existing behavior.
        self._build_ui_compact()

    def _build_ui_compact(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.setCentralWidget(scroll)
        self.setStyleSheet(APP_STYLESHEET)

        container = QWidget()
        container.setObjectName("AppRoot")
        scroll.setWidget(container)

        root = QVBoxLayout(container)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        hero_card = QFrame()
        hero_card.setObjectName("HeroCard")
        hero_layout = QVBoxLayout(hero_card)
        hero_layout.setContentsMargins(20, 10, 20, 10)
        hero_layout.setSpacing(4)
        eyebrow = QLabel("CAPCUT MATE · DUB STUDIO")
        eyebrow.setObjectName("HeroEyebrow")
        hero_title = QLabel("Bảng điều khiển lồng tiếng tiếng Việt chuyên nghiệp")
        hero_title.setObjectName("HeroTitle")
        hero_subtitle = QLabel(
            "Giao diện này được cố định trong một màn hình để bạn không phải kéo qua kéo lại. "
            "Preview, thiết lập, gán giọng và log đều được gom thành từng tab rõ ràng."
        )
        hero_subtitle.setObjectName("HeroSubtitle")
        hero_subtitle.setWordWrap(True)
        hero_layout.addWidget(eyebrow)
        hero_layout.addWidget(hero_title)
        hero_layout.addWidget(hero_subtitle)

        hero_chip_row = QHBoxLayout()
        hero_chip_row.setSpacing(6)
        self.mode_chip = self._make_chip("Chờ phân tích")
        self.subtitle_chip = self._make_chip("Vietsub: Bật")
        self.timing_chip = self._make_chip("Timing: Siêu khít")
        hero_chip_row.addWidget(self.mode_chip)
        hero_chip_row.addWidget(self.subtitle_chip)
        hero_chip_row.addWidget(self.timing_chip)
        hero_chip_row.addStretch(1)
        hero_layout.addLayout(hero_chip_row)
        root.addWidget(hero_card, 0)

        body = QVBoxLayout()
        body.setSpacing(14)
        root.addLayout(body, 1)

        sidebar_card, sidebar_layout = self._make_card(
            "Điều hướng nhanh",
            "Mỗi nhóm chức năng nằm trong một vùng cố định để thao tác nhanh trên mọi loại màn hình.",
        )
        sidebar_card.setMinimumWidth(200)
        sidebar_card.setMaximumWidth(260)
        self.sidebar_status_chip = self._make_chip("Sẵn sàng")
        sidebar_layout.addWidget(self.sidebar_status_chip)
        for label in [
            "1. Nguồn video",
            "2. Tổng quan",
            "3. Preview",
            "4. Thiết lập",
            "5. Nhân vật",
            "6. Tiến trình",
        ]:
            item = QFrame()
            item.setObjectName("StatCard")
            item_layout = QHBoxLayout(item)
            item_layout.setContentsMargins(14, 12, 14, 12)
            item_layout.addWidget(self._make_chip(label.split(".")[0]))
            text_label = QLabel(label.split(". ", 1)[1])
            text_label.setStyleSheet("font-weight: 700; color: #f8fafc;")
            item_layout.addWidget(text_label)
            sidebar_layout.addWidget(item)
        sidebar_layout.addStretch(1)

        input_card, input_layout = self._make_card(
            "Nguồn video",
            "Chọn video gốc, phân tích audio và render nhanh ngay từ giao diện.",
        )
        self.input_path_edit = QLineEdit()
        self.input_path_edit.setReadOnly(True)
        self.input_path_edit.setPlaceholderText("Chưa chọn video nguồn")
        browse_btn = self._make_button("Chọn video", "ghost")
        browse_btn.clicked.connect(self.choose_video)
        analyze_btn = self._make_button("Phân tích video", "primary")
        analyze_btn.clicked.connect(self.start_analysis)
        render_btn = self._make_button("Render bản lồng tiếng", "success")
        render_btn.clicked.connect(self.start_render)
        cancel_btn = self._make_button("Dừng tác vụ", "ghost")
        cancel_btn.clicked.connect(self.controller.cancel_active_job)
        self.analyze_btn = analyze_btn
        self.render_btn = render_btn
        self.cancel_btn = cancel_btn
        self.install_env_btn = self._make_button("Chuẩn bị model", "primary")
        self.install_env_btn.clicked.connect(self.install_environment)
        input_layout.addWidget(self._field_label("Tệp video đầu vào"))
        input_layout.addWidget(self.input_path_edit)
        action_row = QHBoxLayout()
        action_row.setSpacing(6)
        action_row.addWidget(browse_btn)
        action_row.addWidget(analyze_btn)
        action_row.addWidget(render_btn)
        action_row.addWidget(cancel_btn)
        action_row.addWidget(self.install_env_btn)
        action_row.addStretch(1)
        input_layout.addLayout(action_row)

        output_card, output_layout = self._make_card(
            "Output sau render",
            "Render xong sẽ giữ video nội bộ để preview ngay trong app. Chỉ khi bấm Xuất file thì hệ thống mới ghi video ra thư mục bạn chọn.",
        )
        self.output_result_edit = QLineEdit()
        self.output_result_edit.setReadOnly(True)
        self.output_result_edit.setPlaceholderText(
            "Chưa có video render nội bộ nào"
        )
        self.output_folder_quick_edit = QLineEdit()
        self.output_folder_quick_edit.setReadOnly(False)
        self.output_folder_quick_edit.setPlaceholderText(
            "Thư mục gợi ý khi bấm Xuất file sẽ hiện ở đây"
        )
        self.output_folder_quick_edit.editingFinished.connect(
            self.on_output_directory_quick_changed
        )
        self.output_export_status_label = QLabel(
            "Video render nội bộ sẽ sẵn sàng để preview sau khi render hoàn tất."
        )
        self.output_export_status_label.setObjectName("SectionHint")
        self.output_export_status_label.setWordWrap(True)
        output_actions = QHBoxLayout()
        output_actions.setSpacing(8)
        self.preview_video_btn = self._make_button("Xem video", "primary")
        self.preview_video_btn.clicked.connect(self.preview_rendered_video)
        self.export_file_btn = self._make_button("Xuất file", "success")
        self.export_file_btn.clicked.connect(self.export_rendered_video_file)
        self.choose_output_folder_btn = self._make_button("Chọn", "ghost")
        self.choose_output_folder_btn.setText("Chọn thư mục xuất")
        self.choose_output_folder_btn.clicked.connect(self.choose_output_directory)
        output_layout.addWidget(self._field_label("Video render nội bộ mới nhất"))
        output_layout.addWidget(self.output_result_edit)
        output_layout.addWidget(self.output_export_status_label)
        output_layout.addWidget(self._field_label("Thư mục mặc định khi xuất file"))
        output_layout.addWidget(self.output_folder_quick_edit)
        output_actions.addWidget(self.preview_video_btn)
        output_actions.addWidget(self.export_file_btn)
        output_actions.addWidget(self.choose_output_folder_btn)
        output_actions.addStretch(1)
        output_layout.addLayout(output_actions)

        summary_card, summary_layout = self._make_card(
            "Tổng quan nhanh",
            "Các chỉ số quan trọng luôn hiện phía trên để bạn không phải cuộn tìm lại.",
        )
        stats_grid = QGridLayout()
        stats_grid.setHorizontalSpacing(12)
        stats_grid.setVerticalSpacing(12)
        self.summary_labels = {}
        for idx, (title, key) in enumerate(
            [
                ("Ngôn ngữ nguồn", "sourceLanguage"),
                ("Số speaker", "speakers"),
                ("Bố cục audio", "voiceLayout"),
                ("Kiểu cleanup", "cleanupMode"),
            ]
        ):
            card, label = self._make_stat_card(title)
            stats_grid.addWidget(card, idx // 2, idx % 2)
            self.summary_labels[key] = label
        summary_layout.addLayout(stats_grid)
        summary_note = QLabel(
            "Sau khi phân tích xong, bạn chỉ cần chuyển tab bên dưới để chỉnh đúng phần cần làm."
        )
        summary_note.setObjectName("SectionHint")
        summary_note.setWordWrap(True)
        summary_layout.addWidget(summary_note)

        middle_row = QHBoxLayout()
        middle_row.setSpacing(14)

        middle_row.addWidget(sidebar_card, 1)

        middle_col = QVBoxLayout()
        middle_col.setSpacing(14)
        middle_col.addWidget(input_card, 1)
        middle_col.addWidget(output_card, 1)

        middle_row.addLayout(middle_col, 3)
        middle_row.addWidget(summary_card, 2)

        body.addLayout(middle_row, 0)

        self.main_tabs = QTabWidget()
        self.main_tabs.setDocumentMode(True)
        body.addWidget(self.main_tabs, 1)

        preview_page = QWidget()
        self.preview_page = preview_page
        preview_page_layout = QVBoxLayout(preview_page)
        preview_page_layout.setContentsMargins(0, 0, 0, 0)
        preview_page_layout.setSpacing(14)

        preview_card, preview_layout = self._make_card(
            "Preview trực quan",
            "Xem trước khung hình, vùng xử lý phụ đề cũ và kiểu chữ mới ngay trong app.",
        )
        self.preview_canvas = PreviewCanvas()
        self.preview_canvas.subtitle_dragged.connect(self.on_preview_subtitle_dragged)
        self.preview_canvas.cleanup_region_changed.connect(self.on_cleanup_region_changed)
        self.preview_canvas.watermark_scale_changed.connect(self.on_watermark_scale_dragged)
        preview_layout.addWidget(self.preview_canvas, 1)
        slider_grid = QGridLayout()
        slider_grid.setHorizontalSpacing(16)
        slider_grid.setVerticalSpacing(12)
        self.font_size_slider = self._make_slider(18, 72, 28, self.on_font_size_changed)
        self.blur_slider = self._make_slider(2, 24, 10, self.on_blur_changed)
        self.bottom_offset_slider = self._make_slider(
            12, 180, 54, self.on_bottom_offset_changed
        )
        self.font_size_value = QLabel("28 px")
        self.blur_value = QLabel("10 px")
        self.bottom_offset_value = QLabel("54 px")
        slider_grid.addWidget(self._field_label("Cỡ chữ vietsub"), 0, 0)
        slider_grid.addWidget(self.font_size_slider, 0, 1)
        slider_grid.addWidget(self.font_size_value, 0, 2)
        slider_grid.addWidget(self._field_label("Độ mờ phụ đề cũ"), 1, 0)
        slider_grid.addWidget(self.blur_slider, 1, 1)
        slider_grid.addWidget(self.blur_value, 1, 2)
        slider_grid.addWidget(self._field_label("Độ cao phụ đề mới"), 2, 0)
        slider_grid.addWidget(self.bottom_offset_slider, 2, 1)
        slider_grid.addWidget(self.bottom_offset_value, 2, 2)
        preview_layout.addLayout(slider_grid)
        self.preview_note = QLabel(
            "Khung vàng là vùng dọn phụ đề cũ. Phụ đề mới được dựng thử theo đúng font, màu, viền và vị trí hiện tại."
        )
        self.preview_note.setObjectName("SectionHint")
        self.preview_note.setWordWrap(True)
        preview_layout.addWidget(self.preview_note)
        snap_row = QHBoxLayout()
        snap_row.setSpacing(10)
        for label, preset in [
            ("Đặt trên", "top"),
            ("Căn giữa", "middle"),
            ("Đặt dưới", "bottom"),
        ]:
            button = self._make_button(label, "ghost")
            button.clicked.connect(
                lambda _checked=False, p=preset: self.apply_caption_position(p)
            )
            snap_row.addWidget(button)
        snap_row.addStretch(1)
        preview_layout.addLayout(snap_row)
        preview_page_layout.addWidget(preview_card, 3)

        watermark_card, watermark_layout = self._make_card(
            "Watermark",
            "Chỉnh watermark ngay cạnh preview để canh vị trí, bật/tắt và đổi kích thước nhanh hơn.",
        )
        watermark_top_row = QHBoxLayout()
        watermark_top_row.setSpacing(10)
        self.watermark_enabled_check = QCheckBox("Bật watermark")
        self.watermark_enabled_check.stateChanged.connect(self.on_basic_settings_changed)
        watermark_top_row.addWidget(self.watermark_enabled_check)
        watermark_top_row.addStretch(1)
        watermark_layout.addLayout(watermark_top_row)

        self.watermark_path_edit = QLineEdit()
        self.watermark_path_edit.setReadOnly(True)
        self.watermark_path_edit.setPlaceholderText("Chưa chọn ảnh watermark")
        watermark_btn = self._make_button("Chọn ảnh", "ghost")
        watermark_btn.clicked.connect(self.choose_watermark_image)
        watermark_file_row = QWidget()
        watermark_file_layout = QHBoxLayout(watermark_file_row)
        watermark_file_layout.setContentsMargins(0, 0, 0, 0)
        watermark_file_layout.setSpacing(8)
        watermark_file_layout.addWidget(self.watermark_path_edit, 1)
        watermark_file_layout.addWidget(watermark_btn)
        watermark_layout.addWidget(self._field_label("Ảnh watermark"))
        watermark_layout.addWidget(watermark_file_row)

        watermark_controls = QGridLayout()
        watermark_controls.setHorizontalSpacing(14)
        watermark_controls.setVerticalSpacing(10)
        self.watermark_position_combo = self._make_combo(
            WATERMARK_POSITION_OPTIONS, self.on_basic_settings_changed
        )
        self.watermark_scale_slider = self._make_slider(5, 50, 15, self.on_watermark_size_changed)
        self.watermark_scale_value = QLabel("15%")
        self.watermark_scale_value.setFixedWidth(44)
        watermark_scale_row = QWidget()
        watermark_scale_layout = QHBoxLayout(watermark_scale_row)
        watermark_scale_layout.setContentsMargins(0, 0, 0, 0)
        watermark_scale_layout.setSpacing(8)
        watermark_scale_layout.addWidget(self.watermark_scale_slider, 1)
        watermark_scale_layout.addWidget(self.watermark_scale_value)
        watermark_controls.addWidget(self._field_label("Vị trí"), 0, 0)
        watermark_controls.addWidget(self.watermark_position_combo, 0, 1)
        watermark_controls.addWidget(self._field_label("Kích thước"), 1, 0)
        watermark_controls.addWidget(watermark_scale_row, 1, 1)
        watermark_layout.addLayout(watermark_controls)

        watermark_hint = QLabel(
            "Bạn có thể kéo nút vàng ở góc watermark ngay trên preview để resize trực tiếp."
        )
        watermark_hint.setObjectName("SectionHint")
        watermark_hint.setWordWrap(True)
        watermark_layout.addWidget(watermark_hint)
        preview_page_layout.addWidget(watermark_card, 0)

        render_video_card, render_video_layout = self._make_card(
            "Video sau render",
            "Bấm Xem video sau khi render để phát trực tiếp kết quả cuối cùng ngay trong hệ thống.",
        )
        self.render_preview_status_label = QLabel(
            "Chưa có video render để xem trước."
        )
        self.render_preview_status_label.setObjectName("SectionHint")
        self.render_preview_status_label.setWordWrap(True)
        render_video_layout.addWidget(self.render_preview_status_label)
        if self.render_video_widget is not None:
            self.render_video_widget.setMinimumHeight(320)
            self.render_video_widget.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
            )
            render_video_layout.addWidget(self.render_video_widget, 1)
        else:
            self.render_video_unavailable_label = QLabel(
                "Qt Multimedia Video chưa sẵn sàng trong môi trường này nên app chưa thể phát video nội bộ."
            )
            self.render_video_unavailable_label.setAlignment(
                Qt.AlignmentFlag.AlignCenter
            )
            self.render_video_unavailable_label.setWordWrap(True)
            self.render_video_unavailable_label.setMinimumHeight(220)
            self.render_video_unavailable_label.setObjectName("SectionHint")
            render_video_layout.addWidget(self.render_video_unavailable_label, 1)
        render_controls = QHBoxLayout()
        render_controls.setSpacing(10)
        self.pause_preview_btn = self._make_button("Tạm dừng", "ghost")
        self.pause_preview_btn.clicked.connect(self.pause_render_preview)
        self.stop_preview_btn = self._make_button("Dừng phát", "ghost")
        self.stop_preview_btn.clicked.connect(self.stop_render_preview)
        render_controls.addWidget(self.pause_preview_btn)
        render_controls.addWidget(self.stop_preview_btn)
        render_controls.addStretch(1)
        render_video_layout.addLayout(render_controls)
        seek_row = QHBoxLayout()
        seek_row.setSpacing(10)
        self.render_preview_position_label = QLabel("00:00")
        self.render_preview_position_label.setObjectName("FieldLabel")
        self.render_preview_seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.render_preview_seek_slider.setRange(0, 0)
        self.render_preview_seek_slider.setEnabled(False)
        self.render_preview_seek_slider.sliderPressed.connect(
            self.on_render_preview_slider_pressed
        )
        self.render_preview_seek_slider.sliderMoved.connect(
            self.on_render_preview_slider_moved
        )
        self.render_preview_seek_slider.sliderReleased.connect(
            self.on_render_preview_slider_released
        )
        self.render_preview_duration_label = QLabel("00:00")
        self.render_preview_duration_label.setObjectName("FieldLabel")
        seek_row.addWidget(self.render_preview_position_label)
        seek_row.addWidget(self.render_preview_seek_slider, 1)
        seek_row.addWidget(self.render_preview_duration_label)
        render_video_layout.addLayout(seek_row)
        preview_page_layout.addWidget(render_video_card, 2)

        analysis_card, analysis_layout = self._make_card(
            "Chi tiết phân tích",
            "Cảnh báo và timeline được gom chung để kiểm tra nhanh mà vẫn không làm giao diện quá dài.",
        )
        analysis_split = QHBoxLayout()
        analysis_split.setSpacing(14)
        warning_col = QVBoxLayout()
        warning_col.addWidget(self._field_label("Cảnh báo"))
        self.warning_box = QPlainTextEdit()
        self.warning_box.setReadOnly(True)
        self.warning_box.setPlaceholderText(
            "Cảnh báo và ghi chú sau khi phân tích sẽ hiện ở đây."
        )
        warning_col.addWidget(self.warning_box)
        self.warning_box.setMinimumHeight(100)
        self.warning_box.setMaximumHeight(160)
        timeline_col = QVBoxLayout()
        timeline_col.addWidget(self._field_label("Timeline thoại"))
        self.timeline_box = QPlainTextEdit()
        self.timeline_box.setReadOnly(True)
        self.timeline_box.setPlaceholderText(
            "Các câu thoại đầu tiên sẽ được hiển thị để bạn kiểm tra speaker."
        )
        timeline_col.addWidget(self.timeline_box)
        self.timeline_box.setMinimumHeight(100)
        self.timeline_box.setMaximumHeight(160)
        analysis_split.addLayout(warning_col, 4)
        analysis_split.addLayout(timeline_col, 5)
        analysis_layout.addLayout(analysis_split)
        preview_page_layout.addWidget(analysis_card, 2)
        self.main_tabs.addTab(preview_page, "Preview")

        subtitle_page = QWidget()
        subtitle_page_layout = QVBoxLayout(subtitle_page)
        subtitle_page_layout.setContentsMargins(0, 0, 0, 0)
        subtitle_page_layout.setSpacing(14)
        subtitle_card, subtitle_layout = self._make_card(
            "Subtitle timeline",
            "Toàn bộ câu thoại được giữ theo mốc thời gian hiện hành. Bạn có thể sửa trực tiếp, import file SRT ngoài hoặc export SRT đang dùng trước khi render.",
        )
        subtitle_toolbar = QHBoxLayout()
        subtitle_toolbar.setSpacing(10)
        self.import_srt_btn = self._make_button("Import SRT", "ghost")
        self.import_srt_btn.clicked.connect(self.import_subtitle_srt)
        self.export_srt_btn = self._make_button("Export SRT", "ghost")
        self.export_srt_btn.clicked.connect(self.export_subtitle_srt)
        self.subtitle_editor_status = QLabel(
            "Subtitle AI tạo sau khi phân tích sẽ xuất hiện ở đây."
        )
        self.subtitle_editor_status.setObjectName("SectionHint")
        self.subtitle_editor_status.setWordWrap(True)
        subtitle_toolbar.addWidget(self.import_srt_btn)
        subtitle_toolbar.addWidget(self.export_srt_btn)
        subtitle_toolbar.addStretch(1)
        subtitle_layout.addLayout(subtitle_toolbar)
        subtitle_layout.addWidget(self.subtitle_editor_status)
        self.subtitle_table = QTableWidget(0, 3)
        self.subtitle_table.setHorizontalHeaderLabels(["Bắt đầu", "Kết thúc", "Nội dung subtitle"])
        self.subtitle_table.verticalHeader().setVisible(False)
        self.subtitle_table.setAlternatingRowColors(True)
        self.subtitle_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems)
        self.subtitle_table.setWordWrap(True)
        self.subtitle_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.subtitle_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self.subtitle_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self.subtitle_table.setMinimumHeight(200)
        self.subtitle_table.setMaximumHeight(350)
        self.subtitle_table.itemChanged.connect(self.on_subtitle_table_item_changed)
        subtitle_layout.addWidget(self.subtitle_table)
        subtitle_page_layout.addWidget(subtitle_card, 1)
        self.main_tabs.addTab(subtitle_page, "Subtitle")

        settings_card, settings_layout = self._make_card(
            "Thiết lập thông minh",
            "Điều khiển cách nhận diện audio gốc, nhịp đọc, hiển thị vietsub và lựa chọn font ngay trong app.",
        )
        settings_grid = QGridLayout()
        settings_grid.setHorizontalSpacing(14)
        settings_grid.setVerticalSpacing(12)
        settings_layout.addLayout(settings_grid)
        self.source_language_combo = self._make_combo(
            LANGUAGE_OPTIONS, self.on_basic_settings_changed
        )
        self.target_language_combo = self._make_combo(
            TARGET_LANGUAGE_OPTIONS, self.on_basic_settings_changed
        )
        self.speaker_detection_combo = self._make_combo(
            SPEAKER_DETECTION_OPTIONS, self.on_speaker_detection_changed
        )
        self.speaker_count_spin = QSpinBox()
        self.speaker_count_spin.setRange(1, 4)
        self.speaker_count_spin.valueChanged.connect(self.on_basic_settings_changed)
        self.timing_mode_combo = self._make_combo(
            TIMING_MODE_OPTIONS, self.on_basic_settings_changed
        )
        self.video_codec_combo = self._make_combo(
            VIDEO_CODEC_OPTIONS, self.on_basic_settings_changed
        )
        self.ui_theme_combo = self._make_combo(
            UI_THEME_OPTIONS, self.on_theme_preset_changed
        )
        self.cleanup_combo = self._make_combo(
            CLEANUP_OPTIONS, self.on_basic_settings_changed
        )
        self.subtitle_enabled_combo = self._make_combo(
            SUBTITLE_VISIBILITY_OPTIONS, self.on_basic_settings_changed
        )
        self.subtitle_position_combo = self._make_combo(
            SUBTITLE_POSITION_OPTIONS, self.on_basic_settings_changed
        )
        self.font_combo = self._make_combo(
            [(option["value"], option["label"]) for option in FONT_OPTIONS],
            self.on_font_changed,
        )
        self.stroke_width_spin = QSpinBox()
        self.stroke_width_spin.setRange(0, 6)
        self.stroke_width_spin.valueChanged.connect(self.on_basic_settings_changed)
        self.max_words_spin = QSpinBox()
        self.max_words_spin.setRange(2, 8)
        self.max_words_spin.valueChanged.connect(self.on_basic_settings_changed)
        self.font_color_btn = QPushButton("Màu chữ")
        self.font_color_btn.clicked.connect(lambda: self.pick_color("fontColor"))
        self.stroke_color_btn = QPushButton("Màu viền")
        self.stroke_color_btn.clicked.connect(lambda: self.pick_color("strokeColor"))
        self.intro_enabled_check = QCheckBox("Bật teaser")
        self.intro_enabled_check.stateChanged.connect(self.on_basic_settings_changed)
        self.intro_duration_spin = QDoubleSpinBox()
        self.intro_duration_spin.setRange(8.0, 16.0)
        self.intro_duration_spin.setSingleStep(0.5)
        self.intro_duration_spin.valueChanged.connect(self.on_basic_settings_changed)
        self.intro_voice_combo = self._make_combo(
            INTRO_TTS_OPTIONS, self.on_basic_settings_changed
        )
        self.intro_voice_combo.setEditable(True)
        if self.intro_voice_combo.lineEdit() is not None:
            self.intro_voice_combo.lineEdit().setPlaceholderText(
                "Chọn giọng EdgeTTS/VieNeu hoặc nhập Edge voice, ví dụ en-US-AvaNeural"
            )
            self.intro_voice_combo.lineEdit().returnPressed.connect(
                self.on_basic_settings_changed
            )
        self.intro_background_check = QCheckBox("Giữ âm nền teaser")
        self.intro_background_check.stateChanged.connect(self.on_basic_settings_changed)
        self.intro_background_volume_spin = QDoubleSpinBox()
        self.intro_background_volume_spin.setRange(0.0, 0.3)
        self.intro_background_volume_spin.setSingleStep(0.01)
        self.intro_background_volume_spin.valueChanged.connect(
            self.on_basic_settings_changed
        )
        self.keep_original_audio_check = QCheckBox("Giữ audio gốc nhỏ")
        self.keep_original_audio_check.stateChanged.connect(
            self.on_basic_settings_changed
        )
        self.output_mp4_check = QCheckBox("Xuất MP4")
        self.output_mp4_check.stateChanged.connect(self.on_basic_settings_changed)
        self.output_draft_check = QCheckBox("Xuất Draft")
        self.output_draft_check.stateChanged.connect(self.on_basic_settings_changed)
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setPlaceholderText("Ví dụ: C:/Users/.../output")
        self.output_dir_edit.editingFinished.connect(self.on_basic_settings_changed)
        self.draft_dir_edit = QLineEdit()
        self.draft_dir_edit.setPlaceholderText("Ví dụ: C:/Users/.../draft")
        self.draft_dir_edit.editingFinished.connect(self.on_basic_settings_changed)
        output_dir_btn = self._make_button("Chọn", "ghost")
        output_dir_btn.clicked.connect(
            lambda: self.choose_directory(self.output_dir_edit)
        )
        draft_dir_btn = self._make_button("Chọn", "ghost")
        draft_dir_btn.clicked.connect(
            lambda: self.choose_directory(self.draft_dir_edit)
        )
        self.region_x_spin = self._make_region_spin()
        self.region_y_spin = self._make_region_spin()
        self.region_w_spin = self._make_region_spin()
        self.region_h_spin = self._make_region_spin()

        rows = [
            (
                "Chế độ encode",
                self.video_codec_combo,
                "Preset giao diện",
                self.ui_theme_combo,
            ),
            (
                "Ngôn ngữ nguồn",
                self.source_language_combo,
                "Ngôn ngữ subtitle",
                self.target_language_combo,
            ),
            (
                "Nhận diện speaker",
                self.speaker_detection_combo,
                "Số speaker",
                self.speaker_count_spin,
            ),
            (
                "Chế độ timing",
                self.timing_mode_combo,
                "Xử lý sub cũ",
                self.cleanup_combo,
            ),
            (
                "Bật/Tắt vietsub",
                self.subtitle_enabled_combo,
                "Vị trí vietsub",
                self.subtitle_position_combo,
            ),
            (
                "Font chữ",
                self.font_combo,
                "Độ dày viền",
                self.stroke_width_spin,
            ),
            (
                "Tối đa từ mỗi dòng",
                self.max_words_spin,
                "",
                None,
            ),
        ]
        for row, (left_label, left_widget, right_label, right_widget) in enumerate(
            rows
        ):
            settings_grid.addWidget(self._field_label(left_label), row, 0)
            settings_grid.addWidget(left_widget, row, 1)
            if right_label and right_widget is not None:
                settings_grid.addWidget(self._field_label(right_label), row, 2)
                settings_grid.addWidget(right_widget, row, 3)
        self.font_color_btn.setObjectName("ColorButton")
        self.stroke_color_btn.setObjectName("ColorButton")
        settings_grid.addWidget(self.font_color_btn, 7, 0, 1, 2)
        settings_grid.addWidget(self.stroke_color_btn, 7, 2, 1, 2)
        settings_grid.addWidget(self._field_label("Palette màu chữ"), 8, 0)
        settings_grid.addLayout(
            self._build_palette_row("fontColor", FONT_COLOR_SWATCHES), 8, 1, 1, 3
        )
        settings_grid.addWidget(self._field_label("Palette màu viền"), 9, 0)
        settings_grid.addLayout(
            self._build_palette_row("strokeColor", STROKE_COLOR_SWATCHES), 9, 1, 1, 3
        )
        settings_grid.addWidget(self.intro_enabled_check, 10, 0, 1, 2)
        settings_grid.addWidget(self.keep_original_audio_check, 10, 2, 1, 2)
        settings_grid.addWidget(self._field_label("Thời lượng teaser"), 11, 0)
        settings_grid.addWidget(self.intro_duration_spin, 11, 1)
        settings_grid.addWidget(self._field_label("Giọng teaser"), 11, 2)
        settings_grid.addWidget(self.intro_voice_combo, 11, 3)
        settings_grid.addWidget(self.intro_background_check, 12, 0, 1, 2)
        settings_grid.addWidget(self._field_label("Âm nền teaser"), 12, 2)
        settings_grid.addWidget(self.intro_background_volume_spin, 12, 3)
        settings_grid.addWidget(self.output_mp4_check, 13, 0)
        settings_grid.addWidget(self.output_draft_check, 13, 1)
        settings_grid.addWidget(self._field_label("Thư mục output"), 14, 0)
        output_row = QWidget()
        output_row_layout = QHBoxLayout(output_row)
        output_row_layout.setContentsMargins(0, 0, 0, 0)
        output_row_layout.addWidget(self.output_dir_edit)
        output_row_layout.addWidget(output_dir_btn)
        settings_grid.addWidget(output_row, 14, 1, 1, 3)
        settings_grid.addWidget(self._field_label("Thư mục draft"), 15, 0)
        draft_row = QWidget()
        draft_row_layout = QHBoxLayout(draft_row)
        draft_row_layout.setContentsMargins(0, 0, 0, 0)
        draft_row_layout.addWidget(self.draft_dir_edit)
        draft_row_layout.addWidget(draft_dir_btn)
        settings_grid.addWidget(draft_row, 15, 1, 1, 3)
        settings_grid.addWidget(self._field_label("Vùng sub cũ X"), 16, 0)
        settings_grid.addWidget(self.region_x_spin, 16, 1)
        settings_grid.addWidget(self._field_label("Vùng sub cũ Y"), 16, 2)
        settings_grid.addWidget(self.region_y_spin, 16, 3)
        settings_grid.addWidget(self._field_label("Vùng sub cũ W"), 17, 0)
        settings_grid.addWidget(self.region_w_spin, 17, 1)
        settings_grid.addWidget(self._field_label("Vùng sub cũ H"), 17, 2)
        settings_grid.addWidget(self.region_h_spin, 17, 3)

        settings_page = QWidget()
        settings_page_layout = QVBoxLayout(settings_page)
        settings_page_layout.setContentsMargins(0, 0, 0, 0)
        settings_page_layout.addWidget(settings_card)
        settings_page_layout.addStretch(1)
        self.main_tabs.addTab(settings_page, "Thiết lập")

        voice_card, voice_layout_root = self._make_card(
            "Gán giọng theo nhân vật",
            "Giữ ổn định giọng của nhân vật chính và đổi từng speaker ngay sau khi phân tích.",
        )
        self.voice_overview_label = QLabel("Chưa có kết quả phân tích speaker.")
        self.voice_overview_label.setObjectName("SectionHint")
        self.voice_overview_label.setWordWrap(True)
        voice_layout_root.addWidget(self.voice_overview_label)
        self.voice_layout = QVBoxLayout()
        self.voice_layout.setSpacing(10)
        voice_layout_root.addLayout(self.voice_layout)
        voice_page = QWidget()
        voice_page_layout = QVBoxLayout(voice_page)
        voice_page_layout.setContentsMargins(0, 0, 0, 0)
        voice_page_layout.addWidget(voice_card)
        voice_page_layout.addStretch(1)
        self.main_tabs.addTab(voice_page, "Nhân vật")

        status_card, status_layout = self._make_card(
            "Tiến trình & nhật ký",
            "Theo dõi phase chạy pipeline, phần trăm hoàn thành và log chi tiết ngay trong ứng dụng.",
        )
        progress_row = QHBoxLayout()
        progress_row.setSpacing(12)
        self.phase_label = self._make_chip("Trạng thái: idle")
        self.step_label = self._make_chip("Bước: chờ")
        progress_row.addWidget(self.phase_label)
        progress_row.addWidget(self.step_label)
        progress_row.addStretch(1)
        status_layout.addLayout(progress_row)
        self.progress_bar = QProgressBar()
        self.progress_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        status_layout.addWidget(self.progress_bar)
        self.log_box = QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setPlaceholderText("Log chạy pipeline sẽ hiển thị tại đây.")
        self.log_box.setMinimumHeight(150)
        self.log_box.setMaximumHeight(280)
        status_layout.addWidget(self.log_box)
        status_page = QWidget()
        status_page_layout = QVBoxLayout(status_page)
        status_page_layout.setContentsMargins(0, 0, 0, 0)
        status_page_layout.addWidget(status_card)
        self.main_tabs.addTab(status_page, "Tiến trình")

        # ── Batch Processing Tab ────────────────────────────────────
        batch_page = QWidget()
        batch_page_layout = QVBoxLayout(batch_page)
        batch_page_layout.setContentsMargins(0, 0, 0, 0)
        batch_page_layout.setSpacing(14)

        batch_queue_card, batch_queue_layout = self._make_card(
            "Xử lý hàng loạt",
            "Thêm nhiều video cùng lúc, dùng chung một bộ setting, và hệ thống sẽ tự động "
            "phân tích → lồng tiếng → render → xuất file cho từng video theo thứ tự.",
        )

        batch_toolbar = QHBoxLayout()
        batch_toolbar.setSpacing(8)
        self.batch_add_btn = self._make_button("Thêm video", "primary")
        self.batch_add_btn.clicked.connect(self.batch_add_videos)
        self.batch_remove_btn = self._make_button("Xóa chọn", "ghost")
        self.batch_remove_btn.clicked.connect(self.batch_remove_selected)
        self.batch_clear_btn = self._make_button("Xóa tất cả", "ghost")
        self.batch_clear_btn.clicked.connect(self.batch_clear_all)
        self.batch_up_btn = self._make_button("▲ Lên", "ghost")
        self.batch_up_btn.clicked.connect(self.batch_move_up)
        self.batch_down_btn = self._make_button("▼ Xuống", "ghost")
        self.batch_down_btn.clicked.connect(self.batch_move_down)

        self.batch_start_btn = self._make_button("Bắt đầu batch", "success")
        self.batch_start_btn.clicked.connect(self.batch_start)
        self.batch_stop_btn = self._make_button("Tạm dừng", "ghost")
        self.batch_stop_btn.clicked.connect(self.batch_stop)
        self.batch_stop_btn.setEnabled(False)

        batch_toolbar.addWidget(self.batch_add_btn)
        batch_toolbar.addWidget(self.batch_remove_btn)
        batch_toolbar.addWidget(self.batch_clear_btn)
        batch_toolbar.addWidget(self.batch_up_btn)
        batch_toolbar.addWidget(self.batch_down_btn)
        batch_toolbar.addSpacing(20) # Add a small visual gap
        batch_toolbar.addWidget(self.batch_start_btn)
        batch_toolbar.addWidget(self.batch_stop_btn)
        batch_toolbar.addStretch(1)
        batch_queue_layout.addLayout(batch_toolbar)

        self.batch_table = QTableWidget(0, 5)
        self.batch_table.setHorizontalHeaderLabels(
            ["#", "Tên video", "Trạng thái", "Tiến độ", "Output"]
        )
        self.batch_table.verticalHeader().setVisible(False)
        self.batch_table.setAlternatingRowColors(True)
        self.batch_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.batch_table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )
        self.batch_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.batch_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.batch_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self.batch_table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )
        self.batch_table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.Stretch
        )
        self.batch_table.setMinimumHeight(200)
        self.batch_table.setMaximumHeight(220)
        batch_queue_layout.addWidget(self.batch_table)

        batch_output_row = QHBoxLayout()
        batch_output_row.setSpacing(8)
        batch_output_row.addWidget(self._field_label("Thư mục xuất batch"))
        self.batch_output_dir_edit = QLineEdit()
        self.batch_output_dir_edit.setPlaceholderText(
            "Chọn thư mục để tự động xuất tất cả video sau khi render"
        )
        self.batch_output_dir_edit.setReadOnly(True)
        batch_output_browse_btn = self._make_button("Chọn", "ghost")
        batch_output_browse_btn.clicked.connect(self.batch_choose_output_dir)
        batch_output_row.addWidget(self.batch_output_dir_edit, 1)
        batch_output_row.addWidget(batch_output_browse_btn)
        batch_queue_layout.addLayout(batch_output_row)

        batch_watermark_hint = QLabel(
            "💡 Tip: Thiết lập watermark, giọng đọc, subtitle và các setting khác "
            "trong tab Thiết lập trước khi bắt đầu batch. Tất cả video sẽ dùng chung "
            "bộ setting hiện tại."
        )
        batch_watermark_hint.setObjectName("SectionHint")
        batch_watermark_hint.setWordWrap(True)
        batch_queue_layout.addWidget(batch_watermark_hint)

        batch_status_row = QHBoxLayout()
        batch_status_row.setSpacing(12)
        self.batch_status_label = QLabel("Chưa có video trong danh sách batch.")
        self.batch_status_label.setObjectName("SectionHint")
        self.batch_status_label.setWordWrap(True)
        batch_status_row.addWidget(self.batch_status_label, 1)
        batch_queue_layout.addLayout(batch_status_row)

        self.batch_progress_bar = QProgressBar()
        self.batch_progress_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.batch_progress_bar.setTextVisible(True)
        self.batch_progress_bar.setFormat("Batch: %p%")
        batch_queue_layout.addWidget(self.batch_progress_bar)

        batch_page_layout.addWidget(batch_queue_card, 3)

        batch_log_card, batch_log_layout = self._make_card(
            "Nhật ký batch",
            "Toàn bộ quá trình xử lý hàng loạt được ghi lại để theo dõi tiến trình và debug nếu cần.",
        )
        self.batch_log_box = QPlainTextEdit()
        self.batch_log_box.setReadOnly(True)
        self.batch_log_box.setPlaceholderText(
            "Log batch sẽ hiển thị tại đây khi bắt đầu xử lý hàng loạt."
        )
        self.batch_log_box.setMinimumHeight(120)
        self.batch_log_box.setMaximumHeight(200)
        batch_log_layout.addWidget(self.batch_log_box)
        batch_page_layout.addWidget(batch_log_card, 1)

        self.main_tabs.addTab(batch_page, "Batch")

        self.animated_cards = [
            hero_card,
            sidebar_card,
            input_card,
            summary_card,
            preview_card,
            analysis_card,
            subtitle_card,
            settings_card,
            voice_card,
            status_card,
            batch_queue_card,
            batch_log_card,
        ]



