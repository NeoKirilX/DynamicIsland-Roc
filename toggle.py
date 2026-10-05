#!/usr/bin/env python3

from __future__ import annotations

import math
import cairo

class Toggle:
    DEFAULT_WIDTH: float = 46.0
    DEFAULT_HEIGHT: float = 24.0
    KNOB_INSET: float = 2.0
    KNOB_ASPECT: float = 1.0
    DURATION: float = 0.24

    PRESSED_WIDER: float = 0.20
    PRESSED_TALLER: float = 0.32
    STRETCH_SPEED: float = 9.0
    STRETCH_WIDER: float = 0.32
    STRETCH_FLATTER: float = 0.10
    LENS_ZOOM: float = 0.22
    GLASS_SHOWN: float = 0.01
    RIM_THICKNESS: float = 0.8

    COLOR_OFF: tuple[float, float, float] = (0.224, 0.224, 0.239)  # 0x39, 0x39, 0x3D
    COLOR_ON: tuple[float, float, float] = (0.188, 0.820, 0.345)   # 0x30, 0xD1, 0x58

    def __init__(self, initial_state: bool = False) -> None:
        self._on: bool = bool(initial_state)
        self._progress: float = 1.0 if self._on else 0.0
        self._from_progress: float = self._progress
        self._target_progress: float = self._progress
        self._elapsed: float = 0.0
        self._animating: bool = False
        self._velocity: float = 0.0
        self._last_progress: float = self._progress

        self._press: float = 0.0
        self._target_press: float = 0.0
        self._held: bool = False

    @property
    def on(self) -> bool:
        return self._on

    @property
    def is_on(self) -> bool:
        return self._on

    @property
    def progress(self) -> float:
        return self._progress

    @property
    def is_animating(self) -> bool:
        return self._animating or abs(self._press - self._target_press) > 1e-3

    def set_pressed(self, pressed: bool) -> None:
        self._held = bool(pressed)
        self._target_press = 1.0 if pressed else 0.0

    def set_state(self, on: bool, animate: bool = True) -> None:
        on = bool(on)
        self._on = on
        target = 1.0 if on else 0.0

        if not animate:
            self._progress = target
            self._from_progress = target
            self._target_progress = target
            self._animating = False
            self._velocity = 0.0
            return

        if abs(self._progress - target) < 1e-4 and not self._animating:
            return

        self._from_progress = self._progress
        self._target_progress = target
        self._elapsed = 0.0
        self._animating = True

    def toggle(self, animate: bool = True) -> None:
        self.set_state(not self._on, animate=animate)

    def tick(self, dt: float) -> bool:
        dt = max(1e-4, float(dt))
        moved = False

        # Advance press animation
        if abs(self._press - self._target_press) > 1e-3:
            speed = 12.0 if self._target_press > self._press else 8.0
            diff = self._target_press - self._press
            self._press += diff * min(1.0, dt * speed)
            moved = True
        else:
            self._press = self._target_press

        # Advance progress animation
        if self._animating:
            self._elapsed += dt
            t = min(1.0, self._elapsed / self.DURATION) if self.DURATION > 0.0 else 1.0
            # Cubic ease out
            ease = 1.0 - (1.0 - t) ** 3
            prev_prog = self._progress
            self._progress = self._from_progress + (self._target_progress - self._from_progress) * ease
            self._velocity = (self._progress - prev_prog) / dt
            moved = True

            if self._elapsed >= self.DURATION:
                self._progress = self._target_progress
                self._animating = False
                self._velocity = 0.0
        else:
            self._velocity = 0.0

        return moved

    def render(
        self,
        cr: cairo.Context,
        x: float,
        y: float,
        w: float = DEFAULT_WIDTH,
        h: float = DEFAULT_HEIGHT,
    ) -> None:
        if w <= 0.0 or h <= 0.0:
            return

        share = max(0.0, min(1.0, self._progress))
        press = max(0.0, min(1.0, self._press))

        # Speed stretch factor
        stretch = min(1.0, abs(self._velocity) / self.STRETCH_SPEED)

        rest_h = h - self.KNOB_INSET * 2.0
        rest_w = rest_h * self.KNOB_ASPECT
        knob_w = rest_w * (1.0 + self.PRESSED_WIDER * press) * (1.0 + self.STRETCH_WIDER * stretch)
        knob_h = rest_h * (1.0 + self.PRESSED_TALLER * press) * (1.0 - self.STRETCH_FLATTER * stretch)

        travel = max(1.0, w - self.KNOB_INSET * 2.0 - rest_w)
        knob_cx = x + self.KNOB_INSET + rest_w / 2.0 + travel * share
        knob_cy = y + h / 2.0
        knob_x = knob_cx - knob_w / 2.0
        knob_y = knob_cy - knob_h / 2.0

        track_r = self.COLOR_OFF[0] + (self.COLOR_ON[0] - self.COLOR_OFF[0]) * share
        track_g = self.COLOR_OFF[1] + (self.COLOR_ON[1] - self.COLOR_OFF[1]) * share
        track_b = self.COLOR_OFF[2] + (self.COLOR_ON[2] - self.COLOR_OFF[2]) * share

        cr.save()

        # 1. Track pill background
        track_radius = h / 2.0
        _draw_pill(cr, x, y, w, h, track_radius)
        cr.set_source_rgb(track_r, track_g, track_b)
        cr.fill()

        # 2. Knob shadow
        shadow_spread = 0.6 + 1.5 * press
        shadow_drop = 0.6 + 1.0 * press
        shadow_alpha = 0.10 + 0.05 * press
        for layer in range(1, 4):
            spread = shadow_spread * layer
            _draw_pill(
                cr,
                knob_x - spread,
                knob_y - spread + shadow_drop,
                knob_w + spread * 2.0,
                knob_h + spread * 2.0,
                (knob_h + spread * 2.0) / 2.0,
            )
            cr.set_source_rgba(0.0, 0.0, 0.0, shadow_alpha / layer)
            cr.fill()

        # 3. Knob body
        knob_radius = knob_h / 2.0
        is_glass = press > self.GLASS_SHOWN

        if not is_glass:
            _draw_pill(cr, knob_x, knob_y, knob_w, knob_h, knob_radius)
            cr.set_source_rgb(1.0, 1.0, 1.0)
            cr.fill()
        else:
            # Glass lens effect: track through lens magnified
            cr.save()
            _draw_pill(cr, knob_x, knob_y, knob_w, knob_h, knob_radius)
            cr.clip()

            # Magnified track through glass
            zoom = 1.0 + self.LENS_ZOOM * press
            cr.save()
            cr.translate(knob_cx, knob_cy)
            cr.scale(zoom, zoom * 1.08)
            cr.translate(-knob_cx, -knob_cy)
            _draw_pill(cr, x, y, w, h, track_radius)
            cr.set_source_rgb(track_r, track_g, track_b)
            cr.fill()
            cr.restore()

            # Glass white tint clearing
            white_tint = 1.0 - 0.85 * press
            cr.set_source_rgba(1.0, 1.0, 1.0, white_tint)
            cr.paint()

            # Specular vertical highlight
            grad = cairo.LinearGradient(knob_x, knob_y, knob_x, knob_y + knob_h)
            grad.add_color_stop_rgba(0.0, 1.0, 1.0, 1.0, 0.35 * press)
            grad.add_color_stop_rgba(0.45, 1.0, 1.0, 1.0, 0.0)
            grad.add_color_stop_rgba(1.0, 1.0, 1.0, 1.0, 0.12 * press)
            cr.set_source(grad)
            cr.paint()
            cr.restore()

            # Glass rim stroke
            _draw_pill(
                cr,
                knob_x + self.RIM_THICKNESS / 2.0,
                knob_y + self.RIM_THICKNESS / 2.0,
                knob_w - self.RIM_THICKNESS,
                knob_h - self.RIM_THICKNESS,
                (knob_h - self.RIM_THICKNESS) / 2.0,
            )
            rim_grad = cairo.LinearGradient(knob_x, knob_y, knob_x, knob_y + knob_h)
            rim_grad.add_color_stop_rgba(0.0, 1.0, 1.0, 1.0, 0.85 * press)
            rim_grad.add_color_stop_rgba(0.5, 1.0, 1.0, 1.0, 0.25 * press)
            rim_grad.add_color_stop_rgba(1.0, 1.0, 1.0, 1.0, 0.60 * press)
            cr.set_source(rim_grad)
            cr.set_line_width(self.RIM_THICKNESS)
            cr.stroke()

        cr.restore()

def _draw_pill(cr: cairo.Context, x: float, y: float, w: float, h: float, r: float) -> None:
    r = min(r, h / 2.0, w / 2.0)
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2.0, 0.0)
    cr.arc(x + w - r, y + h - r, r, 0.0, math.pi / 2.0)
    cr.arc(x + r, y + h - r, r, math.pi / 2.0, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3.0 * math.pi / 2.0)
    cr.close_path()
