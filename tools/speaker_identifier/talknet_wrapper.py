import os
import sys
import subprocess
import pickle
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
TALKNET_DIR = ROOT / "repos" / "TalkNet-ASD"

def patch_talknet_files() -> None:
    """
    Patches the TaoRuijie/TalkNet-ASD code to be multi-device compatible.
    Replaces hardcoded .cuda() calls with .to(device) where device checks torch.cuda.is_available().
    """
    if not TALKNET_DIR.exists():
        return
        
    # 1. Patch talkNet.py
    talknet_file = TALKNET_DIR / "talkNet.py"
    if talknet_file.exists():
        content = talknet_file.read_text(encoding="utf-8")
        patched = content
        if ".cuda()" in patched:
            print("[talknet_patch] Patching talkNet.py for CPU support...")
            patched = patched.replace("talkNetModel().cuda()", "talkNetModel().to('cuda' if torch.cuda.is_available() else 'cpu')")
            patched = patched.replace("lossAV().cuda()", "lossAV().to('cuda' if torch.cuda.is_available() else 'cpu')")
            patched = patched.replace("lossA().cuda()", "lossA().to('cuda' if torch.cuda.is_available() else 'cpu')")
            patched = patched.replace("lossV().cuda()", "lossV().to('cuda' if torch.cuda.is_available() else 'cpu')")
            patched = patched.replace(".cuda()", ".to('cuda' if torch.cuda.is_available() else 'cpu')")
        if "torch.load(path)" in patched:
            print("[talknet_patch] Patching talkNet.py for torch.load weights_only compatibility...")
            patched = patched.replace("torch.load(path)", "torch.load(path, map_location='cuda' if torch.cuda.is_available() else 'cpu', weights_only=False)")
        if patched != content:
            talknet_file.write_text(patched, encoding="utf-8")

    # 2. Patch demoTalkNet.py
    demo_file = TALKNET_DIR / "demoTalkNet.py"
    if demo_file.exists():
        content = demo_file.read_text(encoding="utf-8")
        patched = content
        if "device='cuda'" in patched or ".cuda()" in patched:
            print("[talknet_patch] Patching demoTalkNet.py for CPU support...")
            patched = patched.replace("S3FD(device='cuda')", "S3FD(device='cuda' if torch.cuda.is_available() else 'cpu')")
            patched = patched.replace(".cuda()", ".to('cuda' if torch.cuda.is_available() else 'cpu')")
        if "visualization(vidTracks, scores, args)" in patched:
            # Disable visualization step at the end of demoTalkNet.py to save time during CLI run
            patched = patched.replace("visualization(vidTracks, scores, args)", "pass  # visualization disabled by wrapper")
        if "-qscale:v 2" in patched and "-r 25" not in patched:
            print("[talknet_patch] Patching demoTalkNet.py to force 25 FPS frame extraction...")
            patched = patched.replace("-qscale:v 2", "-r 25 -qscale:v 2")
        if patched != content:
            demo_file.write_text(patched, encoding="utf-8")

    # 3. Patch model/faceDetector/s3fd/nets.py
    nets_file = TALKNET_DIR / "model" / "faceDetector" / "s3fd" / "nets.py"
    if nets_file.exists():
        content = nets_file.read_text(encoding="utf-8")
        if "torch.load(model_path)" in content:
            print("[talknet_patch] Patching nets.py for map_location support...")
            patched = content.replace(
                "torch.load(model_path)", 
                "torch.load(model_path, map_location='cuda' if torch.cuda.is_available() else 'cpu')"
            )
            nets_file.write_text(patched, encoding="utf-8")

    # 4. Patch model/faceDetector/s3fd/box_utils.py
    box_utils_file = TALKNET_DIR / "model" / "faceDetector" / "s3fd" / "box_utils.py"
    if box_utils_file.exists():
        content = box_utils_file.read_text(encoding="utf-8")
        if "astype(np.int)" in content:
            print("[talknet_patch] Patching box_utils.py to replace deprecated np.int...")
            patched = content.replace("astype(np.int)", "astype(int)")
            box_utils_file.write_text(patched, encoding="utf-8")

    # 5. Patch model/faceDetector/s3fd/__init__.py
    s3fd_init_file = TALKNET_DIR / "model" / "faceDetector" / "s3fd" / "__init__.py"
    if s3fd_init_file.exists():
        content = s3fd_init_file.read_text(encoding="utf-8")
        if "map_location=self.device)" in content and "weights_only" not in content:
            print("[talknet_patch] Patching s3fd/__init__.py to disable weights_only...")
            patched = content.replace("map_location=self.device)", "map_location=self.device, weights_only=False)")
            s3fd_init_file.write_text(patched, encoding="utf-8")

def run_talknet_asd(video_path: Path, output_dir: Path, python_exe: str) -> tuple[list, list] | None:
    """
    Runs TalkNet Active Speaker Detection on a video file.
    Returns: (vidTracks, scores) loaded from pickle files.
    """
    if os.environ.get("BYPASS_TALKNET") == "1":
        print("[talknet_wrapper] BYPASS_TALKNET is enabled. Skipping TalkNet ASD.")
        return None
        
    patch_talknet_files()
    
    # Check pretrain model exists
    pretrain_model = TALKNET_DIR / "pretrain_TalkSet.model"
    # Create output directories
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # We copy the video file to a temp location inside output_dir because demoTalkNet assumes video is inside a folder
    video_temp_dir = output_dir / "input_temp"
    video_temp_dir.mkdir(parents=True, exist_ok=True)
    temp_video_path = video_temp_dir / f"video{video_path.suffix}"
    shutil.copy2(video_path, temp_video_path)
    
    # Run demoTalkNet.py
    print(f"[talknet_wrapper] Running active speaker detection on: {video_path.name}")
    cmd = [
        python_exe,
        "demoTalkNet.py",
        "--videoName", "video",
        "--videoFolder", str(video_temp_dir.resolve()),
        "--pretrainModel", str(pretrain_model.resolve())
    ]
    
    # Execute under repos/TalkNet-ASD Cwd
    try:
        subprocess.run(cmd, cwd=str(TALKNET_DIR), check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print(f"[talknet_wrapper] ERROR running TalkNet: {e.stderr or e.stdout}")
        return None
        
    # Read pickle outputs
    # demoTalkNet saves files inside videoFolder/video/pywork/
    pywork_dir = video_temp_dir / "video" / "pywork"
    tracks_file = pywork_dir / "tracks.pckl"
    scores_file = pywork_dir / "scores.pckl"
    
    if not tracks_file.exists() or not scores_file.exists():
        print("[talknet_wrapper] ERROR: TalkNet output pickle files not found.")
        return None
        
    try:
        with open(tracks_file, "rb") as f:
            vidTracks = pickle.load(f)
        with open(scores_file, "rb") as f:
            scores = pickle.load(f)
        return vidTracks, scores
    except Exception as e:
        print(f"[talknet_wrapper] ERROR loading pickle files: {e}")
        return None
    finally:
        # Clean up temp input folder
        shutil.rmtree(video_temp_dir, ignore_errors=True)
