"""Custom exception classes"""

class TrackNotFound(NameError):
    """Specified track not found"""
class AmbiguousTrack(ValueError):
    """Multiple matching tracks found"""
class SegmentOverlap(ValueError):
    """New segment overlaps with existing segments on the track"""

class MaterialNotFound(NameError):
    """Specified material not found"""
class AmbiguousMaterial(ValueError):
    """Multiple matching materials found"""

class ExtensionFailed(ValueError):
    """Failed to extend segment during material replacement"""

class DraftNotFound(NameError):
    """Draft not found"""
class AutomationError(Exception):
    """Automation operation failed"""
class ExportTimeout(Exception):
    """Export timed out"""
