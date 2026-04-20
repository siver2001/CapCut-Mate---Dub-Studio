"""Video mask metadata"""

from .effect_meta import EffectEnum, MaskMeta

class MaskType(EffectEnum):
    """Mask type"""

    Line = MaskMeta("Line", "line", "6791652175668843016", "636071", "1f467b8b9bb94cecc46d916219b7940a", 1.0)
    """Default blocks lower part"""
    Mirror = MaskMeta("Mirror", "mirror", "6791699060140020232", "636073", "b2c0516d1f737f4542fb9b2862907817", 1.0)
    """Default keeps part between two lines"""
    Circle = MaskMeta("Circle", "circle", "6791700663249146381", "636075", "9a55eae0e99ee6d1ecbc6defaf0501ec", 1.0)
    Rectangle = MaskMeta("Rectangle", "rectangle", "6791700809454195207", "636077", "ef361d96c456cd6077c76d737f98898d", 1.0)
    Heart = MaskMeta("Heart", "geometric_shape", "6794051276482023949", "636079", "0bf09fa1e3a32464fed4f71e49a8ab01", 1.115)
    Star = MaskMeta("Star", "geometric_shape", "6794051169434997255", "636081", "155612dee601d3f5422a3fbeabc7610c", 1.05)
