module [
    Settings,
    defaultSettings,
    clampScale,
    clampGap,
    setLyrics,
    setRim,
    setScale,
    setGap,
    setClickLock,
    setCapitalizeTitle,
    setLineBar,
    setEqualizerDots,
]

Settings : {
    lyrics : Bool,
    lyricEffects : Bool,
    rim : Bool,
    appVolume : Bool,
    network : Bool,
    hideFullscreen : Bool,
    clickLock : Bool,
    scale : U64,
    gap : U64,
    autostart : Bool,
    capitalizeTitle : Bool,
    lineBar : Bool,
    equalizerDots : Bool,
}

minScale : U64
minScale = 85

maxScale : U64
maxScale = 130

maxGap : U64
maxGap = 24

clampScale : U64 -> U64
clampScale = |val|
    Num.max minScale (Num.min maxScale val)

clampGap : U64 -> U64
clampGap = |val|
    Num.max 0 (Num.min maxGap val)

defaultSettings : Settings
defaultSettings = {
    lyrics: Bool.true,
    lyricEffects: Bool.true,
    rim: Bool.true,
    appVolume: Bool.true,
    network: Bool.true,
    hideFullscreen: Bool.true,
    clickLock: Bool.true,
    scale: 100,
    gap: 8,
    autostart: Bool.false,
    capitalizeTitle: Bool.true,
    lineBar: Bool.false,
    equalizerDots: Bool.false,
}

setLyrics : Settings, Bool -> Settings
setLyrics = |settings, lyrics|
    { settings & lyrics }

setLineBar : Settings, Bool -> Settings
setLineBar = |settings, lineBar|
    { settings & lineBar }

setEqualizerDots : Settings, Bool -> Settings
setEqualizerDots = |settings, equalizerDots|
    { settings & equalizerDots }

setRim : Settings, Bool -> Settings
setRim = |settings, rim|
    { settings & rim }

setScale : Settings, U64 -> Settings
setScale = |settings, scale|
    { settings & scale: clampScale scale }

setGap : Settings, U64 -> Settings
setGap = |settings, gap|
    { settings & gap: clampGap gap }

setClickLock : Settings, Bool -> Settings
setClickLock = |settings, clickLock|
    { settings & clickLock }

setCapitalizeTitle : Settings, Bool -> Settings
setCapitalizeTitle = |settings, capitalizeTitle|
    { settings & capitalizeTitle }

expect
    d = defaultSettings
    d.lyrics
    == Bool.true
    and d.lyricEffects
    == Bool.true
    and d.rim
    == Bool.true
    and d.appVolume
    == Bool.true
    and d.network
    == Bool.true
    and d.hideFullscreen
    == Bool.true
    and d.scale
    == 100
    and d.gap
    == 8
    and d.autostart
    == Bool.false
    and d.capitalizeTitle
    == Bool.true

expect
    clampScale 50
    == 85
    and clampScale 85
    == 85
    and clampScale 100
    == 100
    and clampScale 130
    == 130
    and clampScale 200
    == 130

expect
    clampGap 0
    == 0
    and clampGap 8
    == 8
    and clampGap 24
    == 24
    and clampGap 50
    == 24

expect
    s1 = setScale defaultSettings 150
    s2 = setScale defaultSettings 50
    s3 = setScale defaultSettings 115
    s1.scale
    == 130
    and s2.scale
    == 85
    and s3.scale
    == 115

expect
    g1 = setGap defaultSettings 100
    g2 = setGap defaultSettings 16
    g1.gap
    == 24
    and g2.gap
    == 16

expect
    s =
        defaultSettings
        |> setLyrics Bool.false
        |> setRim Bool.false
        |> setScale 120
        |> setGap 12
        |> setCapitalizeTitle Bool.false
    s.lyrics
    == Bool.false
    and s.rim
    == Bool.false
    and s.scale
    == 120
    and s.gap
    == 12
    and s.network
    == Bool.true
    and s.autostart
    == Bool.false
    and s.capitalizeTitle
    == Bool.false
