# Project Constants Definition
import os


# Project root directory
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# Directory for saving CapCut drafts
def get_capcut_draft_dir():
    # Priority: read from environment variables
    env_path = os.getenv("DRAFT_DIR")
    if env_path:
        return env_path
    
    # Default Windows paths
    if os.name == 'nt':
        local_appdata = os.getenv('LOCALAPPDATA')
        if local_appdata:
            # Try paths for both CapCut (Global) and Jianying (China)
            capcut_path = os.path.join(local_appdata, "CapCut", "User Data", "Projects", "com.lveditor.draft")
            jianying_path = os.path.join(local_appdata, "JianyingPro", "User Data", "Projects", "com.lveditor.draft")
            if os.path.exists(capcut_path):
                return capcut_path
            if os.path.exists(jianying_path):
                return jianying_path
            return capcut_path # Default to CapCut
    
    # Fallback to project_root/output/draft
    return os.path.join(PROJECT_ROOT, "output", "draft")

DRAFT_DIR = get_capcut_draft_dir()

# Log directory
LOG_DIR = os.path.join(PROJECT_ROOT, "output", "logs")

# Temporary file directory
TEMP_DIR = os.path.join(PROJECT_ROOT, "temp")

# Draft download URL
DRAFT_URL = os.getenv("DRAFT_URL", "https://capcut-mate.jcaigc.cn/openapi/capcut-mate/v1/get_draft")

# Used to convert internal container paths to URLs by replacing /app/ with DOWNLOAD_URL
DOWNLOAD_URL = os.getenv("DOWNLOAD_URL", "https://capcut-mate.jcaigc.cn/")

# Draft tip URL
TIP_URL = os.getenv("TIP_URL", "https://docs.jcaigc.cn/")

# Sticker configuration path
STICKER_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "sticker.json")

# Text effect (Huazi) configuration path
HUAZI_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "huazi.json")

# Template directory path
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "template")

# Draft save path (download location) - Required for cloud rendering
DRAFT_SAVE_PATH = os.getenv("DRAFT_SAVE_PATH", DRAFT_DIR)

# Tencent Cloud COS configuration - Required for cloud rendering
COS_SECRET_ID = os.getenv("COS_SECRET_ID", "xxx")
COS_SECRET_KEY = os.getenv("COS_SECRET_KEY", "xxx")
COS_BUCKET_NAME = os.getenv("COS_BUCKET_NAME", "xxx")
COS_REGION = os.getenv("COS_REGION", "xxx")

# APIKEY enablement - Default enabled - Required for cloud rendering (env true/false, case-insensitive)
ENABLE_APIKEY = os.getenv("ENABLE_APIKEY", "false").strip().lower() == "true"

# File download size limit (bytes), default 200MB
DOWNLOAD_FILE_SIZE_LIMIT = int(os.getenv("DOWNLOAD_FILE_SIZE_LIMIT", str(200 * 1024 * 1024)))
