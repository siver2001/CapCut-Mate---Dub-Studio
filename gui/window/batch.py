from __future__ import annotations

import copy
import shutil
from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QFileDialog,
    QMessageBox,
)

from gui.config import DEFAULT_OUTPUT_DIR
from gui.utils import repair_mojibake_text


class _BatchItem:
    """Lightweight data holder for a single video in the batch queue."""

    __slots__ = (
        "input_path",
        "status",
        "detail_status",
        "job_id",
        "progress",
        "error",
        "output_path",
    )

    def __init__(self, input_path: str) -> None:
        self.input_path: str = input_path
        self.status: str = "pending"  # pending | analyzing | rendering | done | error
        self.detail_status: str = "⏳ Chờ xử lý"
        self.job_id: str | None = None
        self.progress: float = 0.0
        self.error: str = ""
        self.output_path: str = ""


class WindowBatchMixin:
    """Mixin providing batch / bulk-processing capabilities for DubStudioWindow."""

    _BATCH_STEP_LABELS: dict[str, str] = {
        "prepare": "Chuẩn bị",
        "input": "Chuẩn bị video",
        "analyze": "Đang phân tích",
        "audio_extract": "Đang tách audio",
        "transcribe": "Đang chép lời",
        "diarize": "Đang nhận diện speaker",
        "translate": "Đang dịch phụ đề",
        "subtitle": "Đang tạo subtitle",
        "timeline": "Đang dựng timeline",
        "voice": "Đang gán giọng",
        "tts": "Đang lồng tiếng",
        "tts_mix": "Đang ghép giọng đọc",
        "mix_audio": "Đang trộn audio",
        "background_prepare": "Đang tách âm nền",
        "render": "Đang render",
        "encode": "Đang xuất video",
        "finalize": "Đang hoàn tất",
        "export": "Đang xuất file",
    }

    # ── public state ─────────────────────────────────────────────────
    def _init_batch_state(self) -> None:
        self._batch_queue: list[_BatchItem] = []
        self._batch_running: bool = False
        self._batch_current_index: int = -1
        self._batch_phase: str = ""  # "analyze" | "render"
        self._batch_output_dir: str = ""
        self._batch_cancelled: bool = False

    # ── queue management ─────────────────────────────────────────────
    def batch_add_videos(self) -> None:
        """Open a multi-file dialog and add videos to the batch queue."""
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Chọn nhiều video để xử lý hàng loạt",
            "",
            "Video (*.mp4 *.mov *.mkv *.avi *.m4v *.webm)",
        )
        if not paths:
            return
        last_added_index = -1
        for p in paths:
            if any(item.input_path == p for item in self._batch_queue):
                continue
            self._batch_queue.append(_BatchItem(p))
            last_added_index = len(self._batch_queue) - 1
        self._refresh_batch_ui()
        if last_added_index >= 0 and hasattr(self, "batch_table"):
            self.batch_table.selectRow(last_added_index)
            self.show_source_video_preview(
                self._batch_queue[last_added_index].input_path,
                switch_to_preview_tab=True,
            )

    def batch_remove_selected(self) -> None:
        """Remove the currently-selected row from the batch queue."""
        if not hasattr(self, "batch_table"):
            return
        row = self.batch_table.currentRow()
        if 0 <= row < len(self._batch_queue):
            self._batch_queue.pop(row)
            self._refresh_batch_ui()

    def batch_clear_all(self) -> None:
        """Clear the entire batch queue."""
        if self._batch_running:
            QMessageBox.warning(
                self,
                "Đang xử lý hàng loạt",
                "Hãy dừng batch đang chạy trước khi xóa danh sách.",
            )
            return
        self._batch_queue.clear()
        self._refresh_batch_ui()

    def batch_move_up(self) -> None:
        """Move the selected item up in the queue."""
        if not hasattr(self, "batch_table"):
            return
        row = self.batch_table.currentRow()
        if row > 0:
            self._batch_queue[row], self._batch_queue[row - 1] = (
                self._batch_queue[row - 1],
                self._batch_queue[row],
            )
            self._refresh_batch_ui()
            self.batch_table.selectRow(row - 1)

    def batch_move_down(self) -> None:
        """Move the selected item down in the queue."""
        if not hasattr(self, "batch_table"):
            return
        row = self.batch_table.currentRow()
        if 0 <= row < len(self._batch_queue) - 1:
            self._batch_queue[row], self._batch_queue[row + 1] = (
                self._batch_queue[row + 1],
                self._batch_queue[row],
            )
            self._refresh_batch_ui()
            self.batch_table.selectRow(row + 1)

    # ── output directory ─────────────────────────────────────────────
    def batch_choose_output_dir(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            "Chọn thư mục xuất cho batch",
            self._batch_output_dir or self.output_dir_edit.text().strip() or "",
        )
        if selected:
            self._batch_output_dir = selected
            if hasattr(self, "batch_output_dir_edit"):
                self.batch_output_dir_edit.setText(selected)
            # Sync with the global settings so the user isn't confused by other tabs
            if hasattr(self, "output_dir_edit"):
                self.output_dir_edit.setText(selected)
            if hasattr(self, "output_folder_quick_edit"):
                self.output_folder_quick_edit.setText(selected)
            self.settings["outputDirectory"] = selected

    # ── start / stop batch ───────────────────────────────────────────
    def batch_start(self) -> None:
        """Begin sequential batch processing of all queued videos."""
        if self._batch_running:
            QMessageBox.information(
                self, "Batch đang chạy", "Batch đã đang xử lý, vui lòng đợi."
            )
            return

        pending_items = [
            item for item in self._batch_queue if item.status in ("pending", "error")
        ]
        if not pending_items:
            QMessageBox.information(
                self,
                "Không có video",
                "Hãy thêm video vào danh sách batch trước khi bắt đầu.",
            )
            return

        output_dir = (
            self._batch_output_dir.strip()
            or (
                hasattr(self, "batch_output_dir_edit")
                and self.batch_output_dir_edit.text().strip()
            )
        )
        if not output_dir:
            QMessageBox.warning(
                self,
                "Thiếu thông tin",
                "Vui lòng chọn 'Thư mục xuất batch' để lưu các video sau khi render.",
            )
            return

        self._batch_output_dir = str(output_dir)
        Path(self._batch_output_dir).mkdir(parents=True, exist_ok=True)

        # Read the current shared settings so all videos use the same config
        self.read_settings_from_widgets()

        # Reset pending items
        for item in self._batch_queue:
            if item.status in ("pending", "error"):
                item.status = "pending"
                item.detail_status = "⏳ Chờ xử lý"
                item.progress = 0.0
                item.error = ""
                item.output_path = ""
                item.job_id = None

        self._batch_running = True
        self._batch_cancelled = False
        self._batch_current_index = -1
        
        pending_count = len(pending_items)
        total_count = len(self._batch_queue)
        
        if pending_count == total_count:
            self._update_batch_log(f"▶ Bắt đầu chạy batch cho {total_count} video...")
        else:
            self._update_batch_log(f"▶ Tiếp tục chạy batch cho {pending_count} video còn lại...")
        self._update_batch_log(
            "  • Mỗi video sẽ tự chạy đủ chu trình: phân tích → tạo subtitle → lồng tiếng → render → xuất file."
        )

        self._refresh_batch_ui()
        self._batch_process_next()

    def batch_stop(self) -> None:
        """Cancel the currently running batch processing."""
        if not self._batch_running:
            return
        self._batch_cancelled = True
        self.controller.cancel_active_job()
        self._batch_running = False

        # Reset the currently interrupted item back to pending so it can be retried
        if 0 <= self._batch_current_index < len(self._batch_queue):
            current_item = self._batch_queue[self._batch_current_index]
            if current_item.status in ("analyzing", "rendering"):
                current_item.status = "pending"
                current_item.detail_status = "⏳ Chờ xử lý"
                current_item.progress = 0.0
                current_item.job_id = None
        self._batch_current_index = -1

        self._refresh_batch_ui()
        self._update_batch_log("⏸ Batch đã bị dừng. Bấm 'Bắt đầu batch' để chạy tiếp các video còn lại (video đang xử lý dở sẽ được làm lại từ đầu).")

    # ── internal: sequential processing ──────────────────────────────
    def _batch_process_next(self) -> None:
        """Find the next pending item and start its analysis."""
        if self._batch_cancelled or not self._batch_running:
            self._batch_finalize()
            return

        next_index = -1
        for i, item in enumerate(self._batch_queue):
            if item.status == "pending":
                next_index = i
                break

        if next_index < 0:
            self._batch_finalize()
            return

        self._batch_current_index = next_index
        item = self._batch_queue[next_index]
        item.status = "analyzing"
        item.detail_status = "🔍 Đang chuẩn bị phân tích..."
        item.progress = 0.0
        self._refresh_batch_ui()
        self._update_batch_log(
            f"[{next_index + 1}/{len(self._batch_queue)}] Bắt đầu phân tích: {Path(item.input_path).name}"
        )

        try:
            input_path = Path(item.input_path)
            if not input_path.exists():
                raise RuntimeError(f"Không tìm thấy file: {item.input_path}")

            job_id = self.controller.analyze_video(
                str(input_path),
                {"targetLanguage": self.settings.get("targetLanguage", "vi")},
            )
            item.job_id = job_id
        except Exception as exc:
            item.status = "error"
            item.error = str(exc)
            self._update_batch_log(f"  ✗ Lỗi phân tích: {exc}")
            self._refresh_batch_ui()
            # Continue to next item after a cooldown delay
            QTimer.singleShot(5000, self._batch_process_next)

    def _batch_on_analysis_ready(self, job_id: str, analysis: dict[str, Any]) -> None:
        """Called when a batch item's analysis completes → start rendering."""
        if not self._batch_running:
            return

        item = self._find_batch_item_by_job_id(job_id)
        if item is None:
            return

        item.status = "rendering"
        item.detail_status = "🎬 Đang tạo subtitle + lồng tiếng..."
        item.progress = 0.5
        self._refresh_batch_ui()
        self._update_batch_log(
            f"  ✓ Phân tích xong, bắt đầu tạo subtitle + lồng tiếng + render: {Path(item.input_path).name}"
        )

        try:
            # Store analysis on the controller job
            job = self.controller.jobs.get(job_id)
            if not job or not job.get("analysis"):
                raise RuntimeError("Analysis data missing.")

            # Apply the shared settings as overrides
            overrides = self._batch_build_overrides(analysis)
            self.controller.update_analysis_config(job_id, overrides)

            # Prepare render options using the shared settings
            render_options = self._batch_build_render_options(analysis)
            self.controller.render_video(job_id, render_options)
        except Exception as exc:
            item.status = "error"
            item.error = str(exc)
            self._update_batch_log(f"  ✗ Lỗi render: {exc}")
            self._refresh_batch_ui()
            QTimer.singleShot(5000, self._batch_process_next)

    def _batch_on_render_ready(self, job_id: str, payload: dict[str, Any]) -> None:
        """Called when a batch item's render completes → export & proceed."""
        if not self._batch_running:
            return

        item = self._find_batch_item_by_job_id(job_id)
        if item is None:
            return

        item.detail_status = "📦 Đang xuất file..."
        self._refresh_batch_ui()

        # Export the rendered video to the batch output directory
        source_video = (
            payload.get("previewVideoPath")
            or payload.get("outputVideoPath")
            or ""
        )
        if source_video and Path(source_video).exists():
            output_dir = Path(self._batch_output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            input_stem = Path(item.input_path).stem
            extension = Path(source_video).suffix or ".mp4"
            dest = output_dir / f"{input_stem}_dubbed{extension}"
            # Avoid overwriting
            counter = 1
            while dest.exists():
                dest = output_dir / f"{input_stem}_dubbed_{counter}{extension}"
                counter += 1
            try:
                shutil.copy2(source_video, dest)
                item.output_path = str(dest)
                self._update_batch_log(
                    f"  ✓ Xuất file: {dest.name}"
                )
            except Exception as exc:
                self._update_batch_log(f"  ⚠ Không thể copy output: {exc}")
                item.output_path = source_video
        else:
            item.output_path = source_video or ""

        item.status = "done"
        item.detail_status = "✅ Hoàn tất"
        item.progress = 1.0
        self._refresh_batch_ui()

        # Move to the next item with a cooldown gap
        QTimer.singleShot(5000, self._batch_process_next)

    def _batch_on_job_failed(self, job_id: str, message: str) -> None:
        """Called when a batch item fails."""
        if not self._batch_running:
            return

        item = self._find_batch_item_by_job_id(job_id)
        if item is None:
            return

        item.status = "error"
        item.detail_status = "❌ Lỗi"
        item.error = message
        item.progress = 0.0
        self._update_batch_log(f"  ✗ Lỗi: {repair_mojibake_text(message)}")
        self._refresh_batch_ui()

        # Continue to next item
        QTimer.singleShot(5000, self._batch_process_next)

    def _batch_on_status_changed(self, job_id: str, payload: dict[str, Any]) -> None:
        """Update progress for the currently running batch item."""
        if not self._batch_running:
            return

        item = self._find_batch_item_by_job_id(job_id)
        if item is None:
            return

        raw_progress = float(payload.get("progress") or 0)
        phase = str(payload.get("phase") or "").strip().lower()
        step = str(payload.get("step") or "").strip().lower()
        item.detail_status = self._describe_batch_step(item.status, phase=phase, step=step)
        if item.status == "analyzing":
            item.progress = raw_progress * 0.5
        elif item.status == "rendering":
            item.progress = 0.5 + raw_progress * 0.5
        self._refresh_batch_ui()

    # ── helpers ──────────────────────────────────────────────────────
    def _find_batch_item_by_job_id(self, job_id: str) -> _BatchItem | None:
        for item in self._batch_queue:
            if item.job_id == job_id:
                return item
        return None

    def _current_batch_item(self) -> _BatchItem | None:
        if 0 <= self._batch_current_index < len(self._batch_queue):
            return self._batch_queue[self._batch_current_index]
        return None

    def _describe_batch_step(self, batch_status: str, *, phase: str, step: str) -> str:
        base_label = self._BATCH_STEP_LABELS.get(step)
        if base_label:
            if batch_status == "analyzing":
                return f"🔍 {base_label}"
            if batch_status == "rendering":
                return f"🎬 {base_label}"
            return base_label
        if batch_status == "analyzing":
            return "🔍 Đang phân tích..."
        if batch_status == "rendering":
            if phase == "render":
                return "🎬 Đang render..."
            return "🎬 Đang xử lý..."
        if batch_status == "done":
            return "✅ Hoàn tất"
        if batch_status == "error":
            return "❌ Lỗi"
        return "⏳ Chờ xử lý"

    def _batch_overall_progress(self) -> float:
        total = len(self._batch_queue)
        if total <= 0:
            return 0.0
        completed_units = 0.0
        for item in self._batch_queue:
            completed_units += max(0.0, min(float(item.progress), 1.0))
        return max(0.0, min(completed_units / total, 1.0))

    def _is_batch_job(self, job_id: str) -> bool:
        return self._batch_running and self._find_batch_item_by_job_id(job_id) is not None

    def _batch_build_overrides(self, analysis: dict[str, Any]) -> dict[str, Any]:
        """Build analysis overrides from the shared settings."""
        overrides = self.current_analysis_overrides()
        if self.settings.get("sourceLanguage") == "auto":
            overrides["sourceLanguage"] = ""
        if analysis and "subtitleRegion" in analysis:
            overrides["subtitleRegion"] = copy.deepcopy(analysis["subtitleRegion"])
        return overrides

    def _batch_build_render_options(self, analysis: dict[str, Any]) -> dict[str, Any]:
        """Build render options from the shared settings for a batch item."""
        options = self.current_render_options()
        
        effective_source_language = (
            analysis.get("sourceLanguage")
            if self.settings.get("sourceLanguage") == "auto"
            else self.settings.get("sourceLanguage")
        )
        options["sourceLanguage"] = effective_source_language or ""
        
        if analysis and "subtitleRegion" in analysis:
            options["subtitleRegion"] = copy.deepcopy(analysis["subtitleRegion"])
            
        if self._batch_output_dir:
            options["outputDirectory"] = self._batch_output_dir
            
        return options

    def _batch_finalize(self) -> None:
        """Called when the batch queue is fully processed (or cancelled)."""
        self._batch_running = False
        self._batch_current_index = -1
        self._refresh_batch_ui()

        done_count = sum(1 for item in self._batch_queue if item.status == "done")
        error_count = sum(1 for item in self._batch_queue if item.status == "error")
        total = len(self._batch_queue)

        summary = (
            f"Batch hoàn tất: {done_count}/{total} thành công"
            + (f", {error_count} lỗi" if error_count else "")
            + "."
        )
        self._update_batch_log(summary)

        if not self._batch_cancelled:
            QMessageBox.information(
                self,
                "Batch hoàn tất",
                repair_mojibake_text(
                    f"Đã xử lý xong {done_count}/{total} video.\n"
                    + (f"{error_count} video gặp lỗi.\n" if error_count else "")
                    + f"\nThư mục output: {self._batch_output_dir}"
                ),
            )

    # ── UI refresh ───────────────────────────────────────────────────
    def _refresh_batch_ui(self) -> None:
        """Update the batch tab table and controls."""
        if not hasattr(self, "batch_table"):
            return

        from PyQt6.QtWidgets import QTableWidgetItem

        table = self.batch_table
        table.blockSignals(True)
        table.setRowCount(len(self._batch_queue))
        for row, item in enumerate(self._batch_queue):
            name = Path(item.input_path).name
            status_map = {
                "pending": "⏳ Chờ xử lý",
                "analyzing": "🔍 Đang phân tích...",
                "rendering": "🎬 Đang render...",
                "done": "✅ Hoàn tất",
                "error": "❌ Lỗi",
            }
            status_text = item.detail_status or status_map.get(item.status, item.status)
            progress_text = f"{int(item.progress * 100)}%"
            output_text = Path(item.output_path).name if item.output_path else ""

            for col, value in enumerate([
                str(row + 1),
                name,
                status_text,
                progress_text,
                output_text,
            ]):
                cell = QTableWidgetItem(value)
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if item.status == "done":
                    cell.setForeground(Qt.GlobalColor.green)
                elif item.status == "error":
                    cell.setForeground(Qt.GlobalColor.red)
                    if col == 2:
                        cell.setToolTip(item.error)
                table.setItem(row, col, cell)
        table.blockSignals(False)

        # Update overall batch progress bar
        if hasattr(self, "batch_progress_bar"):
            overall = self._batch_overall_progress()
            overall_percent = int(round(overall * 100))
            self.batch_progress_bar.setValue(overall_percent)
            self.batch_progress_bar.setFormat(f"Tổng batch: {overall_percent}%")

        # Update batch status label
        if hasattr(self, "batch_status_label"):
            done = sum(1 for item in self._batch_queue if item.status == "done")
            errors = sum(1 for item in self._batch_queue if item.status == "error")
            total = len(self._batch_queue)
            if self._batch_running:
                current = self._batch_current_index + 1
                current_item = self._current_batch_item()
                current_progress = (
                    int(round(float(current_item.progress) * 100))
                    if current_item is not None
                    else 0
                )
                self.batch_status_label.setText(
                    repair_mojibake_text(
                        f"Đang xử lý: {current}/{total} | Video hiện tại: {current_progress}% | Xong: {done} | Lỗi: {errors}"
                    )
                )
            elif total > 0:
                self.batch_status_label.setText(
                    repair_mojibake_text(
                        f"Tổng: {total} video | Xong: {done} | Lỗi: {errors}"
                    )
                )
            else:
                self.batch_status_label.setText("Chưa có video trong danh sách batch.")

        # Button states
        if hasattr(self, "batch_start_btn"):
            self.batch_start_btn.setEnabled(
                not self._batch_running and len(self._batch_queue) > 0
            )
        if hasattr(self, "batch_stop_btn"):
            self.batch_stop_btn.setEnabled(self._batch_running)
        if hasattr(self, "batch_add_btn"):
            self.batch_add_btn.setEnabled(not self._batch_running)
        if hasattr(self, "batch_remove_btn"):
            self.batch_remove_btn.setEnabled(
                not self._batch_running and len(self._batch_queue) > 0
            )
        if hasattr(self, "batch_clear_btn"):
            self.batch_clear_btn.setEnabled(
                not self._batch_running and len(self._batch_queue) > 0
            )
        if hasattr(self, "batch_up_btn"):
            self.batch_up_btn.setEnabled(not self._batch_running)
        if hasattr(self, "batch_down_btn"):
            self.batch_down_btn.setEnabled(not self._batch_running)

    def batch_preview_selected(self) -> None:
        if not hasattr(self, "batch_table"):
            return
        row = self.batch_table.currentRow()
        if 0 <= row < len(self._batch_queue):
            self.show_source_video_preview(
                self._batch_queue[row].input_path,
                switch_to_preview_tab=False,
            )

    def on_batch_table_double_clicked(self, item) -> None:
        if not item:
            return
        row = item.row()
        if 0 <= row < len(self._batch_queue):
            batch_item = self._batch_queue[row]
            if batch_item.status == "error" and batch_item.error:
                QMessageBox.critical(
                    self,
                    "Chi tiết lỗi",
                    f"Video: {Path(batch_item.input_path).name}\n\nLỗi:\n{repair_mojibake_text(batch_item.error)}",
                )

    def _update_batch_log(self, message: str) -> None:
        """Append a message to the batch log box."""
        if not hasattr(self, "batch_log_box"):
            return
        existing_lines = self.batch_log_box.toPlainText().splitlines()
        existing_lines.append(repair_mojibake_text(message))
        self.batch_log_box.setPlainText("\n".join(existing_lines[-40:]))
        scroll_bar = self.batch_log_box.verticalScrollBar()
        scroll_bar.setValue(scroll_bar.maximum())
