from __future__ import annotations

import os
from typing import Any

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QIcon

try:
    from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
except Exception:  # pragma: no cover
    QAudioOutput = None
    QMediaPlayer = None

try:
    from PyQt6.QtMultimediaWidgets import QVideoWidget
except Exception:  # pragma: no cover
    QVideoWidget = None

from PyQt6.QtWidgets import QMainWindow

from gui.controller import DubStudioJobController
from gui.utils import default_settings, safe_qta_icon

from .helpers import WindowHelpersMixin
from .layout import WindowLayoutMixin
from .refresh import WindowRefreshMixin
from .voice import WindowVoiceMixin
from .workflow import WindowWorkflowMixin
from .batch import WindowBatchMixin


class DubStudioWindow(
    WindowBatchMixin,
    WindowVoiceMixin,
    WindowRefreshMixin,
    WindowWorkflowMixin,
    WindowLayoutMixin,
    WindowHelpersMixin,
    QMainWindow,
):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("CapCut Mate · Dub Studio PyQt6")
        self._fit_window_to_screen()
        logo_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "assets",
            "logo.png",
        )
        if os.path.exists(logo_path):
            self.setWindowIcon(QIcon(logo_path))
        else:
            icon = safe_qta_icon("fa5s.closed-captioning", color="#f8fafc")
            if icon is not None:
                self.setWindowIcon(icon)

        self.controller = DubStudioJobController()
        self.controller.analysis_ready.connect(self.on_analysis_ready)
        self.controller.render_ready.connect(self.on_render_ready)
        self.controller.status_changed.connect(self.on_status_changed)
        self.controller.job_failed.connect(self.on_job_failed)

        # Batch signal hooks
        self.controller.analysis_ready.connect(self._batch_on_analysis_ready)
        self.controller.render_ready.connect(self._batch_on_render_ready)
        self.controller.status_changed.connect(self._batch_on_status_changed)
        self.controller.job_failed.connect(self._batch_on_job_failed)

        self._init_batch_state()
        self.job_id: str | None = None
        self.analysis: dict[str, Any] | None = None
        self.effective_analysis: dict[str, Any] | None = None
        self.job_status: dict[str, Any] | None = None
        self.last_output_path = ""
        self.last_exported_output_path = ""
        self.preview_media_analysis: dict[str, Any] | None = None
        self.settings = default_settings()
        self.voice_combo_map: dict[str, Any] = {}
        self.animated_cards: list[Any] = []
        self._intro_animation_group = None
        self.install_process = None
        self._install_stdout_buffer = ""
        self._install_stderr_buffer = ""
        self.voice_preview_process = None
        self._voice_preview_stdout = ""
        self._voice_preview_stderr = ""
        self._voice_preview_result_path = None
        self._voice_preview_active_speaker_id = ""
        self._voice_preview_audio_path = ""
        self.voice_test_button_map: dict[str, Any] = {}
        self.voice_status_label_map: dict[str, Any] = {}
        self.voice_audio_output = QAudioOutput(self) if QAudioOutput else None
        self.voice_player = QMediaPlayer(self) if QMediaPlayer else None
        self.render_preview_audio_output = QAudioOutput(self) if QAudioOutput else None
        self.render_preview_player = QMediaPlayer(self) if QMediaPlayer else None
        self.render_video_widget = QVideoWidget(self) if QVideoWidget else None
        self._render_preview_duration_ms = 0
        self._render_preview_scrubbing = False
        self._render_preview_muted = False
        self._render_preview_volume = 100
        self._render_preview_playback_rate = 1.0
        if self.voice_player is not None and self.voice_audio_output is not None:
            self.voice_audio_output.setVolume(0.92)
            self.voice_player.setAudioOutput(self.voice_audio_output)
            self.voice_player.errorOccurred.connect(self._handle_voice_player_error)

        self._build_ui()
        if (
            self.render_preview_player is not None
            and self.render_preview_audio_output is not None
        ):
            self.render_preview_audio_output.setVolume(1.0)
            self.render_preview_player.setAudioOutput(self.render_preview_audio_output)
            if self.render_video_widget is not None:
                self.render_preview_player.setVideoOutput(self.render_video_widget)
                try:
                    self.render_video_widget.fullScreenChanged.connect(
                        self._on_render_preview_fullscreen_changed
                    )
                except Exception:
                    pass
            self.render_preview_player.errorOccurred.connect(
                self._handle_render_preview_error
            )
            self.render_preview_player.positionChanged.connect(
                self._on_render_preview_position_changed
            )
            self.render_preview_player.durationChanged.connect(
                self._on_render_preview_duration_changed
            )
            self.render_preview_player.playbackStateChanged.connect(
                self._on_render_preview_playback_state_changed
            )
        self._configure_responsive_widgets()
        self.preview_canvas.subtitle_dragged.connect(self.on_preview_subtitle_dragged)
        self.preview_canvas.cleanup_region_changed.connect(self.on_cleanup_region_dragged)
        self._repair_widget_texts()
        self.refresh_all()
        QTimer.singleShot(90, self.play_intro_animation)
