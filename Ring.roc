module [RingGeometry, calcRingArc]

RingGeometry : {
    cx : F64,
    cy : F64,
    radius : F64,
    progress : F64,
    startAngle : F64,
    endAngle : F64,
    startX : F64,
    startY : F64,
    endX : F64,
    endY : F64,
    startPoint : (F64, F64),
    endPoint : (F64, F64),
    largeArc : Bool,
    sweepAngle : F64,
}

calcRingArc : (F64, F64), F64, F64 -> RingGeometry
calcRingArc = |(cx, cy), radius, progress|
    share = Num.min (Num.max progress 0.0) 1.0

    emptyAngle = 2.0 * Num.pi * (1.0 - share)

    startX = cx + radius * Num.sin emptyAngle
    startY = cy - radius * Num.cos emptyAngle

    endX = cx
    endY = cy - radius

    startAngle = (-Num.pi) / 2.0 + emptyAngle
    sweepAngle = 2.0 * Num.pi * share
    endAngle = startAngle + sweepAngle

    largeArc = share > 0.5

    {
        cx,
        cy,
        radius,
        progress: share,
        startAngle,
        endAngle,
        startX,
        startY,
        endX,
        endY,
        startPoint: (startX, startY),
        endPoint: (endX, endY),
        largeArc,
        sweepAngle,
    }

expect
    g = calcRingArc (50.0, 50.0) 40.0 1.0
    Num.is_approx_eq g.startX 50.0 {}
    and Num.is_approx_eq g.startY 10.0 {}
    and Num.is_approx_eq g.endX 50.0 {}
    and Num.is_approx_eq g.endY 10.0 {}
    and g.largeArc
    == Bool.true

expect
    g = calcRingArc (50.0, 50.0) 40.0 0.5
    Num.is_approx_eq g.startX 50.0 {}
    and Num.is_approx_eq g.startY 90.0 {}
    and Num.is_approx_eq g.endX 50.0 {}
    and Num.is_approx_eq g.endY 10.0 {}
    and g.largeArc
    == Bool.false

expect
    g = calcRingArc (50.0, 50.0) 40.0 0.25
    Num.is_approx_eq g.startX 10.0 {}
    and Num.is_approx_eq g.startY 50.0 {}
    and g.largeArc
    == Bool.false
