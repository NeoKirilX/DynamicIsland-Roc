module [Timer, init, start, toggle, stop, addMinutes, tick, formatTime, share, isUrgent, shouldSplit]

Timer : {
    total : F64,
    left : F64,
    active : Bool,
    running : Bool,
}

init : Timer
init = {
    total: 0.0,
    left: 0.0,
    active: Bool.false,
    running: Bool.false,
}

start : Timer, F64 -> Timer
start = |timer, total|
    clampedTotal = Num.max total 0.0
    { timer &
        total: clampedTotal,
        left: clampedTotal,
        active: Bool.true,
        running: Bool.true,
    }

toggle : Timer -> Timer
toggle = |timer|
    if !timer.active then
        timer
    else
        { timer & running: !timer.running }

stop : Timer -> Timer
stop = |timer|
    { timer &
        left: 0.0,
        active: Bool.false,
        running: Bool.false,
    }

addMinutes : Timer, I64 -> Timer
addMinutes = |timer, minutes|
    delta = Num.to_f64 minutes * 60.0
    newLeft = Num.max (timer.left + delta) 0.0
    newTotal = Num.max (timer.total + delta) newLeft
    { timer &
        total: newTotal,
        left: newLeft,
    }

tick : Timer, F64 -> { timer : Timer, expired : Bool }
tick = |timer, dt|
    if !timer.active or !timer.running then
        { timer, expired: Bool.false }
    else
        clampedDt = Num.max dt 0.0
        newLeft = timer.left - clampedDt
        if newLeft <= 0.0 then
            {
                timer: { timer & left: 0.0, active: Bool.false, running: Bool.false },
                expired: Bool.true,
            }
        else
            {
                timer: { timer & left: newLeft },
                expired: Bool.false,
            }

pad2 : I64 -> Str
pad2 = |n|
    s = Num.to_str n
    if n < 10 then
        "0${s}"
    else
        s

formatTime : F64 -> Str
formatTime = |seconds|
    totalSecs = Num.round (Num.max seconds 0.0)
    m = totalSecs // 60
    s = totalSecs % 60
    "${pad2 m}:${pad2 s}"

share : Timer -> F64
share = |timer|
    if timer.total <= 0.0 then
        0.0
    else
        Num.min (Num.max (timer.left / timer.total) 0.0) 1.0

isUrgent : Timer -> Bool
isUrgent = |timer|
    timer.active and timer.left <= 10.0

shouldSplit : { timerActive : Bool, mediaPlaying : Bool } -> Bool
shouldSplit = |{ timerActive, mediaPlaying }|
    timerActive and mediaPlaying

expect
    Num.is_approx_eq init.total 0.0 {}
    and Num.is_approx_eq init.left 0.0 {}
    and !init.active
    and !init.running
    and Num.is_approx_eq (share init) 0.0 {}
    and !(isUrgent init)

expect
    t = start init 300.0
    Num.is_approx_eq t.total 300.0 {}
    and Num.is_approx_eq t.left 300.0 {}
    and t.active
    and t.running
    and Num.is_approx_eq (share t) 1.0 {}
    and !(isUrgent t)

expect
    t0 = start init 60.0
    tPaused = toggle t0
    tPaused.active
    and !tPaused.running
    and (
        tResumed = toggle tPaused
        tResumed.active and tResumed.running
    )

expect
    t = toggle init
    !t.active and !t.running

expect
    t0 = start init 120.0
    tStopped = stop t0
    !tStopped.active
    and !tStopped.running
    and Num.is_approx_eq tStopped.left 0.0 {}
    and Num.is_approx_eq (share tStopped) 0.0 {}

expect
    t0 = start init 120.0
    t1 = addMinutes t0 2
    Num.is_approx_eq t1.total 240.0 {}
    and Num.is_approx_eq t1.left 240.0 {}
    and (
        t2 = addMinutes t1 -3
        Num.is_approx_eq t2.left 60.0 {}
        and Num.is_approx_eq t2.total 60.0 {}
    )

expect
    t0 = start init 100.0
    step1 = tick t0 25.0
    !step1.expired
    and Num.is_approx_eq step1.timer.left 75.0 {}
    and Num.is_approx_eq (share step1.timer) 0.75 {}
    and step1.timer.running

expect
    t0 = toggle (start init 100.0)
    step = tick t0 25.0
    !step.expired
    and Num.is_approx_eq step.timer.left 100.0 {}
    and !step.timer.running

expect
    t0 = start init 5.0
    step1 = tick t0 3.0
    !step1.expired
    and Num.is_approx_eq step1.timer.left 2.0 {}
    and isUrgent step1.timer
    and (
        step2 = tick step1.timer 2.0
        step2.expired
        and Num.is_approx_eq step2.timer.left 0.0 {}
        and !step2.timer.active
        and !step2.timer.running
        and !(isUrgent step2.timer)
        and (
            step3 = tick step2.timer 1.0
            !step3.expired
        )
    )

expect formatTime 125.0 == "02:05"
expect formatTime 0.0 == "00:00"
expect formatTime -5.0 == "00:00"
expect formatTime 9.0 == "00:09"
expect formatTime 59.0 == "00:59"
expect formatTime 60.0 == "01:00"
expect formatTime 1500.0 == "25:00"
expect formatTime 4500.0 == "75:00"

expect
    Num.is_approx_eq (share { total: 100.0, left: 50.0, active: Bool.true, running: Bool.true }) 0.5 {}
    and Num.is_approx_eq (share { total: 0.0, left: 0.0, active: Bool.false, running: Bool.false }) 0.0 {}
    and Num.is_approx_eq (share { total: 100.0, left: 150.0, active: Bool.true, running: Bool.true }) 1.0 {}
    and Num.is_approx_eq (share { total: 100.0, left: -10.0, active: Bool.true, running: Bool.true }) 0.0 {}

expect
    tActive15 = { total: 60.0, left: 15.0, active: Bool.true, running: Bool.true }
    tActive10 = { total: 60.0, left: 10.0, active: Bool.true, running: Bool.true }
    tActive5 = { total: 60.0, left: 5.0, active: Bool.true, running: Bool.true }
    tInactive5 = { total: 60.0, left: 5.0, active: Bool.false, running: Bool.false }
    !(isUrgent tActive15)
    and isUrgent tActive10
    and isUrgent tActive5
    and !(isUrgent tInactive5)

expect shouldSplit { timerActive: Bool.true, mediaPlaying: Bool.true } == Bool.true
expect shouldSplit { timerActive: Bool.true, mediaPlaying: Bool.false } == Bool.false
expect shouldSplit { timerActive: Bool.false, mediaPlaying: Bool.true } == Bool.false
expect shouldSplit { timerActive: Bool.false, mediaPlaying: Bool.false } == Bool.false
