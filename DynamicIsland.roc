module [AppState, initApp, tickApp, resizeIsland]

import Spring
import Goo
import Timer
import Views
import Settings

AppState : {
    w : Spring.Spring,
    h : Spring.Spring,
    r : Spring.Spring,
    split : Spring.Spring,
    bubbleScale : Spring.Spring,
    push : Spring.Spring,
    size : Spring.Spring,
    gap : Spring.Spring,
    view : Views.View,
    panel : Views.Panel,
    timer : Timer.Timer,
    settings : Settings.Settings,
}

initApp : Settings.Settings -> AppState
initApp = |settings|
    initialDims = Views.dimsForView Idle settings.lyrics
    scaleVal = Num.to_f64 settings.scale / 100.0
    gapVal = Num.to_f64 settings.gap

    springW = Spring.init initialDims.w |> Spring.tune 320.0 20.0
    springH = Spring.init initialDims.h |> Spring.tune 320.0 26.0
    springR = Spring.init initialDims.r |> Spring.tune 300.0 30.0
    springSplit = Spring.init 0.0 |> Spring.tune 140.0 17.0
    springBubbleScale = Spring.init 1.0 |> Spring.tune 320.0 20.0
    springPush = Spring.init 0.0 |> Spring.tune 420.0 18.0
    springSize = Spring.init scaleVal |> Spring.tune 240.0 26.0
    springGap = Spring.init gapVal |> Spring.tune 240.0 26.0

    {
        w: springW,
        h: springH,
        r: springR,
        split: springSplit,
        bubbleScale: springBubbleScale,
        push: springPush,
        size: springSize,
        gap: springGap,
        view: Idle,
        panel: None,
        timer: Timer.init,
        settings,
    }

resizeIsland : AppState, Views.View -> AppState
resizeIsland = |state, nextView|
    dims = Views.dimsForView nextView state.settings.lyrics
    newW = Spring.setTarget state.w dims.w
    newH = Spring.setTarget state.h dims.h
    newR = Spring.setTarget state.r dims.r

    shouldSplit = state.timer.active and Views.isCompact nextView and nextView != Timer
    splitTarget = if shouldSplit then 1.0 else 0.0
    newSplit = Spring.setTarget state.split splitTarget

    newPanel = Views.viewToPanel nextView

    { state &
        w: newW,
        h: newH,
        r: newR,
        split: newSplit,
        view: nextView,
        panel: newPanel,
    }

tickApp : AppState, F64 -> AppState
tickApp = |state, dt|
    advW = Spring.advance state.w dt
    advH = Spring.advance state.h dt
    advR = Spring.advance state.r dt
    advSplit = Spring.advance state.split dt
    advBubbleScale = Spring.advance state.bubbleScale dt
    advPush = Spring.advance state.push dt
    advSize = Spring.advance state.size dt
    advGap = Spring.advance state.gap dt

    timerResult = Timer.tick state.timer dt
    updatedTimer = timerResult.timer

    updatedSplit =
        if timerResult.expired then
            Spring.setTarget advSplit.spring 0.0
        else
            advSplit.spring

    {
        w: advW.spring,
        h: advH.spring,
        r: advR.spring,
        split: updatedSplit,
        bubbleScale: advBubbleScale.spring,
        push: advPush.spring,
        size: advSize.spring,
        gap: advGap.spring,
        view: state.view,
        panel: state.panel,
        timer: updatedTimer,
        settings: state.settings,
    }

expect
    app = initApp Settings.defaultSettings
    isIdle = when app.view is
        Idle -> Bool.true
        _ -> Bool.false
    isNone = when app.panel is
        None -> Bool.true
        _ -> Bool.false

    Num.is_approx_eq app.w.value 118.0 {}
    and Num.is_approx_eq app.h.value 34.0 {}
    and Num.is_approx_eq app.r.value 17.0 {}
    and Num.is_approx_eq app.split.value 0.0 {}
    and Num.is_approx_eq app.bubbleScale.value 1.0 {}
    and Num.is_approx_eq app.push.value 0.0 {}
    and Num.is_approx_eq app.size.value 1.0 {}
    and Num.is_approx_eq app.gap.value 8.0 {}
    and isIdle
    and isNone
    and !(app.timer.active)

expect
    app0 = initApp Settings.defaultSettings
    app1 = resizeIsland app0 Media
    isMedia = when app1.view is
        Media -> Bool.true
        _ -> Bool.false

    isMedia
    and Num.is_approx_eq app1.w.target 210.0 {}
    and Num.is_approx_eq app1.h.target 34.0 {}
    and Num.is_approx_eq app1.r.target 17.0 {}

expect
    app0 = initApp Settings.defaultSettings
    app1 = resizeIsland app0 MediaBig
    isMediaBig = when app1.view is
        MediaBig -> Bool.true
        _ -> Bool.false
    isPlayer = when app1.panel is
        Player -> Bool.true
        _ -> Bool.false

    isMediaBig
    and isPlayer
    and Num.is_approx_eq app1.w.target 380.0 {}
    and Num.is_approx_eq app1.h.target 250.0 {}
    and Num.is_approx_eq app1.r.target 40.0 {}

expect
    app0 = initApp Settings.defaultSettings
    activeTimer = Timer.start app0.timer 60.0
    appWithTimer = { app0 & timer: activeTimer }
    app1 = resizeIsland appWithTimer Media
    Num.is_approx_eq app1.split.target 1.0 {}

expect
    app0 = initApp Settings.defaultSettings
    app1 = resizeIsland app0 MediaBig
    app2 = tickApp app1 (1.0 / 60.0)
    app2.w.value
    > 118.0
    and app2.w.value
    < 380.0
    and app2.h.value
    > 34.0
    and app2.h.value
    < 176.0

expect
    app0 = initApp Settings.defaultSettings
    activeTimer = Timer.start app0.timer 30.0
    appWithTimer = { app0 & timer: activeTimer }
    app1 = tickApp appWithTimer 1.5
    Num.is_approx_eq app1.timer.left 28.5 {}

expect
    pill = { x: 50.0, y: 20.0, w: 150.0, h: 34.0 }
    bubble = { x: 205.0, y: 20.0, w: Views.bubbleWidth, h: Views.bubbleHeight }
    when Goo.calcNeck pill 17.0 bubble is
        Ok neck ->
            Num.is_approx_eq neck.p1.x 198.978072556 {}

        Err _ ->
            Bool.false
