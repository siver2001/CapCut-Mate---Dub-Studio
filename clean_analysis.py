import json
from pathlib import Path

analysis_path = Path("temp/analysis.json")
if analysis_path.exists():
    with open(analysis_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    if "segments" in data:
        for seg in data["segments"]:
            if "translatedText" in seg:
                del seg["translatedText"]
    
    with open(analysis_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("Cleaned translatedText from analysis.json")
else:
    print("analysis.json not found")
