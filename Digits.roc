module [DigitsState, DigitCell, init, setText, tick, shrinks]

extractDigits : Str -> List U8
extractDigits = |str|
    Str.to_utf8 str
    |> List.keep_if |b| b >= 48 and b <= 57

dropLeadingZeros : List U8 -> List U8
dropLeadingZeros = |bytes|
    when List.find_first_index bytes |b| b != 48 is
        Ok idx -> List.drop_first bytes idx
        Err _ -> []

compareDigitLists : List U8, List U8 -> [Shrinks, Grows, Same]
compareDigitLists = |a, b|
    lenA = List.len a
    lenB = List.len b
    if lenA > lenB then
        Shrinks
    else if lenA < lenB then
        Grows
    else
        mismatch =
            List.map2 a b |x, y| (x, y)
            |> List.find_first |(x, y)| x != y
        when mismatch is
            Ok (x, y) ->
                if x > y then Shrinks else Grows
            Err _ ->
                Same

shrinks : Str, Str -> Result [Shrinks, Grows, Same] [NoDigits]
shrinks = |was, next|
    digitsA = extractDigits was
    digitsB = extractDigits next
    if List.is_empty digitsA or List.is_empty digitsB then
        Err NoDigits
    else
        cleanA = dropLeadingZeros digitsA
        cleanB = dropLeadingZeros digitsB
        Ok (compareDigitLists cleanA cleanB)

DigitCell : {
    char : Str,
    character : Str,
    offsetY : F64,
    opacity : F64,
    blur : F64,
    blurRadius : F64,
    oldChar : Str,
    oldCharacter : Str,
    oldOffsetY : F64,
    oldOpacity : F64,
    oldBlur : F64,
    oldBlurRadius : F64,
    isAnimating : Bool,
    down : Bool,
    leaveElapsed : F64,
    enterElapsed : F64,
}

DigitsState : {
    text : Str,
    down : Bool,
    fontSize : F64,
    cells : List DigitCell,
    isAnimating : Bool,
}

toChars : Str -> List Str
toChars = |str|
    bytes = Str.to_utf8 str
    chunks = List.walk bytes [] |acc, b|
        isContinuation = b >= 128 and b < 192
        if isContinuation then
            when List.last acc is
                Ok currentChunk ->
                    newChunk = List.append currentChunk b
                    List.set acc (List.len acc - 1) newChunk

                Err _ ->
                    List.append acc [b]
        else
            List.append acc [b]

    List.map chunks |chunk|
        when Str.from_utf8 chunk is
            Ok s -> s
            Err _ -> ""

createStaticCell : Str, Bool -> DigitCell
createStaticCell = |ch, down| {
    char: ch,
    character: ch,
    offsetY: 0.0,
    opacity: 1.0,
    blur: 0.0,
    blurRadius: 0.0,
    oldChar: "",
    oldCharacter: "",
    oldOffsetY: 0.0,
    oldOpacity: 0.0,
    oldBlur: 0.0,
    oldBlurRadius: 0.0,
    isAnimating: Bool.false,
    down,
    leaveElapsed: 0.0,
    enterElapsed: 0.0,
}

init : Str, Bool -> DigitsState
init = |text, down| {
    text,
    down,
    fontSize: 24.0,
    cells: List.map (toChars text) |ch| createStaticCell ch down,
    isAnimating: Bool.false,
}

travelDistance : F64 -> F64
travelDistance = |fontSize|
    Num.round (fontSize * 0.5) |> Num.to_f64

blurDistance : F64 -> F64
blurDistance = |fontSize|
    Num.min (Num.max (fontSize * 0.4) 4.0) 12.0

emptyCell : Bool -> DigitCell
emptyCell = |down|
    createStaticCell "" down

setText : DigitsState, Str -> DigitsState
setText = |state, newText|
    if state.text == newText then
        state
    else
        newChars = toChars newText
        newLen = List.len newChars
        oldLen = List.len state.cells
        travel = travelDistance state.fontSize
        blur = blurDistance state.fontSize

        matchedOldCells =
            if oldLen > newLen then
                List.drop_first state.cells (oldLen - newLen)
            else if newLen > oldLen then
                padding = List.repeat (emptyCell state.down) (newLen - oldLen)
                List.concat padding state.cells
            else
                state.cells

        newCells = List.map2 matchedOldCells newChars |oldCell, newChar|
            if oldCell.char == newChar and !oldCell.isAnimating then
                oldCell
            else
                oldChar = oldCell.char
                hasOld = oldChar != ""
                initialOffsetY = if state.down then -travel else travel
                {
                    char: newChar,
                    character: newChar,
                    offsetY: initialOffsetY,
                    opacity: 0.0,
                    blur,
                    blurRadius: blur,
                    oldChar: if hasOld then oldChar else "",
                    oldCharacter: if hasOld then oldChar else "",
                    oldOffsetY: 0.0,
                    oldOpacity: if hasOld then 1.0 else 0.0,
                    oldBlur: 0.0,
                    oldBlurRadius: 0.0,
                    isAnimating: Bool.true,
                    down: state.down,
                    leaveElapsed: 0.0,
                    enterElapsed: 0.0,
                }

        animating = List.any newCells |c| c.isAnimating
        { state &
            text: newText,
            cells: newCells,
            isAnimating: animating,
        }

tickCell : DigitCell, F64, F64, F64 -> DigitCell
tickCell = |cell, dt, travel, blur|
    if !cell.isAnimating then
        cell
    else
        leaveElapsed = cell.leaveElapsed + dt
        enterElapsed = cell.enterElapsed + dt

        leaveDone = leaveElapsed >= 0.26 or cell.oldChar == ""
        (oldOffsetY, oldOpacity, oldBlurVal, oldCh) =
            if leaveDone then
                (0.0, 0.0, 0.0, "")
            else
                tTravel = Num.min 1.0 (leaveElapsed / 0.26)
                easeIn = tTravel * tTravel * tTravel
                dy = (if cell.down then travel else -travel) * easeIn

                tBlur = Num.min 1.0 (leaveElapsed / 0.22)
                bVal = blur * tBlur

                tFade = Num.min 1.0 (leaveElapsed / 0.20)
                alphaVal = Num.max 0.0 (1.0 - tFade)

                (dy, alphaVal, bVal, cell.oldChar)

        enterDone = enterElapsed >= 0.38
        (newOffsetY, newOpacity, newBlurVal) =
            if enterDone then
                (0.0, 1.0, 0.0)
            else
                tTravel = Num.min 1.0 (enterElapsed / 0.38)
                inv = 1.0 - tTravel
                easeOut = 1.0 - inv * inv * inv
                dy = (if cell.down then -travel else travel) * (1.0 - easeOut)

                tBlur = Num.min 1.0 (enterElapsed / 0.32)
                invB = 1.0 - tBlur
                easeOutB = 1.0 - invB * invB * invB
                bVal = blur * (1.0 - easeOutB)

                tFade = Num.min 1.0 (enterElapsed / 0.26)
                alphaVal = Num.min 1.0 tFade

                (dy, alphaVal, bVal)

        isStillAnimating = !(leaveDone and enterDone)
        { cell &
            offsetY: newOffsetY,
            opacity: newOpacity,
            blur: newBlurVal,
            blurRadius: newBlurVal,
            oldChar: oldCh,
            oldCharacter: oldCh,
            oldOffsetY,
            oldOpacity,
            oldBlur: oldBlurVal,
            oldBlurRadius: oldBlurVal,
            isAnimating: isStillAnimating,
            leaveElapsed,
            enterElapsed,
        }

tick : DigitsState, F64 -> DigitsState
tick = |state, dt|
    if !state.isAnimating then
        state
    else
        clampedDt = Num.max dt 0.0
        travel = travelDistance state.fontSize
        blur = blurDistance state.fontSize
        updatedCells = List.map state.cells |cell|
            tickCell cell clampedDt travel blur
        animating = List.any updatedCells |c| c.isAnimating
        { state &
            cells: updatedCells,
            isAnimating: animating,
        }

expect
    d0 = init "25:00" Bool.true
    d0.text == "25:00" and !d0.isAnimating and List.len d0.cells == 5

expect
    d0 = init "25:00" Bool.true
    d1 = setText d0 "24:59"
    c0 = List.get d1.cells 0 |> Result.with_default (createStaticCell "" Bool.true)
    c1 = List.get d1.cells 1 |> Result.with_default (createStaticCell "" Bool.true)
    c2 = List.get d1.cells 2 |> Result.with_default (createStaticCell "" Bool.true)
    c3 = List.get d1.cells 3 |> Result.with_default (createStaticCell "" Bool.true)
    c4 = List.get d1.cells 4 |> Result.with_default (createStaticCell "" Bool.true)
    d1.isAnimating and !c0.isAnimating and c1.isAnimating and !c2.isAnimating and c3.isAnimating and c4.isAnimating

expect
    d0 = init "25:00" Bool.true
    d1 = setText d0 "24:59"
    d2 = tick d1 0.40
    !d2.isAnimating

expect
    cu0 = init "10" Bool.false
    cu1 = setText cu0 "11"
    cu1.isAnimating
    and !cu1.down
    and (
        when List.get cu1.cells 1 is
            Ok cell -> cell.isAnimating and cell.offsetY > 0.0
            Err _ -> Bool.false
    )

expect
    d0 = init "24:59" Bool.true
    d1 = setText d0 "9"
    List.len d1.cells == 1 and d1.text == "9"

expect
    shrinks "1:05" "0:59" == Ok Shrinks

expect
    shrinks "45" "50" == Ok Grows

expect
    shrinks "10" "10" == Ok Same
