#!/usr/bin/env python3

import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Gtk4LayerShell", "1.0")
from gi.repository import Gtk

import cairo

from main_window import MainWindow, Panel, View, PLAYER_LYRIC_ROOM, PLAYER_HEIGHT
from lyric import measure_text

FAILURES: list[str] = []

LINES = [
    (0.0, "And then I realized that everything I had ever believed about the world"),
    (6.0, "Supercalifragilisticexpialidociousandthensomemorewordsthatnevereverend"),
    (12.0, "was wrong"),
    (18.0, "I tried so hard and got so far"),
]


def check(condition: bool, message: str) -> None:
    if not condition:
        FAILURES.append(message)
        print(f"  FAIL {message}")
    else:
        print(f"  ok   {message}")


def cr_8() -> cairo.Context:
    return cairo.Context(cairo.ImageSurface(cairo.FORMAT_ARGB32, 8, 8))


def fake_media(win: MainWindow, position: float) -> None:
    win._lyrics.for_duration = lambda duration: list(LINES)
    win._lyrics.get_current_line = lambda pos, duration, lead=0.0: (1, LINES[1])
    win._media._duration = 24.0
    win._media._position = position
    win._media._position_at = time.monotonic()


def show(win: MainWindow, view: View, panel: Panel) -> None:
    win._panel = panel
    win._current_view = view
    win._previous_view = view
    win._view_transition = 1.0
    win.set_targets()
    for _ in range(30):
        win.on_frame_tick(win.area, None)
    win._current_view = view
    win._previous_view = view
    win.on_draw(win.area, cairo.Context(cairo.ImageSurface(cairo.FORMAT_ARGB32, 700, 560)), 700, 560)


def on_activate(application) -> None:
    print("Testing lyric layout in the real views with long lines...")

    win = MainWindow(application, forced_view="Media", forced_timer=45.0)
    fake_media(win, 7.0)
    win._player_room = True
    show(win, View.MEDIA_BIG, Panel.PLAYER)

    lyric_w = 340.0
    h_prev = measure_text(cr_8(), LINES[0][1], lyric_w, 14.0, False)[1]
    h_curr = measure_text(cr_8(), LINES[1][1], lyric_w, 14.0, True)[1]
    h_next = measure_text(cr_8(), LINES[2][1], lyric_w, 14.0, False)[1]
    stack = h_prev + h_curr + h_next + 4.0 * 2

    print("\n[expanded player] long lines")
    check(win._player_lyric_h >= stack - 0.01, f"room grew to fit the stack ({win._player_lyric_h:.1f} >= {stack:.1f})")
    check(win._player_lyric_h >= PLAYER_LYRIC_ROOM, "room never shrinks below the default")
    size = win.size_of(View.MEDIA_BIG)
    check(size.h >= PLAYER_HEIGHT + stack, f"pill is tall enough for the lines ({size.h:.1f})")
    win.destroy()

    compact = MainWindow(application, forced_view="Media", forced_timer=45.0)
    fake_media(compact, 7.0)
    compact.on_periodic_tick()
    show(compact, View.MEDIA, Panel.NONE)

    print("\n[compact island] long line")
    check(compact._lyric_overflow > 0.0, "line longer than the pill scrolls instead of hiding")
    check(compact._lyric_span > 0.0, "scroll is timed to the length of the line")
    check(compact._lyric_line_start == LINES[1][0], "scroll knows when the line began")

    for _ in range(60):
        compact.on_frame_tick(compact.area, None)
    compact.on_draw(compact.area, cairo.Context(cairo.ImageSurface(cairo.FORMAT_ARGB32, 700, 560)), 700, 560)
    check(compact._lyric_scroll < 0.0, f"text has scrolled into view ({compact._lyric_scroll:.1f})")

    compact._lyrics.get_current_line = lambda pos, duration, lead=0.0: (2, LINES[2])
    compact.on_periodic_tick()
    compact.on_draw(compact.area, cairo.Context(cairo.ImageSurface(cairo.FORMAT_ARGB32, 700, 560)), 700, 560)
    check(compact._lyric_scroll == 0.0, "scroll resets when the next line arrives")
    check(compact._lyric_overflow == 0.0, "a short line needs no scrolling")
    check(compact._media_width == 210.0, f"pill returns to its base width ({compact._media_width})")
    compact.destroy()

    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} check(s)")
    else:
        print("ALL INTEGRATED LYRIC VIEW CHECKS PASSED")


def run() -> int:
    app = Gtk.Application(application_id="io.github.dynamic_island.test_lyric_views")
    app.connect("activate", on_activate)
    app.run([])
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(run())
