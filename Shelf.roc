module [
    tileWidth,
    tileSquare,
    tileStep,
    shelfWidth,
    shelfHeight,
    shelfStripWidth,
    calculateOverflow,
    carryShelfWidth,
    edgeAlpha,
]

tileWidth : F64
tileWidth = 64.0

tileSquare : F64
tileSquare = 56.0

tileStep : F64
tileStep = 68.0

shelfWidth : F64
shelfWidth = 380.0

shelfHeight : F64
shelfHeight = 136.0

shelfStripWidth : F64
shelfStripWidth = 344.0

calculateOverflow : U64 -> F64
calculateOverflow = |count|
    if count == 0 then
        0.0
    else
        c = Num.to_f64 count
        totalTilesWidth = c * tileStep - 4.0
        Num.max 0.0 (totalTilesWidth - shelfStripWidth)

carryShelfWidth : U64 -> F64
carryShelfWidth = |count|
    if count >= 100 then
        64.0
    else if count >= 10 then
        54.0
    else
        50.0

edgeAlpha : F64, F64 -> F64
edgeAlpha = |past, fadeDistance|
    if past <= 0.0 then
        1.0
    else
        clamped = Num.min 1.0 (past / fadeDistance)
        1.0 - clamped

expect
    overflow0 = calculateOverflow 0
    Num.is_approx_eq overflow0 0.0 {}

expect
    overflow5 = calculateOverflow 5
    Num.is_approx_eq overflow5 0.0 {}

expect
    overflow10 = calculateOverflow 10
    overflow10 > 0.0

expect
    w1 = carryShelfWidth 5
    w2 = carryShelfWidth 120
    w1 < w2
