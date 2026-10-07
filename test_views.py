#!/usr/bin/env python3

import os
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Gtk4LayerShell", "1.0")
from gi.repository import Gtk, GLib, Gio

from main_window import MainWindow, View, Panel
from settings import Settings
import cairo

def test_views():
    print("=" * 60)
    print("Testing DynamicIsland MainWindow and 17 Island Views...")
    print("=" * 60)

    app = Gtk.Application(
        application_id="io.github.dynamic_island.test_views",
        flags=Gio.ApplicationFlags.NON_UNIQUE,
    )

    views_to_test = [
        "Idle",
        "Media",
        "Timer",
        "Volume",
        "Charge",
        "Focus",
        "Toast",
        "Notice",
        "MediaBig",
        "IdleBig",
        "TimerBig",
        "TimerSet",
        "Menu",
        "Settings",
        "Look",
        "TextAnim",
        "Combo",
        "Shelf",
        "Update",
        "Equalizer",
    ]

    original_settings = dict(Settings._data)

    def on_activate(application):
        for view_name in views_to_test:
            print(f"Testing view: {view_name}...", end=" ", flush=True)
            win = MainWindow(application, forced_view=view_name, forced_timer=45.0)

            surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 700, 460)
            cr = cairo.Context(surf)
            win.on_draw(win.area, cr, 700, 460)

            for _ in range(5):
                win.on_frame_tick(win.area, None)
            win.on_periodic_tick()

            win.on_draw(win.area, cr, 700, 460)

            win.destroy()
            print("OK!")

        print("\nAll 17 views rendered successfully without errors!")

        print("\nTesting interactive panel transitions and clicks...")
        win = MainWindow(application)
        assert win._current_view in (View.IDLE, View.MEDIA), f"Initial view unexpected: {win._current_view}"

        win.open_panel(Panel.PLAYER)
        win.update_view()
        assert win._panel == Panel.PLAYER
        assert win._current_view in (View.MEDIA_BIG, View.IDLE_BIG)
        print("  Panel.PLAYER opened successfully ->", win._current_view)

        win.open_panel(Panel.NONE)
        win.update_view()
        assert win._panel == Panel.NONE
        print("  Panel.NONE collapsed successfully ->", win._current_view)

        win.open_panel(Panel.MENU)
        win.update_view()
        assert win._panel == Panel.MENU
        assert win._current_view == View.MENU
        print("  Panel.MENU opened successfully ->", win._current_view)

        win.open_panel(Panel.SETTINGS)
        win.update_view()
        assert win._panel == Panel.SETTINGS
        assert win._current_view == View.SETTINGS
        print("  Panel.SETTINGS opened successfully ->", win._current_view)

        win.open_panel(Panel.LOOK)
        win.update_view()
        assert win._panel == Panel.LOOK
        assert win._current_view == View.LOOK
        print("  Panel.LOOK opened successfully ->", win._current_view)

        # Test island height changes and layout stability
        win.set_height(16)
        win.set_targets()
        d_look = win.size_of(View.LOOK)
        assert win._h.target == d_look.h, f"Expanded panel height should remain {d_look.h}, got {win._h.target}"
        win._h.value = win._h.target
        px, py, pw, ph, _, _ = win._get_pill_and_bubble_rects()
        assert ph == d_look.h, f"Pill rect height should match target {d_look.h}, got {ph}"
        r_start, r_h, _ = win.get_look_layout(ph)
        # Test row 7 ("Высота острова") layout position
        r7_y = py + r_start + 7 * r_h
        win._row_list_look.move_to(r7_y, r_h, 7)
        assert win._row_list_look.hover_idx == 7
        assert win._row_list_look._top.target == r7_y
        win.set_height(0)
        win.set_targets()

        win.open_panel(Panel.TEXT_ANIM)
        win.update_view()
        assert win._panel == Panel.TEXT_ANIM
        assert win._current_view == View.TEXT_ANIM
        print("  Panel.TEXT_ANIM opened successfully ->", win._current_view)

        win.open_panel(Panel.COMBO)
        win.update_view()
        assert win._panel == Panel.COMBO
        assert win._current_view == View.COMBO
        print("  Panel.COMBO opened successfully ->", win._current_view)

        win.open_panel(Panel.SHELF)
        win.update_view()
        assert win._panel == Panel.SHELF
        assert win._current_view == View.SHELF
        print("  Panel.SHELF opened successfully ->", win._current_view)

        win.open_panel(Panel.UPDATE)
        win.update_view()
        assert win._panel == Panel.UPDATE
        assert win._current_view == View.UPDATE
        print("  Panel.UPDATE opened successfully ->", win._current_view)

        win.open_panel(Panel.EQUALIZER)
        win.update_view()
        assert win._panel == Panel.EQUALIZER
        assert win._current_view == View.EQUALIZER
        print("  Panel.EQUALIZER opened successfully ->", win._current_view)

        # Test equalizer toggles & dragging
        assert "compact_equalizer" in win._toggles
        assert "mini_equalizer" in win._toggles
        win._toggles["compact_equalizer"].set_state(True)
        assert win._toggles["compact_equalizer"].on is True
        win._toggles["compact_equalizer"].set_drag_fraction(0.2)
        assert abs(win._toggles["compact_equalizer"].progress - 0.2) < 1e-3
        win._toggles["compact_equalizer"].set_drag_fraction(0.85)
        assert abs(win._toggles["compact_equalizer"].progress - 0.85) < 1e-3
        win._apply_toggle_state("compact_equalizer", True)
        assert Settings.compact_equalizer is True
        win._apply_toggle_state("compact_equalizer", False)
        assert Settings.compact_equalizer is False

        # Test matrix fade strength setting and scrolling
        Settings.matrix_fade_strength = 70
        assert Settings.matrix_fade_strength == 70
        assert Settings.matrix_fade is True
        Settings.matrix_fade_strength = 0
        assert Settings.matrix_fade is False
        Settings.matrix_fade_strength = 50

        # Test slider module integration
        from slider import SLIDERS
        expected_keys = [
            "scale", "pos_y", "pos_x", "radius", "height", "text_scale", "glass",
            "lyric_anim_speed", "lyric_anim_height", "lyric_anim_stagger", "lyric_lead_sec",
            "combo_min_repeats", "combo_min_word_len",
            "compact_eq_bars", "eq_bars", "eq_sensitivity", "matrix_rows", "matrix_fade_strength", "matrix_opacity",
        ]
        for k in expected_keys:
            assert k in SLIDERS, f"Slider key missing: {k}"

        assert SLIDERS["scale"].get_min() == 75.0
        assert SLIDERS["scale"].get_max() == 130.0
        assert SLIDERS["text_scale"].get_min() == 75.0
        assert SLIDERS["text_scale"].get_max() == 130.0
        assert SLIDERS["height"].get_min() == 0.0
        assert SLIDERS["height"].get_max() == 16.0
        assert SLIDERS["lyric_anim_height"].get_min() == 15.0
        assert SLIDERS["lyric_anim_height"].get_max() == 80.0
        assert SLIDERS["lyric_lead_sec"].get_min() == 0.0
        assert SLIDERS["lyric_lead_sec"].get_max() == 9.0
        assert SLIDERS["lyric_lead_sec"].format_val(0) == "Выкл"
        assert SLIDERS["lyric_lead_sec"].format_val(5) == "5 сек"

        # Test dynamic screen limits
        assert SLIDERS["pos_x"].get_min(win) <= -300
        assert SLIDERS["pos_x"].get_max(win) >= 300
        assert SLIDERS["pos_y"].get_max(win) >= 200

        # Test interactive on_down / on_move / on_up & apply_step
        SLIDERS["scale"].on_down(0, 0, 100, win)
        SLIDERS["scale"].on_up(win)
        assert Settings.scale == 75
        SLIDERS["scale"].on_down(100, 0, 100, win)
        SLIDERS["scale"].on_up(win)
        assert Settings.scale == 130
        SLIDERS["scale"].apply_step(-10, win)
        assert Settings.scale == 120

        # Test cairo slider rendering
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 200, 40)
        cr_test = cairo.Context(surf)
        SLIDERS["scale"].render(cr_test, 10, 10, 80, 24, (1.0, 0.5, 0.0), 1.0)
        print("  All 19 modular sliders verified successfully!")

        win.start_timer(60.0)
        assert win._timer.active
        assert win._timer.running
        print("  Timer started (60s):", win._timer.formatted)

        win.destroy()
        Settings._data = dict(original_settings)
        Settings.save_now()
        print("\nAll interactive state transition tests PASSED!")
        application.quit()

    app.connect("activate", on_activate)
    app.run([])

if __name__ == "__main__":
    test_views()
