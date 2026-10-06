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
        "Shelf",
        "Update",
    ]

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

        win.start_timer(60.0)
        assert win._timer.active
        assert win._timer.running
        print("  Timer started (60s):", win._timer.formatted)

        win.destroy()
        print("\nAll interactive state transition tests PASSED!")
        application.quit()

    app.connect("activate", on_activate)
    app.run([])

if __name__ == "__main__":
    test_views()
