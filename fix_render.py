import sys

with open('tools/dub_studio/cli_parts/render.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = """    dynamic_regions = [region for region in (dynamic_regions or []) if int(region.get("w", 0)) > 0 and int(region.get("h", 0)) > 0]

    # When there are too many dynamic regions, the filter_complex chain becomes
    # extremely heavy (each region adds split→crop→blur→overlay) and can cause
    # FFmpeg to hang indefinitely on the first frame.  Fall back to a single
    # static blur region that covers the whole subtitle area for the entire
    # video duration.
    MAX_DYNAMIC_REGIONS = 30
    if len(dynamic_regions) > MAX_DYNAMIC_REGIONS:
        print(f"[warn] {len(dynamic_regions)} dynamic regions detected – collapsing to static region to avoid FFmpeg hang.", flush=True)
        dynamic_regions = []

    if dynamic_regions:
        if cleanup_mode == "localized_blur":
            filter_parts: list[str] = []
            current_label = "v0"
            filter_parts.append(f"[0:v]null[{current_label}]")
            for idx, region in enumerate(dynamic_regions, start=1):
                next_label = f"v{idx}"
                start_t = max(int(region.get("startMs", 0)), 0) / 1000
                end_t = max(int(region.get("endMs", 0)), 0) / 1000
                x = max(int(region.get("x", region_x)), 0)
                y = max(int(region.get("y", region_y)), 0)
                w = max(int(region.get("w", region_w)), 1)
                h = max(int(region.get("h", region_h)), 1)
                base_label = f"base{idx}"
                crop_label = f"crop{idx}"
                blur_label = f"blur{idx}"
                filter_parts.append(f"[{current_label}]split=2[{base_label}][{crop_label}]")
                filter_parts.append(
                    f"[{crop_label}]crop=w={w}:h={h}:x={x}:y={y},{blur_filter}[{blur_label}]"
                )
                filter_parts.append(
                    f"[{base_label}][{blur_label}]overlay={x}:{y}:enable='between(t,{start_t:.3f},{end_t:.3f})'[{next_label}]"
                )
                current_label = next_label
            filter_parts.append(f"[{current_label}]{subtitles_filter}[vout]")
            video_filter = ";".join(filter_parts)
            filter_arg = "-filter_complex"
            video_map = "[vout]"
        elif cleanup_mode == "localized_mask":"""

replacement = """    dynamic_regions = [region for region in (dynamic_regions or []) if int(region.get("w", 0)) > 0 and int(region.get("h", 0)) > 0]

    if dynamic_regions:
        if cleanup_mode == "localized_blur":
            drawbox_chain = ",".join(
                [
                    "drawbox="
                    f"x={max(int(region.get('x', region_x)), 0)}:"
                    f"y={max(int(region.get('y', region_y)), 0)}:"
                    f"w={max(int(region.get('w', region_w)), 1)}:"
                    f"h={max(int(region.get('h', region_h)), 1)}:"
                    "color=white:t=fill:"
                    f"enable='between(t,{max(int(region.get('startMs', 0)), 0) / 1000:.3f},{max(int(region.get('endMs', 0)), 0) / 1000:.3f})'"
                    for region in dynamic_regions
                ]
            )
            video_filter = (
                "[0:v]split=3[orig][blur_src][mask_src];"
                f"[blur_src]{blur_filter}[blurred];"
                f"[mask_src]drawbox=x=0:y=0:w=iw:h=ih:color=black:t=fill,{drawbox_chain}[mask];"
                "[orig][blurred][mask]maskedmerge[merged];"
                f"[merged]{subtitles_filter}[vout]"
            )
            filter_arg = "-filter_complex"
            video_map = "[vout]"
        elif cleanup_mode == "localized_mask":"""

if target in content:
    content = content.replace(target, replacement)
    with open('tools/dub_studio/cli_parts/render.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("SUCCESS")
else:
    print("TARGET NOT FOUND!")
