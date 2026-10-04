from __future__ import annotations

import math
from typing import Sequence, Tuple

import cairo

ROW_HEIGHT = 18.0
GAP_HEIGHT = 4.0
BAR_HEIGHT = 10.0
BAND_WIDTH = 170.0
SLANT_FACTOR = 0.35
PASS_SEC = 1.5
REST_SEC = 0.6
CYCLE_SEC = 2.1

ROWS_CONFIG: list[Tuple[float, float]] = [
    (0.58, 0.55),
    (0.84, 1.00),
    (0.42, 0.55),
]

def _mix(a: Tuple[float, float, float], b: Tuple[float, float, float], t: float) -> Tuple[float, float, float]:
    return (
        a[0] + (b[0] - a[0]) * t,
        a[1] + (b[1] - a[1]) * t,
        a[2] + (b[2] - a[2]) * t,
    )

def _lift(c: Tuple[float, float, float]) -> Tuple[float, float, float]:
    white = (1.0, 1.0, 1.0)
    return _mix(c, white, 0.35)

def _draw_rounded_rect(cr: cairo.Context, x: float, y: float, w: float, h: float, r: float) -> None:
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2.0, 0.0)
    cr.arc(x + w - r, y + h - r, r, 0.0, math.pi / 2.0)
    cr.arc(x + r, y + h - r, r, math.pi / 2.0, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3.0 * math.pi / 2.0)
    cr.close_path()

class Shimmer:
    def __init__(self) -> None:
        self._running: bool = False
        self._elapsed: float = 0.0
        self._opacity: float = 0.0
        self._target_opacity: float = 0.0
        self._color_a: Tuple[float, float, float] = (1.0, 1.0, 1.0)
        self._color_b: Tuple[float, float, float] = (1.0, 1.0, 1.0)

    @property
    def is_visible(self) -> bool:
        return self._opacity > 0.001

    @property
    def opacity(self) -> float:
        return self._opacity

    def tint(self, colors: Sequence[Tuple[float, float, float]]) -> None:
        if not colors:
            self._color_a = (1.0, 1.0, 1.0)
            self._color_b = (1.0, 1.0, 1.0)
            return
        self._color_a = _lift(colors[0])
        idx = min(1, len(colors) - 1)
        self._color_b = _lift(colors[idx])

    def run(self, on: bool) -> None:
        if on == self._running and self._target_opacity == (1.0 if on else 0.0):
            return
        self._running = on
        self._target_opacity = 1.0 if on else 0.0
        if on and self._opacity <= 0.001:
            self._elapsed = 0.0

    def tick(self, dt: float) -> bool:
        dt = max(0.0, float(dt))
        animating = False

        if self._running:
            self._elapsed += dt
            animating = True

        if self._opacity != self._target_opacity:
            speed = 1.0 / (0.30 if self._target_opacity > 0.5 else 0.20)
            if self._target_opacity > self._opacity:
                self._opacity = min(self._target_opacity, self._opacity + dt * speed)
            else:
                self._opacity = max(self._target_opacity, self._opacity - dt * speed)
                if self._opacity <= 0.0:
                    self._running = False
            animating = True

        return animating

    def render(
        self,
        cr: cairo.Context,
        x: float,
        y: float,
        w: float,
        h: float,
        alpha: float = 1.0,
    ) -> None:
        eff_alpha = alpha * self._opacity
        if eff_alpha <= 0.001 or w <= 0.0 or h <= 0.0:
            return

        cr.save()
        total_content_h = 3.0 * ROW_HEIGHT + 2.0 * GAP_HEIGHT
        top = y + (h - total_content_h) / 2.0
        r = BAR_HEIGHT / 2.0

        for share, row_alpha in ROWS_CONFIG:
            cr.save()
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.10 * row_alpha * eff_alpha)
            bar_w = round(w * share)
            _draw_rounded_rect(cr, x, top + (ROW_HEIGHT - BAR_HEIGHT) / 2.0, bar_w, BAR_HEIGHT, r)
            cr.fill()
            cr.restore()
            top += ROW_HEIGHT + GAP_HEIGHT

        phase = self._elapsed % CYCLE_SEC if self._elapsed >= CYCLE_SEC else self._elapsed
        from_x = -BAND_WIDTH - 3.0 * (ROW_HEIGHT + GAP_HEIGHT) * SLANT_FACTOR
        to_x = w + BAND_WIDTH

        if phase <= PASS_SEC:
            t = phase / PASS_SEC
            eased = 0.5 - 0.5 * math.cos(math.pi * t)
            move_x = from_x + (to_x - from_x) * eased
        else:
            move_x = to_x

        if move_x < to_x:
            cr.save()
            top = y + (h - total_content_h) / 2.0
            for share, row_alpha in ROWS_CONFIG:
                bar_w = round(w * share)
                _draw_rounded_rect(cr, x, top + (ROW_HEIGHT - BAR_HEIGHT) / 2.0, bar_w, BAR_HEIGHT, r)
                top += ROW_HEIGHT + GAP_HEIGHT
            cr.clip()

            sheen_start_x = x + move_x
            sheen_start_y = y
            sheen_end_x = sheen_start_x + BAND_WIDTH
            sheen_end_y = sheen_start_y + BAND_WIDTH * SLANT_FACTOR

            pat = cairo.LinearGradient(sheen_start_x, sheen_start_y, sheen_end_x, sheen_end_y)
            ca = self._color_a
            cb = self._color_b
            crest = _mix(ca, (1.0, 1.0, 1.0), 0.6)

            pat.add_color_stop_rgba(0.0, 1.0, 1.0, 1.0, 0.0)
            pat.add_color_stop_rgba(0.3, ca[0], ca[1], ca[2], 0.45 * eff_alpha)
            pat.add_color_stop_rgba(0.5, crest[0], crest[1], crest[2], 0.85 * eff_alpha)
            pat.add_color_stop_rgba(0.7, cb[0], cb[1], cb[2], 0.45 * eff_alpha)
            pat.add_color_stop_rgba(1.0, 1.0, 1.0, 1.0, 0.0)

            cr.set_source(pat)
            cr.paint()
            cr.restore()

        cr.restore()
