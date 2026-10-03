module [CoverState, init, show, tick]

CoverState : {
    current : Str,
    previous : Str,
    direction : I32,
    mode : [Idle, Grow, Slide, Leave],
    elapsed : F64,
    duration : F64,
    isAnimating : Bool,
    offset : F64,
    opacity : F64,
    scale : F64,
    incomingOffset : F64,
    incomingOpacity : F64,
    incomingScale : F64,
    outgoingOffset : F64,
    outgoingOpacity : F64,
    outgoingScale : F64,
}

init : CoverState
init = {
    current: "",
    previous: "",
    direction: 0,
    mode: Idle,
    elapsed: 0.0,
    duration: 0.46,
    isAnimating: Bool.false,
    offset: 0.0,
    opacity: 0.0,
    scale: 1.0,
    incomingOffset: 0.0,
    incomingOpacity: 0.0,
    incomingScale: 1.0,
    outgoingOffset: 0.0,
    outgoingOpacity: 0.0,
    outgoingScale: 1.0,
}

show : CoverState, Str, I32 -> CoverState
show = |state, art, direction|
    old = state.current
    if art == "" then
        if old == "" then
            { state &
                current: "",
                previous: "",
                mode: Idle,
                isAnimating: Bool.false,
            }
        else
            dir = if direction == 0 then 1 else direction
            computeFrame
                { state &
                    current: "",
                    previous: old,
                    direction: dir,
                    mode: Leave,
                    elapsed: 0.0,
                    isAnimating: Bool.true,
                }
    else if old == "" or direction == 0 then
        computeFrame
            { state &
                current: art,
                previous: "",
                direction: 0,
                mode: Grow,
                elapsed: 0.0,
                isAnimating: Bool.true,
            }
    else
        dir = if direction >= 0 then 1 else -1
        computeFrame
            { state &
                current: art,
                previous: old,
                direction: dir,
                mode: Slide,
                elapsed: 0.0,
                isAnimating: Bool.true,
            }

computeFrame : CoverState -> CoverState
computeFrame = |state|
    if !state.isAnimating then
        state
    else
        t = Num.min 1.0 (state.elapsed / state.duration)
        inv = 1.0 - t
        ease = 1.0 - inv * inv * inv * inv

        when state.mode is
            Grow ->
                s = 0.88 + 0.12 * ease
                alpha = Num.min 1.0 (state.elapsed / 0.30)
                { state &
                    offset: 0.0,
                    opacity: alpha,
                    scale: s,
                    incomingOffset: 0.0,
                    incomingOpacity: alpha,
                    incomingScale: s,
                    outgoingOffset: 0.0,
                    outgoingOpacity: 0.0,
                    outgoingScale: 1.0,
                }

            Slide ->
                dir = if state.direction >= 0 then 1.0 else -1.0
                outOff = (-dir) * ease
                inOff = dir * (1.0 - ease)
                { state &
                    offset: inOff,
                    opacity: 1.0,
                    scale: 1.0,
                    incomingOffset: inOff,
                    incomingOpacity: 1.0,
                    incomingScale: 1.0,
                    outgoingOffset: outOff,
                    outgoingOpacity: 1.0,
                    outgoingScale: 1.0,
                }

            Leave ->
                dir = if state.direction < 0 then -1.0 else 1.0
                outOff = (-dir) * ease
                outAlpha = Num.max 0.0 (1.0 - state.elapsed / 0.24)
                { state &
                    offset: 0.0,
                    opacity: 0.0,
                    scale: 1.0,
                    incomingOffset: 0.0,
                    incomingOpacity: 0.0,
                    incomingScale: 1.0,
                    outgoingOffset: outOff,
                    outgoingOpacity: outAlpha,
                    outgoingScale: 1.0,
                }

            Idle ->
                state

tick : CoverState, F64 -> CoverState
tick = |state, dt|
    if !state.isAnimating then
        state
    else
        clampedDt = Num.max dt 0.0
        newElapsed = state.elapsed + clampedDt
        if newElapsed >= state.duration then
            finalAlpha = if state.current == "" or state.mode == Leave then 0.0 else 1.0
            { state &
                previous: "",
                mode: Idle,
                elapsed: state.duration,
                isAnimating: Bool.false,
                offset: 0.0,
                opacity: finalAlpha,
                scale: 1.0,
                incomingOffset: 0.0,
                incomingOpacity: finalAlpha,
                incomingScale: 1.0,
                outgoingOffset: 0.0,
                outgoingOpacity: 0.0,
                outgoingScale: 1.0,
            }
        else
            computeFrame { state & elapsed: newElapsed }

expect
    c0 = init
    c0.current == "" and !c0.isAnimating and c0.mode == Idle

expect
    c0 = init
    c1 = show c0 "album1.jpg" 0
    c1.isAnimating and c1.mode == Grow and Num.is_approx_eq c1.scale 0.88 {} and Num.is_approx_eq c1.opacity 0.0 {}

expect
    c0 = init
    c1 = show c0 "album1.jpg" 0
    c2 = tick c1 0.50
    !c2.isAnimating and c2.mode == Idle and Num.is_approx_eq c2.scale 1.0 {} and Num.is_approx_eq c2.opacity 1.0 {}

expect
    c0 = init
    c1 = show c0 "album1.jpg" 0
    c2 = tick c1 0.50
    c3 = show c2 "album2.jpg" 1
    c3.isAnimating and c3.mode == Slide and c3.direction == 1 and c3.previous == "album1.jpg" and c3.current == "album2.jpg"

expect
    c0 = init
    c1 = show c0 "album1.jpg" 0
    c2 = tick c1 0.50
    c3 = show c2 "album0.jpg" -1
    c3.isAnimating and c3.mode == Slide and c3.direction == -1 and c3.previous == "album1.jpg" and c3.current == "album0.jpg"

expect
    c0 = init
    c1 = show c0 "album1.jpg" 0
    c2 = tick c1 0.50
    c3 = show c2 "" 1
    c3.isAnimating
    and c3.mode
    == Leave
    and (
        c4 = tick c3 0.50
        !c4.isAnimating and c4.current == ""
    )
