#!/usr/bin/env python3

from __future__ import annotations

import math
from typing import Optional, Sequence

import cairo

try:
    from settings import Settings, DENSITY_SPARSE, DENSITY_DENSE
except ImportError:
    Settings = None
    DENSITY_SPARSE = "sparse"
    DENSITY_DENSE = "dense"

DEFAULT_ROWS: int = 12
DEFAULT_COLUMN_PITCH: float = 8.0
DEFAULT_ROW_PITCH: float = 6.5
DEFAULT_DOT_RADIUS: float = 1.5
DEFAULT_BOTTOM_MARGIN: float = 7.0
DEFAULT_SIDE_INSET: float = 6.0

UNLIT_OPACITY: float = 0.12
LIT_OPACITY: float = 0.95
HEAD_WHITENESS: float = 0.65


def _is_inside_rounded_rect(
    cx: float,
    cy: float,
    px: float,
    py: float,
    pw: float,
    ph: float,
    rad: float,
    clearance: float = 2.0,
) -> bool:
    if cx < px + clearance or cx > px + pw - clearance:
        return False
    if cy < py + clearance or cy > py + ph - clearance:
        return False
    r_eff = rad - clearance
    if r_eff <= 0.0:
        return True

    # Check the 4 corner curves
    if cx < px + rad and cy < py + rad:
        dx, dy = cx - (px + rad), cy - (py + rad)
        return (dx * dx + dy * dy) <= (r_eff * r_eff)
    if cx > px + pw - rad and cy < py + rad:
        dx, dy = cx - (px + pw - rad), cy - (py + rad)
        return (dx * dx + dy * dy) <= (r_eff * r_eff)
    if cx < px + rad and cy > py + ph - rad:
        dx, dy = cx - (px + rad), cy - (py + ph - rad)
        return (dx * dx + dy * dy) <= (r_eff * r_eff)
    if cx > px + pw - rad and cy > py + ph - rad:
        dx, dy = cx - (px + pw - rad), cy - (py + ph - rad)
        return (dx * dx + dy * dy) <= (r_eff * r_eff)

    return True


class DotMatrix:

    def __init__(self) -> None:
        pass

    def render(
        self,
        cr: cairo.Context,
        px: float,
        py: float,
        pw: float,
        ph: float,
        alpha: float,
        levels: Optional[Sequence[float]] = None,
        color: tuple[float, float, float] = (1.0, 1.0, 1.0),
        radius: float = 28.0,
    ) -> None:
        if alpha <= 0.001 or pw <= 0 or ph <= 0:
            return

        compact = ph <= 46.0

        if not compact and Settings is not None:
            rows = Settings.matrix_rows
            density = Settings.matrix_density
            if density == DENSITY_SPARSE:
                col_pitch = 10.0
            elif density == DENSITY_DENSE:
                col_pitch = 6.0
            else:
                col_pitch = DEFAULT_COLUMN_PITCH
            fade_strength = (Settings.matrix_fade_strength / 100.0) if Settings is not None else 0.70
            fade_enabled = fade_strength > 0.001
            user_opacity = Settings.matrix_opacity / 100.0
            row_pitch = DEFAULT_ROW_PITCH
            dot_rad = DEFAULT_DOT_RADIUS
            bottom_margin = DEFAULT_BOTTOM_MARGIN
            side_inset = DEFAULT_SIDE_INSET
        elif compact:
            rows = 2
            col_pitch = 6.5
            row_pitch = 4.2
            dot_rad = 1.15
            bottom_margin = 4.0
            side_inset = 22.0
            fade_enabled = False
            fade_strength = 0.0
            user_opacity = 0.8
        else:
            rows = DEFAULT_ROWS
            col_pitch = DEFAULT_COLUMN_PITCH
            row_pitch = DEFAULT_ROW_PITCH
            dot_rad = DEFAULT_DOT_RADIUS
            bottom_margin = DEFAULT_BOTTOM_MARGIN
            side_inset = DEFAULT_SIDE_INSET
            fade_enabled = True
            fade_strength = 0.70
            user_opacity = 0.95

        cr.save()

        # Clip to the island's rounded geometry
        rad = max(4.0, min(radius, pw / 2.0, ph / 2.0))
        cr.new_sub_path()
        cr.arc(px + pw - rad, py + rad, rad, -math.pi / 2, 0)
        cr.arc(px + pw - rad, py + ph - rad, rad, 0, math.pi / 2)
        cr.arc(px + rad, py + ph - rad, rad, math.pi / 2, math.pi)
        cr.arc(px + rad, py + rad, rad, math.pi, 3 * math.pi / 2)
        cr.close_path()
        cr.clip()

        width = pw - 2.0 * side_inset
        n_cols = max(4, int(width / col_pitch) + 2)
        step_x = width / float(n_cols)

        base_y = py + ph - bottom_margin

        # Unlit dots background with vertical opacity fade
        base_unlit = (UNLIT_OPACITY * 0.7 if compact else UNLIT_OPACITY) * alpha * user_opacity
        for c in range(n_cols):
            cx = px + side_inset + (c + 0.5) * step_x
            for r in range(rows):
                cy = base_y - r * row_pitch
                if not _is_inside_rounded_rect(cx, cy, px, py, pw, ph, rad, clearance=dot_rad + 1.0):
                    continue
                fade = (1.0 - fade_strength * (float(r) / max(1.0, float(rows - 1)))) if (fade_enabled and rows > 1) else 1.0
                cr.set_source_rgba(1.0, 1.0, 1.0, base_unlit * fade)
                cr.arc(cx, cy, dot_rad, 0, 2.0 * math.pi)
                cr.fill()

        if levels and len(levels) > 0:
            n_levels = len(levels)
            middle = (n_cols - 1) / 2.0
            for c in range(n_cols):
                share = abs(c - middle) / middle if middle > 0 else 0.5
                # Center-focused bass mapping with smooth interpolation across frequency bands
                at = share * (n_levels - 1)
                low = int(at)
                part = at - low
                if low + 1 < n_levels:
                    lvl = (1.0 - part) * levels[low] + part * levels[low + 1]
                else:
                    lvl = levels[low] if low < n_levels else 0.0

                # Dynamic bounce (0 to rows) matching mishakotov LitReach = 1.15
                lit = max(0.0, min(float(rows), (lvl ** 1.05) * rows * 1.15))

                cx = px + side_inset + (c + 0.5) * step_x
                for r in range(rows):
                    diff = lit - r
                    if diff <= 0.01:
                        break
                    cy = base_y - r * row_pitch
                    if not _is_inside_rounded_rect(cx, cy, px, py, pw, ph, rad, clearance=dot_rad + 1.0):
                        continue
                    on = max(0.0, min(1.0, diff))
                    head = on * (1.0 - max(0.0, min(1.0, diff - 1.0)))

                    fade = (1.0 - fade_strength * (float(r) / max(1.0, float(rows - 1)))) if (fade_enabled and rows > 1) else 1.0
                    eff_lit = (LIT_OPACITY * 0.8 if compact else LIT_OPACITY) * user_opacity
                    cr.set_source_rgba(color[0], color[1], color[2], eff_lit * on * alpha * fade)
                    cr.arc(cx, cy, dot_rad, 0, 2.0 * math.pi)
                    cr.fill()

                    if head > 0.01:
                        cr.set_source_rgba(1.0, 1.0, 1.0, HEAD_WHITENESS * head * alpha * fade)
                        cr.arc(cx, cy, dot_rad, 0, 2.0 * math.pi)
                        cr.fill()

        cr.restore()
