"""Transition effect metadata"""

from .effect_meta import EffectEnum, TransitionMeta

class TransitionType(EffectEnum):
    """Transition type"""

    # Free effects
    _3DSpace = TransitionMeta("3DSpace", False, "7049979667406656014", "1506926", "aaecc038f6543411f601608fc5539f0b", 1.500, True)
    """Default duration: 1.50s"""
    UpDownPageFlip = TransitionMeta("UpDownPageFlip", False, "7397337005387944457", "77055399", "091f7995a43fc66fd0a95b2a6b88834f", 1.000, True)
    """Default duration: 1.00s"""
    UpMove = TransitionMeta("UpMove", False, "6724846395116753416", "2917279", "df9bc16697464de201a4924de49234a2", 0.500, True)
    """Default duration: 0.50s"""
    DownMove = TransitionMeta("DownMove", False, "6724849276100284942", "2917280", "9c042543d4846e7c17e8f950ce6f91c2", 0.500, True)
    """Default duration: 0.50s"""
    CenterRotate = TransitionMeta("CenterRotate", False, "6858191434294497805", "878914", "b43f5b2e59f966a3b110222773c2942d", 0.500, False)
    """Default duration: 0.50s"""
    Cloud = TransitionMeta("Cloud", False, "6955722927161479694", "2912469", "283bb4bbe729f19f933cb705024a0983", 0.500, True)
    """Default duration: 0.50s"""
    Reflection = TransitionMeta("Reflection", False, "6748313807031898627", "369691", "0ee10b771dc0443c41a90bb9fd6b3c25", 0.500, True)
    """Default duration: 0.50s"""
    IceCrystal = TransitionMeta("IceCrystal", False, "6919369228701143559", "1017910", "a0fd9d6eb0cb5596cac4f54d0ba59eaf", 0.500, False)
    """Default duration: 0.50s"""
    Charge = TransitionMeta("Charge", False, "7030714241359286821", "1441672", "784b284f040f61ae95f4e8e660f3a873", 0.500, False)
    """Default duration: 0.50s"""
    Split = TransitionMeta("Split", False, "6968372308419285540", "4211683", "ca45695f29bacf2dc29a6eb959e9e968", 0.500, True)
    """Default duration: 0.50s"""
    Split_II = TransitionMeta("Split II", False, "6969782622868214302", "4211740", "5ba1cb89bcf4a0898f86494864348e13", 0.500, True)
    """Default duration: 0.50s"""
    Split_III = TransitionMeta("Split III", False, "6969793843403166215", "4211739", "942fd71d67ca576384b2cd068157ca45", 0.500, True)
    """Default duration: 0.50s"""
    Split_IV = TransitionMeta("Split IV", False, "6969793934356648455", "4211738", "62d08c08542fe62e6a8429f9501e76fa", 0.500, True)
    """Default duration: 0.50s"""
    BeforeAfterComparison_II = TransitionMeta("BeforeAfterComparison II", False, "7299290706277831218", "28895844", "64e8f4a060901fd4349301f97fbdd172", 0.800, True)
    """Default duration: 0.80s"""
    AnimeCloud = TransitionMeta("AnimeCloud", False, "6777178865119793678", "2911876", "e835cbc7fa7b15af90a2a7090bbf68c3", 0.500, False)
    """Default duration: 0.50s"""
    AnimeVortex = TransitionMeta("AnimeVortex", False, "6858191448827761160", "878913", "fa7ba99b13036c0ff167ea3b7d5c31a2", 0.500, False)
    """Default duration: 0.50s"""
    AnimeFlame = TransitionMeta("AnimeFlame", False, "6777178765643485709", "2911875", "8e7c247c5ebd58aa5c3582273e9c840b", 0.500, False)
    """Default duration: 0.50s"""
    AnimeLightning = TransitionMeta("AnimeLightning", False, "6777178696609436174", "2911874", "3fd5d0c7c48668ba5305c57ac0b5d596", 0.500, False)
    """Default duration: 0.50s"""
    Compress = TransitionMeta("Compress", False, "6751618376780485133", "4212466", "337d4cd9be4e1860bd1e7e50a9a93841", 0.500, True)
    """Default duration: 0.50s"""
    Overlay = TransitionMeta("Overlay", False, "6914112332205396488", "1003369", "4f7e4bd421e382860b49e3e34eb4e4aa", 1.000, True)
    """Default duration: 1.00s"""
    Dissolve = TransitionMeta("Dissolve", False, "6724845717472416269", "322577", "2d641adc4bb63e37e3a0067d8c8cc3c3", 0.500, True)
    """Default duration: 0.50s"""
    RightMove = TransitionMeta("RightMove", False, "6726711296063967748", "2917287", "4cfd965c25e33c7df9b2c1b3b4cbdf31", 1.000, True)
    """Default duration: 1.00s"""
    Up = TransitionMeta("Up", False, "6724227090872275463", "359459", "349746a951e130fe896415f51c9eb36a", 1.000, False)
    """Default duration: 1.00s"""
    UpWipe = TransitionMeta("UpWipe", False, "6724849456891564557", "2917281", "9a2e4ebf7309c80be332e3c62594dcd6", 0.500, True)
    """Default duration: 0.50s"""
    Down = TransitionMeta("Down", False, "6724227330190873100", "359449", "9c263958ef3b5762db6ffd94a665f9e8", 1.000, False)
    """Default duration: 1.00s"""
    DownWipe = TransitionMeta("DownWipe", False, "6724849752921346573", "2917282", "ce1fb8739d1fbff3d86498fc18321933", 0.500, True)
    """Default duration: 0.50s"""
    DownFlow = TransitionMeta("DownFlow", False, "6858191469807669773", "878912", "45f28ed2995ca15cfe027784b55d34f2", 0.500, False)
    """Default duration: 0.50s"""
    Right = TransitionMeta("Right", False, "6724227599616184836", "359527", "55af58a9b04ff458c3a9ae3ddb358152", 1.000, False)
    """Default duration: 1.00s"""
    RightUp = TransitionMeta("RightUp", False, "6724227870559834635", "359567", "19d72649fe9bc3b272e1d874a93a0e9b", 0.500, True)
    """Default duration: 0.50s"""
    RightDown = TransitionMeta("RightDown", False, "6724228621742903815", "359537", "4291e21aefc6d87a232441d38cabacc5", 0.500, True)
    """Default duration: 0.50s"""
    RightStretch = TransitionMeta("RightStretch", False, "6987299127025472031", "4211782", "6c3d17aa182e6238ee3a48c2fdf4a627", 0.500, True)
    """Default duration: 0.50s"""
    RightWipe = TransitionMeta("RightWipe", False, "6724849898857959950", "2917284", "a10153bd2b569c49ddd7c055e8c9eba9", 0.500, True)
    """Default duration: 0.50s"""
    RightFlow = TransitionMeta("RightFlow", False, "6858191483573375495", "878911", "8d3508f6e570dc73d3e771d234796cb8", 0.500, False)
    """Default duration: 0.50s"""
    Left = TransitionMeta("Left", False, "6724227717195108867", "359529", "323fadc45da03741e6b393b3e3b34e75", 0.500, False)
    """Default duration: 0.50s"""
    LeftUp = TransitionMeta("LeftUp", False, "6724230442679013902", "359533", "4ed73d43829eb496f6885ac0b882a391", 0.500, True)
    """Default duration: 0.50s"""
    LeftDown = TransitionMeta("LeftDown", False, "6724230577211314695", "359535", "c76650d4ea9bc4e3b0530c9b9f05f28e", 0.500, True)
    """Default duration: 0.50s"""
    LeftStretch = TransitionMeta("LeftStretch", False, "6987201429622493732", "4211781", "b0dd96c3c203104a2df46d83dd91b7bd", 0.500, True)
    """Default duration: 0.50s"""
    LeftWipe = TransitionMeta("LeftWipe", False, "6724849999336706573", "2917283", "316c2a1c1783f51505c793b13381b445", 0.500, True)
    """Default duration: 0.50s"""
    Inhale = TransitionMeta("Inhale", False, "7246288124110705209", "15653345", "fb75bf696e19a04795ae9a06b43a09f2", 1.000, True)
    """Default duration: 1.00s"""
    MemoryDownSlide = TransitionMeta("MemoryDownSlide", False, "7309840407406318117", "33106283", "7e8f1b10bb9979d7ed184d29f301b93d", 1.000, True)
    """Default duration: 1.00s"""
    CircleSplit_II = TransitionMeta("CircleSplit II", False, "7317206886053319194", "37127313", "05017adee9a3798b4fb207bb3206187e", 0.800, True)
    """Default duration: 0.80s"""
    CircleScan = TransitionMeta("CircleScan", False, "6851775006418932238", "813992", "0260ab98d7a840c3344cb5b3e70b7d4b", 1.000, True)
    """Default duration: 1.00s"""
    CircleMask = TransitionMeta("CircleMask", False, "6725767129519362573", "2916676", "a7eb1d47f97049b17f49669622d07f3d", 0.500, True)
    """Default duration: 0.50s"""
    CircleMask_II = TransitionMeta("CircleMask II", False, "6724850215364334083", "2916675", "2772ad7c8c7e30c6421be7c2e5dd3f15", 1.000, True)
    """Default duration: 1.00s"""
    RetroProjection = TransitionMeta("RetroProjection", False, "7237068402945167909", "14192091", "44c3d405f4961d843c74c69e241df643", 0.600, True)
    """Default duration: 0.60s"""
    YearsTrace = TransitionMeta("YearsTrace", False, "6982750240663147044", "1185194", "0b228af1ebde4909bb6ff545ddd89023", 1.000, True)
    """Default duration: 1.00s"""
    LeftDown_II = TransitionMeta("LeftDown角 II", False, "7304868316252738098", "30874190", "e0296196f0ec6666a33b33fead4f63d6", 0.700, True)
    """Default duration: 0.70s"""
    LeftMove = TransitionMeta("LeftMove", False, "6726711499676455435", "2917286", "9562c0ea301229d43f9dca6f6590f306", 1.000, True)
    """Default duration: 1.00s"""
    Opening = TransitionMeta("Opening", False, "6750893890712113677", "391781", "d5f097e701ddaa984a590249896fc51a", 0.500, True)
    """Default duration: 0.50s"""
    BarrageTransition = TransitionMeta("BarrageTransition", False, "7028877116259176974", "1433950", "7b5385070a42a218f194d9daddb59f32", 4.000, False)
    """Default duration: 4.00s"""
    Bounce = TransitionMeta("Bounce", False, "6747865141120864779", "368205", "4b3b8b53bc1f947d57a30489d81387eb", 0.500, True)
    """Default duration: 0.50s"""
    ClapperTransition_I = TransitionMeta("ClapperTransition I", False, "7028143517570437668", "1432322", "355d5c4df581f6c4940c9b999e010f81", 4.000, False)
    """Default duration: 4.00s"""
    ClapperTransition_II = TransitionMeta("ClapperTransition II", False, "7029592645538157086", "1437264", "021dfc9a6541d8d08bac631749f9e87d", 4.000, False)
    """Default duration: 4.00s"""
    Shake = TransitionMeta("Shake", False, "7252544245444121148", "17223925", "a1b79bbc99afca7c9e5372cd050ad61d", 0.800, True)
    """Default duration: 0.80s"""
    Shake_II = TransitionMeta("Shake II", False, "7252544309830881851", "17223924", "37319b02a398332e7159f323ea93ba88", 0.800, True)
    """Default duration: 0.80s"""
    KeyingRotate = TransitionMeta("KeyingRotate", False, "7386584387128660506", "73423370", "290a8f067f8039b1060df3d1e8d07ca0", 0.800, True)
    """Default duration: 0.80s"""
    Stretch = TransitionMeta("Stretch", False, "7231391397717217851", "13402655", "4fd21b4a2e6382ee8851c51c8f65ed73", 1.200, True)
    """Default duration: 1.20s"""
    Stretch_II = TransitionMeta("Stretch II", False, "7259735372039459389", "19137130", "d28fee612c51edf28da804983d220f8d", 0.600, True)
    """Default duration: 0.60s"""
    Stretch_1 = TransitionMeta("Stretch远", False, "6724226338418332167", "359365", "9661d5321722495c0a98959a0d617b0f", 1.000, False)
    """Default duration: 1.00s"""
    Camera = TransitionMeta("Camera", False, "7100849808784495135", "2057168", "b64bebe75d492161875d4fd54725b31d", 0.500, True)
    """Default duration: 0.50s"""
    ZoomIn = TransitionMeta("ZoomIn", False, "6724226861666144779", "359359", "4d5a316f2eae582e7d0604b47feb8c32", 1.000, False)
    """Default duration: 1.00s"""
    TornPaperStretch = TransitionMeta("TornPaperStretch屏", False, "7254847807465460280", "17934952", "c500d2310388b63f3a4e66ff0b15f6dc", 0.700, True)
    """Default duration: 0.70s"""
    Radiation = TransitionMeta("Radiation", False, "6724239584663704071", "4212630", "06cc8d49c558d57e21207f68a6a7dbc0", 1.000, True)
    """Default duration: 1.00s"""
    Glitch = TransitionMeta("Glitch", False, "6725771847444468236", "2918080", "7bec08ae5dae8806e3ba0c66622d0fd3", 1.000, False)
    """Default duration: 1.00s"""
    Glitch_1 = TransitionMeta("Glitch拼贴", False, "7397337004507140618", "77055395", "305fc94470ded4f5b633c80fb4112582", 1.000, True)
    """Default duration: 1.00s"""
    Split_1 = TransitionMeta("斜Split", False, "7085250093527339557", "4211687", "6ae9eb3ee4b08afa67e3d079a2ece505", 0.500, True)
    """Default duration: 0.50s"""
    Star = TransitionMeta("Star", False, "6751564373317128708", "2916678", "5ad3a484b1784e3f5391bf3fa7b188f4", 0.500, True)
    """Default duration: 0.50s"""
    Star_II = TransitionMeta("Star II", False, "6789847494898487822", "2916679", "16a4697aef243c1524e9581fb2f038c9", 0.500, True)
    """Default duration: 0.50s"""
    Blur = TransitionMeta("Blur", False, "6911569618171597320", "4212596", "fc1352435f88c6f284b6c6dce8552ffe", 0.500, True)
    """Default duration: 0.50s"""
    Split_2 = TransitionMeta("横Split", False, "7083771238564237861", "4211685", "aa0aa4a72fc236611d3fd4bf75a12ca3", 0.500, True)
    """Default duration: 0.50s"""
    Stretch_2 = TransitionMeta("横Stretch幕", False, "6724492948144132621", "2917278", "de63aa2d5225bb6a65b5bab8702aa1f5", 1.000, True)
    """Default duration: 1.00s"""
    Blur_1 = TransitionMeta("横Blur", False, "7450031573958660645", "97482744", "38f584c24f4383e9d10037ad4ce6fa00", 0.500, True)
    """Default duration: 0.50s"""
    Line = TransitionMeta("Line", False, "6724845810892149251", "2918076", "36c1c8edb0171ea082c98d38ffa8bd36", 0.500, True)
    """Default duration: 0.50s"""
    BubbleTransition = TransitionMeta("BubbleTransition", False, "7028880945671311903", "1433968", "66489506132d1314f3c7264bcd947cad", 4.000, False)
    """Default duration: 4.00s"""
    Ink = TransitionMeta("Ink", False, "6789847231873683976", "521328", "d1dd3dd8905f0b96be756bd34be1a84d", 0.500, True)
    """Default duration: 0.50s"""
    RippleRoll = TransitionMeta("RippleRoll", False, "6858191497280360973", "878910", "cf9bac91349a227a6155eca9d94a8af8", 0.500, False)
    """Default duration: 0.50s"""
    RippleRight = TransitionMeta("RippleRight", False, "6858191510865711629", "878909", "e9301bacebc6dc444aa4e6f835dd4a31", 0.500, False)
    """Default duration: 0.50s"""
    RippleLeft = TransitionMeta("RippleLeft", False, "6858191524312650248", "878908", "6b6499879310b6d29e9595799829cb15", 0.500, False)
    """Default duration: 0.50s"""
    Glow = TransitionMeta("Glow", False, "6914112263645303303", "4202527", "c978e2e22e9a9768813f5fd8d486b792", 1.000, True)
    """Default duration: 1.00s"""
    Whiteout = TransitionMeta("Whiteout", False, "6949828109663212045", "4202528", "1bf6b83628ff6416a4d87865107b739e", 1.000, False)
    """Default duration: 1.00s"""
    PolkaDotRight = TransitionMeta("PolkaDotRight", False, "6858191541706428941", "878907", "74c13e6250cdff7a4e860625d1098e0c", 0.500, False)
    """Default duration: 0.50s"""
    GradientWipe = TransitionMeta("GradientWipe", False, "6919369138800431629", "1017911", "2fff9b60c929559bce574ab8ef2c14a7", 1.000, True)
    """Default duration: 1.00s"""
    Slide = TransitionMeta("Slide", False, "6757982416649851399", "4212349", "b99916e2936aeb2e56892ca617888694", 1.000, True)
    """Default duration: 1.00s"""
    Vortex = TransitionMeta("Vortex", False, "6851810799510360583", "4211780", "31d2de43e6711a9eeb831d60529d0393", 1.000, False)
    """Default duration: 1.00s"""
    SmokeTransition = TransitionMeta("SmokeTransition", False, "7450031574923350555", "97482746", "67dc647cf7b1c45ada91d32bebc2bde7", 1.500, True)
    """Default duration: 1.50s"""
    Heart = TransitionMeta("Heart", False, "6748289440130535947", "2916677", "2382e2096918b63a0f8e75f720d7d892", 0.500, True)
    """Default duration: 0.50s"""
    Heart_II = TransitionMeta("Heart II", False, "6789846472343949837", "2916682", "0c04684566638932cb6f6d86cdfabda6", 0.500, True)
    """Default duration: 0.50s"""
    HeartUp = TransitionMeta("HeartUp升", False, "6789846246069637640", "2916681", "2a3c5439ce79e6113843a2b7135bd21a", 0.500, True)
    """Default duration: 0.50s"""
    TVGlitch_I = TransitionMeta("TVGlitch I", False, "7046293801123451405", "2918081", "feaf2e85b909a123ea71728f9b61fb03", 1.600, True)
    """Default duration: 1.60s"""
    TVGlitch_II = TransitionMeta("TVGlitch II", False, "7042278078415901192", "2918082", "a082bdaea1122bbf1aba730278d50250", 1.600, True)
    """Default duration: 1.60s"""
    BrushWipe = TransitionMeta("BrushWipe", False, "6789846828788486664", "2912467", "4fafb5343d5c9e726278e90b5e0c1c93", 0.500, True)
    """Default duration: 0.50s"""
    WhiteLightFlash = TransitionMeta("WhiteLightFlash", False, "7343136487182963211", "49272367", "c1f7073a94d22565ace1ab3023d1c154", 0.400, True)
    """Default duration: 0.40s"""
    WhiteInkFlower = TransitionMeta("WhiteInkFlower", False, "6858191556055142919", "878906", "775ccf71576e2b8fb075f0e61e980923", 0.500, False)
    """Default duration: 0.50s"""
    WhiteSmoke = TransitionMeta("WhiteSmoke", False, "6885646856672514567", "947664", "9b679b32ec03c42932fa37b10c141bda", 0.500, False)
    """Default duration: 0.50s"""
    Blinds = TransitionMeta("Blinds", False, "6789847331060584974", "521326", "9f37c3f6f5e84b37b3a0560803a16c30", 0.500, True)
    """Default duration: 0.50s"""
    Blink = TransitionMeta("Blink", False, "6864867302936941064", "2917719", "bf695506c8091f7a01ee7b1323a4d601", 0.500, True)
    """Default duration: 0.50s"""
    Split_3 = TransitionMeta("矩形Split", False, "6858191571196580359", "878905", "82d6235324f8c5f830f8ccf7b1cc036b", 0.500, False)
    """Default duration: 0.50s"""
    Item_0 = TransitionMeta("窗格", False, "6747989545448378888", "368721", "cd6a7ff53319efa1c57690f61c8737a0", 0.500, True)
    """Default duration: 0.50s"""
    Item_0_1 = TransitionMeta("立方体", False, "6785042367498949127", "519784", "be45578bb628a21eaae268a8d8df868f", 0.500, True)
    """Default duration: 0.50s"""
    Split_4 = TransitionMeta("竖Split", False, "7083771107706147364", "4211686", "7cc017d4e1b6ab58ec4b6900432522ff", 0.500, True)
    """Default duration: 0.50s"""
    Stretch_3 = TransitionMeta("竖Stretch幕", False, "6726711903684399619", "2917285", "84f91be5a43cc6a9d03505a465418206", 1.000, True)
    """Default duration: 1.00s"""
    Blur_2 = TransitionMeta("竖Blur", False, "7125661387568714247", "3796327", "cda4099e3f207ef1509f27d0b1ab01c1", 0.800, True)
    """Default duration: 0.80s"""
    Blur_II = TransitionMeta("竖Blur II", False, "7280837008421818936", "23404229", "85e381982a94778e003f3acc9527d5cf", 0.660, True)
    """Default duration: 0.66s"""
    Item_0_2 = TransitionMeta("竖线", False, "6724846536041173511", "2918077", "75019c1486b2366675d95602f58430e2", 0.500, True)
    """Default duration: 0.50s"""
    Right_1 = TransitionMeta("箭头Right", False, "6858191587554365966", "878904", "fa0cfb9e822393af86c6df4a8477cd63", 0.500, False)
    """Default duration: 0.50s"""
    Item_0_3 = TransitionMeta("粒子", False, "6855565313715474952", "4212632", "389d08f0700dd3e646a1e92289d84d58", 0.500, True)
    """Default duration: 0.50s"""
    Flip = TransitionMeta("Flip篇", False, "7034446419641504264", "4212350", "e3a2c5e0bd63416b5f64e489beb8a702", 1.300, True)
    """Default duration: 1.30s"""
    PageFlip = TransitionMeta("PageFlip", False, "6747979085894390279", "368701", "2f157ee5d78c197efc26f8ed37490573", 0.500, True)
    """Default duration: 0.50s"""
    Item_0_4 = TransitionMeta("色差逆时针", False, "6940500629013926413", "1069274", "b235f0bc4c9eb6e090358c09c7b0ffb0", 1.000, False)
    """Default duration: 1.00s"""
    Item_0_5 = TransitionMeta("色差顺时针", False, "6940520116035523080", "1069374", "8661a7a8b19762d35506cd6513d8ed3e", 1.000, False)
    """Default duration: 1.00s"""
    Item_0_6 = TransitionMeta("色彩溶解", False, "6724846004274729480", "322583", "b5f962a334dcc141bbc3dae0f5777564", 0.500, True)
    """Default duration: 0.50s"""
    _II = TransitionMeta("色彩溶解 II", False, "6724866927933526542", "322625", "8179e342f9b24dd1817c56f7ef1f8f9b", 1.000, True)
    """Default duration: 1.00s"""
    _III = TransitionMeta("色彩溶解 III", False, "6724867032312975875", "322627", "293a03bd140d09b0c616f879bda235e1", 1.000, True)
    """Default duration: 1.00s"""
    Item_0_7 = TransitionMeta("蓝色线条", False, "6858191605384352263", "878903", "d4d2996c3f6cf97fb8602f825d98a4da", 0.500, False)
    """Default duration: 0.50s"""
    Rotate = TransitionMeta("逆时针Rotate", False, "6724226603372515853", "359437", "048170ae8df06f9d6964691b1e472c6a", 0.500, True)
    """Default duration: 0.50s"""
    Rotate_II = TransitionMeta("逆时针Rotate II", False, "7252544659245765179", "17224251", "1b2c634ea54e81de34cb6d31848908af", 0.800, True)
    """Default duration: 0.80s"""
    Flip_1 = TransitionMeta("镜像Flip转", False, "6848792278710882824", "2917288", "1109c08965141f90b9174c38e85c8cab", 1.000, False)
    """Default duration: 1.00s"""
    Item_0_8 = TransitionMeta("闪白", False, "6724845376098013708", "322575", "9732e719b858a6dbb648d4fb459fde08", 0.500, False)
    """Default duration: 0.50s"""
    _II_1 = TransitionMeta("闪白 II", False, "7306818286413419017", "31619869", "9a1089fc9fefe2a79a71c37c1bc5831a", 0.300, True)
    """Default duration: 0.30s"""
    Item_0_9 = TransitionMeta("闪黑", False, "6724239388189921806", "321493", "3bca53e9f3dfa2c184fbee96438ea097", 0.500, False)
    """Default duration: 0.50s"""
    Glitch_2 = TransitionMeta("雪花Glitch", False, "6724866446842663431", "2918079", "71cabe836d9c88afd44f43654ba67fa7", 1.000, False)
    """Default duration: 1.00s"""
    Item_0_10 = TransitionMeta("雾化", False, "7216171159589491259", "11387229", "945e1560e2c65277b4bd4127cd479746", 1.200, True)
    """Default duration: 1.20s"""
    Item_0_11 = TransitionMeta("震动", False, "7198100561235808825", "9261771", "e46204ca1e4fcf76d1b1c86e852e862d", 1.000, True)
    """Default duration: 1.00s"""
    Rotate_1 = TransitionMeta("顺时针Rotate", False, "6724226684721041932", "359421", "d6d0c76fb82ca2a355de138d94a94780", 0.500, True)
    """Default duration: 0.50s"""
    Rotate_II_1 = TransitionMeta("顺时针Rotate II", False, "7252544556799889975", "17224317", "5e81c58bf217a2bdaf479275e412ea93", 0.800, True)
    """Default duration: 0.80s"""
    Item_0_12 = TransitionMeta("频闪", False, "7083767957662208549", "1674710", "35a76b77dd0812f7012911109db35799", 0.500, True)
    """Default duration: 0.50s"""
    Item_0_13 = TransitionMeta("风车", False, "6748286529921094157", "369485", "367b8b51b2eeb63eb2009bf5b356bc2f", 0.500, True)
    """Default duration: 0.50s"""
    Item_0_14 = TransitionMeta("马赛克", False, "6724866519022440967", "4212631", "eed93b26d9cd6296b10d2f5065ee396e", 1.000, True)
    """Default duration: 1.00s"""
    Item_0_15 = TransitionMeta("黑色块", False, "6724866346569437710", "2918078", "357e865f3bb0c6529ee882ebf279d7c6", 0.500, True)
    """Default duration: 0.50s"""
    Smoke = TransitionMeta("黑色Smoke", False, "6885647017452769805", "947663", "fa02f80c28a9671a206c2ccf17b41c58", 0.500, False)
    """Default duration: 0.50s"""

    # Paid effects
    _2024Memory = TransitionMeta("2024Memory流", True, "7448898555617481225", "97032533", "e21c31c4d68bb535ab10905af32a8486", 2.000, True)
    """Default duration: 2.00s"""
    X = TransitionMeta("X形震闪", True, "7403208545111380531", "79087478", "07f3707be8fced05b149f16252c3aabc", 1.000, True)
    """Default duration: 1.00s"""
    Item_0_16 = TransitionMeta("万花筒", True, "7257806429086552632", "18722268", "0aa1d28fdb90725586089436e6ccd243", 0.800, True)
    """Default duration: 0.80s"""
    Item_0_17 = TransitionMeta("三屏放大", True, "7320254175466492467", "38586528", "b59a3df958aeeba78f1ceb075be189f0", 1.000, True)
    """Default duration: 1.00s"""
    Slide_1 = TransitionMeta("三屏Slide入", True, "7312438185261273650", "34443818", "09dc4fee56acca3e6f1c104277b8695d", 1.000, True)
    """Default duration: 1.00s"""
    Item_0_18 = TransitionMeta("三屏闪切", True, "7252599996254523959", "17242682", "2bc234d945f15d93f3d292e64042d69d", 0.800, True)
    """Default duration: 0.80s"""
    DownSlide = TransitionMeta("DownSlide", True, "7309694074015977993", "32998125", "9c54ccb7b27ab98f7c3bb03a5d4acc4b", 0.550, True)
    """Default duration: 0.55s"""
    Center = TransitionMeta("Center切开", True, "7450031574931739146", "97482739", "bd58325fc11ddc0a5b865da741d48215", 2.000, True)
    """Default duration: 2.00s"""
    Item_0_19 = TransitionMeta("二次元烟效", True, "7436273714729062921", "90037010", "e4a8dcb9c3a3244f38fbafd54df1875d", 1.920, True)
    """Default duration: 1.92s"""
    Cloud_II = TransitionMeta("Cloud II", True, "6955760408737092132", "2912470", "5a8914a3658f88265bbeda060a7c79aa", 0.500, True)
    """Default duration: 0.50s"""
    Blur_3 = TransitionMeta("亮点Blur", True, "7123135366504124936", "3705757", "b48f47c097e83842d1c0f919d9c67af6", 1.000, True)
    """Default duration: 1.00s"""
    Item_0_20 = TransitionMeta("便利贴", True, "7302023728441856549", "29871972", "a5a04de1e339c4d4907e26ff6b229563", 1.100, True)
    """Default duration: 1.10s"""
    Glitch_3 = TransitionMeta("信号Glitch", True, "7288149307197231676", "25265947", "f23f60f3bee4fac6368268a1406ccaf7", 0.500, True)
    """Default duration: 0.50s"""
    Glitch_II = TransitionMeta("信号Glitch II", True, "7342791345162949183", "49094731", "b5537d48d5d72d9707bb4641d51ecc73", 0.670, False)
    """Default duration: 0.67s"""
    Stretch_4 = TransitionMeta("倾斜Stretch", True, "7383960886131560960", "72481265", "c87e594192131b1b82e1c34cd383f807", 0.800, True)
    """Default duration: 0.80s"""
    Stretch_5 = TransitionMeta("倾斜Stretch开", True, "7450031573958660646", "97482745", "5e528175496005ab698956e2ae692828", 2.000, True)
    """Default duration: 2.00s"""
    Blur_4 = TransitionMeta("倾斜Blur", True, "7355762441533264394", "56268173", "0b88f86366c21c3ebd2bcc8df140810d", 0.800, True)
    """Default duration: 0.80s"""
    Item_0_21 = TransitionMeta("像素冲屏", True, "6981689835534684702", "1182216", "b7f8e6cd03560d1f52e1270dcf7c9ba4", 0.800, True)
    """Default duration: 0.80s"""
    Item_0_22 = TransitionMeta("光束", True, "6982127832042312206", "4202531", "84525ee78728b5cce44c8404d9f50b0d", 0.500, True)
    """Default duration: 0.50s"""
    Item_0_23 = TransitionMeta("全息投影", True, "7298230450768581129", "28518430", "95a2a049736e0843b5984e0090276f7b", 0.400, True)
    """Default duration: 0.40s"""
    Item_0_24 = TransitionMeta("六边形变焦", True, "7182413216276812346", "7824963", "faf521d87b90c79031bfd08d687df52a", 1.000, True)
    """Default duration: 1.00s"""
    Item_0_25 = TransitionMeta("冲屏扭曲", True, "7359133728313971227", "58099421", "2fb5734ab118c745bfa0596264533e54", 0.900, True)
    """Default duration: 0.90s"""
    Split_5 = TransitionMeta("几何Split", True, "7130139199394550303", "3985085", "4f6209fcc7e8746a7c1e43d8a1704827", 0.500, True)
    """Default duration: 0.50s"""
    Slide_2 = TransitionMeta("几何Slide", True, "7437386424036364837", "90546381", "954c56284f79c2d01b291802cc6449e1", 1.000, True)
    """Default duration: 1.00s"""
    DownSlide_1 = TransitionMeta("分屏DownSlide", True, "7337974537683735080", "46873416", "eb4e4368773f40a8c807e77497acab4f", 0.900, True)
    """Default duration: 0.90s"""
    BeforeAfterComparison = TransitionMeta("BeforeAfterComparison", True, "7205856572994490935", "10139297", "f38bc39938f58a4ee3f9c7bfcf4f524f", 1.200, True)
    """Default duration: 1.20s"""
    Item_0_26 = TransitionMeta("剧烈摇晃", True, "7367356130307084838", "63047898", "4ffdc4b55688e65262a229d5e7b987ca", 0.900, True)
    """Default duration: 0.90s"""
    Item_0_27 = TransitionMeta("卡片弹出", True, "7384334283659285032", "72605929", "67660fa9cdb387454a59d3a747cff6ef", 1.000, True)
    """Default duration: 1.00s"""
    Item_0_28 = TransitionMeta("发光变焦", True, "7402999668767986191", "79046595", "9faeac55ef029bce5e933ff4022dfe1d", 1.000, True)
    """Default duration: 1.00s"""
    Dissolve_1 = TransitionMeta("Dissolve扭曲", True, "7439255870896083466", "92006146", "c0d00a409f16dab9ebe8a94802a3a757", 0.500, True)
    """Default duration: 0.50s"""
    Item_0_29 = TransitionMeta("可爱爆炸", True, "7187674415268631101", "8375167", "75942cf09b7e84526a357898a47c18bb", 0.800, True)
    """Default duration: 0.80s"""
    Item_0_30 = TransitionMeta("可爱龙龙", True, "7332697146929451546", "44314889", "9a498314d92e4fc192efe64608b40b60", 1.000, True)
    """Default duration: 1.00s"""
    Item_0_31 = TransitionMeta("吃掉", True, "7372506069328728585", "66629623", "64b8f472cc109cccd9c50e210331af43", 0.900, True)
    """Default duration: 0.90s"""
    Item_0_32 = TransitionMeta("后台切换", True, "7320129407799005734", "38530921", "c5092413343f5e808ffc27ab8b02e7c4", 0.800, True)
    """Default duration: 0.80s"""
    Up_1 = TransitionMeta("Up波动", True, "7148734739807998495", "4861515", "69a520845b900b142b203cf2e677abd5", 5.000, True)
    """Default duration: 5.00s"""
    DownShake = TransitionMeta("DownShake", True, "7338709911791997480", "47241669", "1a44879e265bc89746e30f59d2ff0245", 1.300, True)
    """Default duration: 1.30s"""
    Down_1 = TransitionMeta("Down拖拽", True, "7199528468244075067", "9382531", "f1d490e1e2a87013bee63a8aa4191f9f", 0.800, True)
    """Default duration: 0.80s"""
    LeftStretch_1 = TransitionMeta("LeftStretch屏", True, "7089311972235153950", "1722934", "21538bc8fa278603f8e944fc405a65c9", 0.500, True)
    """Default duration: 0.50s"""
    Left_1 = TransitionMeta("Left波动", True, "7126772940451877406", "3971081", "cbffe80a580575becb3beb3bcbd5cc09", 5.000, True)
    """Default duration: 5.00s"""
    Item_0_33 = TransitionMeta("喜欢", True, "7070430644563612191", "1600478", "945ee55ddc4b7c9762b55c0ee302bdce", 0.500, True)
    """Default duration: 0.50s"""
    Item_0_34 = TransitionMeta("四屏转换", True, "7337612480610308649", "46644610", "e7bd3aacd0daeafdf20d93d4a171a846", 1.000, True)
    """Default duration: 1.00s"""
    Item_0_35 = TransitionMeta("四格展开", True, "7412560964198863394", "81987893", "d204cd232ac137532ff751ff09b5d0a7", 0.500, True)
    """Default duration: 0.50s"""
    Memory = TransitionMeta("Memory", True, "6748220149284737550", "4211778", "48a73d2ca44a59d8faf88ab0c4bb39f6", 0.500, True)
    """Default duration: 0.50s"""
    Memory_II = TransitionMeta("Memory II", True, "6748220462746046989", "4211779", "bfb17d87ed3db6332a6e0855299809d9", 0.500, True)
    """Default duration: 0.50s"""
    MemoryStretch = TransitionMeta("MemoryStretch屏", True, "7184682990901924410", "8027945", "3bc26bcea93ea43b349c60c28bea394f", 1.000, True)
    """Default duration: 1.00s"""
    MemoryStretch_II = TransitionMeta("MemoryStretch屏 II", True, "7306440470119322139", "31456359", "2464d4afc9c5f43072935915c6a86c29", 0.700, True)
    """Default duration: 0.70s"""
    Item_0_36 = TransitionMeta("图片放大", True, "7434055685576348170", "89190525", "4974e799766ed1567d4e5bfafa79e14f", 1.000, True)
    """Default duration: 1.00s"""
    CircleSplit = TransitionMeta("CircleSplit", True, "7083435788322476581", "4211684", "2bb3ad90a4eb3a2563b87c300e0ae8a1", 1.500, False)
    """Default duration: 1.50s"""
    Rotate_2 = TransitionMeta("圆盘Rotate", True, "7341334144485429810", "48516414", "835a263f9afbb614cfc5467343968642", 0.700, True)
    """Default duration: 0.70s"""
    Item_0_37 = TransitionMeta("圣诞光斑", True, "7450334536455426569", "97572058", "431fcb4417f60f17fbc7f1e8ed95c33c", 1.030, True)
    """Default duration: 1.03s"""
    II = TransitionMeta("圣诞光斑II", True, "7451488401062105610", "98049569", "c98322f188fcf08cfe380380da7d4e3b", 1.030, True)
    """Default duration: 1.03s"""
    Item_0_38 = TransitionMeta("圣诞树", True, "7302357935902954035", "29976594", "8c40262df8758d19446264aa5749008a", 0.700, True)
    """Default duration: 0.70s"""
    Item_0_39 = TransitionMeta("圣诞礼盒", True, "7447067834628182578", "96154390", "6da15163fec7a5af3ab7a25e44f94da9", 1.500, True)
    """Default duration: 1.50s"""
    RetroDissolve = TransitionMeta("RetroDissolve影", True, "7200638304591548985", "9529419", "078be6db2b8d8abded47cbd72f5635df", 1.000, True)
    """Default duration: 1.00s"""
    RetroProjection_II = TransitionMeta("RetroProjection II", True, "7240050497804046908", "14607947", "9891a08898646c3795cab650979bf0dc", 1.000, True)
    """Default duration: 1.00s"""
    Retro = TransitionMeta("Retro漏光", True, "7181752495150993957", "8104139", "0af78adb0da721bbe253b096b8152851", 0.800, True)
    """Default duration: 0.80s"""
    Retro_II = TransitionMeta("Retro漏光 II", True, "7287881053534949943", "25193261", "1789e06f18340fbcbd30e6757f10ba75", 0.600, True)
    """Default duration: 0.60s"""
    Retro_1 = TransitionMeta("RetroFilm", True, "7261814111816651322", "19552395", "c5686c7e832a5e8c178c5cadb42d9ab4", 1.000, True)
    """Default duration: 1.00s"""
    Item_0_40 = TransitionMeta("多层环形", True, "7373523970538082866", "67116644", "cf6da6be1066054f86c4524fa6494d8e", 1.500, True)
    """Default duration: 1.50s"""
    Item_0_41 = TransitionMeta("多屏定格", True, "7287860606395224613", "25184085", "c12aeac3828eb06fd5d0f865ee7041d1", 0.800, True)
    """Default duration: 0.80s"""
    Item_0_42 = TransitionMeta("大圆盘", True, "7362104359682839055", "59713023", "9d6a02b47846369cec6d19a35826570d", 0.800, True)
    """Default duration: 0.80s"""
    Item_0_43 = TransitionMeta("大波浪", True, "7426688369653977638", "86769062", "e63143bff5e6394a018f2b802e1d832e", 0.833, True)
    """Default duration: 0.83s"""
    Item_0_44 = TransitionMeta("字母拼贴", True, "7314304549575987749", "35402126", "24be4f664fcf760c00d897362194e276", 1.000, True)
    """Default duration: 1.00s"""
    Item_0_45 = TransitionMeta("射灯", True, "7368775489445433883", "63886272", "23706ad60c2258a524da320eca564d12", 1.600, True)
    """Default duration: 1.60s"""
    Item_0_46 = TransitionMeta("小喇叭", True, "7070430823597478407", "1600476", "3707101142d3069789f3d821cdb7bc35", 0.500, True)
    """Default duration: 0.50s"""
    Item_0_47 = TransitionMeta("小恶魔", True, "7075598043252265509", "1628344", "c9a87dfafa58fbc0d401fc182fbaf6fc", 1.000, True)
    """Default duration: 1.00s"""
    LeftMove_1 = TransitionMeta("LeftMove弹动", True, "7312690473108247078", "34525642", "fa3f7df94e7fc6a7dfaee203590aff47", 0.800, True)
    """Default duration: 0.80s"""
    Item_0_48 = TransitionMeta("幻影", True, "7218040359715082809", "11634125", "4a1a61e615eb94e37e2c198dd4602107", 0.800, True)
    """Default duration: 0.80s"""
    Item_0_49 = TransitionMeta("幻觉", True, "7395044376621093391", "76465118", "cb9796c59a719185df8c9c5d1922b061", 1.000, True)
    """Default duration: 1.00s"""
    Item_0_50 = TransitionMeta("开心", True, "7073053544839909919", "1610838", "0d80e7d2b7171236732668e91b849120", 0.500, False)
    """Default duration: 0.50s"""
    Item_0_51 = TransitionMeta("弹出", True, "7394709307842892303", "76381219", "5c7ab5f82d4253e2225b57ba734edd3a", 0.900, True)
    """Default duration: 0.90s"""
    Item_0_52 = TransitionMeta("弹动发光", True, "7347897562436735503", "51950360", "31bdfcfe5852df71426d22fc02293698", 0.800, True)
    """Default duration: 0.80s"""
    Item_0_53 = TransitionMeta("彩色像素", True, "7096015235953201701", "4212518", "d91c7ef4be8808bddec8a1a119f78da7", 0.500, False)
    """Default duration: 0.50s"""
    Slide_3 = TransitionMeta("彩色Slide片", True, "7437386424036381234", "90546380", "08a7fd3434943bdd3dc0c2f6d9714989", 1.500, True)
    """Default duration: 1.50s"""
    UpPageFlip = TransitionMeta("往UpPageFlip", True, "7461951141333439013", "102053853", "ef160e3ca5fdb97a5919130b278bd745", 1.040, True)
    """Default duration: 1.04s"""
    Shake_1 = TransitionMeta("微Shake", True, "7368739347845091877", "63860874", "9870ae40f2c8a325debc06d25ef46895", 1.500, True)
    """Default duration: 1.50s"""
    Dissolve_2 = TransitionMeta("心形Dissolve", True, "7264829174601224764", "20224653", "24559e84f2cfae6bbfd86d47bb8f60f9", 1.000, True)
    """Default duration: 1.00s"""
    Wipe = TransitionMeta("快涂Wipe", True, "7450031573954466331", "97482742", "584bed7ede0c38de9d86fb5e9199ec29", 0.500, True)
    """Default duration: 0.50s"""
    Item_0_54 = TransitionMeta("快速缩放", True, "7382154814144123392", "71890617", "bbedbf5ac1b865d1e1395d4d402ce5fa", 1.000, True)
    """Default duration: 1.00s"""
    Item_0_55 = TransitionMeta("快速震闪", True, "7403364394404418074", "79172318", "5d1d93e09913898ffd9140351d7a9224", 1.000, True)
    """Default duration: 1.00s"""
    Item_0_56 = TransitionMeta("快门", True, "6882983860615778823", "2917720", "2df569fefb5004c041af5509c10d6c53", 0.500, True)
    """Default duration: 0.50s"""
    Item_0_57 = TransitionMeta("惊悚屏闪", True, "7425528298395931187", "86397088", "7bad249a916e313a5e2f422291e9d4e9", 1.000, True)
    """Default duration: 1.00s"""
    Item_0_58 = TransitionMeta("手机屏放大", True, "7447351620649620005", "96240495", "47f7a2d93348de0cc3363f8bed9e27b8", 2.000, True)
    """Default duration: 2.00s"""
    Item_0_59 = TransitionMeta("扫光", True, "7106765945305043463", "4202535", "333aa7e9d8b24e358ea60784ce47b6fe", 0.500, True)
    """Default duration: 0.50s"""
    Item_0_60 = TransitionMeta("扭曲弹动", True, "7402970650379293199", "79044291", "014956443b20f5c5e87edf79fe2aa5e3", 1.000, True)
    """Default duration: 1.00s"""
    Item_0_61 = TransitionMeta("扭曲旋入", True, "7373640088091103763", "67190756", "2f0a8143624bfc061ae9db4cb785029f", 1.000, True)
    """Default duration: 1.00s"""
    Item_0_62 = TransitionMeta("扭曲溶解", True, "7374259106502152741", "67617874", "756df14869da51538ed41e2bfac3b779", 1.000, True)
    """Default duration: 1.00s"""
    Item_0_63 = TransitionMeta("扭转弹动", True, "7344986966145896994", "50231600", "e5d36f065e3f0e8801c43a625a7d9947", 1.500, True)
    """Default duration: 1.50s"""
    Shake_2 = TransitionMeta("Shake放大", True, "7260415521852494397", "19272888", "e4cafc076ecab223a39a26fe6f05b6db", 0.800, True)
    """Default duration: 0.80s"""
    Shake_3 = TransitionMeta("Shake缩小", True, "7291972229087105563", "26488746", "6e78a0c97c60562573a30342882a240f", 0.700, True)
    """Default duration: 0.70s"""
    Shake_II_1 = TransitionMeta("Shake缩小 II", True, "7316783851206873651", "36841926", "137d3f03fbd4dddbc6a2a0dd1f371e17", 1.000, True)
    """Default duration: 1.00s"""
    Item_0_64 = TransitionMeta("折痕胶带", True, "7436273714733257225", "90037011", "949b5a139458534e713b4751f89cc366", 1.000, True)
    """Default duration: 1.00s"""
    Item_0_65 = TransitionMeta("抽象前景", True, "7104215831919202853", "2459634", "88b3ead3e00313684cd868d51c1173c9", 0.500, True)
    """Default duration: 0.50s"""
    _II_2 = TransitionMeta("抽象前景 II", True, "7108564115529929229", "2870170", "b8628f4b1d6fc27447dfad6a5f25beb4", 0.500, True)
    """Default duration: 0.50s"""
    Stretch_6 = TransitionMeta("Stretch开", True, "7384323685026370098", "72601002", "828b81127e669508f999900bff18cf2a", 0.600, True)
    """Default duration: 0.60s"""
    Stretch_7 = TransitionMeta("Stretch框入屏", True, "7297077423487586826", "28115429", "bfc8a51d2b304be3dd36a68331f8d0f8", 1.000, True)
    """Default duration: 1.00s"""
    Camera_II = TransitionMeta("Camera II", True, "7109727014780670495", "2958464", "5483f878a302c6d7879bd566cebab543", 0.900, True)
    """Default duration: 0.90s"""
    Camera_III = TransitionMeta("Camera III", True, "7107542030976291336", "2792048", "36c9b870a00e16365421398ac4e51652", 0.800, True)
    """Default duration: 0.80s"""
    Item_0_66 = TransitionMeta("挤压分屏", True, "7435897594074632713", "89895302", "ca0072e8c95318ca9babfa5a6d699cac", 0.830, True)
    """Default duration: 0.83s"""
    ZoomIn_II = TransitionMeta("ZoomIn II", True, "7290852476259930685", "26135688", "94815943a86e741a5fec1737fbb46d60", 0.900, True)
    """Default duration: 0.90s"""
    _II_3 = TransitionMeta("推远 II", True, "7360987817066893862", "59043083", "0a10553e75180add06fd336bf16fa8aa", 1.000, True)
    """Default duration: 1.00s"""
    Item_0_67 = TransitionMeta("摄像机", True, "7070047850960261668", "1598384", "bb0b9fa428e5a3fde828c03022b5082d", 0.500, True)
    """Default duration: 0.50s"""
    Item_0_68 = TransitionMeta("摇晃描边", True, "7372137986877559335", "66403340", "0a5449cf1ca4c9fb473ff664ea23185b", 1.000, True)
    """Default duration: 1.00s"""
    Item_0_69 = TransitionMeta("摇晃震动", True, "7343618757530489379", "49545855", "c911cc41c158afbd43636d1aa465e1d2", 1.300, True)
    """Default duration: 1.30s"""
    Item_0_70 = TransitionMeta("摇镜", True, "7305969268259033609", "31254345", "f215c106100f76dcf6c550d0f8217ecb", 0.700, True)
    """Default duration: 0.70s"""
    TornPaper = TransitionMeta("TornPaper", True, "6875627914444935694", "2912468", "131ae40c737ab9f5c79e35e3639a4bad", 0.500, True)
    """Default duration: 0.50s"""
    TornPaper_1 = TransitionMeta("TornPaper掉落", True, "7218114518314914365", "11661051", "42fa2f7a99a392e2801ad5ec5f62d73a", 1.200, True)
    """Default duration: 1.20s"""
    Shake_4 = TransitionMeta("收缩Shake", True, "7347676775633130024", "51859926", "88939867fef0a71b39f549558d724d31", 1.000, True)
    """Default duration: 1.00s"""
    LeftMove_2 = TransitionMeta("放大LeftMove", True, "7347582471111709236", "51784590", "a2c4ddc0f96c5694e941d738ed52cdf4", 1.300, True)
    """Default duration: 1.30s"""
    Item_0_71 = TransitionMeta("放大镜", True, "7313974602156216858", "35244988", "91aee5fc06c85dda958101a677f19c0b", 0.700, True)
    """Default duration: 0.70s"""
    GlitchScan = TransitionMeta("GlitchScan", True, "7425528124013548059", "86396968", "87bd40bfa4f188fa096a161d68c35037", 1.000, True)
    """Default duration: 1.00s"""
    GlitchBlur = TransitionMeta("GlitchBlur", True, "7302270954602762789", "29927992", "fc3fae70595c7bb6f943aca08dc7b9f1", 0.700, True)
    """Default duration: 0.70s"""
    Item_0_72 = TransitionMeta("数字矩阵", True, "7268870949548593725", "20983534", "f39bf079c6066cbfee7c5eca1491b276", 1.000, True)
    """Default duration: 1.00s"""
    Blur_5 = TransitionMeta("斜Blur", True, "7125661284762128910", "3796323", "b14d9650ca6eef79d6b19c16c65166d3", 0.800, True)
    """Default duration: 0.80s"""
    Item_0_73 = TransitionMeta("斜闪光", True, "7384331194978013711", "72603864", "eba796256a96c4ff0d1b331a8819c6f2", 0.700, True)
    """Default duration: 0.70s"""
    PageFlip_1 = TransitionMeta("斜线PageFlip", True, "7339900424956154403", "47905855", "46d525166125a781ce8cf9c6e6370454", 0.700, True)
    """Default duration: 0.70s"""
    Item_0_74 = TransitionMeta("新篇章", True, "7174756125902901797", "7089439", "74716b2d52b85799f78903818eb3c98f", 0.800, True)
    """Default duration: 0.80s"""
    _II_4 = TransitionMeta("新篇章 II", True, "7174754977544409657", "7089435", "6c1c52a50f842600c69417cf38adc113", 1.600, True)
    """Default duration: 1.60s"""
    Split_6 = TransitionMeta("方形Split", True, "7127901205820346917", "3895735", "9f29e50ac72b66f4b0320ee1ea9d112f", 0.500, True)
    """Default duration: 0.50s"""
    Item_0_75 = TransitionMeta("方形变焦", True, "7398512469884277260", "77388758", "93317b58455482c7f5213b943a7e01ce", 1.000, True)
    """Default duration: 1.00s"""
    Blur_6 = TransitionMeta("方形Blur", True, "7122721406210544164", "3686479", "8e3579bda4787d20d8c8ab1b0c68112d", 1.000, True)
    """Default duration: 1.00s"""
    Blur_II_1 = TransitionMeta("方形Blur II", True, "7384005295770440201", "72501238", "301fe868bf7b1549d6d07af9405beb4a", 1.000, True)
    """Default duration: 1.00s"""
    Flip_2 = TransitionMeta("方片Flip转", True, "7451501266246570534", "98063100", "418d4795972e2f70533f05304e796c22", 1.100, True)
    """Default duration: 1.10s"""
    Item_0_76 = TransitionMeta("旋焦", True, "7215424325036282428", "11286537", "917c209246e975d4f10d9b8c8c78035f", 0.500, True)
    """Default duration: 0.50s"""
    Rotate_3 = TransitionMeta("Rotate圆球", True, "7377722094806635048", "69481298", "34211e59f420adb42bc00b9a8d36bb6a", 0.800, True)
    """Default duration: 0.80s"""
    Rotate_4 = TransitionMeta("Rotate圆盘", True, "7261828356386067005", "19556167", "792fd505220632cdca8d727ecafa9866", 1.000, True)
    """Default duration: 1.00s"""
    Rotate_II_2 = TransitionMeta("Rotate圆盘 II", True, "7262674749258469949", "19727008", "17d1ac181dd7b623059b8aed82d2ef13", 1.000, True)
    """Default duration: 1.00s"""
    Rotate_5 = TransitionMeta("Rotate快门", True, "7350577049968316979", "53358879", "f2b536b7d3f17bc58e0e4957f517ece0", 1.000, True)
    """Default duration: 1.00s"""
    Rotate_6 = TransitionMeta("Rotate拨盘", True, "7368844683256009242", "63924504", "88ac2494e5cdec7f874c4157555d2d2b", 1.000, True)
    """Default duration: 1.00s"""
    RotateBlur = TransitionMeta("RotateBlur", True, "7332480491058106943", "44259414", "1a28e7fbb2a177240786bd945fb9ca7e", 1.200, True)
    """Default duration: 1.20s"""
    Rotate_7 = TransitionMeta("Rotate穿越", True, "7343092798993732148", "49228871", "e05493559e59bf7f4c4a9ea5a5d212de", 1.800, True)
    """Default duration: 1.80s"""
    Rotate_8 = TransitionMeta("Rotate纵深", True, "7368687055225754153", "63822177", "e717dfe6ccb3c6a6c6a6f70987b1a894", 0.900, True)
    """Default duration: 0.90s"""
    RotatePageFlip = TransitionMeta("RotatePageFlip", True, "7320577375752688165", "38717232", "31a897fbdd402adaf84724fb28ef606b", 0.800, True)
    """Default duration: 0.80s"""
    Rotate_9 = TransitionMeta("Rotate震动", True, "7326861725213397514", "41492871", "70bea2644a8dc8bc2b24102d8fa90ca4", 0.600, True)
    """Default duration: 0.60s"""
    Item_0_77 = TransitionMeta("无缝撕裂", True, "7439255870896083506", "92006145", "afcefb6980d7212c51229927c39c89e0", 1.500, True)
    """Default duration: 1.50s"""
    _I = TransitionMeta("无限穿越 I", True, "7036984568536109581", "1465694", "3ee3fc9318dc2315d250f0baa1763e5b", 1.600, True)
    """Default duration: 1.60s"""
    _II_5 = TransitionMeta("无限穿越 II", True, "7034717113130422791", "1458828", "b87498756c478952cf7c804234f97bbb", 1.600, True)
    """Default duration: 1.60s"""
    Transition = TransitionMeta("日历Transition", True, "7460472998944838154", "101496138", "ca48c1fe6e5b7cdcc100469f5294820b", 2.000, True)
    """Default duration: 2.00s"""
    Item_0_78 = TransitionMeta("旧Film", True, "7099310030138118687", "1933296", "782110cae96a4f9ed73f6a85d0610a7a", 0.500, False)
    """Default duration: 0.50s"""
    _II_6 = TransitionMeta("旧Film II", True, "7111634884153578014", "3114014", "79901fab61f0b8c2960c73a78e84e5a3", 0.500, True)
    """Default duration: 0.50s"""
    Item_0_79 = TransitionMeta("时光穿梭", True, "7306853312400200229", "31645629", "74eab27c1dc1a568b851a2e543682058", 1.100, True)
    """Default duration: 1.10s"""
    Item_0_80 = TransitionMeta("星光", True, "7177201869612126777", "7339355", "2215320b9ba4138c53f1f7b9d0c58b54", 1.500, True)
    """Default duration: 1.50s"""
    Dissolve_3 = TransitionMeta("星光Dissolve", True, "7321658733497422363", "39173243", "f6d691dd1f991655b2826964c3883772", 0.800, True)
    """Default duration: 0.80s"""
    Item_0_81 = TransitionMeta("星光炸开", True, "7306852010320466483", "31644713", "b7523d4d583c515035937de1c191c808", 1.300, True)
    """Default duration: 1.30s"""
    Star_III = TransitionMeta("Star III", True, "7293358903176204851", "26885516", "1ece838a7bfd2c8b1b0daf25d5776d22", 0.500, True)
    """Default duration: 0.50s"""
    Star_1 = TransitionMeta("Star变焦", True, "7452559875839627786", "98464024", "7eeeca7c07e67b54519995ebdf71d6fc", 1.000, True)
    """Default duration: 1.00s"""
    StarInhale = TransitionMeta("StarInhale", True, "7312716430875562506", "34540914", "6ce2a58bc6a3df532a3c1ca890c97394", 1.000, True)
    """Default duration: 1.00s"""
    StarBlur = TransitionMeta("StarBlur", True, "7206157339253019197", "10169537", "28556f2cabd470e0da1a9ddf16d76198", 0.800, True)
    """Default duration: 0.80s"""
    Item_0_82 = TransitionMeta("春日光斑", True, "7330599151685603875", "43351778", "16080e0cc9aa32e4342335d60dd5dfae", 1.000, True)
    """Default duration: 1.00s"""
    Item_0_83 = TransitionMeta("暧昧光晕", True, "7268613185337299513", "20954940", "ab82749d799477631ae63c081ad569d1", 0.800, True)
    """Default duration: 0.80s"""
    Stretch_8 = TransitionMeta("曝光Stretch丝", True, "7308617539452408358", "32432969", "56eaaf319007193c199f17554890abb4", 2.000, True)
    """Default duration: 2.00s"""
    Item_0_84 = TransitionMeta("曝光摇镜", True, "7283720497513108025", "24147753", "e0ee1d0a29d1138f7a3b673ffbad91d5", 0.700, True)
    """Default duration: 0.70s"""
    Item_0_85 = TransitionMeta("未来光谱", True, "7176890183940313658", "7307905", "7974c984bf60d60079cc03be5928f74d", 0.800, True)
    """Default duration: 0.80s"""
    II_1 = TransitionMeta("未来光谱II", True, "7176914791267570232", "7312585", "524895c4bce265b44ffa8ac92bf0dd6a", 0.800, True)
    """Default duration: 0.80s"""
    Blur_7 = TransitionMeta("条形Blur", True, "7122387202725646862", "3675841", "0a5742430e336b3a1e1b6ff9983c5d25", 1.000, True)
    """Default duration: 1.00s"""
    Blur_8 = TransitionMeta("Blur放大", True, "7301280654015074842", "29614872", "7c0ef1a54495f7cd9343efe2acc57b26", 1.000, True)
    """Default duration: 1.00s"""
    Blur_9 = TransitionMeta("Blur细闪", True, "7452559875839627785", "98464023", "486a1593cc532d15663279bd4a127a45", 1.170, True)
    """Default duration: 1.17s"""
    Blur_10 = TransitionMeta("Blur缩小", True, "7297133348567126566", "28141206", "742e708ac73c3a335a41133684c488ed", 1.200, True)
    """Default duration: 1.20s"""
    Item_0_86 = TransitionMeta("横分屏", True, "7351341191184519699", "53798168", "9b32def73cc4e91d29a92bd640a92e81", 1.000, True)
    """Default duration: 1.00s"""
    Slide_4 = TransitionMeta("横Slide", True, "7433711910727455242", "89071753", "9023b03b64ddd87133a3ed36e60d14a1", 1.530, True)
    """Default duration: 1.53s"""
    Item_0_87 = TransitionMeta("横震动", True, "7403329110597964340", "79166394", "c3c9b35342f9cc1daa938cb512a71baa", 1.000, True)
    """Default duration: 1.00s"""
    Item_0_88 = TransitionMeta("横条挤压", True, "7369507828668568116", "64687184", "6bbc30d59ef4fd16e4ba6656129cfd95", 1.200, True)
    """Default duration: 1.20s"""
    MoveBlur = TransitionMeta("横MoveBlur", True, "7316901787762430491", "36950128", "aa2ce5c9b13a62881d04f9c23aa30678", 0.800, True)
    """Default duration: 0.80s"""
    Item_0_89 = TransitionMeta("樱花飞舞", True, "7462198817211814426", "102144538", "ecd91f7ebaa7817d7eab538a50147fb4", 2.000, True)
    """Default duration: 2.00s"""
    Item_0_90 = TransitionMeta("水滴", True, "7218875183413596730", "11765299", "d5fa6a1daecd2c45b0414626a69e7674", 0.500, True)
    """Default duration: 0.50s"""
    _II_7 = TransitionMeta("水滴 II", True, "7231860840452854332", "13482623", "eebf40246476d57ccbf8bbdf15864864", 0.900, True)
    """Default duration: 0.90s"""
    _III_1 = TransitionMeta("水滴 III", True, "7337571999885038130", "46608908", "32eea5171000b838f2eb74941fb751d7", 1.100, True)
    """Default duration: 1.10s"""
    Item_0_91 = TransitionMeta("水滴溶解", True, "7397337004507140646", "77055389", "ea2d35628f0f6cbc703f7632fbc0588e", 1.000, True)
    """Default duration: 1.00s"""
    Item_0_92 = TransitionMeta("汇聚", True, "7308666709932511753", "32470148", "3bb1668888e7e87764d03b15733370fb", 1.000, True)
    """Default duration: 1.00s"""
    Blur_11 = TransitionMeta("泡泡Blur", True, "7159097688955294222", "5663559", "10478b300821fa6eccadf67b07b63208", 1.000, True)
    """Default duration: 1.00s"""
    Item_0_93 = TransitionMeta("波光粼粼", True, "7361758664182469157", "59511491", "da913924bc6975821de103b371d540ff", 1.167, True)
    """Default duration: 1.17s"""
    Item_0_94 = TransitionMeta("波动", True, "7169480114860724773", "6500749", "af314da6343d025cc0f5d668d2fa0a7b", 0.500, True)
    """Default duration: 0.50s"""
    _II_8 = TransitionMeta("波动 II", True, "7308652550574576138", "32459394", "dd709d2dd83add664f3cbd45893438f7", 0.400, True)
    """Default duration: 0.40s"""
    Glitch_4 = TransitionMeta("波动Glitch", True, "7223312837320380983", "12349835", "bd7d819531a9d2b044f823080aa0fc1c", 0.600, True)
    """Default duration: 0.60s"""
    Item_0_95 = TransitionMeta("泼墨晕染", True, "7424057373741814298", "85924530", "7b36ddff84bae2afa85432cb5fdac1f4", 0.700, True)
    """Default duration: 0.70s"""
    Item_0_96 = TransitionMeta("流光", True, "7316789832833831461", "36847370", "686a5ae873f34ac400ee8ad6a8658d68", 1.000, True)
    """Default duration: 1.00s"""
    Item_0_97 = TransitionMeta("涂鸦放大", True, "7239925851335168569", "14573363", "2a29109cf3c013e6f7770a28cba4154a", 1.500, True)
    """Default duration: 1.50s"""
    Item_0_98 = TransitionMeta("溶解推进", True, "7348406367394206271", "52246665", "e6c9fda251c612d8cdf69ddef055e410", 0.806, True)
    """Default duration: 0.81s"""
    Slide_5 = TransitionMeta("Slide压迫感", True, "7447351620641231387", "96240496", "dd49d44cfd3e5f5b14e3275876fcc79c", 2.000, True)
    """Default duration: 2.00s"""
    Slide_6 = TransitionMeta("Slide弹出", True, "7343237606043292200", "49343171", "bb190e71a692bc20d9060b22b4311896", 1.000, True)
    """Default duration: 1.00s"""
    Slide_7 = TransitionMeta("Slide放大", True, "7327132595190239759", "41576555", "a746b6b7c2e83275d90864d0b28173aa", 1.000, True)
    """Default duration: 1.00s"""
    Slide_8 = TransitionMeta("Slide块拼贴", True, "7239990715307004477", "14594823", "c8552ba32a7e8804013a8a1b977e23c1", 1.500, True)
    """Default duration: 1.50s"""
    Item_0_99 = TransitionMeta("滚动立方", True, "7471167302029808138", "105115378", "376cd96ec36e56b7ea5b921f402fa7f3", 0.733, True)
    """Default duration: 0.73s"""
    Vortex_1 = TransitionMeta("Vortex扭曲", True, "7308653984888132123", "32460372", "fedeb478c6e4d39282dfe1ad13ee653a", 0.700, True)
    """Default duration: 0.70s"""
    TornPaper_2 = TransitionMeta("漫画TornPaper", True, "7429283264424055305", "87580719", "ac08c5a486921431e4bb175cc9b31432", 0.800, True)
    """Default duration: 0.80s"""
    Flame = TransitionMeta("Flame湍流", True, "7397337005375361562", "77055404", "133e52c43b2639f2a202b3b1394846bf", 1.000, True)
    """Default duration: 1.00s"""
    Item_0_100 = TransitionMeta("炫光", True, "6726707814028284423", "4202524", "a3fd6266c293496fd9480884a93fb90e", 0.500, True)
    """Default duration: 0.50s"""
    _II_9 = TransitionMeta("炫光 II", True, "6950255790762496548", "4202530", "aafb556352016d087cddd1939ada20f8", 0.500, False)
    """Default duration: 0.50s"""
    _III_2 = TransitionMeta("炫光 III", True, "6950255930160189988", "4202529", "5ed29701053e9f7640ecf8dcfc34c7cc", 0.500, False)
    """Default duration: 0.50s"""
    Item_0_101 = TransitionMeta("炫光弹动", True, "7348337133838406194", "52201950", "113a7490b314d57a7dea4826e056ff99", 1.000, True)
    """Default duration: 1.00s"""
    Scan = TransitionMeta("炫光Scan", True, "7371717412736995903", "66131585", "4bd676f9001765af20ac02b252da5575", 1.467, True)
    """Default duration: 1.47s"""
    Item_0_102 = TransitionMeta("炫光扭动", True, "7435897594703778330", "89895303", "a1fef85b1aaae8625494711a77ac1903", 0.700, True)
    """Default duration: 0.70s"""
    Item_0_103 = TransitionMeta("炸弹", True, "7076321483282190878", "1632990", "e0a1a6b556395c054ce97d73b6d1ef25", 0.500, True)
    """Default duration: 0.50s"""
    Item_0_104 = TransitionMeta("烟花光斑", True, "7449596462670811686", "97260760", "e7db0e4df4fad1aeb19413ebdb8e940d", 2.000, True)
    """Default duration: 2.00s"""
    Smoke_1 = TransitionMeta("Smoke弹", True, "7366189026677625359", "62284094", "58dced44162cefabdc709058b7583d65", 1.400, True)
    """Default duration: 1.40s"""
    Item_0_105 = TransitionMeta("热成像", True, "7435897594074632742", "89895304", "ed973037edcf37c1c8272776af27ef7b", 1.000, True)
    """Default duration: 1.00s"""
    Item_0_106 = TransitionMeta("燃烧", True, "7089309494550729253", "1722848", "0f42e514001c30186e1c9c68e1ebfee9", 0.500, True)
    """Default duration: 0.50s"""
    _II_10 = TransitionMeta("燃烧 II", True, "7089307363806548510", "1722824", "164c1073bde892dcd9f21d8026fb3cbd", 0.500, True)
    """Default duration: 0.50s"""
    _III_3 = TransitionMeta("燃烧 III", True, "7088523814102897188", "1714536", "da10f2f4ae0aa70ad4d61b2c750aef6b", 0.500, True)
    """Default duration: 0.50s"""
    Item_0_107 = TransitionMeta("爆米花", True, "7075173004560306724", "1623902", "3b70ab38b467c15d463b018b05a420e2", 0.500, True)
    """Default duration: 0.50s"""
    Item_0_108 = TransitionMeta("爆闪", True, "7255132261584998969", "18010162", "c533ae1fe681ec0903b6d631fec5caf6", 1.000, True)
    """Default duration: 1.00s"""
    _II_11 = TransitionMeta("爆闪 II", True, "7259635767096382011", "19102212", "96e672a98b09ef157224e8b1399ae316", 0.600, True)
    """Default duration: 0.60s"""
    Heart_1 = TransitionMeta("Heart冲击", True, "7405941767867994624", "80045036", "b9cc7fee0ef181378b070ddd3b96c08f", 1.500, True)
    """Default duration: 1.50s"""
    HeartBlur = TransitionMeta("HeartBlur", True, "7226945634312393274", "12851969", "3dfdf5cbfe44b5271b9e41acb15ddc37", 0.600, True)
    """Default duration: 0.60s"""
    Heart_2 = TransitionMeta("Heart气球", True, "7267895649599754808", "20810100", "6b969705ffc616c0ad03c1e0fc039bd7", 1.000, True)
    """Default duration: 1.00s"""
    Heart_3 = TransitionMeta("Heart软糖", True, "7330845783006122515", "43363938", "ef23b64fbbf32418248446c9f4703589", 1.500, True)
    """Default duration: 1.50s"""
    HeartMask = TransitionMeta("HeartMask", True, "7468589287299093029", "104143934", "c4e6d4a6c68554cc17b620d2ffa8c41e", 2.000, True)
    """Default duration: 2.00s"""
    ZoomIn_1 = TransitionMeta("环回ZoomIn", True, "7449266731089924658", "97152408", "3ad22aeec6b193f1d3718330bafdb4ac", 1.533, True)
    """Default duration: 1.53s"""
    Item_0_109 = TransitionMeta("环形色散", True, "7384745397022888488", "72761824", "608a4f0f4729821ff115f72bfb57a909", 0.900, True)
    """Default duration: 0.90s"""
    Item_0_110 = TransitionMeta("玻璃破碎", True, "7242225450628420133", "14930013", "55aa86f7d52f2e3471574b51aedfffe8", 1.000, True)
    """Default duration: 1.00s"""
    _II_12 = TransitionMeta("玻璃破碎 II", True, "7249622034878042661", "16373363", "f77fe839adb1ca6cddc086834a514b79", 1.000, True)
    """Default duration: 1.00s"""
    Blur_12 = TransitionMeta("珠光Blur", True, "7181370814594290234", "7738323", "75984d0cab40abfd59ec5d7ede711496", 1.000, True)
    """Default duration: 1.00s"""
    Item_0_111 = TransitionMeta("生气", True, "7070430937900651016", "1600475", "be7a4f8a24aafb10db343e51e72fead2", 0.500, False)
    """Default duration: 0.50s"""
    Item_0_112 = TransitionMeta("电光", True, "7186953120490983997", "8298317", "6142261f8bd0361a56d15a3d408c20ab", 1.000, True)
    """Default duration: 1.00s"""
    _II_13 = TransitionMeta("电光 II", True, "7292990637350064690", "26773684", "e8a9edb89dae57afad5dfd6b707a6b57", 1.300, True)
    """Default duration: 1.30s"""
    Item_0_113 = TransitionMeta("电流", True, "7402545346741539365", "78884363", "435f3111d5b73043c9da4fb52bc1c5aa", 1.167, True)
    """Default duration: 1.17s"""
    Item_0_114 = TransitionMeta("畸变回弹", True, "7434746460186350130", "89406897", "3b87acb614610bef693ceeb28833378b", 2.000, True)
    """Default duration: 2.00s"""
    Blinds_II = TransitionMeta("Blinds II", True, "7389190159989740072", "74345085", "0786c1d4057bf47fbdb5f6bfeab8a0f3", 0.800, True)
    """Default duration: 0.80s"""
    Item_0_115 = TransitionMeta("相机缩小", True, "7462628239286997531", "102354878", "5a4bcb0da1b9aa3a412230ecf4009cf2", 2.000, True)
    """Default duration: 2.00s"""
    Item_0_116 = TransitionMeta("相片切换", True, "7324946677305971226", "40583461", "0bcab7309cd00dc17a95071b62282d0a", 0.700, True)
    """Default duration: 0.70s"""
    Item_0_117 = TransitionMeta("相片拼贴", True, "7212523710685647420", "10917367", "bdff0041ed99b812568c15e5a7c5d798", 0.600, True)
    """Default duration: 0.60s"""
    Down_2 = TransitionMeta("礼物落Down", True, "7462627865197023782", "102354705", "bc569b8205db8dad3eb195df697dfda8", 2.000, True)
    """Default duration: 2.00s"""
    SpaceUpMove = TransitionMeta("SpaceUpMove", True, "7405560276180800009", "79942985", "7043746b8dd5592ffa7e5e8baec3e504", 0.500, True)
    """Default duration: 0.50s"""
    Space = TransitionMeta("Space弹动", True, "7265321906830578235", "20330329", "e86c774726c177ee17fd90f63750cf78", 1.000, False)
    """Default duration: 1.00s"""
    Space_II = TransitionMeta("Space弹动 II", True, "7269664953584325179", "21121644", "adf0c9abb5c1399909318bb603f28ad1", 1.000, False)
    """Default duration: 1.00s"""
    Space_III = TransitionMeta("Space弹动 III", True, "7265322078276948535", "20330339", "d8c4ad960be7cfbe8093fa26076ce000", 1.000, False)
    """Default duration: 1.00s"""
    Space_IV = TransitionMeta("Space弹动 IV", True, "7270393974517404215", "21261060", "fb42b8f0a30fe4a0c81c292460aabdbd", 1.000, False)
    """Default duration: 1.00s"""
    SpaceRotate = TransitionMeta("SpaceRotate", True, "7127563142359421471", "3878325", "07c37c8bcf40b83415aa6f223de2cd8a", 1.000, True)
    """Default duration: 1.00s"""
    SpaceRotate_II = TransitionMeta("SpaceRotate II", True, "7137983390896099871", "4360464", "43927ed137278ab2c3cf8a4933cb4169", 1.000, True)
    """Default duration: 1.00s"""
    SpaceRotate_III = TransitionMeta("SpaceRotate III", True, "7138602593751667207", "4382158", "7baa76e42959ee273c278389d359fc59", 1.000, True)
    """Default duration: 1.00s"""
    SpaceFlip = TransitionMeta("SpaceFlip转", True, "7218870491400901157", "11764147", "0ea4c7c316341196f21440967330f063", 1.200, True)
    """Default duration: 1.20s"""
    SpaceFlip_II = TransitionMeta("SpaceFlip转 II", True, "7223591053973000761", "12371701", "ee9309f01cc53522243198c4ba69ab96", 1.200, True)
    """Default duration: 1.20s"""
    Space_1 = TransitionMeta("Space跳跃", True, "7309399317662405146", "32858947", "82c5ef6e77c7178c7ca45d8549b87578", 0.633, True)
    """Default duration: 0.63s"""
    Item_0_118 = TransitionMeta("穿越", True, "7152422191944962567", "5083535", "80fb974789637e8175557c7c3e649c0e", 1.000, True)
    """Default duration: 1.00s"""
    _II_14 = TransitionMeta("穿越 II", True, "7152354215132664357", "5076093", "aa3181f829fe16f72540cc0ec7dfb171", 1.000, True)
    """Default duration: 1.00s"""
    _III_4 = TransitionMeta("穿越 III", True, "7341295618863665690", "48498880", "6d6fa95fe1414d4b4a45db9ddec0ee9b", 0.800, True)
    """Default duration: 0.80s"""
    Rotate_10 = TransitionMeta("立体Rotate", True, "7397337004511334962", "77055394", "dc1ea47698728162001d4f8ee1f22a80", 1.000, True)
    """Default duration: 1.00s"""
    Flip_3 = TransitionMeta("立体Flip转", True, "7353088031705797159", "54820217", "3746e458c37ab10f2aaa1ac83dee99f6", 0.800, True)
    """Default duration: 0.80s"""
    PageFlip_2 = TransitionMeta("立体PageFlip", True, "7156512800867619335", "5379189", "ac010354774404d6b8e092120ab76772", 0.800, True)
    """Default duration: 0.80s"""
    PageFlip_II = TransitionMeta("立体PageFlip II", True, "7156527319274754568", "5381749", "a033fe7038252ba812a4377ff3326acf", 0.800, True)
    """Default duration: 0.80s"""
    Rotate_11 = TransitionMeta("立方Rotate", True, "7400668689411871251", "78218811", "31c50d0386413970443a6b592b201fd5", 1.000, True)
    """Default duration: 1.00s"""
    Stretch_9 = TransitionMeta("竖Stretch", True, "7384005384349946418", "72501228", "ac2563343aceb1b399c6b97b2b21f567", 1.000, True)
    """Default duration: 1.00s"""
    MoveBlur_1 = TransitionMeta("竖MoveBlur", True, "7270505237935297085", "21300860", "4f77c735f448ec5f6df27f21d88e4ee6", 0.600, True)
    """Default duration: 0.60s"""
    Item_0_119 = TransitionMeta("笔迹涂抹", True, "7435897594078843419", "89895305", "0de59ee84b2fc1195497ade8dea6d5ed", 2.000, True)
    """Default duration: 2.00s"""
    Item_0_120 = TransitionMeta("粉色反转片", True, "7200360240393491000", "9504701", "80529c6e270d25d9fa6e4babb45346c7", 0.800, True)
    """Default duration: 0.80s"""
    Item_0_121 = TransitionMeta("红包雨", True, "7321942209752732186", "39261991", "3a4c80e1aebeea0ebf65d4d4fee96481", 1.500, True)
    """Default duration: 1.50s"""
    Slide_9 = TransitionMeta("纵Slide", True, "7433711910727455259", "89071754", "9359f18a23d5ebfafc54489696912f2b", 1.330, True)
    """Default duration: 1.33s"""
    Item_0_122 = TransitionMeta("纸团", True, "7238905266912105019", "14451527", "283ecb29f26d13d371658f0b8b476776", 0.700, True)
    """Default duration: 0.70s"""
    FlipTransition = TransitionMeta("Flip书Transition", True, "7440002160588231194", "92891048", "5fa1b17f1b45a942f90b13486fef2211", 1.600, True)
    """Default duration: 1.60s"""
    Flip_4 = TransitionMeta("Flip转冲屏", True, "7275914638267519525", "22253379", "c1ebaab317335c387d342a3d0b42a65b", 1.200, True)
    """Default duration: 1.20s"""
    PageFlip_II_1 = TransitionMeta("PageFlip II", True, "7221478593803588152", "12108759", "7720214c69eaa3203c3edda2027b28d4", 0.900, True)
    """Default duration: 0.90s"""
    Item_0_123 = TransitionMeta("聚光灯", True, "7325700559556579878", "40923539", "43853a772e195442e07760b04fb236dd", 1.100, True)
    """Default duration: 1.10s"""
    Slide_10 = TransitionMeta("胶卷Slide", True, "7437386424032170547", "90546382", "ebbf5882c3c8bcaec96da67a69dbb9b4", 2.000, True)
    """Default duration: 2.00s"""
    Item_0_124 = TransitionMeta("Film切闪", True, "7468603557348905510", "104151439", "a4efe5e3a9fd8ce07b1760f5e998acc4", 1.330, True)
    """Default duration: 1.33s"""
    Item_0_125 = TransitionMeta("Film定格", True, "7211146962513433147", "10764691", "1a96476b4a04acd24a1b5a7f293fc2eb", 1.000, True)
    """Default duration: 1.00s"""
    Wipe_1 = TransitionMeta("FilmWipe", True, "7308265370480022026", "32274061", "4bbb3dcb507832529d7a18020c8fc88d", 0.800, True)
    """Default duration: 0.80s"""
    Item_0_126 = TransitionMeta("Film融化", True, "7346474643827462667", "51067351", "563d0dfa49528bb59646384d8a18552a", 0.700, True)
    """Default duration: 0.70s"""
    Item_0_127 = TransitionMeta("Film闪光", True, "7356486482271408666", "56656394", "d3eb0fe7d4088694cc0f9ca02cad07b2", 1.000, True)
    """Default duration: 1.00s"""
    Glitch_5 = TransitionMeta("色块Glitch", True, "7104539089629614606", "2483334", "1f60c6b995a4cf2212dfd9038f738706", 3.000, False)
    """Default duration: 3.00s"""
    Glitch_6 = TransitionMeta("色差Glitch", True, "6724239785205961228", "2918075", "9de90519d59e432b81c38423aa0393d7", 1.000, False)
    """Default duration: 1.00s"""
    _IV = TransitionMeta("色彩溶解 IV", True, "7171714374912971271", "6736571", "a113cd4e04b969f3d988d76899885d42", 0.800, True)
    """Default duration: 0.80s"""
    _V = TransitionMeta("色彩溶解 V", True, "7171714652248740365", "6736575", "da37129b95501377039f01acfded91fc", 0.800, True)
    """Default duration: 0.80s"""
    Item_0_128 = TransitionMeta("色彩负片", True, "7438535170317095451", "91077958", "c33d27f49534075f9076aa97ad06351f", 2.000, True)
    """Default duration: 2.00s"""
    Item_0_129 = TransitionMeta("色散晃镜", True, "7340477409478578738", "48127374", "554ea6d10cd7fbb24ccd24bd91d8c7e1", 0.600, True)
    """Default duration: 0.60s"""
    Item_0_130 = TransitionMeta("色散波纹", True, "7385028833356812840", "72834771", "b56e5f23bd777160a81809df42933b8f", 1.000, True)
    """Default duration: 1.00s"""
    Vortex_2 = TransitionMeta("色散Vortex", True, "7402904919188967963", "79026278", "15a84ee616e08311c77dffe269288c63", 0.800, True)
    """Default duration: 0.80s"""
    Item_0_131 = TransitionMeta("色散闪烁", True, "7234416277974946365", "13830295", "2d9f72076aeefe8f52dfd1a012cd5127", 0.800, True)
    """Default duration: 0.80s"""
    _II_15 = TransitionMeta("色散闪烁 II", True, "7281584246882308665", "23586159", "5f501bb3da1bcbd2ffadca8b916eba81", 0.700, True)
    """Default duration: 0.70s"""
    Transition_1 = TransitionMeta("草图Transition", True, "7439255870891889162", "92006144", "fba0166dc7c61408454dc5e60071dda7", 1.000, True)
    """Default duration: 1.00s"""
    Item_0_132 = TransitionMeta("荧光爆闪", True, "7342499359503684150", "48938221", "a2d70591b5f8dcc52298426ca626c931", 0.800, True)
    """Default duration: 0.80s"""
    Flip_5 = TransitionMeta("菱格Flip转", True, "6983867136510792206", "1187052", "99c0d1524575c7f7020cd77d36a6b008", 1.450, True)
    """Default duration: 1.45s"""
    Scan_1 = TransitionMeta("蓝光Scan", True, "7275176500381356599", "22119723", "95462badbbb87bd7dc4e1d7b04e58306", 1.000, True)
    """Default duration: 1.00s"""
    Item_0_133 = TransitionMeta("蓝色反转片", True, "7200358812316865085", "9504705", "41e718fd6dbac560c6c7a23afc66e50b", 0.800, True)
    """Default duration: 0.80s"""
    Item_0_134 = TransitionMeta("虹光旋入", True, "7401039727761035815", "78355265", "59aaa373c4205aadd62cae40f80df9b5", 1.000, True)
    """Default duration: 1.00s"""
    Item_0_135 = TransitionMeta("融化", True, "7198096122970116663", "9261283", "a0db335169668ca09f5244aa487730c0", 1.000, True)
    """Default duration: 1.00s"""
    _II_16 = TransitionMeta("融化 II", True, "7200339965442527803", "9503051", "74a83d45bdccf5d27bd4b55ddd2733f3", 1.000, True)
    """Default duration: 1.00s"""
    Transition_2 = TransitionMeta("课本Transition", True, "7440040705499599411", "92924027", "98a03de05f89c064dc28e31ddf3690ad", 1.600, True)
    """Default duration: 1.60s"""
    DownSlide_2 = TransitionMeta("负片DownSlide", True, "7302412902181376539", "29999964", "e2db0036d057c27aea3460f3442aedf9", 0.600, True)
    """Default duration: 0.60s"""
    Item_0_136 = TransitionMeta("赛博马赛克", True, "7450031573962854963", "97482741", "b6858b185f28ea0995283665badf7a5a", 2.000, True)
    """Default duration: 2.00s"""
    Item_0_137 = TransitionMeta("超赞", True, "7070430749547041293", "1600477", "e0bd13b237d73eb121473c442c752a23", 0.500, True)
    """Default duration: 0.50s"""
    Item_0_138 = TransitionMeta("边框切换", True, "7434412782285509157", "89307364", "0c5440042359e1d8affab2b2631c23f8", 2.000, True)
    """Default duration: 2.00s"""
    Compress_1 = TransitionMeta("运镜Compress", True, "7447351621266182665", "96240499", "43f8c66c156a4bc8cf48809a908c8f14", 2.000, True)
    """Default duration: 2.00s"""
    Item_0_139 = TransitionMeta("迷幻波纹", True, "7441523705835950619", "93683056", "45b2ac1b9cea1a001a43e673151d1e34", 1.000, True)
    """Default duration: 1.00s"""
    Item_0_140 = TransitionMeta("迷幻频闪", True, "7436273714733257242", "90037012", "74e7013b196e25699e436052c3a3a39f", 1.000, True)
    """Default duration: 1.00s"""
    Glitch_7 = TransitionMeta("透镜Glitch", True, "7097849004062413343", "1889546", "bc652327bcde0e6bf9db8a89d371dd05", 0.500, True)
    """Default duration: 0.50s"""
    DissolveUpSlide = TransitionMeta("重DissolveUpSlide", True, "7232587870672785980", "13582109", "aea42365eeb8cd0df3e4e422cde45e8a", 1.200, True)
    """Default duration: 1.20s"""
    Item_0_141 = TransitionMeta("金币祝福", True, "7326856503963423282", "41488441", "64d858d0716bb9fc9f5b4497afab8206", 1.500, True)
    """Default duration: 1.50s"""
    Item_0_142 = TransitionMeta("金沙", True, "7439681605804757541", "92634974", "21a5ca5fc6862b1baa4813f2c0ff294d", 1.740, True)
    """Default duration: 1.74s"""
    Item_0_143 = TransitionMeta("金色光斑", True, "7317211103652483621", "37131315", "f9224f91ef353fefa3bae96af26a447e", 0.800, True)
    """Default duration: 0.80s"""
    Item_0_144 = TransitionMeta("钱兔无量", True, "7189608212193088060", "8605167", "a6c068f7790c563231b8df2b5796d60c", 1.500, True)
    """Default duration: 1.50s"""
    Move = TransitionMeta("镜头速Move", True, "7418201851507511849", "83974069", "30be83d2e7ed1f2f1fe74b9cfe51c206", 0.567, True)
    """Default duration: 0.57s"""
    Item_0_145 = TransitionMeta("长曝光", True, "7306435255286633010", "31452163", "c239e26c5f99cf83cabd28f63d04b93f", 1.000, True)
    """Default duration: 1.00s"""
    Item_0_146 = TransitionMeta("闪光灯", True, "6986584807543149063", "4202532", "9abfb7452d046a1dafd4d9525b58ec3a", 1.000, True)
    """Default duration: 1.00s"""
    _II_17 = TransitionMeta("闪光灯 II", True, "7244074212158083641", "15250161", "1fcc7fccf7829d94f2747938fcb84706", 1.900, True)
    """Default duration: 1.90s"""
    _III_5 = TransitionMeta("闪光灯 III", True, "7246234663755190839", "15638113", "5af30d0f877301d5235b925ccbda0703", 0.800, True)
    """Default duration: 0.80s"""
    Item_0_147 = TransitionMeta("闪动光斑", True, "6777178510050988551", "4202525", "06560e9ea51f532b18b7e5ae23bd2b9c", 0.500, False)
    """Default duration: 0.50s"""
    _II_18 = TransitionMeta("闪动光斑 II", True, "7148374073716773407", "4840333", "ffeb2bd8b46b0a212c1fbf004aeac626", 1.000, True)
    """Default duration: 1.00s"""
    Item_0_148 = TransitionMeta("闪回", True, "7250427149318885945", "16638473", "0a22de17ce5c2fd97f2bd77aa115de77", 0.200, True)
    """Default duration: 0.20s"""
    Glitch_8 = TransitionMeta("闪屏Glitch", True, "7348352782744687130", "52211013", "a76337e1d1e2301f5d13fd7c90c41282", 1.000, True)
    """Default duration: 1.00s"""
    _II_19 = TransitionMeta("闪黑 II", True, "7264932863613604412", "20257185", "1ecd9bf4057919c5aa78002f97e715de", 0.600, True)
    """Default duration: 0.60s"""
    Item_0_149 = TransitionMeta("闹钟", True, "7074854214479909390", "1621980", "eabbd46c7d68fe93406dd55d4178a574", 0.500, False)
    """Default duration: 0.50s"""
    Transition_3 = TransitionMeta("雨刷Transition", True, "7447351621249405477", "96240497", "2fc9fdbde5b730255e5ffd39c610d735", 2.000, True)
    """Default duration: 2.00s"""
    Dissolve_4 = TransitionMeta("雪花Dissolve", True, "7447044441472242185", "96135908", "e30717b01c4d6ace8c1071a5b7537c0d", 3.000, True)
    """Default duration: 3.00s"""
    Item_0_150 = TransitionMeta("雪花四散", True, "7445177785405936165", "95320371", "3982224ea3c1b93e9d6aab2f3039dc78", 2.000, True)
    """Default duration: 2.00s"""
    Item_0_151 = TransitionMeta("雪花环绕", True, "7445177785397547547", "95320370", "b6b74d907b71741dab39e489ce7ec387", 2.000, True)
    """Default duration: 2.00s"""
    Item_0_152 = TransitionMeta("雪雾", True, "7309372378096603699", "32838061", "776c40711e9f0f6f32570bc12ea50f91", 1.700, True)
    """Default duration: 1.70s"""
    _II_20 = TransitionMeta("震动 II", True, "7195815265337086520", "9041507", "f5685f90de96d6541417f0331f84de8a", 1.000, True)
    """Default duration: 1.00s"""
    Item_0_153 = TransitionMeta("震动缩小", True, "7339865466506056207", "47887388", "3cb961ebfd78ef43742e78bca2d04d06", 1.100, True)
    """Default duration: 1.10s"""
    Item_0_154 = TransitionMeta("霓虹闪光", True, "7337938801882305074", "46839548", "60cee393e1ddf8c117ca6856e474d47d", 0.600, True)
    """Default duration: 0.60s"""
    _II_21 = TransitionMeta("霓虹闪光 II", True, "7337946710041170470", "46846588", "b87a9bf7d6c8e93cc9873ccb47ffc4d0", 0.500, True)
    """Default duration: 0.50s"""
    Item_0_155 = TransitionMeta("顺时针三角", True, "7450031573962854939", "97482743", "d02963275288ab14e24791ad2c0edd78", 1.500, True)
    """Default duration: 1.50s"""
    Item_0_156 = TransitionMeta("飘雪", True, "7169510140138230285", "6506905", "b373d6de281f9cc9cec4b52b0f498517", 2.000, True)
    """Default duration: 2.00s"""
    _II_22 = TransitionMeta("飘雪 II", True, "7170983464416580133", "6658449", "f6e6d83024f30ae2ecf739e15e98813a", 2.000, True)
    """Default duration: 2.00s"""
    _II_23 = TransitionMeta("马赛克 II", True, "7322278354579624486", "39369063", "c2c4fdb0da65e27a073eaba6fcf8dd2a", 0.800, True)
    """Default duration: 0.80s"""
    III = TransitionMeta("马赛克III", True, "7397337004502946314", "77055400", "38bcfd99a2076493d72e2544eeb95811", 1.000, True)
    """Default duration: 1.00s"""
    Item_0_157 = TransitionMeta("鱼眼", True, "7158359902950265352", "5508285", "0319d3f53fd0e79e7e7165f27d7eb9bb", 0.800, True)
    """Default duration: 0.80s"""
    _II_24 = TransitionMeta("鱼眼 II", True, "7152723523721499167", "5096381", "6705e7c01ad8518db1428a34b1357d8f", 0.800, True)
    """Default duration: 0.80s"""
    _III_6 = TransitionMeta("鱼眼 III", True, "7270399429297836605", "21261750", "cdaf9cd4712f5f8061110dfed13738fd", 1.333, True)
    """Default duration: 1.33s"""
    Item_0_158 = TransitionMeta("鱼眼波纹", True, "7433711910731649563", "89071756", "f6d9afd9764c5fc849db3ca346d81997", 0.600, True)
    """Default duration: 0.60s"""
    Item_0_159 = TransitionMeta("鸿运四叶草", True, "7460402504589644326", "101453156", "107619867b318820747866cf632d2dee", 2.000, True)
    """Default duration: 2.00s"""
    Wipe_2 = TransitionMeta("黑板Wipe", True, "7433711910723260979", "89071755", "783cfcdc22f1067cd50142b6731f0b92", 2.000, True)
    """Default duration: 2.00s"""
    Item_0_160 = TransitionMeta("黑白摇镜", True, "7306819191724577331", "31620427", "cc6bea0aa49c6824aa42d0448d6d0080", 0.700, True)
    """Default duration: 0.70s"""
    Item_0_161 = TransitionMeta("黑色反转片", True, "7202075814085530149", "9683173", "8e31bcdedda0fe123ad1a71a967ecaa1", 0.800, True)
    """Default duration: 0.80s"""
