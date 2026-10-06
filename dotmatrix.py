#!/usr/bin/env python3

from __future__ import annotations

import math
from typing import Optional, Sequence

import cairo

ROWS: int = 4
COLUMN_PITCH: float = 8.0
ROW_PITCH: float = 6.5
DOT_RADIUS: float = 1.5
BOTTOM_MARGIN: float = 8.0
SIDE_INSET: float = 14.0
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

        cr.save()
        width = pw - 2.0 * SIDE_INSET
        n_cols = max(4, int(width / COLUMN_PITCH))
        step_x = width / float(n_cols)

        base_y = py + ph - BOTTOM_MARGIN

        # Unlit dots background
        cr.set_source_rgba(1.0, 1.0, 1.0, UNLIT_OPACITY * alpha)
        for c in range(n_cols):
            cx = px + SIDE_INSET + (c + 0.5) * step_x
            for r in range(ROWS):
                cy = base_y - r * ROW_PITCH
                cr.arc(cx, cy, DOT_RADIUS, 0, 2.0 * math.pi)
                cr.fill()

        if levels and len(levels) > 0:
            n_levels = len(levels)
            for c in range(n_cols):
                share = c / float(n_cols - 1) if n_cols > 1 else 0.5
                # Center-focused bass mapping (middle is bass, sides are treble)
                dist_from_center = abs(share - 0.5) * 2.0
                band_idx = int(round(dist_from_center * (n_levels - 1)))
                lvl = levels[band_idx] if band_idx < n_levels else 0.0
                lit = lvl * ROWS * 1.15

                cx = px + SIDE_INSET + (c + 0.5) * step_x
                for r in range(ROWS):
                    diff = lit - r
                    if diff <= 0.01:
                        break
                    cy = base_y - r * ROW_PITCH
                    on = max(0.0, min(1.0, diff))
                    head = on * (1.0 - max(0.0, min(1.0, diff - 1.0)))

                    cr.set_source_rgba(color[0], color[1], color[2], LIT_OPACITY * on * alpha)
                    cr.arc(cx, cy, DOT_RADIUS, 0, 2.0 * math.pi)
                    cr.fill()

                    if head > 0.01:
                        cr.set_source_rgba(1.0, 1.0, 1.0, HEAD_WHITENESS * head * alpha)
                        cr.arc(cx, cy, DOT_RADIUS, 0, 2.0 * math.pi)
                        cr.fill()

        cr.restore()
