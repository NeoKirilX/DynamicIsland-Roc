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
from gi.repository import Gtk, GLib

from main_window import MainWindow, View, Panel
from settings import Settings
import cairo

def test_views():
    print("=" * 60)
    print("Testing DynamicIsland MainWindow and 14 Island Views...")
    print("=" * 60)

    app = Gtk.Application(application_id="com.github.neokirilx.test_views")

    views_to_test = [
        "Idle",
        "Media",
        "Timer",
        "Volume",
        "Charge",
        "Toast",
        "Notice",
        "MediaBig",
        "IdleBig",
        "TimerBig",
        "TimerSet",
        "Menu",
        "Settings",
        "Look",
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

        print("\nAll 14 views rendered successfully without errors!")

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
