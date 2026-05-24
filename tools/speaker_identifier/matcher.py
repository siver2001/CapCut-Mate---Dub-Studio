import os
import cv2
import numpy as np
from pathlib import Path
from .insightface_wrapper import InsightFaceAnalysis
from .memory_manager import find_closest_speaker, add_or_update_speaker

def match_speakers_and_extract_features(
    video_path: Path,
    pyannote_segments: list[dict],
    talknet_tracks: list,
    talknet_scores: list,
    output_speakers_dir: Path,
    use_gpu: bool = False
) -> list[dict]:
    """
    Correlates Pyannote audio speaker labels with TalkNet-ASD visual tracks.
    For each speaker, extracts face embedding and saves face thumbnail.
    
    pyannote_segments: list of dicts:
      [{'start': float, 'end': float, 'speaker': str}]
    talknet_tracks: list of tracks from tracks.pckl
    talknet_scores: list of score lists from scores.pckl
    
    Returns a list of speaker info dicts:
      [{'speakerId': str, 'gender': str, 'age': int, 'faceThumbnail': str, 'recommendedVoice': str, 'memoryName': str}]
    """
    output_speakers_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Group Pyannote segments by speaker
    speaker_audio_frames = {} # speaker_id -> set of frame indices (at 25 fps)
    for seg in pyannote_segments:
        spk = seg.get("speaker")
        if not spk:
            continue
        start_frame = int(seg["start"] * 25)
        end_frame = int(seg["end"] * 25)
        if spk not in speaker_audio_frames:
            speaker_audio_frames[spk] = set()
        for f in range(start_frame, end_frame + 1):
            speaker_audio_frames[spk].add(f)
            
    # 2. Open Video to read frames for cropping
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"[matcher] ERROR: Failed to open video: {video_path}")
        return []
        
    # Initialize InsightFace
    face_analyzer = InsightFaceAnalysis(use_gpu=use_gpu)
    
    results = []
    
    # 3. For each Pyannote speaker, find the best matching TalkNet track
    for spk, audio_frames in speaker_audio_frames.items():
        best_track_idx = -1
        best_score_sum = -999.0
        
        # We calculate the sum of TalkNet speaking scores during the frames Pyannote says this speaker speaks
        for tidx, track_data in enumerate(talknet_tracks):
            track = track_data["track"]
            scores = talknet_scores[tidx]
            
            # Map track frames (which are 0-indexed relative to track start) to absolute video frame numbers
            score_sum = 0.0
            overlap_count = 0
            for fidx, abs_frame in enumerate(track["frame"]):
                if fidx >= len(scores):
                    break
                if abs_frame in audio_frames:
                    score_sum += scores[fidx]
                    overlap_count += 1
            
            if overlap_count > 0:
                # Average score weighted by overlap count
                avg_score = score_sum / overlap_count
                if avg_score > best_score_sum:
                    best_score_sum = avg_score
                    best_track_idx = tidx
                    
        # 4. If we found a matching track, extract face embeddings and crop thumbnail
        if best_track_idx != -1:
            track_data = talknet_tracks[best_track_idx]
            track = track_data["track"]
            scores = talknet_scores[best_track_idx]
            
            # Find the frame in the track where the active speaker score is highest
            best_frame_idx = int(np.argmax(scores))
            best_frame_idx = min(best_frame_idx, len(track["frame"]) - 1) if len(track["frame"]) > 0 else 0
            abs_frame_num = int(track["frame"][best_frame_idx])
            bbox = track["bbox"][best_frame_idx].astype(int).tolist() # [x1, y1, x2, y2]
            
            # Read that specific frame
            cap.set(cv2.CAP_PROP_POS_FRAMES, abs_frame_num)
            ret, frame = cap.read()
            if ret and frame is not None:
                # 5. Crop and save face thumbnail
                h, w = frame.shape[:2]
                x1, y1, x2, y2 = bbox
                # Make box square and pad slightly
                box_w = x2 - x1
                box_h = y2 - y1
                cx = (x1 + x2) // 2
                cy = (y1 + y2) // 2
                side = int(max(box_w, box_h) * 1.3)
                
                nx1 = max(0, cx - side // 2)
                ny1 = max(0, cy - side // 2)
                nx2 = min(w, cx + side // 2)
                ny2 = min(h, cy + side // 2)
                
                face_crop = frame[ny1:ny2, nx1:nx2]
                face_thumb_path = output_speakers_dir / f"{spk}_face.jpg"
                if face_crop.size > 0:
                    cv2.imwrite(str(face_thumb_path), face_crop)
                    
                # 6. Extract Face Embedding using InsightFace
                face_info = face_analyzer.extract_crop_embedding(frame, bbox)
                if face_info and face_info.get("embedding"):
                    embedding = face_info["embedding"]
                    gender = face_info["gender"]
                    age = face_info["age"]
                    
                    # 7. Check Speaker Memory
                    match = find_closest_speaker(embedding, threshold=0.65)
                    if match:
                        memory_name = match["name"]
                        voice_preset = match["preferred_voice"]
                        print(f"[matcher] Matched speaker {spk} with memory identity: {memory_name} ({voice_preset})")
                    else:
                        memory_name = ""
                        # Recommend default voice based on gender
                        voice_preset = "edge:female" if gender == "F" else "edge:male"
                        
                    results.append({
                        "speakerId": spk,
                        "gender": gender,
                        "age": age,
                        "faceThumbnail": str(face_thumb_path.relative_to(output_speakers_dir.parent.parent.parent)),
                        "voicePreset": voice_preset,
                        "memoryName": memory_name,
                        "embedding": embedding
                    })
                    continue
                    
        # Fallback if no face track found or face analysis failed
        results.append({
            "speakerId": spk,
            "gender": "F",
            "age": 25,
            "faceThumbnail": "",
            "voicePreset": "edge:female",
            "memoryName": "",
            "embedding": []
        })
        
    cap.release()
    return results
