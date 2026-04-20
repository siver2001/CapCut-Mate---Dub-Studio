from enum import Enum

class CustomError(Enum):
    """Error codes and messages for the application."""
    
    # ===== Basic Error Codes (1000-1999) =====
    SUCCESS = (0, "Success")
    PARAM_VALIDATION_FAILED = (1001, "Parameter validation failed")
    RESOURCE_NOT_FOUND = (1002, "Resource not found")
    PERMISSION_DENIED = (1003, "Permission denied")
    AUTHENTICATION_FAILED = (1004, "Authentication failed")
    
    # ===== Business Error Codes (2000-2999) =====
    INVALID_DRAFT_URL = (2001, "Invalid draft URL")
    DRAFT_CREATE_FAILED = (2002, "Draft creation failed")
    INVALID_VIDEO_INFO = (2003, "Invalid video information, please check if the value of the video_infos field is correct.")
    FILE_SIZE_LIMIT_EXCEEDED = (2004, "File size exceeds the limit")
    DOWNLOAD_FILE_FAILED = (2005, "Download file failed")
    VIDEO_ADD_FAILED = (2006, "Video addition failed")
    INVALID_AUDIO_INFO = (2007, "Invalid audio information, please check if the value of the audio_infos field is correct.")
    AUDIO_ADD_FAILED = (2008, "Audio addition failed")
    INVALID_IMAGE_INFO = (2009, "Invalid image information, please check if the value of the image_infos field is correct.")
    IMAGE_ADD_FAILED = (2010, "Image addition failed")
    INVALID_STICKER_INFO = (2011, "Invalid sticker information, please check if sticker parameters are correct.")
    STICKER_ADD_FAILED = (2012, "Sticker addition failed")
    INVALID_KEYFRAME_INFO = (2013, "Invalid keyframe information, please check if the value of the keyframes field is correct.")
    KEYFRAME_ADD_FAILED = (2014, "Keyframe addition failed")
    SEGMENT_NOT_FOUND = (2015, "Segment not found, please check if the segment_id is correct.")
    INVALID_SEGMENT_TYPE = (2016, "Invalid segment type, this segment does not support keyframes.")
    INVALID_KEYFRAME_PROPERTY = (2017, "Invalid keyframe property type.")
    INVALID_CAPTION_INFO = (2018, "Invalid caption information, please check if the value of the captions field is correct.")
    CAPTION_ADD_FAILED = (2019, "Caption addition failed")
    INVALID_EFFECT_INFO = (2020, "Invalid effect information, please check if the value of the effect_infos field is correct.")
    EFFECT_ADD_FAILED = (2021, "Effect addition failed")
    EFFECT_NOT_FOUND = (2022, "Effect not found, please check if the effect name is correct.")
    INVALID_MASK_INFO = (2023, "Invalid mask information, please check if mask parameters are correct.")
    MASK_ADD_FAILED = (2024, "Mask addition failed")
    MASK_NOT_FOUND = (2025, "Mask type not found, please check if the mask name is correct.")
    INVALID_TEXT_STYLE_INFO = (2026, "Invalid text style information, please check text or keyword parameters.")
    TEXT_STYLE_CREATE_FAILED = (2027, "Text style creation failed")
    MATERIAL_CREATE_FAILED = (2028, "Material creation failed")
    TEXT_ANIMATION_GET_FAILED = (2029, "Get text animation failed")
    VIDEO_GENERATION_SUBMIT_FAILED = (2030, "Video generation task submit failed")
    VIDEO_TASK_NOT_FOUND = (2031, "Video generation task not found")
    VIDEO_STATUS_QUERY_FAILED = (2032, "Video task status query failed")
    IMAGE_ANIMATION_GET_FAILED = (2033, "Get image animation failed")
    AUDIO_DURATION_GET_FAILED = (2034, "Get audio duration failed")
    INSUFFICIENT_ACCOUNT_BALANCE = (2035, "Insufficient account balance. Minimum 1 point required.")
    INVALID_APIKEY = (2036, "Invalid API key")
    INVALID_FILTER_INFO = (2037, "Invalid filter information, please check the filter_infos field.")
    FILTER_ADD_FAILED = (2038, "Filter addition failed")
    FILTER_NOT_FOUND = (2039, "Filter not found, please check the filter name.")
    FILTER_GET_FAILED = (2040, "Get filter list failed")
    EFFECT_GET_FAILED = (2041, "Get effect list failed")
    DRAFT_LOCK_TIMEOUT = (2042, "Draft lock acquisition timeout")

    # ===== System Error Codes (9000-9999) =====
    INTERNAL_SERVER_ERROR = (9998, "Internal server error")
    UNKNOWN_ERROR = (9999, "Unknown error")

    def __init__(self, code: int, message: str) -> None:
        self.code = code
        self.message = message

    def as_dict(self, detail: str = "") -> dict:
        msg = self.message
        if detail:
            msg += f" ({detail})"
        return {"code": self.code, "message": msg}

class CustomException(Exception):
    def __init__(self, err: CustomError, detail: str = "") -> None:
        self.err = err
        self.detail = detail
        super().__init__(err.message)
