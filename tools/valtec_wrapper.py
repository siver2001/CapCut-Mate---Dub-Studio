import os
import sys
import shutil
import tempfile
import importlib
import wave
from pathlib import Path
from typing import List, Optional

# Constants
VALTEC_REPO_SRC = Path(__file__).parent / "valtec_repo"

# Singleton instance
_provider = None

def get_valtec_provider(preload_zeroshot=False):
    global _provider
    if _provider is None:
        _provider = ValtecProvider()
    return _provider

def _preload_external_tts_deps() -> None:
    """
    Preload common heavy libraries to avoid deadlocks during dynamic path modification.
    pyarrow/pandas may scan sys.path during import and can fail on Windows when they 
    encounter the vendored Valtec repository directory.
    """
    for module_name in ("pyarrow", "pandas"):
        try:
            importlib.import_module(module_name)
        except Exception:
            pass

def _activate_valtec_repo_path() -> None:
    if not VALTEC_REPO_SRC.exists():
        return
    _preload_external_tts_deps()
    repo_path = str(VALTEC_REPO_SRC)
    sys.path[:] = [path for path in sys.path if path != repo_path]
    sys.path.insert(0, repo_path)
    # Clear stale modules from the repo if they exist
    loaded_src = sys.modules.get("src")
    if loaded_src is not None:
        loaded_src_file = str(getattr(loaded_src, "__file__", "") or "")
        if repo_path not in loaded_src_file:
            for module_name in list(sys.modules):
                if module_name == "src" or module_name.startswith("src."):
                    sys.modules.pop(module_name, None)

def _deactivate_valtec_repo_path() -> None:
    repo_path = str(VALTEC_REPO_SRC)
    sys.path[:] = [path for path in sys.path if path != repo_path]

def append_silence_to_wav(wav_path: Path, duration_seconds: float) -> None:
    if duration_seconds <= 0 or not wav_path.exists():
        return
    try:
        with wave.open(str(wav_path), "rb") as wav_in:
            params = wav_in.getparams()
            nchannels = params.nchannels
            sampwidth = params.sampwidth
            framerate = params.framerate
            frames = wav_in.readframes(params.nframes)
        
        # Calculate number of silence frames to add
        silence_frames = int(framerate * duration_seconds)
        # Bytes per frame = sampwidth * nchannels
        silence_bytes = b"\x00" * (silence_frames * sampwidth * nchannels)
        
        # Write back combined frames
        with wave.open(str(wav_path), "wb") as wav_out:
            wav_out.setparams(params)
            wav_out.writeframes(frames + silence_bytes)
    except Exception as e:
        print(f"[!] Error appending silence to wave: {e}", flush=True)

class ValtecProvider:
    def __init__(self):
        root = Path(__file__).parent.parent
        self.model_dir = root / "temp" / "models" / "valtec"
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self._tts = None
        self._zero_shot = None
        
        # Load GPU settings from config if possible
        try:
            from tools.dub_studio.config import DUB_USE_GPU, DUB_GPU_DEVICE
            use_gpu = DUB_USE_GPU
            gpu_idx = DUB_GPU_DEVICE
        except ImportError:
            use_gpu = os.environ.get("DUB_USE_GPU") == "True"
            gpu_idx = os.environ.get("DUB_GPU_DEVICE", "0")
        import torch
        self.device = f"cuda:{gpu_idx}" if (use_gpu and torch.cuda.is_available()) else "cpu"
        
        # Setup runtime temp dir
        temp_root = self.model_dir / "runtime_tmp"
        temp_root.mkdir(parents=True, exist_ok=True)
        self.temp_dir = Path(tempfile.mkdtemp(dir=str(temp_root), prefix="valtec_"))
        
    def _patch_valtec_cache_dir(self):
        cache_dir = self.temp_dir
        try:
            import valtec_tts as valtec_tts_module
            valtec_tts_module.get_cache_dir = lambda: cache_dir
        except Exception:
            pass
        try:
            import valtec_tts.zeroshot as valtec_zeroshot_module
            valtec_zeroshot_module._get_cache_dir = lambda: cache_dir
        except Exception:
            pass

    def _load_tts(self):
        if self._tts is None:
            _activate_valtec_repo_path()
            try:
                self._patch_valtec_cache_dir()
                from valtec_tts import TTS
                local_model_dir = self.model_dir / "models" / "vits-vietnamese"
                if not (local_model_dir / "config.json").exists():
                     raise RuntimeError(f"Valtec-TTS local model missing in {local_model_dir}")
                self._tts = TTS(model_path=str(local_model_dir), device=self.device)
            finally:
                _deactivate_valtec_repo_path()
        return self._tts

    def _load_zero_shot(self):
        if self._zero_shot is None:
            _activate_valtec_repo_path()
            try:
                self._patch_valtec_cache_dir()
                from valtec_tts.zeroshot import ZeroShotTTS
                model_base = self.model_dir / "models" / "zeroshot-vietnamese"
                checkpoint = model_base / "G_175000.pth"
                config = model_base / "config.json"
                self._zero_shot = ZeroShotTTS(
                    checkpoint_path=str(checkpoint),
                    config_path=str(config),
                    device=self.device
                )
            finally:
                _deactivate_valtec_repo_path()
        return self._zero_shot

    def synthesize(
        self,
        text: str,
        output_path: Path,
        *,
        voice_name: str | None = None,
        prompt_audio: Path | None = None,
        speed: float = 1.0,
    ) -> bool:
        # Standard speaker mapping for VITS native speakers
        VALTEC_PRESET_SPEAKER_IDS = {
            "valtec:nf": "NF", "valtec:sf": "SF", "valtec:nm1": "NM1",
            "valtec:sm": "SM", "valtec:nm2": "NM2"
        }
        
        # Mapping for high-quality native reference voices (Thu Ha, Minh Duc, etc.)
        VALTEC_REFERENCE_VOICES = {
            "valtec:thu_ha": "thu_ha.wav",
            "valtec:minh_duc": "minh_duc.wav",
            "valtec:thanh_tam": "thanh_tam.wav",
            "valtec:quang_huy": "quang_huy.wav",
            "valtec:ngoc_anh": "ngoc_anh.wav",
            "valtec:hoang_nam": "hoang_nam.wav"
        }
        
        selected_voice = voice_name or "valtec:nf"
        
        # 1. Native VITS presets (speak directly using internal weights)
        if selected_voice in VALTEC_PRESET_SPEAKER_IDS:
            speaker_id = VALTEC_PRESET_SPEAKER_IDS[selected_voice]
            engine = self._load_tts()
            engine.speak(
                text=text,
                speaker=speaker_id,
                output_path=str(output_path),
                speed=speed
            )
        # 2. Native Reference Preset voices (Thu Ha, Minh Duc, Thanh Tam, etc.)
        elif selected_voice in VALTEC_REFERENCE_VOICES:
            ref_file = VALTEC_REFERENCE_VOICES[selected_voice]
            # Reference file is located in tools/valtec_repo/examples/zeroshot/example_<name>.wav
            ref_path = Path(__file__).parent / "valtec_repo" / "examples" / "zeroshot" / f"example_{ref_file}"
            
            # If the native high-quality reference audio exists, use it for zero-shot synthesis!
            if ref_path.exists():
                engine = self._load_zero_shot()
                engine.clone_voice(
                    text=text,
                    reference_audio=str(ref_path),
                    output_path=str(output_path),
                    length_scale=speed
                )
            else:
                # Fallback to NF preset
                engine = self._load_tts()
                engine.speak(
                    text=text,
                    speaker="NF",
                    output_path=str(output_path),
                    speed=speed
                )
        # 3. Custom Zero-shot cloning (from the original video's character audio prompt)
        else:
            if prompt_audio and prompt_audio.exists():
                engine = self._load_zero_shot()
                engine.clone_voice(
                    text=text,
                    reference_audio=str(prompt_audio),
                    output_path=str(output_path),
                    length_scale=speed
                )
            else:
                # Fallback to NF preset
                engine = self._load_tts()
                engine.speak(
                    text=text,
                    speaker="NF",
                    output_path=str(output_path),
                    speed=speed
                )
        
        # Apply dynamic sentence silence gaps to ensure clean natural pauses at punctuation marks
        if output_path.exists() and output_path.stat().st_size > 0:
            stripped_text = text.strip()
            silence_duration = 0.0
            if stripped_text:
                last_char = stripped_text[-1]
                if last_char in (".", "?", "!", "…"):
                    silence_duration = 0.40  # 400ms pause for full sentence ends
                elif last_char in (",", ";", ":"):
                    silence_duration = 0.18  # 180ms pause for clause transitions
            
            if silence_duration > 0:
                append_silence_to_wav(output_path, silence_duration)
            
            return True
            
        return False

    def close(self):
        if self._tts:
            self._tts = None
        if self._zero_shot:
            self._zero_shot = None
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
