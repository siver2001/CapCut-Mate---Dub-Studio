import json
import os
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
MEMORY_FILE = ROOT / "config" / "speaker_memory.json"

def load_memory() -> dict:
    if not MEMORY_FILE.exists():
        return {"known_speakers": []}
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"known_speakers": []}

def save_memory(data: dict) -> None:
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    if len(v1) != len(v2) or not v1 or not v2:
        return 0.0
    dot_product = sum(a * b for a, b in zip(v1, v2))
    norm_a = math.sqrt(sum(a * a for a in v1))
    norm_b = math.sqrt(sum(b * b for b in v2))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot_product / (norm_a * norm_b)

def find_closest_speaker(embedding: list[float], threshold: float = 0.65) -> dict | None:
    memory = load_memory()
    best_sim = -1.0
    best_speaker = None
    
    for speaker in memory.get("known_speakers", []):
        saved_emb = speaker.get("embedding")
        if saved_emb:
            sim = cosine_similarity(embedding, saved_emb)
            if sim > best_sim:
                best_sim = sim
                best_speaker = speaker
                
    if best_sim >= threshold and best_speaker is not None:
        # Return a copy with match similarity details
        res = dict(best_speaker)
        res["match_similarity"] = best_sim
        return res
    return None

def add_or_update_speaker(name: str, embedding: list[float], gender: str, age: int, voice: str) -> None:
    memory = load_memory()
    speakers = memory.get("known_speakers", [])
    
    # Check if there is already a very similar speaker
    best_sim = -1.0
    matching_speaker = None
    for speaker in speakers:
        saved_emb = speaker.get("embedding")
        if saved_emb:
            sim = cosine_similarity(embedding, saved_emb)
            if sim > best_sim:
                best_sim = sim
                matching_speaker = speaker
                
    if best_sim >= 0.75 and matching_speaker is not None:
        # Update matching speaker details
        matching_speaker["name"] = name
        matching_speaker["preferred_voice"] = voice
        matching_speaker["gender"] = gender
        matching_speaker["age"] = age
        # Update embedding dynamically with running average (optional but keeps features fresh)
        matching_speaker["embedding"] = [
            (a * 0.7 + b * 0.3) for a, b in zip(matching_speaker["embedding"], embedding)
        ]
    else:
        # Add new speaker
        speakers.append({
            "name": name,
            "gender": gender,
            "age": age,
            "embedding": embedding,
            "preferred_voice": voice
        })
        
    memory["known_speakers"] = speakers
    save_memory(memory)
