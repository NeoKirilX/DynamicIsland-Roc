module [
    minMusicDuration,
    isEligibleDuration,
    hasTrack,
    cleanTrackTitle,
    capitalizeFirst,
    formatDisplayTitle,
]

minMusicDuration : F64
minMusicDuration = 30.0

isEligibleDuration : F64 -> Bool
isEligibleDuration = |duration|
    if duration <= 0.0 then
        Bool.true
    else if duration < minMusicDuration then
        Bool.false
    else
        Bool.true

hasTrack : Str, F64 -> Bool
hasTrack = |title, duration|
    trimmed = Str.trim title
    if Str.is_empty trimmed then
        Bool.false
    else
        isEligibleDuration duration

tagsToRemove : List Str
tagsToRemove = [
    "(official audio)",
    "(official video)",
    "(official music video)",
    "(official lyric video)",
    "(lyric video)",
    "(lyrics video)",
    "(lyrics)",
    "(audio)",
    "(visualizer)",
    "(official visualizer)",
    "(sped up)",
    "(speed up)",
    "(slowed + reverb)",
    "(slowed and reverb)",
    "(slowed)",
    "(reverb)",
    "(официальный клип)",
    "(клип)",
    "(премьера клипа)",
    "[official audio]",
    "[official video]",
    "[official music video]",
    "[lyric video]",
    "[lyrics]",
    "[audio]",
    "[visualizer]",
    "[sped up]",
    "[speed up]",
    "[slowed + reverb]",
    "[slowed]",
]

cleanTrackTitle : Str -> Str
cleanTrackTitle = |title|
    cleanStep = |current, tag|
        lower = Str.to_utf8 current |> List.map |b| if b >= 65 and b <= 90 then b + 32 else b
        tagBytes = Str.to_utf8 tag
        when findSublist lower tagBytes 0 is
            Ok idx ->
                prefix = Str.to_utf8 current |> List.take_first idx
                suffix = Str.to_utf8 current |> List.drop_first (idx + List.len tagBytes)
                merged = List.concat prefix suffix
                when Str.from_utf8 merged is
                    Ok s -> Str.trim s
                    Err _ -> current

            Err _ ->
                current

    cleaned = List.walk tagsToRemove (Str.trim title) cleanStep
    Str.trim cleaned

findSublist : List U8, List U8, U64 -> Result U64 [NotFound]
findSublist = |haystack, needle, startIdx|
    needleLen = List.len needle
    haystackLen = List.len haystack
    if needleLen == 0 or startIdx + needleLen > haystackLen then
        Err NotFound
    else
        slice = List.sublist haystack { start: startIdx, len: needleLen }
        if slice == needle then
            Ok startIdx
        else
            findSublist haystack needle (startIdx + 1)

capitalizeFirst : Str -> Str
capitalizeFirst = |str|
    bytes = Str.to_utf8 str
    when bytes is
        [] -> ""
        [first, .. as rest] ->
            capFirst =
                if first >= 97 and first <= 122 then
                    first - 32
                else
                    first
            when Str.from_utf8 (List.prepend rest capFirst) is
                Ok res -> res
                Err _ -> str

formatDisplayTitle : Str, Str, Bool -> Str
formatDisplayTitle = |title, artist, capitalize|
    rawClean = cleanTrackTitle title
    cleaned = if capitalize then capitalizeFirst rawClean else rawClean
    trimmedArtist = Str.trim artist
    if Str.is_empty trimmedArtist then
        cleaned
    else
        "$(cleaned) — $(trimmedArtist)"

expect Num.is_approx_eq minMusicDuration 30.0 {}

expect isEligibleDuration 0.0 == Bool.true
expect isEligibleDuration (-1.0) == Bool.true
expect isEligibleDuration 15.0 == Bool.false
expect isEligibleDuration 29.9 == Bool.false
expect isEligibleDuration 30.0 == Bool.true
expect isEligibleDuration 180.0 == Bool.true

expect hasTrack "" 180.0 == Bool.false
expect hasTrack "Song" 15.0 == Bool.false
expect hasTrack "Song" 120.0 == Bool.true
expect hasTrack "Stream Radio" 0.0 == Bool.true

expect cleanTrackTitle "Starboy (Official Audio)" == "Starboy"
expect cleanTrackTitle "Song [Visualizer]" == "Song"
expect cleanTrackTitle "Track (Sped Up)" == "Track"

expect capitalizeFirst "hello world" == "Hello world"
expect capitalizeFirst "Already Capital" == "Already Capital"

expect formatDisplayTitle "starboy (official audio)" "The Weeknd" Bool.true == "Starboy — The Weeknd"
expect formatDisplayTitle "podcast episode" "" Bool.true == "Podcast episode"
