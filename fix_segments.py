import json
import re
from pathlib import Path

def srt_time_to_ms(time_str):
    h, m, s_ms = time_str.split(':')
    s, ms = s_ms.split(',')
    return int(h) * 3600000 + int(m) * 60000 + int(s) * 1000 + int(ms)

def fix_analysis_json():
    analysis_path = Path("temp/analysis.json")
    srt_path = Path("temp/dub_studio/vlog_test_1/analysis/transcript_merged.srt")
    
    if not analysis_path.exists() or not srt_path.exists():
        print("Missing files")
        return

    with open(analysis_path, "r", encoding="utf-8") as f:
        analysis = json.load(f)
    
    with open(srt_path, "r", encoding="utf-8") as f:
        srt_content = f.read()

    # Parse SRT segments
    srt_segments = []
    # More robust SRT parsing that handles different line endings and doesn't rely on lookahead
    raw_blocks = re.split(r'\n\s*\n', srt_content.strip())
    print(f"Found {len(raw_blocks)} raw blocks in SRT")
    
    for block in raw_blocks:
        lines = block.strip().split('\n')
        if len(lines) >= 3:
            time_match = re.search(r'(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})', lines[1])
            if time_match:
                start_ms = srt_time_to_ms(time_match.group(1))
                end_ms = srt_time_to_ms(time_match.group(2))
                text = " ".join(lines[2:]).strip()
                srt_segments.append({
                    "startMs": start_ms,
                    "endMs": end_ms,
                    "text": text
                })
    
    print(f"Successfully parsed {len(srt_segments)} segments from SRT")

    new_segments = []
    target_max_ms = 8000 
    
    global_index = 1
    for srt_seg in srt_segments:
        text = srt_seg["text"]
        duration = srt_seg["endMs"] - srt_seg["startMs"]
        
        # Optimized split for natural flow: aim for 40-55 chars, max 8 seconds
        if duration > target_max_ms or len(text) > 55:
            # Split by sentences first
            parts = re.split(r'([。？！？！.!? \n])', text)
            chunks = []
            current_text = ""
            for p in parts:
                if not p: continue
                current_text += p
                # If we have a sentence-like part that is long enough, or if we have too much text
                if (len(current_text) > 40 and p in "。？！？！.!? ") or len(current_text) > 60:
                    chunks.append(current_text.strip())
                    current_text = ""
            
            if current_text:
                if chunks:
                    # If the remaining part is very short, merge it to the last chunk
                    if len(current_text) < 15:
                        chunks[-1] += " " + current_text.strip()
                    else:
                        chunks.append(current_text.strip())
                else:
                    chunks.append(current_text.strip())
            
            # If still only one chunk but it's too long, split by comma or spaces
            if len(chunks) == 1 and (duration > target_max_ms or len(text) > 65):
                text = chunks[0]
                sub_parts = re.split(r'([，,;； \n])', text)
                chunks = []
                current_text = ""
                for p in sub_parts:
                    if not p: continue
                    current_text += p
                    if len(current_text) > 35:
                        chunks.append(current_text.strip())
                        current_text = ""
                if current_text:
                    if chunks: chunks[-1] += " " + current_text.strip()
                    else: chunks.append(current_text.strip())
            
            # Final fallback: if still only one chunk (no punctuation at all), force split by length
            if len(chunks) == 1 and (duration > target_max_ms or len(text) > 65):
                text = chunks[0]
                # Aim for ~45 chars per segment
                target_len = 45
                chunks = [text[i:i+target_len] for i in range(0, len(text), target_len)]

            num_chunks = len(chunks)
            chunk_duration = duration / num_chunks
            
            for i, chunk in enumerate(chunks):
                new_segments.append({
                    "id": f"seg_{global_index:04d}",
                    "index": global_index,
                    "startMs": int(srt_seg["startMs"] + i * chunk_duration),
                    "endMs": int(srt_seg["startMs"] + (i + 1) * chunk_duration),
                    "speakerId": "speaker_1",
                    "sourceText": chunk.strip(),
                    "delivery": "neutral",
                    "translatedText": "",
                    "machineTranslatedText": ""
                })
                global_index += 1
        else:
            new_segments.append({
                "id": f"seg_{global_index:04d}",
                "index": global_index,
                "startMs": srt_seg["startMs"],
                "endMs": srt_seg["endMs"],
                "speakerId": "speaker_1",
                "sourceText": text,
                "delivery": "neutral",
                "translatedText": "",
                "machineTranslatedText": ""
            })
            global_index += 1

    analysis["segments"] = new_segments
    analysis["subtitleTimeline"] = []
    analysis["renderDefaults"]["introHook"]["enabled"] = False
    
    with open(analysis_path, "w", encoding="utf-8") as f:
        json.dump(analysis, f, ensure_ascii=False, indent=2)
    
    print(f"Successfully updated analysis.json with {len(new_segments)} optimized segments.")

if __name__ == "__main__":
    fix_analysis_json()
