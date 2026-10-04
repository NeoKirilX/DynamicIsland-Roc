module [Glyph, PathCmd, IconArt, getIconArt, allGlyphs]

Glyph : [
    Mute,
    Quiet,
    Mid,
    Loud,
    Headphones,
    Speaker,
    Vpn,
    Offline,
    Wifi,
    Wired,
    Bell,
    Note,
    Battery,
    Minus,
    Plus,
    Chevron,
    Back,
    Clock,
    Gear,
    Lines,
    Sparkle,
    Rim,
    Expand,
    Windows,
    Linux,
    Power,
    Look,
    Size,
    Gap,
    Drop,
    Moon,
    Tray,
    Cross,
]

PathCmd : [
    M F64 F64,
    L F64 F64,
    H F64,
    V F64,
    C F64 F64 F64 F64 F64 F64,
    A F64 F64 F64 Bool Bool F64 F64,
    Z,
]

IconArt : {
    solid : List PathCmd,
    lines : List PathCmd,
    lineWidth : F64,
    cut : List PathCmd,
    cutWidth : F64,
    over : List PathCmd,
}

allGlyphs : List Glyph
allGlyphs = [
    Mute,
    Quiet,
    Mid,
    Loud,
    Headphones,
    Speaker,
    Vpn,
    Offline,
    Wifi,
    Wired,
    Bell,
    Note,
    Battery,
    Minus,
    Plus,
    Chevron,
    Back,
    Clock,
    Gear,
    Lines,
    Sparkle,
    Rim,
    Expand,
    Windows,
    Linux,
    Power,
    Look,
    Size,
    Gap,
    Drop,
    Moon,
    Tray,
    Cross,
]

getIconArt : Glyph -> IconArt
getIconArt = |glyph|
    when glyph is
        Mute ->
            {
                solid: [
                    M 2.5 9.6,
                    H 6.0,
                    L 10.6 5.6,
                    V 18.4,
                    L 6.0 14.4,
                    H 2.5,
                    Z,
                ],
                lines: [
                    M 14.8 9.2,
                    L 20.4 14.8,
                    M 20.4 9.2,
                    L 14.8 14.8,
                ],
                lineWidth: 2.0,
                cut: [],
                cutWidth: 2.0,
                over: [],
            }

        Quiet ->
            {
                solid: [
                    M 2.5 9.6,
                    H 6.0,
                    L 10.6 5.6,
                    V 18.4,
                    L 6.0 14.4,
                    H 2.5,
                    Z,
                ],
                lines: [
                    M 13.3 9.3,
                    A 3.8 3.8 0.0 Bool.false Bool.true 13.3 14.7,
                ],
                lineWidth: 2.0,
                cut: [],
                cutWidth: 2.0,
                over: [],
            }

        Mid ->
            {
                solid: [
                    M 2.5 9.6,
                    H 6.0,
                    L 10.6 5.6,
                    V 18.4,
                    L 6.0 14.4,
                    H 2.5,
                    Z,
                ],
                lines: [
                    M 13.3 9.3,
                    A 3.8 3.8 0.0 Bool.false Bool.true 13.3 14.7,
                    M 15.7 6.9,
                    A 7.2 7.2 0.0 Bool.false Bool.true 15.7 17.1,
                ],
                lineWidth: 2.0,
                cut: [],
                cutWidth: 2.0,
                over: [],
            }

        Loud ->
            {
                solid: [
                    M 2.5 9.6,
                    H 6.0,
                    L 10.6 5.6,
                    V 18.4,
                    L 6.0 14.4,
                    H 2.5,
                    Z,
                ],
                lines: [
                    M 13.3 9.3,
                    A 3.8 3.8 0.0 Bool.false Bool.true 13.3 14.7,
                    M 15.7 6.9,
                    A 7.2 7.2 0.0 Bool.false Bool.true 15.7 17.1,
                    M 18.1 4.5,
                    A 10.6 10.6 0.0 Bool.false Bool.true 18.1 19.5,
                ],
                lineWidth: 2.0,
                cut: [],
                cutWidth: 2.0,
                over: [],
            }

        Headphones ->
            {
                solid: [
                    M 3.6 14.0,
                    H 7.0,
                    V 19.6,
                    H 3.6,
                    Z,
                    M 17.0 14.0,
                    H 20.4,
                    V 19.6,
                    H 17.0,
                    Z,
                ],
                lines: [
                    M 4.6 14.0,
                    V 12.2,
                    A 7.4 7.4 0.0 Bool.false Bool.true 19.4 12.2,
                    V 14.0,
                ],
                lineWidth: 2.0,
                cut: [],
                cutWidth: 2.0,
                over: [],
            }

        Speaker ->
            {
                solid: [
                    M 7.2 3.4,
                    H 16.8,
                    V 20.6,
                    H 7.2,
                    Z,
                    M 12.0 5.4,
                    A 2.1 2.1 0.0 Bool.true Bool.false 12.0 9.6,
                    A 2.1 2.1 0.0 Bool.true Bool.false 12.0 5.4,
                    Z,
                    M 12.0 11.0,
                    A 3.9 3.9 0.0 Bool.true Bool.false 12.0 18.8,
                    A 3.9 3.9 0.0 Bool.true Bool.false 12.0 11.0,
                    Z,
                ],
                lines: [],
                lineWidth: 2.0,
                cut: [],
                cutWidth: 2.0,
                over: [],
            }

        Vpn ->
            {
                solid: [
                    M 12.0 2.8,
                    L 19.6 5.6,
                    V 11.4,
                    C 19.6 16.2 16.4 19.6 12.0 21.4,
                    C 7.6 19.6 4.4 16.2 4.4 11.4,
                    V 5.6,
                    Z,
                ],
                lines: [],
                lineWidth: 2.0,
                cut: [
                    M 8.6 11.9,
                    L 11.0 14.3,
                    L 15.6 9.4,
                ],
                cutWidth: 2.0,
                over: [],
            }

        Offline ->
            {
                solid: [
                    M 12.0 17.7,
                    A 1.0 1.0 0.0 Bool.true Bool.false 12.0 19.7,
                    A 1.0 1.0 0.0 Bool.true Bool.false 12.0 17.7,
                    Z,
                ],
                lines: [
                    M 2.3 9.0,
                    A 13.7 13.7 0.0 Bool.false Bool.true 21.7 9.0,
                    M 5.4 12.1,
                    A 9.3 9.3 0.0 Bool.false Bool.true 18.6 12.1,
                    M 8.5 15.2,
                    A 4.9 4.9 0.0 Bool.false Bool.true 15.5 15.2,
                ],
                lineWidth: 2.2,
                cut: [
                    M 4.0 3.5,
                    L 20.0 20.5,
                ],
                cutWidth: 5.4,
                over: [
                    M 4.0 3.5,
                    L 20.0 20.5,
                ],
            }

        Wifi ->
            {
                solid: [
                    M 12.0 17.7,
                    A 1.0 1.0 0.0 Bool.true Bool.false 12.0 19.7,
                    A 1.0 1.0 0.0 Bool.true Bool.false 12.0 17.7,
                    Z,
                ],
                lines: [
                    M 2.3 9.0,
                    A 13.7 13.7 0.0 Bool.false Bool.true 21.7 9.0,
                    M 5.4 12.1,
                    A 9.3 9.3 0.0 Bool.false Bool.true 18.6 12.1,
                    M 8.5 15.2,
                    A 4.9 4.9 0.0 Bool.false Bool.true 15.5 15.2,
                ],
                lineWidth: 2.2,
                cut: [],
                cutWidth: 2.0,
                over: [],
            }

        Wired ->
            {
                solid: [
                    M 4.5 6.5,
                    H 19.5,
                    V 14.5,
                    H 16.0,
                    V 18.0,
                    H 8.0,
                    V 14.5,
                    H 4.5,
                    Z,
                ],
                lines: [],
                lineWidth: 2.0,
                cut: [
                    M 8.5 6.0,
                    V 9.6,
                    M 12.0 6.0,
                    V 9.6,
                    M 15.5 6.0,
                    V 9.6,
                ],
                cutWidth: 1.5,
                over: [],
            }

        Bell ->
            {
                solid: [
                    M 12.0 3.2,
                    C 8.6 3.2 6.6 5.8 6.6 9.2,
                    V 12.8,
                    L 4.8 16.2,
                    H 19.2,
                    L 17.4 12.8,
                    V 9.2,
                    C 17.4 5.8 15.4 3.2 12.0 3.2,
                    Z,
                    M 10.0 18.9,
                    A 2.0 2.0 0.0 Bool.false Bool.false 14.0 18.9,
                    Z,
                ],
                lines: [],
                lineWidth: 2.0,
                cut: [],
                cutWidth: 2.0,
                over: [],
            }

        Note ->
            {
                solid: [
                    M 7.2 15.0,
                    A 2.5 2.5 0.0 Bool.true Bool.false 7.2 20.0,
                    A 2.5 2.5 0.0 Bool.true Bool.false 7.2 15.0,
                    Z,
                    M 16.6 13.0,
                    A 2.5 2.5 0.0 Bool.true Bool.false 16.6 18.0,
                    A 2.5 2.5 0.0 Bool.true Bool.false 16.6 13.0,
                    Z,
                    M 9.2 5.4,
                    L 18.6 3.4,
                    V 6.8,
                    L 9.2 8.8,
                    Z,
                ],
                lines: [
                    M 9.3 17.5,
                    V 6.0,
                    M 18.7 15.5,
                    V 4.0,
                ],
                lineWidth: 1.8,
                cut: [],
                cutWidth: 2.0,
                over: [],
            }

        Battery ->
            {
                solid: [
                    M 5.1 10.7,
                    H 16.5,
                    V 13.3,
                    H 5.1,
                    Z,
                ],
                lines: [
                    M 4.2 7.6,
                    H 17.4,
                    A 2.2 2.2 0.0 Bool.false Bool.true 19.6 9.8,
                    V 14.2,
                    A 2.2 2.2 0.0 Bool.false Bool.true 17.4 16.4,
                    H 4.2,
                    A 2.2 2.2 0.0 Bool.false Bool.true 2.0 14.2,
                    V 9.8,
                    A 2.2 2.2 0.0 Bool.false Bool.true 4.2 7.6,
                    Z,
                    M 21.9 10.7,
                    V 13.3,
                ],
                lineWidth: 1.5,
                cut: [],
                cutWidth: 2.0,
                over: [],
            }

        Minus ->
            {
                solid: [],
                lines: [
                    M 5.5 12.0,
                    H 18.5,
                ],
                lineWidth: 2.4,
                cut: [],
                cutWidth: 2.0,
                over: [],
            }

        Plus ->
            {
                solid: [],
                lines: [
                    M 5.5 12.0,
                    H 18.5,
                    M 12.0 5.5,
                    V 18.5,
                ],
                lineWidth: 2.4,
                cut: [],
                cutWidth: 2.0,
                over: [],
            }

        Chevron ->
            {
                solid: [],
                lines: [
                    M 9.0 5.0,
                    L 16.0 12.0,
                    L 9.0 19.0,
                ],
                lineWidth: 2.6,
                cut: [],
                cutWidth: 2.0,
                over: [],
            }

        Back ->
            {
                solid: [],
                lines: [
                    M 15.0 5.0,
                    L 8.0 12.0,
                    L 15.0 19.0,
                ],
                lineWidth: 2.6,
                cut: [],
                cutWidth: 2.0,
                over: [],
            }

        Clock ->
            {
                solid: [],
                lines: [
                    M 12.0 4.0,
                    A 8.0 8.0 0.0 Bool.true Bool.false 12.0 20.0,
                    A 8.0 8.0 0.0 Bool.true Bool.false 12.0 4.0,
                    Z,
                    M 12.0 8.0,
                    V 12.2,
                    L 14.9 14.0,
                ],
                lineWidth: 2.0,
                cut: [],
                cutWidth: 2.0,
                over: [],
            }

        Gear ->
            {
                solid: [
                    M 12.0 5.8,
                    A 6.2 6.2 0.0 Bool.true Bool.false 12.0 18.2,
                    A 6.2 6.2 0.0 Bool.true Bool.false 12.0 5.8,
                    Z,
                ],
                lines: [
                    M 12.0 3.8,
                    V 20.2,
                    M 3.8 12.0,
                    H 20.2,
                    M 6.2 6.2,
                    L 17.8 17.8,
                    M 17.8 6.2,
                    L 6.2 17.8,
                ],
                lineWidth: 3.2,
                cut: [
                    M 12.0 12.0,
                    L 12.01 12.0,
                ],
                cutWidth: 5.6,
                over: [],
            }

        Lines ->
            {
                solid: [],
                lines: [
                    M 4.5 7.0,
                    H 19.5,
                    M 4.5 12.0,
                    H 19.5,
                    M 4.5 17.0,
                    H 13.0,
                ],
                lineWidth: 2.2,
                cut: [],
                cutWidth: 2.0,
                over: [],
            }

        Sparkle ->
            {
                solid: [
                    M 12.0 3.4,
                    C 12.6 8.4 15.6 11.4 20.6 12.0,
                    C 15.6 12.6 12.6 15.6 12.0 20.6,
                    C 11.4 15.6 8.4 12.6 3.4 12.0,
                    C 8.4 11.4 11.4 8.4 12.0 3.4,
                    Z,
                ],
                lines: [],
                lineWidth: 2.0,
                cut: [],
                cutWidth: 2.0,
                over: [],
            }

        Rim ->
            {
                solid: [],
                lines: [
                    M 8.0 7.5,
                    H 16.0,
                    A 4.5 4.5 0.0 Bool.false Bool.true 16.0 16.5,
                    H 8.0,
                    A 4.5 4.5 0.0 Bool.false Bool.true 8.0 7.5,
                    Z,
                ],
                lineWidth: 2.2,
                cut: [],
                cutWidth: 2.0,
                over: [],
            }

        Expand ->
            {
                solid: [],
                lines: [
                    M 4.5 9.5,
                    V 4.5,
                    H 9.5,
                    M 14.5 4.5,
                    H 19.5,
                    V 9.5,
                    M 19.5 14.5,
                    V 19.5,
                    H 14.5,
                    M 9.5 19.5,
                    H 4.5,
                    V 14.5,
                ],
                lineWidth: 2.2,
                cut: [],
                cutWidth: 2.0,
                over: [],
            }

        Windows ->
            {
                solid: [
                    M 4.6 4.6,
                    H 10.4,
                    V 10.4,
                    H 4.6,
                    Z,
                    M 13.6 4.6,
                    H 19.4,
                    V 10.4,
                    H 13.6,
                    Z,
                    M 4.6 13.6,
                    H 10.4,
                    V 19.4,
                    H 4.6,
                    Z,
                    M 13.6 13.6,
                    H 19.4,
                    V 19.4,
                    H 13.6,
                    Z,
                ],
                lines: [],
                lineWidth: 2.0,
                cut: [],
                cutWidth: 2.0,
                over: [],
            }

        Linux ->
            {
                solid: [
                    M 12.0 4.0,
                    C 11.29 5.75 10.86 6.89 10.06 8.58,
                    C 10.55 9.1 11.15 9.7 12.12 10.37,
                    C 11.07 9.95 10.36 9.52 9.83 9.07,
                    C 8.82 11.19 7.23 14.2 4.0 20.0,
                    C 6.54 18.54 8.5 17.63 10.33 17.29,
                    C 10.26 16.95 10.21 16.59 10.21 16.2,
                    L 10.22 16.12,
                    C 10.26 14.5 11.1 13.25 12.1 13.33,
                    C 13.11 13.42 13.88 14.8 13.84 16.43,
                    C 13.84 16.74 13.8 17.03 13.74 17.3,
                    C 15.55 17.66 17.5 18.56 20.0 20.0,
                    C 19.51 19.09 19.07 18.27 18.65 17.49,
                    C 17.98 16.98 17.29 16.31 15.88 15.59,
                    C 16.85 15.84 17.55 16.13 18.09 16.46,
                    C 13.81 8.5 13.46 7.44 12.0 4.0,
                    Z,
                ],
                lines: [],
                lineWidth: 2.0,
                cut: [],
                cutWidth: 2.0,
                over: [],
            }

        Power ->
            {
                solid: [],
                lines: [
                    M 12.0 3.8,
                    V 11.4,
                    M 7.4 6.9,
                    A 7.2 7.2 0.0 Bool.true Bool.false 16.6 6.9,
                ],
                lineWidth: 2.2,
                cut: [],
                cutWidth: 2.0,
                over: [],
            }

        Look ->
            {
                solid: [
                    M 12.0 5.0,
                    A 7.0 7.0 0.0 Bool.false Bool.true 12.0 19.0,
                    Z,
                ],
                lines: [
                    M 12.0 4.0,
                    A 8.0 8.0 0.0 Bool.true Bool.false 12.0 20.0,
                    A 8.0 8.0 0.0 Bool.true Bool.false 12.0 4.0,
                    Z,
                ],
                lineWidth: 2.0,
                cut: [],
                cutWidth: 2.0,
                over: [],
            }

        Size ->
            {
                solid: [],
                lines: [
                    M 6.0 18.0,
                    L 18.0 6.0,
                    M 12.0 5.0,
                    H 19.0,
                    V 12.0,
                    M 12.0 19.0,
                    H 5.0,
                    V 12.0,
                ],
                lineWidth: 2.2,
                cut: [],
                cutWidth: 2.0,
                over: [],
            }

        Gap ->
            {
                solid: [],
                lines: [
                    M 4.0 4.6,
                    H 20.0,
                    M 8.5 12.6,
                    H 15.5,
                    A 3.2 3.2 0.0 Bool.false Bool.true 15.5 19.0,
                    H 8.5,
                    A 3.2 3.2 0.0 Bool.false Bool.true 8.5 12.6,
                    Z,
                ],
                lineWidth: 2.2,
                cut: [],
                cutWidth: 2.0,
                over: [],
            }

        Drop ->
            {
                solid: [
                    M 12.0 4.0,
                    C 9.6 7.4 6.2 11.0 6.2 14.4,
                    A 5.8 5.8 0.0 Bool.false Bool.false 17.8 14.4,
                    C 17.8 11.0 14.4 7.4 12.0 4.0,
                    Z,
                ],
                lines: [],
                lineWidth: 2.0,
                cut: [],
                cutWidth: 2.0,
                over: [],
            }

        Moon ->
            {
                solid: [
                    M 10.58 4.44,
                    A 8.2 8.2 0.0 Bool.true Bool.false 19.52 13.74,
                    A 6.8 6.8 0.0 Bool.false Bool.true 10.58 4.44,
                    Z,
                ],
                lines: [],
                lineWidth: 2.0,
                cut: [],
                cutWidth: 2.0,
                over: [],
            }

        Tray ->
            {
                solid: [],
                lines: [
                    M 4.0 13.5,
                    L 6.4 6.2,
                    A 1.6 1.6 0.0 Bool.false Bool.true 7.9 5.1,
                    H 16.1,
                    A 1.6 1.6 0.0 Bool.false Bool.true 17.6 6.2,
                    L 20.0 13.5,
                    V 17.6,
                    A 2.0 2.0 0.0 Bool.false Bool.true 18.0 19.6,
                    H 6.0,
                    A 2.0 2.0 0.0 Bool.false Bool.true 4.0 17.6,
                    Z,
                    M 4.0 13.5,
                    H 8.6,
                    L 9.8 15.6,
                    H 14.2,
                    L 15.4 13.5,
                    H 20.0,
                ],
                lineWidth: 2.0,
                cut: [],
                cutWidth: 2.0,
                over: [],
            }

        Cross ->
            {
                solid: [],
                lines: [
                    M 7.5 7.5,
                    L 16.5 16.5,
                    M 16.5 7.5,
                    L 7.5 16.5,
                ],
                lineWidth: 2.6,
                cut: [],
                cutWidth: 2.0,
                over: [],
            }

expect List.len allGlyphs == 33
expect List.len (getIconArt Mute).solid == 7
expect List.len (getIconArt Mute).lines == 4
expect List.len (getIconArt Quiet).lines == 2
expect List.len (getIconArt Mid).lines == 4
expect List.len (getIconArt Loud).lines == 6
expect List.len (getIconArt Headphones).solid == 10
expect List.len (getIconArt Headphones).lines == 4
expect List.len (getIconArt Speaker).solid == 13
expect List.len (getIconArt Vpn).solid == 7
expect List.len (getIconArt Vpn).cut == 3
expect List.len (getIconArt Offline).over == 2
expect List.len (getIconArt Wired).solid == 9
expect List.len (getIconArt Wired).cut == 6
expect List.len (getIconArt Windows).solid == 20
expect List.len (getIconArt Linux).solid == 17
expect List.len (List.map allGlyphs getIconArt) == 33
expect Num.is_approx_eq (getIconArt Mute).lineWidth 2.0 {}
expect Num.is_approx_eq (getIconArt Offline).lineWidth 2.2 {}
expect Num.is_approx_eq (getIconArt Offline).cutWidth 5.4 {}
expect Num.is_approx_eq (getIconArt Wired).cutWidth 1.5 {}
expect Num.is_approx_eq (getIconArt Note).lineWidth 1.8 {}
expect Num.is_approx_eq (getIconArt Battery).lineWidth 1.5 {}
expect Num.is_approx_eq (getIconArt Gear).lineWidth 3.2 {}
expect Num.is_approx_eq (getIconArt Gear).cutWidth 5.6 {}
expect Num.is_approx_eq (getIconArt Linux).lineWidth 2.0 {}
