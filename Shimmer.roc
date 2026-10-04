module [ShimmerRow, calculateRows, sheenOffset]

ShimmerRow : {
    y : F64,
    width : F64,
    height : F64,
    radius : F64,
    alpha : F64,
}

rowConfig : List (F64, F64)
rowConfig = [
    (0.58, 0.55),
    (0.84, 1.00),
    (0.42, 0.55),
]

rowHeight : F64
rowHeight = 18.0

gapHeight : F64
gapHeight = 4.0

barHeight : F64
barHeight = 10.0

bandWidth : F64
bandWidth = 170.0

slantFactor : F64
slantFactor = 0.35

passSec : F64
passSec = 1.5

totalCycleSec : F64
totalCycleSec = 2.1

calculateRows : F64, F64 -> List ShimmerRow
calculateRows = |totalWidth, totalHeight|
    numRows = 3.0
    totalContentHeight = numRows * rowHeight + 2.0 * gapHeight
    topOffset = (totalHeight - totalContentHeight) / 2.0
    radius = barHeight / 2.0

    List.map_with_index rowConfig |(wShare, alpha), idx|
        i = Num.to_f64 idx
        y = topOffset + i * (rowHeight + gapHeight) + (rowHeight - barHeight) / 2.0
        width = Num.round (totalWidth * wShare) |> Num.to_f64
        {
            y,
            width,
            height: barHeight,
            radius,
            alpha,
        }

sineEaseInOut : F64 -> F64
sineEaseInOut = |t|
    clamped = Num.min 1.0 (Num.max 0.0 t)
    0.5 - 0.5 * Num.cos (clamped * 3.141592653589793)

floatMod : F64, F64 -> F64
floatMod = |val, m|
    q = Num.to_f64 (Num.floor (val / m))
    val - q * m

sheenOffset : F64, F64 -> F64
sheenOffset = |elapsed, totalWidth|
    cycle = Num.max 0.0 elapsed
    phase =
        if cycle >= totalCycleSec then
            floatMod cycle totalCycleSec
        else
            cycle

    fromX = -bandWidth - 3.0 * (rowHeight + gapHeight) * slantFactor
    toX = totalWidth + bandWidth

    if phase <= passSec then
        t = phase / passSec
        eased = sineEaseInOut t
        fromX + (toX - fromX) * eased
    else
        toX

expect
    rows = calculateRows 340.0 70.0
    List.len rows == 3

expect
    offStart = sheenOffset 0.0 340.0
    offStart < 0.0

expect
    offRest = sheenOffset 1.8 340.0
    offRest >= 340.0 + bandWidth
