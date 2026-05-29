import argparse
import importlib.metadata
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


APP_NAME = "CapCutMate"
ENTRY_POINT = "main.py"

DATA_DIRS = ("assets", "config", "tools")
RUNTIME_MODEL_DIRS = ("valtec", "omnivoice", "pyannote")

REQUIRED_IMPORTS = {
    "PyInstaller": "pyinstaller",
    "PyQt6": "PyQt6",
    "qtawesome": "QtAwesome",
    "qt_material": "qt-material",
    "edge_tts": "edge-tts",
    "yt_dlp": "yt-dlp",
    "requests": "requests",
}

OPTIONAL_COLLECT_MODULES = (
    "qtawesome",
    "qt_material",
    "superqt",
    "edge_tts",
    "yt_dlp",
    "whisperx",
    "pyannote.audio",
    "pyannote.core",
    "pyannote.database",
    "pyannote.metrics",
    "torch",
    "torchaudio",
    "torchvision",
    "viphoneme",
    "underthesea",
    "vinorm",
    "cn2an",
    "jieba",
    "pypinyin",
    "jamo",
    "gruut",
    "anyascii",
    "eng_to_ipa",
    "num2words",
    "inflect",
    "g2p_en",
    "gruut_ipa",
    "gruut_lang_en",
    "unidecode",
    "soundfile",
    "librosa",
    "sea_g2p",
    "onnxruntime",
    "llama_cpp",
    "valtec_tts",
    "omnivoice",
)

METADATA_PACKAGES = (
    "pyinstaller",
    "PyQt6",
    "QtAwesome",
    "qt-material",
    "superqt",
    "edge-tts",
    "yt-dlp",
    "requests",
    "whisperx",
    "pyannote.audio",
    "torch",
    "torchaudio",
    "torchvision",
    "tqdm",
    "regex",
    "packaging",
    "filelock",
    "numpy",
    "tokenizers",
    "huggingface-hub",
    "safetensors",
    "transformers",
    "viphoneme",
    "underthesea",
    "vinorm",
    "cn2an",
    "jieba",
    "pypinyin",
    "jamo",
    "gruut",
    "anyascii",
    "eng-to-ipa",
    "num2words",
    "inflect",
    "g2p_en",
    "unidecode",
    "soundfile",
    "librosa",
    "sea_g2p",
    "onnxruntime",
    "llama-cpp-python",
    "valtec-tts",
    "omnivoice",
)


def module_exists(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def metadata_exists(name: str) -> bool:
    try:
        importlib.metadata.distribution(name)
        return True
    except importlib.metadata.PackageNotFoundError:
        return False


def remove_dir(path: Path) -> None:
    if not path.exists():
        return
    print(f"Cleaning {path.name}...", flush=True)
    try:
        shutil.rmtree(path)
    except PermissionError:
        print(f"\n[!] Khong xoa duoc '{path}'.", flush=True)
        print(f"Hay dong {APP_NAME}.exe hoac cua so dang mo thu muc nay roi chay lai.", flush=True)
        raise SystemExit(1)


def check_required_dependencies(python_exe: str) -> None:
    missing = [
        package_name
        for import_name, package_name in REQUIRED_IMPORTS.items()
        if not module_exists(import_name)
    ]
    if not missing:
        return

    print("\n[!] Moi truong Python hien tai dang thieu package build bat buoc:", flush=True)
    for package_name in missing:
        print(f"    - {package_name}", flush=True)
    print("\nCai bang lenh:", flush=True)
    print(f"    {python_exe} -m pip install {' '.join(missing)}", flush=True)
    raise SystemExit(1)


def build_command(root: Path, python_exe: str, *, clean: bool) -> list[str]:
    cmd = [
        python_exe,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--noupx",
        "--name",
        APP_NAME,
        "--exclude-module",
        "PyQt5",
        "--exclude-module",
        "PySide6",
        "--log-level",
        "WARN",
    ]

    if clean:
        cmd.append("--clean")

    icon_path = root / "assets" / "icon.ico"
    if icon_path.exists():
        cmd.extend(["--icon", str(icon_path)])

    for dirname in DATA_DIRS:
        source = root / dirname
        if source.exists():
            cmd.extend(["--add-data", f"{source}{os.pathsep}{dirname}"])

    for module_name in OPTIONAL_COLLECT_MODULES:
        if module_exists(module_name):
            cmd.extend(["--collect-all", module_name])

    for package_name in METADATA_PACKAGES:
        if metadata_exists(package_name):
            cmd.extend(["--copy-metadata", package_name])

    # Explicitly import all hidden submodules of Valtec-TTS / viphoneme / vinorm to avoid missing dependencies in PyInstaller build
    valtec_hiddens = [
        "src",
        "src.models",
        "src.models.synthesizer",
        "src.text",
        "src.text.symbols",
        "src.vietnamese",
        "src.vietnamese.text_processor",
        "src.vietnamese.phonemizer",
        "src.nn",
        "src.nn.commons",
        "src.nn.mel_processing",
        "src.utils",
        "src.utils.helpers",
        "valtec_tts",
        "viphoneme",
        "viphoneme.T2IPA",
        "viphoneme.syms",
        "viphoneme.text2sequence",
        "viphoneme.get_english_sym",
        "vinorm",
        "vinorm.vinorm",
        "vinorm.Dict",
        "vinorm.Mapping",
        "vinorm.RegexRule",
        "vinorm.lib",
    ]
    for hid in valtec_hiddens:
        cmd.extend(["--hidden-import", hid])

    # Attach the custom runtime hook to setup environmental variables and dynamic sys.path modifications
    runtime_hook_path = root / "tools" / "pyi_runtime_hook.py"
    if runtime_hook_path.exists():
        cmd.extend(["--runtime-hook", str(runtime_hook_path)])

    cmd.append(str(root / ENTRY_POINT))
    return cmd


def create_desktop_shortcut(root: Path) -> None:
    if os.name != "nt":
        return

    try:
        desktop = Path(os.environ["USERPROFILE"]) / "Desktop"
        target = root / "dist" / APP_NAME / f"{APP_NAME}.exe"
        working_dir = target.parent
        shortcut = desktop / f"{APP_NAME}.lnk"
        icon = root / "assets" / "icon.ico"

        ps_cmd = (
            "$ws = New-Object -ComObject WScript.Shell; "
            f"$s = $ws.CreateShortcut('{shortcut}'); "
            f"$s.TargetPath = '{target}'; "
            f"$s.WorkingDirectory = '{working_dir}'; "
            f"$s.IconLocation = '{icon if icon.exists() else target}'; "
            "$s.Save()"
        )
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        print(f"[+] Da tao shortcut Desktop: {shortcut}", flush=True)
    except Exception as exc:
        print(f"[-] Khong tao duoc shortcut Desktop: {exc}", flush=True)


def copy_runtime_models(root: Path, output_dir: Path) -> None:
    source_models = root / "temp" / "models"
    if not source_models.exists():
        print("[!] Khong tim thay temp/models nen ban build se tai model tren may nguoi dung khi can.", flush=True)
        return

    target_models = output_dir / "temp" / "models"
    target_models.mkdir(parents=True, exist_ok=True)

    copied_any = False
    for model_name in RUNTIME_MODEL_DIRS:
        source = source_models / model_name
        if not source.exists():
            continue
        target = target_models / model_name
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
        print(f"Copy runtime model: temp/models/{model_name} -> dist/{APP_NAME}/temp/models/{model_name}", flush=True)
        shutil.copytree(
            source,
            target,
            ignore=shutil.ignore_patterns(
                "__pycache__",
                "runtime_tmp",
                "tmp",
                "*.lock",
                "*.tmp",
            ),
        )
        copied_any = True

    if not copied_any:
        print("[!] Khong co Valtec/OmniVoice model local de copy vao ban build.", flush=True)


def copy_vc_redist(output_dir: Path) -> None:
    print("Copying Microsoft C++ Redistributable DLLs into bundle...", flush=True)
    import shutil
    import sys

    internal_dir = output_dir / "_internal"
    capi_dir = internal_dir / "onnxruntime" / "capi"
    capi_dir.mkdir(parents=True, exist_ok=True)

    sys32 = Path("C:/Windows/System32")
    dlls = ["vcruntime140.dll", "vcruntime140_1.dll", "msvcp140.dll"]

    for dll in dlls:
        # Check in System32 first
        src = sys32 / dll
        if src.exists():
            print(f"  Copying {dll} from System32", flush=True)
            shutil.copy2(src, output_dir / dll)
            shutil.copy2(src, internal_dir / dll)
            shutil.copy2(src, capi_dir / dll)
            continue

        # Fallback to Python folder if not in System32
        p_dll = Path(sys.executable).parent / dll
        if p_dll.exists():
            print(f"  Copying {dll} from Python folder", flush=True)
            shutil.copy2(p_dll, output_dir / dll)
            shutil.copy2(p_dll, internal_dir / dll)
            shutil.copy2(p_dll, capi_dir / dll)


def validate_built_app(root: Path, output_dir: Path) -> None:
    exe_path = output_dir / f"{APP_NAME}.exe"
    health_json = root / "temp" / "build_health_check.json"
    print("Dang kiem tra ban build sau khi dong goi...", flush=True)

    subprocess.check_call([str(exe_path), "--self-test"], cwd=root)
    subprocess.check_call(
        [
            str(exe_path),
            "pipeline",
            "health-check",
            "--output-json",
            str(health_json),
        ],
        cwd=root,
    )

    if not health_json.exists():
        raise RuntimeError(f"Health-check khong tao file ket qua: {health_json}")
    payload = json.loads(health_json.read_text(encoding="utf-8-sig"))
    if not payload.get("ok"):
        errors = payload.get("errors") or []
        raise RuntimeError("Health-check that bai: " + "; ".join(str(item) for item in errors))
    warnings = payload.get("warnings") or []
    if warnings:
        print("[!] Health-check co canh bao:", flush=True)
        for item in warnings:
            print(f"    - {item}", flush=True)
    print("[+] Ban build qua self-test va health-check.", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=f"Build {APP_NAME}.exe bang PyInstaller.")
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Khong xoa thu muc build/dist cu truoc khi build.",
    )
    parser.add_argument(
        "--no-shortcut",
        action="store_true",
        help="Khong tao shortcut tren Desktop sau khi build xong.",
    )
    parser.add_argument(
        "--no-models",
        action="store_true",
        help="Khong copy model Valtec/OmniVoice local vao dist sau khi build.",
    )
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Khong chay self-test/health-check sau khi build.",
    )
    return parser.parse_args()


def build() -> None:
    args = parse_args()
    root = Path(__file__).resolve().parent
    python_exe = sys.executable

    print(f"=== {APP_NAME} build tool ===", flush=True)
    print(f"Project: {root}", flush=True)
    print(f"Python:  {python_exe}", flush=True)

    os.environ.setdefault("QT_API", "pyqt6")
    os.environ.setdefault("PYTHONUTF8", "1")

    check_required_dependencies(python_exe)

    if not args.no_clean:
        remove_dir(root / "dist")
        remove_dir(root / "build")
        (root / f"{APP_NAME}.spec").unlink(missing_ok=True)

    print("Dang dong goi ung dung. Buoc nay co the mat vai phut...", flush=True)
    cmd = build_command(root, python_exe, clean=not args.no_clean)
    try:
        subprocess.check_call(cmd, cwd=root)
    except subprocess.CalledProcessError as exc:
        print(f"\n[!] Build that bai voi ma loi {exc.returncode}.", flush=True)
        raise SystemExit(exc.returncode)

    output_dir = root / "dist" / APP_NAME
    exe_path = output_dir / f"{APP_NAME}.exe"
    if not exe_path.exists():
        print(f"\n[!] Build xong nhung khong tim thay {exe_path}.", flush=True)
        raise SystemExit(1)

    print("\nBUILD SUCCESSFUL!", flush=True)
    print(f"File chay: {exe_path}", flush=True)

    copy_vc_redist(output_dir)

    if not args.no_models:
        copy_runtime_models(root, output_dir)

    if not args.no_validate:
        validate_built_app(root, output_dir)

    if not args.no_shortcut:
        create_desktop_shortcut(root)

    print("\nDe gui cho may khac: nen ZIP ca thu muc dist/CapCutMate.", flush=True)


if __name__ == "__main__":
    build()
