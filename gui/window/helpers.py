from __future__ import annotations

import os
from typing import Any

from PyQt6.QtCore import QEasingCurve, QParallelAnimationGroup, QPropertyAnimation, QSize, Qt
from PyQt6.QtGui import QTextOption
from PyQt6.QtWidgets import (
    QApplication,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QSizePolicy,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from gui.config import QLabeledSlider, UI_THEME_PRESETS, VOICE_LABELS, qta
from gui.utils import repair_mojibake_text, safe_qta_icon


class WindowHelpersMixin:
    def _fit_window_to_screen(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            self.resize(1320, 840)
            self._preferred_window_width = 1320
            self._preferred_window_height = 840
            return
        available = screen.availableGeometry()
        width = min(max(1040, int(available.width() * 0.88)), 1540)
        height = min(max(720, int(available.height() * 0.88)), 980)
        self.resize(width, height)
        self._preferred_window_width = width
        self._preferred_window_height = height

    def _restore_compact_window_width(self) -> None:
        target_width = int(getattr(self, "_preferred_window_width", 0) or 0)
        if target_width <= 0:
            return
        if self.width() > target_width:
            self.resize(target_width, self.height())

    def _repair_widget_texts(self) -> None:
        self.setWindowTitle(repair_mojibake_text(self.windowTitle()))
        for widget in self.findChildren(QWidget):
            if hasattr(widget, "text"):
                try:
                    current = widget.text()
                    fixed = repair_mojibake_text(current)
                    if fixed != current:
                        widget.setText(fixed)
                except Exception:
                    pass
            if hasattr(widget, "placeholderText") and hasattr(
                widget, "setPlaceholderText"
            ):
                try:
                    current_placeholder = widget.placeholderText()
                    fixed_placeholder = repair_mojibake_text(current_placeholder)
                    if fixed_placeholder != current_placeholder:
                        widget.setPlaceholderText(fixed_placeholder)
                except Exception:
                    pass
            if isinstance(widget, QComboBox):
                for index in range(widget.count()):
                    current_item = widget.itemText(index)
                    fixed_item = repair_mojibake_text(current_item)
                    if fixed_item != current_item:
                        widget.setItemText(index, fixed_item)
        for tab_index in range(self.main_tabs.count()):
            current_tab = self.main_tabs.tabText(tab_index)
            fixed_tab = repair_mojibake_text(current_tab)
            if fixed_tab != current_tab:
                self.main_tabs.setTabText(tab_index, fixed_tab)

    def _make_slider(self, minimum: int, maximum: int, value: int, slot) -> QSlider:
        use_superqt = (
            os.environ.get("QT_QPA_PLATFORM") != "offscreen"
            and os.environ.get("CAPCUT_ENABLE_SUPERQT") == "1"
            and QLabeledSlider is not None
        )
        slider_class = QLabeledSlider if use_superqt else QSlider
        slider = slider_class(Qt.Orientation.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setValue(value)
        slider.valueChanged.connect(slot)
        slider.setProperty("enhanced", True)
        return slider

    def _make_combo(self, options: list[tuple[str, str]], slot) -> QComboBox:
        combo = QComboBox()
        for value, label in options:
            combo.addItem(label, value)
        combo.setMaxVisibleItems(12)
        combo.setCursor(Qt.CursorShape.PointingHandCursor)
        combo.setIconSize(QSize(14, 14))
        view = combo.view()
        view.setStyleSheet(
            """
            background: #0f1f35;
            color: #f8fafc;
            border: 1px solid rgba(96, 165, 250, 0.35);
            selection-background-color: #38bdf8;
            selection-color: #07111f;
            padding: 6px;
            """
        )
        combo.currentIndexChanged.connect(slot)
        return combo

    def _make_region_spin(self) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(0, 99999)
        spin.valueChanged.connect(self.on_basic_settings_changed)
        return spin

    @staticmethod
    def _set_combo_value(combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    @staticmethod
    def _resolve_voice_combo_value(combo: QComboBox) -> str:
        current_text = str(combo.currentText() or "").strip()
        index = combo.currentIndex()
        if index >= 0 and current_text == combo.itemText(index):
            data = combo.itemData(index)
            if data is not None and str(data).strip():
                return str(data).strip()
        return current_text

    @staticmethod
    def _format_voice_label(voice: str) -> str:
        value = str(voice or "").strip()
        if not value:
            return ""
        if value in VOICE_LABELS:
            return repair_mojibake_text(VOICE_LABELS[value])
        if value.startswith("vieneu:"):
            return repair_mojibake_text(f"VieNeu-TTS • {value}")
        if value.startswith("edge:") or value.endswith("Neural"):
            return repair_mojibake_text(f"EdgeTTS • {value}")
        return repair_mojibake_text(value)

    def _make_card(self, title: str, hint: str) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("SurfaceCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)
        title_label = QLabel(title)
        title_label.setObjectName("SectionTitle")
        hint_label = QLabel(hint)
        hint_label.setObjectName("SectionHint")
        hint_label.setWordWrap(True)
        layout.addWidget(title_label)
        layout.addWidget(hint_label)
        return card, layout

    def _make_stat_card(self, title: str) -> tuple[QFrame, QLabel]:
        card = QFrame()
        card.setObjectName("StatCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)
        title_label = QLabel(title)
        title_label.setObjectName("StatTitle")
        value_label = QLabel("--")
        value_label.setObjectName("StatValue")
        value_label.setWordWrap(True)
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        return card, value_label

    def _field_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("FieldLabel")
        return label

    def _make_button(self, text: str, variant: str = "ghost") -> QPushButton:
        button = QPushButton(text)
        button.setProperty("variant", variant)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setIconSize(QSize(15, 15))
        button.setMinimumHeight(30)
        if qta:
            icon_map = {
                "Chọn video": "fa5s.folder-open",
                "Phân tích video": "fa5s.search",
                "Render bản lồng tiếng": "fa5s.magic",
                "Dừng tác vụ": "fa5s.stop-circle",
                "Mở output": "fa5s.external-link-alt",
                "Xem video": "fa5s.play-circle",
                "Xuất file": "fa5s.file-export",
                "Từ đầu": "fa5s.undo",
                "Lùi 10s": "fa5s.backward",
                "Tạm dừng": "fa5s.pause-circle",
                "Phát": "fa5s.play-circle",
                "Tiến 10s": "fa5s.forward",
                "Dừng phát": "fa5s.stop-circle",
                "Toàn màn hình": "fa5s.expand",
                "Thu nhỏ": "fa5s.compress",
                "Tắt tiếng": "fa5s.volume-mute",
                "Bật tiếng": "fa5s.volume-up",
                "Import SRT": "fa5s.file-import",
                "Export SRT": "fa5s.file-export",
                "Chọn": "fa5s.folder",
            }
            icon_name = icon_map.get(text)
            if icon_name:
                icon = safe_qta_icon(icon_name, color="white")
                if icon is not None:
                    button.setIcon(icon)
        if button.icon().isNull():
            fallback_icon_map = {
                "Chọn video": QStyle.StandardPixmap.SP_DialogOpenButton,
                "Phân tích video": QStyle.StandardPixmap.SP_FileDialogDetailedView,
                "Render bản lồng tiếng": QStyle.StandardPixmap.SP_MediaPlay,
                "Dừng tác vụ": QStyle.StandardPixmap.SP_BrowserStop,
                "Mở output": QStyle.StandardPixmap.SP_DirOpenIcon,
                "Xem video": QStyle.StandardPixmap.SP_MediaPlay,
                "Xuất file": QStyle.StandardPixmap.SP_DialogSaveButton,
                "Từ đầu": QStyle.StandardPixmap.SP_MediaSkipBackward,
                "Lùi 10s": QStyle.StandardPixmap.SP_MediaSeekBackward,
                "Tạm dừng": QStyle.StandardPixmap.SP_MediaPause,
                "Phát": QStyle.StandardPixmap.SP_MediaPlay,
                "Tiến 10s": QStyle.StandardPixmap.SP_MediaSeekForward,
                "Dừng phát": QStyle.StandardPixmap.SP_MediaStop,
                "Toàn màn hình": QStyle.StandardPixmap.SP_TitleBarMaxButton,
                "Thu nhỏ": QStyle.StandardPixmap.SP_TitleBarNormalButton,
                "Tắt tiếng": QStyle.StandardPixmap.SP_MediaVolumeMuted,
                "Bật tiếng": QStyle.StandardPixmap.SP_MediaVolume,
                "Import SRT": QStyle.StandardPixmap.SP_DialogOpenButton,
                "Export SRT": QStyle.StandardPixmap.SP_DialogSaveButton,
                "Chọn": QStyle.StandardPixmap.SP_DialogOpenButton,
            }
            icon_type = fallback_icon_map.get(text)
            if icon_type is not None:
                button.setIcon(self.style().standardIcon(icon_type))
        button.style().unpolish(button)
        button.style().polish(button)
        return button

    def _make_chip(self, text: str) -> QLabel:
        chip = QLabel(text)
        chip.setObjectName("MetricChip")
        chip.setWordWrap(False)
        chip.setMinimumWidth(0)
        chip.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        return chip

    def _set_chip_display_text(
        self,
        chip: QLabel | None,
        text: str,
        *,
        max_width: int | None = None,
        fixed_width: int | None = None,
    ) -> None:
        if chip is None:
            return
        clean_text = repair_mojibake_text(text)
        chip.setToolTip(clean_text)
        chip.setWordWrap(False)
        chip.setMinimumWidth(0)
        if fixed_width is not None:
            chip.setFixedWidth(fixed_width)
            chip.setText(clean_text)
            return
        if max_width is not None:
            chip.setMaximumWidth(max_width)
            display = chip.fontMetrics().elidedText(
                clean_text,
                Qt.TextElideMode.ElideRight,
                max(max_width - 28, 36),
            )
            chip.setText(display)
            return
        chip.setText(clean_text)

    def _configure_readonly_text_box(self, widget: QPlainTextEdit | None) -> None:
        if widget is None:
            return
        widget.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        widget.setWordWrapMode(QTextOption.WrapMode.WrapAnywhere)
        widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        widget.setMinimumWidth(0)

    def _configure_shrinkable_widget(
        self,
        widget: QWidget | None,
        *,
        vertical_policy: QSizePolicy.Policy = QSizePolicy.Policy.Preferred,
    ) -> None:
        if widget is None:
            return
        widget.setMinimumWidth(0)
        widget.setSizePolicy(QSizePolicy.Policy.Ignored, vertical_policy)

    def _configure_responsive_widgets(self) -> None:
        for attr_name in ("warning_box", "timeline_box", "log_box"):
            self._configure_readonly_text_box(getattr(self, attr_name, None))
        for widget in self.findChildren(QLineEdit):
            self._configure_shrinkable_widget(widget)
        for widget in self.findChildren(QComboBox):
            self._configure_shrinkable_widget(widget)
        for widget in self.findChildren(QSpinBox):
            self._configure_shrinkable_widget(widget)
        for widget in self.findChildren(QDoubleSpinBox):
            self._configure_shrinkable_widget(widget)
        self._configure_shrinkable_widget(getattr(self, "main_tabs", None))
        if hasattr(self, "main_tabs"):
            for tab_index in range(self.main_tabs.count()):
                self._configure_shrinkable_widget(self.main_tabs.widget(tab_index))
        for attr_name in (
            "phase_label",
            "step_label",
            "mode_chip",
            "subtitle_chip",
            "timing_chip",
            "sidebar_status_chip",
        ):
            widget = getattr(self, attr_name, None)
            if widget is None:
                continue
            widget.setMinimumWidth(0)
            widget.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        progress_label = getattr(self, "progress_label", None)
        if progress_label is not None:
            progress_label.setWordWrap(False)
            progress_label.setMinimumWidth(72)
            progress_label.setMaximumWidth(72)
            progress_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        for attr_name in ("voice_overview_label",):
            widget = getattr(self, attr_name, None)
            if widget is None:
                continue
            widget.setMinimumWidth(0)
            widget.setWordWrap(True)
            widget.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

    def _update_color_button_styles(self) -> None:
        font_color = self.settings["subtitlePreset"].get("fontColor", "#ffd200")
        stroke_color = self.settings["subtitlePreset"].get("strokeColor", "#000000")
        self.font_color_btn.setStyleSheet(
            f"background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {font_color}, stop:1 #ffffff); color: #0f172a; border: none;"
        )
        self.stroke_color_btn.setStyleSheet(
            f"background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {stroke_color}, stop:1 #64748b); color: white; border: none;"
        )

    def _make_swatch_button(self, key: str, color: str) -> QPushButton:
        button = QPushButton()
        button.setFixedSize(28, 28)
        button.setToolTip(color)
        button.clicked.connect(lambda: self.apply_palette_color(key, color))
        button.setStyleSheet(
            f"background:{color}; border: 2px solid rgba(255,255,255,0.18); border-radius: 14px;"
        )
        return button

    def _build_palette_row(self, key: str, colors: list[str]) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(0, 0, 0, 0)
        for color in colors:
            layout.addWidget(self._make_swatch_button(key, color))
        layout.addStretch(1)
        return layout

    def apply_palette_color(self, key: str, color: str) -> None:
        self.settings["subtitlePreset"][key] = color
        self._update_color_button_styles()
        self.refresh_all()

    def apply_ui_theme_preset(self, preset_key: str) -> None:
        preset = UI_THEME_PRESETS.get(preset_key)
        if not preset:
            return
        font_option = find_font_option(preset["fontFamily"])
        self.settings["uiThemePreset"] = preset_key
        self.settings["subtitlePreset"].update(
            {
                "fontFamily": font_option["value"],
                "fontFamilyLabel": font_option["label"],
                "fontFamilyName": font_option["fontFamilyName"],
                "cssFontFamily": font_option["cssFontFamily"],
                "assFontName": font_option["assFontName"],
                "draftFontKey": font_option["draftFontKey"],
                "fontColor": preset["fontColor"],
                "strokeColor": preset["strokeColor"],
                "strokeWidth": preset["strokeWidth"],
                "positionPreset": preset["positionPreset"],
            }
        )
        self.settings["sourceSubtitleCleanupMode"] = preset["cleanupMode"]
        self.sync_widgets_from_settings()
        self.refresh_all()

    def on_theme_preset_changed(self) -> None:
        preset_key = str(self.ui_theme_combo.currentData() or "cinema")
        self.apply_ui_theme_preset(preset_key)

    def play_intro_animation(self) -> None:
        self._intro_animation_group = QParallelAnimationGroup(self)
        for index, widget in enumerate(self.animated_cards):
            effect = QGraphicsOpacityEffect(widget)
            effect.setOpacity(0.0)
            widget.setGraphicsEffect(effect)
            animation = QPropertyAnimation(effect, b"opacity", self)
            animation.setStartValue(0.0)
            animation.setEndValue(1.0)
            animation.setDuration(260 + index * 70)
            animation.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._intro_animation_group.addAnimation(animation)
        self._intro_animation_group.start()



