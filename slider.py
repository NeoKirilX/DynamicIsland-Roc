#!/usr/bin/env python3

from __future__ import annotations

import math
from typing import Any, Callable, Optional

import cairo

try:
    from settings import Settings
except ImportError:
    Settings = None

try:
    from spring import Spring
except ImportError:
    class Spring:
        def __init__(self, value: float, stiffness: float = 520.0, damping: float = 30.0) -> None:
            self.value = float(value)
            self.target = float(value)
            self.velocity = 0.0
            self.stiffness = float(stiffness)
            self.damping = float(damping)

        def tune(self, stiffness: float, damping: float) -> None:
            self.stiffness = float(stiffness)
            self.damping = float(damping)

        def advance(self, dt: float) -> bool:
            diff = self.target - self.value
            if abs(diff) < 0.002 and abs(self.velocity) < 0.02:
                self.value = self.target
                self.velocity = 0.0
                return False
            accel = self.stiffness * diff - self.damping * self.velocity
            self.velocity += accel * dt
            self.value += self.velocity * dt
            return True


# ─────────────────────────────────────────────────────────────────────────────
# Visual Layout Constants:
# Тонкая линия (часть белая, часть серая) + Стеклянная капсула-бегунок (Toggle.cs)
# ─────────────────────────────────────────────────────────────────────────────

SLIDER_WIDTH: float = 64.0
SLIDER_HEIGHT: float = 24.0
SLIDER_TRACK_H: float = 4.0

KNOB_REST_H: float = 16.0
KNOB_ASPECT: float = 26.0 / 18.0

SLIDER_VAL_W: float = 42.0
SLIDER_GAP: float = 10.0
SLIDER_RIGHT_MARGIN: float = 16.0


def get_slider_layout(px: float, pw: float) -> tuple[float, float]:
    """Returns (track_x, track_w) positioned relative to the right edge of the row."""
    track_x = px + pw - SLIDER_RIGHT_MARGIN - SLIDER_VAL_W - SLIDER_GAP - SLIDER_WIDTH
    return track_x, SLIDER_WIDTH


def _draw_pill(cr: cairo.Context, x: float, y: float, w: float, h: float, r: float) -> None:
    rad = max(0.0, min(r, h / 2.0, w / 2.0))
    if rad <= 0.0:
        cr.rectangle(x, y, w, h)
        return
    cr.new_sub_path()
    cr.arc(x + w - rad, y + rad, rad, -math.pi / 2.0, 0.0)
    cr.arc(x + w - rad, y + h - rad, rad, 0.0, math.pi / 2.0)
    cr.arc(x + rad, y + h - rad, rad, math.pi / 2.0, math.pi)
    cr.arc(x + rad, y + rad, rad, math.pi, 3.0 * math.pi / 2.0)
    cr.close_path()


class Slider:
    """
    Тонкая линия (белая/серая) + стеклянная капсула-бегунок с физикой Toggle.cs:
      • Линия под капсулой тонкая (4px): левая часть белая, правая часть серая (#33FFFFFF)
      • Бегунок — стеклянная капсула: в покое 23×16px, при зажатии раздувается в линзу
      • Под капсулой сквозь стекло увеличивается тонкая линия с размытием и бликом
      • Пружины (1400, 70) во время драга, (520, 30) при отпускании с резиновым сопротивлением
    """

    PRESSED_WIDER: float = 0.20
    PRESSED_TALLER: float = 0.32
    DRAG_OVERREACH: float = 0.18
    STRETCH_SPEED: float = 9.0
    STRETCH_WIDER: float = 0.32
    STRETCH_FLATTER: float = 0.10
    LENS_ZOOM: float = 0.22
    LENS_ZOOM_TALLER: float = 1.08
    GLASS_CLEARING: float = 0.85
    GLASS_SHOWN: float = 0.01
    RIM_THICKNESS: float = 0.8

    SHADOW_LAYERS: int = 3
    SHADOW_SPREAD: float = 0.6
    PRESSED_SHADOW_SPREAD: float = 1.4
    SHADOW_DROP: float = 0.6
    PRESSED_SHADOW_DROP: float = 1.0
    SHADOW_ALPHA: float = 0.12
    PRESSED_SHADOW_ALPHA: float = 0.06

    def __init__(
        self,
        key: str,
        min_val: float | Callable[[Any], float],
        max_val: float | Callable[[Any], float],
        step: float,
        getter: Callable[[], float],
        setter: Callable[[float], None],
        unit: str = "",
        formatter: Optional[Callable[[float], str]] = None,
        on_change: Optional[Callable[[Any, float], None]] = None,
    ) -> None:
        self.key = key
        self.min_val = min_val
        self.max_val = max_val
        self.step = step
        self.getter = getter
        self.setter = setter
        self.unit = unit
        self.formatter = formatter
        self.on_change = on_change

        self._share = Spring(0.0, 520.0, 30.0)
        self._press = Spring(0.0, 900.0, 38.0)
        self._dragging: bool = False
        self._down_x: float = 0.0
        self._down_share: float = 0.0

    def get_min(self, context: Any = None) -> float:
        if callable(self.min_val):
            return float(self.min_val(context))
        return float(self.min_val)

    def get_max(self, context: Any = None) -> float:
        if callable(self.max_val):
            return float(self.max_val(context))
        return float(self.max_val)

    def get_val(self) -> float:
        return float(self.getter())

    def format_val(self, val: Optional[float] = None, context: Any = None) -> str:
        v = self.get_val() if val is None else float(val)
        if self.formatter is not None:
            return self.formatter(v)
        if self.step >= 1.0:
            return f"{int(round(v))}{self.unit}"
        return f"{v:.1f}{self.unit}"

    def calc_fraction(self, context: Any = None) -> float:
        min_v = self.get_min(context)
        max_v = self.get_max(context)
        cur_v = self.get_val()
        if max_v <= min_v:
            return 0.0
        return max(0.0, min(1.0, (cur_v - min_v) / (max_v - min_v)))

    def sync_to_settings(self, context: Any = None, snap: bool = False) -> None:
        frac = self.calc_fraction(context)
        if snap or not self._dragging:
            self._share.target = frac
            if snap:
                self._share.value = frac
                self._share.velocity = 0.0

    @staticmethod
    def _resist(beyond: float) -> float:
        return beyond / (1.0 + beyond / Slider.DRAG_OVERREACH)

    @staticmethod
    def _overreach(share: float) -> float:
        if share < 0.0:
            return -Slider._resist(-share)
        if share > 1.0:
            return 1.0 + Slider._resist(share - 1.0)
        return share

    def on_down(self, x: float, track_x: float, track_w: float, context: Any = None) -> None:
        self.sync_to_settings(context, snap=True)
        self._dragging = True
        self._down_x = x
        self._share.tune(1400.0, 70.0)
        self._press.tune(900.0, 38.0)
        self._press.target = 1.0

        w = max(1.0, float(track_w))
        frac = max(0.0, min(1.0, (x - track_x) / w))
        self._share.target = frac
        self._down_share = frac

    def on_move(self, x: float, track_x: float, track_w: float, context: Any = None) -> None:
        if not self._dragging:
            return
        w = max(1.0, float(track_w))
        dx = x - self._down_x
        self._share.target = self._overreach(self._down_share + dx / w)

    def on_up(self, window: Any = None) -> None:
        if not self._dragging:
            return
        self._dragging = False
        self._share.tune(520.0, 30.0)
        self._press.tune(420.0, 17.0)
        self._press.target = 0.0

        clamped = max(0.0, min(1.0, self._share.target))
        self._share.target = clamped
        self.apply_fraction(clamped, window)

    def apply_fraction(self, frac: float, window: Any) -> float:
        min_v = self.get_min(window)
        max_v = self.get_max(window)
        raw = min_v + frac * (max_v - min_v)
        step = self.step
        if step > 0:
            rounded = round((raw - min_v) / step) * step + min_v
        else:
            rounded = raw
        final_val = max(min_v, min(max_v, rounded))
        self.setter(final_val)
        if self.on_change is not None and window is not None:
            self.on_change(window, final_val)
        return final_val

    def apply_step(self, nudge: int, window: Any) -> float:
        cur_v = self.get_val()
        min_v = self.get_min(window)
        max_v = self.get_max(window)
        new_v = max(min_v, min(max_v, cur_v + nudge * self.step))
        self.setter(new_v)
        if self.on_change is not None and window is not None:
            self.on_change(window, new_v)
        self.sync_to_settings(window)
        return new_v

    def tick(self, dt: float) -> bool:
        dt = max(1e-4, float(dt))
        return self._share.advance(dt) | self._press.advance(dt)

    def render(
        self,
        cr: cairo.Context,
        x: float,
        y: float,
        w: float = SLIDER_WIDTH,
        h: float = SLIDER_HEIGHT,
        accent_color: tuple[float, float, float] = (1.0, 1.0, 1.0),
        alpha: float = 1.0,
    ) -> None:
        if w <= 0.0 or h <= 0.0 or alpha <= 0.001:
            return

        track_h = SLIDER_TRACK_H
        track_y = y + (h - track_h) / 2.0
        track_r = track_h / 2.0

        share_val = self._share.value
        clamped_share = max(0.0, min(1.0, share_val))
        press = max(0.0, self._press.value)
        stretch = min(1.0, abs(self._share.velocity) / self.STRETCH_SPEED)

        # ─────────────────────────────────────────────────────────────────────
        # 1. Тонкая полоса под капсулой: неактивная правая часть СЕРАЯ (#33FFFFFF)
        # ─────────────────────────────────────────────────────────────────────
        _draw_pill(cr, x, track_y, w, track_h, track_r)
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.22 * alpha)
        cr.fill()

        # Центр бегунка-капсулы
        knob_cx = x + w * share_val
        knob_cy = y + h / 2.0

        # ─────────────────────────────────────────────────────────────────────
        # 2. Тонкая полоса под капсулой: активная левая часть БЕЛАЯ
        # ─────────────────────────────────────────────────────────────────────
        fill_w = max(0.0, min(w, knob_cx - x))
        if fill_w > 0.5:
            _draw_pill(cr, x, track_y, fill_w, track_h, track_r)
            cr.set_source_rgba(1.0, 1.0, 1.0, 1.0 * alpha)
            cr.fill()

        # ─────────────────────────────────────────────────────────────────────
        # 3. Стеклянная капсула-бегунок (Glass Capsule Puck) поверх полосы
        # ─────────────────────────────────────────────────────────────────────
        rest_h = KNOB_REST_H
        rest_w = rest_h * KNOB_ASPECT

        knob_w = rest_w * (1.0 + self.PRESSED_WIDER * press) * (1.0 + self.STRETCH_WIDER * stretch)
        knob_h = rest_h * (1.0 + self.PRESSED_TALLER * press) * (1.0 - self.STRETCH_FLATTER * stretch)
        knob_x = knob_cx - knob_w / 2.0
        knob_y = knob_cy - knob_h / 2.0
        knob_r = knob_h / 2.0

        is_glass = press > self.GLASS_SHOWN

        cr.save()

        # Layer A: Многослойная мягкая тень стеклянной капсулы
        shadow_spread = self.SHADOW_SPREAD + self.PRESSED_SHADOW_SPREAD * press
        shadow_drop = self.SHADOW_DROP + self.PRESSED_SHADOW_DROP * press
        shadow_alpha = (self.SHADOW_ALPHA + self.PRESSED_SHADOW_ALPHA * press) * alpha

        for layer in range(1, self.SHADOW_LAYERS + 1):
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

        # Layer B: Тело стеклянной капсулы
        if not is_glass:
            # Спокойное состояние: чистая белая стеклянная капсула с легким верхним бликом
            _draw_pill(cr, knob_x, knob_y, knob_w, knob_h, knob_r)
            puck_grad = cairo.LinearGradient(knob_x, knob_y, knob_x, knob_y + knob_h)
            puck_grad.add_color_stop_rgba(0.0, 1.0, 1.0, 1.0, 0.99 * alpha)
            puck_grad.add_color_stop_rgba(0.5, 0.96, 0.97, 1.0, 0.95 * alpha)
            puck_grad.add_color_stop_rgba(1.0, 0.90, 0.92, 0.96, 0.90 * alpha)
            cr.set_source(puck_grad)
            cr.fill()

            # Верхний блик
            _draw_pill(cr, knob_x, knob_y, knob_w, knob_h, knob_r)
            cr.clip()
            sheen = cairo.LinearGradient(knob_x, knob_y, knob_x, knob_y + knob_h * 0.45)
            sheen.add_color_stop_rgba(0.0, 1.0, 1.0, 1.0, 0.55 * alpha)
            sheen.add_color_stop_rgba(1.0, 1.0, 1.0, 1.0, 0.0)
            cr.set_source(sheen)
            cr.rectangle(knob_x, knob_y, knob_w, knob_h * 0.5)
            cr.fill()
            cr.reset_clip()

            # Тонкий стеклянный кант
            _draw_pill(cr, knob_x + 0.35, knob_y + 0.35, knob_w - 0.7, knob_h - 0.7, (knob_h - 0.7) / 2.0)
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.65 * alpha)
            cr.set_line_width(0.7)
            cr.stroke()
        else:
            # Состояние зажатия: стеклянная линза Toggle.cs, сквозь которую увеличена тонкая полоса
            cr.save()
            _draw_pill(cr, knob_x, knob_y, knob_w, knob_h, knob_r)
            cr.clip()

            # Увеличение сквозь линзу
            zoom = 1.0 + self.LENS_ZOOM * press
            cr.save()
            cr.translate(knob_cx, knob_cy)
            cr.scale(zoom, zoom * self.LENS_ZOOM_TALLER)
            cr.translate(-knob_cx, -knob_cy)

            # Серая полоса сквозь линзу
            _draw_pill(cr, x, track_y, w, track_h, track_r)
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.22 * alpha)
            cr.fill()

            # Белая полоса сквозь линзу
            if fill_w > 0.5:
                _draw_pill(cr, x, track_y, fill_w, track_h, track_r)
                cr.set_source_rgba(1.0, 1.0, 1.0, 1.0 * alpha)
                cr.fill()
            cr.restore()

            # Белое осветление стекла
            white_tint = (1.0 - self.GLASS_CLEARING * press) * alpha
            cr.set_source_rgba(1.0, 1.0, 1.0, white_tint)
            cr.paint()

            # Вертикальный блик
            grad = cairo.LinearGradient(knob_x, knob_y, knob_x, knob_y + knob_h)
            grad.add_color_stop_rgba(0.0, 1.0, 1.0, 1.0, 0.35 * press * alpha)
            grad.add_color_stop_rgba(0.45, 1.0, 1.0, 1.0, 0.0)
            grad.add_color_stop_rgba(1.0, 1.0, 1.0, 1.0, 0.12 * press * alpha)
            cr.set_source(grad)
            cr.paint()
            cr.restore()

            # Стеклянная окантовка (Rim)
            _draw_pill(
                cr,
                knob_x + self.RIM_THICKNESS / 2.0,
                knob_y + self.RIM_THICKNESS / 2.0,
                knob_w - self.RIM_THICKNESS,
                knob_h - self.RIM_THICKNESS,
                (knob_h - self.RIM_THICKNESS) / 2.0,
            )
            rim_grad = cairo.LinearGradient(knob_x, knob_y, knob_x, knob_y + knob_h)
            rim_grad.add_color_stop_rgba(0.0, 1.0, 1.0, 1.0, 0.85 * press * alpha)
            rim_grad.add_color_stop_rgba(0.5, 1.0, 1.0, 1.0, 0.25 * press * alpha)
            rim_grad.add_color_stop_rgba(1.0, 1.0, 1.0, 1.0, 0.60 * press * alpha)
            cr.set_source(rim_grad)
            cr.set_line_width(self.RIM_THICKNESS)
            cr.stroke()

        cr.restore()


# ─────────────────────────────────────────────────────────────────────────────
# Dynamic Screen Bounds
# ─────────────────────────────────────────────────────────────────────────────

def _screen_max_y(ctx: Any) -> float:
    if ctx is not None and hasattr(ctx, "win_height"):
        return max(200.0, float(ctx.win_height) // 2.0)
    return 540.0


def _screen_min_x(ctx: Any) -> float:
    if ctx is not None and hasattr(ctx, "win_width"):
        return -max(300.0, float(ctx.win_width) // 2.0)
    return -960.0


def _screen_max_x(ctx: Any) -> float:
    if ctx is not None and hasattr(ctx, "win_width"):
        return max(300.0, float(ctx.win_width) // 2.0)
    return 960.0


# ─────────────────────────────────────────────────────────────────────────────
# Pre-defined Sliders Registry
# ─────────────────────────────────────────────────────────────────────────────

SLIDERS: dict[str, Slider] = {
    # ── Оформление (View.LOOK) ─────────────────────────────────────────────────
    "scale": Slider(
        key="scale",
        min_val=75.0,
        max_val=130.0,
        step=1.0,
        getter=lambda: Settings.scale,
        setter=lambda v: setattr(Settings, "scale", int(v)),
        unit="%",
        on_change=lambda win, v: win.set_scale(int(v)),
    ),
    "pos_y": Slider(
        key="pos_y",
        min_val=0.0,
        max_val=_screen_max_y,
        step=1.0,
        getter=lambda: Settings.pos_y,
        setter=lambda v: setattr(Settings, "pos_y", int(v)),
        unit=" px",
        on_change=lambda win, v: win.set_pos_y(int(v)),
    ),
    "pos_x": Slider(
        key="pos_x",
        min_val=_screen_min_x,
        max_val=_screen_max_x,
        step=1.0,
        getter=lambda: Settings.pos_x,
        setter=lambda v: setattr(Settings, "pos_x", int(v)),
        formatter=lambda v: f"+{int(v)} px" if v > 0 else f"{int(v)} px",
        on_change=lambda win, v: win.set_pos_x(int(v)),
    ),
    "radius": Slider(
        key="radius",
        min_val=0.0,
        max_val=100.0,
        step=1.0,
        getter=lambda: Settings.radius,
        setter=lambda v: setattr(Settings, "radius", int(v)),
        unit="%",
        on_change=lambda win, v: win.set_radius(int(v)),
    ),
    "height": Slider(
        key="height",
        min_val=0.0,
        max_val=16.0,
        step=1.0,
        getter=lambda: Settings.height,
        setter=lambda v: setattr(Settings, "height", int(v)),
        unit=" px",
        on_change=lambda win, v: win.set_height(int(v)),
    ),
    "text_scale": Slider(
        key="text_scale",
        min_val=75.0,
        max_val=130.0,
        step=1.0,
        getter=lambda: Settings.text_scale,
        setter=lambda v: setattr(Settings, "text_scale", int(v)),
        unit="%",
        on_change=lambda win, v: win.set_text_scale(int(v)),
    ),
    "glass": Slider(
        key="glass",
        min_val=20.0,
        max_val=100.0,
        step=1.0,
        getter=lambda: Settings.glass,
        setter=lambda v: setattr(Settings, "glass", int(v)),
        unit="%",
        on_change=lambda win, v: win.set_glass(int(v)),
    ),

    # ── Анимация текста (View.TEXT_ANIM) ──────────────────────────────────────
    "lyric_anim_speed": Slider(
        key="lyric_anim_speed",
        min_val=50.0,
        max_val=200.0,
        step=5.0,
        getter=lambda: Settings.lyric_anim_speed,
        setter=lambda v: setattr(Settings, "lyric_anim_speed", int(v)),
        unit="%",
        on_change=lambda win, v: win.area.queue_draw(),
    ),
    "lyric_anim_height": Slider(
        key="lyric_anim_height",
        min_val=15.0,
        max_val=80.0,
        step=1.0,
        getter=lambda: Settings.lyric_anim_height,
        setter=lambda v: setattr(Settings, "lyric_anim_height", int(v)),
        unit=" px",
        on_change=lambda win, v: win.area.queue_draw(),
    ),
    "lyric_anim_stagger": Slider(
        key="lyric_anim_stagger",
        min_val=15.0,
        max_val=50.0,
        step=1.0,
        getter=lambda: Settings.lyric_anim_stagger,
        setter=lambda v: setattr(Settings, "lyric_anim_stagger", int(v)),
        unit=" мс",
        on_change=lambda win, v: win.area.queue_draw(),
    ),
    "lyric_lead_sec": Slider(
        key="lyric_lead_sec",
        min_val=0.0,
        max_val=9.0,
        step=1.0,
        getter=lambda: Settings.lyric_lead_sec,
        setter=lambda v: setattr(Settings, "lyric_lead_sec", int(v)),
        formatter=lambda v: "Выкл" if v <= 0 else (f"{int(v)} сек" if v >= 2 else "2 сек"),
        on_change=lambda win, v: win.area.queue_draw(),
    ),

    # ── Комбо повторов (View.COMBO) ───────────────────────────────────────────
    "combo_min_repeats": Slider(
        key="combo_min_repeats",
        min_val=2.0,
        max_val=5.0,
        step=1.0,
        getter=lambda: Settings.combo_min_repeats,
        setter=lambda v: setattr(Settings, "combo_min_repeats", int(v)),
        unit="",
        on_change=lambda win, v: (setattr(win, "_compact_lines_cache", None), win.area.queue_draw()),
    ),
    "combo_min_word_len": Slider(
        key="combo_min_word_len",
        min_val=2.0,
        max_val=5.0,
        step=1.0,
        getter=lambda: Settings.combo_min_word_len,
        setter=lambda v: setattr(Settings, "combo_min_word_len", int(v)),
        unit="",
        on_change=lambda win, v: (setattr(win, "_compact_lines_cache", None), win.area.queue_draw()),
    ),

    # ── Эквалайзер (View.EQUALIZER) ───────────────────────────────────────────
    "compact_eq_bars": Slider(
        key="compact_eq_bars",
        min_val=3.0,
        max_val=5.0,
        step=1.0,
        getter=lambda: Settings.compact_eq_bars,
        setter=lambda v: setattr(Settings, "compact_eq_bars", int(v)),
        unit="",
        on_change=lambda win, v: (setattr(win._eq_small, "bars", int(v)), win.area.queue_draw()),
    ),
    "eq_bars": Slider(
        key="eq_bars",
        min_val=5.0,
        max_val=9.0,
        step=1.0,
        getter=lambda: Settings.eq_bars,
        setter=lambda v: setattr(Settings, "eq_bars", int(v)),
        unit="",
        on_change=lambda win, v: (setattr(win._eq_big, "bars", int(v)), win.area.queue_draw()),
    ),
    "eq_sensitivity": Slider(
        key="eq_sensitivity",
        min_val=75.0,
        max_val=150.0,
        step=5.0,
        getter=lambda: Settings.eq_sensitivity,
        setter=lambda v: setattr(Settings, "eq_sensitivity", int(v)),
        unit="%",
        on_change=lambda win, v: win.area.queue_draw(),
    ),
    "matrix_rows": Slider(
        key="matrix_rows",
        min_val=8.0,
        max_val=16.0,
        step=1.0,
        getter=lambda: Settings.matrix_rows,
        setter=lambda v: setattr(Settings, "matrix_rows", int(v)),
        unit="",
        on_change=lambda win, v: win.area.queue_draw(),
    ),
    "matrix_fade_strength": Slider(
        key="matrix_fade_strength",
        min_val=0.0,
        max_val=100.0,
        step=5.0,
        getter=lambda: Settings.matrix_fade_strength,
        setter=lambda v: setattr(Settings, "matrix_fade_strength", int(v)),
        formatter=lambda v: "Выкл" if v < 20 else f"{int(v)}%",
        on_change=lambda win, v: win.area.queue_draw(),
    ),
    "matrix_opacity": Slider(
        key="matrix_opacity",
        min_val=70.0,
        max_val=100.0,
        step=5.0,
        getter=lambda: Settings.matrix_opacity,
        setter=lambda v: setattr(Settings, "matrix_opacity", int(v)),
        unit="%",
        on_change=lambda win, v: win.area.queue_draw(),
    ),
}
