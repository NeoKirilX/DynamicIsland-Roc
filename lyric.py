
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import cairo

logger = logging.getLogger(__name__)

FONT_SIZE: float = 14.0
LINE_HEIGHT: float = 18.0
MAX_LINES: int = 2
EDGE: float = 26.0
DIM: float = 0.4
SCALE: float = 0.94
UNSUNG_OPACITY: float = 0.6
FADE_EDGE: float = 8.0

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
        eff_font = font_size if is_active else font_size * SCALE
        select_font(cr, font_size=eff_font, bold=is_active)
        line_h = eff_font * (LINE_HEIGHT / FONT_SIZE)
        rows = layout_lines(cr, self.text or "♪", max_w=max_w, max_lines=MAX_LINES)
        rows_count = max(1, len(rows))
        max_row_w = max((adv for _, adv in rows), default=0.0)
        return (max_row_w, rows_count * line_h)

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

        if not text:
            return

        select_font(cr, font_size=font_size, bold=True)
        ascent, descent, f_height = cr.font_extents()[:3]
        ext = cr.text_extents(text)
        text_w = ext.x_advance

        if text_w <= max_w - 2.0 * fade_edge and offset_x == 0.0:
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
        a = float(color[3]) if len(color) > 3 else 1.0
        cr.set_source_rgba(r, g, b, a)
        cr.move_to(text_x, baseline)
        cr.show_text(text)
        text_group = cr.pop_group()

        fade = min(fade_edge, max_w * 0.45)
        grad = cairo.LinearGradient(x, 0.0, x + max_w, 0.0)
        if fade > 0.5:
            grad.add_color_stop_rgba(0.0, 1.0, 1.0, 1.0, 0.0)
            grad.add_color_stop_rgba(fade / max_w, 1.0, 1.0, 1.0, 1.0)
            grad.add_color_stop_rgba(1.0 - fade / max_w, 1.0, 1.0, 1.0, 1.0)
            grad.add_color_stop_rgba(1.0, 1.0, 1.0, 1.0, 0.0)
        else:
            grad.add_color_stop_rgba(0.0, 1.0, 1.0, 1.0, 1.0)
            grad.add_color_stop_rgba(1.0, 1.0, 1.0, 1.0, 1.0)

        cr.set_source(text_group)
        cr.mask(grad)
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

        display_text = text if text.strip() else "♪"

        if not is_active:
            eff_font = font_size * SCALE
            select_font(cr, font_size=eff_font, bold=False)
            line_h = eff_font * (LINE_HEIGHT / FONT_SIZE)
            rows = layout_lines(cr, display_text, max_w=w, max_lines=MAX_LINES)
            if not rows:
                rows = [("♪", cr.text_extents("♪").x_advance)]

            total_h = len(rows) * line_h
            start_y = y + max(0.0, (h - total_h) / 2.0) if h > 0.0 else y
            ascent, descent, f_height = cr.font_extents()[:3]

            for i, (row_str, adv) in enumerate(rows):
                row_y = start_y + i * line_h
                baseline = row_y + ascent + max(0.0, (line_h - f_height) / 2.0)
                row_x = x + max(0.0, (w - adv) / 2.0)

                cr.save()
                cr.rectangle(x, row_y, w, line_h)
                cr.clip()
                cr.set_source_rgba(1.0, 1.0, 1.0, DIM)
                cr.move_to(row_x, baseline)
                cr.show_text(row_str)
                cr.restore()

            return total_h

        select_font(cr, font_size=font_size, bold=True)
        line_h = font_size * (LINE_HEIGHT / FONT_SIZE)
        rows = layout_lines(cr, display_text, max_w=w, max_lines=MAX_LINES)
        if not rows:
            rows = [("♪", cr.text_extents("♪").x_advance)]

        row_widths = [adv for _, adv in rows]
        total_dist = sum(row_widths) + EDGE * len(rows)

        p = max(0.0, min(1.0, float(progress)))
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
            cr.set_source_rgba(1.0, 1.0, 1.0, 1.0)
            cr.move_to(row_x, baseline)
            cr.show_text(row_str)
            text_group = cr.pop_group()

            grad = cairo.LinearGradient(row_x + from_x, 0.0, row_x + from_x + EDGE, 0.0)
            grad.add_color_stop_rgba(0.0, 1.0, 1.0, 1.0, 1.0)
            grad.add_color_stop_rgba(1.0, 1.0, 1.0, 1.0, unsung_opacity)

            cr.set_source(text_group)
            cr.mask(grad)
            cr.restore()

        return total_h

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

    out_png = "/tmp/opencode/test_lyric_render.png"
    surf.write_to_png(out_png)
    print(f"Exported karaoke test rendering to {out_png}")
    print("LyricLine tests completed successfully!")
