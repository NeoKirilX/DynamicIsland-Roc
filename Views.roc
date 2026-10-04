module [
    View,
    Panel,
    Dims,
    dimsForView,
    resolveView,
    allViews,
    isCompact,
    isExpanded,
    viewToPanel,
    panelToView,
    bubbleWidth,
    bubbleHeight,
    bubbleGap,
]

View : [
    Idle,
    Media,
    Timer,
    Volume,
    Charge,
    Focus,
    Toast,
    Notice,
    MediaBig,
    IdleBig,
    TimerBig,
    TimerSet,
    Menu,
    Settings,
    Look,
    Shelf,
]

Panel : [
    None,
    Player,
    Timer,
    TimerSet,
    Menu,
    Settings,
    Look,
    Shelf,
]

Dims : {
    w : F64,
    h : F64,
    r : F64,
}

allViews : List View
allViews = [
    Idle,
    Media,
    Timer,
    Volume,
    Charge,
    Focus,
    Toast,
    Notice,
    MediaBig,
    IdleBig,
    TimerBig,
    TimerSet,
    Menu,
    Settings,
    Look,
    Shelf,
]

bubbleWidth : F64
bubbleWidth = 78.0

bubbleHeight : F64
bubbleHeight = 34.0

bubbleGap : F64
bubbleGap = 7.0

isCompact : View -> Bool
isCompact = |view|
    when view is
        Idle | Media | Timer | Volume | Charge | Focus -> Bool.true
        _ -> Bool.false

isExpanded : View -> Bool
isExpanded = |view|
    !(isCompact view)

viewToPanel : View -> Panel
viewToPanel = |view|
    when view is
        MediaBig -> Player
        TimerBig -> Timer
        TimerSet -> TimerSet
        Menu -> Menu
        Settings -> Settings
        Look -> Look
        Shelf -> Shelf
        _ -> None

panelToView : Panel -> View
panelToView = |panel|
    when panel is
        Player -> MediaBig
        Timer -> TimerBig
        TimerSet -> TimerSet
        Menu -> Menu
        Settings -> Settings
        Look -> Look
        Shelf -> Shelf
        None -> Idle

dimsForView : View, Bool -> Dims
dimsForView = |view, hasLyrics|
    when view is
        Idle -> { w: 118.0, h: 34.0, r: 17.0 }
        Media -> { w: 210.0, h: 34.0, r: 17.0 }
        Timer -> { w: 132.0, h: 34.0, r: 17.0 }
        Volume -> { w: 250.0, h: 34.0, r: 17.0 }
        Charge -> { w: 230.0, h: 34.0, r: 17.0 }
        Focus -> { w: 236.0, h: 34.0, r: 17.0 }
        Toast -> { w: 340.0, h: 68.0, r: 30.0 }
        Notice -> { w: 320.0, h: 64.0, r: 29.0 }
        MediaBig ->
            h = if hasLyrics then 250.0 else 176.0
            { w: 380.0, h, r: 40.0 }

        IdleBig -> { w: 320.0, h: 124.0, r: 38.0 }
        TimerBig -> { w: 330.0, h: 92.0, r: 40.0 }
        TimerSet -> { w: 300.0, h: 190.0, r: 38.0 }
        Menu -> { w: 300.0, h: 208.0, r: 34.0 }
        Settings -> { w: 320.0, h: 414.0, r: 34.0 }
        Look -> { w: 320.0, h: 460.0, r: 34.0 }
        Shelf -> { w: 380.0, h: 136.0, r: 34.0 }

resolveView : {
    panel : Panel,
    hasMedia : Bool,
    timerActive : Bool,
    isCharging : Bool,
    transientView : [None, Some View],
} -> View
resolveView = |{ panel, hasMedia, timerActive, isCharging, transientView }|
    when panel is
        Menu -> Menu
        Settings -> Settings
        Look -> Look
        Shelf -> Shelf
        TimerSet -> TimerSet
        Timer if timerActive -> TimerBig
        Timer | Player if hasMedia -> MediaBig
        Timer | Player -> IdleBig
        None ->
            target =
                when transientView is
                    Some v -> v
                    None if isCharging -> Charge
                    None if hasMedia -> Media
                    None if timerActive -> Timer
                    None -> Idle

            when target is
                Toast if !hasMedia -> Idle
                _ -> target

expect
    List.len allViews == 16

expect
    dFocus = dimsForView Focus Bool.false
    dShelf = dimsForView Shelf Bool.false
    Num.is_approx_eq dFocus.w 236.0 {}
    and Num.is_approx_eq dFocus.h 34.0 {}
    and Num.is_approx_eq dShelf.w 380.0 {}
    and Num.is_approx_eq dShelf.h 136.0 {}

expect
    dIdle = dimsForView Idle Bool.false
    dMedia = dimsForView Media Bool.false
    dTimer = dimsForView Timer Bool.false
    dVol = dimsForView Volume Bool.false
    dCharge = dimsForView Charge Bool.false
    Num.is_approx_eq dIdle.w 118.0 {}
    and Num.is_approx_eq dIdle.h 34.0 {}
    and Num.is_approx_eq dIdle.r 17.0 {}
    and Num.is_approx_eq dMedia.w 210.0 {}
    and Num.is_approx_eq dMedia.h 34.0 {}
    and Num.is_approx_eq dMedia.r 17.0 {}
    and Num.is_approx_eq dTimer.w 132.0 {}
    and Num.is_approx_eq dTimer.h 34.0 {}
    and Num.is_approx_eq dTimer.r 17.0 {}
    and Num.is_approx_eq dVol.w 250.0 {}
    and Num.is_approx_eq dVol.h 34.0 {}
    and Num.is_approx_eq dVol.r 17.0 {}
    and Num.is_approx_eq dCharge.w 230.0 {}
    and Num.is_approx_eq dCharge.h 34.0 {}
    and Num.is_approx_eq dCharge.r 17.0 {}

expect
    dNoLyrics = dimsForView MediaBig Bool.false
    dLyrics = dimsForView MediaBig Bool.true
    Num.is_approx_eq dNoLyrics.w 380.0 {}
    and Num.is_approx_eq dNoLyrics.h 176.0 {}
    and Num.is_approx_eq dNoLyrics.r 40.0 {}
    and Num.is_approx_eq dLyrics.w 380.0 {}
    and Num.is_approx_eq dLyrics.h 250.0 {}
    and Num.is_approx_eq dLyrics.r 40.0 {}

expect
    dToast = dimsForView Toast Bool.false
    dNotice = dimsForView Notice Bool.false
    dIdleBig = dimsForView IdleBig Bool.false
    dTimerBig = dimsForView TimerBig Bool.false
    dTimerSet = dimsForView TimerSet Bool.false
    dMenu = dimsForView Menu Bool.false
    dSettings = dimsForView Settings Bool.false
    dLook = dimsForView Look Bool.false
    Num.is_approx_eq dToast.w 340.0 {}
    and Num.is_approx_eq dToast.h 68.0 {}
    and Num.is_approx_eq dToast.r 30.0 {}
    and Num.is_approx_eq dNotice.w 320.0 {}
    and Num.is_approx_eq dNotice.h 64.0 {}
    and Num.is_approx_eq dNotice.r 29.0 {}
    and Num.is_approx_eq dIdleBig.w 320.0 {}
    and Num.is_approx_eq dIdleBig.h 124.0 {}
    and Num.is_approx_eq dIdleBig.r 38.0 {}
    and Num.is_approx_eq dTimerBig.w 330.0 {}
    and Num.is_approx_eq dTimerBig.h 92.0 {}
    and Num.is_approx_eq dTimerBig.r 40.0 {}
    and Num.is_approx_eq dTimerSet.w 300.0 {}
    and Num.is_approx_eq dTimerSet.h 190.0 {}
    and Num.is_approx_eq dTimerSet.r 38.0 {}
    and Num.is_approx_eq dMenu.w 300.0 {}
    and Num.is_approx_eq dMenu.h 208.0 {}
    and Num.is_approx_eq dMenu.r 34.0 {}
    and Num.is_approx_eq dSettings.w 320.0 {}
    and Num.is_approx_eq dSettings.h 414.0 {}
    and Num.is_approx_eq dSettings.r 34.0 {}
    and Num.is_approx_eq dLook.w 320.0 {}
    and Num.is_approx_eq dLook.h 460.0 {}
    and Num.is_approx_eq dLook.r 34.0 {}

expect
    vMenu = resolveView { panel: Menu, hasMedia: Bool.false, timerActive: Bool.false, isCharging: Bool.false, transientView: None }
    vSettings = resolveView { panel: Settings, hasMedia: Bool.false, timerActive: Bool.false, isCharging: Bool.false, transientView: None }
    vLook = resolveView { panel: Look, hasMedia: Bool.false, timerActive: Bool.false, isCharging: Bool.false, transientView: None }
    vTimerSet = resolveView { panel: TimerSet, hasMedia: Bool.false, timerActive: Bool.false, isCharging: Bool.false, transientView: None }
    vTimerBig = resolveView { panel: Timer, hasMedia: Bool.false, timerActive: Bool.true, isCharging: Bool.false, transientView: None }
    vPlayerMedia = resolveView { panel: Player, hasMedia: Bool.true, timerActive: Bool.false, isCharging: Bool.false, transientView: None }
    vPlayerIdle = resolveView { panel: Player, hasMedia: Bool.false, timerActive: Bool.false, isCharging: Bool.false, transientView: None }
    vTimerMedia = resolveView { panel: Timer, hasMedia: Bool.true, timerActive: Bool.false, isCharging: Bool.false, transientView: None }
    vTimerIdle = resolveView { panel: Timer, hasMedia: Bool.false, timerActive: Bool.false, isCharging: Bool.false, transientView: None }
    vMenu == Menu
    and vSettings == Settings
    and vLook == Look
    and vTimerSet == TimerSet
    and vTimerBig == TimerBig
    and vPlayerMedia == MediaBig
    and vPlayerIdle == IdleBig
    and vTimerMedia == MediaBig
    and vTimerIdle == IdleBig

expect
    vIdle = resolveView { panel: None, hasMedia: Bool.false, timerActive: Bool.false, isCharging: Bool.false, transientView: None }
    vMedia = resolveView { panel: None, hasMedia: Bool.true, timerActive: Bool.false, isCharging: Bool.false, transientView: None }
    vTimer = resolveView { panel: None, hasMedia: Bool.false, timerActive: Bool.true, isCharging: Bool.false, transientView: None }
    vMediaOverTimer = resolveView { panel: None, hasMedia: Bool.true, timerActive: Bool.true, isCharging: Bool.false, transientView: None }
    vCharge = resolveView { panel: None, hasMedia: Bool.false, timerActive: Bool.false, isCharging: Bool.true, transientView: None }
    vIdle == Idle
    and vMedia == Media
    and vTimer == Timer
    and vMediaOverTimer == Media
    and vCharge == Charge

expect
    vVol = resolveView { panel: None, hasMedia: Bool.true, timerActive: Bool.true, isCharging: Bool.true, transientView: Some Volume }
    vNotice = resolveView { panel: None, hasMedia: Bool.false, timerActive: Bool.false, isCharging: Bool.false, transientView: Some Notice }
    vToastWithMedia = resolveView { panel: None, hasMedia: Bool.true, timerActive: Bool.false, isCharging: Bool.false, transientView: Some Toast }
    vToastNoMedia = resolveView { panel: None, hasMedia: Bool.false, timerActive: Bool.false, isCharging: Bool.false, transientView: Some Toast }
    vVol == Volume
    and vNotice == Notice
    and vToastWithMedia == Toast
    and vToastNoMedia == Idle
