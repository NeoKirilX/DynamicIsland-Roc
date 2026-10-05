module [Equalizer, init, tick, levelForBar]

Equalizer : {
    bars : U64,
    levels : List F64,
    targets : List F64,
    baselines : List F64,
}

attack : F64
attack = 0.03

release : F64
release = 0.17

rise : F64
rise = 0.4

sink : F64
sink = 0.5

floorDb : F64
floorDb = -70.0

rangeDb : F64
rangeDb = 10.0

center : F64
center = 0.5

spreadDb : F64
spreadDb = 24.0

f1 : List F64
f1 = [7.1, 9.3, 6.2, 10.4, 8.0, 5.6, 9.9, 7.7]

f2 : List F64
f2 = [2.3, 3.1, 1.7, 2.9, 3.7, 2.1, 1.3, 3.3]

init : U64 -> Equalizer
init = |barsCount|
    count = Num.max barsCount 2
    {
        bars: count,
        levels: List.repeat 0.0 count,
        targets: List.repeat 0.0 count,
        baselines: List.repeat floorDb count,
    }

levelForBar : Equalizer, U64 -> F64
levelForBar = |eq, bar|
    List.get eq.levels bar |> Result.with_default 0.0

slotForRank : U64, U64 -> U64
slotForRank = |k, barsCount|
    if barsCount == 0 then
        0
    else
        c = (barsCount - 1) // 2
        if k % 2 == 1 then
            c + (k + 1) // 2
        else if k // 2 <= c then
            c - k // 2
        else
            0

rankForBar : U64, U64 -> U64
rankForBar = |bar, barsCount|
    List.range { start: At 0, end: Before barsCount }
    |> List.find_first_index (|k| slotForRank k barsCount == bar)
    |> Result.with_default 0

wobbleTargets : U64, F64, F64 -> List F64
wobbleTargets = |barsCount, peak, t|
    clampedPeak = Num.max 0.0 (Num.min 1.0 (peak * 1.8))
    level = Num.pow clampedPeak 0.6
    mid = (Num.to_f64 barsCount - 1.0) / 2.0
    List.range { start: At 0, end: Before barsCount }
    |> List.map (|i|
        iF = Num.to_f64 i
        f1Val = List.get f1 (i % 8) |> Result.with_default 7.1
        f2Val = List.get f2 (i % 8) |> Result.with_default 2.3
        noise = 0.5 + 0.5 * Num.sin (t * f1Val + iF * 1.9) * Num.cos (t * f2Val + iF * 0.7)
        envelope = if mid > 0.0 then 1.0 - 0.3 * (Num.abs (iF - mid)) / mid else 1.0
        val = level * envelope * (0.3 + 0.7 * noise)
        Num.max 0.0 (Num.min 1.0 val)
    )

tick : Equalizer, List F64, F64, Bool, F64, F64 -> Equalizer
tick = |eq, spectrum, peak, playing, t, dt|
    safeDt = Num.max dt 0.0001
    barsCount = eq.bars

    { targets, baselines } =
        if !playing then
            {
                targets: List.repeat 0.0 barsCount,
                baselines: eq.baselines,
            }
        else if List.len spectrum > 0 && List.any spectrum (|s| s > 1e-9) then
            spectrumLen = List.len spectrum
            headroom = rangeDb * (1.0 - center)

            barsRange = List.range { start: At 0, end: Before barsCount }
            dbsAndBases =
                List.map barsRange (|i|
                    rank = rankForBar i barsCount
                    from = (rank * spectrumLen) // barsCount
                    to = Num.max (((rank + 1) * spectrumLen) // barsCount) (from + 1)
                    actualTo = Num.min to spectrumLen
                    actualFrom = Num.min from actualTo
                    sliceLen = if actualTo > actualFrom then actualTo - actualFrom else 1

                    power =
                        if actualTo > actualFrom then
                            List.sublist spectrum { start: actualFrom, len: actualTo - actualFrom }
                            |> List.sum
                        else
                            0.0

                    meanPower = power / Num.to_f64 sliceLen
                    db = 10.0 * (Num.log (meanPower + 1e-14) / Num.log 10.0)
                    oldBase = List.get eq.baselines i |> Result.with_default floorDb

                    newBase =
                        if db > floorDb then
                            tau = if db > oldBase then rise else sink
                            b = oldBase + (db - oldBase) * (1.0 - Num.pow Num.e (-safeDt / tau))
                            Num.max b (db - headroom)
                        else
                            oldBase

                    { db, base: newBase }
                )

            top =
                List.walk dbsAndBases floorDb (|acc, item|
                    Num.max acc item.base
                )

            newTgts =
                List.map dbsAndBases (|item|
                    reference = Num.max item.base (top - spreadDb)
                    val = center + (item.db - reference) / rangeDb
                    Num.max 0.0 (Num.min 1.0 val)
                )

            newBases = List.map dbsAndBases (|item| item.base)

            { targets: newTgts, baselines: newBases }
        else if peak > 0.0 then
            {
                targets: wobbleTargets barsCount peak t,
                baselines: eq.baselines,
            }
        else
            {
                targets: List.repeat 0.0 barsCount,
                baselines: eq.baselines,
            }

    riseFactor = 1.0 - Num.pow Num.e (-safeDt / attack)
    fallFactor = 1.0 - Num.pow Num.e (-safeDt / release)

    newLevels =
        List.map_with_index targets (|target, i|
            curr = List.get eq.levels i |> Result.with_default 0.0
            factor = if target > curr then riseFactor else fallFactor
            curr + (target - curr) * factor
        )

    {
        bars: barsCount,
        levels: newLevels,
        targets,
        baselines,
    }

expect
    eq = init 5
    eq.bars == 5 && List.len eq.levels == 5 && levelForBar eq 0 <= 0.001

expect
    ranks = List.range { start: At 0, end: Before 5 } |> List.map (|bar| rankForBar bar 5)
    ranks == [4, 2, 0, 1, 3]

expect
    eq0 = init 5
    spectrum = [0.1, 0.05, 0.01, 0.001, 0.0001]
    eq1 = tick eq0 spectrum 0.5 Bool.true 0.0 0.016
    levelForBar eq1 2 > 0.0

expect
    eq0 = init 5
    eq1 = tick eq0 [0.1, 0.05] 0.5 Bool.false 0.0 0.016
    List.all eq1.targets (|tgt| tgt <= 0.001)

expect
    eq0 = init 5
    eq1 = tick eq0 [] 0.7 Bool.true 1.0 0.016
    List.any eq1.levels (|lvl| lvl > 0.0)
