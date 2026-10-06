#!/usr/bin/env python3

import os
import sys
import time
import cairo

sys.path.insert(0, "/home/neokirilx/DynamicIsland-roc")

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from privacy_service import PrivacyService, PrivacyState, _parse_wpctl_status
from weather_service import WeatherService, WeatherInfo, format_temperature
from icon import Glyph, render_icon
from settings import Settings
from main_window import MainWindow, View, Dims

def test_privacy_service():
    print("Testing PrivacyService unit logic...")
    # Test wpctl output parser
    sample_wpctl = """
Audio
 ├─ Devices:
 │      44. Built-in Audio
 ├─ Sinks:
 │  *   52. Built-in Audio Analog Stereo
 ├─ Sources:
 │  *   53. Built-in Audio Analog Stereo
 └─ Streams:
       173. Discord
            161. input_FL        < Loopback PCM:capture_FL\t[active]
            167. input_FR        < Loopback PCM:capture_FR\t[active]

Video
 ├─ Devices:
 │      54. Iriun Webcam
 └─ Streams:
       180. OBS Studio
            181. output_0        > Webcam:capture\t[active]
Settings
"""
    mic, cam, mic_apps, cam_apps = _parse_wpctl_status(sample_wpctl)
    assert mic is True, "Mic should be detected"
    assert cam is True, "Cam should be detected"
    assert "Discord" in mic_apps, f"Expected Discord in mic_apps, got {mic_apps}"
    assert "OBS Studio" in cam_apps, f"Expected OBS Studio in cam_apps, got {cam_apps}"

    # Test service simulation & callback
    events = []
    def on_priv_changed(st: PrivacyState):
        events.append(st)

    ps = PrivacyService(on_changed=on_priv_changed, auto_start=False)
    ps.simulate(mic=True, camera=False, apps=["Telegram"])
    assert ps.mic_active is True
    assert ps.camera_active is False
    assert ps.state.summary == "Микрофон"
    assert ps.state.primary_app == "Telegram"
    assert len(events) == 1

    ps.simulate(mic=True, camera=True, apps=["Zoom"])
    assert ps.mic_active is True
    assert ps.camera_active is True
    assert ps.state.summary == "Камера и микрофон"
    assert len(events) == 2

    ps.simulate()
    assert ps.state.active is False
    assert len(events) == 3
    print("  PrivacyService tests PASSED!")

def test_weather_service():
    print("Testing WeatherService unit logic...")
    assert format_temperature(21.4) == "+21°"
    assert format_temperature(-3.2) == "-3°"
    assert format_temperature(0.0) == "0°"

    # WMO code mapping
    w_sun = WeatherInfo.from_raw(temp=25.0, app_temp=26.0, code=0, is_day=True, city="Москва")
    assert w_sun.icon_glyph == Glyph.Sun
    assert w_sun.condition == "Ясно"
    assert w_sun.temp_str == "+25°"

    w_moon = WeatherInfo.from_raw(temp=14.0, app_temp=14.0, code=0, is_day=False, city="Москва")
    assert w_moon.icon_glyph == Glyph.Moon

    w_rain = WeatherInfo.from_raw(temp=10.0, app_temp=9.0, code=61, is_day=True, city="Москва")
    assert w_rain.icon_glyph == Glyph.CloudRain
    assert "Дождь" in w_rain.condition

    w_snow = WeatherInfo.from_raw(temp=-5.0, app_temp=-8.0, code=73, is_day=True, city="Москва")
    assert w_snow.icon_glyph == Glyph.CloudSnow

    events = []
    def on_weather_changed(w: WeatherInfo):
        events.append(w)

    ws = WeatherService(on_changed=on_weather_changed, auto_start=False)
    ws.simulate(temp=18.0, code=2, is_day=True, city="Казань")
    assert ws.has_weather is True
    assert ws.current.temp_str == "+18°"
    assert len(events) == 1
    print("  WeatherService tests PASSED!")

def test_main_window_integration():
    print("Testing MainWindow UI integration...")
    app = Gtk.Application(application_id="com.test.dynamicisland.privacy_weather")
    app.register()
    win = MainWindow(app)
    win._ready = True

    # 1. Test size_of View.IDLE without weather/privacy
    Settings.weather = False
    Settings.privacy_indicators = False
    base_dims = win.size_of(View.IDLE)
    assert base_dims.w == 118.0, f"Expected 118.0, got {base_dims.w}"

    # 2. Test size_of View.IDLE with weather
    Settings.weather = True
    win._weather.simulate(temp=20.0, code=1, is_day=True, city="Москва")
    weather_dims = win.size_of(View.IDLE)
    assert weather_dims.w == 172.0, f"Expected 172.0 with weather, got {weather_dims.w}"

    # 3. Test size_of View.IDLE with privacy indicators
    Settings.privacy_indicators = True
    win._privacy.simulate(mic=True, camera=True)
    priv_dims = win.size_of(View.IDLE)
    assert priv_dims.w == 172.0 + 18.0, f"Expected 190.0 with weather & privacy, got {priv_dims.w}"

    # 4. Render View.IDLE to Cairo surface
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 400, 200)
    cr = cairo.Context(surface)
    win.render_view(cr, View.IDLE, 50.0, 20.0, priv_dims.w, priv_dims.h, alpha=1.0)
    win.render_privacy_indicators(cr, 50.0, 20.0, priv_dims.w, priv_dims.h, alpha=1.0)

    # 5. Render View.IDLE_BIG with weather
    big_dims = win.size_of(View.IDLE_BIG)
    win.render_view(cr, View.IDLE_BIG, 20.0, 20.0, big_dims.w, big_dims.h, alpha=1.0)
    win.render_privacy_indicators(cr, 20.0, 20.0, big_dims.w, big_dims.h, alpha=1.0)

    # 6. Render Settings view with new privacy & weather toggles
    settings_dims = win.size_of(View.SETTINGS)
    win.render_view(cr, View.SETTINGS, 20.0, 20.0, settings_dims.w, settings_dims.h, alpha=1.0)

    print("  MainWindow UI rendering tests PASSED!")

if __name__ == "__main__":
    test_privacy_service()
    test_weather_service()
    test_main_window_integration()
    print("\nAll Privacy and Weather integration tests completed successfully!")
