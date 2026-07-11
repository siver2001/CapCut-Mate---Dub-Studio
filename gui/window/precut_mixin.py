from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path
from typing import Any
from PyQt6.QtCore import Qt, QTime
from PyQt6.QtWidgets import QTableWidgetItem, QMessageBox, QHeaderView

from tools.dub_studio.cli_parts.precut import merge_intervals, validate_interval, precut_video
from gui.utils import repair_mojibake_text

logger = logging.getLogger("dub_studio.precut_mixin")

class WindowPrecutMixin:
    """Mixin for video excluded ranges (precutting) logic in DubStudioWindow."""

    def sync_precut_video_table(self) -> None:
        """Synchronize precut video list table with the batch queue."""
        if not hasattr(self, "precut_video_table") or self.precut_video_table is None:
            return

        table = self.precut_video_table
        table.blockSignals(True)
        table.setRowCount(len(self._batch_queue))
        for row, item in enumerate(self._batch_queue):
            name = Path(item.input_path).name
            for col, value in enumerate([str(row + 1), name]):
                cell = QTableWidgetItem(value)
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                table.setItem(row, col, cell)
        table.blockSignals(False)

    def on_precut_video_selected(self) -> None:
        """Callback when a video is selected in the left list."""
        row = self.precut_video_table.currentRow()
        if row < 0 or row >= len(self._batch_queue):
            self.precut_ranges_table.setRowCount(0)
            return

        item = self._batch_queue[row]
        # Load video into player
        if item.input_path and os.path.exists(item.input_path):
            self.precut_player.load_video(item.input_path)
            self.precut_player.play()
            
        self.refresh_precut_ranges_table()

    def refresh_precut_ranges_table(self) -> None:
        """Reload the excluded ranges table for the currently selected video."""
        row = self.precut_video_table.currentRow()
        if row < 0 or row >= len(self._batch_queue):
            self.precut_ranges_table.setRowCount(0)
            return

        item = self._batch_queue[row]
        table = self.precut_ranges_table
        table.blockSignals(True)
        
        # Sort and merge ranges
        item.excluded_ranges = merge_intervals(item.excluded_ranges)
        
        table.setRowCount(len(item.excluded_ranges))
        for r_idx, range_item in enumerate(item.excluded_ranges):
            start = range_item["start"]
            end = range_item["end"]
            
            # Format to HH:MM:SS
            start_str = self._format_seconds_to_hms(start)
            end_str = self._format_seconds_to_hms(end)
            
            for col, val in enumerate([start_str, end_str]):
                cell = QTableWidgetItem(val)
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                table.setItem(r_idx, col, cell)
                
        table.blockSignals(False)

    def on_precut_set_start(self) -> None:
        """Capture player position as the start time."""
        pos_ms = self.precut_player._player.position()
        pos_sec = max(0.0, pos_ms / 1000.0)
        qtime = self._seconds_to_qtime(pos_sec)
        self.precut_start_time.setTime(qtime)

    def on_precut_set_end(self) -> None:
        """Capture player position as the end time."""
        pos_ms = self.precut_player._player.position()
        pos_sec = max(0.0, pos_ms / 1000.0)
        qtime = self._seconds_to_qtime(pos_sec)
        self.precut_end_time.setTime(qtime)

    def on_precut_add_range(self) -> None:
        """Add excluded range to the selected video."""
        row = self.precut_video_table.currentRow()
        if row < 0 or row >= len(self._batch_queue):
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng chọn video trước khi thêm khoảng loại bỏ.")
            return

        item = self._batch_queue[row]
        
        start_sec = self._qtime_to_seconds(self.precut_start_time.time())
        end_sec = self._qtime_to_seconds(self.precut_end_time.time())
        
        meta = get_video_meta(item.input_path)
        total_duration = float(meta.get("durationMs", 0) or 0) / 1000.0
        if total_duration <= 0:
            total_duration = 10800.0
            
        error = validate_interval(start_sec, end_sec, total_duration)
        if error:
            QMessageBox.warning(self, "Lỗi dữ liệu", error)
            return
            
        item.excluded_ranges.append({"start": start_sec, "end": end_sec})
        self.refresh_precut_ranges_table()
        self._update_batch_log(f"Đã thêm khoảng loại bỏ: {self._format_seconds_to_hms(start_sec)} -> {self._format_seconds_to_hms(end_sec)} cho video {Path(item.input_path).name}")

    def on_precut_edit_range(self) -> None:
        """Edit the selected excluded range."""
        row = self.precut_video_table.currentRow()
        if row < 0 or row >= len(self._batch_queue):
            return

        range_row = self.precut_ranges_table.currentRow()
        if range_row < 0:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng chọn khoảng cần sửa đổi trong bảng.")
            return

        item = self._batch_queue[row]
        
        selected_range = item.excluded_ranges[range_row]
        start_input = self._qtime_to_seconds(self.precut_start_time.time())
        end_input = self._qtime_to_seconds(self.precut_end_time.time())
        
        if abs(selected_range["start"] - start_input) < 0.1 and abs(selected_range["end"] - end_input) < 0.1:
            # Inputs are already populated, prompt user to edit and click save
            QMessageBox.information(self, "Thông tin", "Hãy chỉnh sửa Giờ/Phút/Giây bên dưới trình phát rồi nhấn nút 'Sửa khoảng' một lần nữa để lưu lại.")
            return
            
        meta = get_video_meta(item.input_path)
        total_duration = float(meta.get("durationMs", 0) or 0) / 1000.0
        if total_duration <= 0:
            total_duration = 10800.0
            
        error = validate_interval(start_input, end_input, total_duration)
        if error:
            QMessageBox.warning(self, "Lỗi dữ liệu", error)
            return
            
        item.excluded_ranges[range_row] = {"start": start_input, "end": end_input}
        self.refresh_precut_ranges_table()
        self._update_batch_log(f"Đã sửa khoảng loại bỏ thành: {self._format_seconds_to_hms(start_input)} -> {self._format_seconds_to_hms(end_input)}")

    def on_precut_delete_range(self) -> None:
        """Delete the selected excluded range."""
        row = self.precut_video_table.currentRow()
        if row < 0 or row >= len(self._batch_queue):
            return

        range_row = self.precut_ranges_table.currentRow()
        if range_row < 0:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng chọn khoảng cần xóa.")
            return

        item = self._batch_queue[row]
        removed = item.excluded_ranges.pop(range_row)
        self.refresh_precut_ranges_table()
        self._update_batch_log(f"Đã xóa khoảng loại bỏ: {self._format_seconds_to_hms(removed['start'])} -> {self._format_seconds_to_hms(removed['end'])}")

    def on_precut_clear_ranges(self) -> None:
        """Clear all excluded ranges for the selected video."""
        row = self.precut_video_table.currentRow()
        if row < 0 or row >= len(self._batch_queue):
            return

        item = self._batch_queue[row]
        if not item.excluded_ranges:
            return
            
        reply = QMessageBox.question(
            self,
            "Xác nhận",
            f"Bạn có chắc chắn muốn xóa toàn bộ các khoảng loại bỏ của video {Path(item.input_path).name}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            item.excluded_ranges.clear()
            self.refresh_precut_ranges_table()
            self._update_batch_log("Đã xóa toàn bộ khoảng loại bỏ.")

    def on_precut_preview_cut(self) -> None:
        """Cut the video and play it in the preview player to preview changes."""
        row = self.precut_video_table.currentRow()
        if row < 0 or row >= len(self._batch_queue):
            return

        item = self._batch_queue[row]
        if not item.excluded_ranges:
            QMessageBox.information(self, "Thông tin", "Video này chưa thiết lập khoảng loại bỏ nào.")
            return
            
        temp_preview = Path("temp/precut_preview_temp.mp4")
        temp_preview.parent.mkdir(parents=True, exist_ok=True)
        
        self._update_batch_log(f"Đang chuẩn bị cắt thử xem trước cho {Path(item.input_path).name}...")
        
        try:
            precut_video(item.input_path, item.excluded_ranges, temp_preview)
            if temp_preview.exists():
                self.precut_player.load_video(str(temp_preview))
                self.precut_player.play()
                self._update_batch_log("Đã nạp video cắt thử xem trước thành công.")
        except Exception as exc:
            QMessageBox.critical(self, "Lỗi cắt video", f"Cắt thử thất bại: {exc}")

    def on_precut_save_config(self) -> None:
        """Save configuration metadata for excluded ranges."""
        config_path = Path("temp/precut_configurations.json")
        data = []
        for item in self._batch_queue:
            data.append({
                "videoPath": item.input_path,
                "excludedRanges": item.excluded_ranges
            })
        try:
            import json
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            QMessageBox.information(self, "Thành công", f"Đã lưu cấu hình loại bỏ của {len(data)} video thành công!")
        except Exception as exc:
            QMessageBox.critical(self, "Lỗi", f"Không thể ghi cấu hình: {exc}")

    def load_precut_configurations(self) -> None:
        """Load configuration metadata if any exists."""
        config_path = Path("temp/precut_configurations.json")
        if not config_path.exists():
            return
        try:
            import json
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            ranges_by_path = {item["videoPath"]: item["excludedRanges"] for item in data if "videoPath" in item}
            
            for item in self._batch_queue:
                if item.input_path in ranges_by_path:
                    item.excluded_ranges = ranges_by_path[item.input_path]
            
            self.refresh_precut_ranges_table()
        except Exception as exc:
            logger.error(f"Error loading precut configurations: {exc}")

    # Helper functions
    def _format_seconds_to_hms(self, seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    def _seconds_to_qtime(self, seconds: float) -> QTime:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds - int(seconds)) * 1000)
        return QTime(h, m, s, ms)

    def _qtime_to_seconds(self, qtime: QTime) -> float:
        return qtime.hour() * 3600 + qtime.minute() * 60 + qtime.second() + qtime.msec() / 1000.0
