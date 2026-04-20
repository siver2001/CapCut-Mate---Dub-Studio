"""Draft folder manager"""

import os
import shutil

from typing import List

from . import assets
from .script_file import ScriptFile

class DraftFolder:
    """Manages a folder and a series of drafts within it"""

    folder_path: str
    """Root path"""

    def __init__(self, folder_path: str):
        """Initialize draft folder manager

        Args:
            folder_path (`str`): Folder containing drafts, usually the CapCut draft storage location

        Raises:
            `FileNotFoundError`: Path does not exist
        """
        self.folder_path = folder_path

        if not os.path.exists(self.folder_path):
            raise FileNotFoundError(f"Root folder {self.folder_path} does not exist")

    def list_drafts(self) -> List[str]:
        """List names of all drafts in the folder

        Note: This only lists subfolder names and does not check if they are valid drafts
        """
        return [f for f in os.listdir(self.folder_path) if os.path.isdir(os.path.join(self.folder_path, f))]

    def has_draft(self, draft_name: str) -> bool:
        """Check if a draft with the specified name exists in the folder

        Note: This only checks for folder existence and does not validate the draft format

        Args:
            draft_name (`str`): Draft name (folder name)
        """
        return draft_name in self.list_drafts()

    def remove(self, draft_name: str) -> None:
        """Remove a draft with the specified name

        Args:
            draft_name (`str`): Draft name (folder name)

        Raises:
            `FileNotFoundError`: Draft does not exist
        """
        draft_path = os.path.join(self.folder_path, draft_name)
        if not os.path.exists(draft_path):
            raise FileNotFoundError(f"Draft folder {draft_name} does not exist")

        shutil.rmtree(draft_path)

    def create_draft(self, draft_name: str, width: int, height: int, fps: int = 30, *,
                     maintrack_adsorb: bool = True,
                     allow_replace: bool = False) -> ScriptFile:
        """Create a new draft and start editing. Use `ScriptFile.save()` to save changes.

        Args:
            draft_name (`str`): Draft name (folder name)
            width (`int`): Video width in pixels
            height (`int`): Video height in pixels
            fps (`int`, optional): Video frame rate. Default is 30.
            maintrack_adsorb (`bool`, optional): Whether to enable main track magnetic absorption. Default is True.
            allow_replace (`bool`, optional): Whether to allow overwriting existing draft. Default is False.

        Raises:
            `FileExistsError`: Draft already exists and `allow_replace` is False.
        """
        draft_path = os.path.join(self.folder_path, draft_name)
        if os.path.exists(draft_path):
            if not allow_replace:
                raise FileExistsError(f"Draft folder {draft_name} already exists and replacement is not allowed")
            shutil.rmtree(draft_path)

        # Create draft folder
        os.makedirs(draft_path)
        shutil.copy(assets.get_asset_path("DRAFT_META_TEMPLATE"), os.path.join(draft_path, "draft_meta_info.json"))

        # Create draft file
        script_file = ScriptFile(width, height, fps, maintrack_adsorb)
        
        # Set save path to draft_content.json
        draft_content_path = os.path.join(draft_path, "draft_content.json")
        script_file.save_path = draft_content_path
        
        # Enable dual file compatibility mode
        script_file.dual_file_compatibility = True
        
        # Save to draft_content.json (will sync to draft_info.json automatically)
        script_file.save()

        return script_file

    def inspect_material(self, draft_name: str) -> None:
        """Inspect sticker material metadata in the specified draft

        Args:
            draft_name (`str`): Draft name (folder name)

        Raises:
            `FileNotFoundError`: Draft does not exist
        """
        draft_path = os.path.join(self.folder_path, draft_name)
        if not os.path.exists(draft_path):
            raise FileNotFoundError(f"Draft folder {draft_name} does not exist")

        script_file = self.load_template(draft_name)
        script_file.inspect_material()

    def load_template(self, draft_name: str) -> ScriptFile:
        """Open a draft from the folder as a template and start editing

        Args:
            draft_name (`str`): Draft name (folder name)

        Returns:
            `ScriptFile`: Draft object opened in template mode

        Raises:
            `FileNotFoundError`: Draft does not exist
        """
        draft_path = os.path.join(self.folder_path, draft_name)
        if not os.path.exists(draft_path):
            raise FileNotFoundError(f"Draft folder {draft_name} does not exist")

        script_file = ScriptFile.load_template(os.path.join(draft_path, "draft_content.json"))
        # Enable dual file compatibility mode to update both files on save
        script_file.dual_file_compatibility = True
        return script_file

    def duplicate_as_template(self, template_name: str, new_draft_name: str, allow_replace: bool = False) -> ScriptFile:
        """Duplicate a draft and start editing on the copy

        Args:
            template_name (`str`): Source draft name
            new_draft_name (`str`): New draft name
            allow_replace (`bool`, optional): Whether to allow overwriting existing draft. Default is False.

        Returns:
            `ScriptFile`: The **duplicated** draft object in template mode

        Raises:
            `FileNotFoundError`: Source draft does not exist
            `FileExistsError`: New draft already exists and `allow_replace` is False.
        """
        template_path = os.path.join(self.folder_path, template_name)
        new_draft_path = os.path.join(self.folder_path, new_draft_name)
        if not os.path.exists(template_path):
            raise FileNotFoundError(f"Template draft {template_name} does not exist")
        if os.path.exists(new_draft_path) and not allow_replace:
            raise FileExistsError(f"New draft {new_draft_name} already exists and replacement is not allowed")

        # Copy draft folder
        shutil.copytree(template_path, new_draft_path, dirs_exist_ok=allow_replace)

        # Open draft
        return self.load_template(new_draft_name)
