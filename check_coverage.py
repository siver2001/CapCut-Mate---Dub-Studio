import json
from pathlib import Path

def run():
    path = Path("temp/test_analysis.json")
    if not path.exists():
        print("test_analysis.json not found")
        return
        
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    timeline = data.get("subtitleTimeline", [])
    if len(timeline) > 0:
        print(f"Timeline item keys: {list(timeline[0].keys())}")
        # Print keys of 'region' or similar keys inside timeline
        for key in timeline[0].keys():
            print(f"  {key}: {type(timeline[0][key])}")

if __name__ == "__main__":
    run()
