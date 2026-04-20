import os
import shutil
import datetime
import uuid
from src.utils.logger import logger
import config
import src.pyJianYingDraft as draft
from src.utils.draft_cache import update_cache
from exceptions import CustomException, CustomError


def create_draft(width: int, height: int) -> str:
    """
    Business logic for creating a new CapCut draft based on a template.
    
    Args:
        width: Canvas width.
        height: Canvas height.
        
    Returns:
        str: Draft URL with the generated draft_id.
    """
    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    unique_id = uuid.uuid4().hex[:8]
    draft_id = f"{timestamp}{unique_id}"
    
    logger.info(f"Creating draft: {draft_id}, size: {width}x{height}")
    
    try:
        template_path = os.path.join(config.TEMPLATE_DIR, 'default2')
        draft_path = os.path.join(config.DRAFT_DIR, draft_id)
        
        if os.path.exists(draft_path):
            shutil.rmtree(draft_path)
            
        shutil.copytree(template_path, draft_path)
        
        draft_info_path = os.path.join(draft_path, 'draft_info.json')
        draft_content_path = os.path.join(draft_path, 'draft_content.json')
        
        script = draft.ScriptFile.load_template(draft_info_path)
        script.dual_file_compatibility = True
        script.width, script.height = width, height
        
        # Update canvas config in content dictionary
        script.content['canvas_config']['width'] = width
        script.content['canvas_config']['height'] = height
        
        script.save_path = draft_content_path
        script.save()
        
        # Initialize main track
        main_track_name = 'main_track'
        script.add_track(track_type=draft.TrackType.video, track_name=main_track_name, relative_index=0)
        script.save()
        
        update_cache(draft_id, script)
        logger.info(f"Successfully created draft: {draft_id}")
        
        return f"{config.DRAFT_URL}?draft_id={draft_id}"
        
    except Exception as e:
        logger.error(f"Failed to create draft: {str(e)}")
        raise CustomException(CustomError.DRAFT_CREATE_FAILED)
