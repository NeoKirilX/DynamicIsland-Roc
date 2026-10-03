module [Aura, init, tick, Patch]

Patch : {
    anchor : F64,
    x : F64,
    level : F64,
    speed : F64,
    phase : F64,
    colorIdx : U64,
}

Aura : {
    patches : List Patch,
    time : F64,
}

attack : F64
attack = 0.07

release : F64
release = 0.45

drift : F64
drift = 0.06

falloff : List (F64, F64)
falloff = [
    (0.0, 1.0),
    (0.25, 0.7),
    (0.5, 0.3),
    (0.75, 0.07),
    (1.0, 0.0),
]

init : Aura
init =
    initialLevel =
        when List.last falloff is
            Ok (_, alpha) -> alpha
            Err _ -> 0.0

    p0 = {
        anchor: 0.40,
        x: 0.40 + drift * Num.sin 0.0,
        level: initialLevel,
        speed: 0.55,
        phase: 0.0,
        colorIdx: 1,
    }
    p1 = {
        anchor: 0.63,
        x: 0.63 + drift * Num.sin 2.1,
        level: initialLevel,
        speed: 0.43,
        phase: 2.1,
        colorIdx: 2,
    }
    p2 = {
        anchor: 0.15,
        x: 0.15 + drift * Num.sin 4.0,
        level: initialLevel,
        speed: 0.71,
        phase: 4.0,
        colorIdx: 0,
    }
    p3 = {
        anchor: 0.86,
        x: 0.86 + drift * Num.sin 5.3,
        level: initialLevel,
        speed: 0.62,
        phase: 5.3,
        colorIdx: 0,
    }
    {
        patches: [p0, p1, p2, p3],
        time: 0.0,
    }

tick : Aura, List F64, F64, F64 -> Aura
tick = |aura, levels, t, dt|
    safeDt = Num.max dt 0.0001
    rise = 1.0 - Num.pow Num.e (-safeDt / attack)
    fall = 1.0 - Num.pow Num.e (-safeDt / release)

    numBars = List.len levels
    numPatches = List.len aura.patches

    updatedPatches =
        List.map_with_index aura.patches (|patch, pIdx|
            target =
                if numBars == 0 then
                    0.0
                else
                    from = (pIdx * numBars) // numPatches
                    to = Num.max (((pIdx + 1) * numBars) // numPatches) (from + 1)
                    actualTo = Num.min to numBars
                    actualFrom = Num.min from actualTo
                    sliceLen = if actualTo > actualFrom then actualTo - actualFrom else 0

                    if sliceLen == 0 then
                        0.0
                    else
                        sum =
                            List.sublist levels { start: actualFrom, len: sliceLen }
                            |> List.sum
                        sum / Num.to_f64 sliceLen

            factor = if target > patch.level then rise else fall
            nextLevel = patch.level + (target - patch.level) * factor
            nextX = patch.anchor + drift * Num.sin (t * patch.speed + patch.phase)

            {
                anchor: patch.anchor,
                x: nextX,
                level: nextLevel,
                speed: patch.speed,
                phase: patch.phase,
                colorIdx: patch.colorIdx,
            }
        )

    {
        patches: updatedPatches,
        time: t,
    }

expect
    aura = init
    List.len aura.patches == 4 && aura.time <= 0.001

expect
    aura0 = init
    levels = [0.8, 0.6, 0.4, 0.2, 0.1]
    aura1 = tick aura0 levels 1.0 0.016
    List.all aura1.patches (|p| p.level > 0.0)

expect
    aura0 = init
    aura1 = tick aura0 [] 10.0 0.016
    List.all aura1.patches (|p| p.level <= 0.001)

expect
    aura0 = init
    aura1 = tick aura0 [0.5] 2.0 0.016
    p0 = List.get aura1.patches 0 |> Result.with_default { anchor: 0.0, x: 0.0, level: 0.0, speed: 0.0, phase: 0.0, colorIdx: 0 }
    expectedX = 0.40 + 0.06 * Num.sin (2.0 * 0.55 + 0.0)
    Num.abs (p0.x - expectedX) < 1e-6
