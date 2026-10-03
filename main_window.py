#!/usr/bin/env python3

from __future__ import annotations

import ctypes
import datetime
import math
import os
import sys
import time
from enum import Enum, auto
from pathlib import Path
from typing import Any, Optional, Tuple

try:
    ctypes.CDLL("libgtk4-layer-shell.so", ctypes.RTLD_GLOBAL)
except Exception:
    pass

import cairo
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Gtk4LayerShell", "1.0")
from gi.repository import Gdk, GLib, Gtk, Gtk4LayerShell

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from alarm import Alarm
from audio_service import AudioService
from battery_service import get_power_status
from cover import Cover
from digits import Digits
from equalizer import Equalizer
from goo import Goo
from headset import get_headset_charge
from icon import Glyph, render_battery, render_icon
from lyric import LyricLine, measure_text, select_font
from lyrics_service import LyricsService
from media_service import MediaService
from native_wayland import is_ctrl_down, is_fullscreen
from network_service import Link, NetworkService, State
from ring import Ring
from row_list import RowList
from settings import Settings
from spectrum_service import SpectrumService
from spring import Spring
from timer_service import Countdown
from toggle import Toggle

try:
    from PIL import Image
except ImportError:
    Image = None

class View(Enum):
    IDLE = auto()
    MEDIA = auto()
    TIMER = auto()
    VOLUME = auto()
    CHARGE = auto()
    TOAST = auto()
    NOTICE = auto()
    MEDIA_BIG = auto()
    IDLE_BIG = auto()
    TIMER_BIG = auto()
    TIMER_SET = auto()
    MENU = auto()
    SETTINGS = auto()
    LOOK = auto()

class Panel(Enum):
    NONE = auto()
    PLAYER = auto()
    TIMER = auto()
    TIMER_SET = auto()
    MENU = auto()
    SETTINGS = auto()
    LOOK = auto()

class Dims:
    __slots__ = ("w", "h", "r")

    def __init__(self, w: float, h: float, r: float) -> None:
        self.w = float(w)
        self.h = float(h)
        self.r = float(r)

    def with_w(self, w: float) -> Dims:
        return Dims(w, self.h, self.r)

    def with_h(self, h: float) -> Dims:
        return Dims(self.w, h, self.r)

SIZES: dict[View, Dims] = {
    View.IDLE: Dims(118, 34, 17),
    View.MEDIA: Dims(210, 34, 17),
    View.TIMER: Dims(132, 34, 17),
    View.VOLUME: Dims(250, 34, 17),
    View.CHARGE: Dims(230, 34, 17),
    View.TOAST: Dims(340, 68, 30),
    View.NOTICE: Dims(320, 64, 29),
    View.MEDIA_BIG: Dims(380, 176, 40),
    View.IDLE_BIG: Dims(320, 124, 38),
    View.TIMER_BIG: Dims(330, 92, 40),
    View.TIMER_SET: Dims(300, 190, 38),
    View.MENU: Dims(300, 208, 34),
    View.SETTINGS: Dims(320, 374, 34),
    View.LOOK: Dims(320, 208, 34),
}

SCALES: list[int] = [85, 100, 115, 130]
GAPS: list[int] = [0, 4, 8, 12, 16, 24]
BUBBLE_WIDTH = 78.0
BUBBLE_HEIGHT = 34.0
BUBBLE_GAP = 7.0
MAX_MINUTES = 99
HEADSET_EVERY = 300
HEADSET_LOW = 20
HEADSET_CRITICAL = 10
TIMER_LAST = 10
SKIP_MEMORY = 3.0
VOLUME_TRACK = 162.0
VOLUME_PUSH = 7.0
SEEK_TRACK = 260.0
SEEK_THIN = 6.0
SEEK_HOVER = 9.0
SEEK_DRAG = 12.0
MEDIA_WIDTH = 210.0
MEDIA_MAX_WIDTH = 440.0
MEDIA_NAME_WIDTH = 300.0
LYRIC_INSET = 77.0
LYRIC_EDGE = 8.0
PLAYER_HEIGHT = 176.0
PLAYER_LYRIC_ROOM = 74.0
PLAYER_LYRIC_GAP = 4.0
PLAYER_LYRIC_PAD = 8.0
LYRIC_COMPACT_FONT = 13.0
PLAYER_LYRIC_FONT = 14.0
LYRIC_SPEED = 36.0
COLLAPSE_DELAY_SEC = 0.55
BUBBLE_LINGER_SEC = 2.5
AWAY_FOR_SEC = 5.0
PUSH_FOR_SEC = 0.14
PAUSED_GRACE_SEC = 30.0

COLOR_DIM = (1.0, 1.0, 1.0, 0.6)
COLOR_ORANGE = (1.0, 0.623, 0.039)
COLOR_GREEN = (0.188, 0.820, 0.345)
COLOR_RED = (1.0, 0.271, 0.227)
COLOR_WHITE = (1.0, 1.0, 1.0)

LOOK_COLORS = [
    (None, "Из обложки"),
    ((1.0, 1.0, 1.0), "Белый"),
    ((1.0, 0.271, 0.227), "Красный"),
    ((1.0, 0.623, 0.039), "Оранжевый"),
    ((1.0, 0.839, 0.039), "Жёлтый"),
    ((0.188, 0.820, 0.345), "Зелёный"),
    ((0.392, 0.824, 1.0), "Голубой"),
    ((0.039, 0.518, 1.0), "Синий"),
    ((0.749, 0.353, 0.949), "Фиолетовый"),
    ((1.0, 0.216, 0.373), "Розовый"),
]

def format_time(seconds: float) -> str:
    secs = max(0, int(seconds))
    mins = secs // 60
    s = secs % 60
    if mins >= 60:
        h = mins // 60
        mins %= 60
        return f"{h}:{mins:02d}:{s:02d}"
    return f"{mins}:{s:02d}"

def clip_rounded_rect(
    cr: cairo.Context, x: float, y: float, w: float, h: float, radius: float
) -> None:
    r = max(0.0, min(radius, min(w, h) / 2.0))
    if r <= 0.0:
        cr.rectangle(x, y, w, h)
    else:
        cr.new_sub_path()
        cr.arc(x + w - r, y + r, r, -math.pi / 2.0, 0.0)
        cr.arc(x + w - r, y + h - r, r, 0.0, math.pi / 2.0)
        cr.arc(x + r, y + h - r, r, math.pi / 2.0, math.pi)
        cr.arc(x + r, y + r, r, math.pi, 3.0 * math.pi / 2.0)
        cr.close_path()
    cr.clip()

def draw_rounded_rect(
    cr: cairo.Context, x: float, y: float, w: float, h: float, radius: float
) -> None:
    r = max(0.0, min(radius, min(w, h) / 2.0))
    if r <= 0.0:
        cr.rectangle(x, y, w, h)
        return
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2.0, 0.0)
    cr.arc(x + w - r, y + h - r, r, 0.0, math.pi / 2.0)
    cr.arc(x + r, y + h - r, r, math.pi / 2.0, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3.0 * math.pi / 2.0)
    cr.close_path()

def draw_text(
    cr: cairo.Context,
    text: str,
    x: float,
    y: float,
    font_size: float = 13.5,
    bold: bool = False,
    color: tuple = (1.0, 1.0, 1.0),
    alpha: float = 1.0,
    align: str = "left",
    valign: str = "center",
    max_w: Optional[float] = None,
) -> float:
    if not text or alpha <= 0.0:
        return 0.0
    select_font(cr, font_size=font_size, bold=bold)
    disp = text
    if max_w is not None and max_w > 0:
        ext = cr.text_extents(disp)
        if ext.width > max_w:
            while len(disp) > 1 and cr.text_extents(disp + "…").width > max_w:
                disp = disp[:-1]
            disp += "…"
    ext = cr.text_extents(disp)
    draw_x = x
    if align == "center":
        draw_x = x - ext.width / 2.0
    elif align == "right":
        draw_x = x - ext.width

    fe_ascent, fe_descent, _, _, _ = cr.font_extents()
    if valign == "center":
        draw_y = y + fe_ascent - (fe_ascent + fe_descent) / 2.0
    elif valign == "top":
        draw_y = y + fe_ascent
    else:
        draw_y = y

    r, g, b = color[0], color[1], color[2]
    a = (color[3] if len(color) > 3 else 1.0) * alpha
    cr.set_source_rgba(r, g, b, a)
    cr.move_to(draw_x, draw_y)
    cr.show_text(disp)
    return ext.width

_IMAGE_SURFACE_CACHE: dict[str, cairo.ImageSurface] = {}
_MEASURE_SURFACE = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1)
_MEASURE_CR = cairo.Context(_MEASURE_SURFACE)

def load_cairo_image(path: Optional[str]) -> Optional[cairo.ImageSurface]:
    if not path or not os.path.isfile(path) or Image is None:
        return None
    if path in _IMAGE_SURFACE_CACHE:
        return _IMAGE_SURFACE_CACHE[path]
    try:
        pil_img = Image.open(path).convert("RGBA")
        raw = bytearray(pil_img.tobytes("raw", "BGRA"))
        stride = cairo.ImageSurface.format_stride_for_width(cairo.FORMAT_ARGB32, pil_img.width)
        surf = cairo.ImageSurface.create_for_data(raw, cairo.FORMAT_ARGB32, pil_img.width, pil_img.height, stride)
        surf._keep_alive = raw
        _IMAGE_SURFACE_CACHE[path] = surf
        if len(_IMAGE_SURFACE_CACHE) > 30:
            old_k = next(iter(_IMAGE_SURFACE_CACHE))
            del _IMAGE_SURFACE_CACHE[old_k]
        return surf
    except Exception:
        return None

class MainWindow(Gtk.Window):

    def __init__(
        self,
        app: Gtk.Application,
        forced_view: Optional[str] = None,
        forced_timer: float = 0.0,
    ) -> None:
        super().__init__(application=app, title="Dynamic Island")
        self._last_tick_time = time.monotonic()
        self.set_decorated(False)
        self.set_resizable(False)

        self.win_width = 700
        self.win_height = 460
        self.set_default_size(self.win_width, self.win_height)

        self.is_layer_shell = Gtk4LayerShell.is_supported()
        if self.is_layer_shell:
            Gtk4LayerShell.init_for_window(self)
            Gtk4LayerShell.set_layer(self, Gtk4LayerShell.Layer.TOP)
            Gtk4LayerShell.set_anchor(self, Gtk4LayerShell.Edge.TOP, True)
            Gtk4LayerShell.set_anchor(self, Gtk4LayerShell.Edge.LEFT, False)
            Gtk4LayerShell.set_anchor(self, Gtk4LayerShell.Edge.RIGHT, False)
            Gtk4LayerShell.set_anchor(self, Gtk4LayerShell.Edge.BOTTOM, False)
            Gtk4LayerShell.set_margin(self, Gtk4LayerShell.Edge.TOP, 0)
            Gtk4LayerShell.set_keyboard_mode(self, Gtk4LayerShell.KeyboardMode.NONE)

        css_provider = Gtk.CssProvider()
        css_data = b"""
        window, window.background, .background, decoration, widget, drawingarea, .csd {
            background-color: transparent;
            background: transparent;
            background-image: none;
            box-shadow: none;
            border: none;
            outline: none;
        }
        """
        css_provider.load_from_data(css_data)
        display = Gdk.Display.get_default()
        if display:
            Gtk.StyleContext.add_provider_for_display(
                display, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_USER
            )

        self.area = Gtk.DrawingArea()
        self.area.set_draw_func(self.on_draw)
        self.set_child(self.area)

        self._ready = False
        self._media = MediaService(on_changed=self.on_media_changed)
        self._lyrics = LyricsService()
        self._lyrics.add_callback(self.update_lyric)
        self._audio = AudioService()
        self._spectrum = SpectrumService()
        self._network = NetworkService(on_changed=self.on_network_changed)
        self._timer = Countdown()
        self._alarm = Alarm()

        self._goo = Goo()
        self._cover_small = Cover()
        self._cover_toast = Cover()
        self._cover_big = Cover()
        self._eq_small = Equalizer(bars=5)
        self._eq_toast = Equalizer(bars=5)
        self._eq_big = Equalizer(bars=8)
        self._digits_timer = Digits("25:00", down=True)
        self._digits_bubble = Digits("25:00", down=True)
        self._digits_big_timer = Digits("25:00", down=True)
        self._digits_setup = Digits("25:00", down=True)
        self._digits_volume = Digits("0", down=True)
        self._row_list_menu = RowList()
        self._row_list_settings = RowList()
        self._row_list_look = RowList()

        self._toggles = {
            "lyrics": Toggle(Settings.lyrics),
            "lyric_effects": Toggle(Settings.lyric_effects),
            "rim": Toggle(Settings.rim),
            "app_volume": Toggle(Settings.app_volume),
            "network": Toggle(Settings.network),
            "hide_fullscreen": Toggle(Settings.hide_fullscreen),
            "click_lock": Toggle(Settings.click_lock),
            "autostart": Toggle(Settings.autostart),
        }

        self._w = Spring(34.0)
        self._h = Spring(34.0)
        self._r = Spring(17.0)
        self._scale = Spring(1.0)
        self._offset = Spring(-50.0)
        self._seek_x = Spring(0.0)
        self._seek_h = Spring(SEEK_THIN)
        self._split = Spring(0.0)
        self._bubble_scale = Spring(1.0)
        self._push = Spring(0.0)
        self._size = Spring(Settings.scale / 100.0)
        self._gap = Spring(float(Settings.gap))

        self._scale.tune(320, 20)
        self._offset.tune(260, 26)
        self._r.tune(300, 30)
        self._seek_x.tune(170, 26)
        self._seek_h.tune(420, 26)
        self._split.tune(140, 17)
        self._bubble_scale.tune(320, 20)
        self._push.tune(420, 18)
        self._size.tune(240, 26)
        self._gap.tune(240, 26)

        self._forced: Optional[View] = None
        if forced_view:
            for v in View:
                if v.name.lower() == forced_view.lower():
                    self._forced = v
                    break
        self._current_view: View = View.IDLE
        self._previous_view: Optional[View] = None
        self._view_transition: float = 1.0
        self._transient: Optional[View] = None
        self._transient_expiry: float = 0.0
        self._panel: Panel = Panel.NONE
        self._collapse_expiry: float = 0.0

        self._hover = False
        self._pressed = False
        self._bubble_hover = False
        self._bubble_pressed = False
        self._hidden = False
        self._away = False
        self._away_expiry: float = 0.0
        self._push_expiry: float = 0.0
        self._scrubbing = False
        self._scrub = 0.0
        self._scrub_until = 0.0
        self._ringing = False
        self._urgent = False
        self._minutes = 25
        self._click_lock_until = time.monotonic() + 0.45

        self._accent_color: tuple[float, float, float] = (1.0, 1.0, 1.0)
        self._timer_tint: tuple[float, float, float] = COLOR_ORANGE
        self._rim_tint: Optional[tuple[float, float, float]] = None

        self._notice_icon: Glyph = Glyph.Wifi
        self._notice_tint: tuple[float, float, float] = COLOR_WHITE
        self._notice_title: str = ""
        self._notice_text: str = ""

        self._player_vol_opacity = 0.0
        self._player_vol_expiry = 0.0
        self._player_vol_text = ""
        self._player_vol_is_app = False

        self._last_volume = -1.0
        self._last_muted = False
        self._last_plugged = False
        self._battery_known = False
        self._battery_pct = 100
        self._headset_pct = -1
        self._last_playing_time: float = 0.0
        self._clock_time_str = "00:00"
        self._clock_date_str = ""
        self._media_width = MEDIA_WIDTH
        self._player_room = False
        self._player_lyric_h = PLAYER_LYRIC_ROOM
        self._lyric_scroll = 0.0
        self._lyric_overflow = 0.0
        self._lyric_span = 0.0
        self._lyric_line_start = 0.0
        self._skip_direction = 1
        self._skip_at = -SKIP_MEMORY
        self._source_at = -SKIP_MEMORY
        self._source_app_name = ""
        self._last_track_key = ""
        self._last_lyric_text = ""

        self._btn_prev_rect: tuple[float, float, float, float] = (0, 0, 0, 0)
        self._btn_play_rect: tuple[float, float, float, float] = (0, 0, 0, 0)
        self._btn_next_rect: tuple[float, float, float, float] = (0, 0, 0, 0)
        self._btn_art_rect: tuple[float, float, float, float] = (0, 0, 0, 0)
        self._seek_rect: tuple[float, float, float, float] = (0, 0, 0, 0)

        self._mouse_x = -1000.0
        self._mouse_y = -1000.0

        self._ticks = 0

        self._setup_controllers()

        self._tick_cb_id = self.area.add_tick_callback(self.on_frame_tick)
        GLib.timeout_add(100, self.on_periodic_tick)

        self._ready = True
        GLib.idle_add(self._initial_media_sync, None)

        self.update_clock()
        self.sync_accent()
        self.update_view()
        self.set_targets()

        if forced_timer > 0:
            self.start_timer(forced_timer)

    def is_click_locked(self) -> bool:
        if not Settings.click_lock:
            return False
        now = time.monotonic()
        if now < self._click_lock_until:
            return True
        if abs(self._w.velocity) > 60.0 or abs(self._h.velocity) > 60.0:
            return True
        if self._view_transition < 0.75 and self._previous_view != self._current_view:
            return True
        return False

    def _setup_controllers(self) -> None:
        motion = Gtk.EventControllerMotion()
        motion.connect("enter", self.on_mouse_enter)
        motion.connect("leave", self.on_mouse_leave)
        motion.connect("motion", self.on_mouse_motion)
        self.area.add_controller(motion)

        click = Gtk.GestureClick()
        click.set_button(0)
        click.connect("pressed", self.on_mouse_pressed)
        click.connect("released", self.on_mouse_released)
        self.area.add_controller(click)

        scroll = Gtk.EventControllerScroll.new(Gtk.EventControllerScrollFlags.BOTH_AXES)
        scroll.connect("scroll", self.on_mouse_scroll)
        self.area.add_controller(scroll)

    def _get_pill_and_bubble_rects(self) -> Tuple[
        float, float, float, float, float,
        Optional[Tuple[float, float, float, float, float]]
    ]:
        size = max(0.01, self._size.value)
        scale = max(0.01, self._scale.value)
        w = max(24.0, self._w.value)
        h = max(24.0, self._h.value)
        r = min(w / 2.0, min(h / 2.0, max(0.0, self._r.value)))

        cx = self.win_width / 2.0
        offset_y = self._offset.value + self._gap.value / size
        pill_top = offset_y * size

        pill_x = -w / 2.0
        pill_y = 0.0

        split = self._split.value
        bubble_scale = max(0.01, self._bubble_scale.value)
        apart = split > 0.01

        bubble_info = None
        if apart:
            pill_right = w / 2.0
            past = ((BUBBLE_GAP + BUBBLE_WIDTH) * split - BUBBLE_WIDTH) / scale
            bx = pill_right + past
            by = 0.0
            bw = BUBBLE_WIDTH * bubble_scale / scale
            bh = BUBBLE_HEIGHT * bubble_scale / scale
            br = bh / 2.0
            bubble_info = (bx, by, bw, bh, br)

        return (pill_x, pill_y, w, h, r, bubble_info)

    def _screen_to_local(self, sx: float, sy: float) -> Tuple[float, float]:
        size = max(0.01, self._size.value)
        scale = max(0.01, self._scale.value)
        cx = self.win_width / 2.0
        offset_y = self._offset.value + self._gap.value / size
        pill_top = offset_y * size

        lx = (sx - cx) / (size * scale)
        ly = (sy - pill_top) / (size * scale)
        return lx, ly

    def on_mouse_enter(self, controller: Gtk.EventControllerMotion, x: float, y: float) -> None:
        self._hover = True
        self._collapse_expiry = 0.0
        self.set_targets()

    def on_mouse_leave(self, controller: Gtk.EventControllerMotion) -> None:
        self._hover = False
        self._pressed = False
        self._bubble_hover = False
        self._bubble_pressed = False
        self._row_list_menu.clear_hover()
        self._row_list_settings.clear_hover()
        self._row_list_look.clear_hover()
        self.set_targets()
        if self._panel != Panel.NONE:
            self._collapse_expiry = time.monotonic() + COLLAPSE_DELAY_SEC

    def on_mouse_motion(self, controller: Gtk.EventControllerMotion, x: float, y: float) -> None:
        self._mouse_x = x
        self._mouse_y = y
        lx, ly = self._screen_to_local(x, y)
        px, py, pw, ph, pr, bubble = self._get_pill_and_bubble_rects()

        if bubble and self._split.value > 0.75:
            bx, by, bw, bh, _ = bubble
            in_bubble = bx <= lx <= bx + bw and by <= ly <= by + bh
            if in_bubble != self._bubble_hover:
                self._bubble_hover = in_bubble
                self.set_targets()
        else:
            if self._bubble_hover:
                self._bubble_hover = False
                self.set_targets()

        if self._scrubbing and self._seek_rect[2] > 0:
            rx, _, rw, _ = self._seek_rect
            self._scrub = max(0.0, min(1.0, (lx - rx) / rw))
            self.area.queue_draw()

        if self._current_view == View.MENU:
            row_y_start = py + 36.0
            row_h = 40.0
            hovered = None
            for idx in range(4):
                ry = row_y_start + idx * row_h
                if px + 10 <= lx <= px + pw - 10 and ry <= ly < ry + row_h:
                    hovered = idx
                    self._row_list_menu.move_to(ry, row_h, idx)
                    break
            if hovered is None:
                self._row_list_menu.clear_hover()
            self.area.queue_draw()

        elif self._current_view == View.SETTINGS:
            row_y_start = py + 44.0
            row_h = 40.0
            hovered = None
            for idx in range(8):
                ry = row_y_start + idx * row_h
                if px + 10 <= lx <= px + pw - 10 and ry <= ly < ry + row_h:
                    hovered = idx
                    self._row_list_settings.move_to(ry, row_h, idx)
                    break
            if hovered is None:
                self._row_list_settings.clear_hover()
            self.area.queue_draw()

        elif self._current_view == View.LOOK:
            row_y_start = py + 44.0
            row_h = 40.0
            hovered = None
            for idx in range(2):
                ry = row_y_start + idx * row_h
                if px + 10 <= lx <= px + pw - 10 and ry <= ly < ry + row_h:
                    hovered = idx
                    self._row_list_look.move_to(ry, row_h, idx)
                    break
            if hovered is None:
                self._row_list_look.clear_hover()
            self.area.queue_draw()

    def on_mouse_pressed(self, gesture: Gtk.GestureClick, n_press: int, x: float, y: float) -> None:
        button = gesture.get_current_button()
        lx, ly = self._screen_to_local(x, y)
        px, py, pw, ph, pr, bubble = self._get_pill_and_bubble_rects()

        if button == 2:
            self.open_panel(Panel.NONE)
            self._away = True
            self._away_expiry = time.monotonic() + AWAY_FOR_SEC
            self.update_view()
            self.set_targets()
            return

        if button == 3:
            if self._panel in (Panel.SETTINGS, Panel.LOOK):
                self.open_panel(Panel.MENU)
            else:
                self.open_panel(Panel.NONE if self._panel == Panel.MENU else Panel.MENU)
            self.update_view()
            self.set_targets()
            return

        if button == 1:
            if self.is_click_locked():
                return

            if bubble and self._split.value > 0.75:
                bx, by, bw, bh, _ = bubble
                if bx <= lx <= bx + bw and by <= ly <= by + bh:
                    self._bubble_pressed = True
                    self.set_targets()
                    return

            if self._current_view == View.MEDIA_BIG:
                rx, ry, rw, rh = self._seek_rect
                if rx <= lx <= rx + rw and ry - 6 <= ly <= ry + rh + 6 and rw > 0 and self._media.duration > 1.0:
                    self._scrubbing = True
                    self._scrub = max(0.0, min(1.0, (lx - rx) / rw))
                    self._seek_x.tune(900, 60)
                    self.area.queue_draw()
                    return

            if self._current_view == View.MENU:
                self._row_list_menu.set_pressed(True)
            elif self._current_view == View.SETTINGS:
                self._row_list_settings.set_pressed(True)
            elif self._current_view == View.LOOK:
                self._row_list_look.set_pressed(True)

            self._pressed = True
            self.set_targets()

    def on_mouse_released(self, gesture: Gtk.GestureClick, n_press: int, x: float, y: float) -> None:
        button = gesture.get_current_button()
        if button != 1:
            return

        if self.is_click_locked():
            self._pressed = False
            self._bubble_pressed = False
            self._scrubbing = False
            self._row_list_menu.set_pressed(False)
            self._row_list_settings.set_pressed(False)
            self._row_list_look.set_pressed(False)
            self.set_targets()
            return

        lx, ly = self._screen_to_local(x, y)
        px, py, pw, ph, pr, bubble = self._get_pill_and_bubble_rects()

        if self._bubble_pressed:
            self._bubble_pressed = False
            self.open_panel(Panel.TIMER)
            self.update_view()
            self.set_targets()
            self._collapse_expiry = time.monotonic() + BUBBLE_LINGER_SEC
            return

        if self._scrubbing:
            self._scrubbing = False
            self._seek_x.tune(170, 26)
            self._scrub_until = time.monotonic() + 1.0
            self._media.seek_fraction(self._scrub)
            self.area.queue_draw()
            return

        self._row_list_menu.set_pressed(False)
        self._row_list_settings.set_pressed(False)
        self._row_list_look.set_pressed(False)

        if not self._pressed:
            return
        self._pressed = False

        if self._ringing:
            self.quiet_alarm()
            self.open_panel(Panel.NONE)
            self.update_view()
            self.set_targets()
            return

        if self._current_view == View.MEDIA_BIG:
            bx, by, bw, bh = self._btn_prev_rect
            if bx <= lx <= bx + bw and by <= ly <= by + bh:
                self.skipped(-1)
                self._media.previous()
                return

            bx, by, bw, bh = self._btn_play_rect
            if bx <= lx <= bx + bw and by <= ly <= by + bh:
                self._media.toggle_play()
                return

            bx, by, bw, bh = self._btn_next_rect
            if bx <= lx <= bx + bw and by <= ly <= by + bh:
                self.skipped(1)
                self._media.next()
                return

            bx, by, bw, bh = self._btn_art_rect
            if bx <= lx <= bx + bw and by <= ly <= by + bh:
                self._media.raise_player()
                self.open_panel(Panel.NONE)
                self.update_view()
                self.set_targets()
                return

        if self._current_view == View.TIMER_BIG:
            if px + 20 <= lx <= px + 70 and py + 21 <= ly <= py + 71:
                self._timer.toggle()
                self.sync_timer()
                return
            if px + 80 <= lx <= px + 130 and py + 21 <= ly <= py + 71:
                self.stop_timer()
                self.open_panel(Panel.NONE)
                self.update_view()
                self.set_targets()
                return

        if self._current_view == View.TIMER_SET:
            if px + 16 <= lx <= px + 56 and py + 42 <= ly <= py + 82:
                self.set_minutes(self._minutes - 1)
                return
            if px + pw - 56 <= lx <= px + pw - 16 and py + 42 <= ly <= py + 82:
                self.set_minutes(self._minutes + 1)
                return
            presets = [5, 10, 15, 25, 45]
            chip_y = py + 98.0
            chip_h = 28.0
            chip_w = (pw - 28.0) / 5.0
            for idx, p_min in enumerate(presets):
                cx_chip = px + 14.0 + idx * chip_w
                if cx_chip <= lx <= cx_chip + chip_w and chip_y <= ly <= chip_y + chip_h:
                    self.set_minutes(p_min)
                    return
            if px + 16 <= lx <= px + pw - 16 and py + 138 <= ly <= py + 174:
                self.start_timer(self._minutes * 60)
                return

        if self._current_view == View.MENU:
            row_y_start = py + 36.0
            row_h = 40.0
            for idx in range(4):
                ry = row_y_start + idx * row_h
                if px + 10 <= lx <= px + pw - 10 and ry <= ly < ry + row_h:
                    if idx == 0:
                        self.open_panel(Panel.TIMER if self._timer.active else Panel.TIMER_SET)
                    elif idx == 1:
                        self.open_panel(Panel.SETTINGS)
                    elif idx == 2:
                        self.open_panel(Panel.LOOK)
                    elif idx == 3:
                        self.exit_island()
                    self.update_view()
                    self.set_targets()
                    return

        if self._current_view == View.SETTINGS:
            if px + 10 <= lx <= px + 150 and py + 12 <= ly <= py + 40:
                self.open_panel(Panel.MENU)
                self.update_view()
                self.set_targets()
                return

            row_y_start = py + 44.0
            row_h = 40.0
            setting_keys = [
                "lyrics",
                "lyric_effects",
                "rim",
                "app_volume",
                "network",
                "hide_fullscreen",
                "click_lock",
                "autostart",
            ]
            for idx, key in enumerate(setting_keys):
                ry = row_y_start + idx * row_h
                if px + 10 <= lx <= px + pw - 10 and ry <= ly < ry + row_h:
                    cur = getattr(Settings, key)
                    setattr(Settings, key, not cur)
                    self._toggles[key].set_state(not cur, animate=True)
                    if key == "rim":
                        self.sync_rim()
                    elif key == "lyrics":
                        self.track_lyrics()
                    elif key == "hide_fullscreen":
                        self.check_fullscreen()
                    self.area.queue_draw()
                    return

        if self._current_view == View.LOOK:
            if px + 10 <= lx <= px + 150 and py + 12 <= ly <= py + 40:
                self.open_panel(Panel.MENU)
                self.update_view()
                self.set_targets()
                return

            if px + 10 <= lx <= px + pw - 10 and py + 44 <= ly < py + 84:
                idx = SCALES.index(Settings.scale) if Settings.scale in SCALES else 1
                new_scale = SCALES[(idx + 1) % len(SCALES)]
                self.set_scale(new_scale)
                return

            if px + 10 <= lx <= px + pw - 10 and py + 84 <= ly < py + 124:
                idx = GAPS.index(Settings.gap) if Settings.gap in GAPS else 2
                new_gap = GAPS[(idx + 1) % len(GAPS)]
                self.set_gap(new_gap)
                return

            swatch_y = py + 160.0
            swatch_h = 30.0
            step_x = (pw - 20.0) / len(LOOK_COLORS)
            for idx, (col, _) in enumerate(LOOK_COLORS):
                sx = px + 10.0 + idx * step_x + step_x / 2.0
                if sx - 14 <= lx <= sx + 14 and swatch_y <= ly <= swatch_y + swatch_h:
                    Settings.accent = col
                    self.sync_accent()
                    self.sync_rim()
                    self.area.queue_draw()
                    return

        if self._panel != Panel.NONE:
            self.open_panel(Panel.NONE)
        else:
            if self.media_active or not self._timer.active:
                self.open_panel(Panel.PLAYER)
            else:
                self.open_panel(Panel.TIMER)

        self.update_view()
        self.set_targets()

    def on_mouse_scroll(
        self, controller: Gtk.EventControllerScroll, dx: float, dy: float
    ) -> bool:
        up = dy < 0 or dx < 0
        step = 1 if up else -1

        if is_ctrl_down():
            self.switch_source(-step)
            return True

        if self._current_view == View.TIMER_SET:
            self.set_minutes(self._minutes + step)
            return True

        lx, ly = self._screen_to_local(self._mouse_x, self._mouse_y)
        px, py, pw, ph, _, _ = self._get_pill_and_bubble_rects()

        if self._current_view == View.LOOK:
            if py + 44 <= ly < py + 84:
                idx = SCALES.index(Settings.scale) if Settings.scale in SCALES else 1
                new_idx = max(0, min(len(SCALES) - 1, idx + step))
                self.set_scale(SCALES[new_idx])
                return True
            if py + 84 <= ly < py + 124:
                idx = GAPS.index(Settings.gap) if Settings.gap in GAPS else 2
                new_idx = max(0, min(len(GAPS) - 1, idx + step))
                self.set_gap(GAPS[new_idx])
                return True

        if self._current_view == View.MEDIA_BIG and Settings.app_volume:
            app_id = self._media.source
            nudged = self._audio.nudge(app_id, step * 0.02)
            if isinstance(nudged, tuple) and nudged[0]:
                self.show_player_volume(nudged[1], False, is_app=True)
                return True

        if self.volume_at_end(up):
            self.push_volume(up)
        else:
            new_vol = self._audio.nudge(step * 0.02)
            if isinstance(new_vol, (int, float)):
                new_vol = float(new_vol)
                self._last_volume = new_vol
                pct = int(round(new_vol * 100))
                self._digits_volume.down = pct < int(self._digits_volume.text or "0")
                self._digits_volume.set_text(str(pct))
                self.show_transient(View.VOLUME, 1.6)
                self.show_player_volume(new_vol, False, is_app=False)
                self.area.queue_draw()

        return True

    @property
    def media_active(self) -> bool:
        return self._media.has_track and (
            self._media.is_playing
            or (time.monotonic() - self._last_playing_time < PAUSED_GRACE_SEC)
        )

    def update_view(self) -> None:
        target = self._forced
        if target is None:
            if self._panel == Panel.MENU:
                target = View.MENU
            elif self._panel == Panel.SETTINGS:
                target = View.SETTINGS
            elif self._panel == Panel.LOOK:
                target = View.LOOK
            elif self._panel == Panel.TIMER_SET:
                target = View.TIMER_SET
            elif self._panel == Panel.TIMER and self._timer.active:
                target = View.TIMER_BIG
            elif self._panel in (Panel.TIMER, Panel.PLAYER):
                target = View.MEDIA_BIG if self._media.has_track else View.IDLE_BIG
            else:
                target = self._transient or (
                    View.MEDIA
                    if self.media_active
                    else View.TIMER
                    if self._timer.active
                    else View.IDLE
                )

        if target == View.TOAST and not self._media.has_track:
            target = View.IDLE

        if target == self._current_view:
            self.sync_spectrum()
            self.sync_rim()
            return

        from_dims = self.size_of(self._current_view)
        self._previous_view = self._current_view
        self._current_view = target
        self._view_transition = 0.0

        if target == View.MEDIA_BIG:
            self.update_player_lyric(snap=True)
            self._seek_x.value = 0.0
            self._seek_x.velocity = 0.0
        elif target == View.MEDIA:
            self.update_lyric(snap=True)

        to_dims = self.size_of(target)
        growing = (to_dims.w * to_dims.h) >= (from_dims.w * from_dims.h)
        self._w.tune(300 if growing else 340, 22 if growing else 30)
        self._h.tune(300 if growing else 340, 22 if growing else 30)

        self.set_targets()
        self.sync_spectrum()
        self.sync_rim()

    def size_of(self, view: View) -> Dims:
        d = SIZES[view]
        if view == View.MEDIA:
            return d.with_w(self._media_width)
        if view == View.MEDIA_BIG and self._player_room:
            return d.with_h(PLAYER_HEIGHT + self._player_lyric_h)
        return d

    def set_targets(self) -> None:
        d = self.size_of(self._current_view)
        compact = d.h < 40.0
        self._w.target = d.w
        self._h.target = d.h
        self._r.target = d.r

        self._split.target = 1.0 if (self._timer.active and compact and self._current_view != View.TIMER) else 0.0

        if (self._hidden or self._away) and not self._ringing:
            self._offset.target = -(d.h + 30.0 + Settings.gap * 100.0 / Settings.scale)
        else:
            self._offset.target = 0.0

        self._scale.target = (
            (0.93 if compact else 0.975)
            if self._pressed
            else (1.07 if (self._hover and compact) else 1.0)
        )
        self._bubble_scale.target = (
            0.93 if self._bubble_pressed else (1.07 if self._bubble_hover else 1.0)
        )
        self.area.queue_draw()

    def open_panel(self, panel: Panel) -> None:
        if panel != self._panel and panel != Panel.NONE:
            self._click_lock_until = time.monotonic() + 0.38
        self._panel = panel
        self._transient = None
        self._transient_expiry = 0.0
        self.quiet_alarm()

    def show_transient(self, view: View, seconds: float, force: bool = False) -> None:
        if force:
            self._panel = Panel.NONE
        elif self._panel != Panel.NONE or self._hidden or self._away:
            return
        self._transient = view
        self._transient_expiry = time.monotonic() + seconds
        self.update_view()

    def notify(
        self,
        glyph: Glyph,
        tint: tuple[float, float, float],
        title: str,
        text: str,
        seconds: float = 3.2,
        force: bool = False,
    ) -> None:
        if self._ringing and not force:
            return
        self._notice_icon = glyph
        self._notice_tint = tint
        self._notice_title = title
        self._notice_text = text
        self.show_transient(View.NOTICE, seconds, force=force)

    @property
    def accent(self) -> tuple[float, float, float]:
        return Settings.accent or self._media.accent or (1.0, 1.0, 1.0)

    def sync_accent(self) -> None:
        self._accent_color = self.accent

    def sync_rim(self) -> None:
        music = (
            self._media.has_track
            and (self.media_active or self._current_view == View.MEDIA_BIG)
        )
        tint = self.accent if (Settings.rim and music) else None
        if tint != self._rim_tint:
            self._rim_tint = tint
            self._goo.tint(tint, duration_sec=0.45)

    def sync_spectrum(self) -> None:
        visible = self._current_view in (View.MEDIA, View.TOAST, View.MEDIA_BIG)
        self._spectrum.active = visible and self._media.is_playing

    def on_frame_tick(self, widget: Gtk.Widget, frame_clock: Gdk.FrameClock) -> bool:
        now = time.monotonic()
        dt = min(now - self._last_tick_time, 0.05)
        self._last_tick_time = now
        if dt <= 0.0:
            return True

        moving = self._w.advance(dt)
        moving |= self._h.advance(dt)
        moving |= self._r.advance(dt)
        moving |= self._scale.advance(dt)
        moving |= self._offset.advance(dt)
        moving |= self._size.advance(dt)
        moving |= self._gap.advance(dt)
        moving |= self._split.advance(dt)
        moving |= self._bubble_scale.advance(dt)
        moving |= self._push.advance(dt)

        if self._current_view == View.MEDIA_BIG or self._scrubbing:
            dur = self._media.duration
            known = dur >= 1.0
            played = max(0.0, min(1.0, self._media.position / dur)) if known else 0.0
            if not self._scrubbing and now < self._scrub_until and abs(played - self._scrub) < 0.02:
                self._scrub_until = 0.0
            shown = self._scrub if (self._scrubbing or now < self._scrub_until) else played
            self._seek_x.target = SEEK_TRACK * shown
            self._seek_h.target = (
                SEEK_DRAG if self._scrubbing else (SEEK_HOVER if self._hover else SEEK_THIN)
            )
            moving |= self._seek_x.advance(dt)
            moving |= self._seek_h.advance(dt)

        if self._current_view == View.MEDIA and self._lyric_overflow > 0.0 and Settings.lyrics:
            moving |= self._advance_lyric_scroll(dt)

        if self._current_view in (View.MEDIA, View.TOAST, View.MEDIA_BIG):
            bands = self._spectrum.get_bands()
            peak = self._audio.peak()
            playing = self._media.is_playing
            moving |= self._eq_small.tick(bands, peak, playing, now, dt)
            moving |= self._eq_toast.tick(bands, peak, playing, now, dt)
            moving |= self._eq_big.tick(bands, peak, playing, now, dt)

        moving |= self._cover_small.tick(dt)
        moving |= self._cover_toast.tick(dt)
        moving |= self._cover_big.tick(dt)
        moving |= self._digits_timer.tick(dt)
        moving |= self._digits_bubble.tick(dt)
        moving |= self._digits_big_timer.tick(dt)
        moving |= self._digits_setup.tick(dt)
        moving |= self._digits_volume.tick(dt)
        moving |= self._row_list_menu.tick(dt)
        moving |= self._row_list_settings.tick(dt)
        moving |= self._row_list_look.tick(dt)

        for tog in self._toggles.values():
            moving |= tog.tick(dt)

        if self._view_transition < 1.0:
            self._view_transition = min(1.0, self._view_transition + dt / 0.22)
            moving = True

        if self._player_vol_opacity > 0:
            if now > self._player_vol_expiry:
                self._player_vol_opacity = max(0.0, self._player_vol_opacity - dt * 2.5)
                moving = True

        if moving or self._media.is_playing or self._timer.running or self._ringing:
            self.area.queue_draw()

        if moving:
            self.update_input_region()
        return True

    def on_periodic_tick(self) -> bool:
        self._ticks += 1
        now = time.monotonic()

        if self._transient and now >= self._transient_expiry:
            self._transient = None
            self.quiet_alarm()
            self.update_view()

        if self._collapse_expiry > 0.0 and now >= self._collapse_expiry:
            self._collapse_expiry = 0.0
            if not self._hover:
                self._panel = Panel.NONE
                self.update_view()

        if self._away and now >= self._away_expiry:
            self._away = False
            self.set_targets()

        if self._push_expiry > 0.0 and now >= self._push_expiry:
            self._push_expiry = 0.0
            self._push.target = 0.0

        self.poll_volume()
        self.update_timer()
        self.update_lyric()

        if self._ticks % HEADSET_EVERY == 1:
            self.read_headset()

        if self._ticks % 5 == 0:
            self.check_fullscreen()

        if self._ticks % 10 == 0:
            self.update_clock()
            self.poll_power()
            if self._media.is_playing:
                self._last_playing_time = now
            self.update_view()

        return True

    def update_input_region(self) -> None:
        surf = self.get_surface()
        if not surf:
            return

        size = max(0.01, self._size.value)
        scale = max(0.01, self._scale.value)
        w = max(24.0, self._w.value)
        h = max(24.0, self._h.value)
        cx = self.win_width / 2.0
        offset_y = self._offset.value + self._gap.value / size
        pill_top = offset_y * size

        pill_left_win = cx - (w * scale * size) / 2.0
        pill_top_win = pill_top
        pill_w_win = w * scale * size
        pill_h_win = h * scale * size

        reg = cairo.Region(
            cairo.RectangleInt(
                int(pill_left_win),
                int(pill_top_win),
                int(math.ceil(pill_w_win)),
                int(math.ceil(pill_h_win)),
            )
        )

        if self._split.value > 0.01:
            pill_right = w / 2.0
            past = ((BUBBLE_GAP + BUBBLE_WIDTH) * self._split.value - BUBBLE_WIDTH) / scale
            bx = pill_right + past
            bw = BUBBLE_WIDTH * max(0.01, self._bubble_scale.value) / scale
            bh = BUBBLE_HEIGHT * max(0.01, self._bubble_scale.value) / scale

            b_left_win = cx + bx * scale * size
            b_top_win = pill_top
            b_w_win = bw * scale * size
            b_h_win = bh * scale * size
            reg.union(
                cairo.RectangleInt(
                    int(b_left_win),
                    int(b_top_win),
                    int(math.ceil(b_w_win)),
                    int(math.ceil(b_h_win)),
                )
            )

        surf.set_input_region(reg)

    def check_fullscreen(self) -> None:
        hidden = Settings.hide_fullscreen and is_fullscreen()
        if hidden != self._hidden:
            self._hidden = hidden
            self.set_targets()

    def update_clock(self) -> None:
        now = datetime.datetime.now()
        self._clock_time_str = now.strftime("%H:%M")
        days = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
        months = [
            "января", "февраля", "марта", "апреля", "мая", "июня",
            "июля", "августа", "сентября", "октября", "ноября", "декабря"
        ]
        d_name = days[now.weekday()]
        m_name = months[now.month - 1]
        self._clock_date_str = f"{d_name}, {now.day} {m_name}"

    def poll_volume(self) -> None:
        _, level, muted = self._audio.try_get_volume()
        switched, dev = self._audio.take_switch()
        if switched and dev:
            self._last_volume = -1.0
            self.read_headset(dev, announce=True)

        first = self._last_volume < 0
        if not first and abs(level - self._last_volume) < 0.004 and muted == self._last_muted:
            return

        self._last_volume = level
        self._last_muted = muted
        pct = int(round(level * 100))
        self._digits_volume.down = pct < int(self._digits_volume.text or "0")
        self._digits_volume.set_text(str(pct))

        if first:
            return

        self.show_transient(View.VOLUME, 1.6)
        self.show_player_volume(level, muted, is_app=False)

    def volume_at_end(self, up: bool) -> bool:
        return (
            self._last_volume >= 0
            and ((not self._last_muted and self._last_volume >= 0.999) if up else self._last_volume <= 0.001)
        )

    def push_volume(self, up: bool) -> None:
        self._push.target = VOLUME_PUSH
        self._push_expiry = time.monotonic() + PUSH_FOR_SEC
        self.show_transient(View.VOLUME, 1.6)
        self.show_player_volume(self._last_volume, self._last_muted, is_app=False)
        self.area.queue_draw()

    def show_player_volume(self, level: float, muted: bool, is_app: bool) -> None:
        if self._current_view != View.MEDIA_BIG:
            return
        self._player_vol_is_app = is_app
        self._player_vol_text = "выкл" if muted else f"{int(round(level * 100))}%"
        self._player_vol_opacity = 1.0
        self._player_vol_expiry = time.monotonic() + 1.8
        self.area.queue_draw()

    def poll_power(self) -> None:
        has_bat, percent, plugged = get_power_status()
        if not has_bat:
            return
        self._battery_pct = percent
        if self._battery_known and plugged and not self._last_plugged:
            self.show_transient(View.CHARGE, 3.0)
        self._battery_known = True
        self._last_plugged = plugged

    def read_headset(self, device: Optional[Any] = None, announce: bool = False) -> None:
        level = get_headset_charge()
        was = self._headset_pct
        self._headset_pct = level
        known = level >= 0
        low = known and level <= HEADSET_LOW

        if announce:
            dev_name = getattr(device, "name", "Аудиоустройство")
            name = f"{dev_name} · {level}%" if known else dev_name
            self.notify(Glyph.Headphones, COLOR_WHITE, "Аудиоустройство", name)
        elif known and was > HEADSET_LOW and level <= HEADSET_LOW:
            self.notify(Glyph.Headphones, COLOR_RED, "Низкий заряд", f"Наушники · {level}%")

    def on_network_changed(self, was: State, now: State) -> None:
        if not self._ready or not Settings.network:
            return
        if now.vpn != was.vpn:
            if now.vpn:
                self.notify(Glyph.Vpn, COLOR_GREEN, "VPN включён", now.vpn.splitlines()[0])
            else:
                self.notify(Glyph.Vpn, COLOR_DIM[:3], "VPN отключён", was.vpn.splitlines()[0])
            return

        if now.link == Link.NONE:
            self.notify(Glyph.Offline, COLOR_RED, "Нет сети", "Подключение потеряно")
            return

        wifi = now.link == Link.WIFI
        title = "Ethernet" if now.link == Link.WIRED else (now.name if now.name else ("Wi-Fi" if wifi else "Мобильная сеть"))
        if now.internet:
            self.notify(Glyph.Wifi if wifi else Glyph.Wired, COLOR_GREEN, title, "Wi-Fi подключён" if wifi else "Сеть подключена")
        else:
            self.notify(Glyph.Wifi if wifi else Glyph.Wired, COLOR_ORANGE, title, "Без доступа к интернету")

    def _initial_media_sync(self, _data: object = None) -> bool:
        self.on_media_changed()
        return False

    def on_media_changed(self) -> None:
        if not self._ready:
            return

        title = self._media.title if self._media.has_track else ""
        new_track = bool(title and title != self._last_track_key)
        self._last_track_key = title

        if new_track:
            self._player_lyric_h = PLAYER_LYRIC_ROOM
            self._lyric_scroll = 0.0

        asked = time.monotonic() - self._source_at < SKIP_MEMORY
        source = self._media.source
        turned = source != self._source_app_name and asked
        if source != self._source_app_name:
            self._source_app_name = source
        self._last_playing_time = time.monotonic()

        art_surf = load_cairo_image(self._media.art_path)
        heading = self._skip_direction if (time.monotonic() - self._skip_at < SKIP_MEMORY) else 1
        self._cover_small.show(art_surf, heading)
        self._cover_toast.show(art_surf, heading)
        self._cover_big.show(art_surf, heading)

        self.sync_accent()
        self.sync_rim()

        if turned or (new_track and self._media.is_playing):
            self.show_transient(View.TOAST, 3.2)

        self.track_lyrics()
        self.update_view()
        self.update_lyric()

    def skipped(self, direction: int) -> None:
        self._skip_direction = direction
        self._skip_at = time.monotonic()

    def switch_source(self, direction: int) -> None:
        now = time.monotonic()
        if now - self._source_at < 0.25 or not self._media.switch(direction):
            return
        self._source_at = now
        self.skipped(direction)

    def track_lyrics(self) -> None:
        if Settings.lyrics and self._media.has_track:
            self._lyrics.track(self._media.title, self._media.artist, self._media.duration)
        else:
            self._lyrics.clear()
            self._last_lyric_text = ""

    def update_lyric(self, snap: bool = False) -> None:
        if self._current_view == View.MEDIA_BIG:
            self.update_player_lyric(snap)
        if self._current_view != View.MEDIA:
            return

        lines = self._lyrics.for_duration(self._media.duration)
        idx, current_line = self._lyrics.get_current_line(self._media.position, self._media.duration, lead=0.2)
        text = current_line[1] if current_line else (self._media.title if self._media.has_track else "")

        if text != self._last_lyric_text or snap:
            self._last_lyric_text = text
            if text:
                select_font(_MEASURE_CR, font_size=LYRIC_COMPACT_FONT, bold=True)
                tw = _MEASURE_CR.text_extents(text).x_advance
                self._lyric_span = 0.0
                self._lyric_line_start = 0.0
                if idx >= 0 and idx < len(lines):
                    self._lyric_line_start = lines[idx][0]
                    if idx + 1 < len(lines):
                        self._lyric_span = max(0.3, lines[idx + 1][0] - lines[idx][0])
                self._media_width = max(
                    MEDIA_WIDTH,
                    min(MEDIA_MAX_WIDTH, tw + 2 * LYRIC_EDGE + LYRIC_INSET + 2.0),
                )
                box = self._media_width - LYRIC_INSET
                self._lyric_overflow = max(0.0, tw - (box - 2 * LYRIC_EDGE))
            else:
                self._media_width = MEDIA_WIDTH
                self._lyric_span = 0.0
                self._lyric_line_start = 0.0
                self._lyric_overflow = 0.0

            self._lyric_scroll = 0.0

            if not snap:
                self._w.tune(280, 30)
            self.set_targets()

    def _advance_lyric_scroll(self, dt: float) -> bool:
        span = self._lyric_span if self._lyric_span > 0.0 else 3.0
        elapsed = max(0.0, min(span, self._media.position - self._lyric_line_start))
        hold = min(0.6, span * 0.2)
        run = min(self._lyric_overflow / LYRIC_SPEED, max(span - hold - 0.5, 0.6))
        if elapsed <= hold:
            target = 0.0
        else:
            k = min(1.0, max(0.0, (elapsed - hold) / run))
            target = -self._lyric_overflow * (0.5 - 0.5 * math.cos(math.pi * k))

        if abs(target - self._lyric_scroll) < 0.05:
            if self._lyric_scroll != target:
                self._lyric_scroll = target
                return True
            return False

        self._lyric_scroll += (target - self._lyric_scroll) * min(1.0, dt * 14.0)
        return True

    def update_player_lyric(self, snap: bool = False) -> None:
        lines = self._lyrics.for_duration(self._media.duration)
        room = len(lines) > 0 or (self._player_room and self._lyrics.pending)
        if room != self._player_room:
            self._player_room = room
            self._h.tune(280, 30)
            self.set_targets()

    def start_timer(self, seconds: float) -> None:
        self._timer.start(seconds)
        self.open_panel(Panel.NONE)
        self.sync_timer()
        self.update_view()
        self.set_targets()

    def stop_timer(self) -> None:
        self._timer.stop()
        self.set_urgent(False)

    def sync_timer(self) -> None:
        self.update_timer()

    def update_timer(self) -> None:
        if not self._timer.active:
            return
        left = self._timer.left
        if left <= 0.0:
            self.timer_done()
            return

        formatted = self._timer.formatted
        self._digits_timer.set_text(formatted)
        self._digits_bubble.set_text(formatted)
        self._digits_big_timer.set_text(formatted)
        self.set_urgent(self._timer.is_urgent)

    def set_urgent(self, on: bool) -> None:
        if on != self._urgent:
            self._urgent = on
            self._timer_tint = COLOR_RED if on else COLOR_ORANGE

    def timer_done(self) -> None:
        total_span = format_time(self._timer.total)
        self.stop_timer()
        self._ringing = True
        self._alarm.ring()
        self.notify(Glyph.Bell, COLOR_ORANGE, "Таймер", f"Время вышло · {total_span}", seconds=12.0, force=True)
        self.set_targets()

    def quiet_alarm(self) -> None:
        if not self._ringing:
            return
        self._ringing = False
        self._alarm.stop()

    def set_minutes(self, minutes: int) -> None:
        clamped = max(1, min(MAX_MINUTES, minutes))
        self._digits_setup.down = clamped < self._minutes
        self._minutes = clamped
        self._digits_setup.set_text(f"{self._minutes}:00")
        self.area.queue_draw()

    def set_scale(self, percent: int) -> None:
        Settings.scale = percent
        self._size.target = percent / 100.0
        self.set_targets()

    def set_gap(self, px: int) -> None:
        Settings.gap = px
        self._gap.target = float(px)
        self.set_targets()

    def exit_island(self) -> None:
        self._alarm.stop()
        self.get_application().quit()

    def on_draw(self, area: Gtk.DrawingArea, cr: cairo.Context, width: int, height: int, user_data=None) -> None:
        cr.save()
        cr.set_operator(cairo.OPERATOR_CLEAR)
        cr.paint()
        cr.restore()
        cr.set_operator(cairo.OPERATOR_OVER)

        dt = min(time.monotonic() - self._last_tick_time, 0.05)
        size = max(0.01, self._size.value)
        scale = max(0.01, self._scale.value)
        w = max(24.0, self._w.value)
        h = max(24.0, self._h.value)
        r = min(w / 2.0, min(h / 2.0, max(0.0, self._r.value)))

        cx = width / 2.0
        offset_y = self._offset.value + self._gap.value / size
        pill_top = offset_y * size

        pill_x = -w / 2.0
        pill_y = 0.0
        pill_rect = (pill_x, pill_y, w, h)

        split = self._split.value
        bubble_scale = max(0.01, self._bubble_scale.value)
        apart = split > 0.01

        bubble_rect = None
        if apart:
            pill_right = w / 2.0
            past = ((BUBBLE_GAP + BUBBLE_WIDTH) * split - BUBBLE_WIDTH) / scale
            bx = pill_right + past
            bw = BUBBLE_WIDTH * bubble_scale / scale
            bh = BUBBLE_HEIGHT * bubble_scale / scale
            bubble_rect = (bx, 0.0, bw, bh)

        cr.save()
        cr.translate(cx, pill_top)
        cr.scale(size, size)
        cr.scale(scale, scale)

        if h > 40.0:
            shadow_alpha = min(0.6, (h - 40.0) / 60.0 * 0.5)
            cr.save()
            draw_rounded_rect(cr, pill_x - 6, pill_y + 4, w + 12, h + 10, r + 4)
            cr.set_source_rgba(0.0, 0.0, 0.0, shadow_alpha)
            cr.fill()
            cr.restore()

        self._goo.shape(pill_rect, r, bubble_rect if apart else None)
        self._goo.render(cr, dt)

        cr.save()
        clip_rounded_rect(cr, pill_x, pill_y, w, h, r)

        trans = self._view_transition
        prev = self._previous_view

        if prev and trans < 1.0 and prev != self._current_view:
            cr.save()
            out_alpha = 1.0 - trans
            out_scale = 1.0 - 0.1 * trans
            cr.translate(0.0, h / 2.0)
            cr.scale(out_scale, out_scale)
            cr.translate(0.0, -h / 2.0)
            self.render_view(cr, prev, pill_x, pill_y, w, h, alpha=out_alpha)
            cr.restore()

            cr.save()
            in_alpha = trans
            in_scale = 0.9 + 0.1 * trans
            cr.translate(0.0, h / 2.0)
            cr.scale(in_scale, in_scale)
            cr.translate(0.0, -h / 2.0)
            self.render_view(cr, self._current_view, pill_x, pill_y, w, h, alpha=in_alpha)
            cr.restore()
        else:
            self.render_view(cr, self._current_view, pill_x, pill_y, w, h, alpha=1.0)

        cr.restore()

        if apart and bubble_rect and split > 0.3:
            bx, by, bw, bh = bubble_rect
            bubble_alpha = max(0.0, min(1.0, split * 4.0 - 3.0))
            if bubble_alpha > 0.01:
                cr.save()
                clip_rounded_rect(cr, bx, by, bw, bh, bh / 2.0)
                Ring.render(
                    cr,
                    cx=bx + 18.0,
                    cy=by + bh / 2.0,
                    radius=8.0,
                    progress=self._timer.share,
                    color=self._timer_tint,
                    thickness=2.2,
                )
                self._digits_bubble.render(
                    cr,
                    x=bx + bw - 10.0,
                    y=by + bh / 2.0,
                    font_size=12.5,
                    color=self._timer_tint,
                    align="right",
                    valign="center",
                )
                cr.restore()

        cr.restore()

    def render_view(
        self,
        cr: cairo.Context,
        view: View,
        px: float,
        py: float,
        pw: float,
        ph: float,
        alpha: float = 1.0,
    ) -> None:
        if alpha <= 0.001:
            return

        if view == View.IDLE:
            self.render_idle(cr, px, py, pw, ph, alpha)
        elif view == View.MEDIA:
            self.render_media(cr, px, py, pw, ph, alpha)
        elif view == View.TIMER:
            self.render_timer(cr, px, py, pw, ph, alpha)
        elif view == View.VOLUME:
            self.render_volume(cr, px, py, pw, ph, alpha)
        elif view == View.CHARGE:
            self.render_charge(cr, px, py, pw, ph, alpha)
        elif view == View.TOAST:
            self.render_toast(cr, px, py, pw, ph, alpha)
        elif view == View.NOTICE:
            self.render_notice(cr, px, py, pw, ph, alpha)
        elif view == View.MEDIA_BIG:
            self.render_media_big(cr, px, py, pw, ph, alpha)
        elif view == View.IDLE_BIG:
            self.render_idle_big(cr, px, py, pw, ph, alpha)
        elif view == View.TIMER_BIG:
            self.render_timer_big(cr, px, py, pw, ph, alpha)
        elif view == View.TIMER_SET:
            self.render_timer_set(cr, px, py, pw, ph, alpha)
        elif view == View.MENU:
            self.render_menu(cr, px, py, pw, ph, alpha)
        elif view == View.SETTINGS:
            self.render_settings(cr, px, py, pw, ph, alpha)
        elif view == View.LOOK:
            self.render_look(cr, px, py, pw, ph, alpha)

    def render_idle(self, cr: cairo.Context, px: float, py: float, pw: float, ph: float, alpha: float) -> None:
        draw_text(
            cr,
            self._clock_time_str,
            px + pw / 2.0,
            py + ph / 2.0,
            font_size=13.5,
            bold=True,
            color=COLOR_WHITE,
            alpha=alpha,
            align="center",
            valign="center",
        )

    def render_media(self, cr: cairo.Context, px: float, py: float, pw: float, ph: float, alpha: float) -> None:
        art_size = 22.0
        art_x = px + 7.0
        art_y = py + (ph - art_size) / 2.0
        if self._cover_small.surface:
            self._cover_small.render(cr, art_x, art_y, art_size, radius=6.0)
        else:
            draw_rounded_rect(cr, art_x, art_y, art_size, art_size, 6.0)
            cr.set_source_rgba(0.2, 0.2, 0.2, alpha)
            cr.fill()
            render_icon(cr, Glyph.Note, art_x + 4.5, art_y + 4.5, 13.0, COLOR_DIM[:3], alpha=alpha)

        eq_w = 21.0
        eq_h = 16.0
        eq_x = px + pw - 13.0 - eq_w
        eq_y = py + (ph - eq_h) / 2.0
        self._eq_small.render(cr, eq_x, eq_y, eq_w, eq_h, color=self._accent_color, alpha=alpha)

        mid_x = art_x + art_size + 7.0
        mid_w = eq_x - mid_x - 7.0
        if mid_w > 10.0:
            lines = self._lyrics.for_duration(self._media.duration)
            _, current_line = self._lyrics.get_current_line(self._media.position, self._media.duration, lead=0.2)
            has_lyric = bool(current_line and current_line[1].strip())
            lyric_text = current_line[1] if has_lyric else self._media.title

            if has_lyric and Settings.lyrics:
                LyricLine.render_compact(
                    cr,
                    lyric_text,
                    mid_x,
                    py,
                    mid_w,
                    COLOR_WHITE,
                    font_size=LYRIC_COMPACT_FONT,
                    offset_x=self._lyric_scroll,
                    h=ph,
                )
            else:
                draw_text(
                    cr,
                    lyric_text,
                    mid_x + mid_w / 2.0,
                    py + ph / 2.0,
                    font_size=LYRIC_COMPACT_FONT,
                    bold=True,
                    color=COLOR_DIM[:3] if has_lyric else COLOR_WHITE,
                    alpha=alpha,
                    align="center",
                    valign="center",
                    max_w=mid_w,
                )

    def render_timer(self, cr: cairo.Context, px: float, py: float, pw: float, ph: float, alpha: float) -> None:
        Ring.render(
            cr,
            cx=px + 18.0,
            cy=py + ph / 2.0,
            radius=9.0,
            progress=self._timer.share,
            color=self._timer_tint,
            thickness=2.5,
        )
        self._digits_timer.render(
            cr,
            x=px + pw - 14.0,
            y=py + ph / 2.0,
            font_size=13.5,
            color=self._timer_tint,
            align="right",
            valign="center",
        )

    def render_volume(self, cr: cairo.Context, px: float, py: float, pw: float, ph: float, alpha: float) -> None:
        vol = max(0.0, self._last_volume)
        glyph = Glyph.Mute if (self._last_muted or vol < 0.01) else (Glyph.Quiet if vol < 0.34 else (Glyph.Mid if vol < 0.67 else Glyph.Loud))
        render_icon(cr, glyph, px + 12.0, py + (ph - 17.0) / 2.0, 17.0, COLOR_WHITE, alpha=alpha)

        track_w = 162.0
        track_h = 5.0
        track_x = px + 42.0
        track_y = py + (ph - track_h) / 2.0

        push = max(-VOLUME_PUSH, self._push.value)
        stretch_w = track_w * (1.0 + push / VOLUME_TRACK)
        stretch_h = track_h * max(0.5, 1.0 - push / VOLUME_PUSH * 0.22)

        draw_rounded_rect(cr, track_x, track_y, stretch_w, stretch_h, stretch_h / 2.0)
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.2 * alpha)
        cr.fill()

        fill_w = stretch_w * (0.0 if self._last_muted else vol)
        if fill_w > 0.5:
            draw_rounded_rect(cr, track_x, track_y, fill_w, stretch_h, stretch_h / 2.0)
            cr.set_source_rgba(1.0, 1.0, 1.0, alpha)
            cr.fill()

        self._digits_volume.render(
            cr,
            x=px + pw - 24.0,
            y=py + ph / 2.0,
            font_size=12.5,
            color=COLOR_WHITE,
            align="center",
            valign="center",
        )

    def render_charge(self, cr: cairo.Context, px: float, py: float, pw: float, ph: float, alpha: float) -> None:
        draw_text(
            cr,
            "Зарядка",
            px + 16.0,
            py + ph / 2.0,
            font_size=13.0,
            bold=True,
            color=COLOR_WHITE,
            alpha=alpha,
            align="left",
            valign="center",
        )
        bat_str = f"{self._battery_pct}%"
        draw_text(
            cr,
            bat_str,
            px + pw - 48.0,
            py + ph / 2.0,
            font_size=13.0,
            bold=True,
            color=COLOR_GREEN,
            alpha=alpha,
            align="right",
            valign="center",
        )
        bx = px + pw - 42.0
        by = py + (ph - 13.0) / 2.0
        draw_rounded_rect(cr, bx, by, 24.0, 13.0, 4.0)
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.4 * alpha)
        cr.set_line_width(1.0)
        cr.stroke()

        fill_w = 20.0 * (self._battery_pct / 100.0)
        if fill_w > 0.5:
            draw_rounded_rect(cr, bx + 2.0, by + 2.0, fill_w, 9.0, 2.5)
            cr.set_source_rgba(COLOR_GREEN[0], COLOR_GREEN[1], COLOR_GREEN[2], alpha)
            cr.fill()

        draw_rounded_rect(cr, bx + 24.0, by + 4.0, 2.0, 5.0, 1.0)
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.4 * alpha)
        cr.fill()

    def render_toast(self, cr: cairo.Context, px: float, py: float, pw: float, ph: float, alpha: float) -> None:
        art_size = 44.0
        art_x = px + 12.0
        art_y = py + (ph - art_size) / 2.0
        if self._cover_toast.surface:
            self._cover_toast.render(cr, art_x, art_y, art_size, radius=11.0)
        else:
            draw_rounded_rect(cr, art_x, art_y, art_size, art_size, 11.0)
            cr.set_source_rgba(0.2, 0.2, 0.2, alpha)
            cr.fill()
            render_icon(cr, Glyph.Note, art_x + 11.0, art_y + 11.0, 22.0, COLOR_DIM[:3], alpha=alpha)

        eq_w = 23.0
        eq_h = 20.0
        eq_x = px + pw - 20.0 - eq_w
        eq_y = py + (ph - eq_h) / 2.0
        self._eq_toast.render(cr, eq_x, eq_y, eq_w, eq_h, color=self._accent_color, alpha=alpha)

        mid_x = art_x + art_size + 12.0
        mid_w = eq_x - mid_x - 10.0
        draw_text(
            cr,
            self._media.title or "Аудио",
            mid_x,
            py + 24.0,
            font_size=14.0,
            bold=True,
            color=COLOR_WHITE,
            alpha=alpha,
            align="left",
            valign="center",
            max_w=mid_w,
        )
        src_text = f"{self._source_app_name} · {self._media.artist}" if self._source_app_name else (self._media.artist or "Неизвестный исполнитель")
        draw_text(
            cr,
            src_text,
            mid_x,
            py + 44.0,
            font_size=12.0,
            bold=False,
            color=COLOR_DIM[:3],
            alpha=alpha,
            align="left",
            valign="center",
            max_w=mid_w,
        )

    def render_notice(self, cr: cairo.Context, px: float, py: float, pw: float, ph: float, alpha: float) -> None:
        badge_size = 40.0
        badge_x = px + 12.0
        badge_y = py + (ph - badge_size) / 2.0
        draw_rounded_rect(cr, badge_x, badge_y, badge_size, badge_size, 11.0)
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.12 * alpha)
        cr.fill()

        pulse_scale = 1.0 + (0.2 * math.sin(time.monotonic() * 8.0) if self._ringing else 0.0)
        icon_size = 22.0 * pulse_scale
        render_icon(
            cr,
            self._notice_icon,
            badge_x + (badge_size - icon_size) / 2.0,
            badge_y + (badge_size - icon_size) / 2.0,
            icon_size,
            self._notice_tint,
            alpha=alpha,
        )

        mid_x = badge_x + badge_size + 12.0
        mid_w = pw - (mid_x - px) - 16.0
        draw_text(
            cr,
            self._notice_title,
            mid_x,
            py + 22.0,
            font_size=14.0,
            bold=True,
            color=COLOR_WHITE,
            alpha=alpha,
            align="left",
            valign="center",
            max_w=mid_w,
        )
        draw_text(
            cr,
            self._notice_text,
            mid_x,
            py + 42.0,
            font_size=12.0,
            bold=False,
            color=COLOR_DIM[:3],
            alpha=alpha,
            align="left",
            valign="center",
            max_w=mid_w,
        )

    def render_media_big(self, cr: cairo.Context, px: float, py: float, pw: float, ph: float, alpha: float) -> None:
        art_size = 64.0
        art_x = px + 20.0
        art_y = py + 20.0
        self._btn_art_rect = (art_x, art_y, art_size, art_size)

        if self._cover_big.surface:
            self._cover_big.render(cr, art_x, art_y, art_size, radius=16.0)
        else:
            draw_rounded_rect(cr, art_x, art_y, art_size, art_size, 16.0)
            cr.set_source_rgba(0.2, 0.2, 0.2, alpha)
            cr.fill()
            render_icon(cr, Glyph.Note, art_x + 17.0, art_y + 17.0, 30.0, COLOR_DIM[:3], alpha=alpha)

        eq_w = 38.0
        eq_h = 26.0
        eq_x = px + pw - 22.0 - eq_w
        eq_y = py + 38.0
        self._eq_big.render(cr, eq_x, eq_y, eq_w, eq_h, color=self._accent_color, alpha=alpha)

        mid_x = art_x + art_size + 14.0
        mid_w = eq_x - mid_x - 12.0
        draw_text(
            cr,
            self._media.title or "Аудио",
            mid_x,
            py + 38.0,
            font_size=16.0,
            bold=True,
            color=COLOR_WHITE,
            alpha=alpha,
            align="left",
            valign="center",
            max_w=mid_w,
        )
        artist_str = self._media.artist or "Неизвестный исполнитель"
        draw_text(
            cr,
            artist_str,
            mid_x,
            py + 58.0,
            font_size=13.0,
            bold=False,
            color=COLOR_DIM[:3],
            alpha=alpha,
            align="left",
            valign="center",
            max_w=mid_w,
        )

        if self._player_room:
            lyric_y = py + 92.0
            lyric_w = 340.0
            lyric_h = self._player_lyric_h
            lines = self._lyrics.for_duration(self._media.duration)
            idx, curr = self._lyrics.get_current_line(self._media.position, self._media.duration, lead=0.2)
            if lines and idx >= 0:
                prev_text = lines[idx - 1][1] if idx > 0 else ""
                curr_text = curr[1] if curr else ""
                next_text = lines[idx + 1][1] if idx + 1 < len(lines) else ""

                prog = 0.0
                if curr_text:
                    start_t = lines[idx][0]
                    end_t = lines[idx + 1][0] if idx + 1 < len(lines) else self._media.duration
                    prog = max(0.0, min(1.0, (self._media.position + 0.2 - start_t) / max(0.5, end_t - start_t)))

                h_prev = measure_text(_MEASURE_CR, prev_text, lyric_w, PLAYER_LYRIC_FONT, False)[1] if prev_text else 0.0
                h_curr = measure_text(_MEASURE_CR, curr_text, lyric_w, PLAYER_LYRIC_FONT, True)[1] if curr_text else 0.0
                h_next = measure_text(_MEASURE_CR, next_text, lyric_w, PLAYER_LYRIC_FONT, False)[1] if next_text else 0.0

                rows = sum(1 for h in (h_prev, h_curr, h_next) if h > 0.0)
                stack_h = h_prev + h_curr + h_next + PLAYER_LYRIC_GAP * max(0, rows - 1)
                needed = max(self._player_lyric_h, stack_h + 2 * PLAYER_LYRIC_PAD, PLAYER_LYRIC_ROOM)
                if needed - self._player_lyric_h > 0.5:
                    self._player_lyric_h = needed
                    self._h.tune(280, 30)
                    self.set_targets()

                lyric_x = px + (pw - lyric_w) / 2.0
                cursor = lyric_y + max(0.0, (lyric_h - stack_h) / 2.0)

                if prev_text:
                    LyricLine.render_karaoke(
                        cr, prev_text, prog, lyric_x, cursor, lyric_w, h_prev,
                        font_size=PLAYER_LYRIC_FONT, is_active=False, alpha=alpha,
                    )
                    cursor += h_prev + PLAYER_LYRIC_GAP

                if curr_text:
                    LyricLine.render_karaoke(
                        cr, curr_text, prog, lyric_x, cursor, lyric_w, h_curr,
                        font_size=PLAYER_LYRIC_FONT, is_active=True, alpha=alpha,
                    )
                    cursor += h_curr + PLAYER_LYRIC_GAP

                if next_text:
                    LyricLine.render_karaoke(
                        cr, next_text, prog, lyric_x, cursor, lyric_w, h_next,
                        font_size=PLAYER_LYRIC_FONT, is_active=False, alpha=alpha,
                    )

        dur = self._media.duration
        known_dur = dur >= 1.0
        pos = dur * (self._seek_x.value / SEEK_TRACK) if known_dur else 0.0

        seek_y = py + ph - 70.0
        draw_text(cr, format_time(pos) if known_dur else "0:00", px + 20.0, seek_y + 3.0, font_size=11.0, color=COLOR_DIM[:3], alpha=alpha, align="left", valign="center")
        seek_w = SEEK_TRACK
        seek_x = px + 60.0
        seek_h = max(2.0, self._seek_h.value)
        self._seek_rect = (seek_x, seek_y - seek_h / 2.0, seek_w, seek_h)

        draw_rounded_rect(cr, seek_x, seek_y - seek_h / 2.0, seek_w, seek_h, seek_h / 2.0)
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.2 * alpha)
        cr.fill()

        fill_seek = max(0.0, min(seek_w, self._seek_x.value))
        if fill_seek > 1.0:
            draw_rounded_rect(cr, seek_x, seek_y - seek_h / 2.0, fill_seek, seek_h, seek_h / 2.0)
            cr.set_source_rgba(1.0, 1.0, 1.0, alpha)
            cr.fill()

        rem = max(0.0, dur - pos) if known_dur else 0.0
        draw_text(cr, f"-{format_time(rem)}" if known_dur else "-0:00", px + pw - 20.0, seek_y + 3.0, font_size=11.0, color=COLOR_DIM[:3], alpha=alpha, align="right", valign="center")

        btn_y = py + ph - 42.0

        self._btn_prev_rect = (px + pw / 2.0 - 74.0, btn_y - 20.0, 40.0, 40.0)
        cr.save()
        cr.translate(px + pw / 2.0 - 54.0, btn_y)
        cr.new_path()
        cr.move_to(-2.0, -8.0)
        cr.line_to(-12.0, 0.0)
        cr.line_to(-2.0, 8.0)
        cr.close_path()
        cr.move_to(8.0, -8.0)
        cr.line_to(-2.0, 0.0)
        cr.line_to(8.0, 8.0)
        cr.close_path()
        cr.set_source_rgba(1.0, 1.0, 1.0, alpha)
        cr.fill()
        cr.restore()

        self._btn_play_rect = (px + pw / 2.0 - 24.0, btn_y - 24.0, 48.0, 48.0)
        cr.save()
        cr.translate(px + pw / 2.0, btn_y)
        if self._media.is_playing:
            cr.rectangle(-6.0, -9.0, 4.0, 18.0)
            cr.rectangle(2.0, -9.0, 4.0, 18.0)
            cr.set_source_rgba(1.0, 1.0, 1.0, alpha)
            cr.fill()
        else:
            cr.new_path()
            cr.move_to(-6.0, -9.0)
            cr.line_to(8.0, 0.0)
            cr.line_to(-6.0, 9.0)
            cr.close_path()
            cr.set_source_rgba(1.0, 1.0, 1.0, alpha)
            cr.fill()
        cr.restore()

        self._btn_next_rect = (px + pw / 2.0 + 34.0, btn_y - 20.0, 40.0, 40.0)
        cr.save()
        cr.translate(px + pw / 2.0 + 54.0, btn_y)
        cr.new_path()
        cr.move_to(-8.0, -8.0)
        cr.line_to(2.0, 0.0)
        cr.line_to(-8.0, 8.0)
        cr.close_path()
        cr.move_to(2.0, -8.0)
        cr.line_to(12.0, 0.0)
        cr.line_to(2.0, 8.0)
        cr.close_path()
        cr.set_source_rgba(1.0, 1.0, 1.0, alpha)
        cr.fill()
        cr.restore()

        if self._headset_pct >= 0:
            render_icon(cr, Glyph.Headphones, px + pw - 60.0, btn_y - 7.0, 14.0, COLOR_DIM[:3], alpha=alpha)
            draw_text(cr, f"{self._headset_pct}%", px + pw - 42.0, btn_y, font_size=11.0, color=COLOR_DIM[:3], alpha=alpha, align="left", valign="center")

        if self._player_vol_opacity > 0.01:
            eff_a = self._player_vol_opacity * alpha
            render_icon(cr, Glyph.Note if self._player_vol_is_app else Glyph.Loud, px + 20.0, btn_y - 7.0, 14.0, self._accent_color if self._player_vol_is_app else COLOR_DIM[:3], alpha=eff_a)
            draw_text(cr, self._player_vol_text, px + 38.0, btn_y, font_size=11.0, color=self._accent_color if self._player_vol_is_app else COLOR_DIM[:3], alpha=eff_a, align="left", valign="center")

    def render_idle_big(self, cr: cairo.Context, px: float, py: float, pw: float, ph: float, alpha: float) -> None:
        draw_text(cr, self._clock_time_str, px + 26.0, py + 48.0, font_size=46.0, bold=True, color=COLOR_WHITE, alpha=alpha, align="left", valign="center")
        draw_text(cr, self._clock_date_str, px + 28.0, py + 86.0, font_size=13.0, bold=False, color=COLOR_DIM[:3], alpha=alpha, align="left", valign="center")

        rx = px + pw - 24.0
        render_icon(cr, Glyph.Loud, rx - 54.0, py + 32.0, 16.0, COLOR_DIM[:3], alpha=alpha)
        vol_pct = int(round(max(0.0, self._last_volume) * 100))
        draw_text(cr, f"{vol_pct}%", rx, py + 40.0, font_size=13.0, bold=True, color=COLOR_WHITE, alpha=alpha, align="right", valign="center")

        if self._headset_pct >= 0:
            render_icon(cr, Glyph.Headphones, rx - 54.0, py + 58.0, 16.0, COLOR_DIM[:3], alpha=alpha)
            draw_text(cr, f"{self._headset_pct}%", rx, py + 66.0, font_size=13.0, bold=True, color=COLOR_WHITE, alpha=alpha, align="right", valign="center")

        if self._battery_known:
            render_icon(cr, Glyph.Battery, rx - 54.0, py + 84.0, 16.0, COLOR_DIM[:3], alpha=alpha)
            draw_text(cr, f"{self._battery_pct}%", rx, py + 92.0, font_size=13.0, bold=True, color=COLOR_GREEN if self._last_plugged else COLOR_WHITE, alpha=alpha, align="right", valign="center")

    def render_timer_big(self, cr: cairo.Context, px: float, py: float, pw: float, ph: float, alpha: float) -> None:
        p_cx = px + 45.0
        p_cy = py + ph / 2.0
        cr.arc(p_cx, p_cy, 25.0, 0, 2 * math.pi)
        cr.set_source_rgba(COLOR_ORANGE[0], COLOR_ORANGE[1], COLOR_ORANGE[2], 0.25 * alpha)
        cr.fill()
        if self._timer.running:
            cr.rectangle(p_cx - 5.0, p_cy - 7.0, 3.5, 14.0)
            cr.rectangle(p_cx + 1.5, p_cy - 7.0, 3.5, 14.0)
            cr.set_source_rgba(COLOR_ORANGE[0], COLOR_ORANGE[1], COLOR_ORANGE[2], alpha)
            cr.fill()
        else:
            cr.new_path()
            cr.move_to(p_cx - 4.0, p_cy - 7.0)
            cr.line_to(p_cx + 7.0, p_cy)
            cr.line_to(p_cx - 4.0, p_cy + 7.0)
            cr.close_path()
            cr.set_source_rgba(COLOR_ORANGE[0], COLOR_ORANGE[1], COLOR_ORANGE[2], alpha)
            cr.fill()

        c_cx = px + 105.0
        c_cy = py + ph / 2.0
        cr.arc(c_cx, c_cy, 25.0, 0, 2 * math.pi)
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.18 * alpha)
        cr.fill()

        cr.set_line_width(2.4)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.move_to(c_cx - 6.0, c_cy - 6.0)
        cr.line_to(c_cx + 6.0, c_cy + 6.0)
        cr.move_to(c_cx + 6.0, c_cy - 6.0)
        cr.line_to(c_cx - 6.0, c_cy + 6.0)
        cr.set_source_rgba(1.0, 1.0, 1.0, alpha)
        cr.stroke()

        draw_text(cr, f"Таймер · {format_time(self._timer.total)}", px + pw - 26.0, py + 26.0, font_size=12.0, color=self._timer_tint, alpha=0.8 * alpha, align="right", valign="center")
        self._digits_big_timer.render(cr, px + pw - 26.0, py + 62.0, font_size=40.0, color=self._timer_tint, align="right", valign="center")

    def render_timer_set(self, cr: cairo.Context, px: float, py: float, pw: float, ph: float, alpha: float) -> None:
        draw_text(cr, "ТАЙМЕР", px + 22.0, py + 24.0, font_size=10.5, bold=True, color=COLOR_DIM[:3], alpha=0.6 * alpha, align="left", valign="center")

        render_icon(cr, Glyph.Minus, px + 24.0, py + 54.0, 16.0, COLOR_WHITE, alpha=alpha)
        self._digits_setup.render(cr, px + pw / 2.0, py + 62.0, font_size=38.0, color=COLOR_WHITE, align="center", valign="center")
        render_icon(cr, Glyph.Plus, px + pw - 40.0, py + 54.0, 16.0, COLOR_WHITE, alpha=alpha)

        presets = [5, 10, 15, 25, 45]
        chip_y = py + 98.0
        chip_h = 28.0
        chip_w = (pw - 28.0) / 5.0
        for idx, p_min in enumerate(presets):
            cx_chip = px + 14.0 + idx * chip_w
            draw_rounded_rect(cr, cx_chip + 2.0, chip_y, chip_w - 4.0, chip_h, 14.0)
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.12 * alpha)
            cr.fill()
            draw_text(cr, f"{p_min} мин", cx_chip + chip_w / 2.0, chip_y + chip_h / 2.0, font_size=12.0, bold=False, color=COLOR_WHITE, alpha=alpha, align="center", valign="center")

        start_y = py + 138.0
        draw_rounded_rect(cr, px + 16.0, start_y, pw - 32.0, 36.0, 14.0)
        cr.set_source_rgba(COLOR_ORANGE[0], COLOR_ORANGE[1], COLOR_ORANGE[2], alpha)
        cr.fill()
        draw_text(cr, "Запустить", px + pw / 2.0, start_y + 18.0, font_size=13.5, bold=True, color=(0.0, 0.0, 0.0), alpha=alpha, align="center", valign="center")

    def render_menu(self, cr: cairo.Context, px: float, py: float, pw: float, ph: float, alpha: float) -> None:
        draw_text(cr, "DYNAMIC ISLAND", px + 22.0, py + 24.0, font_size=10.5, bold=True, color=COLOR_DIM[:3], alpha=0.6 * alpha, align="left", valign="center")

        self._row_list_menu.render_highlight(cr, w=pw - 20.0, x=px + 10.0)

        rows = [
            (Glyph.Clock, "Таймер", self._timer.formatted if self._timer.active else "", COLOR_ORANGE if self._timer.active else COLOR_DIM[:3]),
            (Glyph.Gear, "Настройки", "", COLOR_DIM[:3]),
            (Glyph.Look, "Оформление", "", COLOR_DIM[:3]),
            (Glyph.Power, "Закрыть остров", "", COLOR_RED),
        ]
        row_y_start = py + 36.0
        row_h = 40.0
        for idx, (glyph, label, extra, tint) in enumerate(rows):
            ry = row_y_start + idx * row_h
            render_icon(cr, glyph, px + 22.0, ry + 11.5, 17.0, tint, alpha=alpha)
            draw_text(cr, label, px + 49.0, ry + 20.0, font_size=13.5, bold=False, color=tint if glyph == Glyph.Power else COLOR_WHITE, alpha=alpha, align="left", valign="center")
            if extra:
                draw_text(cr, extra, px + pw - 36.0, ry + 20.0, font_size=13.5, bold=False, color=tint, alpha=alpha, align="right", valign="center")
            if glyph != Glyph.Power:
                render_icon(cr, Glyph.Chevron, px + pw - 28.0, ry + 14.5, 11.0, COLOR_DIM[:3], alpha=alpha)

    def render_settings(self, cr: cairo.Context, px: float, py: float, pw: float, ph: float, alpha: float) -> None:
        render_icon(cr, Glyph.Back, px + 20.0, py + 18.0, 10.0, COLOR_DIM[:3], alpha=0.6 * alpha)
        draw_text(cr, "НАСТРОЙКИ", px + 36.0, py + 23.0, font_size=10.5, bold=True, color=COLOR_DIM[:3], alpha=0.6 * alpha, align="left", valign="center")

        self._row_list_settings.render_highlight(cr, w=pw - 20.0, x=px + 10.0)

        rows = [
            (Glyph.Lines, "Текст песен", "lyrics"),
            (Glyph.Sparkle, "Эффекты текста", "lyric_effects"),
            (Glyph.Rim, "Цветной ободок", "rim"),
            (Glyph.Mid, "Громкость приложения", "app_volume"),
            (Glyph.Wifi, "Уведомления о сети", "network"),
            (Glyph.Expand, "Скрывать на полном экране", "hide_fullscreen"),
            (Glyph.Clock, "Задержка при анимации", "click_lock"),
            (Glyph.Linux, "Запускать при старте", "autostart"),
        ]
        row_y_start = py + 44.0
        row_h = 40.0
        for idx, (glyph, label, key) in enumerate(rows):
            ry = row_y_start + idx * row_h
            render_icon(cr, glyph, px + 22.0, ry + 11.5, 17.0, COLOR_DIM[:3], alpha=alpha)
            draw_text(cr, label, px + 49.0, ry + 20.0, font_size=13.5, bold=False, color=COLOR_WHITE, alpha=alpha, align="left", valign="center")
            self._toggles[key].render(cr, px + pw - 50.0, ry + 10.0, w=38.0, h=22.0)

    def render_look(self, cr: cairo.Context, px: float, py: float, pw: float, ph: float, alpha: float) -> None:
        render_icon(cr, Glyph.Back, px + 20.0, py + 18.0, 10.0, COLOR_DIM[:3], alpha=0.6 * alpha)
        draw_text(cr, "ОФОРМЛЕНИЕ", px + 36.0, py + 23.0, font_size=10.5, bold=True, color=COLOR_DIM[:3], alpha=0.6 * alpha, align="left", valign="center")

        self._row_list_look.render_highlight(cr, w=pw - 20.0, x=px + 10.0)

        render_icon(cr, Glyph.Size, px + 22.0, py + 55.5, 17.0, COLOR_DIM[:3], alpha=alpha)
        draw_text(cr, "Размер", px + 49.0, py + 64.0, font_size=13.5, bold=False, color=COLOR_WHITE, alpha=alpha, align="left", valign="center")
        draw_text(cr, f"{Settings.scale}%", px + pw - 24.0, py + 64.0, font_size=13.5, bold=False, color=COLOR_DIM[:3], alpha=alpha, align="right", valign="center")

        render_icon(cr, Glyph.Gap, px + 22.0, py + 95.5, 17.0, COLOR_DIM[:3], alpha=alpha)
        draw_text(cr, "Отступ от края", px + 49.0, py + 104.0, font_size=13.5, bold=False, color=COLOR_WHITE, alpha=alpha, align="left", valign="center")
        draw_text(cr, f"{Settings.gap} px", px + pw - 24.0, py + 104.0, font_size=13.5, bold=False, color=COLOR_DIM[:3], alpha=alpha, align="right", valign="center")

        render_icon(cr, Glyph.Drop, px + 22.0, py + 135.5, 17.0, COLOR_DIM[:3], alpha=alpha)
        draw_text(cr, "Акцентный цвет", px + 49.0, py + 144.0, font_size=13.5, bold=False, color=COLOR_WHITE, alpha=alpha, align="left", valign="center")
        cur_accent_label = "Из обложки"
        for col, lbl in LOOK_COLORS:
            if col == Settings.accent:
                cur_accent_label = lbl
                break
        draw_text(cr, cur_accent_label, px + pw - 24.0, py + 144.0, font_size=13.5, bold=False, color=COLOR_DIM[:3], alpha=alpha, align="right", valign="center")

        swatch_y = py + 172.0
        step_x = (pw - 20.0) / len(LOOK_COLORS)
        for idx, (col, _) in enumerate(LOOK_COLORS):
            sx = px + 10.0 + idx * step_x + step_x / 2.0
            is_checked = (col == Settings.accent)

            if is_checked:
                cr.arc(sx, swatch_y, 11.0, 0, 2 * math.pi)
                cr.set_source_rgba(1.0, 1.0, 1.0, alpha)
                cr.set_line_width(1.5)
                cr.stroke()

            cr.arc(sx, swatch_y, 7.0, 0, 2 * math.pi)
            if col is None:
                cr.set_source_rgba(1.0, 0.4, 0.7, alpha)
            else:
                cr.set_source_rgba(col[0], col[1], col[2], alpha)
            cr.fill()
