from .effect_meta import EffectEnum
from .effect_meta import EffectMeta

class SpeechToSongType(EffectEnum):
    """CapCut's built-in 'Speech to Song' audio effect types. These effects are currently not automatically recognized by CapCut."""

    Lofi = EffectMeta("Lofi", False, "7252917861948068410", "17345060", "8dd8889045e6c065177df791ddb3dfb8", [])
    Folk = EffectMeta("Folk", False, "7251868698170888759", "17046923", "8dd8889045e6c065177df791ddb3dfb8", [])
    HipHop = EffectMeta("HipHop", True, "7252918249036190245", "17344948", "8dd8889045e6c065177df791ddb3dfb8", [])
    Jazz = EffectMeta("Jazz", True, "7264413578860433978", "20120940", "8dd8889045e6c065177df791ddb3dfb8", [])
    RnB = EffectMeta("RnB", True, "7252918101958726200", "17345046", "8dd8889045e6c065177df791ddb3dfb8", [])
    Reggae = EffectMeta("Reggae", True, "7264413386962637368", "20120864", "8dd8889045e6c065177df791ddb3dfb8", [])
