from __future__ import annotations

import copy
import hashlib
import importlib
import shutil
import time
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QProcess, QProcessEnvironment, Qt, QUrl
from PyQt6.QtGui import QColor, QDesktopServices
try:
    from PyQt6.QtMultimedia import QMediaPlayer
except Exception:  # pragma: no cover
    QMediaPlayer = None

from PyQt6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QFileDialog,
    QInputDialog,
    QLineEdit,
    QMessageBox,
    QTableWidgetItem,
)

from gui.config import BOX_STYLE_PRESETS, DEFAULT_OUTPUT_DIR, FONT_OPTIONS, get_sticker_by_id, PIPELINE_PYTHON, ROOT, VOICE_LABELS, VOICE_OPTIONS, is_frozen

from gui.utils import (
    default_settings,
    ensure_dir,
    find_font_option,
    normalize_preview_text,
    preferred_default_voice,
    repair_mojibake_text,
    resolve_intro_voice_preset,
)
from tools.dub_studio.media_utils import extract_thumbnail, get_video_meta
from tools.dub_studio.render_utils import default_subtitle_region
from tools.dub_studio.subtitle_utils import compose_srt_from_timeline, parse_srt_to_timeline


class WindowWorkflowMixin:
    def _build_quick_preview_analysis(self, video_path: Path) -> dict[str, Any] | None:
        resolved_path = video_path.expanduser().resolve()
        if not resolved_path.exists() or not resolved_path.is_file():
            return None
        cache_dir = ensure_dir(ROOT / "temp" / "dub_studio" / "preview_cache")
        stat = resolved_path.stat()
        cache_key = hashlib.sha1(
            f"{resolved_path}|{stat.st_size}|{stat.st_mtime_ns}".encode("utf-8")
        ).hexdigest()[:16]
        thumbnail_path = cache_dir / f"{cache_key}.jpg"
        video_meta = get_video_meta(resolved_path)
        if not thumbnail_path.exists() or thumbnail_path.stat().st_size <= 0:
            extract_thumbnail(resolved_path, thumbnail_path)
        subtitle_region = default_subtitle_region(video_meta)
        return {
            "inputPath": str(resolved_path),
            "thumbnailPath": str(thumbnail_path) if thumbnail_path.exists() else "",
            "videoMeta": video_meta,
            "subtitleRegion": subtitle_region,
            "warnings": [],
            "subtitleTimeline": [],
            "segments": [],
        }

    def show_source_video_preview(
        self,
        video_path: str | Path,
        *,
        switch_to_preview_tab: bool = False,
        refresh_all: bool = False,
    ) -> None:
        source_path = Path(video_path)
        try:
            preview_analysis = self._build_quick_preview_analysis(source_path)
        except Exception:
            preview_analysis = None
        self.preview_media_analysis = preview_analysis

        video_preview = getattr(self, "_video_preview_widget", None)
        if video_preview is not None:
            video_preview.load_video(source_path)

        if switch_to_preview_tab and hasattr(self, "_page_stack"):
            self._switch_page(1)
        elif switch_to_preview_tab and hasattr(self, "main_tabs") and hasattr(
            self, "preview_page"
        ):
            _tabs = getattr(self, "main_tabs", None)
            if _tabs is not None:
                _tabs.setCurrentWidget(self.preview_page)
        if refresh_all:
            self.refresh_all()
        else:
            self.refresh_preview()

    @staticmethod
    def _format_render_preview_time(ms: int) -> str:
        total_seconds = max(0, int(ms // 1000))
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    def _set_render_preview_time_labels(
        self, position_ms: int, duration_ms: int | None = None
    ) -> None:
        total_ms = (
            self._render_preview_duration_ms
            if duration_ms is None
            else max(0, int(duration_ms))
        )
        if hasattr(self, "render_preview_position_label"):
            self.render_preview_position_label.setText(
                self._format_render_preview_time(max(0, int(position_ms)))
            )
        if hasattr(self, "render_preview_duration_label"):
            self.render_preview_duration_label.setText(
                self._format_render_preview_time(total_ms)
            )

    def _reset_render_preview_timeline(self, *, clear_duration: bool = True) -> None:
        if clear_duration:
            self._render_preview_duration_ms = 0
        self._render_preview_scrubbing = False
        max_duration = self._render_preview_duration_ms if not clear_duration else 0
        if hasattr(self, "render_preview_seek_slider"):
            self.render_preview_seek_slider.blockSignals(True)
            self.render_preview_seek_slider.setRange(0, max_duration)
            self.render_preview_seek_slider.setValue(0)
            self.render_preview_seek_slider.blockSignals(False)
        self._set_render_preview_time_labels(0, self._render_preview_duration_ms)

    def _update_render_preview_button_labels(self) -> None:
        is_playing = False
        if self.render_preview_player is not None:
            playback_state = getattr(self.render_preview_player, "playbackState", None)
            if callable(playback_state):
                is_playing = (
                    playback_state() == QMediaPlayer.PlaybackState.PlayingState
                )
        if hasattr(self, "pause_preview_btn"):
            self.pause_preview_btn.setText("Tạm dừng" if is_playing else "Phát")
        if hasattr(self, "mute_preview_btn"):
            self.mute_preview_btn.setText(
                "Bật tiếng" if self._render_preview_muted else "Tắt tiếng"
            )
        if hasattr(self, "fullscreen_preview_btn") and self.render_video_widget is not None:
            is_fullscreen = bool(
                getattr(self.render_video_widget, "isFullScreen", lambda: False)()
            )
            self.fullscreen_preview_btn.setText(
                "Thu nhỏ" if is_fullscreen else "Phóng To"
            )

    def _apply_render_preview_audio_state(self) -> None:
        safe_volume = max(0, min(int(self._render_preview_volume), 100))
        if hasattr(self, "render_preview_volume_slider"):
            self.render_preview_volume_slider.blockSignals(True)
            self.render_preview_volume_slider.setValue(safe_volume)
            self.render_preview_volume_slider.blockSignals(False)
        if hasattr(self, "render_preview_volume_value"):
            label = "Tắt tiếng" if self._render_preview_muted else f"{safe_volume}%"
            self.render_preview_volume_value.setText(label)
        if self.render_preview_audio_output is not None:
            effective_volume = 0 if self._render_preview_muted else safe_volume
            self.render_preview_audio_output.setVolume(effective_volume / 100.0)
        self._update_render_preview_button_labels()

    def _apply_render_preview_playback_rate(self) -> None:
        safe_rate = max(0.25, min(float(self._render_preview_playback_rate), 3.0))
        self._render_preview_playback_rate = safe_rate
        if hasattr(self, "render_preview_speed_combo"):
            self._set_combo_value(self.render_preview_speed_combo, str(safe_rate))
        if self.render_preview_player is not None:
            self.render_preview_player.setPlaybackRate(safe_rate)

    def _current_render_player_position(self) -> int:
        if self.render_preview_player is None:
            return 0
        position_getter = getattr(self.render_preview_player, "position", None)
        if callable(position_getter):
            try:
                return max(0, int(position_getter()))
            except Exception:
                return 0
        return 0

    def choose_video(self) -> None:
        if self.controller.has_running_job():
            QMessageBox.warning(
                self,
                "Đang xử lý",
                "Hãy đợi tác vụ hiện tại hoàn tất hoặc dừng nó trước khi đổi video.",
            )
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Chọn video nguồn", "", "Video (*.mp4 *.mov *.mkv *.avi *.m4v *.webm)"
        )
        if not path:
            return
        self.input_path_edit.setText(path)
        self.job_id = None
        self.analysis = None
        self.effective_analysis = None
        self.preview_media_analysis = None
        self.job_status = None
        self.last_output_path = ""
        self.last_exported_output_path = ""
        self.stop_render_preview(clear_source=True)
        self.show_source_video_preview(
            path,
            switch_to_preview_tab=True,
            refresh_all=True,
        )

    @staticmethod
    def _parse_video_urls(raw_text: str) -> list[str]:
        urls: list[str] = []
        seen: set[str] = set()
        for line in str(raw_text or "").replace(",", "\n").splitlines():
            value = line.strip()
            if not value or value.startswith("#"):
                continue
            if not value.lower().startswith(("http://", "https://")):
                raise RuntimeError(f"Link không hợp lệ, cần bắt đầu bằng http:// hoặc https://\n\n{value}")
            if value not in seen:
                urls.append(value)
                seen.add(value)
        return urls

    def choose_video_from_url(self) -> None:
        if self.controller.has_running_job():
            QMessageBox.warning(
                self,
                "Đang xử lý",
                "Hãy đợi tác vụ hiện tại hoàn tất hoặc dừng nó trước khi tải video mới.",
            )
            return
        text, ok = QInputDialog.getMultiLineText(
            self,
            "Tải video từ link",
            "Dán một link video. App sẽ dùng yt-dlp để tải về rồi tự chọn làm video nguồn:",
            "",
        )
        if not ok:
            return
        try:
            urls = self._parse_video_urls(text)
            if len(urls) != 1:
                raise RuntimeError("Màn phân tích chỉ nhận 1 link mỗi lần. Với nhiều link, dùng tab Batch > Thêm link.")
            self._start_video_downloads(urls, mode="single")
        except Exception as exc:
            QMessageBox.warning(self, "Link chưa hợp lệ", repair_mojibake_text(str(exc)))

    def _ytdlp_cookies_path(self) -> Path:
        return ROOT / "config" / "yt_dlp_cookies.txt"

    def choose_ytdlp_cookies_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn file cookies.txt cho yt-dlp",
            "",
            "Cookies (*.txt);;All Files (*)",
        )
        if not path:
            return
        try:
            source = Path(path).expanduser()
            if not source.exists() or not source.is_file():
                raise RuntimeError(f"Không tìm thấy file cookies:\n{source}")
            text_head = source.read_text(encoding="utf-8", errors="ignore")[:2048]
            if "# Netscape HTTP Cookie File" not in text_head and "\tdouyin.com\t" not in text_head.lower():
                answer = QMessageBox.question(
                    self,
                    "File cookies có thể không đúng định dạng",
                    repair_mojibake_text(
                        "File này không giống định dạng Netscape cookies.txt mà yt-dlp thường dùng.\n\n"
                        "Bạn vẫn muốn lưu và thử dùng file này?"
                    ),
                )
                if answer != QMessageBox.StandardButton.Yes:
                    return
            target = self._ytdlp_cookies_path()
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            QMessageBox.information(
                self,
                "Đã lưu cookies",
                repair_mojibake_text(
                    f"Đã lưu cookies cho yt-dlp:\n{target}\n\n"
                    "Khi tải link Douyin, app sẽ ưu tiên dùng file cookies này trước."
                ),
            )
        except Exception as exc:
            QMessageBox.critical(self, "Không lưu được cookies", repair_mojibake_text(str(exc)))

    @staticmethod
    def _installed_ytdlp_version() -> str:
        try:
            from importlib import metadata

            return metadata.version("yt-dlp")
        except Exception:
            return "chưa cài"

    def update_ytdlp(self) -> None:
        if is_frozen:
            QMessageBox.information(
                self,
                "Cập nhật yt-dlp",
                repair_mojibake_text(
                    "Bạn đang sử dụng phiên bản ứng dụng đóng gói độc lập (.exe).\n\n"
                    "Trong phiên bản đóng gói độc lập, thư viện yt-dlp đã được nén sẵn bên trong và không thể cập nhật trực tiếp qua pip được.\n\n"
                    "Để cập nhật yt-dlp:\n"
                    "1. Hãy cập nhật yt-dlp trên môi trường Python gốc của bạn (chạy lệnh 'pip install -U yt-dlp' trong cmd/terminal của máy).\n"
                    "2. Chạy lại file đóng gói 'python build_exe.py' để biên dịch ra bản .exe mới chứa yt-dlp mới nhất."
                ),
            )
            return

        if getattr(self, "video_download_process", None) is not None:
            QMessageBox.information(
                self,
                "yt-dlp đang tải video",
                "Hãy đợi lượt tải hiện tại hoàn tất rồi cập nhật yt-dlp.",
            )
            return
        if getattr(self, "ytdlp_update_process", None) is not None:
            QMessageBox.information(self, "Đang cập nhật", "yt-dlp đang được cập nhật, vui lòng đợi.")
            return
        before_version = self._installed_ytdlp_version()
        if not QMessageBox.question(
            self,
            "Cập nhật yt-dlp",
            repair_mojibake_text(
                f"Phiên bản hiện tại: {before_version}\n\n"
                "App sẽ chạy lệnh trong đúng môi trường Python hiện tại:\n"
                "python -m pip install -U yt-dlp\n\n"
                "Bạn muốn tiếp tục?"
            ),
        ) == QMessageBox.StandardButton.Yes:
            return

        self._ytdlp_update_stdout = ""
        self._ytdlp_update_stderr = ""
        process = QProcess(self)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONIOENCODING", "utf-8")
        process.setProcessEnvironment(env)
        process.setProgram(str(PIPELINE_PYTHON))
        process.setArguments(["-m", "pip", "install", "-U", "yt-dlp"])
        process.setWorkingDirectory(str(ROOT))
        process.readyReadStandardOutput.connect(self._drain_ytdlp_update_output)
        process.readyReadStandardError.connect(self._drain_ytdlp_update_output)
        process.finished.connect(
            lambda code, status, before=before_version: self._handle_ytdlp_update_finished(code, status, before)
        )
        self.ytdlp_update_process = process
        self._set_video_download_controls_enabled(False)
        if hasattr(self, "phase_label"):
            self.phase_label.setText("Trạng thái: đang cập nhật yt-dlp")
        if hasattr(self, "batch_log_box"):
            self._update_batch_log(f"▶ Đang cập nhật yt-dlp từ phiên bản {before_version}...")
        process.start()

    def _drain_ytdlp_update_output(self) -> None:
        process = getattr(self, "ytdlp_update_process", None)
        if process is None:
            return
        from gui.utils import decode_process_bytes

        stdout = decode_process_bytes(bytes(process.readAllStandardOutput()))
        stderr = decode_process_bytes(bytes(process.readAllStandardError()))
        self._ytdlp_update_stdout += stdout
        self._ytdlp_update_stderr += stderr
        merged = (stdout + "\n" + stderr).strip()
        if merged and hasattr(self, "batch_log_box"):
            last_line = merged.splitlines()[-1].strip()
            if last_line:
                self._update_batch_log(f"  {last_line[:220]}")

    def _handle_ytdlp_update_finished(self, code: int, _status, before_version: str) -> None:
        self._drain_ytdlp_update_output()
        process = getattr(self, "ytdlp_update_process", None)
        if process is not None:
            try:
                process.readyReadStandardOutput.disconnect(self._drain_ytdlp_update_output)
                process.readyReadStandardError.disconnect(self._drain_ytdlp_update_output)
            except Exception:
                pass
        self.ytdlp_update_process = None
        self._set_video_download_controls_enabled(True)
        if hasattr(self, "refresh_all"):
            try:
                self.refresh_all()
            except Exception:
                pass

        after_version = self._installed_ytdlp_version()
        output = (self._ytdlp_update_stderr.strip() or self._ytdlp_update_stdout.strip()).strip()
        if code == 0:
            message = (
                f"yt-dlp đã sẵn sàng.\n\n"
                f"Trước: {before_version}\n"
                f"Sau: {after_version}"
            )
            if before_version == after_version:
                message += "\n\nKhông có phiên bản mới hơn trong nguồn pip hiện tại."

            # Đồng thời cập nhật cả trình tải douyin
            try:
                import subprocess
                from pathlib import Path
                # Try pulling specific file from origin main via git
                p1 = subprocess.run(["git", "fetch", "origin"], cwd=str(ROOT), capture_output=True, text=True)
                p2 = subprocess.run(["git", "checkout", "origin/main", "--", "tools/douyin_api_downloader.py"], cwd=str(ROOT), capture_output=True, text=True)
                if p2.returncode == 0:
                    message += "\n\n✓ Đã cập nhật xong Douyin Downloader qua Git."
                else:
                    raise RuntimeError(p2.stderr or p1.stderr or "Lỗi Git checkout")
            except Exception as e:
                # Fallback to direct HTTP request with user agent
                try:
                    import urllib.request
                    req = urllib.request.Request(
                        "https://raw.githubusercontent.com/siver2001/CapCut-Mate---Dub-Studio/main/tools/douyin_api_downloader.py",
                        headers={"User-Agent": "Mozilla/5.0"}
                    )
                    with urllib.request.urlopen(req) as response:
                        content = response.read()
                    douyin_file = Path(ROOT) / "tools" / "douyin_api_downloader.py"
                    douyin_file.write_bytes(content)
                    message += "\n\n✓ Đã cập nhật xong Douyin Downloader qua HTTP."
                except Exception as e2:
                    message += f"\n\n⚠ Không thể tải Douyin Downloader mới nhất: {e2}"

            if hasattr(self, "batch_log_box"):
                self._update_batch_log(f"✓ Cập nhật yt-dlp xong: {before_version} → {after_version}")
            QMessageBox.information(self, "Cập nhật trình tải video hoàn tất", repair_mojibake_text(message))
            return

        detail = output or "pip không trả về thông tin lỗi."
        if hasattr(self, "batch_log_box"):
            self._update_batch_log(f"✗ Cập nhật yt-dlp thất bại: {detail[-500:]}")
        QMessageBox.critical(
            self,
            "Cập nhật yt-dlp thất bại",
            repair_mojibake_text(
                "Không cập nhật được yt-dlp.\n\n"
                f"Phiên bản hiện tại: {before_version}\n\n"
                f"Chi tiết pip:\n{detail[-1800:]}"
            ),
        )

    def _set_video_download_controls_enabled(self, enabled: bool) -> None:
        for attr in (
            "download_video_btn",
            "ytdlp_cookies_btn",
            "update_ytdlp_btn",
            "analyze_btn",
            "render_btn",
            "batch_add_btn",
            "batch_add_links_btn",
            "batch_start_btn",
        ):
            button = getattr(self, attr, None)
            if button is not None:
                button.setEnabled(enabled)
        if hasattr(self, "cancel_btn"):
            self.cancel_btn.setEnabled(enabled)
        if hasattr(self, "batch_stop_btn"):
            self.batch_stop_btn.setEnabled(enabled and bool(getattr(self, "_batch_running", False)))

    def _start_video_downloads(self, urls: list[str], *, mode: str) -> None:
        if getattr(self, "video_download_process", None) is not None:
            QMessageBox.information(self, "Đang tải video", "yt-dlp đang tải video, vui lòng đợi xong rồi thử lại.")
            return
        if not urls:
            raise RuntimeError("Chưa có link video để tải.")
        if not self._has_dependency("yt_dlp"):
            raise RuntimeError(
                "Thiếu thư viện `yt-dlp` nên chưa thể tải video từ link.\n\n"
                "Cài bằng lệnh:\n"
                "python -m pip install yt-dlp\n\n"
                "Sau khi cài xong, mở lại app rồi thử lại."
            )
        self._video_download_queue = list(urls)
        self._video_download_mode = mode
        self._video_download_results = []
        self._video_download_errors = []
        self._video_download_stdout = ""
        self._video_download_stderr = ""
        self._set_video_download_controls_enabled(False)
        if mode == "batch" and hasattr(self, "batch_log_box"):
            self._update_batch_log(f"▶ Bắt đầu tải {len(urls)} link bằng yt-dlp...")
        elif hasattr(self, "phase_label"):
            self.phase_label.setText("Trạng thái: đang tải video")
        self._start_next_video_download()

    def _start_next_video_download(self) -> None:
        if not self._video_download_queue:
            self._finish_video_downloads()
            return
        url = self._video_download_queue.pop(0)
        self._video_download_current_url = url
        self._video_download_stdout = ""
        self._video_download_stderr = ""
        self._video_download_attempt_logs = []
        download_root = ensure_dir(ROOT / "temp" / "dub_studio" / "downloads")
        digest = hashlib.sha1(f"{url}|{time.time_ns()}".encode("utf-8")).hexdigest()[:12]
        run_dir = ensure_dir(download_root / digest)
        self._video_download_current_dir = run_dir
        self._video_download_current_attempts = self._build_video_download_attempts(url, run_dir)
        self._video_download_current_attempt_index = 0
        self._start_video_download_attempt()

    @staticmethod
    def _is_douyin_url(url: str) -> bool:
        lowered = str(url or "").lower()
        return "douyin.com/" in lowered or "iesdouyin.com/" in lowered

    def _common_ytdlp_download_args(self, url: str, run_dir: Path) -> list[str]:
        base = ["yt_dlp"] if is_frozen else ["-m", "yt_dlp"]
        return base + [
            "--proxy=",
            "--newline",
            "--no-playlist",
            "-f",
            "bv*+ba/b",
            "--merge-output-format",
            "mp4",
            "--remux-video",
            "mp4",
            "-P",
            str(run_dir),
            "-o",
            "%(title).200B [%(id)s].%(ext)s",
            url,
        ]


    def _build_video_download_attempts(self, url: str, run_dir: Path) -> list[dict[str, object]]:
        base_args = self._common_ytdlp_download_args(url, run_dir)
        if not self._is_douyin_url(url):
            return [{"label": "yt-dlp", "args": base_args}]

        douyin_headers = [
            "--add-headers",
            "Referer:https://www.douyin.com/",
            "--add-headers",
            "User-Agent:Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        ]
        attempts: list[dict[str, object]] = [
            {"label": "Douyin headers", "args": base_args[:-1] + douyin_headers + [url]},
            {
                "label": "Douyin_TikTok_Download_API",
                "args": (
                    ["douyin", "--url", url, "--output-dir", str(run_dir), "--timeout", "20"]
                    if is_frozen
                    else ["-u", str(ROOT / "tools" / "douyin_api_downloader.py"), "--url", url, "--output-dir", str(run_dir), "--timeout", "20"]
                ),
            },

        ]
        cookies_file = self._ytdlp_cookies_path()
        if cookies_file.exists():
            attempts.append(
                {
                    "label": "Douyin cookies.txt",
                    "args": base_args[:-1] + douyin_headers + ["--cookies", str(cookies_file)] + [url],
                }
            )
        for browser in ("edge", "chrome", "firefox"):
            attempts.append(
                {
                    "label": f"Douyin cookies từ {browser}",
                    "args": base_args[:-1] + douyin_headers + ["--cookies-from-browser", browser] + [url],
                }
            )
        return attempts

    def _start_video_download_attempt(self) -> None:
        attempts = list(getattr(self, "_video_download_current_attempts", []) or [])
        attempt_index = int(getattr(self, "_video_download_current_attempt_index", 0) or 0)
        if not attempts or attempt_index >= len(attempts):
            self._video_download_errors.append(self._video_download_error_detail())
            self._start_next_video_download()
            return
        attempt = attempts[attempt_index]
        attempt_label = str(attempt.get("label") or f"attempt {attempt_index + 1}")
        attempt_args = list(attempt.get("args") or [])

        process = QProcess(self)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONIOENCODING", "utf-8")
        ytdlp_temp_dir = ensure_dir(ROOT / "temp" / "dub_studio" / "yt_dlp_tmp")
        env.insert("TMP", str(ytdlp_temp_dir))
        env.insert("TEMP", str(ytdlp_temp_dir))
        for proxy_key in (
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "ALL_PROXY",
            "http_proxy",
            "https_proxy",
            "all_proxy",
        ):
            env.remove(proxy_key)
        process.setProcessEnvironment(env)
        process.setProgram(str(PIPELINE_PYTHON))
        process.setArguments([str(arg) for arg in attempt_args])
        process.setWorkingDirectory(str(ROOT))
        process.readyReadStandardOutput.connect(self._drain_video_download_output)
        process.readyReadStandardError.connect(self._drain_video_download_output)
        process.finished.connect(self._handle_video_download_finished)
        self.video_download_process = process
        if self._video_download_mode == "batch" and hasattr(self, "batch_log_box"):
            total_done = len(self._video_download_results) + len(self._video_download_errors) + 1
            self._update_batch_log(f"[yt-dlp {total_done}] Đang tải ({attempt_label}): {self._video_download_current_url}")
        elif hasattr(self, "input_path_edit"):
            self.input_path_edit.setText(f"Đang tải bằng yt-dlp ({attempt_label}): {self._video_download_current_url}")
        process.start()

    def _drain_video_download_output(self) -> None:
        process = getattr(self, "video_download_process", None)
        if process is None:
            return
        from gui.utils import decode_process_bytes

        stdout = decode_process_bytes(bytes(process.readAllStandardOutput()))
        stderr = decode_process_bytes(bytes(process.readAllStandardError()))
        self._video_download_stdout += stdout
        self._video_download_stderr += stderr
        merged = (stdout + "\n" + stderr).strip()
        if merged and self._video_download_mode == "batch" and hasattr(self, "batch_log_box"):
            last_line = merged.splitlines()[-1].strip()
            if last_line:
                self._update_batch_log(f"  {last_line[:220]}")

    def _find_downloaded_video_file(self, directory: Path) -> Path | None:
        video_exts = {".mp4", ".mov", ".mkv", ".avi", ".m4v", ".webm"}
        candidates = [
            path
            for path in directory.rglob("*")
            if path.is_file()
            and path.suffix.lower() in video_exts
            and ".part" not in path.name.lower()
            and path.stat().st_size > 0
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda path: (path.stat().st_size, path.stat().st_mtime_ns))

    def _video_download_error_detail(self) -> str:
        output = (self._video_download_stderr.strip() or self._video_download_stdout.strip()).strip()
        if not output:
            output = "yt-dlp không trả về thông tin lỗi."
        attempt_logs = "\n\n".join(getattr(self, "_video_download_attempt_logs", []) or [])
        if attempt_logs:
            output = f"{attempt_logs}\n\nLỗi cuối:\n{output}"
        return (
            f"Không tải được video từ link:\n{self._video_download_current_url}\n\n"
            f"Chi tiết yt-dlp:\n{output[-1800:]}"
        )

    def _remember_video_download_attempt_failure(self, label: str) -> None:
        output = (self._video_download_stderr.strip() or self._video_download_stdout.strip()).strip()
        if not output:
            output = "Không có log chi tiết."
        compact = output[-700:]
        self._video_download_attempt_logs.append(f"[{label}] thất bại:\n{compact}")

    def _handle_video_download_finished(self, code: int, _status) -> None:
        self._drain_video_download_output()
        process = getattr(self, "video_download_process", None)
        if process is not None:
            try:
                process.readyReadStandardOutput.disconnect(self._drain_video_download_output)
                process.readyReadStandardError.disconnect(self._drain_video_download_output)
                process.finished.disconnect(self._handle_video_download_finished)
            except Exception:
                pass
        self.video_download_process = None

        run_dir = Path(self._video_download_current_dir) if self._video_download_current_dir else None
        downloaded = self._find_downloaded_video_file(run_dir) if run_dir else None
        if code == 0 and downloaded is not None:
            self._video_download_results.append(str(downloaded))
            if self._video_download_mode == "batch" and hasattr(self, "batch_log_box"):
                self._update_batch_log(f"  ✓ Tải xong: {downloaded.name}")
                if hasattr(self, "_add_downloaded_video_to_batch"):
                    self._add_downloaded_video_to_batch(str(downloaded))
            else:
                self._use_downloaded_video_as_source(downloaded)
        else:
            attempts = list(getattr(self, "_video_download_current_attempts", []) or [])
            attempt_index = int(getattr(self, "_video_download_current_attempt_index", 0) or 0)
            if self._is_douyin_url(self._video_download_current_url) and attempt_index + 1 < len(attempts):
                failed_label = str((attempts[attempt_index] or {}).get("label") or f"attempt {attempt_index + 1}")
                self._remember_video_download_attempt_failure(failed_label)
                self._video_download_current_attempt_index = attempt_index + 1
                next_label = str((attempts[attempt_index + 1] or {}).get("label") or f"attempt {attempt_index + 2}")
                if self._video_download_mode == "batch" and hasattr(self, "batch_log_box"):
                    self._update_batch_log(f"  ⚠ Douyin chưa tải được bằng {failed_label}; thử lại bằng {next_label}...")
                elif hasattr(self, "input_path_edit"):
                    self.input_path_edit.setText(f"Douyin cần cookie, đang thử lại bằng {next_label}...")
                self._video_download_stdout = ""
                self._video_download_stderr = ""
                self._start_video_download_attempt()
                return
            if self._is_douyin_url(self._video_download_current_url) and attempts:
                failed_label = str((attempts[attempt_index] or {}).get("label") or f"attempt {attempt_index + 1}")
                self._remember_video_download_attempt_failure(failed_label)
            detail = self._video_download_error_detail()
            if self._is_douyin_url(self._video_download_current_url):
                detail += (
                    "\n\nGợi ý cho Douyin:\n"
                    "- Mở Douyin trong Edge hoặc Chrome trên máy này trước, chấp nhận xác minh/cookie nếu có.\n"
                    "- Không nhất thiết phải đăng nhập, nhưng Douyin thường cần cookie mới.\n"
                    "- Nếu trình duyệt bị Windows khóa cookie database, hãy export cookies Douyin ra file config/yt_dlp_cookies.txt.\n"
                    "- Có thể tự host Evil0ctal/Douyin_TikTok_Download_API rồi set biến DOUYIN_TIKTOK_API_BASE_URL=http://127.0.0.1/api để app dùng fallback local.\n"
                    "- Nếu vẫn lỗi, hãy cập nhật yt-dlp rồi thử lại link."
                )
            self._video_download_errors.append(detail)
            if self._video_download_mode == "batch" and hasattr(self, "batch_log_box"):
                self._update_batch_log(f"  ✗ Lỗi tải link: {repair_mojibake_text(detail)}")
            else:
                if hasattr(self, "input_path_edit"):
                    self.input_path_edit.clear()
                QMessageBox.critical(self, "Tải video thất bại", repair_mojibake_text(detail))

        self._start_next_video_download()

    def _use_downloaded_video_as_source(self, video_path: Path) -> None:
        self.input_path_edit.setText(str(video_path))
        self.job_id = None
        self.analysis = None
        self.effective_analysis = None
        self.preview_media_analysis = None
        self.job_status = None
        self.last_output_path = ""
        self.last_exported_output_path = ""
        self.stop_render_preview(clear_source=True)
        self.show_source_video_preview(
            video_path,
            switch_to_preview_tab=True,
            refresh_all=True,
        )

    def _finish_video_downloads(self) -> None:
        self._set_video_download_controls_enabled(True)
        if hasattr(self, "refresh_all"):
            try:
                self.refresh_all()
            except Exception:
                pass
        if self._video_download_mode == "batch":
            if hasattr(self, "_refresh_batch_ui"):
                self._refresh_batch_ui()
            success_count = len(self._video_download_results)
            error_count = len(self._video_download_errors)
            if hasattr(self, "batch_log_box"):
                self._update_batch_log(f"yt-dlp hoàn tất: {success_count} tải thành công, {error_count} lỗi.")
            if success_count and hasattr(self, "batch_table"):
                self.batch_table.selectRow(max(0, len(self._batch_queue) - success_count))
            message = f"Đã tải thành công {success_count} video."
            if error_count:
                message += "\n\nMột số link bị lỗi. Chi tiết đã được ghi trong log batch; kiểm tra lại link, quyền xem, cookies hoặc mạng."
            QMessageBox.information(self, "Tải batch hoàn tất", repair_mojibake_text(message))
        elif self._video_download_results:
            QMessageBox.information(
                self,
                "Tải video hoàn tất",
                repair_mojibake_text(f"Đã tải và chọn video nguồn:\n{Path(self._video_download_results[-1]).name}"),
            )
        self._video_download_mode = ""
        self._video_download_current_url = ""
        self._video_download_current_dir = None

    def choose_directory(self, target_edit: QLineEdit) -> None:
        selected = QFileDialog.getExistingDirectory(
            self, "Chọn thư mục", target_edit.text() or str(ROOT)
        )
        if selected:
            if target_edit is self.output_dir_edit:
                self.sync_output_directory_inputs(selected)
            else:
                target_edit.setText(selected)
            self.on_basic_settings_changed()

    def choose_output_directory(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            "Chọn thư mục xuất video sau render",
            self.output_folder_quick_edit.text().strip()
            or self.output_dir_edit.text().strip()
            or str(ROOT),
        )
        if selected:
            self.sync_output_directory_inputs(selected)
            self.on_basic_settings_changed()

    def on_output_directory_quick_changed(self) -> None:
        selected = self.output_folder_quick_edit.text().strip()
        self.sync_output_directory_inputs(selected)
        self.on_basic_settings_changed()

    def sync_output_directory_inputs(self, selected: str) -> None:
        value = selected.strip()
        if hasattr(self, "output_folder_quick_edit"):
            self.output_folder_quick_edit.blockSignals(True)
        if hasattr(self, "output_dir_edit"):
            self.output_dir_edit.blockSignals(True)
        if hasattr(self, "batch_output_dir_edit"):
            self.batch_output_dir_edit.blockSignals(True)
        
        if hasattr(self, "output_folder_quick_edit"):
            self.output_folder_quick_edit.setText(value)
        if hasattr(self, "output_dir_edit"):
            self.output_dir_edit.setText(value)
        
        if hasattr(self, "batch_output_dir_edit"):
            self.batch_output_dir_edit.setText(value)
        if hasattr(self, "_batch_output_dir"):
            self._batch_output_dir = value

        if hasattr(self, "output_folder_quick_edit"):
            self.output_folder_quick_edit.blockSignals(False)
        if hasattr(self, "output_dir_edit"):
            self.output_dir_edit.blockSignals(False)
        if hasattr(self, "batch_output_dir_edit"):
            self.batch_output_dir_edit.blockSignals(False)

    def choose_watermark_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Chọn ảnh watermark", "", "Image (*.png *.jpg *.jpeg)"
        )
        if not path:
            return
        self.watermark_path_edit.setText(path)
        wm = self.settings.setdefault("watermark", {})
        wm["path"] = path
        
        # Auto-detect background removal needs
        try:
            from PIL import Image
            with Image.open(path) as img:
                has_alpha = "A" in img.mode or (img.mode == "P" and "transparency" in img.info)
                if not has_alpha:
                    # Auto-enable background removal and sample color
                    wm["removeBg"] = True
                    tl = img.getpixel((0, 0))
                    if isinstance(tl, tuple):
                        wm["bgColor"] = "#{:02x}{:02x}{:02x}".format(tl[0], tl[1], tl[2])
                    else:
                        wm["bgColor"] = "#{:02x}{:02x}{:02x}".format(tl, tl, tl)
                    if hasattr(self, "watermark_remove_bg_check"):
                        self.watermark_remove_bg_check.setChecked(True)
                else:
                    # If it already has alpha, we can usually turn off removeBg unless user wants it
                    # But for "automatic", we'll just leave it as is or turn it off
                    # Let's keep it OFF for true transparent PNGs
                    wm["removeBg"] = False
                    if hasattr(self, "watermark_remove_bg_check"):
                        self.watermark_remove_bg_check.setChecked(False)
        except Exception:
            pass

        self.on_basic_settings_changed()

    def _ensure_directory(self, raw_path: str, fallback: Path) -> Path:
        candidate = Path(raw_path.strip()) if raw_path.strip() else fallback
        ensure_dir(candidate)
        return candidate

    def _resolve_output_directory(self, raw_path: str | None = None) -> Path:
        raw_value = str(raw_path or "").strip()
        if not raw_value:
            raise RuntimeError("Vui lòng chọn 'Thư mục output' trước khi render.")
        output_dir = Path(raw_value).expanduser()
        if output_dir.exists() and not output_dir.is_dir():
            raise RuntimeError(
                f"Đường dẫn output đang trỏ tới một file, không phải thư mục:\n{output_dir}"
            )
        ensure_dir(output_dir)
        return output_dir.resolve()

    def _current_render_preview_path(self) -> str:
        render_result = (
            ((self.job_status or {}).get("renderResult") or {})
            if self.job_status
            else {}
        )
        return str(
            render_result.get("previewVideoPath")
            or render_result.get("outputVideoPath")
            or self.last_output_path
            or ""
        ).strip()

    @staticmethod
    def _has_dependency(module_name: str) -> bool:
        return importlib.util.find_spec(module_name) is not None

    def _validate_analysis_input(self) -> Path:
        input_path = Path(self.input_path_edit.text().strip())
        if not str(input_path):
            raise RuntimeError("Hãy chọn video trước khi phân tích.")
        if not input_path.exists():
            raise RuntimeError(f"Không tìm thấy file video: {input_path}")
        if not input_path.is_file():
            raise RuntimeError("Đường dẫn video không hợp lệ.")
        return input_path

    def _prepare_render_options(self) -> dict[str, Any]:
        if not self._has_dependency("edge_tts"):
            raise RuntimeError(
                "Thiếu thư viện `edge_tts`, nên app chưa thể tạo giọng đọc.\n\n"
                "Cài bằng lệnh:\n"
                "python -m pip install edge-tts"
            )
        options = self.current_render_options()
        output_targets = options.get("outputTargets") or {}
        if not any(bool(value) for value in output_targets.values()):
            raise RuntimeError("Hãy bật ít nhất một định dạng output trước khi render.")
        output_dir = self._resolve_output_directory(options.get("outputDirectory"))
        options["outputDirectory"] = str(output_dir)
        self.settings["outputDirectory"] = str(output_dir)
        self.sync_output_directory_inputs(str(output_dir))
        if output_targets.get("draft"):
            draft_root = self._ensure_directory(
                str(options.get("draftRoot") or ""), output_dir / "draft"
            )
            options["draftRoot"] = str(draft_root)
            self.settings["draftRoot"] = str(draft_root)
            self.draft_dir_edit.setText(str(draft_root))
        elif not str(options.get("draftRoot") or "").strip():
            options["draftRoot"] = str(output_dir / "draft")
        return options

    def start_analysis(self) -> None:
        try:
            input_path = self._validate_analysis_input()
            self.job_id = self.controller.analyze_video(
                str(input_path),
                {"targetLanguage": self.settings.get("targetLanguage", "vi")},
            )
            self.job_status = self.controller.get_job_status(self.job_id)
            self.refresh_all()
        except Exception as exc:
            QMessageBox.critical(self, "Phân tích thất bại", str(exc))

    def start_render(self) -> None:
        if not self.job_id or not self.analysis:
            QMessageBox.warning(
                self, "Thiếu dữ liệu phân tích", "Cần phân tích video trước khi render."
            )
            return
        try:
            self.read_settings_from_widgets()
            self._push_analysis_overrides()
            self.stop_render_preview(clear_source=True)
            self.last_exported_output_path = ""
            self.controller.render_video(self.job_id, self._prepare_render_options())
        except Exception as exc:
            QMessageBox.critical(self, "Render thất bại", str(exc))

    def preview_rendered_video(self) -> None:
        preview_path = self._current_render_preview_path()
        if not preview_path:
            QMessageBox.information(
                self,
                "Chưa có video render",
                "Hãy render video trước khi xem preview.",
            )
            return
        if self.render_preview_player is None or self.render_video_widget is None:
            QMessageBox.warning(
                self,
                "Không thể preview",
                "Qt Multimedia Video chưa sẵn sàng nên app chưa thể phát video trực tiếp trong giao diện.",
            )
            return
        video_path = Path(preview_path)
        if not video_path.exists():
            QMessageBox.information(
                self,
                "Không tìm thấy video",
                f"Không thấy file video render tại:\n{video_path}",
            )
            return
        self.last_output_path = str(video_path)
        if hasattr(self, "main_tabs") and hasattr(self, "render_page"):
            _tabs = getattr(self, "main_tabs", None)
            if _tabs is not None:
                _tabs.setCurrentWidget(self.render_page)
        self.render_preview_player.stop()
        self.render_preview_player.setSource(QUrl.fromLocalFile(str(video_path)))
        self._apply_render_preview_audio_state()
        self._apply_render_preview_playback_rate()
        self.render_preview_player.play()
        self._update_render_preview_button_labels()
        if hasattr(self, "render_preview_status_label"):
            self.render_preview_status_label.setText(
                repair_mojibake_text(
                    f"Đang phát video render nội bộ: {video_path.name}"
                )
            )

    def restart_render_preview(self) -> None:
        if self.render_preview_player is None:
            return
        self.render_preview_player.setPosition(0)
        self.render_preview_player.play()
        self._update_render_preview_button_labels()
        self._set_render_preview_time_labels(0, self._render_preview_duration_ms)

    def seek_render_preview_relative(self, delta_ms: int) -> None:
        if self.render_preview_player is None:
            return
        target_position = max(
            0,
            min(
                self._current_render_player_position() + int(delta_ms),
                self._render_preview_duration_ms,
            ),
        )
        self.render_preview_player.setPosition(target_position)
        self._set_render_preview_time_labels(
            target_position, self._render_preview_duration_ms
        )

    def pause_render_preview(self) -> None:
        if self.render_preview_player is None:
            return
        playback_state = getattr(self.render_preview_player, "playbackState", None)
        if callable(playback_state):
            current_state = playback_state()
            if current_state == QMediaPlayer.PlaybackState.StoppedState:
                self.preview_rendered_video()
                return
            if current_state == QMediaPlayer.PlaybackState.PausedState:
                self.render_preview_player.play()
                self._update_render_preview_button_labels()
                preview_path = (
                    Path(self._current_render_preview_path()).name or "video render"
                )
                if hasattr(self, "render_preview_status_label"):
                    self.render_preview_status_label.setText(
                        repair_mojibake_text(
                            f"Đang phát tiếp preview: {preview_path}"
                        )
                    )
                return
        self.render_preview_player.pause()
        self._update_render_preview_button_labels()
        preview_path = Path(self._current_render_preview_path()).name or "video render"
        if hasattr(self, "render_preview_status_label"):
            self.render_preview_status_label.setText(
                repair_mojibake_text(f"Đã tạm dừng preview: {preview_path}")
            )

    def stop_render_preview(self, *, clear_source: bool = False) -> None:
        if self.render_preview_player is not None:
            self.render_preview_player.stop()
            if clear_source:
                self.render_preview_player.setSource(QUrl())
        self._reset_render_preview_timeline(clear_duration=clear_source)
        self._update_render_preview_button_labels()
        if clear_source and hasattr(self, "render_preview_status_label"):
            self.render_preview_status_label.setText(
                "Chưa có video render để xem trước."
            )
        elif hasattr(self, "render_preview_status_label"):
            preview_path = Path(self._current_render_preview_path()).name or "video render"
            self.render_preview_status_label.setText(
                repair_mojibake_text(f"Đã dừng preview: {preview_path}")
            )

    def toggle_render_preview_mute(self) -> None:
        self._render_preview_muted = not self._render_preview_muted
        self._apply_render_preview_audio_state()

    def on_render_preview_volume_changed(self, value: int) -> None:
        self._render_preview_volume = max(0, min(int(value), 100))
        if self._render_preview_volume > 0 and self._render_preview_muted:
            self._render_preview_muted = False
        self._apply_render_preview_audio_state()

    def on_render_preview_speed_changed(self) -> None:
        if not hasattr(self, "render_preview_speed_combo"):
            return
        try:
            self._render_preview_playback_rate = float(
                self.render_preview_speed_combo.currentData() or 1.0
            )
        except Exception:
            self._render_preview_playback_rate = 1.0
        self._apply_render_preview_playback_rate()

    def toggle_render_preview_fullscreen(self) -> None:
        if self.render_video_widget is None:
            return
        is_fullscreen = bool(
            getattr(self.render_video_widget, "isFullScreen", lambda: False)()
        )
        if is_fullscreen:
            self.exit_render_preview_fullscreen()
            return
        if hasattr(self.render_video_widget, "setFullScreen"):
            self.render_video_widget.setFullScreen(True)
        else:
            self.render_video_widget.showFullScreen()
        self.render_video_widget.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self._update_render_preview_button_labels()

    def exit_render_preview_fullscreen(self) -> None:
        if self.render_video_widget is None:
            return
        is_fullscreen = bool(
            getattr(self.render_video_widget, "isFullScreen", lambda: False)()
        )
        if not is_fullscreen:
            return
        if hasattr(self.render_video_widget, "setFullScreen"):
            self.render_video_widget.setFullScreen(False)
        else:
            self.render_video_widget.showNormal()
        self._update_render_preview_button_labels()

    def _on_render_preview_duration_changed(self, duration: int) -> None:
        self._render_preview_duration_ms = max(0, int(duration))
        if hasattr(self, "render_preview_seek_slider"):
            self.render_preview_seek_slider.blockSignals(True)
            self.render_preview_seek_slider.setRange(0, self._render_preview_duration_ms)
            if not self._render_preview_scrubbing:
                self.render_preview_seek_slider.setValue(
                    min(
                        self.render_preview_seek_slider.value(),
                        self._render_preview_duration_ms,
                    )
                )
            self.render_preview_seek_slider.blockSignals(False)
        self._set_render_preview_time_labels(
            self.render_preview_seek_slider.value()
            if hasattr(self, "render_preview_seek_slider")
            else 0,
            self._render_preview_duration_ms,
        )

    def _on_render_preview_position_changed(self, position: int) -> None:
        safe_position = max(0, int(position))
        if hasattr(self, "render_preview_seek_slider") and not self._render_preview_scrubbing:
            self.render_preview_seek_slider.blockSignals(True)
            self.render_preview_seek_slider.setValue(safe_position)
            self.render_preview_seek_slider.blockSignals(False)
        if not self._render_preview_scrubbing:
            self._set_render_preview_time_labels(
                safe_position, self._render_preview_duration_ms
            )

    def _on_render_preview_playback_state_changed(self, _state) -> None:
        self._update_render_preview_button_labels()

    def _on_render_preview_fullscreen_changed(self, _fullscreen: bool) -> None:
        if _fullscreen and self.render_video_widget is not None:
            self.render_video_widget.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self._update_render_preview_button_labels()

    def on_render_preview_slider_pressed(self) -> None:
        self._render_preview_scrubbing = True

    def on_render_preview_slider_moved(self, value: int) -> None:
        self._set_render_preview_time_labels(value, self._render_preview_duration_ms)

    def on_render_preview_slider_released(self) -> None:
        self._render_preview_scrubbing = False
        if (
            self.render_preview_player is not None
            and hasattr(self, "render_preview_seek_slider")
        ):
            target_position = int(self.render_preview_seek_slider.value())
            self.render_preview_player.setPosition(target_position)
            self._set_render_preview_time_labels(
                target_position, self._render_preview_duration_ms
            )

    def export_rendered_video_file(self) -> None:
        preview_path = self._current_render_preview_path()
        if not preview_path:
            QMessageBox.information(
                self,
                "Chưa có video render",
                "Hãy render video trước khi xuất file.",
            )
            return
        source_path = Path(preview_path)
        if not source_path.exists():
            QMessageBox.information(
                self,
                "Không tìm thấy video",
                f"Không thấy file video render tại:\n{source_path}",
            )
            return
        default_dir = Path(
            self.output_dir_edit.text().strip() or str(DEFAULT_OUTPUT_DIR)
        )
        default_dir.mkdir(parents=True, exist_ok=True)
        default_name = source_path.name or "dubstudio_render.mp4"
        target_path, _ = QFileDialog.getSaveFileName(
            self,
            "Xuất file video",
            str(default_dir / default_name),
            "Video (*.mp4 *.mov *.mkv *.avi *.m4v *.webm)",
        )
        if not target_path:
            return
        destination = Path(target_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination)
        self.last_exported_output_path = str(destination)
        self.sync_output_directory_inputs(str(destination.parent))
        self.settings["outputDirectory"] = str(destination.parent)
        self.refresh_all()
        QMessageBox.information(
            self,
            "Xuất file hoàn tất",
            f"Đã xuất video ra file:\n{destination}",
        )

    def export_video_thumbnail(self) -> None:
        import requests
        import os
        from PyQt6.QtWidgets import QInputDialog, QLineEdit
        from pathlib import Path
        try:
            env_file = Path(__file__).resolve().parent.parent.parent / ".env"
            if env_file.exists():
                for raw_line in env_file.read_text(encoding="utf-8-sig").splitlines():
                    line = raw_line.replace("\x00", "").strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ[k.strip()] = v.strip().strip('"').strip("'")
        except Exception:
            pass

        # Check for HF_TOKEN
        hf_token = ""
        for key in ("HF_TOKEN", "HUGGINGFACE_TOKEN", "HUGGING_FACE_HUB_TOKEN"):
            val = os.getenv(key, "").strip()
            if val:
                hf_token = val
                break
        
        if not hf_token:
            QMessageBox.warning(
                self,
                "Thiếu Token Hugging Face",
                "Chưa tìm thấy token kết nối Hugging Face (HF_TOKEN). Vui lòng thiết lập trong biến môi trường trước khi dùng.",
            )
            return

        # Prompt user for description
        prompt, ok = QInputDialog.getText(
            self,
            "Thiết kế Thumbnail",
            "Nhập mô tả hình ảnh thumbnail (Tiếng Anh cho AI hiểu tốt nhất):",
            QLineEdit.EchoMode.Normal,
            "A beautiful YouTube thumbnail for a video, vibrant colors, cinematic, 4k"
        )
        if not ok or not prompt.strip():
            return
            
        QMessageBox.information(
            self,
            "Đang xử lý",
            "Đang gửi yêu cầu đến Hugging Face AI để thiết kế thumbnail. Vui lòng đợi...",
        )
        
        try:
            from huggingface_hub import InferenceClient
            client = InferenceClient(token=hf_token)
            image = client.text_to_image(
                prompt.strip(),
                model="black-forest-labs/FLUX.1-schnell"
            )
            
            # Save location
            default_dir = Path(
                self.output_dir_edit.text().strip() or str(ROOT / "output")
            )
            default_dir.mkdir(parents=True, exist_ok=True)
            
            from PyQt6.QtWidgets import QFileDialog
            target_path, _ = QFileDialog.getSaveFileName(
                self,
                "Lưu Thumbnail",
                str(default_dir / "thumbnail.png"),
                "Hình ảnh (*.png *.jpg *.jpeg)",
            )
            if not target_path:
                return
                
            image.save(target_path)
                
            QMessageBox.information(
                self,
                "Thành công",
                f"Đã thiết kế và lưu thumbnail thành công tại:\n{target_path}",
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Lỗi tạo thumbnail",
                f"Không thể tạo thumbnail bằng Hugging Face API:\n{str(e)}",
            )


    def open_output(self) -> None:
        target = self.last_output_path or self.output_dir_edit.text().strip()
        if not target:
            QMessageBox.information(self, "Chưa có output", "Chưa có output để mở.")
            return
        path = Path(target)
        open_target = path.parent if path.is_file() else path
        if not open_target.exists() and path.parent.exists():
            open_target = path.parent
        if not open_target.exists():
            QMessageBox.information(
                self, "Không tìm thấy output", f"Đường dẫn chưa tồn tại:\n{open_target}"
            )
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(open_target))):
            QMessageBox.warning(
                self, "Không thể mở", f"Không thể mở đường dẫn:\n{open_target}"
            )

    def choose_hf_cache_dir(self) -> None:
        current = self.conf_hf_cache_edit.text().strip()
        default_path = current if current else str(ROOT / "temp" / ".cache" / "huggingface" / "hub")
        dir_path = QFileDialog.getExistingDirectory(self, "Chọn thư mục cache HuggingFace", default_path)
        if dir_path:
            self.conf_hf_cache_edit.setText(dir_path)

    def load_system_config_into_ui(self) -> None:
        import os, sys
        if getattr(sys, "frozen", False):
            env_file = Path(sys.executable).resolve().parent / ".env"
        else:
            env_file = Path(__file__).resolve().parent.parent.parent / ".env"
        env_data = {}
        if env_file.exists():
            try:
                for raw_line in env_file.read_text(encoding="utf-8-sig").splitlines():
                    line = raw_line.replace("\x00", "").strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        env_data[k.strip()] = v.strip().strip('"').strip("'")
            except Exception:
                pass

        # Map data to UI fields with fallback to current environment or defaults
        transcribe = env_data.get("DUB_TRANSCRIBE_PROVIDER") or os.getenv("DUB_TRANSCRIBE_PROVIDER", "auto")
        self.conf_transcribe_combo.setCurrentText(transcribe)

        translate = env_data.get("DUB_TRANSLATE_PROVIDER") or os.getenv("DUB_TRANSLATE_PROVIDER", "ollama")
        self.conf_translate_combo.setCurrentText(translate)

        ollama_url = env_data.get("DUB_OLLAMA_BASE_URL") or os.getenv("DUB_OLLAMA_BASE_URL", "http://localhost:11434")
        self.conf_ollama_url_edit.setText(ollama_url)

        ollama_model = env_data.get("DUB_OLLAMA_MODEL") or os.getenv("DUB_OLLAMA_MODEL", "qwen3.5:4b")
        self.conf_ollama_model_edit.setText(ollama_model)

        hf_token = env_data.get("HF_TOKEN") or os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_TOKEN") or os.getenv("HUGGING_FACE_HUB_TOKEN", "")
        self.conf_hf_token_edit.setText(hf_token)

        hf_cache = env_data.get("DUB_HF_CACHE_DIR") or os.getenv("DUB_HF_CACHE_DIR") or str(ROOT / "temp" / ".cache" / "huggingface" / "hub")
        self.conf_hf_cache_edit.setText(hf_cache)

        # Cloud AI configurations
        ai_mode = env_data.get("DUB_AI_MODE") or os.getenv("DUB_AI_MODE", "local")
        self.conf_ai_mode_combo.setCurrentText(ai_mode)

        cloud_api_key = env_data.get("DUB_CLOUD_API_KEY") or os.getenv("DUB_CLOUD_API_KEY", "")
        self.conf_cloud_api_key_edit.setText(cloud_api_key)

        cloud_model = env_data.get("DUB_CLOUD_MODEL") or os.getenv("DUB_CLOUD_MODEL", "gemini-2.5-flash")
        self.conf_cloud_model_edit.setText(cloud_model)

        voice_api_url = env_data.get("DUB_VOICE_API_URL") or os.getenv("DUB_VOICE_API_URL", "")
        self.conf_voice_api_url_edit.setText(voice_api_url)

        voice_api_key = env_data.get("DUB_VOICE_API_KEY") or os.getenv("DUB_VOICE_API_KEY", "")
        self.conf_voice_api_key_edit.setText(voice_api_key)

        # Read-only encoding parameters
        x264_crf = env_data.get("DUB_VIDEO_X264_CRF") or os.getenv("DUB_VIDEO_X264_CRF", "18")
        self.conf_x264_crf_edit.setText(x264_crf)
        
        x264_preset = env_data.get("DUB_VIDEO_X264_PRESET") or os.getenv("DUB_VIDEO_X264_PRESET", "slow")
        self.conf_x264_preset_edit.setText(x264_preset)
        
        nvenc_cq = env_data.get("DUB_VIDEO_NVENC_CQ") or os.getenv("DUB_VIDEO_NVENC_CQ", "18")
        self.conf_nvenc_cq_edit.setText(nvenc_cq)
        
        nvenc_preset = env_data.get("DUB_VIDEO_NVENC_PRESET") or os.getenv("DUB_VIDEO_NVENC_PRESET", "p7")
        self.conf_nvenc_preset_edit.setText(nvenc_preset)

    def save_system_config(self) -> None:
        import os, sys
        if getattr(sys, "frozen", False):
            env_file = Path(sys.executable).resolve().parent / ".env"
        else:
            env_file = Path(__file__).resolve().parent.parent.parent / ".env"
        
        ai_mode = self.conf_ai_mode_combo.currentText().strip()
        cloud_api_key = self.conf_cloud_api_key_edit.text().strip()
        cloud_model = self.conf_cloud_model_edit.text().strip()
        voice_api_url = self.conf_voice_api_url_edit.text().strip()
        voice_api_key = self.conf_voice_api_key_edit.text().strip()

        if ai_mode == "cloud":
            if not cloud_api_key:
                QMessageBox.warning(self, "Lỗi", "Vui lòng nhập API Key cho Cloud AI.")
                return
            if not cloud_model:
                QMessageBox.warning(self, "Lỗi", "Vui lòng nhập tên Model Cloud.")
                return

            import requests
            m_name = cloud_model if cloud_model.startswith("models/") else f"models/{cloud_model}"
            url = f"https://generativelanguage.googleapis.com/v1beta/{m_name}:generateContent?key={cloud_api_key}"
            headers = {"Content-Type": "application/json"}
            payload = {
                "contents": [{"parts": [{"text": "Hello, answer immediately in 1 word: OK"}]}],
                "generationConfig": {"maxOutputTokens": 10}
            }
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=15)
                if resp.status_code == 429:
                    QMessageBox.warning(self, "Lỗi", "Hết quota. Vui lòng kiểm tra lại quota của API Key này.")
                    return
                if resp.status_code != 200:
                    try:
                        err_msg = resp.json().get("error", {}).get("message", resp.text)
                    except Exception:
                        err_msg = resp.text
                    QMessageBox.warning(self, "Lỗi", f"Model hoặc API Key không chính xác:\n{err_msg}")
                    return
            except Exception as e:
                if "quota" in str(e).lower():
                    QMessageBox.warning(self, "Lỗi", "Hết quota. Vui lòng kiểm tra lại quota của API Key này.")
                    return
                QMessageBox.warning(self, "Lỗi", f"Lỗi kiểm tra model Cloud AI:\n{e}")
                return

        # Gather current lines from .env if it exists, to preserve unrelated configs
        lines = []
        if env_file.exists():
            try:
                lines = env_file.read_text(encoding="utf-8-sig").splitlines()
            except Exception:
                pass
        
        new_values = {
            "DUB_TRANSCRIBE_PROVIDER": self.conf_transcribe_combo.currentText(),
            "DUB_TRANSLATE_PROVIDER": self.conf_translate_combo.currentText(),
            "DUB_OLLAMA_BASE_URL": self.conf_ollama_url_edit.text().strip(),
            "DUB_OLLAMA_MODEL": self.conf_ollama_model_edit.text().strip(),
            "HF_TOKEN": self.conf_hf_token_edit.text().strip(),
            "DUB_HF_CACHE_DIR": self.conf_hf_cache_edit.text().strip().replace("\\", "/"),
            "DUB_AI_MODE": ai_mode,
            "DUB_CLOUD_API_KEY": cloud_api_key,
            "DUB_CLOUD_MODEL": cloud_model,
            "DUB_VOICE_API_URL": voice_api_url,
            "DUB_VOICE_API_KEY": voice_api_key,
        }

        # Apply changes to lines
        updated_keys = set()
        new_lines = []
        for raw_line in lines:
            line_stripped = raw_line.strip()
            if line_stripped and not line_stripped.startswith("#") and "=" in line_stripped:
                k, v = line_stripped.split("=", 1)
                k = k.strip()
                if k in new_values:
                    new_lines.append(f"{k}={new_values[k]}")
                    updated_keys.add(k)
                    # Also update current os.environ at runtime
                    os.environ[k] = new_values[k]
                else:
                    new_lines.append(raw_line)
            else:
                new_lines.append(raw_line)

        # Append new keys that weren't in the original .env
        for k, v in new_values.items():
            if k not in updated_keys:
                new_lines.append(f"{k}={v}")
                os.environ[k] = v

        try:
            env_file.write_text("\n".join(new_lines), encoding="utf-8")
            QMessageBox.information(self, "Thành công", "Cấu hình đã được lưu vào file .env và áp dụng ngay lập tức.")
        except Exception as e:
            QMessageBox.warning(self, "Lỗi", f"Không thể ghi cấu hình ra file .env:\n{e}")

    def check_and_update_application(self) -> None:
        import sys
        from pathlib import Path
        from gui.updater import trigger_update
        is_frozen = getattr(sys, "frozen", False)
        if is_frozen:
            root = Path(sys.executable).resolve().parent
        else:
            root = Path(__file__).resolve().parent.parent.parent
        trigger_update(self, is_frozen, root)

    def check_cloud_models(self) -> None:
        api_key = self.conf_cloud_api_key_edit.text().strip()
        if not api_key:
            QMessageBox.warning(self, "Lỗi", "Vui lòng nhập API Key trước khi kiểm tra.")
            return
        
        import requests
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        try:
            resp = requests.get(url, timeout=15)
            if resp.status_code == 429:
                QMessageBox.warning(self, "Lỗi", "Hết quota. Vui lòng kiểm tra lại API Key.")
                return
            if resp.status_code != 200:
                try:
                    err_msg = resp.json().get("error", {}).get("message", resp.text)
                except Exception:
                    err_msg = resp.text
                QMessageBox.warning(self, "Lỗi", f"API Key không chính xác hoặc không thể truy cập:\n{err_msg}")
                return
            
            data = resp.json()
            models = [m.get("name", "").replace("models/", "") for m in data.get("models", []) if "generateContent" in m.get("supportedGenerationMethods", [])]
            if not models:
                models = [m.get("name", "").replace("models/", "") for m in data.get("models", [])]
            
            if models:
                msg = "Các model có thể sử dụng với API Key này:\n\n" + "\n".join(models[:15])
                if len(models) > 15:
                    msg += f"\n...và {len(models)-15} model khác."
                QMessageBox.information(self, "Các model khả dụng", msg)
            else:
                QMessageBox.warning(self, "Thông báo", "Không tìm thấy model khả dụng cho API Key này.")
        except Exception as e:
            if "quota" in str(e).lower():
                QMessageBox.warning(self, "Lỗi", "Hết quota. Vui lòng kiểm tra lại quota của API Key này.")
            else:
                QMessageBox.warning(self, "Lỗi", f"Không thể kết nối hoặc kiểm tra API Key:\n{e}")

    def check_voice_api_voices(self) -> None:
        api_url = self.conf_voice_api_url_edit.text().strip()
        api_key = self.conf_voice_api_key_edit.text().strip()
        if not api_url:
            QMessageBox.warning(self, "Lỗi", "Vui lòng nhập Voice API URL trước khi kiểm tra.")
            return

        import requests
        # Standardize voice list endpoint URL
        target_url = api_url
        if target_url.endswith("/audio/speech") or target_url.endswith("/audio/speech/"):
            target_url = target_url.replace("/audio/speech", "").replace("/audio/speech/", "")
            
        if not target_url.endswith("/voices") and not target_url.endswith("/voices/"):
            if target_url.endswith("/"):
                target_url += "voices"
            else:
                target_url += "/voices"

        headers = {
            "Content-Type": "application/json"
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        try:
            extracted_voices = []
            
            # 1. Handle FPT AI dynamic bypass & quota limit check
            if "fpt.ai" in api_url.lower():
                token_info = ""
                try:
                    fpt_limit_url = "https://api.fpt.ai/houts/v1/limit"
                    limit_headers = {"api-key": api_key}
                    limit_resp = requests.get(fpt_limit_url, headers=limit_headers, timeout=10)
                    if limit_resp.status_code == 200:
                        limit_data = limit_resp.json()
                        limit_val = limit_data.get("limit") or limit_data.get("current_limit")
                        usage_val = limit_data.get("usage") or limit_data.get("current_usage")
                        if limit_val is not None and usage_val is not None:
                            remaining = max(0, int(limit_val) - int(usage_val))
                            token_info = f"Số ký tự (token) FPT AI còn lại: {remaining:,} / {int(limit_val):,} ký tự."
                except Exception:
                    pass

                extracted_voices = [
                    ("leminh", "FPT • Lê Minh (Nam Bắc)"),
                    ("banmai", "FPT • Ban Mai (Nữ Bắc)"),
                    ("thuha", "FPT • Thu Hà (Nữ Bắc)"),
                    ("lannhi", "FPT • Lan Nhi (Nữ Nam)"),
                    ("haicong", "FPT • Hải Công (Nam Nam)"),
                    ("giaminh", "FPT • Gia Minh (Nam Trung)"),
                ]
                
                self._save_and_sync_voices(extracted_voices, token_info)
                return

            # 2. Handle standard OpenAI or Custom OpenAI-compatible TTS URL
            resp = requests.get(target_url, headers=headers, timeout=15)
            if resp.status_code != 200:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text}")
            
            data = resp.json()
            
            # Highly flexible parsing of various API JSON formats
            items = []
            if isinstance(data, dict):
                if "data" in data and isinstance(data["data"], list):
                    items = data["data"]
                elif "voices" in data and isinstance(data["voices"], list):
                    items = data["voices"]
                else:
                    for k, v in data.items():
                        if isinstance(v, dict) and ("name" in v or "label" in v):
                            lbl = v.get("name") or v.get("label") or k
                            extracted_voices.append((k, lbl))
                        elif isinstance(v, str):
                            extracted_voices.append((k, v))
            elif isinstance(data, list):
                items = data
                
            if items:
                for item in items:
                    if isinstance(item, dict):
                        voice_id = item.get("id") or item.get("voice_id")
                        voice_name = item.get("name") or item.get("label") or voice_id
                        if voice_id:
                            extracted_voices.append((str(voice_id), str(voice_name)))
                    elif isinstance(item, str):
                        extracted_voices.append((item, item))
            
            if not extracted_voices:
                QMessageBox.warning(self, "Thông báo", "Không tìm thấy giọng nói hợp lệ trong phản hồi từ API.")
                return

            self._save_and_sync_voices(extracted_voices)
            
        except Exception as e:
            QMessageBox.warning(self, "Lỗi", f"Không thể kết nối hoặc tải danh sách giọng nói từ Voice API:\n{e}")

    def _save_and_sync_voices(self, extracted_voices: list, extra_info: str = "") -> None:
        import json
        import sys
        from pathlib import Path
        
        is_frozen = getattr(sys, "frozen", False)
        if is_frozen:
            root = Path(sys.executable).resolve().parent
        else:
            root = Path(__file__).resolve().parent.parent.parent
            
        config_dir = root / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        custom_voices_file = config_dir / "custom_cloud_voices.json"
        
        voices_to_save = {}
        for vid, vname in extracted_voices:
            voices_to_save[f"cloud:{vid}"] = {"label": f"Cloud • {vname}"}
            
        custom_voices_file.write_text(json.dumps(voices_to_save, ensure_ascii=False, indent=2), encoding="utf-8")
        
        # Trigger dynamic in-place reload in gui/config.py
        from gui.config import reload_custom_cloud_voices
        reload_custom_cloud_voices()
        
        # Refresh Intro Hook Voice drop-down
        if hasattr(self, "intro_voice_combo") and self.intro_voice_combo:
            from gui.config import VOICE_OPTIONS
            current_intro_voice = self.intro_voice_combo.currentData()
            self.intro_voice_combo.clear()
            for val, lbl in VOICE_OPTIONS:
                self.intro_voice_combo.addItem(lbl, val)
            idx = self.intro_voice_combo.findData(current_intro_voice)
            if idx >= 0:
                self.intro_voice_combo.setCurrentIndex(idx)

        # Refresh Character voice mapping panel
        if hasattr(self, "rebuild_voice_mapping_ui"):
            self.rebuild_voice_mapping_ui()

        # Refresh Subtitle Timeline editing grid
        if hasattr(self, "rebuild_subtitle_table"):
            self.rebuild_subtitle_table()
            
        voice_list_str = "\n".join([f"- {vname} (ID: {vid})" for vid, vname in extracted_voices[:30]])
        if len(extracted_voices) > 30:
            voice_list_str += f"\n... và {len(extracted_voices) - 30} giọng nói khác."
            
        msg = f"Đã tải thành công {len(extracted_voices)} giọng nói từ Voice API:\n\n{voice_list_str}\n"
        if extra_info:
            msg += f"\n👉 {extra_info}\n"
        msg += "\nCác giọng nói mới này đã được tự động cập nhật vào trang chính và có thể sử dụng trực tiếp để lồng tiếng ngay lập tức!"
        QMessageBox.information(self, "Kiểm tra Voice API thành công", msg)

    def open_configured_output_directory(self) -> None:
        target = self.output_dir_edit.text().strip()
        if not target:
            QMessageBox.information(
                self, "Thiếu thư mục output", "Bạn chưa đặt thư mục output."
            )
            return
        output_dir = Path(target)
        if not output_dir.exists():
            QMessageBox.information(
                self, "Chưa có thư mục output", f"Thư mục chưa tồn tại:\n{output_dir}"
            )
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(output_dir))):
            QMessageBox.warning(
                self, "Không thể mở", f"Không thể mở thư mục:\n{output_dir}"
            )

    def _current_subtitle_timeline(self) -> list[dict[str, Any]]:
        analysis = self.effective_analysis or self.analysis or {}
        return copy.deepcopy(analysis.get("subtitleTimeline") or [])

    def _set_subtitle_timeline(
        self, timeline: list[dict[str, Any]], *, source: str
    ) -> None:
        if not self.job_id or not self.analysis:
            return
        try:
            self.effective_analysis = self.controller.update_analysis_config(
                self.job_id,
                {
                    "subtitleTimeline": copy.deepcopy(timeline),
                    "subtitleSrt": compose_srt_from_timeline(timeline),
                    "subtitleTimelineSource": source,
                },
            )
            self.refresh_all()
        except Exception as exc:
            QMessageBox.critical(self, "Cập nhật subtitle thất bại", str(exc))

    def import_subtitle_srt(self) -> None:
        if not self.job_id or not self.analysis:
            QMessageBox.information(
                self,
                "Chưa có phân tích",
                "Hãy phân tích video trước khi import subtitle.",
            )
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Import subtitle SRT", "", "Subtitle (*.srt)"
        )
        if not path:
            return
        try:
            content = Path(path).read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            content = Path(path).read_text(encoding="utf-8")
        timeline = parse_srt_to_timeline(
            content,
            fallback_segments=(self.effective_analysis or self.analysis or {}).get(
                "segments"
            )
            or [],
        )
        if not timeline:
            QMessageBox.warning(
                self,
                "Import thất bại",
                "File SRT không có block subtitle hợp lệ.",
            )
            return
        self._set_subtitle_timeline(timeline, source="imported")

    def export_subtitle_srt(self) -> None:
        timeline = self._current_subtitle_timeline()
        if not timeline:
            QMessageBox.information(
                self,
                "Chưa có subtitle",
                "Không có subtitle nào để export.",
            )
            return
        default_name = "subtitle_current.srt"
        input_path = (
            Path(self.input_path_edit.text().strip())
            if self.input_path_edit.text().strip()
            else None
        )
        if input_path is not None:
            default_name = f"{input_path.stem}.srt"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export subtitle SRT",
            str(Path(self.output_dir_edit.text().strip() or str(ROOT)) / default_name),
            "Subtitle (*.srt)",
        )
        if not path:
            return
        Path(path).write_text(
            compose_srt_from_timeline(timeline), encoding="utf-8-sig"
        )

    def rebuild_subtitle_table(self) -> None:
        if not hasattr(self, "subtitle_table"):
            return
        timeline = self._current_subtitle_timeline()
        self._subtitle_table_syncing = True
        self.subtitle_table.blockSignals(True)
        self.subtitle_table.setRowCount(len(timeline))
        self.subtitle_table.verticalHeader().setDefaultSectionSize(30)
        for row, item in enumerate(timeline):
            start_ms = int(item.get("startMs") or 0)
            end_ms = int(item.get("endMs") or 0)
            start_text = f"{start_ms / 1000:.2f}s"
            end_text = f"{end_ms / 1000:.2f}s"
            for column, value, editable in [
                (0, start_text, False),
                (1, end_text, False),
                (3, repair_mojibake_text(item.get("text") or ""), True),
            ]:
                cell = QTableWidgetItem(value)
                if not editable:
                    cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.subtitle_table.setItem(row, column, cell)
            voice_combo = QComboBox()
            voice_combo.setEditable(True)
            voice_combo.setMinimumHeight(26)
            voice_combo.setMaximumHeight(26)
            voice_combo.setStyleSheet(
                """
                QComboBox {
                    min-height: 26px;
                    padding: 2px 22px 2px 8px;
                    border-radius: 8px;
                }
                QComboBox QAbstractItemView {
                    padding: 4px;
                }
                QComboBox QAbstractItemView::item {
                    min-height: 24px;
                    padding: 4px 8px;
                }
                """
            )
            voice_combo.addItem("Mặc định", "")
            for value, label in VOICE_OPTIONS:
                voice_combo.addItem(repair_mojibake_text(label), value)
            selected_voice = str(
                item.get("voice")
                or item.get("voicePreset")
                or item.get("voiceOverride")
                or ""
            ).strip()
            if selected_voice:
                found_index = voice_combo.findData(selected_voice)
                if found_index >= 0:
                    voice_combo.setCurrentIndex(found_index)
                else:
                    voice_combo.setCurrentText(selected_voice)
            else:
                voice_combo.setCurrentIndex(0)
            voice_combo.setToolTip("Chọn voice riêng cho câu này; để Mặc định nếu muốn dùng voice chung.")
            voice_combo.currentIndexChanged.connect(
                lambda _index, row=row, combo=voice_combo: self._on_subtitle_voice_combo_changed(row, combo)
            )
            if voice_combo.lineEdit() is not None:
                voice_combo.lineEdit().setStyleSheet("padding: 0px; margin: 0px;")
                voice_combo.lineEdit().editingFinished.connect(
                    lambda row=row, combo=voice_combo: self._on_subtitle_voice_combo_changed(row, combo)
                )
            self.subtitle_table.setCellWidget(row, 2, voice_combo)
            self.subtitle_table.setRowHeight(row, 30)
        self.subtitle_table.blockSignals(False)
        self._subtitle_table_syncing = False

    @staticmethod
    def _resolve_subtitle_voice_value(combo: QComboBox) -> str:
        current_text = str(combo.currentText() or "").strip()
        index = combo.currentIndex()
        if index >= 0 and current_text == combo.itemText(index):
            data = combo.itemData(index)
            return str(data or "").strip()
        if current_text.lower() in {"", "mặc định", "mac dinh", "default"}:
            return ""
        return current_text

    def _on_subtitle_voice_combo_changed(self, row: int, combo: QComboBox) -> None:
        if getattr(self, "_subtitle_table_syncing", False):
            return
        timeline = self._current_subtitle_timeline()
        if row >= len(timeline):
            return
        voice = self._resolve_subtitle_voice_value(combo)
        current_voice = str(timeline[row].get("voice") or "").strip()
        if voice == current_voice:
            return
        if voice:
            timeline[row]["voice"] = voice
        else:
            timeline[row].pop("voice", None)
            timeline[row].pop("voicePreset", None)
            timeline[row].pop("voiceOverride", None)
        self._set_subtitle_timeline(timeline, source="edited")

    def on_subtitle_table_item_changed(self, item: QTableWidgetItem) -> None:
        if getattr(self, "_subtitle_table_syncing", False):
            return
        if item.column() != 3:
            return
        timeline = self._current_subtitle_timeline()
        if item.row() >= len(timeline):
            return
        timeline[item.row()]["text"] = normalize_preview_text(item.text())
        self._set_subtitle_timeline(timeline, source="edited")

    def on_analysis_ready(self, job_id: str, analysis: dict[str, Any]) -> None:
        if self._is_batch_job(job_id):
            return
        self.job_id = job_id
        self.analysis = copy.deepcopy(self.controller.jobs[job_id]["analysis"])
        self.effective_analysis = analysis
        self.preview_media_analysis = None
        self.hydrate_settings_from_analysis(analysis)
        self.rebuild_voice_mapping_ui()
        self.refresh_all()

    def on_render_ready(self, job_id: str, payload: dict[str, Any]) -> None:
        if self._is_batch_job(job_id):
            return
        self.last_output_path = (
            payload.get("previewVideoPath")
            or payload.get("outputVideoPath")
            or payload.get("draftPath")
            or ""
        )
        self.last_exported_output_path = ""
        self.stop_render_preview(clear_source=True)
        self.job_status = self.controller.get_job_status(job_id)
        self.refresh_all()
        if not getattr(self, "_batch_running", False):
            QMessageBox.information(
                self,
                "Render hoàn tất",
                "Đã render xong. Bạn có thể bấm Xem video để preview ngay trong app hoặc bấm Xuất file khi muốn lưu ra ngoài.",
            )

    def on_status_changed(self, job_id: str, payload: dict[str, Any]) -> None:
        if self._is_batch_job(job_id):
            return
        if self.job_id == job_id:
            self.job_status = payload
            self.refresh_status_only()

    def on_job_failed(self, job_id: str, message: str) -> None:
        if self._is_batch_job(job_id):
            return
        if self.job_id == job_id:
            self.stop_render_preview()
            if not getattr(self, "_batch_running", False):
                QMessageBox.critical(self, "Lỗi pipeline", repair_mojibake_text(message))

    def _handle_render_preview_error(self, _error, error_string: str) -> None:
        message = repair_mojibake_text(
            error_string or "Không thể phát video preview trong giao diện."
        )
        self._update_render_preview_button_labels()
        if hasattr(self, "render_preview_status_label"):
            self.render_preview_status_label.setText("Phát video thất bại")
        QMessageBox.warning(self, "Không thể xem preview", message)

    def on_font_size_changed(self, value: int) -> None:
        safe_value = int(value)
        self.settings["subtitlePreset"]["fontSize"] = safe_value
        sender = self.sender()
        if hasattr(self, "font_size_spin") and sender is not self.font_size_spin:
            self.font_size_spin.blockSignals(True)
            self.font_size_spin.setValue(safe_value)
            self.font_size_spin.blockSignals(False)
        if hasattr(self, "font_size_slider") and sender is not self.font_size_slider:
            self.font_size_slider.blockSignals(True)
            self.font_size_slider.setValue(safe_value)
            self.font_size_slider.blockSignals(False)
        self.font_size_value.setText(f"{safe_value}px")
        self.refresh_preview()

    def on_blur_changed(self, value: int) -> None:
        self.settings["subtitlePreset"]["cleanupBlurStrength"] = int(value)
        self.blur_value.setText(f"{value}%")
        self.refresh_preview()

    def on_bottom_offset_changed(self, value: int) -> None:
        self.settings["subtitlePreset"]["bottomOffset"] = int(value)
        self.bottom_offset_value.setText(f"{value}px")
        self.refresh_preview()

    def on_watermark_size_changed(self, value: int) -> None:
        safe_value = max(5, min(50, int(value)))
        self.settings.setdefault("watermark", {})["scale"] = safe_value / 100.0
        if hasattr(self, "watermark_scale_value"):
            self.watermark_scale_value.setText(f"{safe_value}%")
        self.refresh_preview()

    def on_watermark_opacity_changed(self, value: int) -> None:
        safe_value = max(0, min(100, int(value)))
        self.settings.setdefault("watermark", {})["opacity"] = safe_value / 100.0
        if hasattr(self, "watermark_opacity_value"):
            self.watermark_opacity_value.setText(f"{safe_value}%")
        self.refresh_preview()

    def pick_watermark_bg_color(self) -> None:
        wm = self.settings.setdefault("watermark", {})
        current = QColor(wm.get("bgColor", "#000000"))
        color = QColorDialog.getColor(current, self, "Chọn màu nền để xóa")
        if not color.isValid():
            return
        wm["bgColor"] = color.name()
        self.refresh_all()

    def on_watermark_scale_dragged(self, scale: float) -> None:
        slider_value = max(5, min(50, int(round(float(scale) * 100))))
        self.settings.setdefault("watermark", {})["scale"] = slider_value / 100.0
        if hasattr(self, "watermark_scale_slider"):
            self.watermark_scale_slider.blockSignals(True)
            self.watermark_scale_slider.setValue(slider_value)
            self.watermark_scale_slider.blockSignals(False)
        if hasattr(self, "watermark_scale_value"):
            self.watermark_scale_value.setText(f"{slider_value}%")
        self.refresh_preview()

    def on_preview_subtitle_dragged(
        self, position_preset: str, bottom_offset: int
    ) -> None:
        self.settings["subtitlePreset"]["positionPreset"] = position_preset
        self.settings["subtitlePreset"]["bottomOffset"] = int(bottom_offset)
        self.sync_widgets_from_settings()
        self.refresh_preview()

    def apply_caption_position(self, position_preset: str) -> None:
        default_offset = {"top": 24, "middle": 0, "bottom": 54}
        self.settings["subtitlePreset"]["positionPreset"] = position_preset
        self.settings["subtitlePreset"]["bottomOffset"] = default_offset.get(
            position_preset, 54
        )
        self.sync_widgets_from_settings()
        self.refresh_preview()

    def on_font_group_changed(self) -> None:
        self.settings["subtitlePreset"]["fontGroup"] = str(
            self.font_group_combo.currentData() or "all"
        )
        self.on_basic_settings_changed()

    def apply_box_style_preset(self, preset_name: str) -> None:
        preset_key = str(preset_name or "").strip()
        preset = BOX_STYLE_PRESETS.get(preset_key)
        if not preset:
            return
        self.settings["subtitlePreset"].update(preset)
        self.settings["subtitlePreset"]["boxStylePreset"] = preset_key
        self.sync_widgets_from_settings()
        self.refresh_all()

    def on_box_style_changed(self) -> None:
        self.apply_box_style_preset(str(self.box_style_combo.currentData() or ""))
        self.refresh_preview()

    def on_box_style_detail_changed(self) -> None:
        self.settings["subtitlePreset"]["boxStylePreset"] = "custom"
        if hasattr(self, "box_style_combo"):
            self.box_style_combo.blockSignals(True)
            self._set_combo_value(self.box_style_combo, "custom")
            self.box_style_combo.blockSignals(False)
        self.on_basic_settings_changed()
        self.refresh_preview()

    def choose_background_music_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Chon file nhac nen",
            "",
            "Audio (*.mp3 *.wav *.m4a *.aac *.flac *.ogg *.opus *.wma)",
        )
        if not path:
            return
        for attr in ("background_music_path_edit", "main_background_music_path_edit"):
            w = getattr(self, attr, None)
            if w is not None:
                w.setText(path)
        for attr in ("background_music_enabled_check", "main_background_music_enabled_check"):
            w = getattr(self, attr, None)
            if w is not None:
                w.setChecked(True)
        self.settings.setdefault("backgroundMusic", {})["path"] = path
        self.settings["backgroundMusic"]["enabled"] = True
        self.on_basic_settings_changed()

    def choose_ending_video_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn file ending clip",
            "",
            "Video (*.mp4 *.mov *.avi *.mkv *.wmv *.webm *.flv)",
        )
        if not path:
            return
        if hasattr(self, "ending_video_path_edit"):
            self.ending_video_path_edit.setText(path)
        if hasattr(self, "ending_video_enabled_check"):
            self.ending_video_enabled_check.setChecked(True)
        self.settings.setdefault("endingVideo", {})["path"] = path
        self.settings["endingVideo"]["enabled"] = True
        self.on_basic_settings_changed()

    def on_cleanup_region_dragged(self, region: dict[str, int]) -> None:
        self.settings["subtitleRegion"] = {
            "x": int(region.get("x", 0)),
            "y": int(region.get("y", 0)),
            "w": int(region.get("w", 0)),
            "h": int(region.get("h", 0)),
        }
        self.sync_widgets_from_settings()
        self.refresh_preview()

    def on_cleanup_region_changed(self, region: dict[str, int]) -> None:
        self.on_cleanup_region_dragged(region)

    def on_font_changed(self) -> None:
        option = find_font_option(self.font_combo.currentData())
        self.settings["subtitlePreset"].update(
            {
                "fontFamily": option["value"],
                "fontFamilyLabel": option["label"],
                "fontFamilyName": option["fontFamilyName"],
                "cssFontFamily": option["cssFontFamily"],
                "assFontName": option["assFontName"],
                "draftFontKey": option["draftFontKey"],
            }
        )
        self.refresh_preview()

    def on_speaker_detection_changed(self) -> None:
        mode = self.speaker_detection_combo.currentData()
        self.settings["speakerDetectionMode"] = mode
        if mode == "narrator":
            self.speaker_count_spin.setValue(1)
        else:
            detected_raw = int(
                (self.analysis or {}).get("detectedSpeakerCountRaw")
                or self.speaker_count_spin.value()
                or 2
            )
            self.speaker_count_spin.setValue(max(2, detected_raw))
        self.on_basic_settings_changed()

    def on_basic_settings_changed(self) -> None:
        self.read_settings_from_widgets()
        self._push_analysis_overrides()
        self.refresh_all()

    def pick_color(self, key: str) -> None:
        current = QColor(self.settings["subtitlePreset"].get(key, "#ffffff"))
        color = QColorDialog.getColor(current, self, "Chọn màu")
        if not color.isValid():
            return
        self.settings["subtitlePreset"][key] = color.name()
        self.refresh_all()

    def _sync_voice_mapping_from_widgets(self) -> None:
        voice_mapping = copy.deepcopy(self.settings.get("voiceMapping") or {})
        for speaker_id, combo in getattr(self, "voice_combo_map", {}).items():
            if combo is None:
                continue
            voice = self._resolve_voice_combo_value(combo)
            if not str(voice or "").strip():
                continue
            voice_mapping[str(speaker_id)] = str(voice).strip()
            status_label = self.voice_status_label_map.get(str(speaker_id))
            if status_label is not None:
                status_label.setText(
                    f"Đã chọn: {self._format_voice_label(voice_mapping[str(speaker_id)])}"
                )
        self.settings["voiceMapping"] = voice_mapping

    def _selected_default_voice(self) -> str:
        combo = getattr(self, "default_voice_combo", None)
        voice = ""
        if combo is not None:
            voice = str(self._resolve_voice_combo_value(combo) or "").strip()
        if not voice:
            voice = str(self.settings.get("defaultVoice") or "").strip()
        if not voice:
            voice = str((self.settings.get("voiceMapping") or {}).get("speaker_1") or "").strip()
        return voice or preferred_default_voice()

    def _expanded_voice_mapping(self) -> dict[str, str]:
        voice_mapping = copy.deepcopy(self.settings.get("voiceMapping") or {})
        default_voice = str(self.settings.get("defaultVoice") or self._selected_default_voice()).strip()
        if not default_voice:
            default_voice = preferred_default_voice()
        try:
            speaker_count = int(self.settings.get("speakerCount") or 1)
        except Exception:
            speaker_count = 1
        speaker_count = max(1, min(speaker_count, 4))
        for index in range(speaker_count):
            voice_mapping.setdefault(f"speaker_{index + 1}", default_voice)
        return voice_mapping

    def read_settings_from_widgets(self) -> None:
        is_page_0 = getattr(self, "_page_stack", None) is not None and self._page_stack.currentIndex() == 0
        
        def get_combo_val(main_w, default_w):
            w = main_w if (is_page_0 and main_w) else default_w
            return str(w.currentData()) if w else ""
            
        def get_spin_val(main_w, default_w):
            w = main_w if (is_page_0 and main_w) else default_w
            return w.value() if w else 0
            
        def get_check_val(main_w, default_w):
            w = main_w if (is_page_0 and main_w) else default_w
            return w.isChecked() if w else False

        self.settings["sourceLanguage"] = get_combo_val(getattr(self, "main_source_language_combo", None), self.source_language_combo)
        self.settings["targetLanguage"] = get_combo_val(getattr(self, "main_target_language_combo", None), self.target_language_combo)
        self.settings["speakerDetectionMode"] = get_combo_val(getattr(self, "main_speaker_detection_combo", None), self.speaker_detection_combo)
        self.settings["speakerCount"] = int(get_spin_val(getattr(self, "main_speaker_count_spin", None), self.speaker_count_spin))
        self.settings["defaultVoice"] = self._selected_default_voice()
        self.settings["timingMode"] = get_combo_val(getattr(self, "main_timing_mode_combo", None), self.timing_mode_combo)
        self.settings["videoCodecMode"] = str(
            self.video_codec_combo.currentData() or "gpu_preferred"
        )
        self.settings["sourceSubtitleCleanupMode"] = get_combo_val(getattr(self, "main_cleanup_combo", None), self.cleanup_combo)
        self.settings["subtitlePreset"]["enabled"] = (
            get_combo_val(None, self.subtitle_enabled_combo) == "on"
        )
        self.settings["subtitlePreset"]["positionPreset"] = str(
            self.subtitle_position_combo.currentData()
        )
        if hasattr(self, "font_group_combo"):
            self.settings["subtitlePreset"]["fontGroup"] = str(
                self.font_group_combo.currentData() or "all"
            )
        if hasattr(self, "font_size_spin"):
            self.settings["subtitlePreset"]["fontSize"] = int(
                self.font_size_spin.value()
            )
        self.settings["subtitlePreset"]["strokeWidth"] = int(
            self.stroke_width_spin.value()
        )
        self.settings["subtitlePreset"]["maxWordsPerChunk"] = int(
            self.max_words_spin.value()
        )
        if hasattr(self, "subtitle_box_check"):
            self.settings["subtitlePreset"]["boxEnabled"] = bool(
                self.subtitle_box_check.isChecked()
            )
        if hasattr(self, "box_style_combo"):
            self.settings["subtitlePreset"]["boxStylePreset"] = str(
                self.box_style_combo.currentData() or "custom"
            )
        self.settings["subtitlePreset"]["boxLayoutMode"] = str(
            self.settings["subtitlePreset"].get("boxLayoutMode", "line") or "line"
        )
        if hasattr(self, "box_radius_spin"):
            self.settings["subtitlePreset"]["boxRadius"] = int(
                self.box_radius_spin.value()
            )
        if hasattr(self, "box_border_width_spin"):
            self.settings["subtitlePreset"]["boxBorderWidth"] = int(
                self.box_border_width_spin.value()
            )
        if hasattr(self, "box_fill_opacity_spin"):
            self.settings["subtitlePreset"]["boxFillOpacity"] = float(
                self.box_fill_opacity_spin.value()
            )
        if hasattr(self, "text_effect_combo"):
            self.settings["subtitlePreset"]["textEffect"] = str(
                self.text_effect_combo.currentData() or "none"
            )
        if hasattr(self, "subtitle_style_combo"):
            self.settings["subtitlePreset"]["subtitleStyle"] = str(self.subtitle_style_combo.currentData() or "Classic")
        if hasattr(self, "subtitle_animation_combo"):
            self.settings["subtitlePreset"]["subtitleAnimation"] = str(self.subtitle_animation_combo.currentData() or "None")
        if hasattr(self, "localization_mode_combo"):
            self.settings["localizationMode"] = str(self.localization_mode_combo.currentData() or "creative")
        sticker_id = str(self.sticker_combo.currentData() or "none")
        sticker_data = get_sticker_by_id(sticker_id) if sticker_id != "none" else {}
        sticker_transform_x = float(
            self.sticker_x_spin.value()
            if hasattr(self, "sticker_x_spin")
            else (self.settings.get("stickerOptions") or {}).get("transform_x", 0.0)
        )
        sticker_transform_y = float(
            self.sticker_y_spin.value()
            if hasattr(self, "sticker_y_spin")
            else (self.settings.get("stickerOptions") or {}).get("transform_y", -0.3)
        )
        self.settings["stickerOptions"] = {
            "stickerId": sticker_id if sticker_id != "none" else "",
            "sticker_id": sticker_id if sticker_id != "none" else "",
            "stickerName": str(self.sticker_combo.currentText() or ""),
            "image_url": str(sticker_data.get("image_url", "") or ""),
            "sticker_type": int(sticker_data.get("sticker_type", 1)),
            "scale": float(getattr(self, "sticker_scale_spin", None) and self.sticker_scale_spin.value() or 1.0),
            "transform_x": max(-1.0, min(sticker_transform_x, 1.0)),
            "transform_y": max(-1.0, min(sticker_transform_y, 1.0)),
        }
        self.settings["introHook"]["enabled"] = self.intro_enabled_check.isChecked()
        self.settings["introHook"]["clipDurationMs"] = int(
            round(self.intro_duration_spin.value() * 1000)
        )
        intro_voice_value = (
            self._resolve_voice_combo_value(self.intro_voice_combo)
            or preferred_default_voice()
        )
        intro_preset = resolve_intro_voice_preset(intro_voice_value)
        self.settings["introHook"]["voicePresetKey"] = intro_preset["key"]
        self.settings["introHook"]["voice"] = str(intro_preset["voice"])
        self.settings["introHook"]["voiceRateDeltaPercent"] = int(
            intro_preset["rateDeltaPercent"]
        )
        self.settings["introHook"]["useBackgroundAudio"] = (
            self.intro_background_check.isChecked()
        )
        intro_bg_vol_slider = getattr(self, "main_intro_background_volume_spin" if is_page_0 else "intro_background_volume_spin", None)
        if intro_bg_vol_slider is not None:
            slider_val = intro_bg_vol_slider.value()
            self.settings["introHook"]["backgroundVolume"] = slider_val / 100.0
            if hasattr(self, "intro_background_volume_label"):
                self.intro_background_volume_label.setText(f"{slider_val}%")
            if hasattr(self, "main_intro_background_volume_label"):
                self.main_intro_background_volume_label.setText(f"{slider_val}%")
        self.settings["keepOriginalAudio"] = get_check_val(getattr(self, "main_keep_original_audio_check", None), self.keep_original_audio_check)
        
        bg_music = self.settings.setdefault("backgroundMusic", {})
        bg_music["enabled"] = get_check_val(getattr(self, "main_background_music_enabled_check", None), self.background_music_enabled_check)
        
        bg_vol_slider = getattr(self, "main_background_music_volume_spin" if is_page_0 else "background_music_volume_spin", None)
        if bg_vol_slider is not None:
            slider_val = bg_vol_slider.value()
            bg_music["volume"] = slider_val / 50.0
            if hasattr(self, "background_music_volume_label"):
                self.background_music_volume_label.setText(f"{slider_val}%")
            if hasattr(self, "main_background_music_volume_label"):
                self.main_background_music_volume_label.setText(f"{slider_val}%")
                
        bg_path_edit = getattr(self, "main_background_music_path_edit" if is_page_0 else "background_music_path_edit", None)
        if bg_path_edit is not None:
            bg_music["path"] = bg_path_edit.text().strip()

        ending_vid = self.settings.setdefault("endingVideo", {})
        ending_vid["enabled"] = get_check_val(getattr(self, "main_ending_video_enabled_check", None), getattr(self, "ending_video_enabled_check", None))
        ending_path_edit = getattr(self, "main_ending_video_path_edit" if is_page_0 else "ending_video_path_edit", None)
        if ending_path_edit is not None:
            ending_vid["path"] = ending_path_edit.text().strip()
        elif hasattr(self, "ending_video_path_edit"):
            ending_vid["path"] = self.ending_video_path_edit.text().strip()

        self.settings["outputTargets"]["mp4"] = self.output_mp4_check.isChecked()
        self.settings["outputTargets"]["draft"] = self.output_draft_check.isChecked()
        self.settings["outputRatio"] = get_combo_val(getattr(self, "main_output_ratio_combo", None), getattr(self, "output_ratio_combo", None)) or "original"
        output_directory = self.output_dir_edit.text().strip()
        if not output_directory and hasattr(self, "output_folder_quick_edit"):
            output_directory = self.output_folder_quick_edit.text().strip()
        self.settings["outputDirectory"] = output_directory
        self.settings["draftRoot"] = self.draft_dir_edit.text().strip()
        self.settings["subtitleRegion"] = {
            "x": int(self.region_x_spin.value()),
            "y": int(self.region_y_spin.value()),
            "w": int(self.region_w_spin.value()),
            "h": int(self.region_h_spin.value()),
        }
        self.settings.setdefault("watermark", {})["enabled"] = self.watermark_enabled_check.isChecked()
        self.settings["watermark"]["path"] = self.watermark_path_edit.text()
        self.settings["watermark"]["position"] = str(self.watermark_position_combo.currentData())
        self.settings["watermark"]["scale"] = float(self.watermark_scale_slider.value()) / 100.0
        self.settings["watermark"]["opacity"] = float(self.watermark_opacity_slider.value()) / 100.0
        self.settings["watermark"]["removeBg"] = self.watermark_remove_bg_check.isChecked()
        self._sync_voice_mapping_from_widgets()
        # Sync display names
        display_names = {}
        for speaker_id, edit in getattr(self, "voice_name_edit_map", {}).items():
            if edit:
                val = edit.text().strip()
                if val:
                    display_names[speaker_id] = val
        self.settings["displayNameMapping"] = display_names

        if not getattr(self, "voice_combo_map", {}):
            self.settings["voiceMapping"] = {}
        self.settings["voiceMapping"] = self._expanded_voice_mapping()
        self.on_font_changed()

    def current_analysis_overrides(self) -> dict[str, Any]:
        return {
            "sourceLanguage": ""
            if self.settings["sourceLanguage"] == "auto"
            else self.settings["sourceLanguage"],
            "targetLanguage": self.settings["targetLanguage"],
            "speakerDetectionMode": self.settings["speakerDetectionMode"],
            "speakerCount": int(self.settings["speakerCount"]),
            "voiceMapping": self._expanded_voice_mapping(),
            "displayNameMapping": copy.deepcopy(self.settings.get("displayNameMapping") or {}),
            "subtitleRegion": copy.deepcopy(self.settings["subtitleRegion"]),
        }

    def current_render_options(self) -> dict[str, Any]:
        effective_source_language = (
            (self.effective_analysis or self.analysis or {}).get("sourceLanguage")
            if self.settings["sourceLanguage"] == "auto"
            else self.settings["sourceLanguage"]
        )
        return {
            "sourceLanguage": effective_source_language or "",
            "targetLanguage": self.settings["targetLanguage"],
            "speakerDetectionMode": self.settings["speakerDetectionMode"],
            "voiceMapping": self._expanded_voice_mapping(),
            "introHook": copy.deepcopy(self.settings["introHook"]),
            "subtitlePreset": copy.deepcopy(self.settings["subtitlePreset"]),
            "subtitleRegion": copy.deepcopy(self.settings["subtitleRegion"]),
            "sourceSubtitleCleanupMode": self.settings["sourceSubtitleCleanupMode"],
            "outputTargets": copy.deepcopy(self.settings["outputTargets"]),
            "outputRatio": self.settings.get("outputRatio", "original"),
            "timingMode": self.settings["timingMode"],
            "videoCodecMode": self.settings.get("videoCodecMode", "gpu_preferred"),
            "keepOriginalAudio": self.settings["keepOriginalAudio"],
            "backgroundMusic": copy.deepcopy(self.settings.get("backgroundMusic", {})),
            "endingVideo": copy.deepcopy(self.settings.get("endingVideo", {})),
            "draftRoot": self.settings["draftRoot"],
            "outputDirectory": self.settings["outputDirectory"],
            "watermarkEnabled": self.settings.get("watermark", {}).get("enabled", False),
            "watermarkPath": self.settings.get("watermark", {}).get("path", ""),
            "watermarkPosition": self.settings.get("watermark", {}).get("position", "top-right"),
            "watermarkScale": self.settings.get("watermark", {}).get("scale", 0.15),
            "stickerOptions": copy.deepcopy(self.settings.get("stickerOptions", {})),
        }

    def _push_analysis_overrides(self, *, rebuild_voice_ui: bool = True) -> None:
        if not self.job_id or not self.analysis:
            return
        try:
            self.effective_analysis = self.controller.update_analysis_config(
                self.job_id, self.current_analysis_overrides()
            )
            if rebuild_voice_ui:
                self.rebuild_voice_mapping_ui()
        except Exception:
            self.effective_analysis = copy.deepcopy(self.analysis)

    def hydrate_settings_from_analysis(self, analysis: dict[str, Any]) -> None:
        merged = default_settings()
        render_defaults = analysis.get("renderDefaults") or {}
        merged["sourceLanguage"] = (
            self.settings.get("sourceLanguage") or merged["sourceLanguage"]
        )
        merged["targetLanguage"] = analysis.get(
            "targetLanguage", self.settings.get("targetLanguage") or "vi"
        )
        merged["speakerDetectionMode"] = render_defaults.get(
            "speakerDetectionMode", merged["speakerDetectionMode"]
        )
        merged["speakerCount"] = len(analysis.get("speakers") or []) or 1
        merged["defaultVoice"] = str(
            self.settings.get("defaultVoice")
            or (self.settings.get("voiceMapping") or {}).get("speaker_1")
            or merged.get("defaultVoice")
            or preferred_default_voice()
        )
        merged["voiceMapping"] = {
            speaker.get("speakerId"): speaker.get("voicePreset")
            for speaker in analysis.get("speakers", [])
        }
        for index in range(max(1, min(int(merged["speakerCount"] or 1), 4))):
            merged["voiceMapping"].setdefault(f"speaker_{index + 1}", merged["defaultVoice"])
        
        merged["displayNameMapping"] = {}
        for speaker in analysis.get("speakers", []):
            name = speaker.get("displayName")
            spk_id = speaker.get("speakerId")
            if not name or not spk_id:
                continue
            if name.startswith("Người quen: "):
                merged["displayNameMapping"][spk_id] = name.replace("Người quen: ", "", 1)
            elif not name.startswith("speaker_") and "(" not in name and "tuổi" not in name:
                merged["displayNameMapping"][spk_id] = name
        merged["introHook"].update(render_defaults.get("introHook") or {})
        merged["subtitlePreset"].update(render_defaults.get("subtitlePreset") or {})
        merged["subtitleRegion"].update(analysis.get("subtitleRegion") or {})
        merged["sourceSubtitleCleanupMode"] = render_defaults.get(
            "sourceSubtitleCleanupMode", merged["sourceSubtitleCleanupMode"]
        )
        merged["outputTargets"].update(render_defaults.get("outputTargets") or {})
        merged["timingMode"] = render_defaults.get("timingMode", merged["timingMode"])
        merged["videoCodecMode"] = self.settings.get(
            "videoCodecMode",
            render_defaults.get("videoCodecMode", merged["videoCodecMode"]),
        )
        merged["uiThemePreset"] = self.settings.get(
            "uiThemePreset", merged["uiThemePreset"]
        )
        merged["keepOriginalAudio"] = bool(
            render_defaults.get("keepOriginalAudio", merged["keepOriginalAudio"])
        )
        merged["draftRoot"] = render_defaults.get("draftRoot") or merged["draftRoot"]
        merged["outputDirectory"] = (
            render_defaults.get("outputDirectory") or merged["outputDirectory"]
        )
        intro_preset_key = str(
            (merged.get("introHook") or {}).get("voicePresetKey") or ""
        )
        if not intro_preset_key:
            intro_voice = str((merged.get("introHook") or {}).get("voice") or "")
            if intro_voice.endswith("Neural") and intro_voice not in {
                "vi-VN-HoaiMyNeural",
                "vi-VN-NamMinhNeural",
            }:
                intro_preset_key = intro_voice
            else:
                intro_preset_key = (
                    "female_story" if intro_voice == "vi-VN-HoaiMyNeural" else "male_story"
                )
        intro_preset = resolve_intro_voice_preset(intro_preset_key)
        merged["introHook"]["voicePresetKey"] = intro_preset["key"]
        merged["introHook"]["voice"] = intro_preset["voice"]
        merged["introHook"]["voiceRateDeltaPercent"] = int(
            (merged["introHook"] or {}).get(
                "voiceRateDeltaPercent", intro_preset["rateDeltaPercent"]
            )
        )
        merged.setdefault("watermark", {})
        merged["watermark"]["enabled"] = render_defaults.get("watermarkEnabled", merged["watermark"].get("enabled", False))
        merged["watermark"]["path"] = render_defaults.get("watermarkPath", merged["watermark"].get("path", ""))
        merged["watermark"]["position"] = render_defaults.get("watermarkPosition", merged["watermark"].get("position", "top-right"))
        merged["watermark"]["scale"] = render_defaults.get("watermarkScale", merged["watermark"].get("scale", 0.15))
        merged.setdefault("stickerOptions", {}).update(
            self.settings.get("stickerOptions")
            or render_defaults.get("stickerOptions")
            or {}
        )
        self.settings = merged
        self.sync_widgets_from_settings()

    def sync_widgets_from_settings(self) -> None:
        widgets = [
            self.source_language_combo,
            self.target_language_combo,
            self.speaker_detection_combo,
            self.speaker_count_spin,
            self.timing_mode_combo,
            self.video_codec_combo,
            self.cleanup_combo,
            self.subtitle_enabled_combo,
            self.subtitle_position_combo,
            self.font_group_combo,
            self.font_combo,
            self.font_size_spin,
            self.subtitle_box_check,
            self.box_style_combo,
              self.box_radius_spin,
            self.box_border_width_spin,
            self.box_fill_opacity_spin,
            self.text_effect_combo,
            self.sticker_combo,
            self.sticker_scale_spin,
            self.sticker_x_spin,
            self.sticker_y_spin,
            self.stroke_width_spin,
            self.max_words_spin,
            self.intro_enabled_check,
            self.intro_duration_spin,
            self.intro_voice_combo,
            self.intro_background_check,
            self.intro_background_volume_spin,
            self.keep_original_audio_check,
            self.output_mp4_check,
            self.output_draft_check,
            getattr(self, "output_ratio_combo", None),
            self.output_dir_edit,
            self.draft_dir_edit,
            self.region_x_spin,
            self.region_y_spin,
            self.region_w_spin,
            self.region_h_spin,
            self.font_size_slider,
            self.blur_slider,
            self.bottom_offset_slider,
            self.watermark_enabled_check,
            self.watermark_path_edit,
            self.watermark_position_combo,
            self.watermark_scale_slider,
            self.watermark_opacity_slider,
            self.watermark_remove_bg_check,
        ]
        for optional_name in (
            "default_voice_combo", "default_voice_test_btn",
            "main_source_language_combo", "main_target_language_combo",
            "main_speaker_detection_combo", "main_speaker_count_spin",
            "main_timing_mode_combo", "main_cleanup_combo",
            "main_intro_enabled_check", "main_intro_duration_spin",
            "main_intro_voice_combo", "main_intro_background_check",
            "main_intro_background_volume_spin", "main_keep_original_audio_check",
            "background_music_enabled_check", "main_background_music_enabled_check",
            "background_music_volume_spin", "main_background_music_volume_spin",
            "main_output_ratio_combo"
        ):
            widget = getattr(self, optional_name, None)
            if widget is not None:
                widgets.append(widget)
        for widget in widgets:
            if widget is not None:
                widget.blockSignals(True)
        self._set_combo_value(
            self.source_language_combo, self.settings["sourceLanguage"]
        )
        self._set_combo_value(
            self.target_language_combo, self.settings["targetLanguage"]
        )
        self._set_combo_value(
            self.speaker_detection_combo, self.settings["speakerDetectionMode"]
        )
        self.speaker_count_spin.setValue(int(self.settings["speakerCount"]))
        self._set_combo_value(self.timing_mode_combo, self.settings["timingMode"])
        self._set_combo_value(
            self.video_codec_combo, self.settings.get("videoCodecMode", "gpu_preferred")
        )
        self._set_combo_value(
            self.cleanup_combo, self.settings["sourceSubtitleCleanupMode"]
        )
        self._set_combo_value(
            self.subtitle_enabled_combo,
            "on" if self.settings["subtitlePreset"]["enabled"] else "off",
        )
        self._set_combo_value(
            self.subtitle_position_combo,
            self.settings["subtitlePreset"]["positionPreset"],
        )
        self._set_combo_value(
            self.font_group_combo,
            self.settings["subtitlePreset"].get("fontGroup", "all"),
        )
        self._set_combo_value(
            self.font_combo, self.settings["subtitlePreset"]["fontFamily"]
        )
        self.font_size_spin.setValue(int(self.settings["subtitlePreset"]["fontSize"]))
        self.stroke_width_spin.setValue(
            int(self.settings["subtitlePreset"]["strokeWidth"])
        )
        self.max_words_spin.setValue(
            int(self.settings["subtitlePreset"]["maxWordsPerChunk"])
        )
        self.subtitle_box_check.setChecked(
            bool(self.settings["subtitlePreset"].get("boxEnabled", False))
        )
        self._set_combo_value(
            self.box_style_combo,
            self.settings["subtitlePreset"].get("boxStylePreset", "custom"),
        )
        if hasattr(self, "box_layout_combo"):
            self._set_combo_value(
                self.box_layout_combo,
                self.settings["subtitlePreset"].get("boxLayoutMode", "line"),
            )
        self.box_radius_spin.setValue(
            int(self.settings["subtitlePreset"].get("boxRadius", 16))
        )
        self.box_border_width_spin.setValue(
            int(self.settings["subtitlePreset"].get("boxBorderWidth", 2))
        )
        self.box_fill_opacity_spin.setValue(
            float(self.settings["subtitlePreset"].get("boxFillOpacity", 0.8))
        )
        self._set_combo_value(
            self.text_effect_combo,
            self.settings["subtitlePreset"].get("textEffect", "none"),
        )
        if hasattr(self, "subtitle_style_combo"):
            self._set_combo_value(self.subtitle_style_combo, self.settings["subtitlePreset"].get("subtitleStyle", "Classic"))
        if hasattr(self, "subtitle_animation_combo"):
            self._set_combo_value(self.subtitle_animation_combo, self.settings["subtitlePreset"].get("subtitleAnimation", "None"))
        if hasattr(self, "localization_mode_combo"):
            self._set_combo_value(self.localization_mode_combo, self.settings.get("localizationMode", "creative"))
        sticker_options = self.settings.get("stickerOptions") or {}
        self._set_combo_value(
            self.sticker_combo,
            str(sticker_options.get("stickerId") or sticker_options.get("sticker_id") or "none"),
        )
        self.sticker_scale_spin.setValue(float(sticker_options.get("scale", 1.0)))
        self.sticker_x_spin.setValue(float(sticker_options.get("transform_x", 0.0)))
        self.sticker_y_spin.setValue(float(sticker_options.get("transform_y", -0.3)))
        self.intro_enabled_check.setChecked(bool(self.settings["introHook"]["enabled"]))
        self.intro_duration_spin.setValue(
            float(self.settings["introHook"]["clipDurationMs"]) / 1000.0
        )
        intro_voice_key = str(
            self.settings["introHook"].get("voicePresetKey")
            or self.settings["introHook"].get("voice")
            or preferred_default_voice()
        )
        if self.intro_voice_combo.findData(intro_voice_key) >= 0:
            self._set_combo_value(self.intro_voice_combo, intro_voice_key)
        else:
            self.intro_voice_combo.setEditText(intro_voice_key)
        default_voice = str(
            self.settings.get("defaultVoice")
            or (self.settings.get("voiceMapping") or {}).get("speaker_1")
            or preferred_default_voice()
        )
        default_voice_combo = getattr(self, "default_voice_combo", None)
        if default_voice_combo is not None:
            if default_voice_combo.findData(default_voice) >= 0:
                self._set_combo_value(default_voice_combo, default_voice)
            else:
                default_voice_combo.setEditText(default_voice)
        self.intro_background_check.setChecked(
            bool(self.settings["introHook"]["useBackgroundAudio"])
        )
        intro_bg_vol = float(self.settings.get("introHook", {}).get("backgroundVolume", 0.30))
        intro_bg_slider_val = int(intro_bg_vol * 100.0)
        
        for attr in ("intro_background_volume_spin", "main_intro_background_volume_spin"):
            w = getattr(self, attr, None)
            if w is not None:
                w.setValue(intro_bg_slider_val)
                
        if hasattr(self, "intro_background_volume_label"):
            self.intro_background_volume_label.setText(f"{intro_bg_slider_val}%")
        if hasattr(self, "main_intro_background_volume_label"):
            self.main_intro_background_volume_label.setText(f"{intro_bg_slider_val}%")
        self.keep_original_audio_check.setChecked(
            bool(self.settings["keepOriginalAudio"])
        )
        self.output_mp4_check.setChecked(bool(self.settings["outputTargets"]["mp4"]))
        self.output_draft_check.setChecked(
            bool(self.settings["outputTargets"]["draft"])
        )
        if hasattr(self, "output_ratio_combo"):
            self._set_combo_value(self.output_ratio_combo, self.settings.get("outputRatio", "original"))
        if hasattr(self, "main_output_ratio_combo"):
            self._set_combo_value(self.main_output_ratio_combo, self.settings.get("outputRatio", "original"))
        
        bg_music = self.settings.get("backgroundMusic", {})
        bg_enabled = bool(bg_music.get("enabled", False))
        bg_vol = float(bg_music.get("volume", 0.12))
        bg_slider_val = int(bg_vol * 50.0)
        
        for attr in ("background_music_enabled_check", "main_background_music_enabled_check"):
            w = getattr(self, attr, None)
            if w is not None:
                w.setChecked(bg_enabled)
                
        for attr in ("background_music_volume_spin", "main_background_music_volume_spin"):
            w = getattr(self, attr, None)
            if w is not None:
                w.setValue(bg_slider_val)
                
        if hasattr(self, "background_music_volume_label"):
            self.background_music_volume_label.setText(f"{bg_slider_val}%")
        if hasattr(self, "main_background_music_volume_label"):
            self.main_background_music_volume_label.setText(f"{bg_slider_val}%")

        ending_vid = self.settings.get("endingVideo", {})
        ending_enabled = bool(ending_vid.get("enabled", False))
        ending_path = str(ending_vid.get("path", ""))
        
        if hasattr(self, "ending_video_enabled_check"):
            self.ending_video_enabled_check.setChecked(ending_enabled)
        if hasattr(self, "main_ending_video_enabled_check"):
            self.main_ending_video_enabled_check.setChecked(ending_enabled)
            
        if hasattr(self, "ending_video_path_edit"):
            self.ending_video_path_edit.setText(ending_path)
        if hasattr(self, "main_ending_video_path_edit"):
            self.main_ending_video_path_edit.setText(ending_path)

        self.output_dir_edit.setText(self.settings["outputDirectory"])
        self.output_folder_quick_edit.setText(self.settings["outputDirectory"])
        self.draft_dir_edit.setText(self.settings["draftRoot"])
        self.region_x_spin.setValue(int(self.settings["subtitleRegion"]["x"]))
        self.region_y_spin.setValue(int(self.settings["subtitleRegion"]["y"]))
        self.region_w_spin.setValue(int(self.settings["subtitleRegion"]["w"]))
        self.region_h_spin.setValue(int(self.settings["subtitleRegion"]["h"]))
        self.font_size_slider.setValue(int(self.settings["subtitlePreset"]["fontSize"]))
        self.blur_slider.setValue(
            int(self.settings["subtitlePreset"]["cleanupBlurStrength"])
        )
        self.bottom_offset_slider.setValue(
            int(self.settings["subtitlePreset"]["bottomOffset"])
        )
        watermark = self.settings.setdefault("watermark", {})
        self.watermark_enabled_check.setChecked(bool(watermark.get("enabled", False)))
        self.watermark_path_edit.setText(watermark.get("path", ""))
        self._set_combo_value(self.watermark_position_combo, watermark.get("position", "top-right"))
        self.watermark_scale_slider.setValue(int(watermark.get("scale", 0.15) * 100))
        self.watermark_opacity_slider.setValue(int(watermark.get("opacity", 1.0) * 100))
        self.watermark_remove_bg_check.setChecked(bool(watermark.get("removeBg", False)))
        for widget in widgets:
            if widget is not None:
                widget.blockSignals(False)
        self.font_size_value.setText(f"{self.settings['subtitlePreset']['fontSize']}px")
        self.blur_value.setText(
            f"{self.settings['subtitlePreset']['cleanupBlurStrength']}%"
        )
        self.bottom_offset_value.setText(
            f"{self.settings['subtitlePreset']['bottomOffset']}px"
        )
        if hasattr(self, "watermark_scale_value"):
            self.watermark_scale_value.setText(
                f"{int(round(float(watermark.get('scale', 0.15)) * 100))}%"
            )
        if hasattr(self, "watermark_opacity_value"):
            self.watermark_opacity_value.setText(
                f"{int(round(float(watermark.get('opacity', 1.0)) * 100))}%"
            )
        default_voice_status_label = getattr(self, "default_voice_status_label", None)
        if default_voice_status_label is not None:
            default_voice_status_label.setText(
                f"Giọng mặc định: {self._format_voice_label(default_voice)}"
            )



