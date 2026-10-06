#!/usr/bin/env python3

from __future__ import annotations

import math
import random
from typing import Optional, Sequence

import cairo

BASS_BANDS: int = 3
STAR_COUNT: int = 44
STAR_SEED: int = 7
STAR_MARGIN: float = 10.0
STAR_TOP: float = 6.0
FLOOR_OVER_EDGE: float = 16.0
SKY_BIAS: float = 1.4
SMALLEST_STAR: float = 0.55
STAR_SPREAD: float = 0.65
DIMMEST_STAR: float = 0.25
STAR_BRIGHTENING: float = 0.4
SLOWEST_TWINKLE: float = 0.7
TWINKLE_SPREAD: float = 1.7
TWINKLE_DEPTH: float = 0.5
STAR_CALM: float = 0.45
STAR_LEVEL_GAIN: float = 0.75
HALO_FROM: float = 0.55
HALO_REACH: float = 3.5
HALO_GAIN: float = 0.65

ONSET_JUMP: float = 0.22
BASS_AVG_SEC: float = 0.5
METEOR_WAKEFULNESS: float = 0.4
SHORTEST_METEOR_REST: float = 6.0
LONGEST_METEOR_REST: float = 14.0
METEOR_SEC: float = 0.6
METEOR_SPEED: float = 240.0
METEOR_TAIL: float = 44.0
METEOR_SLOPE: float = 0.35

class Star:
    __slots__ = ("x", "y", "radius", "glow", "band", "speed", "phase")

    def __init__(self, x: float, y: float, radius: float, glow: float, band: int, speed: float, phase: float) -> None:
        self.x = x
        self.y = y
        self.radius = radius
        self.glow = glow
        self.band = band
        self.speed = speed
        self.phase = phase

def _scatter() -> list[Star]:
    rnd = random.Random(STAR_SEED)
    stars: list[Star] = []
    for _ in range(STAR_COUNT):
        size = rnd.random()
        stars.append(
            Star(
                x=rnd.random(),
                y=math.pow(rnd.random(), SKY_BIAS),
                radius=SMALLEST_STAR + STAR_SPREAD * size * size * size,
                glow=DIMMEST_STAR + STAR_BRIGHTENING * size,
                band=BASS_BANDS + rnd.randint(0, 12),
                speed=SLOWEST_TWINKLE + TWINKLE_SPREAD * rnd.random(),
                phase=2.0 * math.pi * rnd.random(),
            )
        )
    return stars

_STARS: list[Star] = _scatter()

class StarField:

    def __init__(self) -> None:
        self._random = random.Random()
        self._time: float = 0.0
        self._activity: float = 0.0
        self._bass_avg: float = 0.0
        self._meteor_rest: float = SHORTEST_METEOR_REST
        self._meteor_age: float = -1.0
        self._meteor_start_x: float = 0.0
        self._meteor_start_y: float = 0.0
        self._meteor_dx: float = 1.0
        self._meteor_dy: float = 0.35

    def tick(self, levels: Optional[Sequence[float]], playing: bool, dt: float) -> bool:
        self._time += dt
        target_act = 1.0 if playing else 0.0
        wake_rate = 1.0 - math.exp(-dt / (0.8 if playing else 1.2))
        self._activity += (target_act - self._activity) * wake_rate
        if self._activity < 0.002:
            self._activity = 0.0

        bass = 0.0
        if levels and len(levels) >= BASS_BANDS:
            bass = sum(levels[:BASS_BANDS]) / float(BASS_BANDS)

        onset = (bass - self._bass_avg) > ONSET_JUMP
        self._bass_avg += (bass - self._bass_avg) * (1.0 - math.exp(-dt / BASS_AVG_SEC))
        self._meteor_rest -= dt

        if self._meteor_age < 0 and onset and self._meteor_rest <= 0 and self._activity > METEOR_WAKEFULNESS:
            self._launch(380.0, 180.0)

        if self._meteor_age >= 0:
            self._meteor_age += dt
            if self._meteor_age >= METEOR_SEC:
                self._meteor_age = -1.0

        return playing or self._activity > 0.01 or self._meteor_age >= 0

    def _launch(self, w: float, h: float) -> None:
        self._meteor_age = 0.0
        self._meteor_rest = SHORTEST_METEOR_REST + self._random.random() * (LONGEST_METEOR_REST - SHORTEST_METEOR_REST)
        self._meteor_start_x = w * (0.5 + 0.6 * (self._random.random() - 0.5))
        self._meteor_start_y = STAR_TOP + (h - FLOOR_OVER_EDGE - STAR_TOP) * 0.35 * self._random.random()
        heading_x = 1.0 if self._meteor_start_x < w / 2.0 else -1.0
        heading_y = METEOR_SLOPE
        hyp = math.hypot(heading_x, heading_y)
        self._meteor_dx = heading_x / hyp
        self._meteor_dy = heading_y / hyp

    def render(self, cr: cairo.Context, px: float, py: float, pw: float, ph: float, alpha: float, levels: Optional[Sequence[float]] = None) -> None:
        if alpha <= 0.001 or pw <= 0 or ph <= 0:
            return

        cr.save()
        width = pw - 2.0 * STAR_MARGIN
        height = max(10.0, ph - FLOOR_OVER_EDGE - STAR_TOP)

        # Draw stars
        for st in _STARS:
            twinkle = 0.5 + 0.5 * math.sin(self._time * st.speed + st.phase)
            lvl = levels[st.band] if (levels and st.band < len(levels)) else 0.0
            flare = max(0.0, min(1.0, (lvl - STAR_CALM) / (1.0 - STAR_CALM)))
            glow = min(1.0, st.glow * (1.0 - TWINKLE_DEPTH * self._activity * twinkle) + STAR_LEVEL_GAIN * flare) * alpha

            cx = px + STAR_MARGIN + width * st.x
            cy = py + STAR_TOP + height * st.y

            if glow > 0.01:
                cr.set_source_rgba(1.0, 1.0, 1.0, glow)
                cr.arc(cx, cy, st.radius, 0, 2.0 * math.pi)
                cr.fill()

                halo = (glow - HALO_FROM) / (1.0 - HALO_FROM)
                if halo > 0.0:
                    halo_r = st.radius * HALO_REACH
                    pat = cairo.RadialGradient(cx, cy, 0.0, cx, cy, halo_r)
                    pat.add_color_stop_rgba(0.0, 1.0, 1.0, 1.0, halo * HALO_GAIN * 0.6)
                    pat.add_color_stop_rgba(1.0, 1.0, 1.0, 1.0, 0.0)
                    cr.set_source(pat)
                    cr.arc(cx, cy, halo_r, 0, 2.0 * math.pi)
                    cr.fill()

        # Draw meteor
        if self._meteor_age >= 0:
            fade = math.sin(math.pi * self._meteor_age / METEOR_SEC) * alpha
            hx = px + self._meteor_start_x + self._meteor_dx * METEOR_SPEED * self._meteor_age
            hy = py + self._meteor_start_y + self._meteor_dy * METEOR_SPEED * self._meteor_age
            tx = hx - self._meteor_dx * METEOR_TAIL * (0.4 + 0.6 * fade)
            ty = hy - self._meteor_dy * METEOR_TAIL * (0.4 + 0.6 * fade)

            pat = cairo.LinearGradient(tx, ty, hx, hy)
            pat.add_color_stop_rgba(0.0, 1.0, 1.0, 1.0, 0.0)
            pat.add_color_stop_rgba(1.0, 1.0, 1.0, 1.0, fade)

            cr.set_source(pat)
            cr.set_line_width(1.3)
            cr.set_line_cap(cairo.LINE_CAP_ROUND)
            cr.move_to(tx, ty)
            cr.line_to(hx, hy)
            cr.stroke()

            cr.set_source_rgba(1.0, 1.0, 1.0, fade)
            cr.arc(hx, hy, 1.2, 0, 2.0 * math.pi)
            cr.fill()

        cr.restore()
