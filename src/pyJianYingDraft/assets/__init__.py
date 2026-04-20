"""
Resource management module for pyJianYingDraft, providing a centralized way to manage asset files and avoid hardcoded paths
"""

from pathlib import Path

# Get the directory where the current module is located
ASSETS_DIR = Path(__file__).parent

# Asset file mapping - centrally manage all asset filenames
ASSET_FILES = {
    # Template files
    'DRAFT_CONTENT_TEMPLATE': 'draft_content_template.json',
    'DRAFT_META_TEMPLATE': 'draft_meta_info.json',
}

def get_asset_path(asset_name: str) -> Path:
    """
    Get the full path of the specified asset file

    Args:
        asset_name: Asset name (key in ASSET_FILES)

    Returns:
        Path: Full path to the asset file

    Raises:
        KeyError: Asset name does not exist
        FileNotFoundError: File does not exist
    """
    if asset_name not in ASSET_FILES:
        raise KeyError(f"Asset '{asset_name}' not found. Available assets: {list(ASSET_FILES.keys())}")

    file_path = ASSETS_DIR / ASSET_FILES[asset_name]

    if not file_path.exists():
        raise FileNotFoundError(f"Asset file '{file_path}' does not exist")

    return file_path

# Export main interfaces
__all__ = [
    'get_asset_path',
    'ASSET_FILES'
]
