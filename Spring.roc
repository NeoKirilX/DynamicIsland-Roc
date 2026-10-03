module [Spring, init, tune, setTarget, advance, isAtRest]

Spring : {
    value : F64,
    velocity : F64,
    target : F64,
    stiffness : F64,
    damping : F64,
}

maxStep : F64
maxStep = 1.0 / 240.0

init : F64 -> Spring
init = |value| {
    value,
    velocity: 0.0,
    target: value,
    stiffness: 300.0,
    damping: 24.0,
}

tune : Spring, F64, F64 -> Spring
tune = |spring, stiffness, damping|
    { spring &
        stiffness,
        damping,
    }

setTarget : Spring, F64 -> Spring
setTarget = |spring, target|
    { spring &
        target,
    }

step : Spring, F64 -> Spring
step = |spring, dt|
    if dt <= 0.0 then
        spring
    else
        h = Num.min maxStep dt
        accel = (-spring.stiffness) * (spring.value - spring.target) - spring.damping * spring.velocity
        velocity = spring.velocity + accel * h
        value = spring.value + velocity * h
        { spring & value, velocity }

isAtRest : Spring -> Bool
isAtRest = |spring|
    Num.abs (spring.value - spring.target) < 0.005 and Num.abs spring.velocity < 0.05

advance : Spring, F64 -> { spring : Spring, moving : Bool }
advance = |spring, dt|
    stepped = advanceHelp spring dt
    if isAtRest stepped then
        {
            spring: { stepped & value: stepped.target, velocity: 0.0 },
            moving: Bool.false,
        }
    else
        {
            spring: stepped,
            moving: Bool.true,
        }

advanceHelp : Spring, F64 -> Spring
advanceHelp = |spring, dt|
    if dt <= 0.0 then
        spring
    else
        h = Num.min maxStep dt
        nextSpring = step spring h
        advanceHelp nextSpring (dt - h)

expect
    s = init 42.0
    Num.abs (s.value - 42.0)
    < 0.0001
    and Num.abs (s.target - 42.0)
    < 0.0001
    and Num.abs s.velocity
    < 0.0001
    and Num.abs (s.stiffness - 300.0)
    < 0.0001
    and Num.abs (s.damping - 24.0)
    < 0.0001
    and isAtRest s

expect
    s = tune (init 0.0) 500.0 30.0
    Num.abs (s.stiffness - 500.0)
    < 0.0001
    and Num.abs (s.damping - 30.0)
    < 0.0001
    and Num.abs s.value
    < 0.0001

expect
    s = setTarget (init 10.0) 20.0
    Num.abs (s.value - 10.0)
    < 0.0001
    and Num.abs (s.target - 20.0)
    < 0.0001
    and !(isAtRest s)

expect
    s0 = setTarget (init 0.0) 100.0
    s1 = step s0 (1.0 / 240.0)
    Num.abs (s1.velocity - 125.0)
    < 0.0001
    and Num.abs (s1.value - (25.0 / 48.0))
    < 0.0001

expect
    s0 = setTarget (init 0.0) 100.0
    s1 = step s0 0.0
    Num.abs (s1.velocity - s0.velocity)
    < 0.0001
    and Num.abs (s1.value - s0.value)
    < 0.0001

expect
    s0 = setTarget (init 0.0) 100.0
    res = advance s0 (1.0 / 60.0)
    res.moving
    == Bool.true
    and Num.abs (res.spring.value - 4.675599)
    < 0.001
    and Num.abs (res.spring.velocity - 424.015404)
    < 0.001

expect
    simulateToRest = |spring, count|
        if count == 0 then
            { spring, moving: Bool.true }
        else
            res = advance spring (1.0 / 60.0)
            if !(res.moving) then
                res
            else
                simulateToRest res.spring (count - 1)

    s0 = setTarget (init 0.0) 100.0
    finalRes = simulateToRest s0 100
    finalRes.moving
    == Bool.false
    and Num.abs (finalRes.spring.value - 100.0)
    < 0.0001
    and Num.abs finalRes.spring.velocity
    < 0.0001
    and isAtRest finalRes.spring

expect
    atRest = { value: 100.004, velocity: 0.049, target: 100.0, stiffness: 300.0, damping: 24.0 }
    movingPos = { value: 100.006, velocity: 0.01, target: 100.0, stiffness: 300.0, damping: 24.0 }
    movingVel = { value: 100.001, velocity: 0.06, target: 100.0, stiffness: 300.0, damping: 24.0 }
    isAtRest atRest and !(isAtRest movingPos) and !(isAtRest movingVel)
