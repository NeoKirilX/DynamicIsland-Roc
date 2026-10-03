module [Rect, Point, Neck, calcNeck, calcRimColor]

Point : { x : F64, y : F64 }
Rect : { x : F64, y : F64, w : F64, h : F64 }
Color : { r : F64, g : F64, b : F64, a : F64 }
BezierCurve : { start : Point, cp1 : Point, cp2 : Point, end : Point }
Neck : {
    p1 : Point,
    p2 : Point,
    p3 : Point,
    p4 : Point,
    topCurve : BezierCurve,
    bottomCurve : BezierCurve,
}

tear : F64
tear = 7.5

hold : F64
hold = 0.5

handle : F64
handle = 2.4

rim : F64
rim = 1.0

plainAlpha : F64
plainAlpha = 32.0 / 255.0

tintedAlpha : F64
tintedAlpha = 140.0 / 255.0

clamp : F64, F64, F64 -> F64
clamp = |val, low, high|
    Num.max low (Num.min high val)

atan2 : F64, F64 -> F64
atan2 = |y, x|
    if x > 0.0 then
        Num.atan (y / x)
    else if x < 0.0 and y >= 0.0 then
        Num.atan (y / x) + Num.pi
    else if x < 0.0 and y < 0.0 then
        Num.atan (y / x) - Num.pi
    else if y > 0.0 then
        Num.pi / 2.0
    else if y < 0.0 then
        (-Num.pi) / 2.0
    else
        0.0

on : Point, F64, F64 -> Point
on = |centre, angle, rad| {
    x: centre.x + rad * Num.cos angle,
    y: centre.y + rad * Num.sin angle,
}

calcNeck : Rect, F64, Rect -> Result Neck [NoNeck, Detached]
calcNeck = |pill, radius, bubble|
    c1 = {
        x: pill.x + pill.w - radius,
        y: pill.y + radius,
    }
    c2 = {
        x: bubble.x + bubble.h / 2.0,
        y: bubble.y + bubble.h / 2.0,
    }
    r1 = radius - rim
    r2 = bubble.h / 2.0 - rim
    between = {
        x: c2.x - c1.x,
        y: c2.y - c1.y,
    }
    d = Num.sqrt (between.x * between.x + between.y * between.y)
    gap = d - r1 - r2

    if r1 <= 0.0 or r2 <= 0.0 or between.x <= 0.0 or d <= Num.abs (r1 - r2) then
        Err NoNeck
    else if gap >= tear then
        Err Detached
    else
        (u1, u2) =
            if gap < 0.0 then
                cosU1 = clamp ((r1 * r1 + d * d - r2 * r2) / (2.0 * r1 * d)) -1.0 1.0
                cosU2 = clamp ((r2 * r2 + d * d - r1 * r1) / (2.0 * r2 * d)) -1.0 1.0
                (Num.acos cosU1, Num.acos cosU2)
            else
                (0.0, 0.0)

        clampedGapRatio = clamp (gap / tear) 0.0 1.0
        effectiveHold = hold * (1.0 - clampedGapRatio)
        axis = atan2 between.y between.x
        wide = Num.acos (clamp ((r1 - r2) / d) -1.0 1.0)

        a1 = axis + u1 + (wide - u1) * effectiveHold
        a2 = axis - u1 - (wide - u1) * effectiveHold
        a3 = axis + Num.pi - u2 - (Num.pi - u2 - wide) * effectiveHold
        a4 = axis - Num.pi + u2 + (Num.pi - u2 - wide) * effectiveHold

        p1 = on c1 a1 r1
        p2 = on c1 a2 r1
        p3 = on c2 a3 r2
        p4 = on c2 a4 r2

        dx = p1.x - p3.x
        dy = p1.y - p3.y
        distP1P3 = Num.sqrt (dx * dx + dy * dy)
        rSum = r1 + r2

        reach =
            Num.min (effectiveHold * handle) (distP1P3 / rSum)
            * Num.min 1.0 (2.0 * d / rSum)

        quarter = Num.pi / 2.0

        topCurve = {
            start: p2,
            cp1: on p2 (a2 + quarter) (r1 * reach),
            cp2: on p4 (a4 - quarter) (r2 * reach),
            end: p4,
        }

        bottomCurve = {
            start: p1,
            cp1: on p1 (a1 - quarter) (r1 * reach),
            cp2: on p3 (a3 + quarter) (r2 * reach),
            end: p3,
        }

        Ok {
            p1,
            p2,
            p3,
            p4,
            topCurve,
            bottomCurve,
        }

calcRimColor : Color, F64 -> Color
calcRimColor = |tintColor, t|
    factor = clamp t 0.0 1.0
    plainA = plainAlpha
    tintedA = tintedAlpha
    {
        r: 1.0 + (tintColor.r - 1.0) * factor,
        g: 1.0 + (tintColor.g - 1.0) * factor,
        b: 1.0 + (tintColor.b - 1.0) * factor,
        a: plainA + (tintedA - plainA) * factor,
    }

expect
    pill = { x: 50.0, y: 20.0, w: 150.0, h: 34.0 }
    bubble = { x: 205.0, y: 20.0, w: 78.0, h: 34.0 }
    when calcNeck pill 17.0 bubble is
        Ok neck ->
            Num.is_approx_eq neck.p1.x 198.978072556 {}
            and Num.is_approx_eq neck.p1.y 37.837375299 {}
            and Num.is_approx_eq neck.p2.x 198.978072556 {}
            and Num.is_approx_eq neck.p2.y 36.162624700 {}
            and Num.is_approx_eq neck.p3.x 206.021927443 {}
            and Num.is_approx_eq neck.p3.y 37.837375299 {}
            and Num.is_approx_eq neck.p4.x 206.021927443 {}
            and Num.is_approx_eq neck.p4.y 36.162624700 {}
            and Num.is_approx_eq neck.topCurve.start.x 198.978072556 {}
            and Num.is_approx_eq neck.topCurve.end.x 206.021927443 {}
            and Num.is_approx_eq neck.bottomCurve.start.x 198.978072556 {}
            and Num.is_approx_eq neck.bottomCurve.end.x 206.021927443 {}

        Err _ ->
            Bool.false

expect
    pill = { x: 50.0, y: 20.0, w: 150.0, h: 34.0 }
    bubble = { x: 206.0, y: 20.0, w: 78.0, h: 34.0 }
    when calcNeck pill 17.0 bubble is
        Err Detached ->
            Bool.true

        _ ->
            Bool.false

expect
    pill = { x: 50.0, y: 20.0, w: 150.0, h: 34.0 }
    bubble = { x: 400.0, y: 20.0, w: 78.0, h: 34.0 }
    when calcNeck pill 17.0 bubble is
        Err Detached ->
            Bool.true

        _ ->
            Bool.false

expect
    pill = { x: 50.0, y: 20.0, w: 150.0, h: 34.0 }
    bubble = { x: 50.0, y: 20.0, w: 78.0, h: 34.0 }
    when calcNeck pill 17.0 bubble is
        Err NoNeck ->
            Bool.true

        _ ->
            Bool.false

expect
    pill = { x: 50.0, y: 20.0, w: 150.0, h: 34.0 }
    bubble = { x: 205.0, y: 20.0, w: 78.0, h: 34.0 }
    when calcNeck pill 0.5 bubble is
        Err NoNeck ->
            Bool.true

        _ ->
            Bool.false

expect
    pill = { x: 50.0, y: 20.0, w: 150.0, h: 34.0 }
    bubble = { x: 180.0, y: 20.0, w: 78.0, h: 34.0 }
    when calcNeck pill 17.0 bubble is
        Ok _ ->
            Bool.true

        _ ->
            Bool.false

expect
    c0 = calcRimColor { r: 1.0, g: 0.0, b: 0.0, a: 1.0 } 0.0
    Num.is_approx_eq c0.r 1.0 {}
    and Num.is_approx_eq c0.g 1.0 {}
    and Num.is_approx_eq c0.b 1.0 {}
    and Num.is_approx_eq c0.a (32.0 / 255.0) {}

expect
    c1 = calcRimColor { r: 0.2, g: 0.4, b: 0.6, a: 1.0 } 1.0
    Num.is_approx_eq c1.r 0.2 {}
    and Num.is_approx_eq c1.g 0.4 {}
    and Num.is_approx_eq c1.b 0.6 {}
    and Num.is_approx_eq c1.a (140.0 / 255.0) {}

expect
    cHalf = calcRimColor { r: 0.0, g: 0.0, b: 0.0, a: 1.0 } 0.5
    Num.is_approx_eq cHalf.r 0.5 {}
    and Num.is_approx_eq cHalf.g 0.5 {}
    and Num.is_approx_eq cHalf.b 0.5 {}
    and Num.is_approx_eq cHalf.a ((32.0 + 140.0) / 2.0 / 255.0) {}
