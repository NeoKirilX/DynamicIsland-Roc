#!/usr/bin/env python3

from __future__ import annotations
import math
import time
import cairo

STEP_TIME: float = 0.420
PAIR_WIDTH: float = 23.0
PAIR_HEIGHT: float = 15.0
SPACING: float = 11.0
TAIL_X: float = 1.0
TIP_X: float = 11.0
VANISHED: float = 0.02

class Skip:
    def __init__(self, back: bool = False) -> None:
        self.back: bool = back
        self._target_turn: int = 0
        self._from_turn: float = 0.0
        self._start_time: float = 0.0
        self.turn: float = 0.0
        self.is_animating: bool = False

    def play(self) -> None:
        self._target_turn += 1
        self._from_turn = self.turn
        self._start_time = time.monotonic()
        self.is_animating = True

    def advance(self, dt: float) -> bool:
        if not self.is_animating:
            return False
        elapsed = time.monotonic() - self._start_time
        t = min(1.0, elapsed / STEP_TIME)
        # Cubic ease out
        ease = 1.0 - (1.0 - t) ** 3
        self.turn = self._from_turn + (self._target_turn - self._from_turn) * ease
        if t >= 1.0:
            self.turn = float(self._target_turn)
            self._target_turn = 0
            self._from_turn = 0.0
            self.turn = 0.0
            self.is_animating = False
        return True

    def render(
        self,
        cr: cairo.Context,
        cx: float,
        cy: float,
        color: tuple[float, float, float] = (1.0, 1.0, 1.0),
        alpha: float = 1.0,
    ) -> None:
        cr.save()
        cr.translate(cx - PAIR_WIDTH / 2.0, cy - PAIR_HEIGHT / 2.0)
        turn = self.turn - math.floor(self.turn)

        if self.back:
            cr.translate(PAIR_WIDTH, 0.0)
            cr.scale(-1.0, 1.0)

        self._draw_triangle(cr, 0.0, turn, TAIL_X, color, alpha)
        self._draw_triangle(cr, SPACING * turn, 1.0, TAIL_X, color, alpha)
        self._draw_triangle(cr, SPACING, 1.0 - turn, TIP_X, color, alpha)

        cr.restore()

    def _draw_triangle(
        self,
        cr: cairo.Context,
        x: float,
        size: float,
        pivot_x: float,
        color: tuple[float, float, float],
        alpha: float,
    ) -> None:
        if size < VANISHED:
            return
        cr.save()
        cr.translate(x, 0.0)

        # Scale about pivot_x, PAIR_HEIGHT / 2.0
        piv_y = PAIR_HEIGHT / 2.0
        cr.translate(pivot_x, piv_y)
        cr.scale(size, size)
        cr.translate(-pivot_x, -piv_y)

        a = min(size * 2.0, 1.0) * alpha
        cr.set_source_rgba(color[0], color[1], color[2], a)
        cr.set_line_width(2.0)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)

        # Triangle path: M1,1 L11,7.5 L1,14 Z
        cr.new_path()
        cr.move_to(1.0, 1.0)
        cr.line_to(11.0, 7.5)
        cr.line_to(1.0, 14.0)
        cr.close_path()
        cr.fill_preserve()
        cr.stroke()

        cr.restore()
