"""
Valtec Vietnamese TTS - Text to Speech for Vietnamese

Simple usage:
    from valtec_tts import TTS
    
    tts = TTS()
    tts.speak("Xin chào các bạn", output_path="output.wav")
"""

__version__ = "1.0.0"
__author__ = "Valtec Team"

from .tts import TTS

try:
    from .zeroshot import ZeroShotTTS
except ImportError:
    ZeroShotTTS = None

__all__ = ["TTS", "ZeroShotTTS", "__version__"]
