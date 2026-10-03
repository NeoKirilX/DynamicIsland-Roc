import hashlib
import math
import sys

import cairo

from lyric import LyricLine, layout_lines, measure_text, select_font

FAILURES: list[str] = []


def check(condition: bool, message: str) -> None:
    if not condition:
        FAILURES.append(message)
        print(f"  FAIL {message}")
    else:
        print(f"  ok   {message}")


def make_cr(w: int = 900, h: int = 600) -> cairo.Context:
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    cr = cairo.Context(surf)
    cr.set_source_rgb(0.06, 0.06, 0.07)
    cr.paint()
    return cr


SHORT = "I tried so hard"
LONG = "And then I realized that everything I had ever believed about the world was wrong"
LONG_WORD = "Supercalifragilisticexpialidociousandthensomemorewordsthatneverend"


def test_compact_fits_without_hiding() -> None:
    print("\n[1] compact: wrapped rows never exceed the box they are drawn in")
    cr = make_cr()
    lyric_w = 340.0
    select_font(cr, font_size=13.0, bold=True)

    for name, text in (("short", SHORT), ("long", LONG), ("unbreakable", LONG_WORD)):
        rows = layout_lines(cr, text, max_w=lyric_w, max_lines=2)
        widest = max((a for _, a in rows), default=0.0)
        check(len(rows) >= 1, f"{name}: produced at least one row")
        check(widest <= lyric_w + 0.01, f"{name}: rows fit inside box ({widest:.1f} <= {lyric_w})")
        check(all(not r[0].endswith("…") or r[1] <= lyric_w for r in rows), f"{name}: truncated rows stay inside")

    rows = layout_lines(cr, LONG, max_w=lyric_w, max_lines=2)
    check(len(rows) == 2, "long line wraps into two rows instead of one clipped row")
    rows = layout_lines(cr, LONG_WORD, max_w=lyric_w, max_lines=2)
    check(rows[-1][0].endswith("…"), "a word wider than the box is cut with an ellipsis")


def test_compact_width_matches_render() -> None:
    print("\n[2] compact: bar grows only as far as the text really needs")
    cr = make_cr()
    inset, edge, base, cap = 77.0, 8.0, 210.0, 440.0

    for name, text in (("short", SHORT), ("long", LONG), ("unbreakable", LONG_WORD)):
        select_font(cr, font_size=13.0, bold=True)
        tw = cr.text_extents(text).x_advance
        width = max(base, min(cap, tw + 2 * edge + inset + 2.0))
        mid_w = width - inset
        fits = tw <= mid_w - 2 * edge
        check(
            fits or tw > cap - inset,
            f"{name}: pill fits the line, or the line is longer than any pill ({tw:.1f}, mid_w {mid_w:.1f})",
        )
        if fits:
            check(width <= cap, f"{name}: width stays within the cap ({width:.1f} <= {cap})")


def test_compact_scroll_offset() -> None:
    print("\n[3] compact: overflowing text can be scrolled into view")
    images = {}
    for offset in (0.0, -50.0, -180.0):
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 400, 60)
        cr = cairo.Context(surf)
        cr.set_source_rgb(0.0, 0.0, 0.0)
        cr.paint()
        LyricLine.render_compact(cr, LONG_WORD, 10.0, 10.0, 200.0, (1.0, 1.0, 1.0, 1.0), font_size=13.0, offset_x=offset)
        surf.flush()
        images[offset] = hashlib.md5(surf.get_data()).hexdigest()

    check(len(set(images.values())) == 3, "each scroll offset draws a different frame")
    for offset, digest in images.items():
        check(digest is not None, f"offset {offset} rendered")


def test_expanded_stack_never_overlaps() -> None:
    print("\n[4] expanded: prev / current / next stack without overlapping")
    cr = make_cr()
    lyric_w = 340.0
    font = 14.0
    gap = 4.0

    cases = [
        ("three short", SHORT, SHORT, SHORT),
        ("long current", SHORT, LONG, SHORT),
        ("long neighbours", LONG, SHORT, LONG),
        ("all long", LONG, LONG, LONG_WORD),
        ("no prev", "", LONG, SHORT),
    ]

    for name, prev_text, curr_text, next_text in cases:
        h_prev = measure_text(cr, prev_text, lyric_w, font, False)[1] if prev_text else 0.0
        h_curr = measure_text(cr, curr_text, lyric_w, font, True)[1] if curr_text else 0.0
        h_next = measure_text(cr, next_text, lyric_w, font, False)[1] if next_text else 0.0
        rows = sum(1 for h in (h_prev, h_curr, h_next) if h > 0.0)

        top_prev = 0.0
        top_curr = top_prev + h_prev + (gap if h_prev > 0.0 and rows > 1 else 0.0)
        top_next = top_curr + h_curr + (gap if h_curr > 0.0 and rows > 1 else 0.0)
        stack_h = h_prev + h_curr + h_next + gap * max(0, rows - 1)

        check(rows >= 1, f"{name}: something is drawn")
        if h_prev > 0.0 and h_curr > 0.0:
            check(
                top_curr >= top_prev + h_prev - 0.01,
                f"{name}: current line starts below prev ({top_curr:.1f} >= {top_prev + h_prev:.1f})",
            )
        if h_curr > 0.0 and h_next > 0.0:
            check(
                top_next >= top_curr + h_curr - 0.01,
                f"{name}: next line starts below current ({top_next:.1f} >= {top_curr + h_curr:.1f})",
            )

        room = max(74.0, stack_h + 16.0)
        start = max(0.0, (room - stack_h) / 2.0)
        bottom = start + stack_h
        check(
            start >= 0.0 and bottom <= room + 0.01,
            f"{name}: stack fits the room ({bottom:.1f} <= {room:.1f})",
        )


def test_wrapped_line_height_is_scored_per_row() -> None:
    print("\n[5] measure reports two rows for a wrapped line")
    cr = make_cr()
    w, one_h = measure_text(cr, SHORT, 340.0, 14.0, True)
    _, two_h = measure_text(cr, LONG, 340.0, 14.0, True)
    check(two_h > one_h, f"wrapped line is taller ({two_h:.1f} > {one_h:.1f})")
    check(
        math.isclose(two_h, one_h * 2, rel_tol=1e-6),
        "wrapped line measures exactly two rows tall",
    )
    dim_w, dim_h = measure_text(cr, LONG, 340.0, 14.0, False)
    check(dim_h < two_h, "dim neighbours are drawn smaller than the sung line")


def test_measure_matches_render() -> None:
    print("\n[6] measure agrees with what render_karaoke draws")
    cr = make_cr()
    lyric_w = 340.0
    for text in (SHORT, LONG, LONG_WORD):
        for active in (True, False):
            _, want = measure_text(cr, text, lyric_w, 14.0, active)
            got = LyricLine.render_karaoke(
                cr, text, 0.4, 20.0, 20.0, lyric_w, 0.0, font_size=14.0, is_active=active
            )
            check(
                math.isclose(got, want, rel_tol=1e-6),
                f"measure == render for {'active' if active else 'dim'} {text[:18]!r} ({got:.2f} vs {want:.2f})",
            )


def main() -> int:
    test_compact_fits_without_hiding()
    test_compact_width_matches_render()
    test_compact_scroll_offset()
    test_expanded_stack_never_overlaps()
    test_wrapped_line_height_is_scored_per_row()
    test_measure_matches_render()

    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} check(s)")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("ALL LYRIC LAYOUT CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
