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
        "render", 
        "--analysis-json", "backtest_3_analysis.json", 
        "--render-options-json", "backtest_3_options.json",
        "--output-json", "backtest_render_result.json"
    ]
    render_main()
