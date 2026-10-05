
from __future__ import annotations

import math
from typing import Any

import cairo

RIM: float = 1.0
TEAR: float = 7.5
HOLD: float = 0.5
HANDLE: float = 2.4

DEFAULT_RIM_COLOR: tuple[float, float, float, float] = (
    1.0, 1.0, 1.0, 0x20 / 255.0,
)
TINTED_ALPHA: float = 0x8C / 255.0


def _chroma(r: float, g: float, b: float) -> tuple[float, float, float]:
    max_c = max(r, g, b, 0.01)
    cr_r = r / max_c
    cr_g = g / max_c
    cr_b = b / max_c
    lum_weight = 0.2126 * cr_r + 0.7152 * cr_g + 0.0722 * cr_b
    lum_scale = min(1.0, 0.65 / math.sqrt(max(0.2, lum_weight)))
    return cr_r * lum_scale, cr_g * lum_scale, cr_b * lum_scale


class Goo:

    def __init__(
        self,
        rim_color: tuple[float, float, float, float] = DEFAULT_RIM_COLOR,
    ) -> None:
        self.pill: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
        self.radius: float = 0.0
        self.bubble: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)

        self.rim_color: tuple[float, float, float, float] = rim_color
        self._target_rim_color: tuple[float, float, float, float] = rim_color
        self._tint_start_color: tuple[float, float, float, float] = rim_color
        self._tint_duration: float = 0.0
        self._tint_elapsed: float = 0.0

        is_default = (rim_color == DEFAULT_RIM_COLOR)
        init_amount = 0.0 if is_default else 1.0
        self._tint_amount: float = init_amount
        self._tint_amount_from: float = init_amount
        self._tint_amount_to: float = init_amount
        self._glass: float = 0.70

        self._liquid: float = 1.0
        self._liquid_from: float = 1.0
        self._liquid_to: float = 1.0
        self._liquid_elapsed: float = 1.0
        self._liquid_duration: float = 0.45

        self._glass_enabled: float = 1.0
        self._glass_enabled_from: float = 1.0
        self._glass_enabled_to: float = 1.0
        self._glass_enabled_elapsed: float = 1.0
        self._glass_enabled_duration: float = 0.35
        self.notch_factor: float = 0.0
        self.ear_size: float = 14.0

    def shape(
        self,
        pill: tuple[float, float, float, float],
        radius: float,
        bubble: tuple[float, float, float, float] | None = None,
        notch_factor: float = 0.0,
        ear_size: float = 14.0,
    ) -> None:
        self.pill = (
            float(pill[0]),
            float(pill[1]),
            float(pill[2]),
            float(pill[3]),
        )
        self.radius = float(radius)
        self.notch_factor = float(notch_factor)
        self.ear_size = float(ear_size)
        if bubble is not None:
            self.bubble = (
                float(bubble[0]),
                float(bubble[1]),
                float(bubble[2]),
                float(bubble[3]),
            )
        else:
            self.bubble = (0.0, 0.0, 0.0, 0.0)

    def tint(
        self,
        color: tuple[float, float, float] | None,
        duration_sec: float = 0.0,
    ) -> None:
        if color is not None:
            r, g, b = color
            r = r / 255.0 if r > 1.0 else float(r)
            g = g / 255.0 if g > 1.0 else float(g)
            b = b / 255.0 if b > 1.0 else float(b)
            to_color = (r, g, b, TINTED_ALPHA)
            target_amount = 1.0
        else:
            to_color = DEFAULT_RIM_COLOR
            target_amount = 0.0

        duration = max(0.0, float(duration_sec))
        if duration <= 0.0:
            self.rim_color = to_color
            self._target_rim_color = to_color
            self._tint_start_color = to_color
            self._tint_duration = 0.0
            self._tint_elapsed = 0.0
            self._tint_amount = target_amount
            self._tint_amount_from = target_amount
            self._tint_amount_to = target_amount
        else:
            self._tint_start_color = self.rim_color
            self._target_rim_color = to_color
            self._tint_duration = duration
            self._tint_elapsed = 0.0
            self._tint_amount_from = self._tint_amount
            self._tint_amount_to = target_amount

    def set_glass(self, factor: float) -> None:
        self._glass = max(0.1, min(1.5, float(factor)))

    def set_mode(self, mode: str, duration_sec: float = 0.35) -> None:
        is_glass = (mode != "none")
        is_liquid = (mode == "liquid")
        self.material(is_liquid, duration_sec)

        target = 1.0 if is_glass else 0.0
        duration = max(0.0, float(duration_sec))
        if duration <= 0.0:
            self._glass_enabled = target
            self._glass_enabled_from = target
            self._glass_enabled_to = target
            self._glass_enabled_elapsed = 1.0
            self._glass_enabled_duration = 0.0
            return
        if abs(target - self._glass_enabled_to) < 0.001:
            return
        self._glass_enabled_from = self._glass_enabled
        self._glass_enabled_to = target
        self._glass_enabled_elapsed = 0.0
        self._glass_enabled_duration = duration

    def material(self, liquid: bool, duration_sec: float = 0.0) -> None:
        target = 1.0 if liquid else 0.0
        duration = max(0.0, float(duration_sec))
        if duration <= 0.0:
            self._liquid = target
            self._liquid_from = target
            self._liquid_to = target
            self._liquid_elapsed = 1.0
            self._liquid_duration = 0.0
            return
        if abs(target - self._liquid_to) < 0.001:
            return
        self._liquid_from = self._liquid
        self._liquid_to = target
        self._liquid_elapsed = 0.0
        self._liquid_duration = duration

    def _advance_material(self, dt: float) -> None:
        if self._liquid_duration <= 0.0:
            self._liquid = self._liquid_to
        else:
            self._liquid_elapsed = min(1.0, self._liquid_elapsed + dt / self._liquid_duration)
            t = self._liquid_elapsed
            eased = t * t * (3.0 - 2.0 * t)
            self._liquid = self._liquid_from + (self._liquid_to - self._liquid_from) * eased

        if self._glass_enabled_duration <= 0.0:
            self._glass_enabled = self._glass_enabled_to
        else:
            self._glass_enabled_elapsed = min(1.0, self._glass_enabled_elapsed + dt / self._glass_enabled_duration)
            t = self._glass_enabled_elapsed
            eased = t * t * (3.0 - 2.0 * t)
            self._glass_enabled = self._glass_enabled_from + (self._glass_enabled_to - self._glass_enabled_from) * eased

    def neck(self) -> dict[str, Any] | None:
        if self._is_empty(self.pill) or self._is_empty(self.bubble):
            return None

        r1 = self.radius - RIM
        r2 = self.bubble[3] / 2.0 - RIM

        c1 = (
            self.pill[0] + self.pill[2] - self.radius,
            self.pill[1] + self.radius,
        )
        c2 = (
            self.bubble[0] + self.bubble[3] / 2.0,
            self.bubble[1] + self.bubble[3] / 2.0,
        )

        between_x = c2[0] - c1[0]
        between_y = c2[1] - c1[1]
        d = math.hypot(between_x, between_y)
        gap = d - r1 - r2

        if (
            r1 <= 0.0
            or r2 <= 0.0
            or between_x <= 0.0
            or d <= abs(r1 - r2)
            or gap >= TEAR
        ):
            return None

        u1 = 0.0
        u2 = 0.0
        if gap < 0.0:
            val1 = (r1 * r1 + d * d - r2 * r2) / (2.0 * r1 * d)
            u1 = math.acos(max(-1.0, min(1.0, val1)))
            val2 = (r2 * r2 + d * d - r1 * r1) / (2.0 * r2 * d)
            u2 = math.acos(max(-1.0, min(1.0, val2)))

        hold = HOLD * (1.0 - max(0.0, min(1.0, gap / TEAR)))
        axis = math.atan2(between_y, between_x)
        wide = math.acos(max(-1.0, min(1.0, (r1 - r2) / d)))

        a1 = axis + u1 + (wide - u1) * hold
        a2 = axis - u1 - (wide - u1) * hold
        a3 = axis + math.pi - u2 - (math.pi - u2 - wide) * hold
        a4 = axis - math.pi + u2 + (math.pi - u2 - wide) * hold

        def on(
            centre: tuple[float, float], angle: float, rad: float
        ) -> tuple[float, float]:
            return (
                centre[0] + rad * math.cos(angle),
                centre[1] + rad * math.sin(angle),
            )

        p1 = on(c1, a1, r1)
        p2 = on(c1, a2, r1)
        p3 = on(c2, a3, r2)
        p4 = on(c2, a4, r2)

        p1_p3_len = math.hypot(p1[0] - p3[0], p1[1] - p3[1])
        reach = min(hold * HANDLE, p1_p3_len / (r1 + r2)) * min(
            1.0, 2.0 * d / (r1 + r2)
        )
        quarter = math.pi / 2.0

        h_top_p2 = on(p2, a2 + quarter, r1 * reach)
        h_top_p4 = on(p4, a4 - quarter, r2 * reach)

        h_bot_p3 = on(p3, a3 + quarter, r2 * reach)
        h_bot_p1 = on(p1, a1 - quarter, r1 * reach)

        return {
            "c1": c1,
            "c2": c2,
            "r1": r1,
            "r2": r2,
            "d": d,
            "gap": gap,
            "hold": hold,
            "axis": axis,
            "wide": wide,
            "u1": u1,
            "u2": u2,
            "a1": a1,
            "a2": a2,
            "a3": a3,
            "a4": a4,
            "p1": p1,
            "p2": p2,
            "p3": p3,
            "p4": p4,
            "reach": reach,
            "h_top_p2": h_top_p2,
            "h_top_p4": h_top_p4,
            "h_bot_p3": h_bot_p3,
            "h_bot_p1": h_bot_p1,
        }

    def render(self, cr: cairo.Context, dt: float = 0.0) -> None:
        if self._is_empty(self.pill):
            return

        self._advance_material(dt)

        if self._tint_elapsed < self._tint_duration:
            self._tint_elapsed += dt
            t = (
                min(1.0, self._tint_elapsed / self._tint_duration)
                if self._tint_duration > 0.0
                else 1.0
            )
            self.rim_color = (
                self._tint_start_color[0]
                + (self._target_rim_color[0] - self._tint_start_color[0]) * t,
                self._tint_start_color[1]
                + (self._target_rim_color[1] - self._tint_start_color[1]) * t,
                self._tint_start_color[2]
                + (self._target_rim_color[2] - self._tint_start_color[2]) * t,
                self._tint_start_color[3]
                + (self._target_rim_color[3] - self._tint_start_color[3]) * t,
            )
            t_amt = t * t * (3.0 - 2.0 * t)
            self._tint_amount = (
                self._tint_amount_from
                + (self._tint_amount_to - self._tint_amount_from) * t_amt
            )
        elif self._tint_duration > 0.0:
            self.rim_color = self._target_rim_color
            self._tint_amount = self._tint_amount_to

        px, py, pw, ph, pr = self._shrunk_rect(self.pill, self.radius)
        bubble_empty = self._is_empty(self.bubble)

        if bubble_empty:
            cr.new_path()
            self._add_rounded_rect_path(cr, px, py, pw, ph, pr, notch_factor=self.notch_factor, ear_size=self.ear_size)
            self._stroke_and_fill(cr)
            return

        bx, by, bw, bh, br = self._shrunk_rect(
            self.bubble, self.bubble[3] / 2.0
        )
        neck_info = self.neck()
        intersects = self._rects_intersect(self.pill, self.bubble)

        if neck_info is None and not intersects:
            cr.new_path()
            self._add_rounded_rect_path(cr, px, py, pw, ph, pr, notch_factor=self.notch_factor, ear_size=self.ear_size)
            self._stroke_and_fill(cr)

            cr.new_path()
            self._add_rounded_rect_path(cr, bx, by, bw, bh, br)
            self._stroke_and_fill(cr)
            return

        if neck_info is not None:
            cr.new_path()
            self._build_unified_path(
                cr, px, py, pw, ph, pr, bx, by, bw, bh, br, neck_info
            )
            self._stroke_and_fill(cr)
            return

        cr.new_path()
        self._add_rounded_rect_path(cr, px, py, pw, ph, pr, notch_factor=self.notch_factor, ear_size=self.ear_size)
        self._add_rounded_rect_path(cr, bx, by, bw, bh, br)
        self._stroke_and_fill(cr)

    def _build_unified_path(
        self,
        cr: cairo.Context,
        px: float,
        py: float,
        pw: float,
        ph: float,
        pr: float,
        bx: float,
        by: float,
        bw: float,
        bh: float,
        br: float,
        info: dict[str, Any],
    ) -> None:
        c1 = info["c1"]
        c2 = info["c2"]
        r1 = info["r1"]
        r2 = info["r2"]
        a1 = info["a1"]
        a2 = info["a2"]
        a3 = info["a3"]
        a4 = info["a4"]
        p4 = info["p4"]
        p1 = info["p1"]
        h_top_p2 = info["h_top_p2"]
        h_top_p4 = info["h_top_p4"]
        h_bot_p3 = info["h_bot_p3"]
        h_bot_p1 = info["h_bot_p1"]

        cr.new_sub_path()

        cr.move_to(px + pr, py)
        cr.line_to(px + pw - pr, py)

        cr.arc(c1[0], c1[1], r1, -math.pi / 2.0, a2)

        cr.curve_to(
            h_top_p2[0], h_top_p2[1], h_top_p4[0], h_top_p4[1], p4[0], p4[1]
        )

        cr.arc(c2[0], c2[1], r2, a4, -math.pi / 2.0)
        c2_r = (bx + bw - r2, by + r2)
        if bw > 2.0 * r2:
            cr.line_to(c2_r[0], by)
            cr.arc(c2_r[0], c2_r[1], r2, -math.pi / 2.0, math.pi / 2.0)
            cr.line_to(c2[0], by + bh)
        else:
            cr.arc(c2[0], c2[1], r2, -math.pi / 2.0, math.pi / 2.0)
        cr.arc(c2[0], c2[1], r2, math.pi / 2.0, a3)

        cr.curve_to(
            h_bot_p3[0], h_bot_p3[1], h_bot_p1[0], h_bot_p1[1], p1[0], p1[1]
        )

        cr.arc(c1[0], c1[1], r1, a1, math.pi / 2.0)

        if ph > 2.0 * pr:
            cr.line_to(px + pw - pr, py + ph)
        cr.line_to(px + pr, py + ph)
        cr.arc(px + pr, py + ph - pr, pr, math.pi / 2.0, math.pi)
        cr.line_to(px, py + pr)
        cr.arc(px + pr, py + pr, pr, math.pi, 3.0 * math.pi / 2.0)
        cr.close_path()

    def _bounds(self) -> tuple[float, float, float, float]:
        x0, y0, w0, h0 = self.pill
        x1, y1 = x0 + w0, y0 + h0
        if not self._is_empty(self.bubble):
            bx, by, bw, bh = self.bubble
            x0 = min(x0, bx)
            y0 = min(y0, by)
            x1 = max(x1, bx + bw)
            y1 = max(y1, by + bh)
        return x0, y0, x1, y1

    def _paint_liquid(
        self,
        cr: cairo.Context,
        strength: float,
        tint: tuple[float, float, float],
        tint_amount: float,
        path: cairo.Path | None,
        bounds: tuple[float, float, float, float],
    ) -> None:
        x0, y0, x1, y1 = bounds
        w = max(1.0, x1 - x0)
        h = max(1.0, y1 - y0)

        cr_r, cr_g, cr_b = _chroma(tint[0], tint[1], tint[2])
        amt = max(0.0, min(1.0, tint_amount))

        base_alpha = 0.92 + 0.04 * (1.0 - strength * 0.4)
        body = cairo.LinearGradient(0.0, y0, 0.0, y1)
        body.add_color_stop_rgba(
            0.0,
            0.024 + 0.065 * cr_r * amt,
            0.024 + 0.065 * cr_g * amt,
            0.030 + 0.065 * cr_b * amt,
            base_alpha,
        )
        body.add_color_stop_rgba(
            0.48,
            0.028 + 0.110 * cr_r * amt,
            0.028 + 0.110 * cr_g * amt,
            0.034 + 0.110 * cr_b * amt,
            base_alpha,
        )
        body.add_color_stop_rgba(
            1.0,
            0.020 + 0.075 * cr_r * amt,
            0.020 + 0.075 * cr_g * amt,
            0.026 + 0.075 * cr_b * amt,
            base_alpha,
        )
        cr.set_source(body)
        cr.rectangle(x0, y0, w, h)
        cr.fill()

        if amt > 0.001 and strength > 0.01:
            glow_rad = max(w * 0.6, h * 1.6)
            glow = cairo.RadialGradient(
                x0 + w * 0.5, y0 + h * 0.65, 0.0,
                x0 + w * 0.5, y0 + h * 0.65, glow_rad,
            )
            glow.add_color_stop_rgba(0.0, cr_r, cr_g, cr_b, 0.14 * amt * strength)
            glow.add_color_stop_rgba(0.55, cr_r, cr_g, cr_b, 0.04 * amt * strength)
            glow.add_color_stop_rgba(1.0, cr_r, cr_g, cr_b, 0.0)
            cr.set_source(glow)
            cr.rectangle(x0, y0, w, h)
            cr.fill()

        if amt > 0.001 and strength > 0.01:
            caustic = cairo.LinearGradient(0.0, y1, 0.0, y1 - h * 0.45)
            caustic.add_color_stop_rgba(0.0, cr_r, cr_g, cr_b, 0.22 * amt * strength)
            caustic.add_color_stop_rgba(0.38, cr_r, cr_g, cr_b, 0.07 * amt * strength)
            caustic.add_color_stop_rgba(1.0, cr_r, cr_g, cr_b, 0.0)
            cr.set_source(caustic)
            cr.rectangle(x0, y0, w, h)
            cr.fill()

        if strength > 0.01:
            sheen = cairo.LinearGradient(0.0, y0, 0.0, y1)
            sheen.add_color_stop_rgba(0.0, 1.0, 1.0, 1.0, 0.25 * strength)
            sheen.add_color_stop_rgba(0.10, 1.0, 1.0, 1.0, 0.10 * strength)
            sheen.add_color_stop_rgba(0.35, 1.0, 1.0, 1.0, 0.015 * strength)
            sheen.add_color_stop_rgba(0.70, 0.0, 0.0, 0.0, 0.0)
            sheen.add_color_stop_rgba(1.0, 0.0, 0.0, 0.0, 0.16 * strength)
            cr.set_source(sheen)
            cr.rectangle(x0, y0, w, h)
            cr.fill()

            glint_x = x0 + min(w * 0.25, 65.0)
            glint_y = y0 + h * 0.12
            glint_rad = max(w * 0.45, 80.0)
            spec = cairo.RadialGradient(glint_x, glint_y, 0.0, glint_x, glint_y, glint_rad)
            spec.add_color_stop_rgba(0.0, 1.0, 1.0, 1.0, 0.16 * strength)
            spec.add_color_stop_rgba(0.45, 1.0, 1.0, 1.0, 0.03 * strength)
            spec.add_color_stop_rgba(1.0, 1.0, 1.0, 1.0, 0.0)
            cr.set_source(spec)
            cr.rectangle(x0, y0, w, h)
            cr.fill()

        if path is not None and strength > 0.01:
            cr.append_path(path)
            inner = cairo.LinearGradient(0.0, y0, 0.0, y1)
            inner.add_color_stop_rgba(0.0, 1.0, 1.0, 1.0, 0.32 * strength)
            inner.add_color_stop_rgba(0.25, 1.0, 1.0, 1.0, 0.08 * strength)
            if amt > 0.001:
                inner.add_color_stop_rgba(0.70, cr_r, cr_g, cr_b, 0.12 * amt * strength)
                inner.add_color_stop_rgba(1.0, cr_r, cr_g, cr_b, 0.28 * amt * strength)
            else:
                inner.add_color_stop_rgba(1.0, 1.0, 1.0, 1.0, 0.04 * strength)
            cr.set_source(inner)
            cr.set_line_width(2.0)
            cr.stroke()

    def _stroke_and_fill(self, cr: cairo.Context) -> None:
        path = cr.copy_path()
        glass_factor = max(0.0, min(1.0, self._glass_enabled))

        if glass_factor <= 0.001:
            cr.set_source_rgba(0.0, 0.0, 0.0, 1.0)
            cr.fill()
            cr.append_path(path)
            cr.set_source_rgba(*self.rim_color)
            cr.set_line_width(2.0 * RIM)
            cr.set_line_join(cairo.LINE_JOIN_ROUND)
            cr.stroke()
            return

        liquid = self._liquid
        tint = (self.rim_color[0], self.rim_color[1], self.rim_color[2])
        amt = max(0.0, min(1.0, self._tint_amount)) * glass_factor

        ext = cr.path_extents()
        if ext[2] > ext[0] and ext[3] > ext[1]:
            bounds = ext
        else:
            bounds = self._bounds()

        if glass_factor < 0.999:
            cr.save()
            cr.set_source_rgba(0.0, 0.0, 0.0, 1.0)
            cr.fill_preserve()
            cr.restore()

        cr.save()
        cr.clip()
        strength = max(0.0, min(1.0, liquid)) * (0.6 + 0.4 * self._glass) * glass_factor
        self._paint_liquid(cr, strength, tint, amt, path, bounds)
        cr.restore()

        cr.append_path(path)
        x0, y0, x1, y1 = bounds
        rim_line_width = 1.6 * RIM
        cr.set_line_width(rim_line_width)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)

        if amt > 0.001 and glass_factor > 0.1:
            rim_grad = cairo.LinearGradient(0.0, y0, 0.0, y1)
            rim_top_a = min(1.0, self.rim_color[3] + 0.15 * liquid * glass_factor)
            rim_bot_a = min(1.0, self.rim_color[3] + 0.30 * liquid * glass_factor)
            rim_grad.add_color_stop_rgba(
                0.0,
                0.25 + 0.75 * tint[0],
                0.25 + 0.75 * tint[1],
                0.25 + 0.75 * tint[2],
                rim_top_a,
            )
            rim_grad.add_color_stop_rgba(
                1.0,
                tint[0],
                tint[1],
                tint[2],
                rim_bot_a,
            )
            cr.set_source(rim_grad)
        else:
            cr.set_source_rgba(*self.rim_color)
        cr.stroke()

    @staticmethod
    def _is_empty(rect: tuple[float, float, float, float] | None) -> bool:
        return rect is None or rect[2] <= 0.0 or rect[3] <= 0.0

    @staticmethod
    def _rects_intersect(
        r1: tuple[float, float, float, float],
        r2: tuple[float, float, float, float],
    ) -> bool:
        return not (
            r1[0] + r1[2] <= r2[0]
            or r2[0] + r2[2] <= r1[0]
            or r1[1] + r1[3] <= r2[1]
            or r2[1] + r2[3] <= r1[1]
        )

    @staticmethod
    def _shrunk_rect(
        rect: tuple[float, float, float, float],
        radius: float,
    ) -> tuple[float, float, float, float, float]:
        x, y, w, h = rect
        rx = min(RIM, w / 2.0)
        ry = min(RIM, h / 2.0)
        sx = x + rx
        sy = y + ry
        sw = max(0.0, w - 2.0 * rx)
        sh = max(0.0, h - 2.0 * ry)
        sr = max(0.0, radius - RIM)
        sr = min(sr, sw / 2.0, sh / 2.0) if sw > 0.0 and sh > 0.0 else 0.0
        return sx, sy, sw, sh, sr

    @staticmethod
    def _add_rounded_rect_path(
        cr: cairo.Context,
        x: float,
        y: float,
        w: float,
        h: float,
        r: float,
        notch_factor: float = 0.0,
        ear_size: float = 14.0,
    ) -> None:
        if w <= 0.0 or h <= 0.0:
            return
        r = min(r, w / 2.0, h / 2.0)
        nf = max(0.0, min(1.0, float(notch_factor)))

        if nf <= 0.01:
            cr.new_sub_path()
            cr.arc(x + w - r, y + r, r, -math.pi / 2.0, 0.0)
            cr.arc(x + w - r, y + h - r, r, 0.0, math.pi / 2.0)
            cr.arc(x + r, y + h - r, r, math.pi / 2.0, math.pi)
            cr.arc(x + r, y + r, r, math.pi, 3.0 * math.pi / 2.0)
            cr.close_path()
            return

        ear_w = ear_size * nf
        ear_h = min(h * 0.45, ear_size * nf)

        cr.new_sub_path()
        cr.move_to(x - ear_w, y)
        cr.line_to(x + w + ear_w, y)
        cr.curve_to(
            x + w + ear_w * 0.45, y,
            x + w, y + ear_h * 0.45,
            x + w, y + ear_h,
        )
        cr.line_to(x + w, y + h - r)
        cr.arc(x + w - r, y + h - r, r, 0.0, 0.5 * math.pi)
        cr.line_to(x + r, y + h)
        cr.arc(x + r, y + h - r, r, 0.5 * math.pi, math.pi)
        cr.line_to(x, y + ear_h)
        cr.curve_to(
            x, y + ear_h * 0.45,
            x - ear_w * 0.45, y,
            x - ear_w, y,
        )
        cr.close_path()

if __name__ == "__main__":
    goo = Goo()

    goo.shape((50, 20, 150, 34), 17)
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 400, 100)
    cr = cairo.Context(surface)
    goo.render(cr)
    print("Test 1 (Pill only): Success")

    goo.shape((50, 20, 150, 34), 17, (205, 20, 78, 34))
    neck = goo.neck()
    assert neck is not None, "Neck expected to form when gap < TEAR"
    print(
        f"Test 2 (Neck formed): gap={neck['gap']:.2f}, "
        f"hold={neck['hold']:.3f}, reach={neck['reach']:.3f}"
    )
    goo.render(cr)

    goo.shape((50, 20, 150, 34), 17, (206, 20, 78, 34))
    assert goo.neck() is None, "Neck expected to snap when gap >= TEAR"
    goo.render(cr)
    print("Test 3 (Neck snap): Success")

    goo.tint((255, 128, 0), duration_sec=0.2)
    assert goo._target_rim_color[0] == 1.0
    assert abs(goo._target_rim_color[3] - TINTED_ALPHA) < 1e-5
    goo.render(cr, dt=0.1)
    assert abs(goo.rim_color[0] - 1.0) < 1e-4
    goo.render(cr, dt=0.1)
    assert abs(goo.rim_color[1] - (128.0 / 255.0)) < 1e-2
    print(f"Test 4 (Tint animation): rim_color={goo.rim_color}")

    goo.tint(None, duration_sec=0.0)
    assert goo.rim_color == DEFAULT_RIM_COLOR
    print("Test 5 (Tint reset): Success")

    print("\nAll Goo tests executed successfully without errors!")
