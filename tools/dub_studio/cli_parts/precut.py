from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from .common import run, get_video_meta

logger = logging.getLogger("dub_studio.precut")

def merge_intervals(intervals: list[dict[str, float]]) -> list[dict[str, float]]:
    """
    Merge overlapping or intersecting intervals.
    Example: [{start: 10, end: 30}, {start: 20, end: 40}] -> [{start: 10, end: 40}]
    """
    if not intervals:
        return []
    
    # Filter valid dicts with float start and end keys
    valid_intervals = []
    for item in intervals:
        try:
            start = float(item.get("start", 0.0))
            end = float(item.get("end", 0.0))
            valid_intervals.append({"start": start, "end": end})
        except (ValueError, TypeError):
            continue
            
    # Sort intervals by start time
    sorted_intervals = sorted(valid_intervals, key=lambda x: x["start"])
    
    merged: list[dict[str, float]] = []
    for interval in sorted_intervals:
        if not merged:
            merged.append(interval)
        else:
            last = merged[-1]
            if interval["start"] <= last["end"]:
                # Intersecting or adjacent, merge
                last["end"] = max(last["end"], interval["end"])
            else:
                merged.append(interval)
                
    return merged

def validate_interval(start: float, end: float, max_duration: float) -> str | None:
    """
    Validate if start and end times are correct.
    Returns error message if invalid, or None if valid.
    """
    if start < 0.0 or end < 0.0:
        return "Thời gian không được âm."
    if start >= end:
        return "Thời gian bắt đầu phải nhỏ hơn thời gian kết thúc."
    if start > max_duration or end > max_duration:
        return f"Thời gian vượt quá thời lượng video ({max_duration:.2f}s)."
    return None

def precut_video(input_path: Path | str, excluded_ranges: list[dict[str, float]], output_path: Path | str) -> Path:
    """
    Pre-cuts a video by excluding certain time ranges and stitching the kept parts together.
    If no ranges are kept or there are no exclusions, behaves appropriately.
    """
    input_path = Path(input_path)
    output_path = Path(output_path)
    
    if not input_path.exists():
        raise FileNotFoundError(f"Không tìm thấy video gốc: {input_path}")
        
    # Get total video duration in seconds
    meta = get_video_meta(input_path)
    total_duration = float(meta.get("durationMs", 0) or 0) / 1000.0
    if total_duration <= 0:
        total_duration = 10800.0 
        
    has_audio = bool(meta.get("hasAudio", False))
    
    # Merge excluded ranges first
    merged_excluded = merge_intervals(excluded_ranges)
    
    # Calculate kept segments
    kept_segments: list[tuple[float, float]] = []
    current_time = 0.0
    
    for range_item in merged_excluded:
        start = float(range_item["start"])
        end = float(range_item["end"])
        
        # Clamp times to total video duration
        start = min(start, total_duration)
        end = min(end, total_duration)
        
        if start > current_time:
            # We keep this part
            kept_segments.append((current_time, start))
        current_time = max(current_time, end)
        
    if current_time < total_duration:
        kept_segments.append((current_time, total_duration))
        
    # Clean up kept segments that are too short (less than 0.1s)
    kept_segments = [seg for seg in kept_segments if (seg[1] - seg[0]) >= 0.1]
    
    if not kept_segments:
        logger.warning(f"Tất cả thời lượng video '{input_path.name}' bị loại bỏ theo khoảng đã chọn. Giữ nguyên video gốc để tiếp tục.")
        import shutil
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(input_path, output_path)
        return output_path
        
    # If no segments were actually cut (i.e. we keep the whole duration)
    # just copy the file or return the original
    if len(kept_segments) == 1 and kept_segments[0][0] <= 0.05 and abs(kept_segments[0][1] - total_duration) <= 0.1:
        import shutil
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(input_path, output_path)
        logger.info(f"Không có khoảng loại bỏ thực tế nào, sao chép sang {output_path}")
        return output_path
        
    # Process cutting & stitching via FFmpeg using a single input trim filter complex
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    filter_parts = []
    for i, seg in enumerate(kept_segments):
        filter_parts.append(f"[0:v]trim=start={seg[0]:.3f}:end={seg[1]:.3f},setpts=PTS-STARTPTS[v{i}];")
        if has_audio:
            filter_parts.append(f"[0:a]atrim=start={seg[0]:.3f}:end={seg[1]:.3f},asetpts=PTS-STARTPTS[a{i}];")
            
    concat_inputs = ""
    for i in range(len(kept_segments)):
        if has_audio:
            concat_inputs += f"[v{i}][a{i}]"
        else:
            concat_inputs += f"[v{i}]"
            
    a_param = "1" if has_audio else "0"
    if has_audio:
        filter_parts.append(f"{concat_inputs}concat=n={len(kept_segments)}:v=1:a=1[outv][outa]")
    else:
        filter_parts.append(f"{concat_inputs}concat=n={len(kept_segments)}:v=1:a=0[outv]")
        
    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-filter_complex", "".join(filter_parts),
        "-map", "[outv]"
    ]
    if has_audio:
        cmd.extend(["-map", "[outa]"])
        
    cmd.extend([
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23"
    ])
    if has_audio:
        cmd.extend(["-c:a", "aac"])
        
    cmd.append(str(output_path))
    
    logger.info(f"Running precut FFmpeg command for {input_path} -> {output_path}")
    run(cmd)
    
    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError(f"FFmpeg precut failed to create output file: {output_path}")
        
    return output_path
