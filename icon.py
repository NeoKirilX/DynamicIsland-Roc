
from __future__ import annotations

import functools
import math
import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import Sequence

import cairo

GRID: float = 24.0
SOFT: float = 1.5
TOLERANCE: float = 0.01

class Glyph(Enum):

    Mute = auto()
    Quiet = auto()
    Mid = auto()
    Loud = auto()
    Headphones = auto()
    Speaker = auto()
    Vpn = auto()
    Offline = auto()
    Wifi = auto()
    Wired = auto()
    Bell = auto()
    Note = auto()
    Battery = auto()
    Minus = auto()
    Plus = auto()
    Chevron = auto()
    Back = auto()
    Clock = auto()
    Gear = auto()
    Lines = auto()
    Sparkle = auto()
    Rim = auto()
    Expand = auto()
    Windows = auto()
    Linux = auto()
    Power = auto()
    Look = auto()
    Size = auto()
    Gap = auto()
    Drop = auto()
    Moon = auto()
    Tray = auto()
    Cross = auto()
    Pulse = auto()
    Bolt = auto()
    VpnOff = auto()
    Mic = auto()
    Camera = auto()
    Sun = auto()
    Cloud = auto()
    CloudRain = auto()
    CloudSnow = auto()

@dataclass(frozen=True)
class Art:

    solid: str = ""
    lines: str = ""
    line: float = 2.0
    cut: str = ""
    gap: float = 2.0
    over: str = ""
    soft: float = SOFT

Horn: str = "M2.5,9.6 H6 L10.6,5.6 V18.4 L6,14.4 H2.5 Z"
Wave1: str = "M13.3,9.3 A3.8,3.8 0 0 1 13.3,14.7"
Wave2: str = " M15.7,6.9 A7.2,7.2 0 0 1 15.7,17.1"
Wave3: str = " M18.1,4.5 A10.6,10.6 0 0 1 18.1,19.5"
Fan: str = (
    "M2.3,9 A13.7,13.7 0 0 1 21.7,9 M5.4,12.1 A9.3,9.3 0 0 1 18.6,12.1 "
    "M8.5,15.2 A4.9,4.9 0 0 1 15.5,15.2"
)
Dot: str = "M12,17.7 A1,1 0 1 0 12,19.7 A1,1 0 1 0 12,17.7 Z"
Slash: str = "M4,3.5 L20,20.5"

ArchLinux: str = (
    "M12.0,3.7 C11.26,5.51 10.81,6.7 9.99,8.45 C10.5,8.99 11.12,9.61 12.12,10.31 "
    "C11.04,9.87 10.3,9.42 9.75,8.96 C8.7,11.16 7.05,14.29 3.7,20.3 "
    "C6.33,18.78 8.37,17.85 10.27,17.49 C10.19,17.14 10.14,16.76 10.15,16.36 "
    "L10.15,16.28 C10.19,14.59 11.07,13.3 12.11,13.38 C13.15,13.47 13.95,14.91 "
    "13.91,16.6 C13.9,16.91 13.87,17.22 13.81,17.5 C15.69,17.87 17.7,18.8 20.3,20.3 "
    "C19.79,19.36 19.33,18.51 18.89,17.7 C18.21,17.17 17.49,16.47 16.03,15.72 "
    "C17.03,15.99 17.75,16.29 18.31,16.62 C13.88,8.37 13.52,7.27 12.0,3.7 Z"
)

ARTS: dict[Glyph, Art] = {
    Glyph.Mute: Art(Horn, "M14.8,9.2 L20.4,14.8 M20.4,9.2 L14.8,14.8"),
    Glyph.Quiet: Art(Horn, Wave1),
    Glyph.Mid: Art(Horn, Wave1 + Wave2),
    Glyph.Loud: Art(Horn, Wave1 + Wave2 + Wave3),
    Glyph.Headphones: Art(
        "M3.6,14 H7 V19.6 H3.6 Z M17,14 H20.4 V19.6 H17 Z",
        "M4.6,14 V12.2 A7.4,7.4 0 0 1 19.4,12.2 V14",
    ),
    Glyph.Speaker: Art(
        "F0 M7.2,3.4 H16.8 V20.6 H7.2 Z "
        "M12,5.4 A2.1,2.1 0 1 0 12,9.6 A2.1,2.1 0 1 0 12,5.4 Z "
        "M12,11 A3.9,3.9 0 1 0 12,18.8 A3.9,3.9 0 1 0 12,11 Z"
    ),
    Glyph.Vpn: Art(
        "M12,2.8 L19.6,5.6 V11.4 C19.6,16.2 16.4,19.6 12,21.4 C7.6,19.6 4.4,16.2 4.4,11.4 V5.6 Z",
        cut="M8.6,11.9 L11,14.3 L15.6,9.4",
    ),
    Glyph.Offline: Art(Dot, Fan, line=2.2, cut=Slash, gap=5.4, over=Slash),
    Glyph.Wifi: Art(Dot, Fan, line=2.2),
    Glyph.Wired: Art(
        "M4.5,6.5 H19.5 V14.5 H16 V18 H8 V14.5 H4.5 Z",
        cut="M8.5,6 V9.6 M12,6 V9.6 M15.5,6 V9.6",
        gap=1.5,
    ),
    Glyph.Bell: Art(
        "M12,3.2 C8.6,3.2 6.6,5.8 6.6,9.2 V12.8 L4.8,16.2 H19.2 L17.4,12.8 V9.2 C17.4,5.8 15.4,3.2 12,3.2 Z "
        "M10,18.9 A2,2 0 0 0 14,18.9 Z"
    ),
    Glyph.Note: Art(
        "M7.2,15 A2.5,2.5 0 1 0 7.2,20 A2.5,2.5 0 1 0 7.2,15 Z "
        "M16.6,13 A2.5,2.5 0 1 0 16.6,18 A2.5,2.5 0 1 0 16.6,13 Z "
        "M9.2,5.4 L18.6,3.4 V6.8 L9.2,8.8 Z",
        "M9.3,17.5 V6 M18.7,15.5 V4",
        line=1.8,
    ),
    Glyph.Battery: Art(
        "M5.1,10.7 H16.5 V13.3 H5.1 Z",
        "M4.2,7.6 H17.4 A2.2,2.2 0 0 1 19.6,9.8 V14.2 A2.2,2.2 0 0 1 17.4,16.4 H4.2 A2.2,2.2 0 0 1 2,14.2 V9.8 A2.2,2.2 0 0 1 4.2,7.6 Z "
        "M21.9,10.7 V13.3",
        line=1.5,
    ),
    Glyph.Minus: Art(lines="M5.5,12 H18.5", line=2.4),
    Glyph.Plus: Art(lines="M5.5,12 H18.5 M12,5.5 V18.5", line=2.4),
    Glyph.Chevron: Art(lines="M9,5 L16,12 L9,19", line=2.6),
    Glyph.Back: Art(lines="M15,5 L8,12 L15,19", line=2.6),
    Glyph.Clock: Art(
        lines="M12,4 A8,8 0 1 0 12,20 A8,8 0 1 0 12,4 Z M12,8 V12.2 L14.9,14"
    ),
    Glyph.Gear: Art(
        "M12,5.8 A6.2,6.2 0 1 0 12,18.2 A6.2,6.2 0 1 0 12,5.8 Z",
        "M12,3.8 V20.2 M3.8,12 H20.2 M6.2,6.2 L17.8,17.8 M17.8,6.2 L6.2,17.8",
        line=3.2,
        cut="M12,12 L12.01,12",
        gap=5.6,
    ),
    Glyph.Lines: Art(
        lines="M4.5,7 H19.5 M4.5,12 H19.5 M4.5,17 H13", line=2.2
    ),
    Glyph.Sparkle: Art(
        "M12,3.4 C12.6,8.4 15.6,11.4 20.6,12 C15.6,12.6 12.6,15.6 12,20.6 "
        "C11.4,15.6 8.4,12.6 3.4,12 C8.4,11.4 11.4,8.4 12,3.4 Z"
    ),
    Glyph.Rim: Art(
        lines="M8,7.5 H16 A4.5,4.5 0 0 1 16,16.5 H8 A4.5,4.5 0 0 1 8,7.5 Z",
        line=2.2,
    ),
    Glyph.Expand: Art(
        lines="M4.5,9.5 V4.5 H9.5 M14.5,4.5 H19.5 V9.5 M19.5,14.5 V19.5 H14.5 M9.5,19.5 H4.5 V14.5",
        line=2.2,
    ),
    Glyph.Windows: Art(
        "M4.6,4.6 H10.4 V10.4 H4.6 Z M13.6,4.6 H19.4 V10.4 H13.6 Z "
        "M4.6,13.6 H10.4 V19.4 H4.6 Z M13.6,13.6 H19.4 V19.4 H13.6 Z"
    ),
    Glyph.Linux: Art(ArchLinux, soft=0.6),
    Glyph.Power: Art(
        lines="M12,3.8 V11.4 M7.4,6.9 A7.2,7.2 0 1 0 16.6,6.9", line=2.2
    ),
    Glyph.Look: Art(
        "M12,5 A7,7 0 0 1 12,19 Z",
        "M12,4 A8,8 0 1 0 12,20 A8,8 0 1 0 12,4 Z",
    ),
    Glyph.Size: Art(
        lines="M6,18 L18,6 M12,5 H19 V12 M12,19 H5 V12", line=2.2
    ),
    Glyph.Gap: Art(
        lines="M4,4.6 H20 M8.5,12.6 H15.5 A3.2,3.2 0 0 1 15.5,19 H8.5 A3.2,3.2 0 0 1 8.5,12.6 Z",
        line=2.2,
    ),
    Glyph.Drop: Art(
        "M12,4 C9.6,7.4 6.2,11 6.2,14.4 A5.8,5.8 0 0 0 17.8,14.4 C17.8,11 14.4,7.4 12,4 Z"
    ),
    Glyph.Moon: Art(
        "M10.58,4.44 A8.2,8.2 0 1 0 19.52,13.74 A6.8,6.8 0 0 1 10.58,4.44 Z"
    ),
    Glyph.Tray: Art(
        lines="M4,13.5 L6.4,6.2 A1.6,1.6 0 0 1 7.9,5.1 H16.1 A1.6,1.6 0 0 1 17.6,6.2 L20,13.5 V17.6 A2,2 0 0 1 18,19.6 H6 A2,2 0 0 1 4,17.6 Z M4,13.5 H8.6 L9.8,15.6 H14.2 L15.4,13.5 H20",
        line=2.0,
    ),
    Glyph.Cross: Art(
        lines="M7.5,7.5 L16.5,16.5 M16.5,7.5 L7.5,16.5",
        line=2.6,
    ),
    Glyph.Pulse: Art(
        lines="M3,12.5 H7.6 L10.2,6 L13.8,18.5 L16.2,12.5 H21",
        line=2.2,
    ),
    Glyph.Bolt: Art(
        "M13.6,3 L6.2,13.3 H11.3 L10.4,21 L17.8,10.7 H12.7 Z"
    ),
    Glyph.VpnOff: Art(
        lines="M12,2.8 L19.6,5.6 V11.4 C19.6,16.2 16.4,19.6 12,21.4 C7.6,19.6 4.4,16.2 4.4,11.4 V5.6 Z M4,4 L20,20",
        line=2.0,
    ),
    Glyph.Mic: Art(
        solid="M12,4 C13.65,4 15,5.35 15,7 V12 C15,13.65 13.65,15 12,15 C10.35,15 9,13.65 9,12 V7 C9,5.35 10.35,4 12,4 Z",
        lines="M6.5,11 C6.5,14 8.9,16.5 12,16.5 C15.1,16.5 17.5,14 17.5,11 M12,16.5 V20.5 M8.5,20.5 H15.5",
        line=1.8,
    ),
    Glyph.Camera: Art(
        lines="M3,8 H21 A2,2 0 0 1 23,10 V18 A2,2 0 0 1 21,20 H3 A2,2 0 0 1 1,18 V10 A2,2 0 0 1 3,8 Z M12,11 A3,3 0 1 0 12,17 A3,3 0 1 0 12,11 Z M7,5 H11 L12,8 H6 Z",
        line=1.8,
    ),
    Glyph.Sun: Art(
        solid="M12,8 A4,4 0 1 0 12,16 A4,4 0 1 0 12,8 Z",
        lines="M12,2 V4.5 M12,19.5 V22 M2,12 H4.5 M19.5,12 H22 M4.9,4.9 L6.7,6.7 M17.3,17.3 L19.1,19.1 M4.9,19.1 L6.7,17.3 M17.3,6.7 L19.1,4.9",
        line=1.8,
    ),
    Glyph.Cloud: Art(
        solid="M7.5,18 H17 A4,4 0 0 0 17,10 A6,6 0 0 0 6,12 A3.5,3.5 0 0 0 7.5,18 Z",
    ),
    Glyph.CloudRain: Art(
        solid="M7.5,16 H17 A3.5,3.5 0 0 0 17,9 A5,5 0 0 0 7.5,10 A3,3 0 0 0 7.5,16 Z",
        lines="M8,18 L6.5,21.5 M12,18 L10.5,21.5 M16,18 L14.5,21.5",
        line=1.8,
    ),
    Glyph.CloudSnow: Art(
        solid="M7.5,16 H17 A3.5,3.5 0 0 0 17,9 A5,5 0 0 0 7.5,10 A3,3 0 0 0 7.5,16 Z",
        lines="M8,19.5 H8.01 M12,19.5 H12.01 M16,19.5 H16.01 M10,21.5 H10.01 M14,21.5 H14.01",
        line=2.4,
    ),
}

_TOKEN_RE = re.compile(
    r"([a-zA-Z]|[-+]?(?:[0-9]*\.[0-9]+|[0-9]+)(?:[eE][-+]?[0-9]+)?)"
)

def arc_to_beziers(
    x1: float,
    y1: float,
    rx: float,
    ry: float,
    phi_deg: float,
    large_arc: int,
    sweep: int,
    x2: float,
    y2: float,
) -> list[tuple[float, float, float, float, float, float]]:
    if x1 == x2 and y1 == y2:
        return []
    rx, ry = abs(rx), abs(ry)
    if rx == 0.0 or ry == 0.0:
        cp1x = (2.0 * x1 + x2) / 3.0
        cp1y = (2.0 * y1 + y2) / 3.0
        cp2x = (x1 + 2.0 * x2) / 3.0
        cp2y = (y1 + 2.0 * y2) / 3.0
        return [(cp1x, cp1y, cp2x, cp2y, x2, y2)]

    phi = math.radians(phi_deg % 360.0)
    cos_phi = math.cos(phi)
    sin_phi = math.sin(phi)

    dx = (x1 - x2) / 2.0
    dy = (y1 - y2) / 2.0
    x1_p = cos_phi * dx + sin_phi * dy
    y1_p = -sin_phi * dx + cos_phi * dy

    rx_sq = rx * rx
    ry_sq = ry * ry
    x1_p_sq = x1_p * x1_p
    y1_p_sq = y1_p * y1_p

    rad_check = x1_p_sq / rx_sq + y1_p_sq / ry_sq
    if rad_check > 1.0:
        scale = math.sqrt(rad_check)
        rx *= scale
        ry *= scale
        rx_sq = rx * rx
        ry_sq = ry * ry

    denom = rx_sq * y1_p_sq + ry_sq * x1_p_sq
    num = max(0.0, rx_sq * ry_sq - denom)
    s = math.sqrt(num / denom) if denom > 0.0 else 0.0
    if bool(large_arc) == bool(sweep):
        s = -s

    cx_p = s * (rx * y1_p / ry)
    cy_p = s * (-ry * x1_p / rx)

    cx = cos_phi * cx_p - sin_phi * cy_p + (x1 + x2) / 2.0
    cy = sin_phi * cx_p + cos_phi * cy_p + (y1 + y2) / 2.0

    ux = (x1_p - cx_p) / rx
    uy = (y1_p - cy_p) / ry
    vx = (-x1_p - cx_p) / rx
    vy = (-y1_p - cy_p) / ry

    theta1 = math.atan2(uy, ux)
    d_theta = math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)
    sweep_flag = bool(sweep)
    if not sweep_flag and d_theta > 0:
        d_theta -= 2.0 * math.pi
    elif sweep_flag and d_theta < 0:
        d_theta += 2.0 * math.pi

    num_segments = max(1, math.ceil(abs(d_theta) / (math.pi / 2.0)))
    segment_d_theta = d_theta / num_segments

    def transform_pt(u: float, v: float) -> tuple[float, float]:
        xu = rx * u
        yv = ry * v
        return (
            cos_phi * xu - sin_phi * yv + cx,
            sin_phi * xu + cos_phi * yv + cy,
        )

    curves: list[tuple[float, float, float, float, float, float]] = []
    t = theta1
    for i in range(num_segments):
        t_next = t + segment_d_theta
        delta = segment_d_theta
        k = (4.0 / 3.0) * math.tan(delta / 4.0)

        cos_t = math.cos(t)
        sin_t = math.sin(t)
        cos_t_next = math.cos(t_next)
        sin_t_next = math.sin(t_next)

        p1 = (cos_t - k * sin_t, sin_t + k * cos_t)
        p2 = (cos_t_next + k * sin_t_next, sin_t_next - k * cos_t_next)
        p3 = (cos_t_next, sin_t_next)

        c1x, c1y = transform_pt(p1[0], p1[1])
        c2x, c2y = transform_pt(p2[0], p2[1])
        end_x, end_y = (x2, y2) if i == num_segments - 1 else transform_pt(p3[0], p3[1])

        curves.append((c1x, c1y, c2x, c2y, end_x, end_y))
        t = t_next

    return curves

@functools.lru_cache(maxsize=256)
def compile_svg_path(path_str: str) -> tuple[tuple[str, tuple[float, ...]], ...]:
    tokens = _TOKEN_RE.findall(path_str)
    if not tokens:
        return ()

    ops: list[tuple[str, tuple[float, ...]]] = []
    idx = 0
    n = len(tokens)

    current_x = 0.0
    current_y = 0.0
    start_x = 0.0
    start_y = 0.0
    last_ctrl_x = 0.0
    last_ctrl_y = 0.0
    last_cmd = ""
    cmd: str | None = None
    has_moved = False

    while idx < n:
        tok = tokens[idx]
        if tok.isalpha():
            cmd = tok
            idx += 1
            if cmd == "F":
                rule = int(tokens[idx])
                idx += 1
                ops.append(("F", (float(rule),)))
                cmd = None
                continue
            if cmd in ("Z", "z"):
                ops.append(("Z", ()))
                current_x = start_x
                current_y = start_y
                last_cmd = cmd
                continue
        elif cmd is None:
            idx += 1
            continue

        if cmd == "M":
            x = float(tokens[idx])
            y = float(tokens[idx + 1])
            idx += 2
            ops.append(("M", (x, y)))
            current_x = start_x = x
            current_y = start_y = y
            has_moved = True
            cmd = "L"
            last_cmd = "M"
        elif cmd == "m":
            if not has_moved:
                x = float(tokens[idx])
                y = float(tokens[idx + 1])
            else:
                x = current_x + float(tokens[idx])
                y = current_y + float(tokens[idx + 1])
            idx += 2
            ops.append(("M", (x, y)))
            current_x = start_x = x
            current_y = start_y = y
            has_moved = True
            cmd = "l"
            last_cmd = "m"
        elif cmd == "L":
            x = float(tokens[idx])
            y = float(tokens[idx + 1])
            idx += 2
            ops.append(("L", (x, y)))
            current_x = x
            current_y = y
            last_cmd = "L"
        elif cmd == "l":
            x = current_x + float(tokens[idx])
            y = current_y + float(tokens[idx + 1])
            idx += 2
            ops.append(("L", (x, y)))
            current_x = x
            current_y = y
            last_cmd = "l"
        elif cmd == "H":
            x = float(tokens[idx])
            idx += 1
            ops.append(("L", (x, current_y)))
            current_x = x
            last_cmd = "H"
        elif cmd == "h":
            x = current_x + float(tokens[idx])
            idx += 1
            ops.append(("L", (x, current_y)))
            current_x = x
            last_cmd = "h"
        elif cmd == "V":
            y = float(tokens[idx])
            idx += 1
            ops.append(("L", (current_x, y)))
            current_y = y
            last_cmd = "V"
        elif cmd == "v":
            y = current_y + float(tokens[idx])
            idx += 1
            ops.append(("L", (current_x, y)))
            current_y = y
            last_cmd = "v"
        elif cmd == "C":
            c1x = float(tokens[idx])
            c1y = float(tokens[idx + 1])
            c2x = float(tokens[idx + 2])
            c2y = float(tokens[idx + 3])
            x = float(tokens[idx + 4])
            y = float(tokens[idx + 5])
            idx += 6
            ops.append(("C", (c1x, c1y, c2x, c2y, x, y)))
            last_ctrl_x = c2x
            last_ctrl_y = c2y
            current_x = x
            current_y = y
            last_cmd = "C"
        elif cmd == "c":
            c1x = current_x + float(tokens[idx])
            c1y = current_y + float(tokens[idx + 1])
            c2x = current_x + float(tokens[idx + 2])
            c2y = current_y + float(tokens[idx + 3])
            x = current_x + float(tokens[idx + 4])
            y = current_y + float(tokens[idx + 5])
            idx += 6
            ops.append(("C", (c1x, c1y, c2x, c2y, x, y)))
            last_ctrl_x = c2x
            last_ctrl_y = c2y
            current_x = x
            current_y = y
            last_cmd = "c"
        elif cmd == "S":
            if last_cmd in ("C", "c", "S", "s"):
                c1x = 2.0 * current_x - last_ctrl_x
                c1y = 2.0 * current_y - last_ctrl_y
            else:
                c1x = current_x
                c1y = current_y
            c2x = float(tokens[idx])
            c2y = float(tokens[idx + 1])
            x = float(tokens[idx + 2])
            y = float(tokens[idx + 3])
            idx += 4
            ops.append(("C", (c1x, c1y, c2x, c2y, x, y)))
            last_ctrl_x = c2x
            last_ctrl_y = c2y
            current_x = x
            current_y = y
            last_cmd = "S"
        elif cmd == "s":
            if last_cmd in ("C", "c", "S", "s"):
                c1x = 2.0 * current_x - last_ctrl_x
                c1y = 2.0 * current_y - last_ctrl_y
            else:
                c1x = current_x
                c1y = current_y
            c2x = current_x + float(tokens[idx])
            c2y = current_y + float(tokens[idx + 1])
            x = current_x + float(tokens[idx + 2])
            y = current_y + float(tokens[idx + 3])
            idx += 4
            ops.append(("C", (c1x, c1y, c2x, c2y, x, y)))
            last_ctrl_x = c2x
            last_ctrl_y = c2y
            current_x = x
            current_y = y
            last_cmd = "s"
        elif cmd == "A":
            rx = float(tokens[idx])
            ry = float(tokens[idx + 1])
            rot = float(tokens[idx + 2])
            large = int(float(tokens[idx + 3]))
            sweep = int(float(tokens[idx + 4]))
            x = float(tokens[idx + 5])
            y = float(tokens[idx + 6])
            idx += 7
            for b in arc_to_beziers(
                current_x, current_y, rx, ry, rot, large, sweep, x, y
            ):
                ops.append(("C", b))
            current_x = x
            current_y = y
            last_cmd = "A"
        elif cmd == "a":
            rx = float(tokens[idx])
            ry = float(tokens[idx + 1])
            rot = float(tokens[idx + 2])
            large = int(float(tokens[idx + 3]))
            sweep = int(float(tokens[idx + 4]))
            x = current_x + float(tokens[idx + 5])
            y = current_y + float(tokens[idx + 6])
            idx += 7
            for b in arc_to_beziers(
                current_x, current_y, rx, ry, rot, large, sweep, x, y
            ):
                ops.append(("C", b))
            current_x = x
            current_y = y
            last_cmd = "a"
        else:
            idx += 1

    return tuple(ops)

def execute_path_ops(
    cr: cairo.Context, ops: Sequence[tuple[str, tuple[float, ...]]]
) -> None:
    for cmd, args in ops:
        if cmd == "M":
            cr.move_to(args[0], args[1])
        elif cmd == "L":
            cr.line_to(args[0], args[1])
        elif cmd == "C":
            cr.curve_to(args[0], args[1], args[2], args[3], args[4], args[5])
        elif cmd == "Z":
            cr.close_path()
        elif cmd == "F":
            rule = int(args[0])
            cr.set_fill_rule(
                cairo.FILL_RULE_EVEN_ODD if rule == 0 else cairo.FILL_RULE_WINDING
            )

def parse_svg_path(cr: cairo.Context, path_str: str) -> None:
    ops = compile_svg_path(path_str)
    execute_path_ops(cr, ops)

def render_icon(
    cr: cairo.Context,
    glyph: Glyph,
    x: float,
    y: float,
    size: float,
    color: tuple[float, float, float] | tuple[float, float, float, float] = (
        1.0,
        1.0,
        1.0,
    ),
    alpha: float = 1.0,
    stroke_width: float | None = None,
) -> None:
    if size <= 0.0 or alpha <= 0.0:
        return

    art = ARTS[glyph]
    line_w = stroke_width if stroke_width is not None else art.line

    if len(color) >= 4:
        r, g, b, a = color[0], color[1], color[2], color[3]
        effective_alpha = alpha * a
    else:
        r, g, b = color[0], color[1], color[2]
        effective_alpha = alpha

    cr.save()
    cr.translate(x, y)
    scale = size / GRID
    cr.scale(scale, scale)

    cr.push_group()
    cr.set_source_rgba(r, g, b, 1.0)

    if art.solid:
        cr.new_path()
        parse_svg_path(cr, art.solid)
        cr.fill_preserve()
        if art.soft > 0.0:
            cr.set_line_width(art.soft)
            cr.set_line_cap(cairo.LINE_CAP_ROUND)
            cr.set_line_join(cairo.LINE_JOIN_ROUND)
            cr.stroke()
        else:
            cr.new_path()

    if art.lines:
        cr.new_path()
        parse_svg_path(cr, art.lines)
        cr.set_line_width(line_w)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        cr.stroke()

    if art.cut:
        cr.set_operator(cairo.OPERATOR_CLEAR)
        cr.new_path()
        parse_svg_path(cr, art.cut)
        cr.set_line_width(art.gap)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        cr.stroke()
        cr.set_operator(cairo.OPERATOR_OVER)

    if art.over:
        cr.set_source_rgba(r, g, b, 1.0)
        cr.new_path()
        parse_svg_path(cr, art.over)
        cr.set_line_width(line_w)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        cr.stroke()

    group = cr.pop_group()
    cr.set_source(group)
    if effective_alpha < 1.0:
        cr.paint_with_alpha(effective_alpha)
    else:
        cr.paint()

    cr.restore()

def render_battery(
    cr: cairo.Context,
    x: float,
    y: float,
    size: float,
    level: float = 1.0,
    color: tuple[float, float, float] | tuple[float, float, float, float] = (
        1.0,
        1.0,
        1.0,
    ),
    alpha: float = 1.0,
) -> None:
    lvl = max(0.0, min(1.0, float(level)))
    min_x = 5.1
    max_w = 11.4
    bar_w = max_w * lvl
    dynamic_solid = (
        f"M{min_x},10.7 H{min_x + bar_w} V13.3 H{min_x} Z" if bar_w > 0.1 else ""
    )

    shell_lines = (
        "M4.2,7.6 H17.4 A2.2,2.2 0 0 1 19.6,9.8 V14.2 A2.2,2.2 0 0 1 17.4,16.4 "
        "H4.2 A2.2,2.2 0 0 1 2,14.2 V9.8 A2.2,2.2 0 0 1 4.2,7.6 Z M21.9,10.7 V13.3"
    )

    if len(color) >= 4:
        r, g, b, a = color[0], color[1], color[2], color[3]
        effective_alpha = alpha * a
    else:
        r, g, b = color[0], color[1], color[2]
        effective_alpha = alpha

    cr.save()
    cr.translate(x, y)
    scale = size / GRID
    cr.scale(scale, scale)

    cr.push_group()
    cr.set_source_rgba(r, g, b, 1.0)

    if dynamic_solid:
        cr.new_path()
        parse_svg_path(cr, dynamic_solid)
        cr.fill_preserve()
        cr.set_line_width(SOFT)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        cr.stroke()

    cr.new_path()
    parse_svg_path(cr, shell_lines)
    cr.set_line_width(1.5)
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    cr.set_line_join(cairo.LINE_JOIN_ROUND)
    cr.stroke()

    group = cr.pop_group()
    cr.set_source(group)
    if effective_alpha < 1.0:
        cr.paint_with_alpha(effective_alpha)
    else:
        cr.paint()

    cr.restore()

class Icon:

    def __init__(
        self,
        glyph: Glyph = Glyph.Note,
        size: float = 24.0,
        color: tuple[float, float, float]
        | tuple[float, float, float, float] = (1.0, 1.0, 1.0),
        alpha: float = 1.0,
        stroke_width: float | None = None,
    ) -> None:
        self.glyph = glyph
        self.size = float(size)
        self.color = color
        self.alpha = float(alpha)
        self.stroke_width = stroke_width

    def render(self, cr: cairo.Context, x: float, y: float) -> None:
        render_icon(
            cr,
            self.glyph,
            x,
            y,
            self.size,
            self.color,
            self.alpha,
            self.stroke_width,
        )

if __name__ == "__main__":
    print("Testing icon vector iconography engine...")

    test_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 100, 100)
    test_cr = cairo.Context(test_surface)
    test_cr.set_source_rgb(1.0, 1.0, 1.0)
    parse_svg_path(test_cr, "M10,10 H90 V90 H10 Z")
    test_cr.fill()
    test_stride = test_surface.get_stride()
    assert (
        test_surface.get_data()[50 * test_stride + 50 * 4] != 0
    ), "Direct parse_svg_path failed to draw pixels"
    print("Test 1 (Direct SVG path parser): Success")

    required_glyphs = [
        Glyph.Mute,
        Glyph.Loud,
        Glyph.Wifi,
        Glyph.Battery,
        Glyph.Sparkle,
        Glyph.Linux,
    ]
    img_size = 48
    surf = cairo.ImageSurface(
        cairo.FORMAT_ARGB32, len(required_glyphs) * img_size, img_size
    )
    cr = cairo.Context(surf)

    for i, g in enumerate(required_glyphs):
        render_icon(
            cr,
            g,
            x=i * img_size + 4,
            y=4,
            size=img_size - 8,
            color=(1.0, 1.0, 1.0),
            alpha=1.0,
        )

    data = surf.get_data()
    stride = surf.get_stride()
    for i, g in enumerate(required_glyphs):
        bright_count = 0
        for y in range(img_size):
            for x in range(i * img_size, (i + 1) * img_size):
                idx = y * stride + x * 4
                if data[idx] > 50:
                    bright_count += 1
        assert (
            bright_count > 20
        ), f"Glyph {g.name} failed to render sufficient pixels: {bright_count}"
        print(f"Test 2 (Required glyph {g.name:8s}): Success ({bright_count} pixels)")

    full_surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 32 * len(Glyph), 32)
    full_cr = cairo.Context(full_surf)
    for i, g in enumerate(Glyph):
        render_icon(full_cr, g, x=i * 32 + 4, y=4, size=24)
    print(f"Test 3 (All {len(Glyph)} glyphs in enum): Success")

    bat_surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 64, 64)
    bat_cr = cairo.Context(bat_surf)
    render_battery(bat_cr, 8, 8, 48, level=0.5, color=(0.2, 0.8, 0.4))
    print("Test 4 (Dynamic battery level): Success")

    icon_obj = Icon(Glyph.Sparkle, size=32, color=(1.0, 0.8, 0.0), alpha=0.9)
    icon_obj.render(bat_cr, 0, 0)
    print("Test 5 (Icon OOP class): Success")

    print("\nAll icon vector iconography tests executed successfully with 0 errors!")
