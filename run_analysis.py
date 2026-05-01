import sys
from pathlib import Path
import os

# Add the root directory to sys.path
sys.path.append(os.getcwd())

from tools.dub_studio.cli_parts.render import main as render_main

if __name__ == "__main__":
    # Simulate command line arguments
    sys.argv = [
        "render.py", 
        "analyze", 
        "--job-id", "backtest_3", 
        "--input", "douyin_video (3).mp4", 
        "--output-json", "backtest_3_analysis.json"
    ]
    render_main()
