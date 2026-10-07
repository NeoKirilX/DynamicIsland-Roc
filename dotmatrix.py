#!/usr/bin/env python3

from __future__ import annotations

import math
from typing import Optional, Sequence

import cairo

DEFAULT_ROWS: int = 4
DEFAULT_COLUMN_PITCH: float = 8.0
DEFAULT_ROW_PITCH: float = 6.5
DEFAULT_DOT_RADIUS: float = 1.5
DEFAULT_BOTTOM_MARGIN: float = 8.0
DEFAULT_SIDE_INSET: float = 14.0

UNLIT_OPACITY: float = 0.08
LIT_OPACITY: float = 0.85
HEAD_WHITENESS: float = 0.5


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
    ) -> None:
        if alpha <= 0.001 or pw <= 0 or ph <= 0:
            return

        compact = ph <= 46.0

        if compact:
            rows = 2
            col_pitch = 6.5
            row_pitch = 4.2
            dot_rad = 1.15
            bottom_margin = 4.0
            side_inset = 22.0
        else:
            rows = DEFAULT_ROWS
            col_pitch = DEFAULT_COLUMN_PITCH
            row_pitch = DEFAULT_ROW_PITCH
            dot_rad = DEFAULT_DOT_RADIUS
            bottom_margin = DEFAULT_BOTTOM_MARGIN
            side_inset = DEFAULT_SIDE_INSET

        cr.save()
        width = pw - 2.0 * side_inset
        n_cols = max(4, int(width / col_pitch))
        step_x = width / float(n_cols)

        base_y = py + ph - bottom_margin

        # Unlit dots background
        cr.set_source_rgba(1.0, 1.0, 1.0, (UNLIT_OPACITY * 0.7 if compact else UNLIT_OPACITY) * alpha)
        for c in range(n_cols):
            cx = px + side_inset + (c + 0.5) * step_x
            for r in range(rows):
                cy = base_y - r * row_pitch
                cr.arc(cx, cy, dot_rad, 0, 2.0 * math.pi)
                cr.fill()

        if levels and len(levels) > 0:
            n_levels = len(levels)
            for c in range(n_cols):
                share = c / float(n_cols - 1) if n_cols > 1 else 0.5
                # Center-focused bass mapping (middle is bass, sides are treble)
                dist_from_center = abs(share - 0.5) * 2.0
                band_idx = int(round(dist_from_center * (n_levels - 1)))
                lvl = levels[band_idx] if band_idx < n_levels else 0.0
                lit = lvl * rows * 1.25

                cx = px + side_inset + (c + 0.5) * step_x
                for r in range(rows):
                    diff = lit - r
                    if diff <= 0.01:
                        break
                    cy = base_y - r * row_pitch
                    on = max(0.0, min(1.0, diff))
                    head = on * (1.0 - max(0.0, min(1.0, diff - 1.0)))

                    eff_lit = LIT_OPACITY * 0.8 if compact else LIT_OPACITY
                    cr.set_source_rgba(color[0], color[1], color[2], eff_lit * on * alpha)
                    cr.arc(cx, cy, dot_rad, 0, 2.0 * math.pi)
                    cr.fill()

                    if head > 0.01:
                        cr.set_source_rgba(1.0, 1.0, 1.0, HEAD_WHITENESS * head * alpha)
                        cr.arc(cx, cy, dot_rad, 0, 2.0 * math.pi)
                        cr.fill()

        cr.restore()
