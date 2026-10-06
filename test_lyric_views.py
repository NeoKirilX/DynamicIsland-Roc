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
from lyric import LyricLine, measure_text
from settings import Settings, COMBO_SPLIT_ALL

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
    win._media._duration = 180.0
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
    Settings.text_scale = 100

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

    print("\n[expanded player] intro before the first line")
    intro = MainWindow(application, forced_view="Media", forced_timer=45.0)
    fake_media(intro, 1.0)
    intro._lyrics.get_current_line = lambda pos, duration, lead=0.0: (-1, None)
    intro._player_room = True
    show(intro, View.MEDIA_BIG, Panel.PLAYER)
    check(intro._player_lyric_h >= PLAYER_LYRIC_ROOM, "room is filled, not left empty")
    check(intro._player_rows_cache is not None, "rows are measured for the whole song")
    intro.destroy()

    print("\n[expanded player] column scrolls instead of jumping")
    glide = MainWindow(application, forced_view="Media", forced_timer=45.0)
    fake_media(glide, 7.0)
    glide._player_room = True
    show(glide, View.MEDIA_BIG, Panel.PLAYER)
    glide._player_col.value = glide._player_col.target
    before = glide._player_col.target
    glide._media._position = 13.0
    glide._media._position_at = time.monotonic()
    glide.on_frame_tick(glide.area, None)
    glide.on_draw(glide.area, cairo.Context(cairo.ImageSurface(cairo.FORMAT_ARGB32, 700, 560)), 700, 560)
    after_target = glide._player_col.target
    check(after_target < before, f"column target moved for the next line ({before:.1f} -> {after_target:.1f})")
    check(
        glide._player_col.value > after_target + 0.5,
        f"column eases toward the target instead of teleporting ({glide._player_col.value:.1f})",
    )
    glide.destroy()

    print("\n[expanded player] lyrics remain visible while scrolling")
    scroll_win = MainWindow(application, forced_view="Media", forced_timer=45.0)
    fake_media(scroll_win, 0.0)
    scroll_win._player_room = True
    show(scroll_win, View.MEDIA_BIG, Panel.PLAYER)

    for test_pos, expected_active in [(1.0, 0), (7.0, 1), (13.0, 2), (19.0, 3)]:
        scroll_win._media._position = test_pos
        scroll_win._media._position_at = time.monotonic()
        for _ in range(30):
            scroll_win.on_frame_tick(scroll_win.area, None)

        rendered_lines = []
        orig_rk = LyricLine.render_karaoke
        def track_rk(*args, **kwargs):
            text = args[1] if len(args) > 1 else kwargs.get("text", "")
            is_active = args[8] if len(args) > 8 else kwargs.get("is_active", False)
            rendered_lines.append((text, is_active))
            return orig_rk(*args, **kwargs)
        LyricLine.render_karaoke = track_rk

        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 700, 560)
        cr = cairo.Context(surf)
        scroll_win.render_player_lyrics(cr, 100.0, 20.0, 400.0, 200.0, 1.0)
        LyricLine.render_karaoke = orig_rk

        active_rendered = [txt for txt, act in rendered_lines if act]
        check(len(rendered_lines) >= 2, f"pos {test_pos}s: multiple lines rendered ({len(rendered_lines)})")
        check(len(active_rendered) == 1, f"pos {test_pos}s: active line rendered")
        check(active_rendered and active_rendered[0] == LINES[expected_active][1], f"pos {test_pos}s: line {expected_active} is active")

    scroll_win.destroy()

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

    print("\n[compact island] first lyric line animates after toast")
    toast_win = MainWindow(application, forced_timer=45.0)
    toast_win._media._current_player = "test"
    toast_win._media._has_track = True
    toast_win._media._title = "New Song"
    toast_win._media._artist = "Artist"
    toast_win._media._duration = 60.0
    toast_win._media._position = 2.0
    toast_win._media._is_playing = True
    toast_win._lyrics.for_duration = lambda d: [(0.0, "First line of song"), (10.0, "Second line")]
    toast_win._lyrics.get_current_line = lambda pos, dur, lead=0.0: (0, (0.0, "First line of song"))
    toast_win.on_media_changed()
    check(toast_win._current_view == View.TOAST, "track start shows toast")
    toast_win._transient = None
    toast_win.update_view()
    check(toast_win._current_view == View.MEDIA, "view transitions to media pill")
    check(toast_win._lyric_enter.value == 0.0, "first line enters from 0.0 without snap")
    check(toast_win._lyric_enter.target == 1.0, "first line springs towards 1.0")
    check(toast_win._lyric_prev_alpha.value == 0.0, "no ghost exit animation for first line")
    toast_win.destroy()

    print("\n[compact island] duplicate consecutive lines animate on change")
    old_combo = Settings.combo_enabled
    Settings.combo_enabled = False
    dup_win = MainWindow(application, forced_timer=45.0)
    dup_lines = [(10.0, "Repeated refrain"), (15.0, "Repeated refrain"), (20.0, "Final line")]
    dup_win._media._current_player = "test"
    dup_win._media._has_track = True
    dup_win._media._title = "Repeated Song"
    dup_win._media._duration = 60.0
    dup_win._media._position = 10.0
    dup_win._media._is_playing = True
    dup_win._lyrics.for_duration = lambda d: dup_lines
    dup_win._lyrics.get_current_line = lambda pos, dur, lead=0.0: (0, dup_lines[0])
    show(dup_win, View.MEDIA, Panel.NONE)
    dup_win.on_periodic_tick()
    for _ in range(60):
        dup_win._last_tick_time -= 0.02
        dup_win.on_frame_tick(dup_win.area, None)
    check(dup_win._lyric_enter.value > 0.99, "line 1 finished entering")
    check(dup_win._last_lyric_key == (10.0, "Repeated refrain"), "key tracks line 1 timestamp and text")

    dup_win._media._position = 15.0
    dup_win._lyrics.get_current_line = lambda pos, dur, lead=0.0: (1, dup_lines[1])
    dup_win.on_periodic_tick()
    check(dup_win._last_lyric_key == (15.0, "Repeated refrain"), "key updated to line 2 despite identical text")
    check(dup_win._lyric_enter.value == 0.0, "line 2 triggers enter animation from 0.0")
    check(dup_win._lyric_enter.target == 1.0, "line 2 targets 1.0")
    check(dup_win._lyric_prev_text == "Repeated refrain", "line 1 set as exit text")
    check(dup_win._lyric_prev_alpha.value > 0.2, "line 1 exit alpha triggered")
    dup_win.destroy()
    Settings.combo_enabled = old_combo

    print("\n[compact island] lookahead to active does not retrigger slide-in")
    arm_win = MainWindow(application, forced_timer=45.0)
    arm_lines = [(10.0, "Future line")]
    arm_win._media._has_track = True
    arm_win._media._current_player = "test"
    arm_win._media._title = "Lookahead Song"
    arm_win._media._duration = 60.0
    arm_win._media._position = 8.5
    arm_win._media._is_playing = True
    arm_win._lyrics.for_duration = lambda d: arm_lines
    arm_win._lyrics.get_current_line = lambda pos, dur, lead=0.0: (-1, None)
    show(arm_win, View.MEDIA, Panel.NONE)
    arm_win.on_periodic_tick()
    check(arm_win._lyric_target is not None and not arm_win._lyric_target[3], "line armed with started=False")
    for _ in range(60):
        arm_win._last_tick_time -= 0.02
        arm_win.on_frame_tick(arm_win.area, None)
    check(arm_win._lyric_enter.value > 0.99, "armed line settled")

    arm_win._media._position = 10.0
    arm_win._lyrics.get_current_line = lambda pos, dur, lead=0.0: (0, arm_lines[0])
    arm_win.on_periodic_tick()
    check(arm_win._lyric_target is not None and arm_win._lyric_target[3], "target updated to started=True")
    check(arm_win._lyric_enter.value > 0.99, "slide-in was not retriggered")
    arm_win.destroy()

    print("\n[compact island] repeated phrases >= 4 split into x1..x4")
    rep_win = MainWindow(application, forced_timer=45.0)
    rep_win._media._current_player = "test"
    rep_win._media._has_track = True
    rep_win._media._is_playing = True
    rep_win._media._duration = 30.0
    rep_lines = [
        (10.0, "Будь котом, будь котом"),
        (14.0, "Будь котом, будь котом"),
        (18.0, "Другая строчка"),
    ]
    rep_win._lyrics.for_duration = lambda d: rep_lines
    show(rep_win, View.MEDIA, Panel.NONE)

    c_lines = rep_win.compact_lyric_lines()
    check(len(c_lines) == 5, f"repeated phrases split into 4 sub-items + 1 line (got {len(c_lines)})")
    check("х1" in c_lines[0][1], f"first item has х1: {c_lines[0][1]!r}")
    check("х2" in c_lines[1][1], f"second item has х2: {c_lines[1][1]!r}")
    check("х3" in c_lines[2][1], f"third item has х3: {c_lines[2][1]!r}")
    check("х4" in c_lines[3][1], f"fourth item has х4: {c_lines[3][1]!r}")
    check(c_lines[4][1] == "Другая строчка", f"normal line untouched: {c_lines[4][1]!r}")

    rep_win._media._position = 10.5
    rep_win._media._position_at = time.monotonic()
    rep_win.on_periodic_tick()
    check(rep_win._lyric_target is not None and "х1" in rep_win._lyric_target[0], f"at 10.5s target is x1: {rep_win._lyric_target[0] if rep_win._lyric_target else None}")

    rep_win._media._position = 12.5
    rep_win._media._position_at = time.monotonic()
    rep_win.on_periodic_tick()
    check(rep_win._lyric_target is not None and "х2" in rep_win._lyric_target[0], f"at 12.5s target is x2: {rep_win._lyric_target[0] if rep_win._lyric_target else None}")
    rep_win.destroy()

    print("\n[compact island] parenthesized repeated phrases stripped and comboed")
    paren_lines = [
        (10.0, "(Светит солнце, светит солнце)"),
        (14.0, "(Светит солнце, светит солнце)"),
        (18.0, "(Светит солнце, светит солнце)"),
        (22.0, "Конец"),
    ]
    p_lines = MainWindow._process_compact_lines(paren_lines, 30.0)
    check(len(p_lines) == 7, f"parenthesized lines split into 6 combo items + 1 end (got {len(p_lines)})")
    check(p_lines[0][1] == "Светит солнце х1", f"brackets trimmed on combo 1: {p_lines[0][1]!r}")
    check(p_lines[1][1] == "светит солнце х2", f"brackets trimmed on combo 2: {p_lines[1][1]!r}")
    check(p_lines[5][1] == "светит солнце х6", f"brackets trimmed on combo 6: {p_lines[5][1]!r}")
    check("(" not in p_lines[0][1] and ")" not in p_lines[0][1], "no parentheses in combo text")

    print("\n[compact island] ad-lib interjections like (у) do not break combo chain")
    adlib_lines = [
        (0.0, "едем дальше"),
        (2.0, "едем дальше"),
        (4.0, "едем дальше (у)"),
        (6.0, "едем дальше"),
        (8.0, "едем дальше"),
    ]
    adlib_res = MainWindow._process_compact_lines(adlib_lines, 12.0)
    check(len(adlib_res) == 5, f"all 5 lines comboed despite (у) (got {len(adlib_res)})")
    check(adlib_res[0][1] == "едем дальше х1", f"line 0 is x1: {adlib_res[0][1]!r}")
    check(adlib_res[1][1] == "едем дальше х2", f"line 1 is x2: {adlib_res[1][1]!r}")
    check(adlib_res[2][1] == "едем дальше (у) х3", f"line 2 has (у) x3: {adlib_res[2][1]!r}")
    check(adlib_res[3][1] == "едем дальше х4", f"line 3 is x4: {adlib_res[3][1]!r}")
    check(adlib_res[4][1] == "едем дальше х5", f"line 4 is x5: {adlib_res[4][1]!r}")

    print("\n[compact island] single line repeated words with trailing word combo correctly")
    single_line = [(0.0, "быстро, быстро, быстро, быстро, ай")]
    single_res = MainWindow._process_compact_lines(single_line, 5.0)
    check(len(single_res) == 5, f"single line split into 4 combo items + 1 trailing word (got {len(single_res)})")
    check(single_res[0][1] == "быстро х1", f"part 0 is x1: {single_res[0][1]!r}")
    check(single_res[1][1] == "быстро х2", f"part 1 is x2: {single_res[1][1]!r}")
    check(single_res[2][1] == "быстро х3", f"part 2 is x3: {single_res[2][1]!r}")
    check(single_res[3][1] == "быстро х4", f"part 3 is x4: {single_res[3][1]!r}")
    check(single_res[4][1] == "ай", f"part 4 is trailing word: {single_res[4][1]!r}")

    print("\n[compact island] COMBO_SPLIT_ALL works across all breakdown strategies simultaneously")
    Settings.combo_split_mode = COMBO_SPLIT_ALL
    Settings.combo_min_repeats = 2

    # 1. Word repeats without punctuation
    word_line = [(0.0, "ла ла ла ла")]
    word_res = MainWindow._process_compact_lines(word_line, 4.0)
    check(len(word_res) == 4, f"words split into 4 items (got {len(word_res)})")
    check(word_res[0][1] == "ла х1", f"word 0: {word_res[0][1]!r}")
    check(word_res[3][1] == "ла х4", f"word 3: {word_res[3][1]!r}")

    # 2. Multi-word phrase n-gram repeats without commas
    ngram_line = [(0.0, "тра та та тра та та тра та та")]
    ngram_res = MainWindow._process_compact_lines(ngram_line, 6.0)
    check(len(ngram_res) == 3, f"ngrams split into 3 phrases (got {len(ngram_res)})")
    check(ngram_res[0][1] == "тра та та х1", f"ngram 0: {ngram_res[0][1]!r}")
    check(ngram_res[2][1] == "тра та та х3", f"ngram 2: {ngram_res[2][1]!r}")

    # 3. Mixed punctuation and repeating words
    mixed_line = [(0.0, "Эй, пам пам пам пам!")]
    mixed_res = MainWindow._process_compact_lines(mixed_line, 5.0)
    check(len(mixed_res) == 5, f"mixed split into 5 items (got {len(mixed_res)})")
    check(mixed_res[0][1] == "Эй", f"mixed lead word preserved: {mixed_res[0][1]!r}")
    check(mixed_res[1][1] == "пам х1", f"mixed combo 1: {mixed_res[1][1]!r}")
    check(mixed_res[4][1] == "пам х4", f"mixed combo 4: {mixed_res[4][1]!r}")

    # 4. Whole lines repeating across lines (line-level breakdown)
    line_level = [(0.0, "Только ты"), (4.0, "Только ты"), (8.0, "Только ты")]
    lines_res = MainWindow._process_compact_lines(line_level, 12.0)
    check(len(lines_res) == 3, f"line-level kept as 3 combo lines (got {len(lines_res)})")
    check(lines_res[0][1] == "Только ты х1", f"line 0: {lines_res[0][1]!r}")
    check(lines_res[1][1] == "Только ты х2", f"line 1: {lines_res[1][1]!r}")
    check(lines_res[2][1] == "Только ты х3", f"line 2: {lines_res[2][1]!r}")

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
