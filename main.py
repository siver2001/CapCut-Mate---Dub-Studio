import sys
import os

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

if getattr(sys, 'frozen', False):
    ROOT_DIR = os.path.dirname(os.path.abspath(sys.executable))
    if ROOT_DIR not in sys.path:
        sys.path.insert(0, ROOT_DIR)
    
    # Bypass PyInstaller's FrozenImporter for tools, gui, and config modules
    # to allow "Hot Updates" directly from raw python files on the disk!
    for finder in sys.meta_path:
        if finder.__class__.__name__ == 'PyiFrozenImporter':
            if hasattr(finder, '_toc'):
                try:
                    to_remove = [
                        name for name in finder._toc
                        if name.startswith("tools") or name.startswith("gui") or name == "config"
                    ]
                    for name in to_remove:
                        if hasattr(finder._toc, "discard"):
                            finder._toc.discard(name)
                        elif hasattr(finder._toc, "pop"):
                            finder._toc.pop(name, None)
                except Exception:
                    pass
else:
    ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

# Migrate old DUB_HF_CACHE_DIR to new shorter path in .env to prevent MAX_PATH limit errors on Windows
try:
    import shutil
    new_cache_path = os.path.join(os.path.expanduser("~"), ".capcut_mate", "hf_cache", "huggingface", "hub")
    
    env_file = os.path.join(ROOT_DIR, ".env")
    if os.path.exists(env_file):
        with open(env_file, "r", encoding="utf-8-sig") as f:
            lines = f.readlines()
        
        modified = False
        new_lines = []
        for line in lines:
            line_stripped = line.strip()
            if line_stripped and not line_stripped.startswith("#") and "=" in line_stripped:
                k, v = line_stripped.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k == "DUB_HF_CACHE_DIR" and v in ("temp/.cache/huggingface/hub", "hf_cache/huggingface/hub"):
                    new_lines.append("# DUB_HF_CACHE_DIR is now defaulted to user home directory to prevent path limit errors\n")
                    os.environ.pop("DUB_HF_CACHE_DIR", None)
                    modified = True
                    continue
            new_lines.append(line)
        
        if modified:
            with open(env_file, "w", encoding="utf-8-sig") as f:
                f.writelines(new_lines)

    # Helper to recursively merge and clean directories
    def merge_dirs(src, dst):
        if not os.path.exists(src):
            return
        os.makedirs(dst, exist_ok=True)
        for item in os.listdir(src):
            s = os.path.join(src, item)
            d = os.path.join(dst, item)
            if os.path.isdir(s):
                merge_dirs(s, d)
            else:
                if not os.path.exists(d):
                    try:
                        shutil.move(s, d)
                    except Exception:
                        pass
        try:
            shutil.rmtree(src, ignore_errors=True)
        except Exception:
            pass

    # Migrate existing model files from all potential old local cache locations
    old_locations = [
        os.path.join(ROOT_DIR, "temp", ".cache", "huggingface", "hub"),
        os.path.join(ROOT_DIR, "hf_cache", "huggingface", "hub"),
        os.path.join(ROOT_DIR, "_internal", "hf_cache", "huggingface", "hub"),
    ]
    for old_loc in old_locations:
        if os.path.exists(old_loc):
            try:
                merge_dirs(old_loc, new_cache_path)
            except Exception:
                pass

    # Migrate OmniVoice model from hf_cache/hub to user's home folder ~/.capcut_mate/hf_cache/hub
    new_cache_path_hub = os.path.join(os.path.expanduser("~"), ".capcut_mate", "hf_cache", "hub")
    old_hub_locations = [
        os.path.join(ROOT_DIR, "hf_cache", "hub"),
        os.path.join(ROOT_DIR, "_internal", "hf_cache", "hub"),
    ]
    for old_loc in old_hub_locations:
        if os.path.exists(old_loc):
            try:
                merge_dirs(old_loc, new_cache_path_hub)
            except Exception:
                pass

    # Clean up empty parent directories of old cache locations
    def remove_empty_dir(d):
        try:
            if os.path.exists(d) and not os.listdir(d):
                os.rmdir(d)
        except Exception:
            pass

    for parent in [
        os.path.join(ROOT_DIR, "temp", ".cache", "huggingface"),
        os.path.join(ROOT_DIR, "temp", ".cache"),
        os.path.join(ROOT_DIR, "hf_cache", "huggingface"),
        os.path.join(ROOT_DIR, "hf_cache", "hub"),
        os.path.join(ROOT_DIR, "hf_cache"),
        os.path.join(ROOT_DIR, "_internal", "hf_cache", "huggingface"),
        os.path.join(ROOT_DIR, "_internal", "hf_cache", "hub"),
        os.path.join(ROOT_DIR, "_internal", "hf_cache"),
    ]:
        remove_empty_dir(parent)
except Exception:
    pass

import warnings
warnings.filterwarnings("ignore")

try:
    import torch
    # Eagerly import torch at the top level to avoid deadlocks in multi-process environments on Windows
    # This is a critical stability fix for Windows/Python 3.12+
except ImportError:
    torch = None


if getattr(sys, 'frozen', False):
    import os
    meipass = getattr(sys, '_MEIPASS', os.path.abspath(os.path.dirname(sys.executable)))
    capi_dir = os.path.join(meipass, "onnxruntime", "capi")
    os.environ["PATH"] = meipass + os.pathsep + capi_dir + os.pathsep + os.environ.get("PATH", "")
    if hasattr(os, "add_dll_directory"):
        try:
            os.add_dll_directory(meipass)
        except Exception:
            pass
        try:
            os.add_dll_directory(capi_dir)
        except Exception:
            pass

# Legacy shim for 'imp' module (removed in Python 3.12+)
# Needed for 'vinorm' and other legacy dependencies
DISABLE_IMP = os.environ.get("DISABLE_IMP_SHIM") == "1"
if not DISABLE_IMP:
    try:
        import imp
    except ImportError:
        import types
        import importlib.util
        import importlib.machinery
        
        _imp_shim = types.ModuleType('imp')
        
        def _find_module(name, path=None):
            try:
                spec = importlib.util.find_spec(name, path)
                if spec is None:
                    raise ImportError(f"No module named {name}")
                
                origin = getattr(spec, "origin", None)
                if origin and (origin.endswith('__init__.py') or os.path.isdir(origin)):
                    if origin.endswith('__init__.py'):
                        origin = os.path.dirname(origin)
                return (None, origin, (None, None, 1))
            except Exception:
                raise ImportError(f"No module named {name}")
        
        _imp_shim.find_module = _find_module
        _imp_shim.new_module = lambda name: types.ModuleType(name)
        _imp_shim.get_suffixes = lambda: [('.py', 'U', 1)]
        sys.modules['imp'] = _imp_shim

def main():
    if len(sys.argv) > 1:
        mode = sys.argv[1]
        if mode == "pipeline":
            # If called with 'pipeline' argument, act as the dub studio worker.
            sys.argv.pop(1)
            # Add root to path for imports
            root = ROOT_DIR
            if root not in sys.path:
                sys.path.insert(0, root)
            from tools.dub_studio_pipeline import main as run_pipeline, setup_quiet_excepthook
            setup_quiet_excepthook()
            sys.exit(run_pipeline())
        elif mode == "yt_dlp":
            # Act as yt-dlp entry point
            sys.argv.pop(1)
            import yt_dlp
            sys.exit(yt_dlp.main())
        elif mode == "-m" and len(sys.argv) > 2:
            module_name = sys.argv[2]
            sys.argv.pop(1) # remove -m
            sys.argv.pop(1) # remove module_name
            
            # Add root to path for imports
            root = ROOT_DIR
            if root not in sys.path:
                sys.path.insert(0, root)
            import importlib
            try:
                # Try running the __main__ of the module
                mod = importlib.import_module(f"{module_name}.__main__")
                if hasattr(mod, "main"):
                    try:
                        sys.exit(mod.main())
                    except Exception as e:
                        import traceback
                        traceback.print_exc()
                        sys.exit(1)
                else:
                    print(f"No main function found in {module_name}.__main__")
                    sys.exit(1)
            except ImportError:
                try:
                    mod = importlib.import_module(module_name)
                    if hasattr(mod, "main"):
                        try:
                            sys.exit(mod.main())
                        except Exception as e:
                            import traceback
                            traceback.print_exc()
                            sys.exit(1)
                    else:
                        print(f"No main function found in {module_name}")
                        sys.exit(1)
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    sys.exit(1)
            except Exception as e:
                import traceback
                traceback.print_exc()
                sys.exit(1)
        elif mode.endswith(".py") or (os.path.exists(mode) and os.path.isfile(mode) and mode.endswith(".py")):
            # Act as a python interpreter running the script
            sys.argv.pop(1)  # Remove script name from sys.argv
            script_path = os.path.abspath(mode)
            # Add script's directory to sys.path
            script_dir = os.path.dirname(script_path)
            if script_dir not in sys.path:
                sys.path.insert(0, script_dir)
            # Make sys.argv[0] point to the script path
            if len(sys.argv) > 0:
                sys.argv[0] = script_path
            else:
                sys.argv.append(script_path)
            # Execute the script
            try:
                with open(script_path, "r", encoding="utf-8") as f:
                    code_content = f.read()
                global_dict = {
                    "__file__": script_path,
                    "__name__": "__main__",
                    "__doc__": None,
                    "__package__": None,
                }
                exec(code_content, global_dict)
                sys.exit(0)
            except Exception as e:
                import traceback
                traceback.print_exc()
                sys.exit(1)


    # Default behavior: run as normal app if no specialized mode
    # Add root to path for imports
    root = ROOT_DIR
    if root not in sys.path:
        sys.path.insert(0, root)
    
    from gui.main import main as run_gui
    sys.exit(run_gui())


if __name__ == "__main__":
    main()