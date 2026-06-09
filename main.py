import warnings
warnings.filterwarnings("ignore")

try:
    import torch
    # Eagerly import torch at the top level to avoid deadlocks in multi-process environments on Windows
    # This is a critical stability fix for Windows/Python 3.12+
except ImportError:
    torch = None

import sys
import os

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
            root = os.path.dirname(os.path.abspath(__file__))
            if root not in sys.path:
                sys.path.insert(0, root)
            from tools.dub_studio_pipeline import main as run_pipeline
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
            root = os.path.dirname(os.path.abspath(__file__))
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

    # Default behavior: run as normal app if no specialized mode
    # Add root to path for imports
    root = os.path.dirname(os.path.abspath(__file__))
    if root not in sys.path:
        sys.path.insert(0, root)
    
    from gui.main import main as run_gui
    sys.exit(run_gui())


if __name__ == "__main__":
    main()