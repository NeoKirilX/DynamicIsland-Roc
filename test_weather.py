#!/usr/bin/env python3

import os
import sys
import time
import cairo

sys.path.insert(0, "/home/neokirilx/DynamicIsland-roc")

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from weather_service import WeatherService, WeatherInfo, format_temperature
from icon import Glyph, render_icon
from settings import Settings
from main_window import MainWindow, View, Dims


def test_weather_service():
    print("Testing WeatherService unit logic...")
    ws = WeatherService(auto_start=False)
    # Test simulation
    ws.simulate(temp=22.5, code=0, is_day=True, city="Москва")
    w = ws.current
    assert w is not None
    assert w.temperature == 22.5
    assert w.icon_glyph == Glyph.Sun
    assert format_temperature(23.0) == "+23°"
    assert format_temperature(-3.2) == "-3°"

    # Test rain glyph
    ws.simulate(temp=14.0, code=61, is_day=True, city="Москва")
    assert ws.current.icon_glyph == Glyph.CloudRain
    print("  WeatherService tests PASSED!")


def test_mainwindow_weather_integration():
    print("Testing MainWindow UI integration...")
    app = Gtk.Application(application_id="com.test.dynamicisland.weather")

    def on_activate(application):
        win = MainWindow(application)

        # Test size_of View.IDLE without weather
        Settings.weather = False
        idle_dims = win.size_of(View.IDLE)
        assert idle_dims.w == 118.0, f"Expected 118.0 for base IDLE, got {idle_dims.w}"

        # Test size_of View.IDLE with weather
        Settings.weather = True
        win._weather.simulate(temp=20.0, code=0, is_day=True, city="Москва")
        win._apply_weather_changed(win._weather.current)
        w_dims = win.size_of(View.IDLE)
        assert w_dims.w == 172.0, f"Expected 172.0 with weather, got {w_dims.w}"

        # Render idle view
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, int(w_dims.w) + 100, int(w_dims.h) + 100)
        cr = cairo.Context(surf)
        win.render_view(cr, View.IDLE, 50.0, 20.0, w_dims.w, w_dims.h, alpha=1.0)

        # Render idle_big view
        big_dims = win.size_of(View.IDLE_BIG)
        win.render_view(cr, View.IDLE_BIG, 20.0, 20.0, big_dims.w, big_dims.h, alpha=1.0)

        win.destroy()
        print("  MainWindow UI rendering tests PASSED!")

    app.connect("activate", on_activate)
    app.run([])


if __name__ == "__main__":
    test_weather_service()
    test_mainwindow_weather_integration()
    print("\nAll Weather integration tests completed successfully!")
