module [ToggleState, init, setState, tick, knobX, trackColor]

ToggleState : {
    on : Bool,
    progress : F64,
    fromProgress : F64,
    targetProgress : F64,
    elapsed : F64,
    duration : F64,
    isAnimating : Bool,
}

init : Bool -> ToggleState
init = |initialOn|
    p = if initialOn then 1.0 else 0.0
    {
        on: initialOn,
        progress: p,
        fromProgress: p,
        targetProgress: p,
        elapsed: 0.0,
        duration: 0.22,
        isAnimating: Bool.false,
    }

setState : ToggleState, Bool -> ToggleState
setState = |state, on|
    target = if on then 1.0 else 0.0
    if state.on == on and !state.isAnimating then
        state
    else
        { state &
            on,
            fromProgress: state.progress,
            targetProgress: target,
            elapsed: 0.0,
            isAnimating: Bool.true,
        }

tick : ToggleState, F64 -> ToggleState
tick = |state, dt|
    if !state.isAnimating then
        state
    else
        clampedDt = Num.max dt 0.0
        newElapsed = state.elapsed + clampedDt
        if newElapsed >= state.duration or state.duration <= 0.0 then
            { state &
                progress: state.targetProgress,
                fromProgress: state.targetProgress,
                elapsed: state.duration,
                isAnimating: Bool.false,
            }
        else
            t = newElapsed / state.duration
            inv = 1.0 - t
            ease = 1.0 - inv * inv * inv
            newProgress = state.fromProgress + (state.targetProgress - state.fromProgress) * ease
            { state &
                progress: newProgress,
                elapsed: newElapsed,
                isAnimating: Bool.true,
            }

knobX : ToggleState, F64, F64 -> F64
knobX = |state, width, height|
    share = Num.min (Num.max state.progress 0.0) 1.0
    radius = height / 2.0
    radius + (width - height) * share

trackColor : ToggleState -> (F64, F64, F64)
trackColor = |state|
    share = Num.min (Num.max state.progress 0.0) 1.0
    r = 0.22 + (0.19 - 0.22) * share
    g = 0.22 + (0.82 - 0.22) * share
    b = 0.24 + (0.35 - 0.24) * share
    (r, g, b)

expect
    s0 = init Bool.false
    !s0.on and Num.is_approx_eq s0.progress 0.0 {} and !s0.isAnimating

expect
    s0 = init Bool.true
    s0.on and Num.is_approx_eq s0.progress 1.0 {} and !s0.isAnimating

expect
    sOff = init Bool.false
    sOn = init Bool.true
    xOff = knobX sOff 36.0 20.0
    xOn = knobX sOn 36.0 20.0
    Num.is_approx_eq xOff 10.0 {} and Num.is_approx_eq xOn 26.0 {}

expect
    sOff = init Bool.false
    sOn = init Bool.true
    (rOff, gOff, bOff) = trackColor sOff
    (rOn, gOn, bOn) = trackColor sOn
    Num.is_approx_eq rOff 0.22 {}
    and Num.is_approx_eq gOff 0.22 {}
    and Num.is_approx_eq bOff 0.24 {}
    and Num.is_approx_eq rOn 0.19 {}
    and Num.is_approx_eq gOn 0.82 {}
    and Num.is_approx_eq bOn 0.35 {}

expect
    s0 = init Bool.false
    s1 = setState s0 Bool.true
    s1.isAnimating
    and (
        s2 = tick s1 0.11
        s2.isAnimating
        and s2.progress
        > 0.4
        and s2.progress
        < 0.9
        and (
            s3 = tick s2 0.15
            !s3.isAnimating and Num.is_approx_eq s3.progress 1.0 {}
        )
    )
