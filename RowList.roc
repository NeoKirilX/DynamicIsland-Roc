module [
    RowList,
    HighlightRect,
    init,
    setHover,
    setPressed,
    clearHover,
    tick,
    calcHighlight,
]

import Spring

HighlightRect : {
    x : F64,
    y : F64,
    w : F64,
    h : F64,
    opacity : F64,
}

RowList : {
    top : Spring.Spring,
    bottom : Spring.Spring,
    shown : Spring.Spring,
    squish : Spring.Spring,
    lit : Bool,
    pressed : Bool,
}

hoverOpacity : F64
hoverOpacity = 0.12

pressOpacity : F64
pressOpacity = 0.21

squishX : F64
squishX = 5.0

squishY : F64
squishY = 2.0

pop : F64
pop = 0.6

init : RowList
init = {
    top: Spring.init 0.0,
    bottom: Spring.init 0.0,
    shown: Spring.init 0.0,
    squish: Spring.init 0.0,
    lit: Bool.false,
    pressed: Bool.false,
}

setHover : RowList, F64, F64 -> RowList
setHover = |rowList, top, bottom|
    wasHidden = rowList.shown.value < 0.05
    (newTop, newBottom, newSquish) =
        if wasHidden then
            oldTop = rowList.top
            oldBottom = rowList.bottom
            oldSquish = rowList.squish
            sTop = { oldTop & value: top, target: top, velocity: 0.0 }
            sBottom = { oldBottom & value: bottom, target: bottom, velocity: 0.0 }
            targetSquish = if rowList.pressed then 1.0 else 0.0
            sSquish = { oldSquish & value: pop, target: targetSquish }
            (sTop, sBottom, sSquish)
        else if !(Num.is_approx_eq top rowList.top.target {}) then
            isMovingDown = top > rowList.top.target
            (topTuned, bottomTuned) =
                if isMovingDown then
                    (Spring.tune rowList.top 230.0 26.0, Spring.tune rowList.bottom 560.0 36.0)
                else
                    (Spring.tune rowList.top 560.0 36.0, Spring.tune rowList.bottom 230.0 26.0)
            (
                Spring.setTarget topTuned top,
                Spring.setTarget bottomTuned bottom,
                rowList.squish,
            )
        else
            (
                Spring.setTarget rowList.top top,
                Spring.setTarget rowList.bottom bottom,
                rowList.squish,
            )

    newShown =
        if !(rowList.lit) then
            rowList.shown
            |> Spring.tune 420.0 41.0
            |> Spring.setTarget 1.0
        else
            Spring.setTarget rowList.shown 1.0

    {
        top: newTop,
        bottom: newBottom,
        shown: newShown,
        squish: newSquish,
        lit: Bool.true,
        pressed: rowList.pressed,
    }

setPressed : RowList, Bool -> RowList
setPressed = |rowList, pressed|
    newSquish =
        if pressed != rowList.pressed then
            tuned =
                if pressed then
                    Spring.tune rowList.squish 700.0 44.0
                else
                    Spring.tune rowList.squish 380.0 16.0
            Spring.setTarget tuned (if pressed then 1.0 else 0.0)
        else
            rowList.squish

    { rowList &
        pressed,
        squish: newSquish,
    }

clearHover : RowList -> RowList
clearHover = |rowList|
    newShown =
        if rowList.lit then
            rowList.shown
            |> Spring.tune 90.0 19.0
            |> Spring.setTarget 0.0
        else
            Spring.setTarget rowList.shown 0.0

    newSquish =
        if rowList.pressed then
            rowList.squish
            |> Spring.tune 380.0 16.0
            |> Spring.setTarget 0.0
        else
            Spring.setTarget rowList.squish 0.0

    { rowList &
        lit: Bool.false,
        pressed: Bool.false,
        shown: newShown,
        squish: newSquish,
    }

tick : RowList, F64 -> RowList
tick = |rowList, dt|
    if dt <= 0.0 then
        rowList
    else
        advTop = Spring.advance rowList.top dt
        advBottom = Spring.advance rowList.bottom dt
        advShown = Spring.advance rowList.shown dt
        advSquish = Spring.advance rowList.squish dt
        { rowList &
            top: advTop.spring,
            bottom: advBottom.spring,
            shown: advShown.spring,
            squish: advSquish.spring,
        }

calcHighlight : RowList, F64 -> HighlightRect
calcHighlight = |rowList, width|
    sq = rowList.squish.value
    x = squishX * sq
    y = rowList.top.value + squishY * sq
    w = Num.max (width - x * 2.0) 0.0
    h = Num.max (rowList.bottom.value - rowList.top.value - (squishY * sq) * 2.0) 0.0
    shownClamped = Num.min (Num.max rowList.shown.value 0.0) 1.0
    squishClamped = Num.min (Num.max sq 0.0) 1.0
    opacity = shownClamped * (hoverOpacity + (pressOpacity - hoverOpacity) * squishClamped)
    { x, y, w, h, opacity }

expect
    rl = init
    !(rl.lit)
    and !(rl.pressed)
    and Num.is_approx_eq rl.top.value 0.0 {}
    and Num.is_approx_eq rl.bottom.value 0.0 {}
    and Num.is_approx_eq rl.shown.value 0.0 {}
    and Num.is_approx_eq rl.squish.value 0.0 {}

expect
    rl0 = init
    rl1 = setHover rl0 20.0 60.0
    rl1.lit
    and !(rl1.pressed)
    and Num.is_approx_eq rl1.top.value 20.0 {}
    and Num.is_approx_eq rl1.top.target 20.0 {}
    and Num.is_approx_eq rl1.top.velocity 0.0 {}
    and Num.is_approx_eq rl1.bottom.value 60.0 {}
    and Num.is_approx_eq rl1.bottom.target 60.0 {}
    and Num.is_approx_eq rl1.bottom.velocity 0.0 {}
    and Num.is_approx_eq rl1.squish.value 0.6 {}
    and Num.is_approx_eq rl1.shown.target 1.0 {}
    and Num.is_approx_eq rl1.shown.stiffness 420.0 {}
    and Num.is_approx_eq rl1.shown.damping 41.0 {}

expect
    rl0 = init |> setHover 10.0 40.0
    rl1 = tick rl0 0.1
    rl2 = setHover rl1 50.0 80.0
    Num.is_approx_eq rl2.top.target 50.0 {}
    and Num.is_approx_eq rl2.bottom.target 80.0 {}
    and Num.is_approx_eq rl2.top.stiffness 230.0 {}
    and Num.is_approx_eq rl2.top.damping 26.0 {}
    and Num.is_approx_eq rl2.bottom.stiffness 560.0 {}
    and Num.is_approx_eq rl2.bottom.damping 36.0 {}

expect
    rl0 = init |> setHover 50.0 80.0
    rl1 = tick rl0 0.1
    rl2 = setHover rl1 10.0 40.0
    Num.is_approx_eq rl2.top.target 10.0 {}
    and Num.is_approx_eq rl2.bottom.target 40.0 {}
    and Num.is_approx_eq rl2.top.stiffness 560.0 {}
    and Num.is_approx_eq rl2.top.damping 36.0 {}
    and Num.is_approx_eq rl2.bottom.stiffness 230.0 {}
    and Num.is_approx_eq rl2.bottom.damping 26.0 {}

expect
    rl0 = init |> setHover 10.0 40.0
    rl1 = tick rl0 0.1
    rl2 = setHover rl1 10.0 40.0
    Num.is_approx_eq rl2.top.target 10.0 {}
    and Num.is_approx_eq rl2.bottom.target 40.0 {}

expect
    rl0 = init |> setHover 10.0 40.0
    rl1 = setPressed rl0 Bool.true
    isPressedOk =
        rl1.pressed
        and Num.is_approx_eq rl1.squish.target 1.0 {}
        and Num.is_approx_eq rl1.squish.stiffness 700.0 {}
        and Num.is_approx_eq rl1.squish.damping 44.0 {}
    rl2 = setPressed rl1 Bool.false
    isReleasedOk =
        !(rl2.pressed)
        and Num.is_approx_eq rl2.squish.target 0.0 {}
        and Num.is_approx_eq rl2.squish.stiffness 380.0 {}
        and Num.is_approx_eq rl2.squish.damping 16.0 {}
    isPressedOk and isReleasedOk

expect
    rl0 = init |> setHover 10.0 40.0
    rl1 = clearHover rl0
    !(rl1.lit)
    and !(rl1.pressed)
    and Num.is_approx_eq rl1.shown.target 0.0 {}
    and Num.is_approx_eq rl1.shown.stiffness 90.0 {}
    and Num.is_approx_eq rl1.shown.damping 19.0 {}

expect
    rl0 = init |> setHover 0.0 50.0
    simulate = |state, count|
        if count == 0 then
            state
        else
            simulate (tick state (1.0 / 60.0)) (count - 1)
    rlSettled = simulate rl0 120
    Num.is_approx_eq rlSettled.top.value 0.0 {}
    and Num.is_approx_eq rlSettled.bottom.value 50.0 {}
    and Num.is_approx_eq rlSettled.shown.value 1.0 {}
    and Num.is_approx_eq rlSettled.squish.value 0.0 {}

expect
    rl0 = init |> setHover 10.0 40.0
    rl1 = tick rl0 0.0
    Num.is_approx_eq rl1.top.value rl0.top.value {}
    and Num.is_approx_eq rl1.bottom.value rl0.bottom.value {}

expect
    t0 = Spring.init 20.0
    b0 = Spring.init 60.0
    s0 = Spring.init 1.0
    sq0 = Spring.init 0.0
    rl = {
        top: { t0 & value: 20.0, target: 20.0 },
        bottom: { b0 & value: 60.0, target: 60.0 },
        shown: { s0 & value: 1.0, target: 1.0 },
        squish: { sq0 & value: 0.0, target: 0.0 },
        lit: Bool.true,
        pressed: Bool.false,
    }
    h = calcHighlight rl 200.0
    Num.is_approx_eq h.x 0.0 {}
    and Num.is_approx_eq h.y 20.0 {}
    and Num.is_approx_eq h.w 200.0 {}
    and Num.is_approx_eq h.h 40.0 {}
    and Num.is_approx_eq h.opacity 0.12 {}

expect
    t0 = Spring.init 10.0
    b0 = Spring.init 50.0
    s0 = Spring.init 1.0
    sq0 = Spring.init 1.0
    rl = {
        top: { t0 & value: 10.0, target: 10.0 },
        bottom: { b0 & value: 50.0, target: 50.0 },
        shown: { s0 & value: 1.0, target: 1.0 },
        squish: { sq0 & value: 1.0, target: 1.0 },
        lit: Bool.true,
        pressed: Bool.true,
    }
    h = calcHighlight rl 200.0
    Num.is_approx_eq h.x 5.0 {}
    and Num.is_approx_eq h.y 12.0 {}
    and Num.is_approx_eq h.w 190.0 {}
    and Num.is_approx_eq h.h 36.0 {}
    and Num.is_approx_eq h.opacity 0.21 {}

expect
    rl0 = init |> setHover 10.0 50.0
    h = calcHighlight rl0 200.0
    Num.is_approx_eq h.x 3.0 {}
    and Num.is_approx_eq h.y 11.2 {}
    and Num.is_approx_eq h.w 194.0 {}
    and Num.is_approx_eq h.h 37.6 {}
    and Num.is_approx_eq h.opacity 0.0 {}

expect
    t0 = Spring.init 10.0
    b0 = Spring.init 50.0
    s0 = Spring.init 1.0
    sq0 = Spring.init 0.0
    rl = {
        top: { t0 & value: 10.0, target: 10.0 },
        bottom: { b0 & value: 50.0, target: 50.0 },
        shown: { s0 & value: 1.0, target: 1.0 },
        squish: { sq0 & value: -0.1, target: 0.0 },
        lit: Bool.true,
        pressed: Bool.false,
    }
    h = calcHighlight rl 200.0
    Num.is_approx_eq h.x -0.5 {}
    and Num.is_approx_eq h.y 9.8 {}
    and Num.is_approx_eq h.w 201.0 {}
    and Num.is_approx_eq h.h 40.4 {}
    and Num.is_approx_eq h.opacity 0.12 {}
