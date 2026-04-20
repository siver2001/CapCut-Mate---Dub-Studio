import json
import re
from typing import List, Dict, Any, Tuple
from src.utils.logger import logger


def add_text_style(
    text: str,
    keyword: str,
    font_size: int = 12,
    keyword_color: str = "#ff7100",
    keyword_font_size: int = 15
) -> str:
    """
    Create rich text style with keyword highlighting and size adjustments.
    
    Args:
        text: Original text content.
        keyword: Keywords separated by '|'.
        font_size: Default font size.
        keyword_color: Hex color for keywords.
        keyword_font_size: Font size for keywords.
        
    Returns:
        str: JSON string containing text and style information.
    """
    logger.info(f"add_text_style started for text: {text[:20]}...")

    try:
        keywords = parse_keywords(keyword)
        if not keywords:
            return create_simple_text_style(text, font_size)

        keyword_positions = find_keyword_positions(text, keywords)
        keyword_rgb = hex_to_rgb(keyword_color)
        normal_rgb = [1.0, 1.0, 1.0]

        styles = generate_text_styles(
            text,
            keyword_positions,
            font_size,
            keyword_font_size,
            normal_rgb,
            keyword_rgb
        )

        result = {
            "text": text,
            "styles": styles
        }

        return json.dumps(result, ensure_ascii=False, separators=(',', ':'))

    except Exception as e:
        logger.error(f"add_text_style failed: {str(e)}")
        raise


def parse_keywords(keyword_str: str) -> List[str]:
    """Split and sort keywords by length (longest first)."""
    if not keyword_str or not keyword_str.strip():
        return []
    keywords = [kw.strip() for kw in keyword_str.split('|') if kw.strip()]
    keywords.sort(key=len, reverse=True)
    return keywords


def find_keyword_positions(text: str, keywords: List[str]) -> List[Tuple[int, int, str]]:
    """Find non-overlapping positions of keywords in text."""
    positions = []
    used = set()

    for kw in keywords:
        for match in re.finditer(re.escape(kw), text):
            start, end = match.start(), match.end()
            if not any(p in used for p in range(start, end)):
                positions.append((start, end, kw))
                used.update(range(start, end))

    positions.sort(key=lambda x: x[0])
    return positions


def hex_to_rgb(hex_color: str) -> List[float]:
    """Convert hex color to RGB list (0-1 range)."""
    hex_color = hex_color.lstrip('#')
    if len(hex_color) != 6:
        return [1.0, 0.443, 0.0]  # Default orange
    try:
        return [int(hex_color[i:i+2], 16) / 255.0 for i in (0, 2, 4)]
    except ValueError:
        return [1.0, 0.443, 0.0]


def generate_text_styles(
    text: str,
    keyword_positions: List[Tuple[int, int, str]],
    normal_font_size: int,
    keyword_font_size: int,
    normal_color: List[float],
    keyword_color: List[float]
) -> List[Dict[str, Any]]:
    """Generate style segments for normal and highlighted text."""
    styles = []
    current_pos = 0

    for start, end, _ in keyword_positions:
        if current_pos < start:
            styles.append(create_text_style_segment(current_pos, start, normal_font_size, normal_color))
        
        styles.append(create_text_style_segment(start, end, keyword_font_size, keyword_color, True))
        current_pos = end

    if current_pos < len(text):
        styles.append(create_text_style_segment(current_pos, len(text), normal_font_size, normal_color))

    return styles


def create_text_style_segment(
    start: int,
    end: int,
    font_size: int,
    color: List[float],
    use_letter_color: bool = False
) -> Dict[str, Any]:
    """Create a single style segment dictionary."""
    style = {
        "fill": {"content": {"solid": {"color": color}}},
        "range": [start, end],
        "size": float(font_size),
        "font": {"id": "", "path": ""}
    }
    if use_letter_color:
        style["useLetterColor"] = True
    return style


def create_simple_text_style(text: str, font_size: int) -> str:
    """Create a default style for the entire text without highlights."""
    result = {
        "text": text,
        "styles": [create_text_style_segment(0, len(text), font_size, [1.0, 1.0, 1.0])]
    }
    return json.dumps(result, ensure_ascii=False, separators=(',', ':'))
