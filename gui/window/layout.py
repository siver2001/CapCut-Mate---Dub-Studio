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
    QStackedWidget,
    QStyle,
    QTabWidget,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from gui.config import (
    BOX_BORDER_COLOR_SWATCHES,
    BOX_FILL_COLOR_SWATCHES,
    BOX_LAYOUT_OPTIONS,
    BOX_STYLE_OPTIONS,
    CLEANUP_OPTIONS,
    FONT_COLOR_SWATCHES,
    FONT_GROUP_OPTIONS,
    FONT_OPTIONS,
    INTRO_TTS_OPTIONS,
    INTRO_VOICE_OPTIONS,
    LANGUAGE_OPTIONS,
    SPEAKER_DETECTION_OPTIONS,
    STROKE_COLOR_SWATCHES,
    SUBTITLE_POSITION_OPTIONS,
    SUBTITLE_VISIBILITY_OPTIONS,
    TEXT_EFFECT_OPTIONS,
    TARGET_LANGUAGE_OPTIONS,
    TIMING_MODE_OPTIONS,
    UI_THEME_OPTIONS,
    VIDEO_CODEC_OPTIONS,
    VOICE_OPTIONS,
    WATERMARK_POSITION_OPTIONS,
)
from gui.preview_canvas import PreviewCanvas
from gui.utils import APP_STYLESHEET, repair_mojibake_text
from .helpers import SafeDoubleSpinBox, SafeSlider, SafeSpinBox, SectionWidget


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
        self.font_size_slider = self._make_slider(10, 72, 14, self.on_font_size_changed)

        self.blur_slider = self._make_slider(2, 24, 10, self.on_blur_changed)
        self.bottom_offset_slider = self._make_slider(
            12, 180, 54, self.on_bottom_offset_changed
        )
        self.font_size_value = QLabel("14 px")
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
            "Preview này dùng để xem subtitle mới và watermark trên video theo đúng font, màu, viền và vị trí hiện tại."
        )
        self.preview_note.setObjectName("SectionHint")
        self.preview_note.setWordWrap(True)
        preview_layout.addWidget(self.preview_note)
        self.preview_style_card = QFrame()
        self.preview_style_card.setObjectName("StatCard")
        preview_style_layout = QVBoxLayout(self.preview_style_card)
        preview_style_layout.setContentsMargins(16, 16, 16, 16)
        preview_style_layout.setSpacing(8)
        self.preview_style_title = QLabel("Live style preview")
        self.preview_style_title.setObjectName("StatTitle")
        self.preview_style_label = QLabel("Subtitle style will update here")
        self.preview_style_label.setWordWrap(True)
        self.preview_style_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_style_label.setMinimumHeight(88)
        self.preview_style_meta = QLabel("Font, box, effect va preset hien tai.")
        self.preview_style_meta.setObjectName("SectionHint")
        self.preview_style_meta.setWordWrap(True)
        preview_style_layout.addWidget(self.preview_style_title)
        preview_style_layout.addWidget(self.preview_style_label)
        preview_style_layout.addWidget(self.preview_style_meta)
        preview_layout.addWidget(self.preview_style_card)
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
        self.speaker_count_spin = SafeSpinBox()
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
        self.font_group_combo = self._make_combo(
            FONT_GROUP_OPTIONS, self.on_font_group_changed
        )
        self.font_combo = self._make_combo(
            [(option["value"], option["label"]) for option in FONT_OPTIONS],
            self.on_font_changed,
        )
        self.font_size_spin = SafeSpinBox()
        self.font_size_spin.setRange(10, 72)
        self.font_size_spin.setSuffix(" px")
        self.font_size_spin.setValue(14)
        self.font_size_spin.setToolTip(
            "Cỡ chữ subtitle. Số càng lớn thì chữ càng to."
        )
        self.font_size_spin.valueChanged.connect(self.on_font_size_changed)
        self.stroke_width_spin = SafeSpinBox()
        self.stroke_width_spin.setRange(0, 6)
        self.stroke_width_spin.valueChanged.connect(self.on_basic_settings_changed)
        self.max_words_spin = SafeSpinBox()
        self.max_words_spin.setRange(2, 8)
        self.max_words_spin.setToolTip(
            "Giới hạn số từ trong một dòng subtitle trước khi hệ thống tự xuống dòng."
        )
        self.max_words_spin.valueChanged.connect(self.on_basic_settings_changed)
        self.font_color_btn = QPushButton("Màu chữ")
        self.font_color_btn.clicked.connect(lambda: self.pick_color("fontColor"))
        self.stroke_color_btn = QPushButton("Màu viền")
        self.stroke_color_btn.clicked.connect(lambda: self.pick_color("strokeColor"))
        self.subtitle_box_check = QCheckBox("Subtitle trong box")
        self.subtitle_box_check.stateChanged.connect(self.on_basic_settings_changed)
        self.text_effect_combo = self._make_combo(
            TEXT_EFFECT_OPTIONS, self.on_basic_settings_changed
        )
        self.box_style_combo = self._make_combo(
            BOX_STYLE_OPTIONS, self.on_box_style_changed
        )
        self.box_layout_combo = self._make_combo(
            BOX_LAYOUT_OPTIONS, self.on_box_style_detail_changed
        )
        self.box_radius_spin = SafeSpinBox()
        self.box_radius_spin.setRange(0, 40)
        self.box_radius_spin.setValue(16)
        self.box_radius_spin.setSuffix(" px")
        self.box_radius_spin.valueChanged.connect(self.on_box_style_detail_changed)
        self.box_border_width_spin = SafeSpinBox()
        self.box_border_width_spin.setRange(0, 8)
        self.box_border_width_spin.setValue(2)
        self.box_border_width_spin.valueChanged.connect(self.on_box_style_detail_changed)
        self.box_fill_opacity_spin = SafeDoubleSpinBox()
        self.box_fill_opacity_spin.setRange(0.15, 1.0)
        self.box_fill_opacity_spin.setDecimals(2)
        self.box_fill_opacity_spin.setSingleStep(0.05)
        self.box_fill_opacity_spin.setValue(0.86)
        self.box_fill_opacity_spin.setToolTip(
            "Độ đậm của nền box. Số càng lớn thì nền càng rõ."
        )
        self.box_fill_opacity_spin.valueChanged.connect(self.on_box_style_detail_changed)
        self.box_fill_color_btn = QPushButton("Nền box")
        self.box_fill_color_btn.clicked.connect(lambda: self.pick_color("boxFillColor"))
        self.box_border_color_btn = QPushButton("Viền box")
        self.box_border_color_btn.clicked.connect(lambda: self.pick_color("boxBorderColor"))
        self.intro_enabled_check = QCheckBox("Bật teaser")
        self.intro_enabled_check.stateChanged.connect(self.on_basic_settings_changed)
        self.intro_duration_spin = SafeDoubleSpinBox()
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
        self.intro_background_volume_spin = SafeDoubleSpinBox()
        self.intro_background_volume_spin.setRange(0.0, 0.3)
        self.intro_background_volume_spin.setSingleStep(0.01)
        self.intro_background_volume_spin.valueChanged.connect(
            self.on_basic_settings_changed
        )
        self.keep_original_audio_check = QCheckBox("Giữ audio gốc nhỏ")
        self.keep_original_audio_check.stateChanged.connect(
            self.on_basic_settings_changed
        )
        self.background_music_enabled_check = QCheckBox("Nhạc nền toàn video")
        self.background_music_enabled_check.stateChanged.connect(
            self.on_basic_settings_changed
        )
        self.background_music_volume_spin = SafeDoubleSpinBox()
        self.background_music_volume_spin.setRange(0.0, 1.0)
        self.background_music_volume_spin.setSingleStep(0.05)
        self.background_music_volume_spin.setValue(0.12)
        self.background_music_volume_spin.setToolTip(
            "Âm lượng riêng cho nhạc nền. Nhạc ngắn sẽ tự lặp tới hết video."
        )
        self.background_music_volume_spin.valueChanged.connect(
            self.on_basic_settings_changed
        )
        self.background_music_path_edit = QLineEdit()
        self.background_music_path_edit.setReadOnly(True)
        self.background_music_path_edit.setPlaceholderText(
            "Chưa chọn file nhạc nền (.mp3, .wav, .m4a...)"
        )
        self.background_music_choose_btn = self._make_button("Chọn nhạc", "ghost")
        self.background_music_choose_btn.clicked.connect(
            self.choose_background_music_file
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
                "Nhóm font",
                self.font_group_combo,
                "Font chữ",
                self.font_combo,
            ),
            (
                "Cỡ chữ",
                self.font_size_spin,
                "Độ dày viền",
                self.stroke_width_spin,
            ),
            (
                "Tối đa từ mỗi dòng sub",
                self.max_words_spin,
                "Mẫu chữ (CapCut)",
                self.text_effect_combo,
            ),
            (
                "Preset box",
                self.box_style_combo,
                "Kiểu box",
                self.box_layout_combo,
            ),
            (
                "Bo góc box",
                self.box_radius_spin,
                "Độ dày viền box",
                self.box_border_width_spin,
            ),
            (
                "Độ đậm nền box",
                self.box_fill_opacity_spin,
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
        self.box_fill_color_btn.setObjectName("ColorButton")
        self.box_border_color_btn.setObjectName("ColorButton")
        settings_grid.addWidget(self.font_color_btn, 10, 0, 1, 2)
        settings_grid.addWidget(self.stroke_color_btn, 10, 2, 1, 2)
        settings_grid.addWidget(self.subtitle_box_check, 11, 0, 1, 2)
        settings_grid.addWidget(self.box_fill_color_btn, 11, 2)
        settings_grid.addWidget(self.box_border_color_btn, 11, 3)
        settings_grid.addWidget(self._field_label("Palette màu chữ"), 12, 0)
        settings_grid.addLayout(
            self._build_palette_row("fontColor", FONT_COLOR_SWATCHES), 12, 1, 1, 3
        )
        settings_grid.addWidget(self._field_label("Palette màu viền"), 13, 0)
        settings_grid.addLayout(
            self._build_palette_row("strokeColor", STROKE_COLOR_SWATCHES), 13, 1, 1, 3
        )
        settings_grid.addWidget(self._field_label("Palette nền box"), 14, 0)
        settings_grid.addLayout(
            self._build_palette_row("boxFillColor", BOX_FILL_COLOR_SWATCHES), 14, 1, 1, 3
        )
        settings_grid.addWidget(self._field_label("Palette viền box"), 15, 0)
        settings_grid.addLayout(
            self._build_palette_row("boxBorderColor", BOX_BORDER_COLOR_SWATCHES), 15, 1, 1, 3
        )
        settings_grid.addWidget(self.intro_enabled_check, 16, 0, 1, 2)
        settings_grid.addWidget(self.keep_original_audio_check, 16, 2, 1, 2)
        settings_grid.addWidget(self._field_label("Thời lượng teaser"), 17, 0)
        settings_grid.addWidget(self.intro_duration_spin, 17, 1)
        settings_grid.addWidget(self._field_label("Giọng teaser"), 17, 2)
        settings_grid.addWidget(self.intro_voice_combo, 17, 3)
        settings_grid.addWidget(self.intro_background_check, 18, 0, 1, 2)
        settings_grid.addWidget(self._field_label("Âm nền teaser"), 18, 2)
        settings_grid.addWidget(self.intro_background_volume_spin, 18, 3)
        settings_grid.addWidget(self.background_music_enabled_check, 19, 0, 1, 2)
        settings_grid.addWidget(self._field_label("Âm lượng nhạc nền"), 19, 2)
        settings_grid.addWidget(self.background_music_volume_spin, 19, 3)
        settings_grid.addWidget(self._field_label("File nhạc nền"), 20, 0)
        background_music_row = QWidget()
        background_music_row_layout = QHBoxLayout(background_music_row)
        background_music_row_layout.setContentsMargins(0, 0, 0, 0)
        background_music_row_layout.setSpacing(8)
        background_music_row_layout.addWidget(self.background_music_path_edit, 1)
        background_music_row_layout.addWidget(self.background_music_choose_btn)
        settings_grid.addWidget(background_music_row, 20, 1, 1, 3)
        settings_grid.addWidget(self.output_mp4_check, 21, 0)
        settings_grid.addWidget(self.output_draft_check, 21, 1)
        settings_grid.addWidget(self._field_label("Thư mục output"), 22, 0)
        output_row = QWidget()
        output_row_layout = QHBoxLayout(output_row)
        output_row_layout.setContentsMargins(0, 0, 0, 0)
        output_row_layout.addWidget(self.output_dir_edit)
        output_row_layout.addWidget(output_dir_btn)
        settings_grid.addWidget(output_row, 22, 1, 1, 3)
        settings_grid.addWidget(self._field_label("Thư mục draft"), 23, 0)
        draft_row = QWidget()
        draft_row_layout = QHBoxLayout(draft_row)
        draft_row_layout.setContentsMargins(0, 0, 0, 0)
        draft_row_layout.addWidget(self.draft_dir_edit)
        draft_row_layout.addWidget(draft_dir_btn)
        settings_grid.addWidget(draft_row, 23, 1, 1, 3)
        settings_grid.addWidget(self._field_label("Vùng sub cũ X"), 24, 0)
        settings_grid.addWidget(self.region_x_spin, 24, 1)
        settings_grid.addWidget(self._field_label("Vùng sub cũ Y"), 24, 2)
        settings_grid.addWidget(self.region_y_spin, 24, 3)
        settings_grid.addWidget(self._field_label("Vùng sub cũ W"), 25, 0)
        settings_grid.addWidget(self.region_w_spin, 25, 1)
        settings_grid.addWidget(self._field_label("Vùng sub cũ H"), 25, 2)
        settings_grid.addWidget(self.region_h_spin, 25, 3)
        right_col.addWidget(settings_card)

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
        self.setStyleSheet(APP_STYLESHEET)

        container = QWidget()
        container.setObjectName("AppRoot")
        self.setCentralWidget(container)
        root = QVBoxLayout(container)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # --- Page navigation buttons ---
        nav_bar = QHBoxLayout()
        nav_bar.setSpacing(8)

        self._nav_edit_btn = self._make_button("Trang chính", "ghost")
        self._nav_edit_btn.setObjectName("NavActive")
        self._nav_preview_btn = self._make_button("Preview", "ghost")
        self._nav_batch_btn = self._make_button("Batch", "ghost")
        self._nav_edit_btn.clicked.connect(lambda: self._switch_page(0))
        self._nav_preview_btn.clicked.connect(lambda: self._switch_page(1))
        self._nav_batch_btn.clicked.connect(lambda: self._switch_page(2))

        self.mode_chip = self._make_chip("Chờ phân tích")
        self.subtitle_chip = self._make_chip("Vietsub: Bật")
        self.timing_chip = self._make_chip("Timing: Siêu khít")
        nav_bar.addWidget(self._nav_edit_btn)
        nav_bar.addWidget(self._nav_preview_btn)
        nav_bar.addWidget(self._nav_batch_btn)
        nav_bar.addSpacing(12)
        nav_bar.addWidget(self.mode_chip)
        nav_bar.addWidget(self.subtitle_chip)
        nav_bar.addWidget(self.timing_chip)
        nav_bar.addStretch(1)
        root.addLayout(nav_bar, 0)

        # --- Stacked pages ---
        self._page_stack = QStackedWidget()
        root.addWidget(self._page_stack, 1)

        # =========================================================
        # PAGE 0: EDIT - Left controls + Right video preview
        # =========================================================
        edit_page = QWidget()
        edit_layout = QHBoxLayout(edit_page)
        edit_layout.setContentsMargins(0, 0, 0, 0)
        edit_layout.setSpacing(10)

        # Left: scrollable controls
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        left_container = QWidget()
        left_container.setObjectName("AppRoot")
        left_scroll.setWidget(left_container)
        left_col = QVBoxLayout(left_container)
        left_col.setContentsMargins(0, 0, 0, 0)
        left_col.setSpacing(8)

        # Nguồn video
        input_card, input_layout = self._make_card(
            "Nguồn video",
            "Chọn video gốc rồi phân tích để bắt đầu.",
        )
        input_layout.setContentsMargins(12, 8, 12, 8)
        input_layout.setSpacing(5)
        self.input_path_edit = QLineEdit()
        self.input_path_edit.setReadOnly(True)
        self.input_path_edit.setPlaceholderText("Chưa chọn video nguồn")
        browse_btn = self._make_button("Chọn video", "ghost")
        browse_btn.clicked.connect(self.choose_video)
        analyze_btn = self._make_button("Phân tích", "primary")
        analyze_btn.clicked.connect(self.start_analysis)
        render_btn = self._make_button("Render", "success")
        render_btn.clicked.connect(self.start_render)
        cancel_btn = self._make_button("Dừng", "ghost")
        cancel_btn.clicked.connect(self.controller.cancel_active_job)
        self.analyze_btn = analyze_btn
        self.render_btn = render_btn
        self.cancel_btn = cancel_btn
        self.install_env_btn = self._make_button("Chuẩn bị model", "ghost")
        self.install_env_btn.clicked.connect(self.install_environment)
        action_row = QHBoxLayout()
        action_row.setSpacing(5)
        action_row.addWidget(browse_btn)
        action_row.addWidget(analyze_btn)
        action_row.addWidget(render_btn)
        action_row.addWidget(cancel_btn)
        action_row.addWidget(self.install_env_btn)
        action_row.addStretch(1)
        input_layout.addWidget(self.input_path_edit)
        input_layout.addLayout(action_row)

        # Tiến trình
        status_card, status_layout = self._make_card("Tiến trình & Nhật ký", "")
        status_layout.setContentsMargins(12, 8, 12, 8)
        status_layout.setSpacing(5)
        progress_row = QHBoxLayout()
        progress_row.setSpacing(6)
        progress_row.setContentsMargins(0, 0, 0, 0)
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
        self.log_box.setMinimumHeight(80)
        self.log_box.setMaximumHeight(120)
        status_layout.addWidget(self.log_box)

        # Ngôn ngữ & Xử lý
        lang_section = self._make_section("Ngôn ngữ & Xử lý", expanded=False)
        lang_grid = QGridLayout()
        lang_grid.setHorizontalSpacing(8)
        lang_grid.setVerticalSpacing(7)
        self.source_language_combo = self._make_combo(LANGUAGE_OPTIONS, self.on_basic_settings_changed)
        self.target_language_combo = self._make_combo(TARGET_LANGUAGE_OPTIONS, self.on_basic_settings_changed)
        self.speaker_detection_combo = self._make_combo(SPEAKER_DETECTION_OPTIONS, self.on_speaker_detection_changed)
        self.speaker_count_spin = SafeSpinBox()
        self.speaker_count_spin.setRange(1, 4)
        self.speaker_count_spin.valueChanged.connect(self.on_basic_settings_changed)
        self.timing_mode_combo = self._make_combo(TIMING_MODE_OPTIONS, self.on_basic_settings_changed)
        self.video_codec_combo = self._make_combo(VIDEO_CODEC_OPTIONS, self.on_basic_settings_changed)
        self.ui_theme_combo = self._make_combo(UI_THEME_OPTIONS, self.on_theme_preset_changed)
        self.cleanup_combo = self._make_combo(CLEANUP_OPTIONS, self.on_basic_settings_changed)

        lang_grid.addWidget(self._field_label("Ngôn ngữ nguồn"), 0, 0)
        lang_grid.addWidget(self.source_language_combo, 0, 1)
        lang_grid.addWidget(self._field_label("Ngôn ngữ sub"), 0, 2)
        lang_grid.addWidget(self.target_language_combo, 0, 3)
        lang_grid.addWidget(self._field_label("Nhận diện speaker"), 1, 0)
        lang_grid.addWidget(self.speaker_detection_combo, 1, 1)
        lang_grid.addWidget(self._field_label("Số speaker"), 1, 2)
        lang_grid.addWidget(self.speaker_count_spin, 1, 3)
        lang_grid.addWidget(self._field_label("Chế độ timing"), 2, 0)
        lang_grid.addWidget(self.timing_mode_combo, 2, 1)
        lang_grid.addWidget(self._field_label("Xử lý sub cũ"), 2, 2)
        lang_grid.addWidget(self.cleanup_combo, 2, 3)
        lang_grid.addWidget(self._field_label("Chế độ encode"), 3, 0)
        lang_grid.addWidget(self.video_codec_combo, 3, 1)
        lang_grid.addWidget(self._field_label("Preset giao diện"), 3, 2)
        lang_grid.addWidget(self.ui_theme_combo, 3, 3)
        lang_section.content_layout.addLayout(lang_grid)

        # Audio & Teaser
        audio_section = self._make_section("Audio & Teaser", expanded=False)
        audio_grid = QGridLayout()
        audio_grid.setHorizontalSpacing(8)
        audio_grid.setVerticalSpacing(7)
        self.intro_enabled_check = QCheckBox("Bật teaser")
        self.intro_enabled_check.stateChanged.connect(self.on_basic_settings_changed)
        self.intro_duration_spin = SafeDoubleSpinBox()
        self.intro_duration_spin.setRange(8.0, 16.0)
        self.intro_duration_spin.setSingleStep(0.5)
        self.intro_duration_spin.valueChanged.connect(self.on_basic_settings_changed)
        self.intro_voice_combo = self._make_combo(INTRO_TTS_OPTIONS, self.on_basic_settings_changed)
        self.intro_voice_combo.setEditable(True)
        if self.intro_voice_combo.lineEdit() is not None:
            self.intro_voice_combo.lineEdit().setPlaceholderText("Chọn giọng EdgeTTS/VieNeu")
            self.intro_voice_combo.lineEdit().returnPressed.connect(self.on_basic_settings_changed)
        self.intro_background_check = QCheckBox("Giữ âm nền teaser")
        self.intro_background_check.stateChanged.connect(self.on_basic_settings_changed)
        self.intro_background_volume_spin = SafeDoubleSpinBox()
        self.intro_background_volume_spin.setRange(0.0, 0.3)
        self.intro_background_volume_spin.setSingleStep(0.01)
        self.intro_background_volume_spin.valueChanged.connect(self.on_basic_settings_changed)
        self.keep_original_audio_check = QCheckBox("Giữ audio gốc nhỏ")
        self.keep_original_audio_check.stateChanged.connect(self.on_basic_settings_changed)
        self.background_music_enabled_check = QCheckBox("Nhạc nền toàn video")
        self.background_music_enabled_check.stateChanged.connect(self.on_basic_settings_changed)
        self.background_music_volume_spin = SafeDoubleSpinBox()
        self.background_music_volume_spin.setRange(0.0, 1.0)
        self.background_music_volume_spin.setSingleStep(0.05)
        self.background_music_volume_spin.setValue(0.12)
        self.background_music_volume_spin.valueChanged.connect(self.on_basic_settings_changed)
        self.background_music_path_edit = QLineEdit()
        self.background_music_path_edit.setReadOnly(True)
        self.background_music_path_edit.setPlaceholderText("Chưa chọn file nhạc nền")
        self.background_music_choose_btn = self._make_button("Chọn", "ghost")
        self.background_music_choose_btn.clicked.connect(self.choose_background_music_file)
        bg_music_row = QHBoxLayout()
        bg_music_row.setContentsMargins(0, 0, 0, 0)
        bg_music_row.setSpacing(5)
        bg_music_row.addWidget(self.background_music_path_edit, 1)
        bg_music_row.addWidget(self.background_music_choose_btn)

        audio_grid.addWidget(self.intro_enabled_check, 0, 0, 1, 2)
        audio_grid.addWidget(self.keep_original_audio_check, 0, 2, 1, 2)
        audio_grid.addWidget(self._field_label("Thời lượng teaser"), 1, 0)
        audio_grid.addWidget(self.intro_duration_spin, 1, 1)
        audio_grid.addWidget(self._field_label("Giọng teaser"), 1, 2)
        audio_grid.addWidget(self.intro_voice_combo, 1, 3)
        audio_grid.addWidget(self.intro_background_check, 2, 0, 1, 2)
        audio_grid.addWidget(self._field_label("Âm nền teaser"), 2, 2)
        audio_grid.addWidget(self.intro_background_volume_spin, 2, 3)
        audio_grid.addWidget(self.background_music_enabled_check, 3, 0, 1, 2)
        audio_grid.addWidget(self._field_label("Âm lượng nhạc nền"), 3, 2)
        audio_grid.addWidget(self.background_music_volume_spin, 3, 3)
        audio_grid.addWidget(self._field_label("File nhạc nền"), 4, 0)
        audio_grid.addLayout(bg_music_row, 4, 1, 1, 3)
        audio_section.content_layout.addLayout(audio_grid)

        # Output
        output_section = self._make_section("Output", expanded=False)
        output_grid = QGridLayout()
        output_grid.setHorizontalSpacing(8)
        output_grid.setVerticalSpacing(7)
        self.output_mp4_check = QCheckBox("Xuất MP4")
        self.output_mp4_check.stateChanged.connect(self.on_basic_settings_changed)
        self.output_draft_check = QCheckBox("Xuất Draft")
        self.output_draft_check.stateChanged.connect(self.on_basic_settings_changed)
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setPlaceholderText("Thư mục output")
        self.output_dir_edit.editingFinished.connect(self.on_basic_settings_changed)
        self.draft_dir_edit = QLineEdit()
        self.draft_dir_edit.setPlaceholderText("Thư mục draft")
        self.draft_dir_edit.editingFinished.connect(self.on_basic_settings_changed)
        output_dir_btn = self._make_button("Chọn", "ghost")
        output_dir_btn.clicked.connect(lambda: self.choose_directory(self.output_dir_edit))
        draft_dir_btn = self._make_button("Chọn", "ghost")
        draft_dir_btn.clicked.connect(lambda: self.choose_directory(self.draft_dir_edit))
        output_dir_row = QHBoxLayout()
        output_dir_row.setContentsMargins(0, 0, 0, 0)
        output_dir_row.addWidget(self.output_dir_edit)
        output_dir_row.addWidget(output_dir_btn)
        draft_dir_row = QHBoxLayout()
        draft_dir_row.setContentsMargins(0, 0, 0, 0)
        draft_dir_row.addWidget(self.draft_dir_edit)
        draft_dir_row.addWidget(draft_dir_btn)
        output_grid.addWidget(self.output_mp4_check, 0, 0)
        output_grid.addWidget(self.output_draft_check, 0, 1)
        output_grid.addWidget(self._field_label("Thư mục output"), 1, 0)
        output_grid.addLayout(output_dir_row, 1, 1, 1, 3)
        output_grid.addWidget(self._field_label("Thư mục draft"), 2, 0)
        output_grid.addLayout(draft_dir_row, 2, 1, 1, 3)
        output_section.content_layout.addLayout(output_grid)

        # Vùng sub cũ
        region_section = self._make_section("Vùng subtitle cũ cần che", expanded=False)
        region_grid = QGridLayout()
        region_grid.setHorizontalSpacing(8)
        region_grid.setVerticalSpacing(7)
        self.region_x_spin = self._make_region_spin()
        self.region_y_spin = self._make_region_spin()
        self.region_w_spin = self._make_region_spin()
        self.region_h_spin = self._make_region_spin()
        region_grid.addWidget(self._field_label("X"), 0, 0)
        region_grid.addWidget(self.region_x_spin, 0, 1)
        region_grid.addWidget(self._field_label("Y"), 0, 2)
        region_grid.addWidget(self.region_y_spin, 0, 3)
        region_grid.addWidget(self._field_label("W"), 1, 0)
        region_grid.addWidget(self.region_w_spin, 1, 1)
        region_grid.addWidget(self._field_label("H"), 1, 2)
        region_grid.addWidget(self.region_h_spin, 1, 3)
        region_section.content_layout.addLayout(region_grid)

        # Nhân vật - Gán giọng
        voice_card, voice_layout_root = self._make_card("Nhân vật - Gán giọng", "")
        voice_layout_root.setContentsMargins(12, 8, 12, 8)
        voice_layout_root.setSpacing(5)
        self.voice_overview_label = QLabel("Kết quả phân tích speaker sẽ xuất hiện ở đây sau khi phân tích.")
        self.voice_overview_label.setObjectName("SectionHint")
        self.voice_overview_label.setWordWrap(True)
        voice_layout_root.addWidget(self.voice_overview_label)
        self.voice_layout = QVBoxLayout()
        self.voice_layout.setSpacing(6)
        voice_layout_root.addLayout(self.voice_layout)

        # Subtitle timeline
        subtitle_card, subtitle_layout = self._make_card("Phụ đề theo thời gian", "")
        subtitle_layout.setContentsMargins(12, 8, 12, 8)
        subtitle_layout.setSpacing(5)
        subtitle_toolbar = QHBoxLayout()
        subtitle_toolbar.setSpacing(6)
        self.import_srt_btn = self._make_button("Nhập SRT", "ghost")
        self.import_srt_btn.clicked.connect(self.import_subtitle_srt)
        self.export_srt_btn = self._make_button("Xuất SRT", "ghost")
        self.export_srt_btn.clicked.connect(self.export_subtitle_srt)
        self.subtitle_editor_status = QLabel("Subtitle sẽ xuất hiện ở đây sau phân tích.")
        self.subtitle_editor_status.setObjectName("SectionHint")
        self.subtitle_editor_status.setWordWrap(True)
        subtitle_toolbar.addWidget(self.import_srt_btn)
        subtitle_toolbar.addWidget(self.export_srt_btn)
        subtitle_toolbar.addWidget(self.subtitle_editor_status)
        subtitle_toolbar.addStretch(1)
        subtitle_layout.addLayout(subtitle_toolbar)
        self.subtitle_table = QTableWidget(0, 3)
        self.subtitle_table.setHorizontalHeaderLabels(["Bắt đầu", "Kết thúc", "Nội dung subtitle"])
        self.subtitle_table.verticalHeader().setVisible(False)
        self.subtitle_table.setAlternatingRowColors(True)
        self.subtitle_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems)
        self.subtitle_table.setWordWrap(True)
        self.subtitle_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.subtitle_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.subtitle_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.subtitle_table.setMinimumHeight(100)
        self.subtitle_table.setMaximumHeight(140)
        self.subtitle_table.itemChanged.connect(self.on_subtitle_table_item_changed)
        subtitle_layout.addWidget(self.subtitle_table)

        left_col.addWidget(input_card)
        left_col.addWidget(status_card)
        left_col.addWidget(lang_section)
        left_col.addWidget(audio_section)
        left_col.addWidget(output_section)
        left_col.addWidget(region_section)
        left_col.addWidget(voice_card)
        left_col.addWidget(subtitle_card)
        left_col.addStretch(1)
        edit_layout.addWidget(left_scroll, 55)

        # Right: video preview (fixed, always visible on Edit page)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        # self.preview_style_card has been removed to give more space to the rendered video

        # Thành phẩm
        render_result_card, render_result_layout = self._make_card(
            "Thành phẩm sau render",
            "Video render nội bộ để xem lại, tải nhanh trước khi xuất file.",
        )
        render_result_layout.setContentsMargins(12, 8, 12, 8)
        render_result_layout.setSpacing(5)
        self.render_preview_status_label = QLabel("Chưa có video render để xem trước.")
        self.render_preview_status_label.setObjectName("SectionHint")
        self.render_preview_status_label.setWordWrap(True)
        render_result_layout.addWidget(self.render_preview_status_label)
        if self.render_video_widget is not None:
            self.render_video_widget.setMinimumHeight(280)
            self.render_video_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            render_result_layout.addWidget(self.render_video_widget, 1)
        else:
            self.render_video_unavailable_label = QLabel(
                "Qt Multimedia chưa sẵn sàng để phát video nội bộ.")
            self.render_video_unavailable_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.render_video_unavailable_label.setWordWrap(True)
            self.render_video_unavailable_label.setMinimumHeight(280)
            self.render_video_unavailable_label.setObjectName("SectionHint")
            render_result_layout.addWidget(self.render_video_unavailable_label, 1)

        # Player controls
        render_controls = QHBoxLayout()
        render_controls.setSpacing(5)
        self.restart_preview_btn = self._make_button("Từ đầu", "ghost")
        self.restart_preview_btn.clicked.connect(self.restart_render_preview)
        self.seek_back_preview_btn = self._make_button("-10s", "ghost")
        self.seek_back_preview_btn.clicked.connect(lambda: self.seek_render_preview_relative(-10000))
        self.pause_preview_btn = self._make_button("Phát", "ghost")
        self.pause_preview_btn.clicked.connect(self.pause_render_preview)
        self.seek_forward_preview_btn = self._make_button("+10s", "ghost")
        self.seek_forward_preview_btn.clicked.connect(lambda: self.seek_render_preview_relative(10000))
        self.stop_preview_btn = self._make_button("Dừng", "ghost")
        self.stop_preview_btn.clicked.connect(self.stop_render_preview)
        self.fullscreen_preview_btn = self._make_button("Toàn mh", "ghost")
        self.fullscreen_preview_btn.clicked.connect(self.toggle_render_preview_fullscreen)
        render_controls.addWidget(self.restart_preview_btn)
        render_controls.addWidget(self.seek_back_preview_btn)
        render_controls.addWidget(self.pause_preview_btn)
        render_controls.addWidget(self.seek_forward_preview_btn)
        render_controls.addWidget(self.stop_preview_btn)
        render_controls.addWidget(self.fullscreen_preview_btn)
        render_controls.addStretch(1)
        render_result_layout.addLayout(render_controls)

        seek_row = QHBoxLayout()
        seek_row.setSpacing(6)
        self.render_preview_position_label = QLabel("00:00")
        self.render_preview_position_label.setObjectName("FieldLabel")
        self.render_preview_seek_slider = SafeSlider(Qt.Orientation.Horizontal)
        self.render_preview_seek_slider.setRange(0, 0)
        self.render_preview_seek_slider.setEnabled(False)
        self.render_preview_seek_slider.sliderPressed.connect(self.on_render_preview_slider_pressed)
        self.render_preview_seek_slider.sliderMoved.connect(self.on_render_preview_slider_moved)
        self.render_preview_seek_slider.sliderReleased.connect(self.on_render_preview_slider_released)
        self.render_preview_duration_label = QLabel("00:00")
        self.render_preview_duration_label.setObjectName("FieldLabel")
        seek_row.addWidget(self.render_preview_position_label)
        seek_row.addWidget(self.render_preview_seek_slider, 1)
        seek_row.addWidget(self.render_preview_duration_label)
        render_result_layout.addLayout(seek_row)

        audio_row = QHBoxLayout()
        audio_row.setSpacing(5)
        self.mute_preview_btn = self._make_button("Tắt tiếng", "ghost")
        self.mute_preview_btn.clicked.connect(self.toggle_render_preview_mute)
        self.render_preview_volume_slider = SafeSlider(Qt.Orientation.Horizontal)
        self.render_preview_volume_slider.setRange(0, 100)
        self.render_preview_volume_slider.setValue(100)
        self.render_preview_volume_slider.valueChanged.connect(self.on_render_preview_volume_changed)
        self.render_preview_volume_value = QLabel("100%")
        self.render_preview_volume_value.setObjectName("FieldLabel")
        self.render_preview_speed_combo = self._make_combo(
            [("0.75", "0.75x"), ("1.0", "1x"), ("1.25", "1.25x"), ("1.5", "1.5x"), ("2.0", "2x")],
            self.on_render_preview_speed_changed)
        self._set_combo_value(self.render_preview_speed_combo, "1.0")
        audio_row.addWidget(self.mute_preview_btn)
        audio_row.addWidget(self._field_label("Âm"))
        audio_row.addWidget(self.render_preview_volume_slider, 1)
        audio_row.addWidget(self.render_preview_volume_value)
        audio_row.addSpacing(6)
        audio_row.addWidget(self._field_label("Tốc độ"))
        audio_row.addWidget(self.render_preview_speed_combo)
        render_result_layout.addLayout(audio_row)

        # Output sau render
        output_actions_card, output_actions_layout = self._make_card("Output sau render", "")
        output_actions_layout.setContentsMargins(12, 8, 12, 8)
        output_actions_layout.setSpacing(5)
        self.output_result_edit = QLineEdit()
        self.output_result_edit.setReadOnly(True)
        self.output_result_edit.setPlaceholderText("Chưa có video render nội bộ")
        self.output_folder_quick_edit = QLineEdit()
        self.output_folder_quick_edit.setReadOnly(False)
        self.output_folder_quick_edit.setPlaceholderText("Thư mục xuất file")
        self.output_folder_quick_edit.editingFinished.connect(self.on_output_directory_quick_changed)
        self.output_export_status_label = QLabel("Render xong sẽ có video nội bộ để xem và xuất file.")
        self.output_export_status_label.setObjectName("SectionHint")
        self.output_export_status_label.setWordWrap(True)
        self.preview_video_btn = self._make_button("Xem video", "primary")
        self.preview_video_btn.clicked.connect(self.preview_rendered_video)
        self.export_file_btn = self._make_button("Xuất file", "success")
        self.export_file_btn.clicked.connect(self.export_rendered_video_file)
        self.choose_output_folder_btn = self._make_button("Chọn thư mục xuất", "ghost")
        self.choose_output_folder_btn.clicked.connect(self.choose_output_directory)
        output_actions_layout.addWidget(self.output_result_edit)
        output_actions_layout.addWidget(self.output_export_status_label)
        output_actions_layout.addWidget(self.output_folder_quick_edit)
        output_quick_actions = QHBoxLayout()
        output_quick_actions.setSpacing(5)
        output_quick_actions.addWidget(self.preview_video_btn)
        output_quick_actions.addWidget(self.export_file_btn)
        output_quick_actions.addWidget(self.choose_output_folder_btn)
        output_quick_actions.addStretch(1)
        output_actions_layout.addLayout(output_quick_actions)

        right_layout.addWidget(render_result_card, 1)
        right_layout.addWidget(output_actions_card, 0)
        edit_layout.addWidget(right_panel, 45)

        self._page_stack.addWidget(edit_page)

        # =========================================================
        # PAGE 1: PREVIEW - Full canvas + all style settings
        # =========================================================
        preview_page = QWidget()
        preview_page_layout = QVBoxLayout(preview_page)
        preview_page_layout.setContentsMargins(0, 0, 0, 0)
        preview_page_layout.setSpacing(10)

        preview_top = QHBoxLayout()
        preview_top.setSpacing(10)
        preview_top.setStretchFactor(preview_top, 1)

        # Left of Preview page: Preview canvas (large)
        preview_canvas_area = QWidget()
        pca_layout = QVBoxLayout(preview_canvas_area)
        pca_layout.setContentsMargins(0, 0, 0, 0)
        pca_layout.setSpacing(8)
        pca_inner, pca_inner_layout = self._make_card(
            "Preview trực quan",
            "Khung hình + subtitle + watermark. Kéo subtitle để đổi vị trí.",
        )
        pca_inner_layout.setContentsMargins(8, 8, 8, 8)
        self._preview_canvas_full = PreviewCanvas()
        self._preview_canvas_full.setMinimumHeight(360)
        self._preview_canvas_full.subtitle_dragged.connect(self.on_preview_subtitle_dragged)
        self._preview_canvas_full.cleanup_region_changed.connect(self.on_cleanup_region_changed)
        self._preview_canvas_full.watermark_scale_changed.connect(self.on_watermark_scale_dragged)
        pca_inner_layout.addWidget(self._preview_canvas_full, 1)
        self.blur_slider = self._make_slider(2, 24, 10, self.on_blur_changed)
        self.blur_value = QLabel("10 px")
        self.blur_value.setFixedWidth(40)
        blur_row2 = QHBoxLayout()
        blur_row2.setSpacing(6)
        blur_row2.addWidget(self._field_label("Độ mờ phụ đề cũ"))
        blur_row2.addWidget(self.blur_slider, 1)
        blur_row2.addWidget(self.blur_value)
        pca_inner_layout.addLayout(blur_row2)
        pca_layout.addWidget(pca_inner, 1)
        self._preview_style_card_full = QFrame()
        self._preview_style_card_full.setObjectName("StatCard")
        pss_layout = QVBoxLayout(self._preview_style_card_full)
        pss_layout.setContentsMargins(10, 8, 10, 8)
        pss_layout.setSpacing(4)
        pst = QLabel("Xem trước kiểu subtitle")
        pst.setObjectName("StatTitle")
        pst2 = QLabel("Subtitle style sẽ cập nhật tại đây")
        pst2.setWordWrap(True)
        pst2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pst2.setMinimumHeight(40)
        pst3 = QLabel("Font, hộp, hiệu ứng hiện tại.")
        pst3.setObjectName("SectionHint")
        pst3.setWordWrap(True)
        pss_layout.addWidget(pst)
        pss_layout.addWidget(pst2)
        pss_layout.addWidget(pst3)
        pca_layout.addWidget(self._preview_style_card_full, 0)
        preview_top.addWidget(preview_canvas_area, 1)

        # Right of Preview page: all style settings
        preview_right_scroll = QScrollArea()
        preview_right_scroll.setWidgetResizable(True)
        preview_right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        preview_right_scroll.setFrameShape(QFrame.Shape.NoFrame)
        preview_right_container = QWidget()
        preview_right_container.setObjectName("AppRoot")
        preview_right_scroll.setWidget(preview_right_container)
        pr_col = QVBoxLayout(preview_right_container)
        pr_col.setContentsMargins(0, 0, 0, 0)
        pr_col.setSpacing(8)

        # Phông chữ
        font_section = self._make_section("Phông chữ", expanded=True)
        font_grid = QGridLayout()
        font_grid.setHorizontalSpacing(8)
        font_grid.setVerticalSpacing(7)
        self.font_group_combo = self._make_combo(FONT_GROUP_OPTIONS, self.on_font_group_changed)
        self.font_combo = self._make_combo(
            [(o["value"], o["label"]) for o in FONT_OPTIONS], self.on_font_changed)
        self.font_size_spin = SafeSpinBox()
        self.font_size_spin.setRange(10, 72)
        self.font_size_spin.setSuffix(" px")
        self.font_size_spin.setValue(14)
        self.font_size_spin.setToolTip("Cỡ chữ subtitle.")
        self.font_size_spin.valueChanged.connect(self.on_font_size_changed)
        self.font_size_slider = self._make_slider(10, 72, 14, self.on_font_size_changed)
        self.font_size_slider.valueChanged.connect(
            lambda v: self.font_size_spin.setValue(v) if not self.font_size_spin.hasFocus() else None)
        self.font_size_value = QLabel("14 px")
        self.font_size_value.setFixedWidth(40)
        self.stroke_width_spin = SafeSpinBox()
        self.stroke_width_spin.setRange(0, 6)
        self.stroke_width_spin.valueChanged.connect(self.on_basic_settings_changed)
        self.text_effect_combo = self._make_combo(TEXT_EFFECT_OPTIONS, self.on_basic_settings_changed)
        self.max_words_spin = SafeSpinBox()
        self.max_words_spin.setRange(2, 8)
        self.max_words_spin.valueChanged.connect(self.on_basic_settings_changed)
        self.font_color_btn = QPushButton("Màu chữ")
        self.font_color_btn.setObjectName("ColorButton")
        self.font_color_btn.clicked.connect(lambda: self.pick_color("fontColor"))
        self.stroke_color_btn = QPushButton("Màu viền")
        self.stroke_color_btn.setObjectName("ColorButton")
        self.stroke_color_btn.clicked.connect(lambda: self.pick_color("strokeColor"))
        font_grid.addWidget(self._field_label("Nhóm font"), 0, 0)
        font_grid.addWidget(self.font_group_combo, 0, 1, 1, 3)
        font_grid.addWidget(self._field_label("Font"), 1, 0)
        font_grid.addWidget(self.font_combo, 1, 1, 1, 3)
        font_grid.addWidget(self._field_label("Cỡ chữ"), 2, 0)
        font_grid.addWidget(self.font_size_spin, 2, 1)
        font_grid.addWidget(self.font_size_slider, 2, 2)
        font_grid.addWidget(self.font_size_value, 2, 3)
        font_grid.addWidget(self._field_label("Độ dày viền"), 3, 0)
        font_grid.addWidget(self.stroke_width_spin, 3, 1)
        font_grid.addWidget(self._field_label("Hiệu ứng CapCut"), 3, 2)
        font_grid.addWidget(self.text_effect_combo, 3, 3)
        font_grid.addWidget(self._field_label("Tối đa từ/dòng"), 4, 0)
        font_grid.addWidget(self.max_words_spin, 4, 1)
        font_grid.addWidget(self.font_color_btn, 4, 2, 1, 2)
        font_grid.addWidget(self._field_label("Palette màu chữ"), 5, 0)
        font_grid.addLayout(self._build_palette_row("fontColor", FONT_COLOR_SWATCHES), 5, 1, 1, 3)
        font_grid.addWidget(self._field_label("Palette màu viền"), 6, 0)
        font_grid.addLayout(self._build_palette_row("strokeColor", STROKE_COLOR_SWATCHES), 6, 1, 1, 3)
        font_grid.addWidget(self.stroke_color_btn, 7, 0, 1, 2)
        font_section.content_layout.addLayout(font_grid)

        # Box subtitle
        box_section = self._make_section("Hộp phụ đề", expanded=True)
        box_grid = QGridLayout()
        box_grid.setHorizontalSpacing(8)
        box_grid.setVerticalSpacing(7)
        self.subtitle_box_check = QCheckBox("Bật box subtitle")
        self.subtitle_box_check.stateChanged.connect(self.on_basic_settings_changed)
        self.box_style_combo = self._make_combo(BOX_STYLE_OPTIONS, self.on_box_style_changed)
        self.box_layout_combo = self._make_combo(BOX_LAYOUT_OPTIONS, self.on_box_style_detail_changed)
        self.box_radius_spin = SafeSpinBox()
        self.box_radius_spin.setRange(0, 40)
        self.box_radius_spin.setValue(16)
        self.box_radius_spin.setSuffix(" px")
        self.box_radius_spin.valueChanged.connect(self.on_box_style_detail_changed)
        self.box_border_width_spin = SafeSpinBox()
        self.box_border_width_spin.setRange(0, 8)
        self.box_border_width_spin.setValue(2)
        self.box_border_width_spin.valueChanged.connect(self.on_box_style_detail_changed)
        self.box_fill_opacity_spin = SafeDoubleSpinBox()
        self.box_fill_opacity_spin.setRange(0.15, 1.0)
        self.box_fill_opacity_spin.setDecimals(2)
        self.box_fill_opacity_spin.setSingleStep(0.05)
        self.box_fill_opacity_spin.setValue(0.86)
        self.box_fill_opacity_spin.valueChanged.connect(self.on_box_style_detail_changed)
        self.box_fill_color_btn = QPushButton("Nền box")
        self.box_fill_color_btn.setObjectName("ColorButton")
        self.box_fill_color_btn.clicked.connect(lambda: self.pick_color("boxFillColor"))
        self.box_border_color_btn = QPushButton("Viền box")
        self.box_border_color_btn.setObjectName("ColorButton")
        self.box_border_color_btn.clicked.connect(lambda: self.pick_color("boxBorderColor"))
        box_grid.addWidget(self.subtitle_box_check, 0, 0, 1, 4)
        box_grid.addWidget(self._field_label("Preset"), 1, 0)
        box_grid.addWidget(self.box_style_combo, 1, 1, 1, 3)
        box_grid.addWidget(self._field_label("Kiểu box"), 2, 0)
        box_grid.addWidget(self.box_layout_combo, 2, 1, 1, 3)
        box_grid.addWidget(self._field_label("Bo góc"), 3, 0)
        box_grid.addWidget(self.box_radius_spin, 3, 1)
        box_grid.addWidget(self._field_label("Độ dày viền"), 3, 2)
        box_grid.addWidget(self.box_border_width_spin, 3, 3)
        box_grid.addWidget(self._field_label("Độ đậm nền"), 4, 0)
        box_grid.addWidget(self.box_fill_opacity_spin, 4, 1, 1, 3)
        box_grid.addWidget(self.box_fill_color_btn, 5, 0, 1, 2)
        box_grid.addWidget(self.box_border_color_btn, 5, 2, 1, 2)
        box_grid.addWidget(self._field_label("Palette nền"), 6, 0)
        box_grid.addLayout(self._build_palette_row("boxFillColor", BOX_FILL_COLOR_SWATCHES), 6, 1, 1, 3)
        box_grid.addWidget(self._field_label("Palette viền"), 7, 0)
        box_grid.addLayout(self._build_palette_row("boxBorderColor", BOX_BORDER_COLOR_SWATCHES), 7, 1, 1, 3)
        box_section.content_layout.addLayout(box_grid)

        # Vị trí subtitle
        pos_section = self._make_section("Vị trí subtitle", expanded=True)
        pos_grid = QGridLayout()
        pos_grid.setHorizontalSpacing(8)
        pos_grid.setVerticalSpacing(7)
        self.subtitle_enabled_combo = self._make_combo(SUBTITLE_VISIBILITY_OPTIONS, self.on_basic_settings_changed)
        self.subtitle_position_combo = self._make_combo(SUBTITLE_POSITION_OPTIONS, self.on_basic_settings_changed)
        self.bottom_offset_slider = self._make_slider(12, 180, 54, self.on_bottom_offset_changed)
        self.bottom_offset_value = QLabel("54 px")
        self.bottom_offset_value.setFixedWidth(40)
        snap_row2 = QHBoxLayout()
        snap_row2.setSpacing(5)
        for label, preset in [("Trên", "top"), ("Giữa", "middle"), ("Dưới", "bottom")]:
            button = self._make_button(label, "ghost")
            button.clicked.connect(lambda _checked=False, p=preset: self.apply_caption_position(p))
            snap_row2.addWidget(button)
        snap_row2.addStretch(1)
        pos_grid.addWidget(self._field_label("Bật/Tắt vietsub"), 0, 0)
        pos_grid.addWidget(self.subtitle_enabled_combo, 0, 1, 1, 3)
        pos_grid.addWidget(self._field_label("Vị trí"), 1, 0)
        pos_grid.addWidget(self.subtitle_position_combo, 1, 1, 1, 3)
        pos_grid.addWidget(self._field_label("Độ cao dưới"), 2, 0)
        pos_grid.addWidget(self.bottom_offset_slider, 2, 1, 1, 2)
        pos_grid.addWidget(self.bottom_offset_value, 2, 3)
        pos_grid.addWidget(QLabel("Đặt nhanh:"), 3, 0)
        pos_grid.addLayout(snap_row2, 3, 1, 1, 3)
        pos_section.content_layout.addLayout(pos_grid)

        # Watermark
        wm_section = self._make_section("Watermark", expanded=False)
        wm_grid = QGridLayout()
        wm_grid.setHorizontalSpacing(8)
        wm_grid.setVerticalSpacing(7)
        self.watermark_enabled_check = QCheckBox("Bật watermark")
        self.watermark_enabled_check.stateChanged.connect(self.on_basic_settings_changed)
        self.watermark_path_edit = QLineEdit()
        self.watermark_path_edit.setReadOnly(True)
        self.watermark_path_edit.setPlaceholderText("Chưa chọn ảnh watermark")
        wm_btn = self._make_button("Chọn", "ghost")
        wm_btn.clicked.connect(self.choose_watermark_image)
        wm_path_row = QHBoxLayout()
        wm_path_row.setContentsMargins(0, 0, 0, 0)
        wm_path_row.setSpacing(5)
        wm_path_row.addWidget(self.watermark_path_edit, 1)
        wm_path_row.addWidget(wm_btn)
        self.watermark_position_combo = self._make_combo(WATERMARK_POSITION_OPTIONS, self.on_watermark_size_changed)
        self.watermark_scale_slider = self._make_slider(5, 50, 15, self.on_watermark_size_changed)
        self.watermark_scale_value = QLabel("15%")
        self.watermark_scale_value.setFixedWidth(40)
        wm_grid.addWidget(self.watermark_enabled_check, 0, 0, 1, 4)
        wm_grid.addWidget(self._field_label("Ảnh"), 1, 0)
        wm_grid.addLayout(wm_path_row, 1, 1, 1, 3)
        wm_grid.addWidget(self._field_label("Vị trí"), 2, 0)
        wm_grid.addWidget(self.watermark_position_combo, 2, 1, 1, 3)
        wm_grid.addWidget(self._field_label("Kích thước"), 3, 0)
        wm_grid.addWidget(self.watermark_scale_slider, 3, 1, 1, 2)
        wm_grid.addWidget(self.watermark_scale_value, 3, 3)
        wm_section.content_layout.addLayout(wm_grid)

        pr_col.addWidget(font_section)
        pr_col.addWidget(box_section)
        pr_col.addWidget(pos_section)
        pr_col.addWidget(wm_section)
        pr_col.addStretch(1)
        preview_top.addWidget(preview_right_scroll, 0)

        preview_page_layout.addLayout(preview_top, 1)
        self._page_stack.addWidget(preview_page)

        # =========================================================
        # PAGE 2: BATCH
        # =========================================================
        batch_page = QWidget()
        batch_page_layout = QVBoxLayout(batch_page)
        batch_page_layout.setContentsMargins(0, 0, 0, 0)
        batch_page_layout.setSpacing(10)

        batch_queue_card, batch_layout = self._make_card("Xử lý hàng loạt", "")
        batch_layout.setContentsMargins(12, 8, 12, 8)
        batch_layout.setSpacing(5)
        batch_toolbar = QHBoxLayout()
        batch_toolbar.setSpacing(5)
        self.batch_add_btn = self._make_button("Thêm video", "primary")
        self.batch_add_btn.clicked.connect(self.batch_add_videos)
        self.batch_remove_btn = self._make_button("Xóa chọn", "ghost")
        self.batch_remove_btn.clicked.connect(self.batch_remove_selected)
        self.batch_clear_btn = self._make_button("Xóa tất cả", "ghost")
        self.batch_clear_btn.clicked.connect(self.batch_clear_all)
        self.batch_start_btn = self._make_button("Bắt đầu batch", "success")
        self.batch_start_btn.clicked.connect(self.batch_start)
        self.batch_stop_btn = self._make_button("Tạm dừng", "ghost")
        self.batch_stop_btn.clicked.connect(self.batch_stop)
        self.batch_stop_btn.setEnabled(False)
        batch_toolbar.addWidget(self.batch_add_btn)
        batch_toolbar.addWidget(self.batch_remove_btn)
        batch_toolbar.addWidget(self.batch_clear_btn)
        batch_toolbar.addSpacing(10)
        batch_toolbar.addWidget(self.batch_start_btn)
        batch_toolbar.addWidget(self.batch_stop_btn)
        batch_toolbar.addStretch(1)
        batch_layout.addLayout(batch_toolbar)
        self.batch_table = QTableWidget(0, 4)
        self.batch_table.setHorizontalHeaderLabels(["#", "Tên video", "Trạng thái", "Output"])
        self.batch_table.verticalHeader().setVisible(False)
        self.batch_table.setAlternatingRowColors(True)
        self.batch_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.batch_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.batch_table.itemSelectionChanged.connect(self.batch_preview_selected)
        self.batch_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.batch_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.batch_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.batch_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.batch_table.setMinimumHeight(160)
        batch_layout.addWidget(self.batch_table)
        batch_output_row = QHBoxLayout()
        batch_output_row.setSpacing(5)
        batch_output_row.addWidget(self._field_label("Thư mục xuất batch"))
        self.batch_output_dir_edit = QLineEdit()
        self.batch_output_dir_edit.setPlaceholderText("Chọn thư mục xuất batch")
        self.batch_output_dir_edit.setReadOnly(True)
        batch_output_browse_btn = self._make_button("Chọn", "ghost")
        batch_output_browse_btn.clicked.connect(self.batch_choose_output_dir)
        batch_output_row.addWidget(self.batch_output_dir_edit, 1)
        batch_output_row.addWidget(batch_output_browse_btn)
        batch_layout.addLayout(batch_output_row)
        self.batch_progress_bar = QProgressBar()
        self.batch_progress_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.batch_progress_bar.setTextVisible(True)
        self.batch_progress_bar.setFormat("Tổng batch: %p%")
        batch_layout.addWidget(self.batch_progress_bar)
        self.batch_log_box = QPlainTextEdit()
        self.batch_log_box.setReadOnly(True)
        self.batch_log_box.setPlaceholderText("Log batch sẽ hiển thị tại đây.")
        self.batch_log_box.setMinimumHeight(120)
        batch_layout.addWidget(self.batch_log_box)
        batch_page_layout.addWidget(batch_queue_card, 1)

        self._page_stack.addWidget(batch_page)

        # Page navigation
        self.main_tabs = None
        self.preview_page = None
        self.render_page = None

        # Store animated cards
        self.animated_cards = []

    def _switch_page(self, index: int) -> None:
        """Switch between Edit/Preview/Batch pages and update nav button styles."""
        self._page_stack.setCurrentIndex(index)
        self.setStyleSheet(self.styleSheet())
        for btn, active in [(self._nav_edit_btn, index == 0),
                              (self._nav_preview_btn, index == 1),
                              (self._nav_batch_btn, index == 2)]:
            if btn:
                btn.setObjectName("NavActive" if active else "")
                btn.style().unpolish(btn)
                btn.style().polish(btn)
        if index == 1:
            self.refresh_preview()
