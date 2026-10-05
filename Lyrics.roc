module [LyricLine, KaraokeSweep, parseLrcLine, findActiveLine, calcKaraokeSweep, isWordless]

LyricLine : {
    time : F64,
    text : Str,
}

KaraokeSweep : {
    progress : F64,
    litWidth : F64,
    edgeWidth : F64,
    totalWidth : F64,
    unsungOpacity : F64,
}

parseTimestamp : Str -> Result F64 [InvalidTimestamp]
parseTimestamp = |str|
    trimmed = Str.trim str
    innerRes =
        if Str.starts_with trimmed "[" then
            if Str.ends_with trimmed "]" then
                Ok (Str.drop_prefix (Str.drop_suffix trimmed "]") "[")
            else
                Err InvalidTimestamp
        else if Str.ends_with trimmed "]" then
            Err InvalidTimestamp
        else
            Ok trimmed

    when innerRes is
        Err InvalidTimestamp -> Err InvalidTimestamp
        Ok innerRaw ->
            inner = Str.trim innerRaw
            parts = Str.split_on inner ":"
            when parts is
                [minRaw, secRaw] ->
                    minStr = Str.trim minRaw
                    secStr = Str.trim secRaw
                    if isValidDigits minStr and isValidSeconds secStr then
                        when (Str.to_f64 minStr, Str.to_f64 secStr) is
                            (Ok min, Ok sec) ->
                                if min >= 0.0 and sec >= 0.0 then
                                    Ok (min * 60.0 + sec)
                                else
                                    Err InvalidTimestamp

                            _ -> Err InvalidTimestamp
                    else
                        Err InvalidTimestamp

                [hrRaw, minRaw, secRaw] ->
                    hrStr = Str.trim hrRaw
                    minStr = Str.trim minRaw
                    secStr = Str.trim secRaw
                    if isValidDigits hrStr and isValidDigits minStr and isValidSeconds secStr then
                        when (Str.to_f64 hrStr, Str.to_f64 minStr, Str.to_f64 secStr) is
                            (Ok hr, Ok min, Ok sec) ->
                                if hr >= 0.0 and min >= 0.0 and sec >= 0.0 then
                                    Ok (hr * 3600.0 + min * 60.0 + sec)
                                else
                                    Err InvalidTimestamp

                            _ -> Err InvalidTimestamp
                    else
                        Err InvalidTimestamp

                _ -> Err InvalidTimestamp

isValidDigits : Str -> Bool
isValidDigits = |s|
    bytes = Str.to_utf8 s
    !(List.is_empty bytes) and List.all bytes |b| b >= '0' and b <= '9'

isValidSeconds : Str -> Bool
isValidSeconds = |s|
    bytes = Str.to_utf8 s
    if List.is_empty bytes then
        Bool.false
    else
        dotCount = List.count_if bytes |b| b == '.'
        allDigitsOrDot = List.all bytes |b| (b >= '0' and b <= '9') or b == '.'
        dotCount <= 1 and allDigitsOrDot

stripAdditionalTimestamps : Str -> Str
stripAdditionalTimestamps = |text|
    trimmed = Str.trim text
    if Str.starts_with trimmed "[" then
        when Str.split_first trimmed "]" is
            Ok { before, after } ->
                stampCandidate = Str.concat before "]"
                when parseTimestamp stampCandidate is
                    Ok _ ->
                        stripAdditionalTimestamps after

                    Err InvalidTimestamp ->
                        trimmed

            Err _ ->
                trimmed
    else
        trimmed

parseLrcLine : Str -> Result LyricLine [NotLyrics]
parseLrcLine = |line|
    trimmed = Str.trim line
    if Str.starts_with trimmed "[" then
        when Str.split_first trimmed "]" is
            Ok { before, after } ->
                stampCandidate = Str.concat before "]"
                when parseTimestamp stampCandidate is
                    Ok time ->
                        text = stripAdditionalTimestamps after
                        Ok { time, text }

                    Err InvalidTimestamp ->
                        Err NotLyrics

            Err _ ->
                Err NotLyrics
    else
        Err NotLyrics

findActiveLine : List LyricLine, F64 -> { index : I64, line : Result LyricLine [NotFound], progress : F64 }
findActiveLine = |lines, position|
    best = findActiveIndexHelp lines position 0 (Err NotFound)
    when best is
        Err NotFound ->
            {
                index: -1i64,
                line: Err NotFound,
                progress: 0.0,
            }

        Ok { idx } ->
            when List.get lines idx is
                Ok currentLine ->
                    duration =
                        when List.get lines (idx + 1) is
                            Ok nextLine ->
                                gap = nextLine.time - currentLine.time
                                if gap > 0.0 then
                                    Num.min gap 8.0
                                else
                                    8.0

                            Err _ ->
                                8.0

                    elapsed = position - currentLine.time
                    rawProgress =
                        if duration <= 0.0 then
                            1.0
                        else
                            elapsed / duration

                    progress = Num.min (Num.max rawProgress 0.0) 1.0

                    {
                        index: Num.to_i64 idx,
                        line: Ok currentLine,
                        progress,
                    }

                Err _ ->
                    {
                        index: -1i64,
                        line: Err NotFound,
                        progress: 0.0,
                    }

findActiveIndexHelp : List LyricLine, F64, U64, Result { idx : U64, time : F64 } [NotFound] -> Result { idx : U64, time : F64 } [NotFound]
findActiveIndexHelp = |lines, position, idx, best|
    if idx >= List.len lines then
        best
    else
        when List.get lines idx is
            Ok line ->
                if line.time <= position then
                    newBest =
                        when best is
                            Ok b ->
                                if line.time >= b.time then
                                    Ok { idx, time: line.time }
                                else
                                    best

                            Err NotFound ->
                                Ok { idx, time: line.time }

                    findActiveIndexHelp lines position (idx + 1) newBest
                else
                    findActiveIndexHelp lines position (idx + 1) best

            Err _ ->
                best

calcKaraokeSweep : F64, F64 -> KaraokeSweep
calcKaraokeSweep = |arg1, arg2|
    (progressArg, widthArg) =
        if arg1 > 1.0 and arg2 <= 1.0 then
            (arg2, arg1)
        else
            (arg1, arg2)

    edgeWidth = 26.0
    unsungOpacity = 0.6
    totalWidth = Num.max widthArg 0.0
    progress = Num.min (Num.max progressArg 0.0) 1.0

    at = progress * (totalWidth + edgeWidth)
    from = Num.min (Num.max at 0.0) (totalWidth + edgeWidth) - edgeWidth
    litWidth = Num.min (Num.max from 0.0) totalWidth

    {
        progress,
        litWidth,
        edgeWidth,
        totalWidth,
        unsungOpacity,
    }

isWordless : Str -> Bool
isWordless = |text|
    bytes = Str.to_utf8 text
    !(List.any bytes |b| (b >= '0' and b <= '9') or (b >= 'A' and b <= 'Z') or (b >= 'a' and b <= 'z'))

expect isWordless "" == Bool.true
expect isWordless "♪" == Bool.true
expect isWordless "---" == Bool.true
expect isWordless "Hello" == Bool.false
expect isWordless "123" == Bool.false

expect
    when parseTimestamp "[01:23.45]" is
        Ok t -> Num.is_approx_eq t 83.45 {}
        Err _ -> Bool.false

expect
    when parseTimestamp "01:23.45" is
        Ok t -> Num.is_approx_eq t 83.45 {}
        Err _ -> Bool.false

expect
    when parseTimestamp "[00:00.00]" is
        Ok t -> Num.is_approx_eq t 0.0 {}
        Err _ -> Bool.false

expect
    when parseTimestamp "[02:15]" is
        Ok t -> Num.is_approx_eq t 135.0 {}
        Err _ -> Bool.false

expect
    when parseTimestamp "[00:15.5]" is
        Ok t -> Num.is_approx_eq t 15.5 {}
        Err _ -> Bool.false

expect
    when parseTimestamp "[01:02:03.45]" is
        Ok t -> Num.is_approx_eq t 3723.45 {}
        Err _ -> Bool.false

expect
    when parseTimestamp "[ti:Never Gonna Give You Up]" is
        Err InvalidTimestamp -> Bool.true
        Ok _ -> Bool.false

expect
    when parseTimestamp "[01:23.45" is
        Err InvalidTimestamp -> Bool.true
        Ok _ -> Bool.false

expect
    when parseTimestamp "01:23.45]" is
        Err InvalidTimestamp -> Bool.true
        Ok _ -> Bool.false

expect
    when parseTimestamp "" is
        Err InvalidTimestamp -> Bool.true
        Ok _ -> Bool.false

expect
    when parseLrcLine "[01:23.45] Hello world" is
        Ok { time, text } -> Num.is_approx_eq time 83.45 {} and text == "Hello world"
        Err _ -> Bool.false

expect
    when parseLrcLine "[00:10.00][00:20.00] Echo" is
        Ok { time, text } -> Num.is_approx_eq time 10.0 {} and text == "Echo"
        Err _ -> Bool.false

expect
    when parseLrcLine "[01:23.45] [Guitar Solo]" is
        Ok { time, text } -> Num.is_approx_eq time 83.45 {} and text == "[Guitar Solo]"
        Err _ -> Bool.false

expect
    when parseLrcLine "[01:23.45]" is
        Ok { time, text } -> Num.is_approx_eq time 83.45 {} and text == ""
        Err _ -> Bool.false

expect
    when parseLrcLine "[ti:Song Title]" is
        Err NotLyrics -> Bool.true
        Ok _ -> Bool.false

expect
    when parseLrcLine "Plain lyrics without timing" is
        Err NotLyrics -> Bool.true
        Ok _ -> Bool.false

expect
    when parseLrcLine "" is
        Err NotLyrics -> Bool.true
        Ok _ -> Bool.false

sampleLines : List LyricLine
sampleLines = [
    { time: 10.0, text: "Line 1" },
    { time: 14.0, text: "Line 2" },
    { time: 24.0, text: "Line 3" },
]

expect
    res = findActiveLine sampleLines 5.0
    isNotFound =
        when res.line is
            Err NotFound -> Bool.true
            Ok _ -> Bool.false

    res.index
    == -1i64
    and isNotFound
    and Num.is_approx_eq res.progress 0.0 {}

expect
    res = findActiveLine sampleLines 10.0
    matchesLine1 =
        when res.line is
            Ok l -> l.text == "Line 1" and Num.is_approx_eq l.time 10.0 {}
            Err _ -> Bool.false

    res.index
    == 0i64
    and matchesLine1
    and Num.is_approx_eq res.progress 0.0 {}

expect
    res = findActiveLine sampleLines 12.0
    res.index
    == 0i64
    and Num.is_approx_eq res.progress 0.5 {}

expect
    res = findActiveLine sampleLines 14.0
    matchesLine2 =
        when res.line is
            Ok l -> l.text == "Line 2" and Num.is_approx_eq l.time 14.0 {}
            Err _ -> Bool.false

    res.index
    == 1i64
    and matchesLine2
    and Num.is_approx_eq res.progress 0.0 {}

expect
    res = findActiveLine sampleLines 18.0
    res.index
    == 1i64
    and Num.is_approx_eq res.progress 0.5 {}

expect
    res = findActiveLine sampleLines 22.0
    res.index
    == 1i64
    and Num.is_approx_eq res.progress 1.0 {}

expect
    res = findActiveLine sampleLines 23.5
    res.index
    == 1i64
    and Num.is_approx_eq res.progress 1.0 {}

expect
    res = findActiveLine sampleLines 24.0
    matchesLine3 =
        when res.line is
            Ok l -> l.text == "Line 3" and Num.is_approx_eq l.time 24.0 {}
            Err _ -> Bool.false

    res.index
    == 2i64
    and matchesLine3
    and Num.is_approx_eq res.progress 0.0 {}

expect
    res = findActiveLine sampleLines 28.0
    res.index
    == 2i64
    and Num.is_approx_eq res.progress 0.5 {}

expect
    res = findActiveLine sampleLines 40.0
    res.index
    == 2i64
    and Num.is_approx_eq res.progress 1.0 {}

expect
    res = findActiveLine [] 15.0
    isNotFound =
        when res.line is
            Err NotFound -> Bool.true
            Ok _ -> Bool.false

    res.index
    == -1i64
    and isNotFound
    and Num.is_approx_eq res.progress 0.0 {}

expect
    sw = calcKaraokeSweep 0.0 100.0
    Num.is_approx_eq sw.progress 0.0 {}
    and Num.is_approx_eq sw.litWidth 0.0 {}
    and Num.is_approx_eq sw.edgeWidth 26.0 {}
    and Num.is_approx_eq sw.totalWidth 100.0 {}
    and Num.is_approx_eq sw.unsungOpacity 0.6 {}

expect
    sw = calcKaraokeSweep 1.0 100.0
    Num.is_approx_eq sw.progress 1.0 {}
    and Num.is_approx_eq sw.litWidth 100.0 {}
    and Num.is_approx_eq sw.edgeWidth 26.0 {}
    and Num.is_approx_eq sw.totalWidth 100.0 {}
    and Num.is_approx_eq sw.unsungOpacity 0.6 {}

expect
    sw = calcKaraokeSweep 0.5 100.0
    Num.is_approx_eq sw.progress 0.5 {}
    and Num.is_approx_eq sw.litWidth 37.0 {}
    and Num.is_approx_eq sw.edgeWidth 26.0 {}
    and Num.is_approx_eq sw.totalWidth 100.0 {}
    and Num.is_approx_eq sw.unsungOpacity 0.6 {}

expect
    sw = calcKaraokeSweep 200.0 0.5
    Num.is_approx_eq sw.progress 0.5 {}
    and Num.is_approx_eq sw.litWidth 87.0 {}
    and Num.is_approx_eq sw.edgeWidth 26.0 {}
    and Num.is_approx_eq sw.totalWidth 200.0 {}
    and Num.is_approx_eq sw.unsungOpacity 0.6 {}
