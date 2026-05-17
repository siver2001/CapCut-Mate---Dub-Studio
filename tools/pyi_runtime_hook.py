import sys
import os

if getattr(sys, 'frozen', False):
    application_path = sys._MEIPASS
    
    # Ensure extraction directory is in path
    if application_path not in sys.path:
        sys.path.insert(0, application_path)
    
    # Add _internal directory to path for onedir mode
    internal_dir = os.path.join(application_path, '_internal')
    if os.path.exists(internal_dir) and internal_dir not in sys.path:
        sys.path.insert(0, internal_dir)
        
    # Vendor packages (viphoneme, vinorm, etc.) need explicit paths when frozen
    os.environ['VI_PHONEME_PATH'] = os.path.join(internal_dir if os.path.exists(internal_dir) else application_path, 'viphoneme')
    os.environ['VINORM_PATH'] = os.path.join(internal_dir if os.path.exists(internal_dir) else application_path, 'vinorm')
    
    # Add tools/valtec_repo/src to path dynamically
    valtec_repo_src = os.path.join(application_path, 'tools', 'valtec_repo')
    if os.path.exists(valtec_repo_src) and valtec_repo_src not in sys.path:
        sys.path.insert(0, valtec_repo_src)
