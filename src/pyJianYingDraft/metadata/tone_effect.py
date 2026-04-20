from .effect_meta import EffectEnum
from .effect_meta import EffectMeta, EffectParam

class ToneEffectType(EffectEnum):
    """CapCut built-in audio 'Tone' effect types"""

    # Free
    TaiwaneseGuy = EffectMeta("Taiwanese Guy", False, "7255565276819755576", "18149602", "8dd8889045e6c065177df791ddb3dfb8", [])
    ChristmasElf = EffectMeta("Christmas Elf", False, "7310059412062736946", "33214695", "8dd8889045e6c065177df791ddb3dfb8", [])
    SantaClaus   = EffectMeta("Santa Claus", False, "7310059178133819930", "33214489", "8dd8889045e6c065177df791ddb3dfb8", [])
    AdMale       = EffectMeta("Ad Male", False, "7328088579811316263", "42060748", "f554735f65a98cc4da17a1c53ef6a886", [])
    HKMale       = EffectMeta("HK Male", False, "7328087687548637732", "42060743", "f554735f65a98cc4da17a1c53ef6a886", [])
    OldLady      = EffectMeta("Old Lady", False, "7328089253114548799", "42060746", "f554735f65a98cc4da17a1c53ef6a886", [])
    Xiaoshuai    = EffectMeta("Xiaoshuai", False, "7332473259369173540", "44254166", "f554735f65a98cc4da17a1c53ef6a886", [])
    Uncle        = EffectMeta("Uncle", False, "7020344898033291790", "2672760", "2509bbd71e127b04a29f52a54e82c53c", [
                                    EffectParam("Pitch", 0.834, 0.000, 1.000),
                                    EffectParam("Timbre", 1.000, 0.000, 1.000)])
    """Params:
        - Pitch: Default 0.83, 0.00 ~ 1.00
        - Timbre: Default 1.00, 0.00 ~ 1.00
    """
    Female       = EffectMeta("Female", False, "7020345715901600270", "2672757", "0ce1aade5958506c97bffea150772b6e", [
                                    EffectParam("Pitch", 0.834, 0.000, 1.000),
                                    EffectParam("Timbre", 0.334, 0.000, 1.000)])
    """Params:
        - Pitch: Default 0.83, 0.00 ~ 1.00
        - Timbre: Default 0.33, 0.00 ~ 1.00
    """
    Monster      = EffectMeta("Monster", False, "7020344978794615327", "2672759", "2130ffa21e5980196e014ec0baade179", [
                                    EffectParam("Pitch", 0.650, 0.000, 1.000),
                                    EffectParam("Timbre", 0.780, 0.000, 1.000)])
    """Params:
        - Pitch: Default 0.65, 0.00 ~ 1.00
        - Timbre: Default 0.78, 0.00 ~ 1.00
    """
    Robot        = EffectMeta("Robot", False, "7018011705414259213", "2672750", "4b87db25aecd2f6f71927930110c4a1e", [
                                    EffectParam("Strength", 1.000, 0.000, 1.000)])
    """Params:
        - Strength: Default 1.00, 0.00 ~ 1.00
    """
    Male         = EffectMeta("Male", False, "7020345085233467917", "2672758", "ffd7a609207fd849efc9f63bf31697b1", [
                                    EffectParam("Pitch", 0.375, 0.000, 1.000),
                                    EffectParam("Timbre", 0.250, 0.000, 1.000)])
    """Params:
        - Pitch: Default 0.38, 0.00 ~ 1.00
        - Timbre: Default 0.25, 0.00 ~ 1.00
    """
    Chipmunk     = EffectMeta("Chipmunk", False, "7018011553081332231", "2672752", "e30b1922b8300423f21f9f84eff41ced", [
                                    EffectParam("Pitch", 0.500, 0.000, 1.000),
                                    EffectParam("Timbre", 0.500, 0.000, 1.000)])
    """Params:
        - Pitch: Default 0.50, 0.00 ~ 1.00
        - Timbre: Default 0.50, 0.00 ~ 1.00
    """
    Loli         = EffectMeta("Loli", False, "7020345789599715848", "2672756", "00b7ed2ccfe4d6076f78c8d751347a53", [
                                    EffectParam("Pitch", 0.750, 0.000, 1.000),
                                    EffectParam("Timbre", 0.600, 0.000, 1.000)])
    """Params:
        - Pitch: Default 0.75, 0.00 ~ 1.00
        - Timbre: Default 0.60, 0.00 ~ 1.00
    """


    # Paid
    TVBFemale    = EffectMeta("TVB Female", True, "7260024060417937978", "19186454", "8dd8889045e6c065177df791ddb3dfb8", [])
    Eunuch       = EffectMeta("Eunuch", True, "7328092524612948491", "42060742", "f554735f65a98cc4da17a1c53ef6a886", [])
    Yunlong      = EffectMeta("Yunlong", True, "7376558114830553612", "68856989", "f554735f65a98cc4da17a1c53ef6a886", [])
    Knight       = EffectMeta("Knight", True, "7328089134331859468", "42060738", "f554735f65a98cc4da17a1c53ef6a886", [])
    Artificial   = EffectMeta("Artificial", True, "7367676929496846911", "63231108", "f554735f65a98cc4da17a1c53ef6a886", [])
    Bajie        = EffectMeta("Bajie", True, "7265891792766112314", "20427371", "8dd8889045e6c065177df791ddb3dfb8", [])
    Military     = EffectMeta("Military", True, "7328092289480266252", "42060734", "f554735f65a98cc4da17a1c53ef6a886", [])
    AnimeShin    = EffectMeta("Anime Shin", True, "7360901047662940708", "58979441", "f554735f65a98cc4da17a1c53ef6a886", [])
    AnimeSponge  = EffectMeta("Anime Sponge", True, "7367676859883983379", "63231109", "f554735f65a98cc4da17a1c53ef6a886", [])
    Roar         = EffectMeta("Roar", True, "7332473122605503039", "44254278", "f554735f65a98cc4da17a1c53ef6a886", [])
    Business     = EffectMeta("Business", True, "7328085477267870249", "42060747", "f554735f65a98cc4da17a1c53ef6a886", [])
    Silang       = EffectMeta("Silang", True, "7250403044414722621", "16627073", "8dd8889045e6c065177df791ddb3dfb8", [])
    Taibai       = EffectMeta("Taibai", True, "7328091247308968484", "42060736", "f554735f65a98cc4da17a1c53ef6a886", [])
    Buddha       = EffectMeta("Buddha", True, "7376558174049931830", "68856990", "f554735f65a98cc4da17a1c53ef6a886", [])
    Gingerbread  = EffectMeta("Gingerbread", True, "7310059267384414747", "33214539", "8dd8889045e6c065177df791ddb3dfb8", [])
    Nanny        = EffectMeta("Nanny", True, "7332472945366798860", "44254320", "f554735f65a98cc4da17a1c53ef6a886", [])
    Child        = EffectMeta("Child", True, "7262648951948448315", "19716244", "8dd8889045e6c065177df791ddb3dfb8", [])
    StrongGirl   = EffectMeta("Strong Girl", True, "7328091624427229759", "42060740", "f554735f65a98cc4da17a1c53ef6a886", [])
    Clapper      = EffectMeta("Clapper", True, "7328088454183522827", "42060741", "f554735f65a98cc4da17a1c53ef6a886", [])
    Horror       = EffectMeta("Horror", True, "7325710953247412787", "40932465", "f554735f65a98cc4da17a1c53ef6a886", [])
    Suspense     = EffectMeta("Suspense", True, "7325711304390349362", "40932811", "f554735f65a98cc4da17a1c53ef6a886", [])
    LazyLamb     = EffectMeta("Lazy Lamb", True, "7332473035116515859", "44254304", "f554735f65a98cc4da17a1c53ef6a886", [])
    Funny        = EffectMeta("Funny", True, "7262648842238038584", "19716150", "8dd8889045e6c065177df791ddb3dfb8", [])
    Literary     = EffectMeta("Literary", True, "7379565719991620132", "70562787", "f554735f65a98cc4da17a1c53ef6a886", [])
    Maruko       = EffectMeta("Maruko", True, "7325709643332719113", "40931609", "f554735f65a98cc4da17a1c53ef6a886", [])
    SakuraGuy    = EffectMeta("Sakura Guy", True, "7328091741678998055", "42060735", "f554735f65a98cc4da17a1c53ef6a886", [])
    WuZetian     = EffectMeta("Wu Zetian", True, "7328088300474864167", "42060744", "f554735f65a98cc4da17a1c53ef6a886", [])
    Steady       = EffectMeta("Steady", True, "7367676791164506636", "63231110", "f554735f65a98cc4da17a1c53ef6a886", [])
    GentleSister = EffectMeta("Gentle Sister", True, "7379565769190806079", "70562785", "f554735f65a98cc4da17a1c53ef6a886", [])
    Xionger      = EffectMeta("Xionger", True, "7250403222798471740", "16627311", "8dd8889045e6c065177df791ddb3dfb8", [])
    Monkey       = EffectMeta("Monkey", True, "7236944659547689531", "14477015", "4f6a1fbc0000e178c724d355efea1d9f", [])
    Sweet        = EffectMeta("Sweet", True, "7325710673978069530", "40932253", "f554735f65a98cc4da17a1c53ef6a886", [])
    Tips         = EffectMeta("Tips", True, "7328092409525441065", "42060737", "f554735f65a98cc4da17a1c53ef6a886", [])
    E_Sports     = EffectMeta("E-Sports", True, "7325711893551649330", "40933559", "f554735f65a98cc4da17a1c53ef6a886", [])
    TVAd         = EffectMeta("TV Ad", True, "7360901109667336743", "58979440", "f554735f65a98cc4da17a1c53ef6a886", [])
    Ziwei        = EffectMeta("Ziwei", True, "7281175506391667257", "23475307", "8dd8889045e6c065177df791ddb3dfb8", [])
    Gourmet      = EffectMeta("Gourmet", True, "7328091500753982015", "42060739", "f554735f65a98cc4da17a1c53ef6a886", [])
    CrayonNini   = EffectMeta("Crayon Nini", True, "7379565670398169619", "70562786", "f554735f65a98cc4da17a1c53ef6a886", [])
    VoiceAssistant = EffectMeta("Voice Assistant", True, "7325710335455793714", "40931973", "f554735f65a98cc4da17a1c53ef6a886", [])
    Najie        = EffectMeta("Najie", True, "7369177370873303587", "64206631", "f554735f65a98cc4da17a1c53ef6a886", [])
    HammerGuy    = EffectMeta("Hammer Guy", True, "7328091348098093580", "42060745", "f554735f65a98cc4da17a1c53ef6a886", [])
    Gujie        = EffectMeta("Gujie", True, "7250403134923608631", "16627197", "8dd8889045e6c065177df791ddb3dfb8", [])
    Daiyu        = EffectMeta("Daiyu", True, "7255565592093004343", "18149634", "8dd8889045e6c065177df791ddb3dfb8", [])
