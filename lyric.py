
from __future__ import annotations

import logging
import math
from pathlib import Path
import tempfile
import time
from typing import Any, Optional

import cairo

logger = logging.getLogger(__name__)

FONT_SIZE: float = 14.0
LINE_HEIGHT: float = 18.0
MAX_LINES: int = 2
EDGE: float = 26.0
SWEEP_EDGE: float = 18.0
DIM: float = 0.4
SCALE: float = 0.94
UNSUNG_OPACITY: float = 0.6
FADE_EDGE: float = 8.0

DOT_COUNT: int = 3
DOT_SIZE: float = 6.0
DOT_GAP: float = 5.0
DOT_BREATH_PERIOD: float = 1.8
DOT_SWELL: float = 0.24
DOT_FAINT: float = 1.75
DOT_DYING: float = 0.3

def is_wordless(text: str) -> bool:
    clean = text.strip()
    if not clean:
        return True
    return not any(c.isalnum() for c in clean)

def draw_break_dots(
    cr: cairo.Context,
    cx: float,
    cy: float,
    progress: float = 0.0,
    alpha: float = 1.0,
    unsung_opacity: float = UNSUNG_OPACITY,
    is_active: bool = True,
    now: float | None = None,
) -> float:
    if now is None:
        now = time.monotonic()

    total_w = DOT_COUNT * DOT_SIZE + (DOT_COUNT - 1) * DOT_GAP
    start_x = cx - total_w / 2.0

    gone = max(0.0, min(1.0, 1.0 - DOT_FAINT * (1.0 - (1.0 if is_active else unsung_opacity))))
    p = max(0.0, min(1.0, float(progress)))
    left = (1.0 - p) * DOT_COUNT
    breath = (1.0 - math.cos(now * 2.0 * math.pi / DOT_BREATH_PERIOD)) / 2.0
    scale = 1.0 + DOT_SWELL * (1.0 - gone) * breath
    r = (DOT_SIZE / 2.0) * scale

    for i in range(DOT_COUNT):
        op = gone + (1.0 - gone) * max(0.0, min(1.0, (left - i) / DOT_DYING))
        dot_a = op * alpha
        if dot_a <= 0.001:
            continue
        dot_x = start_x + i * (DOT_SIZE + DOT_GAP) + DOT_SIZE / 2.0
        cr.save()
        cr.set_source_rgba(1.0, 1.0, 1.0, dot_a)
        cr.arc(dot_x, cy, r, 0.0, 2.0 * math.pi)
        cr.fill()
        cr.restore()

    return LINE_HEIGHT if is_active else LINE_HEIGHT * SCALE

_FONTS_REGISTERED: bool = False

def _register_bundled_fonts() -> None:
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return
    _FONTS_REGISTERED = True

    try:
        import ctypes
        import ctypes.util

        fc_lib = ctypes.util.find_library("fontconfig") or "libfontconfig.so.1"
        fc = ctypes.cdll.LoadLibrary(fc_lib)
        fonts_dir = Path(__file__).resolve().parent / "fonts"
        if fonts_dir.exists():
            for font_file in sorted(fonts_dir.glob("*.otf")):
                fc.FcConfigAppFontAddFile(None, str(font_file).encode("utf-8"))
    except Exception as exc:
        logger.debug("Fontconfig font registration failed: %s", exc)

def select_font(
    cr: cairo.Context,
    font_size: float = FONT_SIZE,
    bold: bool = True,
    family: str = "SF Pro Text",
) -> None:
    _register_bundled_fonts()
    weight = cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL
    cr.select_font_face(family, cairo.FONT_SLANT_NORMAL, weight)
    cr.set_font_size(font_size)

def layout_lines(
    cr: cairo.Context,
    text: str,
    max_w: float,
    max_lines: int = MAX_LINES,
) -> list[tuple[str, float]]:
    clean_text = text.strip()
    if not clean_text:
        return []

    words = clean_text.split()
    if not words:
        return []

    if max_w <= 0.0:
        return [(clean_text, cr.text_extents(clean_text).x_advance)]

    ext = cr.text_extents(clean_text)
    if ext.x_advance <= max_w:
        return [(clean_text, ext.x_advance)]

    lines: list[tuple[str, float]] = []
    idx = 0
    ellipsis = "…"

    while idx < len(words) and len(lines) < max_lines:
        line_words: list[str] = []
        is_last_line = len(lines) == max_lines - 1

        while idx < len(words):
            candidate = " ".join(line_words + [words[idx]]) if line_words else words[idx]
            adv = cr.text_extents(candidate).x_advance
            if adv <= max_w or not line_words:
                line_words.append(words[idx])
                idx += 1
            else:
                break

        line_str = " ".join(line_words)
        if is_last_line and idx < len(words):
            line_str = " ".join(line_words + words[idx:])
            idx = len(words)

        adv = cr.text_extents(line_str).x_advance
        if adv > max_w:
            while line_str and cr.text_extents(line_str + ellipsis).x_advance > max_w:
                line_str = line_str[:-1]
            line_str = line_str.rstrip() + ellipsis
            adv = cr.text_extents(line_str).x_advance

        lines.append((line_str, adv))

    return lines

def measure_text(
    cr: cairo.Context,
    text: str,
    max_w: float,
    font_size: float = FONT_SIZE,
    is_active: bool = True,
) -> tuple[float, float]:
    eff_font = font_size if is_active else font_size * SCALE
    if is_wordless(text):
        return (DOT_COUNT * DOT_SIZE + (DOT_COUNT - 1) * DOT_GAP, eff_font * (LINE_HEIGHT / FONT_SIZE))
    select_font(cr, font_size=font_size, bold=True)
    canonical_rows = layout_lines(cr, text.strip() or "♪", max_w=max_w, max_lines=MAX_LINES)
    rows_count = max(1, len(canonical_rows))
    line_h = eff_font * (LINE_HEIGHT / FONT_SIZE)
    select_font(cr, font_size=eff_font, bold=is_active)
    max_row_w = max((cr.text_extents(r[0]).x_advance for r in canonical_rows), default=0.0)
    return (max_row_w, rows_count * line_h)

def render_staggered_text(
    cr: cairo.Context,
    text: str,
    text_x: float,
    baseline: float,
    f_height: float,
    r: float,
    g: float,
    b: float,
    a: float,
    exit_p: Optional[float] = None,
    enter_p: Optional[float] = None,
    anim_style: str = "letters",
    fly_height: float = 26.0,
    stagger: float = 0.35,
) -> None:
    if not text:
        return

    n_chars = len(text)
    cur_x = text_x
    advances = [cr.text_extents(ch).x_advance for ch in text]

    for idx, (ch, ch_w) in enumerate(zip(text, advances)):
        if ch.isspace():
            cur_x += ch_w
            continue

        rel = idx / max(1, n_chars - 1)

        if exit_p is not None:
            ep = max(0.0, min(1.0, float(exit_p)))
            if anim_style == "letters":
                jitter = (((idx * 7 + 13) % 17) / 17.0 - 0.5) * 0.2
                d = max(0.0, min(stagger, stagger * rel + jitter))
                t = max(0.0, min(1.0, (ep - d) / max(0.01, 1.0 - stagger)))
                dy = -fly_height * (t ** 1.35)
                dx = math.sin(idx * 1.8 + 0.5) * 5.0 * t
                rot = math.sin(idx * 2.3 + 1.1) * 0.20 * t
                ch_alpha = a * max(0.0, 1.0 - (t ** 1.4))
            elif anim_style == "wave":
                d = stagger * rel
                t = max(0.0, min(1.0, (ep - d) / max(0.01, 1.0 - stagger)))
                dy = -fly_height * (t ** 1.25)
                dx = 0.0
                rot = 0.0
                ch_alpha = a * max(0.0, 1.0 - t)
            elif anim_style == "bounce":
                d = stagger * (1.0 - abs(rel - 0.5) * 2.0)
                t = max(0.0, min(1.0, (ep - d) / max(0.01, 1.0 - stagger)))
                dy = -fly_height * math.sin(t * math.pi * 0.5)
                dx = math.sin(idx * 2.7) * 4.0 * t
                rot = math.sin(idx * 3.1) * 0.15 * t
                ch_alpha = a * max(0.0, 1.0 - (t ** 1.4))
            else:  # slide
                dy = -fly_height * ep
                dx = 0.0
                rot = 0.0
                ch_alpha = a * max(0.0, 1.0 - ep)
        elif enter_p is not None:
            en = max(0.0, min(1.0, float(enter_p)))
            if anim_style == "letters":
                jitter = (((idx * 11 + 7) % 19) / 19.0 - 0.5) * 0.18
                d = max(0.0, min(stagger, stagger * (1.0 - rel) + jitter))
                t = max(0.0, min(1.0, (en - d) / max(0.01, 1.0 - stagger)))
                dy = fly_height * ((1.0 - t) ** 1.8)
                dx = math.sin(idx * 1.5) * 4.0 * (1.0 - t)
                rot = -math.sin(idx * 2.1) * 0.18 * (1.0 - t)
                ch_alpha = a * min(1.0, t * 1.5)
            elif anim_style == "wave":
                d = stagger * rel
                t = max(0.0, min(1.0, (en - d) / max(0.01, 1.0 - stagger)))
                dy = fly_height * ((1.0 - t) ** 1.5)
                dx = 0.0
                rot = 0.0
                ch_alpha = a * min(1.0, t * 1.3)
            elif anim_style == "bounce":
                d = stagger * (1.0 - abs(rel - 0.5) * 2.0)
                t = max(0.0, min(1.0, (en - d) / max(0.01, 1.0 - stagger)))
                dy = fly_height * math.cos(t * math.pi * 0.5)
                dx = 0.0
                rot = 0.0
                ch_alpha = a * t
            else:  # slide
                dy = fly_height * (1.0 - en)
                dx = 0.0
                rot = 0.0
                ch_alpha = a * en
        else:
            dy = 0.0
            dx = 0.0
            rot = 0.0
            ch_alpha = a

        if ch_alpha > 0.005:
            cx = cur_x + ch_w / 2.0 + dx
            cy = baseline - f_height / 3.0 + dy
            cr.save()
            cr.translate(cx, cy)
            if abs(rot) > 0.001:
                cr.rotate(rot)
            cr.set_source_rgba(r, g, b, ch_alpha)
            cr.move_to(-ch_w / 2.0, f_height / 3.0)
            cr.show_text(ch)
            cr.restore()

        cur_x += ch_w


class LyricLine:

    def __init__(
        self,
        text: str = "",
        progress: float = 0.0,
        unsung_opacity: float = UNSUNG_OPACITY,
    ) -> None:
        self.text: str = text
        self._progress: float = max(0.0, min(1.0, float(progress)))
        self._unsung_opacity: float = max(0.0, min(1.0, float(unsung_opacity)))

    @property
    def progress(self) -> float:
        return self._progress

    @progress.setter
    def progress(self, value: float) -> None:
        self._progress = max(0.0, min(1.0, float(value)))

    @property
    def unsung_opacity(self) -> float:
        return self._unsung_opacity

    @unsung_opacity.setter
    def unsung_opacity(self, value: float) -> None:
        self._unsung_opacity = max(0.0, min(1.0, float(value)))

    def measure(
        self,
        cr: cairo.Context,
        max_w: float,
        font_size: float = FONT_SIZE,
        is_active: bool = True,
    ) -> tuple[float, float]:
        return measure_text(cr, self.text or "♪", max_w, font_size, is_active)

    def render_compact(
        self_or_cls,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        inst: LyricLine | None = None
        if isinstance(self_or_cls, LyricLine):
            inst = self_or_cls
            actual_args = args
        elif isinstance(self_or_cls, cairo.Context):
            actual_args = (self_or_cls,) + args
        else:
            actual_args = args

        cr: cairo.Context = actual_args[0] if actual_args else kwargs["cr"]
        rest = actual_args[1:]

        if len(rest) > 0 and isinstance(rest[0], str):
            text: str = rest[0]
            x: float = float(rest[1]) if len(rest) > 1 else float(kwargs.get("x", 0.0))
            y: float = float(rest[2]) if len(rest) > 2 else float(kwargs.get("y", 0.0))
            max_w: float = float(rest[3]) if len(rest) > 3 else float(kwargs.get("max_w", 200.0))
            color: tuple[float, ...] = (
                rest[4] if len(rest) > 4 else kwargs.get("color", (1.0, 1.0, 1.0))
            )
        else:
            text = kwargs.get("text", inst.text if inst else "")
            x = float(rest[0]) if len(rest) > 0 else float(kwargs.get("x", 0.0))
            y = float(rest[1]) if len(rest) > 1 else float(kwargs.get("y", 0.0))
            max_w = float(rest[2]) if len(rest) > 2 else float(kwargs.get("max_w", 200.0))
            color = rest[3] if len(rest) > 3 else kwargs.get("color", (1.0, 1.0, 1.0))

        font_size: float = float(kwargs.get("font_size", 13.0))
        fade_edge: float = float(kwargs.get("fade_edge", FADE_EDGE))
        offset_x: float = float(kwargs.get("offset_x", 0.0))
        h: float = float(kwargs.get("h", 34.0))
        alpha: float = float(kwargs.get("alpha", 1.0))
        dim: float = float(kwargs.get("dim", 1.0))
        progress: Optional[float] = kwargs.get("progress", None)
        unsung: float = float(kwargs.get("unsung", DIM))
        exit_progress: Optional[float] = kwargs.get("exit_progress", None)
        enter_progress: Optional[float] = kwargs.get("enter_progress", None)
        anim_style: str = str(kwargs.get("anim_style", "letters"))
        fly_height: float = float(kwargs.get("fly_height", 26.0))
        stagger: float = float(kwargs.get("stagger", 0.35))

        if not text:
            return

        if is_wordless(text):
            draw_break_dots(
                cr,
                x + max_w / 2.0,
                y + h / 2.0,
                progress=progress if progress is not None else 0.0,
                alpha=alpha * dim,
                unsung_opacity=unsung,
                is_active=True,
            )
            return

        select_font(cr, font_size=font_size, bold=True)
        ascent, descent, f_height = cr.font_extents()[:3]
        ext = cr.text_extents(text)
        text_w = ext.x_advance

        if h <= 42.0:
            fly_height = min(fly_height, max(5.0, (h - f_height) * 0.55))

        is_overflowing = (text_w > max_w - 2.0 * fade_edge) or (offset_x != 0.0)
        if not is_overflowing:
            text_x = x + (max_w - text_w) / 2.0
        else:
            text_x = x + fade_edge + offset_x

        baseline = y + (h + ascent - descent) / 2.0

        cr.save()
        cr.rectangle(x, y, max_w, h)
        cr.clip()

        cr.push_group()
        r = float(color[0])
        g = float(color[1])
        b = float(color[2])
        a = (float(color[3]) if len(color) > 3 else 1.0) * alpha * dim

        if exit_progress is not None or (enter_progress is not None and enter_progress < 0.999):
            render_staggered_text(
                cr,
                text,
                text_x,
                baseline,
                f_height,
                r,
                g,
                b,
                a,
                exit_p=exit_progress,
                enter_p=enter_progress,
                anim_style=anim_style,
                fly_height=fly_height,
                stagger=stagger,
            )
        else:
            cr.set_source_rgba(r, g, b, a)
            cr.move_to(text_x, baseline)
            cr.show_text(text)
        cr.new_path()
        text_group = cr.pop_group()

        cr.push_group()
        cr.set_source(text_group)

        if progress is not None:
            p = max(0.0, min(1.0, float(progress)))
            head = x + (max_w - text_w) / 2.0 + text_w * p if text_w <= max_w else text_x + text_w * p
            grad = cairo.LinearGradient(head - SWEEP_EDGE, 0.0, head + SWEEP_EDGE, 0.0)
            grad.add_color_stop_rgba(0.0, 1.0, 1.0, 1.0, a)
            grad.add_color_stop_rgba(0.42, 1.0, 1.0, 1.0, a)
            grad.add_color_stop_rgba(0.72, 1.0, 1.0, 1.0, a * (1.0 - (1.0 - unsung) * 0.45))
            grad.add_color_stop_rgba(1.0, 1.0, 1.0, 1.0, a * unsung)
            cr.mask(grad)
        elif is_overflowing:
            fade = min(16.0, max_w * 0.25)
            grad = cairo.LinearGradient(x, 0.0, x + max_w, 0.0)
            left_a = 0.0 if offset_x < -1.0 else a
            grad.add_color_stop_rgba(0.0, 1.0, 1.0, 1.0, left_a)
            grad.add_color_stop_rgba(fade / max_w, 1.0, 1.0, 1.0, a)
            remaining_right = (text_w + offset_x) - (max_w - 2.0 * fade_edge)
            right_a = 0.0 if remaining_right > 1.0 else a
            grad.add_color_stop_rgba(1.0 - fade / max_w, 1.0, 1.0, 1.0, a)
            grad.add_color_stop_rgba(1.0, 1.0, 1.0, 1.0, right_a)
            cr.mask(grad)
        else:
            cr.paint()
        horiz_group = cr.pop_group()

        cr.set_source(horiz_group)
        fade_v = min(7.0, h * 0.22)
        v_grad = cairo.LinearGradient(0.0, y, 0.0, y + h)
        v_grad.add_color_stop_rgba(0.0, 1.0, 1.0, 1.0, 0.0)
        v_grad.add_color_stop_rgba(fade_v / h, 1.0, 1.0, 1.0, 1.0)
        v_grad.add_color_stop_rgba(1.0 - fade_v / h, 1.0, 1.0, 1.0, 1.0)
        v_grad.add_color_stop_rgba(1.0, 1.0, 1.0, 1.0, 0.0)
        cr.mask(v_grad)

        cr.restore()

    def render_karaoke(
        self_or_cls,
        *args: Any,
        **kwargs: Any,
    ) -> float:
        inst: LyricLine | None = None
        if isinstance(self_or_cls, LyricLine):
            inst = self_or_cls
            actual_args = args
        elif isinstance(self_or_cls, cairo.Context):
            actual_args = (self_or_cls,) + args
        else:
            actual_args = args

        cr: cairo.Context = actual_args[0] if actual_args else kwargs["cr"]
        rest = actual_args[1:]

        if len(rest) > 0 and isinstance(rest[0], str):
            text: str = rest[0]
            progress: float = float(rest[1]) if len(rest) > 1 else float(kwargs.get("progress", 0.0))
            x: float = float(rest[2]) if len(rest) > 2 else float(kwargs.get("x", 0.0))
            y: float = float(rest[3]) if len(rest) > 3 else float(kwargs.get("y", 0.0))
            w: float = float(rest[4]) if len(rest) > 4 else float(kwargs.get("w", 200.0))
            h: float = float(rest[5]) if len(rest) > 5 else float(kwargs.get("h", 0.0))
            font_size: float = float(rest[6]) if len(rest) > 6 else float(kwargs.get("font_size", FONT_SIZE))
            unsung_opacity: float = float(rest[7]) if len(rest) > 7 else float(kwargs.get("unsung_opacity", UNSUNG_OPACITY))
            is_active: bool = bool(rest[8]) if len(rest) > 8 else bool(kwargs.get("is_active", True))
        else:
            text = kwargs.get("text", inst.text if inst else "")
            progress = float(kwargs.get("progress", inst.progress if inst else 0.0))
            unsung_opacity = float(kwargs.get("unsung_opacity", inst.unsung_opacity if inst else UNSUNG_OPACITY))
            x = float(rest[0]) if len(rest) > 0 else float(kwargs.get("x", 0.0))
            y = float(rest[1]) if len(rest) > 1 else float(kwargs.get("y", 0.0))
            w = float(rest[2]) if len(rest) > 2 else float(kwargs.get("w", 200.0))
            h = float(rest[3]) if len(rest) > 3 else float(kwargs.get("h", 0.0))
            font_size = float(rest[4]) if len(rest) > 4 else float(kwargs.get("font_size", FONT_SIZE))
            is_active = bool(kwargs.get("is_active", True))

        if is_wordless(text):
            return draw_break_dots(
                cr,
                x + w / 2.0,
                y + (h / 2.0 if h > 0.0 else LINE_HEIGHT / 2.0),
                progress=progress,
                alpha=alpha,
                unsung_opacity=unsung_opacity,
                is_active=is_active,
            )

        display_text = text if text.strip() else "♪"
        alpha: float = float(kwargs.get("alpha", 1.0))
        vertical_fill: bool = bool(kwargs.get("vertical_fill", False))

        select_font(cr, font_size=font_size, bold=True)
        canonical_rows = layout_lines(cr, display_text, max_w=w, max_lines=MAX_LINES)
        if not canonical_rows:
            canonical_rows = [("♪", cr.text_extents("♪").x_advance)]

        if not is_active:
            eff_font = font_size * SCALE
            select_font(cr, font_size=eff_font, bold=False)
            line_h = eff_font * (LINE_HEIGHT / FONT_SIZE)
            total_h = len(canonical_rows) * line_h
            start_y = y + max(0.0, (h - total_h) / 2.0) if h > 0.0 else y
            ascent, descent, f_height = cr.font_extents()[:3]

            for i, (row_str, _) in enumerate(canonical_rows):
                adv = cr.text_extents(row_str).x_advance
                row_y = start_y + i * line_h
                baseline = row_y + ascent + max(0.0, (line_h - f_height) / 2.0)
                row_x = x + max(0.0, (w - adv) / 2.0)

                cr.save()
                cr.rectangle(x, row_y, w, line_h)
                cr.clip()
                cr.set_source_rgba(1.0, 1.0, 1.0, DIM * alpha)
                cr.move_to(row_x, baseline)
                cr.show_text(row_str)
                cr.new_path()
                cr.restore()

            return total_h

        select_font(cr, font_size=font_size, bold=True)
        line_h = font_size * (LINE_HEIGHT / FONT_SIZE)
        rows = canonical_rows

        total_h = len(rows) * line_h
        start_y = y + max(0.0, (h - total_h) / 2.0) if h > 0.0 else y
        ascent, descent, f_height = cr.font_extents()[:3]

        p = max(0.0, min(1.0, float(progress)))

        if vertical_fill:
            cr.save()
            cr.rectangle(x, y, w, h if h > 0.0 else total_h)
            cr.clip()

            cr.push_group()
            for i, (row_str, rw) in enumerate(rows):
                row_y = start_y + i * line_h
                baseline = row_y + ascent + max(0.0, (line_h - f_height) / 2.0)
                row_x = x + max(0.0, (w - rw) / 2.0)
                cr.set_source_rgba(1.0, 1.0, 1.0, alpha)
                cr.move_to(row_x, baseline)
                cr.show_text(row_str)
                cr.new_path()
            text_group = cr.pop_group()

            cr.set_source(text_group)
            if p <= 0.001:
                cr.paint_with_alpha(unsung_opacity)
            elif p >= 0.999:
                cr.paint()
            else:
                fill_y = start_y + p * total_h
                fade_h = 10.0
                grad = cairo.LinearGradient(0.0, fill_y - fade_h, 0.0, fill_y + fade_h)
                grad.add_color_stop_rgba(0.0, 1.0, 1.0, 1.0, 1.0)
                grad.add_color_stop_rgba(0.35, 1.0, 1.0, 1.0, 1.0)
                grad.add_color_stop_rgba(0.75, 1.0, 1.0, 1.0, unsung_opacity + (1.0 - unsung_opacity) * 0.35)
                grad.add_color_stop_rgba(1.0, 1.0, 1.0, 1.0, unsung_opacity)
                cr.mask(grad)
            cr.restore()
            return total_h

        row_widths = [adv for _, adv in rows]
        total_dist = sum(row_widths) + EDGE * len(rows)
        at = p * total_dist

        total_h = len(rows) * line_h
        start_y = y + max(0.0, (h - total_h) / 2.0) if h > 0.0 else y
        ascent, descent, f_height = cr.font_extents()[:3]

        for i, (row_str, rw) in enumerate(rows):
            from_x = min(max(at, 0.0), rw + EDGE) - EDGE
            at -= rw + EDGE

            row_y = start_y + i * line_h
            baseline = row_y + ascent + max(0.0, (line_h - f_height) / 2.0)
            row_x = x + max(0.0, (w - rw) / 2.0)

            cr.save()
            cr.rectangle(x, row_y, w, line_h)
            cr.clip()

            cr.push_group()
            cr.set_source_rgba(1.0, 1.0, 1.0, alpha)
            cr.move_to(row_x, baseline)
            cr.show_text(row_str)
            cr.new_path()
            text_group = cr.pop_group()

            head = row_x + from_x
            grad = cairo.LinearGradient(head - SWEEP_EDGE * 1.6, 0.0, head + SWEEP_EDGE * 2.2, 0.0)
            grad.add_color_stop_rgba(0.0, 1.0, 1.0, 1.0, alpha)
            grad.add_color_stop_rgba(0.46, 1.0, 1.0, 1.0, alpha)
            grad.add_color_stop_rgba(0.68, 1.0, 1.0, 1.0, alpha * (1.0 - (1.0 - unsung_opacity) * 0.4))
            grad.add_color_stop_rgba(0.88, 1.0, 1.0, 1.0, alpha * (unsung_opacity + (1.0 - unsung_opacity) * 0.45))
            grad.add_color_stop_rgba(1.0, 1.0, 1.0, 1.0, alpha * unsung_opacity)

            cr.set_source(text_group)
            cr.mask(grad)
            cr.restore()

        return total_h

def render_wait(
    cr: cairo.Context,
    cx: float,
    cy: float,
    progress: float = 0.0,
    alpha: float = 1.0,
    now: float = 0.0,
    radius: float = 13.0,
    tint: tuple[float, float, float] = (1.0, 1.0, 1.0),
) -> None:
    draw_break_dots(
        cr,
        cx,
        cy,
        progress=progress,
        alpha=alpha,
        now=now,
        is_active=True,
    )

Lyric = LyricLine
render_compact = LyricLine.render_compact
render_karaoke = LyricLine.render_karaoke

if __name__ == "__main__":
    print("Testing Lyric / LyricLine rendering with Cairo...")

    width, height = 500, 320
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    cr = cairo.Context(surf)

    cr.set_source_rgb(0.06, 0.06, 0.07)
    cr.paint()

    print("\n--- Testing Compact Island View ---")
    cr.set_source_rgba(1.0, 1.0, 1.0, 0.1)
    cr.rectangle(20, 20, 200, 30)
    cr.fill()

    LyricLine.render_compact(
        cr,
        text="I tried so hard",
        x=20.0,
        y=20.0,
        max_w=200.0,
        color=(1.0, 1.0, 1.0),
    )

    cr.set_source_rgba(1.0, 1.0, 1.0, 0.1)
    cr.rectangle(240, 20, 220, 30)
    cr.fill()
    LyricLine.render_compact(
        cr,
        text="And got so far, but in the end it doesn't even matter",
        x=240.0,
        y=20.0,
        max_w=220.0,
        color=(0.3, 0.8, 1.0),
    )
    print("Compact view rendered successfully.")

    print("\n--- Testing Expanded Player Karaoke View ---")

    y_cursor = 80.0
    w_box = 440.0

    prev_line = LyricLine("It starts with one thing, I don't know why")
    h1 = prev_line.render_karaoke(
        cr,
        x=20.0,
        y=y_cursor,
        w=w_box,
        h=24.0,
        is_active=False,
    )
    y_cursor += h1 + 6.0

    active_line = LyricLine("It doesn't even matter how hard you try, keep that in mind", progress=0.5)
    h2 = active_line.render_karaoke(
        cr,
        x=20.0,
        y=y_cursor,
        w=w_box,
        h=40.0,
        is_active=True,
    )
    y_cursor += h2 + 6.0

    next_line = LyricLine("I designed this rhyme to explain in due time")
    h3 = next_line.render_karaoke(
        cr,
        x=20.0,
        y=y_cursor,
        w=w_box,
        h=24.0,
        is_active=False,
    )
    y_cursor += h3 + 12.0

    wrapped_line = LyricLine(
        "I had to fall to lose it all, but in the end it doesn't even matter",
        progress=0.75,
    )
    h4 = wrapped_line.render_karaoke(
        cr,
        x=20.0,
        y=y_cursor,
        w=320.0,
        h=45.0,
        is_active=True,
    )

    out_png = str(Path(tempfile.gettempdir()) / "test_lyric_render.png")
    surf.write_to_png(out_png)
    print(f"Exported karaoke test rendering to {out_png}")
    print("LyricLine tests completed successfully!")
