import os
import subprocess
import sys
import shutil
from pathlib import Path

def build():
    print("=== Dub Studio - Batch Build Tool ===")
    
    ROOT = Path(__file__).resolve().parent
    dist_dir = ROOT / "dist"
    build_dir = ROOT / "build"
    
    # 1. Clean up old builds
    if dist_dir.exists():
        print("Cleaning old dist folder...")
        shutil.rmtree(dist_dir)
    if build_dir.exists():
        shutil.rmtree(build_dir)

    # 2. Check PyInstaller
    try:
        import PyInstaller
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # 3. Prepare data paths
    # We always include assets, config, and tools
    datas = [
        ("assets", "assets"),
        ("config", "config"),
        ("tools", "tools"),
    ]
    
    # Check if models exist and include them to make the EXE "all-in-one"
    models_dir = ROOT / "temp" / "models"
    if models_dir.exists():
        print("Found AI models in temp/models. Including them in the package...")
        datas.append(("temp/models", "temp/models"))
    
    # Check if FFmpeg was downloaded to tools/bin
    ffmpeg_bin = ROOT / "tools" / "bin"
    if ffmpeg_bin.exists():
        print("Found FFmpeg in tools/bin. Including it in the package...")
        # Note: datas.append(("tools/bin", "tools/bin")) is redundant because "tools" is already added
        # but it doesn't hurt to be explicit if tools/bin is where we put it.
        pass

    # 4. Construct command
    # Using --onedir for better performance with large AI libraries
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onedir", 
        "--windowed",
        "--name", "CapCutMate",
        "--contents-directory", "internal", # Keeps the root folder clean
        "--exclude-module", "PyQt5",
    ]
    
    for src, dst in datas:
        cmd.extend(["--add-data", f"{src}{os.pathsep}{dst}"])
        
    # Collect complex dependencies
    cmd.extend([
        "--collect-all", "qtawesome",
        "--collect-all", "qt_material",
        "--collect-submodules", "whisperx",
    ])
    
    cmd.append("main.py")
    
    print(f"\nRunning PyInstaller (this may take several minutes)...\n")
    
    try:
        subprocess.check_call(cmd)
        
        print("\n" + "="*50)
        print("BUILD SUCCESSFUL!")
        print(f"Location: {dist_dir / 'CapCutMate'}")
        print("="*50)
        print("\nINSTRUCTIONS FOR DISTRIBUTION:")
        print("1. Go to the 'dist' folder.")
        print("2. Right-click the 'CapCutMate' folder and 'Compress to ZIP'.")
        print("3. Send the ZIP file to other users.")
        print("4. They just need to unzip and run 'CapCutMate.exe' inside the folder.")
        
    except subprocess.CalledProcessError as e:
        print(f"\nBuild failed with error code {e.returncode}")
        sys.exit(e.returncode)

if __name__ == "__main__":
    build()
