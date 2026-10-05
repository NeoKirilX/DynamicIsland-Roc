#!/usr/bin/env python3

from __future__ import annotations

import ctypes
import datetime
import io
import math
import os
import re
import sys
import time
import urllib.parse
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
from gi.repository import Gdk, Gio, GLib, Gtk, Gtk4LayerShell

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from alarm import Alarm
from audio_service import AudioService
from battery_service import get_power_status, get_battery_info, BatteryInfo
from sound_service import play_sound
from cover import Cover
from digits import Digits
from equalizer import Equalizer
from goo import Goo
from headset import get_headset_charge
from icon import Glyph, render_battery, render_icon
from lyric import LyricLine, measure_text, render_wait, select_font
from lyrics_service import LyricsService
from media_service import MediaService, clean_track_title, format_display_title
from native_wayland import is_ctrl_down, is_fullscreen, query_do_not_disturb
from network_service import Link, NetworkService, State
from ring import Ring
from row_list import RowList
from settings import MATERIAL_LIQUID, MATERIAL_MATTE, MATERIAL_NONE, Settings
from shelf import Shelf, ShelfItem
from spectrum_service import SpectrumService
from spring import Spring
from shimmer import Shimmer
from timer_service import Countdown
from toggle import Toggle
from line_bar import LineBar
from skip import Skip
from updater import Updater, UpdateState

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
    FOCUS = auto()
    TOAST = auto()
    NOTICE = auto()
    MEDIA_BIG = auto()
    IDLE_BIG = auto()
    TIMER_BIG = auto()
    TIMER_SET = auto()
    MENU = auto()
    SETTINGS = auto()
    LOOK = auto()
    SHELF = auto()
    UPDATE = auto()

class Panel(Enum):
    NONE = auto()
    PLAYER = auto()
    TIMER = auto()
    TIMER_SET = auto()
    MENU = auto()
    SETTINGS = auto()
    LOOK = auto()
    SHELF = auto()
    UPDATE = auto()

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

LOOK_WIDTH = 320.0
LOOK_HEIGHT = 540.0
COLOR_INDIGO: Tuple[float, float, float] = (0.49, 0.478, 1.0)
CARRY_TIMER: float = 78.0
CARRY_SHELF: float = 54.0

SIZES: dict[View, Dims] = {
    View.IDLE: Dims(118, 34, 17),
    View.MEDIA: Dims(210, 34, 17),
    View.TIMER: Dims(132, 34, 17),
    View.VOLUME: Dims(250, 34, 17),
    View.CHARGE: Dims(230, 34, 17),
    View.FOCUS: Dims(236, 34, 17),
    View.TOAST: Dims(340, 68, 30),
    View.NOTICE: Dims(320, 64, 29),
    View.MEDIA_BIG: Dims(380, 176, 40),
    View.IDLE_BIG: Dims(320, 124, 38),
    View.TIMER_BIG: Dims(330, 92, 40),
    View.TIMER_SET: Dims(300, 190, 38),
    View.MENU: Dims(300, 248, 34),
    View.SETTINGS: Dims(320, 414, 34),
    View.LOOK: Dims(LOOK_WIDTH, LOOK_HEIGHT, 34),
    View.SHELF: Dims(380, 136, 34),
    View.UPDATE: Dims(340, 230, 34),
}

SCALES: list[int] = [85, 100, 115, 130]
GAPS: list[int] = [0, 4, 8, 12, 16, 24]
RADII: list[int] = [0, 25, 50, 75, 100]
HEIGHTS: list[int] = [0, 4, 8, 12, 16]
TEXT_SCALES: list[int] = [80, 90, 100, 115, 130]
GLASS_LEVELS: list[int] = [20, 40, 60, 70, 85, 100]
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
MEDIA_MAX_WIDTH = 480.0
MEDIA_NAME_WIDTH = 300.0
LYRIC_INSET = 77.0
LYRIC_EDGE = 8.0
PLAYER_HEIGHT = 176.0
PLAYER_LYRIC_ROOM = 74.0
PLAYER_LYRIC_W = 340.0
PLAYER_LYRIC_GAP = 4.0
PLAYER_LYRIC_PAD = 8.0
WAIT_ROW_H = 22.0
LYRIC_COMPACT_FONT = 13.0
PLAYER_LYRIC_FONT = 14.0


def compact_lyric_font() -> float:
    return LYRIC_COMPACT_FONT * Settings.text_factor()


def player_lyric_font() -> float:
    return PLAYER_LYRIC_FONT * Settings.text_factor()
LYRIC_SPEED = 36.0
LYRIC_LEAD = 0.2
LYRIC_LOOKAHEAD = 1.8
LYRIC_ARM_BEFORE = 2.0
LYRIC_DIM_ARM = 0.45
LYRIC_ENTER_SHIFT = 7.0
LYRIC_EXIT_SHIFT = -6.0
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
    select_font(cr, font_size=font_size * Settings.text_factor(), bold=bold)
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
    cr.new_path()
    return ext.width

_IMAGE_SURFACE_CACHE: dict[str, tuple[cairo.ImageSurface, bytearray]] = {}
_MEASURE_SURFACE = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1)
_MEASURE_CR = cairo.Context(_MEASURE_SURFACE)

def load_cairo_image(path: Optional[str]) -> Optional[cairo.ImageSurface]:
    if not path or not os.path.isfile(path) or Image is None:
        return None
    if path in _IMAGE_SURFACE_CACHE:
        return _IMAGE_SURFACE_CACHE[path][0]
    try:
        pil_img = Image.open(path).convert("RGBA")
        raw = bytearray(pil_img.tobytes("raw", "BGRA"))
        stride = cairo.ImageSurface.format_stride_for_width(cairo.FORMAT_ARGB32, pil_img.width)
        surf = cairo.ImageSurface.create_for_data(raw, cairo.FORMAT_ARGB32, pil_img.width, pil_img.height, stride)
        _IMAGE_SURFACE_CACHE[path] = (surf, raw)
        if len(_IMAGE_SURFACE_CACHE) > 30:
            old_k = next(iter(_IMAGE_SURFACE_CACHE))
            del _IMAGE_SURFACE_CACHE[old_k]
        return surf
    except Exception as exc:
        logger.debug("Failed loading cairo image from %s: %s", path, exc)
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

        self.win_width = 1920
        self.win_height = 1080
        self.set_default_size(self.win_width, self.win_height)

        self.is_layer_shell = Gtk4LayerShell.is_supported()
        if self.is_layer_shell:
            Gtk4LayerShell.init_for_window(self)
            Gtk4LayerShell.set_layer(self, Gtk4LayerShell.Layer.TOP)
            Gtk4LayerShell.set_anchor(self, Gtk4LayerShell.Edge.TOP, True)
            Gtk4LayerShell.set_anchor(self, Gtk4LayerShell.Edge.BOTTOM, True)
            Gtk4LayerShell.set_anchor(self, Gtk4LayerShell.Edge.LEFT, True)
            Gtk4LayerShell.set_anchor(self, Gtk4LayerShell.Edge.RIGHT, True)
            Gtk4LayerShell.set_exclusive_zone(self, 0)
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
        self._digits_shelf = Digits("0", down=True)
        self._digits_shelf_menu = Digits("0", down=True)
        self._digits_clock = Digits("00:00", down=True)
        self._digits_big_clock = Digits("00:00", down=True)
        self._digits_charge = Digits("100%", down=True)
        self._digits_info_vol = Digits("0%", down=True)
        self._digits_info_headset = Digits("0%", down=True)
        self._digits_info_battery = Digits("100%", down=True)
        self._digits_pos = Digits("0:00", down=False)
        self._digits_rem = Digits("-0:00", down=True)
        self._digits_player_vol = Digits("100%", down=True)
        self._digits_player_headset = Digits("100%", down=True)
        self._digits_menu_timer = Digits("25:00", down=True)
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
            "capitalize_title": Toggle(Settings.capitalize_title),
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
        self._gap = Spring(float(Settings.pos_y))
        self._pos_x = Spring(float(Settings.pos_x))

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
        self._pos_x.tune(240, 26)

        self._line_bar = LineBar()
        self._skip_prev = Skip(back=True)
        self._skip_next = Skip(back=False)
        self._cover_scale = Spring(1.0)
        self._cover_scale.tune(260, 13)
        self._lean = Spring(0.0)
        self._lean.tune(230, 15)

        self._grab: str = "none"
        self._grab_from: tuple[float, float] = (0.0, 0.0)
        self._grab_last: tuple[float, float] = (0.0, 0.0)
        self._grab_at: float = 0.0
        self._grab_pace_x: float = 0.0
        self._grab_pace_y: float = 0.0
        self._pull_by: float = 0.0
        self._lean_by: float = 0.0

        self._alarm_start_time: float = 0.0
        self._shake_x: float = 0.0
        self._bell_angle: float = 0.0

        self._updater = Updater.get()
        self._updater.add_callback(lambda: GLib.idle_add(self.area.queue_draw))
        self._btn_update_rect: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)

        self._dragging_look: bool = False
        self._drag_start_x: float = 0.0
        self._drag_start_y: float = 0.0
        self._drag_orig_pos_x: int = 0
        self._drag_orig_pos_y: int = 0

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
        bat_info = get_battery_info()
        self._last_plugged = bat_info.is_plugged
        self._battery_known = False
        self._battery_pct = bat_info.percent
        self._battery_status = bat_info.status_text
        self._battery_color = bat_info.color
        self._bolt_spring = Spring(1.0 if bat_info.is_plugged else 0.0)
        self._bolt_spring.tune(320, 20)
        self._headset_pct = -1
        self._last_playing_time: float = 0.0
        self._clock_time_str = "00:00"
        self._clock_date_str = ""
        self._media_width = MEDIA_WIDTH
        self._player_room = False
        self._player_lyric_h = PLAYER_LYRIC_ROOM
        self._shimmer = Shimmer()
        self._player_col = Spring(0.0, 170.0, 26.0)
        self._player_last_active: int = -1
        self._player_prev_active: int = -1
        self._player_active_spring = Spring(1.0, 160.0, 22.0)
        self._player_row_waves: dict[int, Spring] = {}
        self._player_row_dues: dict[int, float] = {}
        self._player_rows_cache: Optional[tuple[object, list[tuple[float, str, float, float, float]]]] = None
        self._compact_lines_cache: Optional[tuple[object, list[tuple[float, str]]]] = None
        self._lyric_scroll = 0.0
        self._lyric_overflow = 0.0
        self._lyric_span = 0.0
        self._lyric_line_start = 0.0
        self._lyric_target: Optional[tuple[str, float, float, bool]] = None
        self._lyric_enter = Spring(1.0, 220.0, 26.0)
        self._lyric_prev_alpha = Spring(0.0, 220.0, 26.0)
        self._lyric_prev_text = ""
        self._lyric_prev_target: Optional[tuple[str, float, float, bool]] = None
        self._skip_direction = 1
        self._skip_at = -SKIP_MEMORY
        self._source_at = -SKIP_MEMORY
        self._source_app_name = ""
        self._last_track_key = ""
        self._last_lyric_text = ""
        self._last_lyric_key: Optional[tuple[Optional[float], str]] = None

        self._shelf = Shelf()
        self._shelf.add_change_listener(self.on_shelf_changed)
        self._carry_shelf = Spring(0.0)
        self._carry_timer = Spring(0.0)
        self._shelf_wide = Spring(CARRY_SHELF)
        self._shelf_scroll = Spring(0.0)
        self._carry_shelf.tune(260, 24)
        self._carry_timer.tune(260, 24)
        self._shelf_wide.tune(260, 24)
        self._shelf_scroll.tune(260, 30)
        self._digits_shelf = Digits(str(len(self._shelf.items)) if self._shelf.items else "0")
        self._digits_shelf_menu = Digits(str(len(self._shelf.items)) if self._shelf.items else "0")
        self._shelf_shown: int = len(self._shelf.items)

        self._quiet: Optional[bool] = None
        self._focus_swing = Spring(0.0)
        self._focus_scale = Spring(1.0)
        self._focus_swing.tune(260, 24)
        self._focus_scale.tune(260, 24)
        self._last_quiet_poll: float = 0.0

        self._shelf_hover_tile: Optional[int] = None
        self._shelf_hover_cross: Optional[int] = None
        self._shelf_btn_add_rect: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
        self._shelf_btn_clear_rect: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
        self._dragging_shelf: bool = False

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

        self._goo.set_glass(Settings.glass / 100.0)
        self.update_clock()
        self.sync_accent()
        self.sync_rim(snap=True)
        self.update_view()
        self.set_targets()

        if forced_timer > 0:
            self.start_timer(forced_timer)

    def is_click_locked(self) -> bool:
        if not Settings.click_lock:
            return False
        if self._panel != Panel.PLAYER or self._current_view != View.MEDIA_BIG:
            return False
        now = time.monotonic()
        return now < self._click_lock_until

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

        key_ctrl = Gtk.EventControllerKey.new()
        key_ctrl.connect("key-pressed", self.on_key_pressed)
        self.area.add_controller(key_ctrl)

        try:
            drag_source = Gtk.DragSource.new()
            drag_source.set_actions(Gdk.DragAction.COPY | Gdk.DragAction.LINK)
            drag_source.connect("prepare", self.on_drag_prepare)
            drag_source.connect("drag-begin", self.on_drag_begin)
            drag_source.connect("drag-end", self.on_drag_end)
            drag_source.connect("drag-cancel", self.on_drag_cancel)
            self.area.add_controller(drag_source)
        except Exception:
            pass

        try:
            formats = Gdk.ContentFormats.new(['text/uri-list', 'text/plain', 'text/plain;charset=utf-8']).union(
                Gdk.ContentFormats.new_for_gtype(Gdk.FileList)
            )
            drop_target = Gtk.DropTargetAsync.new(formats, Gdk.DragAction.COPY | Gdk.DragAction.MOVE | Gdk.DragAction.LINK)
            drop_target.connect("accept", self.on_drop_accept)
            drop_target.connect("drag-enter", self.on_drop_enter)
            drop_target.connect("drag-motion", self.on_drop_motion)
            drop_target.connect("drop", self.on_drop)
            self.area.add_controller(drop_target)
        except Exception:
            pass

    def on_drop_accept(self, target: Gtk.DropTargetAsync, drop: Gdk.Drop) -> bool:
        return True

    def on_drop_enter(self, target: Gtk.DropTargetAsync, drop: Gdk.Drop, x: float, y: float) -> Gdk.DragAction:
        self.open_panel(Panel.SHELF)
        self.update_view()
        self.set_targets()
        return Gdk.DragAction.COPY

    def on_drop_motion(self, target: Gtk.DropTargetAsync, drop: Gdk.Drop, x: float, y: float) -> Gdk.DragAction:
        return Gdk.DragAction.COPY

    def on_drop(self, target: Gtk.DropTargetAsync, drop: Gdk.Drop, x: float, y: float) -> bool:
        formats = drop.get_formats()
        if formats.contain_gtype(Gdk.FileList):
            drop.read_value_async(Gdk.FileList, GLib.PRIORITY_DEFAULT, None, self._on_drop_file_list_ready)
            return True
        elif formats.contain_mime_type("text/uri-list") or formats.contain_mime_type("text/plain"):
            drop.read_async(["text/uri-list", "text/plain"], GLib.PRIORITY_DEFAULT, None, self._on_drop_uri_ready)
            return True
        return False

    def _on_drop_uri_ready(self, drop: Gdk.Drop, result: Gio.AsyncResult) -> None:
        try:
            stream, _ = drop.read_finish(result)
        except Exception:
            try:
                drop.finish(Gdk.DragAction.COPY)
            except Exception:
                pass
            return

        if stream is None:
            try:
                drop.finish(Gdk.DragAction.COPY)
            except Exception:
                pass
            return

        def read_worker() -> None:
            paths: list[str] = []
            try:
                chunks: list[bytes] = []
                while True:
                    b = stream.read_bytes(65536, None)
                    data = b.get_data() if b else b""
                    if not data:
                        break
                    chunks.append(data)
                try:
                    stream.close(None)
                except Exception:
                    pass
                raw_text = b"".join(chunks).decode("utf-8", errors="replace")
                for line in raw_text.splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if line.startswith("file://"):
                        path = urllib.parse.unquote(urllib.parse.urlsplit(line).path)
                    else:
                        path = urllib.parse.unquote(line)
                    if os.path.exists(path):
                        paths.append(path)
            except Exception:
                pass
            finally:
                def on_done() -> None:
                    try:
                        drop.finish(Gdk.DragAction.COPY)
                    except Exception:
                        pass
                    if paths:
                        self._shelf.add(paths)
                        self.open_panel(Panel.SHELF)
                        self.update_view()
                        self.set_targets()
                GLib.idle_add(on_done)

        threading.Thread(target=read_worker, daemon=True).start()

    def _on_drop_file_list_ready(self, drop: Gdk.Drop, result: Gio.AsyncResult) -> None:
        paths = []
        try:
            val = drop.read_value_finish(result)
            if hasattr(val, "get_value"):
                val = val.get_value()
            files = val.get_files() if hasattr(val, "get_files") else (val if hasattr(val, "__iter__") else [])
            for f in files:
                if hasattr(f, "get_path"):
                    p = f.get_path()
                    if p and os.path.exists(p):
                        paths.append(p)
            if paths:
                self._shelf.add(paths)
                self.open_panel(Panel.SHELF)
                self.update_view()
                self.set_targets()
        except Exception:
            pass
        finally:
            try:
                drop.finish(Gdk.DragAction.COPY)
            except Exception:
                pass

    def _get_shelf_item_at(self, lx: float, ly: float) -> Optional[Any]:
        if self._current_view != View.SHELF or not self._shelf.items:
            return None
        px, py, pw, ph, _, _ = self._get_pill_and_bubble_rects()
        strip_x = px + 18.0
        strip_y = py + 42.0
        strip_w = pw - 36.0
        strip_h = 80.0
        if not (strip_x <= lx <= strip_x + strip_w and strip_y <= ly <= strip_y + strip_h):
            return None
        offset_x = self._shelf_scroll.value
        for idx, item in enumerate(self._shelf.items):
            tx = strip_x - offset_x + idx * 68.0
            ty = strip_y + 4.0
            cross_x = tx + 44.0
            cross_y = ty - 4.0
            if cross_x <= lx <= cross_x + 18.0 and cross_y <= ly <= cross_y + 18.0:
                return None
            if tx <= lx <= tx + 56.0 and ty <= ly <= ty + 70.0:
                return item
        return None

    def on_drag_prepare(self, source: Gtk.DragSource, x: float, y: float) -> Optional[Gdk.ContentProvider]:
        lx, ly = self._screen_to_local(x, y)
        item = self._get_shelf_item_at(lx, ly)
        if item is None or not os.path.exists(item.path):
            return None

        gfile = Gio.File.new_for_path(item.path)
        fl = Gdk.FileList.new_from_list([gfile])
        cp_fl = Gdk.ContentProvider.new_for_value(fl)
        cp_f = Gdk.ContentProvider.new_for_value(gfile)

        uri_str = f"{gfile.get_uri()}\r\n"
        uri_bytes = GLib.Bytes.new(uri_str.encode("utf-8"))
        cp_uri = Gdk.ContentProvider.new_for_bytes("text/uri-list", uri_bytes)

        txt_bytes = GLib.Bytes.new(f"{item.path}\n".encode("utf-8"))
        cp_txt = Gdk.ContentProvider.new_for_bytes("text/plain", txt_bytes)

        try:
            tex = None
            if item.surface is not None:
                buf = io.BytesIO()
                item.surface.write_to_png(buf)
                tex = Gdk.Texture.new_from_bytes(GLib.Bytes.new(buf.getvalue()))
            elif item.path:
                try:
                    tex = Gdk.Texture.new_from_filename(item.path)
                except Exception:
                    pass
            if tex is not None:
                tw = tex.get_width()
                th = tex.get_height()
                source.set_icon(tex, int(tw / 2), int(th / 2))
        except Exception:
            pass

        return Gdk.ContentProvider.new_union([cp_fl, cp_f, cp_uri, cp_txt])

    def on_drag_begin(self, source: Gtk.DragSource, drag: Gdk.Drag) -> None:
        self._dragging_shelf = True

    def on_drag_end(self, source: Gtk.DragSource, drag: Gdk.Drag, delete_data: bool) -> None:
        self._dragging_shelf = False

    def on_drag_cancel(self, source: Gtk.DragSource, drag: Gdk.Drag, reason: Gdk.DragCancelReason) -> bool:
        self._dragging_shelf = False
        return False

    def on_shelf_changed(self) -> None:
        count = len(self._shelf.items)
        self._digits_shelf.set_text(str(count) if count > 0 else "0")
        self._digits_shelf_menu.set_text(str(count) if count > 0 else "")
        self._shelf_shown = count
        self.set_targets()
        self.area.queue_draw()

    def _get_pill_and_bubble_rects(self) -> Tuple[
        float, float, float, float, float,
        Optional[Tuple[float, float, float, float, float]]
    ]:
        size = max(0.01, self._size.value)
        scale = max(0.01, self._scale.value)
        w = max(24.0, self._w.value)
        h = max(24.0, self._h.value)
        r = min(w / 2.0, min(h / 2.0, max(0.0, self._r.value)))

        cx = self.win_width / 2.0 + self._pos_x.value
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
            timer_w = self._carry_timer.value * CARRY_TIMER
            shelf_w = self._carry_shelf.value * self._shelf_wide.value
            both = (self._carry_timer.value > 0.05 and self._carry_shelf.value > 0.05)
            base_bw = max(CARRY_SHELF, timer_w + shelf_w + (6.0 if both else 0.0))
            past = ((BUBBLE_GAP + base_bw) * split - base_bw) / scale
            bx = pill_right + past
            by = 0.0
            bw = base_bw * bubble_scale / scale
            bh = BUBBLE_HEIGHT * bubble_scale / scale
            br = bh / 2.0
            bubble_info = (bx, by, bw, bh, br)

        return (pill_x, pill_y, w, h, r, bubble_info)

    def _screen_to_local(self, sx: float, sy: float) -> Tuple[float, float]:
        size = max(0.01, self._size.value)
        scale = max(0.01, self._scale.value)
        cx = self.win_width / 2.0 + self._pos_x.value
        offset_y = self._offset.value + self._gap.value / size
        pill_top = offset_y * size

        lx = (sx - cx) / (size * scale)
        ly = (sy - pill_top) / (size * scale)
        return lx, ly

    def on_mouse_enter(self, controller: Gtk.EventControllerMotion, x: float, y: float) -> None:
        self._hover = True
        self._collapse_expiry = 0.0
        self.set_targets()

    def _finish_grab(self, x: float, y: float) -> None:
        if self._grab == "none":
            return
        grab = self._grab
        pulled = self._pull_by
        leant = self._lean_by
        now = time.monotonic()
        pace_x = self._grab_pace_x if (now - self._grab_at < 0.09) else 0.0
        pace_y = self._grab_pace_y if (now - self._grab_at < 0.09) else 0.0

        self._grab = "none"
        self._pull_by = 0.0
        self._lean_by = 0.0
        self._lean.target = 0.0
        self._pressed = False

        if grab == "lean":
            way = 0
            if abs(leant) >= 12.0 and abs(pace_x) >= 550.0:
                way = int(math.copysign(1, pace_x))
            elif abs(leant) >= 40.0:
                way = int(math.copysign(1, leant))

            if way != 0 and self.media_active:
                if way < 0:
                    self.skipped(1)
                    self._skip_next.play()
                    self._media.next()
                else:
                    self.skipped(-1)
                    self._skip_prev.play()
                    self._media.previous()
            self.set_targets()
            return

        if grab == "pull":
            way_y = 0
            if abs(pulled) >= 12.0 and abs(pace_y) >= 550.0:
                way_y = 1
            elif abs(pulled) >= 42.0:
                way_y = 1

            if way_y <= 0:
                self.set_targets()
                return

            self.open_panel(Panel.PLAYER if (self.media_active or not self._timer.active) else Panel.TIMER)
            self.update_view()
            self.set_targets()
            return

        if grab in ("held", "none"):
            if self._ringing:
                self.quiet_alarm()
                self.open_panel(Panel.NONE)
            elif self._panel != Panel.NONE:
                self.open_panel(Panel.NONE)
            else:
                self.open_panel(Panel.PLAYER if (self.media_active or not self._timer.active) else Panel.TIMER)
            self.update_view()
            self.set_targets()
            return

    def _cancel_grab(self) -> None:
        if self._grab == "none":
            return
        self._grab = "none"
        self._pull_by = 0.0
        self._lean_by = 0.0
        self._lean.target = 0.0
        self._pressed = False
        self._dragging_look = False
        self._scrubbing = False
        self.set_targets()

    def on_mouse_leave(self, controller: Gtk.EventControllerMotion) -> None:
        self._hover = False
        self._bubble_hover = False
        self._bubble_pressed = False
        self._row_list_menu.clear_hover()
        self._row_list_settings.clear_hover()
        self._row_list_look.clear_hover()
        if self._grab != "none":
            self._cancel_grab()
        else:
            self._pressed = False
        self.set_targets()
        if self._panel != Panel.NONE:
            self._collapse_expiry = time.monotonic() + COLLAPSE_DELAY_SEC

    def on_mouse_motion(self, controller: Gtk.EventControllerMotion, x: float, y: float) -> None:
        self._mouse_x = x
        self._mouse_y = y

        if self._grab != "none" or self._pressed or self._dragging_look:
            state = 0
            if hasattr(controller, "get_current_event_state"):
                try:
                    state = int(controller.get_current_event_state())
                except Exception:
                    pass
            if state and not (state & Gdk.ModifierType.BUTTON1_MASK):
                self._cancel_grab()
                return

        if self._dragging_look and self._current_view == View.LOOK:
            step = self.get_modifier_step(controller)
            dx = x - self._drag_start_x
            dy = y - self._drag_start_y
            snapped_dx = round(dx / step) * step
            snapped_dy = round(dy / step) * step
            self.set_pos_x(self._drag_orig_pos_x + int(snapped_dx))
            self.set_pos_y(max(0, self._drag_orig_pos_y + int(snapped_dy)))
            return

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

        if self._grab != "none":
            now = time.monotonic()
            dt = now - self._grab_at
            if dt >= 0.004:
                inst_vx = (x - self._grab_last[0]) / dt
                inst_vy = (y - self._grab_last[1]) / dt
                decay = 1.0 - math.exp(-dt / 0.03)
                self._grab_pace_x += (inst_vx - self._grab_pace_x) * decay
                self._grab_pace_y += (inst_vy - self._grab_pace_y) * decay
                self._grab_last = (x, y)
                self._grab_at = now

            dx = x - self._grab_from[0]
            dy = y - self._grab_from[1]
            if self._grab == "held":
                if abs(dx) < 6.0 and abs(dy) < 6.0:
                    return
                self._grab = "lean" if abs(dx) > abs(dy) else "pull"
                self.update_input_region()

            if self._grab == "pull":
                self._pull_by = max(0.0, dy)
            elif self._grab == "lean":
                self._lean_by = dx
            self.set_targets()

        if self._scrubbing and self._seek_rect[2] > 0:
            rx, _, rw, _ = self._seek_rect
            raw_x = lx - rx
            if Settings.line_bar and self._media.duration >= 1.0 and self._lyrics_lines:
                raw_x = self._line_bar.snap(raw_x, rw)
            self._scrub = max(0.0, min(1.0, raw_x / rw))
            self.area.queue_draw()

        if self._current_view == View.MENU:
            row_y_start = py + 36.0
            row_h = 40.0
            hovered = None
            for idx in range(5):
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
            for idx in range(10):
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
            for idx in range(11):
                ry = row_y_start + idx * row_h
                if px + 10 <= lx <= px + pw - 10 and ry <= ly < ry + row_h:
                    hovered = idx
                    self._row_list_look.move_to(ry, row_h, idx)
                    break
            if hovered is None:
                self._row_list_look.clear_hover()
            self.area.queue_draw()

        elif self._current_view == View.SHELF:
            strip_x = px + 18.0
            strip_y = py + 42.0
            strip_w = pw - 36.0
            offset_x = self._shelf_scroll.value
            for idx, item in enumerate(self._shelf.items):
                tx = strip_x - offset_x + idx * 68.0
                ty = strip_y + 4.0
                in_tile = tx <= lx <= tx + 56.0 and ty <= ly <= ty + 56.0
                cross_x = tx + 44.0
                cross_y = ty - 4.0
                in_cross = cross_x <= lx <= cross_x + 18.0 and cross_y <= ly <= cross_y + 18.0
                item.is_hovered = in_tile or in_cross
                item.swell.target = 1.06 if (in_tile or in_cross) else 1.0
                item.cross.target = 1.0 if (in_tile or in_cross) else 0.0
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
                    raw_x = lx - rx
                    if Settings.line_bar and self._media.duration >= 1.0 and self._lyrics_lines:
                        raw_x = self._line_bar.snap(raw_x, rw)
                    self._scrub = max(0.0, min(1.0, raw_x / rw))
                    self._seek_x.tune(900, 60)
                    self.area.queue_draw()
                    return

            if self._panel == Panel.NONE and not self._ringing:
                self._grab = "held"
                self._grab_from = (x, y)
                self._grab_last = (x, y)
                self._grab_at = time.monotonic()
                self._grab_pace_x = 0.0
                self._grab_pace_y = 0.0

            if self._current_view == View.MENU:
                self._row_list_menu.set_pressed(True)
            elif self._current_view == View.SETTINGS:
                self._row_list_settings.set_pressed(True)
            elif self._current_view == View.LOOK:
                self._row_list_look.set_pressed(True)
                self._dragging_look = True
                self._drag_start_x = x
                self._drag_start_y = y
                self._drag_orig_pos_x = Settings.pos_x
                self._drag_orig_pos_y = Settings.pos_y

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
            timer_on = self._carry_timer.value > 0.05
            shelf_on = self._carry_shelf.value > 0.05
            if timer_on and shelf_on:
                bx = bubble[0] if bubble else 0.0
                if lx < bx + CARRY_TIMER:
                    self.open_panel(Panel.TIMER)
                else:
                    self.open_panel(Panel.SHELF)
            elif timer_on:
                self.open_panel(Panel.TIMER)
            else:
                self.open_panel(Panel.SHELF)
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

        if self._grab != "none":
            self._finish_grab(x, y)
            return

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
                self._skip_prev.play()
                self._media.previous()
                return

            bx, by, bw, bh = self._btn_play_rect
            if bx <= lx <= bx + bw and by <= ly <= by + bh:
                self._media.toggle_play()
                return

            bx, by, bw, bh = self._btn_next_rect
            if bx <= lx <= bx + bw and by <= ly <= by + bh:
                self.skipped(1)
                self._skip_next.play()
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
            for idx in range(5):
                ry = row_y_start + idx * row_h
                if px + 10 <= lx <= px + pw - 10 and ry <= ly < ry + row_h:
                    if idx == 0:
                        self.open_panel(Panel.TIMER if self._timer.active else Panel.TIMER_SET)
                    elif idx == 1:
                        self.open_panel(Panel.SHELF)
                    elif idx == 2:
                        self.open_panel(Panel.SETTINGS)
                    elif idx == 3:
                        self.open_panel(Panel.LOOK)
                    elif idx == 4:
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
                "capitalize_title",
            ]
            for idx in range(9):
                key = setting_keys[idx]
                ry = row_y_start + idx * row_h
                if px <= lx <= px + pw and ry <= ly < ry + row_h:
                    cur = getattr(Settings, key)
                    setattr(Settings, key, not cur)
                    self._toggles[key].set_state(not cur, animate=True)
                    if key == "rim":
                        self.sync_rim()
                    elif key == "lyrics":
                        self.track_lyrics()
                    elif key == "hide_fullscreen":
                        self.check_fullscreen()
                    elif key == "capitalize_title":
                        self.update_lyric()
                    self.area.queue_draw()
                    return

            if px <= lx <= px + pw and row_y_start + 9 * row_h <= ly < row_y_start + 10 * row_h:
                self.open_panel(Panel.UPDATE)
                self._updater.check_async()
                self.update_view()
                self.set_targets()
                return

        if self._current_view == View.LOOK:
            if self._dragging_look:
                did_drag = abs(x - self._drag_start_x) >= 4 or abs(y - self._drag_start_y) >= 4
                self._dragging_look = False
                if did_drag:
                    return

            if px <= lx <= px + 150 and py + 12 <= ly <= py + 40:
                self.open_panel(Panel.MENU)
                self.update_view()
                self.set_targets()
                return

            row_y_start = py + 44.0
            row_h = 40.0
            mod_step = self.get_modifier_step()

            if px <= lx <= px + pw:
                if row_y_start <= ly < row_y_start + row_h:
                    idx = SCALES.index(Settings.scale) if Settings.scale in SCALES else 1
                    new_scale = SCALES[(idx + 1) % len(SCALES)]
                    self.set_scale(new_scale)
                    return

                if row_y_start + row_h <= ly < row_y_start + 2 * row_h:
                    self.set_pos_y(Settings.pos_y + mod_step)
                    return

                if row_y_start + 2 * row_h <= ly < row_y_start + 3 * row_h:
                    self.set_pos_x(Settings.pos_x + mod_step)
                    return

                if row_y_start + 3 * row_h <= ly < row_y_start + 4 * row_h:
                    idx = RADII.index(Settings.radius) if Settings.radius in RADII else -1
                    new_radius = RADII[(idx + 1) % len(RADII)] if idx >= 0 else RADII[0]
                    self.set_radius(new_radius)
                    return

                if row_y_start + 4 * row_h <= ly < row_y_start + 5 * row_h:
                    idx = HEIGHTS.index(Settings.height) if Settings.height in HEIGHTS else -1
                    new_h = HEIGHTS[(idx + 1) % len(HEIGHTS)] if idx >= 0 else HEIGHTS[0]
                    self.set_height(new_h)
                    return

                if row_y_start + 5 * row_h <= ly < row_y_start + 6 * row_h:
                    idx = TEXT_SCALES.index(Settings.text_scale) if Settings.text_scale in TEXT_SCALES else -1
                    new_ts = TEXT_SCALES[(idx + 1) % len(TEXT_SCALES)] if idx >= 0 else TEXT_SCALES[0]
                    self.set_text_scale(new_ts)
                    return

                if row_y_start + 6 * row_h <= ly < row_y_start + 7 * row_h:
                    modes = [MATERIAL_LIQUID, MATERIAL_MATTE, MATERIAL_NONE]
                    cur_idx = modes.index(Settings.material) if Settings.material in modes else 0
                    new_mat = modes[(cur_idx + 1) % len(modes)]
                    self.set_material(new_mat)
                    return

                if row_y_start + 7 * row_h <= ly < row_y_start + 8 * row_h:
                    idx = GLASS_LEVELS.index(Settings.glass) if Settings.glass in GLASS_LEVELS else -1
                    new_glass = GLASS_LEVELS[(idx + 1) % len(GLASS_LEVELS)] if idx >= 0 else GLASS_LEVELS[0]
                    self.set_glass(new_glass)
                    return

                if row_y_start + 8 * row_h <= ly < row_y_start + 9 * row_h:
                    Settings.line_bar = not Settings.line_bar
                    self.area.queue_draw()
                    return

                if row_y_start + 9 * row_h <= ly < row_y_start + 10 * row_h:
                    Settings.equalizer_dots = not Settings.equalizer_dots
                    self.area.queue_draw()
                    return

                if row_y_start + 10 * row_h <= ly < row_y_start + 11 * row_h:
                    colors = [c[0] for c in LOOK_COLORS]
                    cur_idx = colors.index(Settings.accent) if Settings.accent in colors else 0
                    new_accent = colors[(cur_idx + 1) % len(colors)]
                    self.set_accent(new_accent)
                    return

            swatch_y = row_y_start + 11 * row_h + 18.0
            step_x = (pw - 20.0) / len(LOOK_COLORS)
            if swatch_y - 15.0 <= ly <= swatch_y + 15.0 and px <= lx <= px + pw:
                idx = int((lx - (px + 10.0)) / step_x)
                if 0 <= idx < len(LOOK_COLORS):
                    self.set_accent(LOOK_COLORS[idx][0])
                    return

        if self._current_view == View.UPDATE:
            if px + 10 <= lx <= px + 150 and py + 12 <= ly <= py + 40:
                self.open_panel(Panel.SETTINGS)
                self.update_view()
                self.set_targets()
                return

            bx, by, bw, bh = self._btn_update_rect
            if bx <= lx <= bx + bw and by <= ly <= by + bh:
                if self._updater.state == UpdateState.READY:
                    self._updater.restart()
                elif self._updater.state == UpdateState.AVAILABLE:
                    self._updater.start_download_async()
                else:
                    self._updater.check_async(force=True)
                return

        if self._current_view == View.SHELF:
            if px + 10 <= lx <= px + 100 and py + 12 <= ly <= py + 40:
                self.open_panel(Panel.MENU)
                self.update_view()
                self.set_targets()
                return

            bx, by, bw, bh = self._shelf_btn_add_rect
            if bx <= lx <= bx + bw and by <= ly <= by + bh:
                self.pick_files_for_shelf()
                return

            cx, cy, cw, ch = self._shelf_btn_clear_rect
            if cx <= lx <= cx + cw and cy <= ly <= cy + ch:
                self._shelf.clear()
                return

            strip_x = px + 18.0
            strip_y = py + 42.0
            strip_w = pw - 36.0
            strip_h = 80.0

            if not self._shelf.items:
                if strip_x <= lx <= strip_x + strip_w and strip_y <= ly <= strip_y + strip_h:
                    self.pick_files_for_shelf()
                return

            offset_x = self._shelf_scroll.value
            for idx, item in enumerate(self._shelf.items):
                tx = strip_x - offset_x + idx * 68.0
                ty = strip_y + 4.0
                cross_x = tx + 44.0
                cross_y = ty - 4.0
                if cross_x <= lx <= cross_x + 18.0 and cross_y <= ly <= cross_y + 18.0:
                    self._shelf.remove(item)
                    return
                if tx <= lx <= tx + 56.0 and ty <= ly <= ty + 56.0:
                    if self._dragging_shelf:
                        return
                    self._shelf.open_item(item)
                    self.open_panel(Panel.NONE)
                    self.update_view()
                    self.set_targets()
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

        if self._current_view == View.SHELF:
            max_scroll = max(0.0, len(self._shelf.items) * 68.0 - 4.0 - (SHELF_WIDE - 36.0))
            new_target = max(0.0, min(max_scroll, self._shelf_scroll.target - step * 68.0))
            self._shelf_scroll.target = new_target
            return True

        lx, ly = self._screen_to_local(self._mouse_x, self._mouse_y)
        px, py, pw, ph, _, _ = self._get_pill_and_bubble_rects()

        if self._current_view == View.LOOK:
            nudge = 1 if up else -1
            mod_step = self.get_modifier_step(controller)
            row_y_start = py + 44.0
            row_h = 40.0

            if row_y_start <= ly < row_y_start + row_h:
                idx = SCALES.index(Settings.scale) if Settings.scale in SCALES else 1
                new_idx = max(0, min(len(SCALES) - 1, idx + nudge))
                self.set_scale(SCALES[new_idx])
                return True

            if row_y_start + row_h <= ly < row_y_start + 2 * row_h:
                new_y = Settings.pos_y - nudge * mod_step
                self.set_pos_y(new_y)
                return True

            if row_y_start + 2 * row_h <= ly < row_y_start + 3 * row_h:
                new_x = Settings.pos_x + nudge * mod_step
                self.set_pos_x(new_x)
                return True

            if row_y_start + 3 * row_h <= ly < row_y_start + 4 * row_h:
                new_radius = max(0, min(100, Settings.radius + nudge * 5))
                self.set_radius(new_radius)
                return True

            if row_y_start + 4 * row_h <= ly < row_y_start + 5 * row_h:
                new_h = max(0, min(16, Settings.height + nudge))
                self.set_height(new_h)
                return True

            if row_y_start + 5 * row_h <= ly < row_y_start + 6 * row_h:
                new_ts = max(80, min(130, Settings.text_scale + nudge * 5))
                self.set_text_scale(new_ts)
                return True

            if row_y_start + 6 * row_h <= ly < row_y_start + 7 * row_h:
                modes = [MATERIAL_LIQUID, MATERIAL_MATTE, MATERIAL_NONE]
                cur_idx = modes.index(Settings.material) if Settings.material in modes else 0
                new_idx = max(0, min(len(modes) - 1, cur_idx - nudge))
                self.set_material(modes[new_idx])
                return True

            if row_y_start + 7 * row_h <= ly < row_y_start + 8 * row_h:
                new_glass = max(20, min(100, Settings.glass + nudge * 5))
                self.set_glass(new_glass)
                return True

            if row_y_start + 8 * row_h <= ly:
                colors = [c[0] for c in LOOK_COLORS]
                cur_idx = colors.index(Settings.accent) if Settings.accent in colors else 0
                new_idx = max(0, min(len(colors) - 1, cur_idx + nudge))
                self.set_accent(colors[new_idx])
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
            elif self._panel == Panel.SHELF:
                target = View.SHELF
            elif self._panel == Panel.UPDATE:
                target = View.UPDATE
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
        else:
            self._shimmer.run(False)
            if target == View.MEDIA:
                snap = self._previous_view not in (View.TOAST, View.IDLE) and self._last_lyric_key is not None
                self.update_lyric(snap=snap)

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
        if view == View.LOOK:
            return Dims(LOOK_WIDTH, LOOK_HEIGHT, 34)
        return d

    def set_targets(self) -> None:
        d = self.size_of(self._current_view)
        compact = d.h < 40.0

        pull = (self._pull_by * 96.0) / (self._pull_by + 96.0) if (self._pull_by + 96.0) > 0 else 0.0
        abs_lean = abs(self._lean_by)
        lean_rubber = (abs_lean * 44.0) / (abs_lean + 44.0) if (abs_lean + 44.0) > 0 else 0.0
        lean = math.copysign(lean_rubber, self._lean_by) if self._lean_by != 0 else 0.0
        taken = self._grab in ("pull", "lean")

        self._w.target = d.w + pull * 0.4 + abs(lean) * 0.6
        self._h.target = d.h + pull + Settings.height
        self._r.target = (d.r + pull * 0.3) * Settings.radius / 100.0
        self._lean.target = lean
        self._cover_scale.target = 0.85 if (self._current_view == View.MEDIA_BIG and not self._media.is_playing) else 1.0

        timer = self._timer.active and self._current_view != View.TIMER
        shelf = len(self._shelf.items) > 0
        split = compact and (timer or shelf)
        self._split.target = 1.0 if split else 0.0
        self._carry_timer.target = 1.0 if timer else 0.0
        self._carry_shelf.target = 1.0 if shelf else 0.0
        count = len(self._shelf.items)
        self._shelf_wide.target = 64.0 if count >= 100 else (54.0 if count >= 10 else 50.0)

        if (self._hidden or self._away) and not self._ringing:
            self._offset.target = -(d.h + 30.0 + Settings.gap * 100.0 / Settings.scale)
        else:
            self._offset.target = 0.0

        self._scale.target = (
            1.0 if taken else ((0.93 if compact else 0.975)
            if self._pressed
            else (1.07 if (self._hover and compact) else 1.0))
        )
        self._bubble_scale.target = (
            0.93 if self._bubble_pressed else (1.07 if self._bubble_hover else 1.0)
        )
        self.update_input_region()
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

    def sync_rim(self, snap: bool = False) -> None:
        music = (
            self._media.has_track
            and (self.media_active or self._current_view in (View.MEDIA, View.MEDIA_BIG, View.TOAST))
        )
        if not Settings.rim:
            tint = None
        elif Settings.accent is not None:
            tint = Settings.accent
        elif music:
            tint = self._media.accent
        else:
            tint = None
        if tint != self._rim_tint or snap:
            self._rim_tint = tint
            self._goo.tint(tint, duration_sec=0.0 if snap else 0.45)

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
        moving |= self._pos_x.advance(dt)
        moving |= self._split.advance(dt)
        moving |= self._bubble_scale.advance(dt)
        moving |= self._push.advance(dt)
        moving |= self._carry_shelf.advance(dt)
        moving |= self._carry_timer.advance(dt)
        moving |= self._shelf_scroll.advance(dt)
        moving |= self._shelf_wide.advance(dt)
        moving |= self._focus_swing.advance(dt)
        moving |= self._focus_scale.advance(dt)
        moving |= self._lean.advance(dt)
        moving |= self._cover_scale.advance(dt)
        moving |= self._bolt_spring.advance(dt)
        moving |= self._skip_prev.advance(dt)
        moving |= self._skip_next.advance(dt)
        moving |= self._shelf.tick(dt)
        moving |= self._digits_shelf.tick(dt)
        moving |= self._digits_shelf_menu.tick(dt)
        self._poll_quiet(now)

        if self._ringing:
            moving = True
            ring_t = (now - self._alarm_start_time) % 1.5
            if ring_t < 0.8:
                st = ring_t / 0.8
                angles = [24.0, -22.0, 17.0, -13.0, 8.0, -4.0, 0.0]
                idx_f = st * (len(angles) - 1)
                idx_i = int(idx_f)
                frac = idx_f - idx_i
                a0 = angles[idx_i]
                a1 = angles[min(len(angles) - 1, idx_i + 1)]
                self._bell_angle = a0 + (a1 - a0) * frac
            else:
                self._bell_angle = 0.0

            if ring_t < 0.56:
                st = ring_t / 0.56
                shakes = [-3.5, 3.5, -3.0, 3.0, -2.0, 1.5, -1.0, 0.0]
                idx_f = st * (len(shakes) - 1)
                idx_i = int(idx_f)
                frac = idx_f - idx_i
                s0 = shakes[idx_i]
                s1 = shakes[min(len(shakes) - 1, idx_i + 1)]
                self._shake_x = s0 + (s1 - s0) * frac
            else:
                self._shake_x = 0.0
        else:
            self._shake_x = 0.0
            self._bell_angle = 0.0

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

        if self._current_view == View.MEDIA_BIG:
            moving |= self._player_col.advance(dt)
            moving |= self._player_active_spring.advance(dt)
            moving |= self._shimmer.tick(dt)
            for i, due in list(self._player_row_dues.items()):
                if now >= due:
                    del self._player_row_dues[i]
                    if i in self._player_row_waves:
                        self._player_row_waves[i].target = self._player_col.target
            for sp in self._player_row_waves.values():
                moving |= sp.advance(dt)

        if self._current_view == View.MEDIA and self._lyric_overflow > 0.0 and Settings.lyrics:
            moving |= self._advance_lyric_scroll(dt)

        if self._current_view == View.MEDIA and Settings.lyrics:
            moving |= self._lyric_enter.advance(dt)
            moving |= self._lyric_prev_alpha.advance(dt)
            if self._lyric_prev_alpha.value <= 0.0:
                self._lyric_prev_text = ""
                self._lyric_prev_target = None

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
        moving |= self._digits_clock.tick(dt)
        moving |= self._digits_big_clock.tick(dt)
        moving |= self._digits_charge.tick(dt)
        moving |= self._digits_info_vol.tick(dt)
        moving |= self._digits_info_headset.tick(dt)
        moving |= self._digits_info_battery.tick(dt)
        moving |= self._digits_pos.tick(dt)
        moving |= self._digits_rem.tick(dt)
        moving |= self._digits_player_vol.tick(dt)
        moving |= self._digits_player_headset.tick(dt)
        moving |= self._digits_menu_timer.tick(dt)
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

    def _poll_quiet(self, now: float) -> None:
        if now - self._last_quiet_poll < 1.0:
            return
        self._last_quiet_poll = now
        q = query_do_not_disturb()
        if q is None or q == self._quiet:
            return
        first = self._quiet is None
        self._quiet = q
        if first:
            return
        if q:
            self._focus_swing.value = -80.0
            self._focus_swing.target = 0.0
            self._focus_scale.value = 0.4
            self._focus_scale.target = 1.0
        else:
            self._focus_swing.value = 0.0
            self._focus_swing.target = 24.0
            self._focus_scale.value = 1.0
            self._focus_scale.target = 0.84
        self.show_transient(View.FOCUS, 2.2)

    def pick_files_for_shelf(self) -> None:
        def worker() -> None:
            try:
                import shutil
                if shutil.which("zenity"):
                    res = subprocess.run(
                        ["zenity", "--file-selection", "--multiple", "--separator=|"],
                        capture_output=True,
                        text=True,
                        timeout=60,
                    )
                    if res.returncode == 0 and res.stdout.strip():
                        paths = res.stdout.strip().split("|")
                        GLib.idle_add(self._shelf.add, paths)
                elif shutil.which("kdialog"):
                    res = subprocess.run(
                        ["kdialog", "--getopenfilename", "--multiple", "."],
                        capture_output=True,
                        text=True,
                        timeout=60,
                    )
                    if res.returncode == 0 and res.stdout.strip():
                        paths = res.stdout.strip().split(" ")
                        GLib.idle_add(self._shelf.add, paths)
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()

    def update_input_region(self) -> None:
        surf = self.get_surface()
        if not surf:
            return

        if (self._hidden or self._away) and not self._ringing:
            surf.set_input_region(cairo.Region())
            return

        if self._grab in ("pull", "lean") or self._dragging_look or self._scrubbing:
            w_win = max(1, int(self.win_width))
            h_win = max(1, int(self.win_height))
            reg = cairo.Region(cairo.RectangleInt(0, 0, w_win, h_win))
            surf.set_input_region(reg)
            return

        size = max(0.01, self._size.value)
        scale = max(0.01, self._scale.value)
        w = max(24.0, self._w.value)
        h = max(24.0, self._h.value + Settings.height)
        cx = self.win_width / 2.0 + self._pos_x.value
        offset_y = self._offset.value + self._gap.value / size
        pill_top = offset_y * size

        if pill_top + h * scale * size <= 0:
            surf.set_input_region(cairo.Region())
            return

        pill_left_win = cx - (w * scale * size) / 2.0 - 2.0
        pill_top_win = max(0.0, pill_top - 2.0)
        pill_w_win = w * scale * size + 4.0
        pill_h_win = h * scale * size + 4.0

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

            b_left_win = cx + bx * scale * size - 2.0
            b_top_win = max(0.0, pill_top - 2.0)
            b_w_win = bw * scale * size + 4.0
            b_h_win = bh * scale * size + 4.0
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
        self._digits_clock.set_text(self._clock_time_str)
        self._digits_big_clock.set_text(self._clock_time_str)
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
        info = get_battery_info()
        if not info.has_battery:
            return

        was_plugged = self._last_plugged
        was_pct = self._battery_pct
        was_known = self._battery_known

        self._battery_pct = info.percent
        self._battery_status = info.status_text
        self._battery_color = info.color
        self._digits_charge.set_text(f"{info.percent}%")
        self._digits_info_battery.set_text(f"{info.percent}%")

        if was_known:
            if info.is_plugged and not was_plugged:
                play_sound("charging")
                self._bolt_spring.value = 0.0
                self._bolt_spring.target = 1.0
                self.show_transient(View.CHARGE, 3.0)
            elif not info.is_plugged and was_plugged:
                play_sound("unplugged")
                self.show_transient(View.CHARGE, 2.0)
            elif info.is_plugged and info.percent >= 100 and was_pct < 100:
                play_sound("battery_full")
                self.notify(Glyph.Bolt, (0.20, 0.84, 0.29), "Батарея", "Полностью заряжена · 100%", seconds=3.5)
            elif not info.is_plugged and was_pct > 20 and info.percent <= 20:
                play_sound("battery_low")
                self.notify(Glyph.Battery, (1.0, 0.58, 0.0), "Низкий заряд", f"Осталось {info.percent}%", seconds=4.0)
            elif not info.is_plugged and was_pct > 10 and info.percent <= 10:
                play_sound("battery_critical")
                self.notify(Glyph.Battery, (1.0, 0.27, 0.23), "Батарея разряжена", f"Срочно подключите питание ({info.percent}%)", seconds=5.0)

        self._battery_known = True
        self._last_plugged = info.is_plugged

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
            self._player_col.value = 0.0
            self._player_col.target = 0.0
            self._player_last_active = -1
            self._player_prev_active = -1
            self._player_active_spring.value = 1.0
            self._player_active_spring.target = 1.0
            self._player_rows_cache = None
            self._compact_lines_cache = None
            self._lyric_scroll = 0.0
            self._last_lyric_key = None
            self._last_lyric_text = ""
            self._lyric_target = None
            self._lyric_prev_text = ""
            self._lyric_prev_target = None
            self._lyric_prev_alpha.value = 0.0
            self._lyric_prev_alpha.target = 0.0
            self._lyric_enter.value = 0.0
            self._lyric_enter.target = 1.0
            self._lyric_overflow = 0.0
            self._lyric_span = 0.0
            self._lyric_line_start = 0.0

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
            self._compact_lines_cache = None
            self._last_lyric_text = ""
            self._last_lyric_key = None
            self._lyric_target = None
            self._lyric_prev_text = ""
            self._lyric_prev_target = None
            self._lyric_prev_alpha.value = 0.0
            self._lyric_prev_alpha.target = 0.0
            self._lyric_enter.value = 1.0
            self._lyric_enter.target = 1.0

    PUNCT_ONLY = '.,;!?-—–:\"\'«» '

    @classmethod
    def _clean_phrase(cls, p: str) -> str:
        s = p.strip().strip(cls.PUNCT_ONLY).strip()
        if (s.startswith("(") and s.endswith(")")) or (s.startswith("[") and s.endswith("]")) or (s.startswith("{") and s.endswith("}")):
            inner = s[1:-1].strip().strip(cls.PUNCT_ONLY).strip()
            if inner:
                s = inner
        return s

    @classmethod
    def _normalize_phrase(cls, p: str) -> str:
        without_brackets = re.sub(r'\([^)]*\)|\[[^\]]*\]|\{[^}]*\}', '', p)
        target = without_brackets if without_brackets.strip() else p
        return re.sub(r'[\s.,!?;:\"\'—–\-\(\)\[\]\{\}«»]+', '', target.lower())

    @classmethod
    def _split_phrase_line(cls, text: str) -> list[str]:
        s = text.strip()
        if (s.startswith("(") and s.endswith(")")) or (s.startswith("[") and s.endswith("]")) or (s.startswith("{") and s.endswith("}")):
            s = s[1:-1].strip()
        parts = [cls._clean_phrase(p) for p in re.split(r'[,;!?]+\s*', s) if cls._clean_phrase(p)]
        if len(parts) > 1:
            norm0 = cls._normalize_phrase(parts[0])
            if norm0 and all(cls._normalize_phrase(p) == norm0 for p in parts):
                return parts
        clean_full = cls._clean_phrase(text)
        return [clean_full] if clean_full else []

    @classmethod
    def _process_compact_lines(cls, raw_lines: list[tuple[float, str]], duration: float) -> list[tuple[float, str]]:
        if not raw_lines:
            return []
        expanded: list[tuple[float, str, float, bool, str]] = []
        for idx, (t, txt) in enumerate(raw_lines):
            if not txt.strip():
                expanded.append((t, txt, 0.0, False, txt))
                continue
            parts = cls._split_phrase_line(txt)
            next_t = raw_lines[idx + 1][0] if idx + 1 < len(raw_lines) else max(duration, t + 4.0)
            line_span = max(0.5, next_t - t)

            if len(parts) > 1:
                step = line_span / len(parts)
                for k, p in enumerate(parts):
                    expanded.append((round(t + k * step, 3), p, round(step, 3), True, txt))
            else:
                expanded.append((t, txt, round(line_span, 3), False, txt))

        result: list[tuple[float, str]] = []
        i = 0
        while i < len(expanded):
            item = expanded[i]
            t, txt = item[0], item[1]
            if not txt.strip():
                result.append((t, txt))
                i += 1
                continue

            norm = cls._normalize_phrase(txt)
            j = i
            while j < len(expanded):
                cur_norm = cls._normalize_phrase(expanded[j][1])
                if cur_norm == norm:
                    j += 1
                elif (
                    j + 1 < len(expanded)
                    and cls._normalize_phrase(expanded[j + 1][1]) == norm
                    and (len(cls._clean_phrase(expanded[j][1])) <= 4 or (expanded[j][1].strip().startswith("(") and expanded[j][1].strip().endswith(")")))
                ):
                    j += 1
                else:
                    break

            count = j - i
            if count >= 3:
                combo_idx = 1
                for k in range(i, j):
                    sub_t, sub_txt = expanded[k][0], expanded[k][1]
                    clean_sub = cls._clean_phrase(sub_txt)
                    result.append((sub_t, f"{clean_sub} х{combo_idx}"))
                    combo_idx += 1
                i = j
            else:
                k = i
                while k < j:
                    orig_txt = expanded[k][4]
                    orig_t = expanded[k][0]
                    if expanded[k][3]:
                        m = k
                        while m < j and expanded[m][3] and expanded[m][4] == orig_txt:
                            m += 1
                        result.append((orig_t, orig_txt))
                        k = m
                    else:
                        result.append((orig_t, orig_txt))
                        k += 1
                i = j

        return result

    def compact_lyric_lines(self) -> list[tuple[float, str]]:
        raw = self._lyrics.for_duration(self._media.duration)
        if not raw:
            return []
        cached = self._compact_lines_cache
        if cached is not None and cached[0] is raw:
            return cached[1]
        processed = self._process_compact_lines(raw, self._media.duration)
        self._compact_lines_cache = (raw, processed)
        return processed

    def compact_lyric_target(self) -> Optional[tuple[str, float, float, bool]]:
        raw_lines = self._lyrics.for_duration(self._media.duration)
        if not raw_lines:
            return None

        lines = self.compact_lyric_lines()
        at = self._media.position + LYRIC_LEAD

        if len(lines) != len(raw_lines):
            idx = -1
            for i, (line_t, line_text) in enumerate(lines):
                if line_t <= at:
                    idx = i
                else:
                    break
            current = lines[idx] if idx >= 0 else None
        else:
            idx, current = self._lyrics.get_current_line(self._media.position, self._media.duration, lead=LYRIC_LEAD)
            if idx >= 0 and idx < len(lines):
                current = lines[idx]

        def end_of(index: int) -> float:
            if index + 1 < len(lines):
                return lines[index + 1][0]
            return max(self._media.duration, lines[index][0] + 4.0)

        if current is not None and current[1].strip():
            return (current[1], current[0], end_of(idx), at >= current[0])

        start = idx + 1 if idx >= 0 else 0
        for j in range(start, len(lines)):
            line_t, line_text = lines[j]
            if line_text.strip() and line_t - at <= LYRIC_LOOKAHEAD:
                return (line_text, line_t, end_of(j), False)

        return None

    def lyrics_have_words(self) -> bool:
        mode = Settings.lyric_anim
        if mode == "vertical":
            return False
        if mode == "words":
            return True
        return self._lyrics.is_synced

    def compact_track_title(self) -> str:
        if not self._media.has_track:
            return ""
        return format_display_title(
            self._media.title,
            self._media.artist,
            capitalize_first=Settings.capitalize_title,
        )

    def update_lyric(self, snap: bool = False) -> None:
        if self._current_view == View.MEDIA_BIG:
            self.update_player_lyric(snap)
        if self._current_view != View.MEDIA:
            return

        target = self.compact_lyric_target()
        text = target[0] if target else self.compact_track_title()
        target_t = target[1] if target else None
        line_key = (target_t, text)

        if line_key != self._last_lyric_key or snap:
            if not snap and self._last_lyric_text:
                self._lyric_prev_text = self._last_lyric_text
                self._lyric_prev_target = self._lyric_target
                self._lyric_prev_alpha.value = min(0.6, max(self._lyric_prev_alpha.value, 0.25))
                self._lyric_prev_alpha.target = 0.0
            else:
                self._lyric_prev_text = ""
                self._lyric_prev_target = None
                self._lyric_prev_alpha.value = 0.0
                self._lyric_prev_alpha.target = 0.0

            self._lyric_target = target
            self._lyric_enter.value = 1.0 if snap else 0.0
            self._lyric_enter.target = 1.0
            self._last_lyric_key = line_key
            self._last_lyric_text = text
            if text:
                select_font(_MEASURE_CR, font_size=compact_lyric_font(), bold=True)
                tw = _MEASURE_CR.text_extents(text).x_advance
                self._lyric_span = 0.0
                self._lyric_line_start = target[1] if target else 0.0
                if target and target[3]:
                    self._lyric_span = max(0.3, target[2] - target[1])
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
        elif target != self._lyric_target:
            self._lyric_target = target
            at = self._media.position + LYRIC_LEAD
            if target and (target[3] or at >= target[1]):
                self._lyric_span = max(0.3, target[2] - target[1])
                self._lyric_line_start = target[1]
            self.area.queue_draw()

    def lyric_phase(
        self,
        target: Optional[tuple[str, float, float, bool]],
    ) -> tuple[Optional[float], float]:
        if target is None:
            return (None, 1.0)
        _text, start_t, end_t, started = target
        at = self._media.position + LYRIC_LEAD
        if started or at >= start_t:
            span = max(0.5, end_t - start_t)
            return (max(0.0, min(1.0, (at - start_t) / span)), 1.0)
        until = start_t - at
        if until > LYRIC_ARM_BEFORE:
            return (None, 1.0)
        return (None, LYRIC_DIM_ARM)

    def _advance_lyric_scroll(self, dt: float) -> bool:
        span = self._lyric_span if self._lyric_span > 0.0 else 3.0
        elapsed = max(0.0, min(span, self._media.position - self._lyric_line_start))
        hold_start = min(0.5, span * 0.15)
        hold_end = min(0.6, span * 0.15)
        run_span = max(0.5, span - hold_start - hold_end)

        if elapsed <= hold_start:
            target = 0.0
        elif elapsed >= span - hold_end:
            target = -self._lyric_overflow
        else:
            k = (elapsed - hold_start) / run_span
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

        wait = room and len(lines) == 0
        if wait:
            palette = [Settings.accent, *self._media.palette] if Settings.accent else self._media.palette
            self._shimmer.tint(palette)
        self._shimmer.run(wait)

    def start_timer(self, seconds: float) -> None:
        self._timer.start(seconds)
        self.open_panel(Panel.NONE)
        self.sync_timer()
        self.update_view()
        self.set_targets()

    def stop_timer(self) -> None:
        self._timer.stop()
        self.set_urgent(False)
        self._split.target = 0.0
        self.update_view()
        self.set_targets()

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
        self._alarm_start_time = time.monotonic()
        self._alarm.ring()
        self.notify(Glyph.Bell, COLOR_ORANGE, "Таймер", f"Время вышло · {total_span}", seconds=3.5, force=True)
        self.set_targets()

    def quiet_alarm(self) -> None:
        if not self._ringing:
            return
        self._ringing = False
        self._shake_x = 0.0
        self._bell_angle = 0.0
        self._alarm.stop()

    def set_minutes(self, minutes: int) -> None:
        clamped = max(1, min(MAX_MINUTES, minutes))
        self._digits_setup.down = clamped < self._minutes
        self._minutes = clamped
        self._digits_setup.set_text(f"{self._minutes}:00")
        self.area.queue_draw()

    def get_modifier_step(self, controller: Optional[Any] = None) -> int:
        state = 0
        if controller and hasattr(controller, "get_current_event_state"):
            try:
                state = int(controller.get_current_event_state())
            except Exception:
                state = 0
        if state & Gdk.ModifierType.CONTROL_MASK:
            return 50
        if state & Gdk.ModifierType.SHIFT_MASK:
            return 10
        return 1

    def on_key_pressed(
        self, controller: Gtk.EventControllerKey, keyval: int, keycode: int, state: Gdk.ModifierType
    ) -> bool:
        if self._current_view != View.LOOK:
            return False
        step = 50 if (state & Gdk.ModifierType.CONTROL_MASK) else (10 if (state & Gdk.ModifierType.SHIFT_MASK) else 1)
        if keyval in (Gdk.KEY_Left, 0xFF51):
            self.set_pos_x(Settings.pos_x - step)
            return True
        elif keyval in (Gdk.KEY_Right, 0xFF53):
            self.set_pos_x(Settings.pos_x + step)
            return True
        elif keyval in (Gdk.KEY_Up, 0xFF52):
            self.set_pos_y(Settings.pos_y - step)
            return True
        elif keyval in (Gdk.KEY_Down, 0xFF54):
            self.set_pos_y(Settings.pos_y + step)
            return True
        return False

    def set_pos_x(self, px: int) -> None:
        Settings.pos_x = px
        self._pos_x.target = float(px)
        self.set_targets()

    def set_pos_y(self, py: int) -> None:
        Settings.pos_y = py
        self._gap.target = float(py)
        self.set_targets()

    def set_scale(self, percent: int) -> None:
        Settings.scale = percent
        self._size.target = percent / 100.0
        self.set_targets()

    def set_gap(self, px: int) -> None:
        self.set_pos_y(px)

    def set_radius(self, percent: int) -> None:
        Settings.radius = percent
        self.set_targets()

    def set_height(self, px: int) -> None:
        Settings.height = px
        self.set_targets()

    def set_text_scale(self, percent: int) -> None:
        Settings.text_scale = percent
        self.update_lyric(snap=True)
        self.area.queue_draw()

    def set_material(self, mat: str) -> None:
        Settings.material = mat
        self._goo.set_mode(mat, 0.35)
        self.area.queue_draw()

    def set_glass(self, percent: int) -> None:
        Settings.glass = percent
        self._goo.set_glass(percent / 100.0)
        self.area.queue_draw()

    def set_accent(self, col: Optional[Tuple[float, float, float]]) -> None:
        Settings.accent = col
        self.sync_accent()
        self.sync_rim()
        self.area.queue_draw()

    def destroy(self) -> None:
        for s in ("_network", "_audio", "_media", "_battery", "_spectrum", "_alarm"):
            srv = getattr(self, s, None)
            if srv and hasattr(srv, "stop"):
                try:
                    srv.stop()
                except Exception:
                    pass
        super().destroy()

    def exit_island(self) -> None:
        self._alarm.stop()
        self.get_application().quit()

    def on_draw(self, area: Gtk.DrawingArea, cr: cairo.Context, width: int, height: int, user_data=None) -> None:
        cr.save()
        cr.set_operator(cairo.OPERATOR_CLEAR)
        cr.paint()
        cr.restore()
        cr.set_operator(cairo.OPERATOR_OVER)

        if width > 50 and height > 50:
            if self.win_width != width or self.win_height != height:
                self.win_width = width
                self.win_height = height
                self.update_input_region()

        dt = min(time.monotonic() - self._last_tick_time, 0.05)
        size = max(0.01, self._size.value)
        scale = max(0.01, self._scale.value)
        w = max(24.0, self._w.value)
        h = max(24.0, self._h.value + Settings.height)
        r = min(w / 2.0, min(h / 2.0, max(0.0, self._r.value * Settings.radius / 100.0)))

        cx = width / 2.0 + self._pos_x.value + self._lean.value + self._shake_x
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
            timer_w = self._carry_timer.value * CARRY_TIMER
            shelf_w = self._carry_shelf.value * self._shelf_wide.value
            both = (self._carry_timer.value > 0.05 and self._carry_shelf.value > 0.05)
            base_bw = max(CARRY_SHELF, timer_w + shelf_w + (6.0 if both else 0.0))
            past = ((BUBBLE_GAP + base_bw) * split - base_bw) / scale
            bx = pill_right + past
            bw = base_bw * bubble_scale / scale
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
        self._goo.set_mode(Settings.material, 0.35)
        self._goo.set_glass(Settings.glass / 100.0)
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
                timer_on = self._carry_timer.value > 0.05
                shelf_on = self._carry_shelf.value > 0.05
                if timer_on and shelf_on:
                    t_w = CARRY_TIMER
                    Ring.render(
                        cr,
                        cx=bx + 16.0,
                        cy=by + bh / 2.0,
                        radius=8.0,
                        progress=self._timer.share,
                        color=self._timer_tint,
                        thickness=2.2,
                    )
                    self._digits_bubble.render(
                        cr,
                        x=bx + t_w - 6.0,
                        y=by + bh / 2.0,
                        font_size=12.5,
                        color=self._timer_tint,
                        align="right",
                        valign="center",
                    )
                    sx = bx + t_w + 6.0
                    render_icon(cr, Glyph.Tray, sx + 6.0, by + bh / 2.0 - 7.0, 14.0, COLOR_DIM[:3], alpha=bubble_alpha)
                    self._digits_shelf.render(
                        cr,
                        x=bx + bw - 10.0,
                        y=by + bh / 2.0,
                        font_size=12.5,
                        color=COLOR_WHITE,
                        align="right",
                        valign="center",
                    )
                elif timer_on:
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
                elif shelf_on:
                    render_icon(cr, Glyph.Tray, bx + 12.0, by + bh / 2.0 - 7.0, 14.0, COLOR_DIM[:3], alpha=bubble_alpha)
                    self._digits_shelf.render(
                        cr,
                        x=bx + bw - 12.0,
                        y=by + bh / 2.0,
                        font_size=12.5,
                        color=COLOR_WHITE,
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
        elif view == View.FOCUS:
            self.render_focus(cr, px, py, pw, ph, alpha)
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
        elif view == View.SHELF:
            self.render_shelf(cr, px, py, pw, ph, alpha)
        elif view == View.UPDATE:
            self.render_update(cr, px, py, pw, ph, alpha)

    def render_idle(self, cr: cairo.Context, px: float, py: float, pw: float, ph: float, alpha: float) -> None:
        self._digits_clock.render(
            cr,
            px + pw / 2.0,
            py + ph / 2.0,
            font_size=13.5,
            color=(1.0, 1.0, 1.0, alpha),
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
            target = self._lyric_target
            lyric_text = target[0] if target else self.compact_track_title()
            has_lyric = target is not None and bool(lyric_text.strip())

            if has_lyric and Settings.lyrics:
                has_words = self.lyrics_have_words()
                prev_a = self._lyric_prev_alpha.value
                if prev_a > 0.01 and self._lyric_prev_text:
                    p_prev, d_prev = self.lyric_phase(self._lyric_prev_target)
                    LyricLine.render_compact(
                        cr,
                        self._lyric_prev_text,
                        mid_x,
                        py + LYRIC_EXIT_SHIFT * (1.0 - prev_a),
                        mid_w,
                        COLOR_WHITE,
                        font_size=compact_lyric_font(),
                        offset_x=self._lyric_scroll if self._lyric_prev_target == target else 0.0,
                        h=ph,
                        alpha=prev_a * alpha,
                        dim=d_prev,
                        progress=p_prev if has_words else None,
                    )

                enter = self._lyric_enter.value
                prog, dim = self.lyric_phase(target)
                LyricLine.render_compact(
                    cr,
                    lyric_text,
                    mid_x,
                    py + LYRIC_ENTER_SHIFT * (1.0 - enter),
                    mid_w,
                    COLOR_WHITE,
                    font_size=compact_lyric_font(),
                    offset_x=self._lyric_scroll,
                    h=ph,
                    alpha=enter * alpha,
                    dim=dim,
                    progress=prog if has_words else None,
                )
            else:
                draw_text(
                    cr,
                    lyric_text,
                    mid_x + mid_w / 2.0,
                    py + ph / 2.0,
                    font_size=compact_lyric_font(),
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
        col = self._battery_color
        status_txt = self._battery_status

        if self._last_plugged:
            bolt_scale = 0.7 + 0.3 * max(0.0, min(1.0, self._bolt_spring.value))
            icon_cx = px + 22.0
            icon_cy = py + ph / 2.0
            cr.save()
            cr.translate(icon_cx, icon_cy)
            cr.scale(bolt_scale, bolt_scale)
            cr.translate(-icon_cx, -icon_cy)
            render_icon(cr, Glyph.Bolt, icon_cx - 9.0, icon_cy - 9.0, 18.0, col, alpha=alpha)
            cr.restore()
            text_x = px + 38.0
        else:
            icon_cx = px + 22.0
            icon_cy = py + ph / 2.0
            render_icon(cr, Glyph.Battery, icon_cx - 9.0, icon_cy - 9.0, 18.0, col, alpha=alpha)
            text_x = px + 38.0

        draw_text(
            cr,
            status_txt,
            text_x,
            py + ph / 2.0,
            font_size=13.0,
            bold=True,
            color=COLOR_WHITE,
            alpha=alpha,
            align="left",
            valign="center",
        )
        bat_str = f"{self._battery_pct}%"
        self._digits_charge.set_text(bat_str)
        self._digits_charge.render(
            cr,
            px + pw - 46.0,
            py + ph / 2.0,
            font_size=13.0,
            color=(col[0], col[1], col[2], alpha),
            align="right",
            valign="center",
        )
        bx = px + pw - 38.0
        by = py + (ph - 13.0) / 2.0
        draw_rounded_rect(cr, bx, by, 24.0, 13.0, 4.0)
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.4 * alpha)
        cr.set_line_width(1.0)
        cr.stroke()

        fill_w = 20.0 * (self._battery_pct / 100.0)
        if fill_w > 0.5:
            draw_rounded_rect(cr, bx + 2.0, by + 2.0, fill_w, 9.0, 2.5)
            cr.set_source_rgba(col[0], col[1], col[2], alpha)
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

        icon_cx = badge_x + badge_size / 2.0
        icon_cy = badge_y + badge_size / 2.0
        icon_size = 22.0
        cr.save()
        if self._ringing and self._notice_icon == Glyph.Bell:
            cr.translate(icon_cx, icon_cy - 8.0)
            cr.rotate(math.radians(self._bell_angle))
            cr.translate(-icon_cx, -(icon_cy - 8.0))
        render_icon(
            cr,
            self._notice_icon,
            icon_cx - icon_size / 2.0,
            icon_cy - icon_size / 2.0,
            icon_size,
            self._notice_tint,
            alpha=alpha,
        )
        cr.restore()

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

    def player_lyric_rows(self) -> list[tuple[float, str, float, float, float]]:
        lines = self._lyrics.for_duration(self._media.duration)
        cached = self._player_rows_cache
        if cached is not None and cached[0] is lines:
            return cached[1]

        lyric_w = PLAYER_LYRIC_W
        rows: list[tuple[float, str, float, float, float]] = []
        top = 0.0
        for line_t, line_text in lines:
            if line_text.strip():
                h_act = measure_text(_MEASURE_CR, line_text, lyric_w, player_lyric_font(), True)[1]
                h_dim = measure_text(_MEASURE_CR, line_text, lyric_w, player_lyric_font(), False)[1]
            else:
                h_act = h_dim = WAIT_ROW_H
            rows.append((line_t, line_text, h_act, h_dim, top))
            top += h_act + PLAYER_LYRIC_GAP

        self._player_rows_cache = (lines, rows)
        return rows

    def render_player_lyrics(
        self,
        cr: cairo.Context,
        px: float,
        py: float,
        pw: float,
        ph: float,
        alpha: float,
    ) -> None:
        if alpha <= 0.001:
            return

        lyric_y = py + 92.0
        room = self._player_lyric_h
        lyric_w = PLAYER_LYRIC_W
        lyric_x = px + (pw - lyric_w) / 2.0
        rows = self.player_lyric_rows()

        if not rows:
            self._shimmer.render(cr, lyric_x, lyric_y, lyric_w, room, alpha)
            return

        at = self._media.position + LYRIC_LEAD
        active = -1
        for i, (line_t, _t, _ha, _hd, _top) in enumerate(rows):
            if line_t <= at:
                active = i
            else:
                break

        window_h = 0.0
        for i in range(max(0, active - 1), min(len(rows), active + 2)):
            _lt, txt, h_act, h_dim, _tp = rows[i]
            window_h += h_act if txt.strip() else h_dim
        window_h += PLAYER_LYRIC_GAP * max(0, min(len(rows), active + 2) - max(0, active - 1) - 1)
        needed = max(PLAYER_LYRIC_ROOM, window_h + 2 * PLAYER_LYRIC_PAD)
        if needed - self._player_lyric_h > 0.5:
            self._player_lyric_h = needed
            self._h.tune(280, 30)
            self.set_targets()
            room = self._player_lyric_h

        if active < 0:
            first_t = rows[0][0]
            target_y = room / 2.0 - (rows[0][4] + rows[0][2] / 2.0)
            self._player_col.target = target_y
            until_first = max(0.0, first_t - at)
            wait_fade = 1.0 if until_first > 1.8 else max(0.0, until_first / 1.8)
            if wait_fade > 0.01:
                render_wait(
                    cr,
                    px + pw / 2.0,
                    lyric_y + room / 2.0,
                    progress=self._wait_progress(first_t),
                    alpha=alpha * wait_fade,
                    now=time.monotonic(),
                    tint=COLOR_WHITE[:3],
                )
            if wait_fade >= 0.99:
                return

        if active >= 0:
            _lt, _txt, h_act, _hd, top = rows[active]
            target_y = room / 2.0 - (top + h_act / 2.0)
            if abs(target_y - self._player_col.target) > 0.5:
                self._player_col.target = target_y
                self._player_col.tune(120, 24)

            if active != self._player_last_active:
                was = self._player_last_active
                self._player_prev_active = was
                self._player_last_active = active
                self._player_active_spring.value = 0.0
                self._player_active_spring.target = 1.0

                up = target_y <= self._player_col.value
                lead = active + (-1 if up else 1)
                now_s = time.monotonic()
                for idx in range(len(rows)):
                    if abs(idx - active) > 4 and abs(idx - max(0, was)) > 4:
                        if idx in self._player_row_waves:
                            self._player_row_waves[idx].value = target_y
                            self._player_row_waves[idx].target = target_y
                        continue
                    behind = max(0, min(5, (idx - lead) if up else (lead - idx)))
                    self._player_row_dues[idx] = now_s + behind * 0.04
                    if idx not in self._player_row_waves:
                        self._player_row_waves[idx] = Spring(self._player_col.value, 120, 24)

        col_y = self._player_col.value
        margin = max(WAIT_ROW_H, 32.0)
        top_limit = lyric_y - margin
        bottom_limit = lyric_y + room + margin

        effective_active = max(0, active)
        start_t = rows[effective_active][0]
        end_t = self._media.duration
        if rows[effective_active][1].strip() and effective_active + 1 < len(rows):
            end_t = rows[effective_active + 1][0]
        else:
            for j in range(effective_active + 1, len(rows)):
                if rows[j][1].strip():
                    end_t = rows[j][0]
                    break
        if Settings.lyric_effects:
            prog = max(0.0, min(1.0, (at - start_t) / max(0.25, end_t - start_t)))
        else:
            prog = 1.0

        cr.save()
        cr.rectangle(lyric_x, lyric_y, lyric_w, room)
        cr.clip()

        fade_h = min(18.0, room * 0.22)
        has_fade = fade_h > 1.0 and alpha > 0.01
        if has_fade:
            cr.push_group()

        t_anim = max(0.0, min(1.0, self._player_active_spring.value))
        intro_text_mult = (1.0 - wait_fade) if active < 0 else 1.0

        try:
            for i, (line_t, line_text, h_a, h_d, row_top) in enumerate(rows):
                wave_y = self._player_row_waves[i].value if i in self._player_row_waves else col_y
                y = lyric_y + wave_y + row_top
                if y + max(h_a, h_d) < top_limit or y > bottom_limit:
                    continue

                if not line_text.strip():
                    if i == active:
                        time_left = max(0.0, end_t - at)
                        gap_fade = 1.0 if time_left > 1.2 else max(0.0, time_left / 1.2)
                        if gap_fade > 0.01:
                            render_wait(
                                cr,
                                px + pw / 2.0,
                                y + WAIT_ROW_H / 2.0,
                                progress=self._wait_progress(line_t, end_t),
                                alpha=alpha * gap_fade,
                                now=time.monotonic(),
                                tint=COLOR_WHITE[:3],
                            )
                    continue

                if i == active:
                    line_a = alpha * (0.40 + 0.60 * t_anim) * intro_text_mult
                    LyricLine.render_karaoke(
                        cr, line_text, prog, lyric_x, y, lyric_w, h_a,
                        font_size=player_lyric_font(), is_active=True, alpha=line_a,
                        vertical_fill=not self.lyrics_have_words(),
                    )
                elif i == self._player_prev_active and active >= 0:
                    line_a = alpha * max(0.35, 1.0 - 0.60 * t_anim)
                    LyricLine.render_karaoke(
                        cr, line_text, 0.0, lyric_x, y, lyric_w, h_a,
                        font_size=player_lyric_font(), is_active=False, alpha=line_a,
                    )
                else:
                    near = 1.0 - min(1.0, abs(i - effective_active) / 2.5)
                    line_a = alpha * (0.35 + 0.3 * near) * intro_text_mult
                    LyricLine.render_karaoke(
                        cr, line_text, 0.0, lyric_x, y, lyric_w, h_a,
                        font_size=player_lyric_font(), is_active=False, alpha=line_a,
                    )

            if has_fade:
                lyrics_group = cr.pop_group()
                stop_top = fade_h / room
                stop_bot = 1.0 - stop_top
                grad = cairo.LinearGradient(0.0, lyric_y, 0.0, lyric_y + room)
                grad.add_color_stop_rgba(0.0, 1.0, 1.0, 1.0, 0.0)
                grad.add_color_stop_rgba(stop_top, 1.0, 1.0, 1.0, 1.0)
                grad.add_color_stop_rgba(stop_bot, 1.0, 1.0, 1.0, 1.0)
                grad.add_color_stop_rgba(1.0, 1.0, 1.0, 1.0, 0.0)
                cr.set_source(lyrics_group)
                cr.mask(grad)
        finally:
            cr.restore()

    def _wait_progress(self, next_t: Optional[float], end_t: Optional[float] = None) -> float:
        if next_t is None:
            return 0.0
        at = self._media.position
        if end_t is not None and end_t > next_t:
            return max(0.0, min(1.0, (at - next_t) / (end_t - next_t)))
        return max(0.0, min(1.0, 1.0 - (next_t - at) / 6.0))

    def render_media_big(self, cr: cairo.Context, px: float, py: float, pw: float, ph: float, alpha: float) -> None:
        cover_scale = max(0.5, min(1.0, self._cover_scale.value))
        art_size = 64.0 * cover_scale
        art_back = (64.0 - art_size) / 2.0
        art_x = px + 20.0 + art_back
        art_y = py + 20.0 + art_back
        self._btn_art_rect = (px + 20.0, py + 20.0, 64.0, 64.0)

        if self._cover_big.surface:
            self._cover_big.render(cr, art_x, art_y, art_size, radius=16.0 * cover_scale)
        else:
            draw_rounded_rect(cr, art_x, art_y, art_size, art_size, 16.0 * cover_scale)
            cr.set_source_rgba(0.2, 0.2, 0.2, alpha)
            cr.fill()
            render_icon(cr, Glyph.Note, art_x + 17.0 * cover_scale, art_y + 17.0 * cover_scale, 30.0 * cover_scale, COLOR_DIM[:3], alpha=alpha)

        eq_w = 38.0
        eq_h = 26.0
        eq_x = px + pw - 22.0 - eq_w
        eq_y = py + 38.0
        self._eq_big.render(cr, eq_x, eq_y, eq_w, eq_h, color=self._accent_color, alpha=alpha, dots=Settings.equalizer_dots)

        mid_x = px + 20.0 + 64.0 + 14.0
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
            self.render_player_lyrics(cr, px, py, pw, ph, alpha)

        dur = self._media.duration
        known_dur = dur >= 1.0
        pos = dur * (self._seek_x.value / SEEK_TRACK) if known_dur else 0.0
        pos_str = format_time(pos) if known_dur else "0:00"
        self._digits_pos.set_text(pos_str)
        seek_y = py + ph - 70.0
        self._digits_pos.render(cr, px + 20.0, seek_y + 3.0, font_size=11.0, color=(COLOR_DIM[0], COLOR_DIM[1], COLOR_DIM[2], alpha), align="left", valign="center")
        seek_w = SEEK_TRACK
        seek_x = px + 60.0
        seek_h = max(2.0, self._seek_h.value)
        self._seek_rect = (seek_x, seek_y - seek_h / 2.0, seek_w, seek_h)

        if Settings.line_bar and known_dur and self._lyrics_lines:
            starts = [t / dur for t, _ in self._lyrics_lines if 0.0 <= t <= dur]
            self._line_bar.set_starts(starts)
            prog = self._seek_x.value / seek_w
            accent = self._accent_color or COLOR_WHITE[:3]
            self._line_bar.render(cr, seek_x, seek_y - seek_h / 2.0, seek_w, seek_h, prog, accent, alpha=alpha)
        else:
            draw_rounded_rect(cr, seek_x, seek_y - seek_h / 2.0, seek_w, seek_h, seek_h / 2.0)
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.2 * alpha)
            cr.fill()

            fill_seek = max(0.0, min(seek_w, self._seek_x.value))
            if fill_seek > 1.0:
                draw_rounded_rect(cr, seek_x, seek_y - seek_h / 2.0, fill_seek, seek_h, seek_h / 2.0)
                cr.set_source_rgba(1.0, 1.0, 1.0, alpha)
                cr.fill()

        rem = max(0.0, dur - pos) if known_dur else 0.0
        rem_str = f"-{format_time(rem)}" if known_dur else "-0:00"
        self._digits_rem.set_text(rem_str)
        self._digits_rem.render(cr, px + pw - 20.0, seek_y + 3.0, font_size=11.0, color=(COLOR_DIM[0], COLOR_DIM[1], COLOR_DIM[2], alpha), align="right", valign="center")

        btn_y = py + ph - 42.0

        self._btn_prev_rect = (px + pw / 2.0 - 74.0, btn_y - 20.0, 40.0, 40.0)
        self._skip_prev.render(cr, px + pw / 2.0 - 54.0, btn_y, color=COLOR_WHITE, alpha=alpha)

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
        self._skip_next.render(cr, px + pw / 2.0 + 54.0, btn_y, color=COLOR_WHITE, alpha=alpha)

        if self._headset_pct >= 0:
            render_icon(cr, Glyph.Headphones, px + pw - 60.0, btn_y - 7.0, 14.0, COLOR_DIM[:3], alpha=alpha)
            self._digits_player_headset.render(cr, px + pw - 42.0, btn_y, font_size=11.0, color=(COLOR_DIM[0], COLOR_DIM[1], COLOR_DIM[2], alpha), align="left", valign="center")

        if self._player_vol_opacity > 0.01:
            eff_a = self._player_vol_opacity * alpha
            render_icon(cr, Glyph.Note if self._player_vol_is_app else Glyph.Loud, px + 20.0, btn_y - 7.0, 14.0, self._accent_color if self._player_vol_is_app else COLOR_DIM[:3], alpha=eff_a)
            self._digits_player_vol.render(cr, px + 38.0, btn_y, font_size=11.0, color=self._accent_color if self._player_vol_is_app else (COLOR_DIM[0], COLOR_DIM[1], COLOR_DIM[2], eff_a), align="left", valign="center")

    def render_idle_big(self, cr: cairo.Context, px: float, py: float, pw: float, ph: float, alpha: float) -> None:
        self._digits_big_clock.render(cr, px + 26.0, py + 48.0, font_size=46.0, color=(1.0, 1.0, 1.0, alpha), align="left", valign="center")
        draw_text(cr, self._clock_date_str, px + 28.0, py + 86.0, font_size=13.0, bold=False, color=COLOR_DIM[:3], alpha=alpha, align="left", valign="center")
        if self._quiet:
            date_w = measure_text(cr, self._clock_date_str, 13.0, bold=False)
            render_icon(cr, Glyph.Moon, px + 28.0 + date_w + 6.0, py + 79.0, 13.0, COLOR_INDIGO, alpha=alpha)

        rx = px + pw - 24.0
        render_icon(cr, Glyph.Loud, rx - 54.0, py + 32.0, 16.0, COLOR_DIM[:3], alpha=alpha)
        vol_pct = int(round(max(0.0, self._last_volume) * 100))
        self._digits_info_vol.set_text(f"{vol_pct}%")
        self._digits_info_vol.render(cr, rx, py + 40.0, font_size=13.0, color=(1.0, 1.0, 1.0, alpha), align="right", valign="center")

        if self._headset_pct >= 0:
            render_icon(cr, Glyph.Headphones, rx - 54.0, py + 58.0, 16.0, COLOR_DIM[:3], alpha=alpha)
            self._digits_info_headset.render(cr, rx, py + 66.0, font_size=13.0, color=(1.0, 1.0, 1.0, alpha), align="right", valign="center")

        if self._battery_known:
            render_icon(cr, Glyph.Battery, rx - 54.0, py + 84.0, 16.0, COLOR_DIM[:3], alpha=alpha)
            self._digits_info_battery.render(cr, rx, py + 92.0, font_size=13.0, color=(COLOR_GREEN[0], COLOR_GREEN[1], COLOR_GREEN[2], alpha) if self._last_plugged else (1.0, 1.0, 1.0, alpha), align="right", valign="center")

    def render_focus(self, cr: cairo.Context, px: float, py: float, pw: float, ph: float, alpha: float) -> None:
        if alpha <= 0.001:
            return
        quiet = bool(self._quiet)
        col = COLOR_INDIGO if quiet else COLOR_DIM[:3]

        cr.save()
        icon_cx = px + 12.0 + 9.0
        icon_cy = py + ph / 2.0
        cr.translate(icon_cx, icon_cy)
        cr.rotate(math.radians(self._focus_swing.value))
        s = max(0.1, self._focus_scale.value)
        cr.scale(s, s)
        render_icon(cr, Glyph.Moon, -9.0, -9.0, 18.0, col, alpha=alpha)
        cr.restore()

        draw_text(cr, "Не беспокоить", px + 38.0, py + ph / 2.0, font_size=13.0, bold=False, color=COLOR_WHITE, alpha=alpha, align="left", valign="center")
        draw_text(cr, "Вкл." if quiet else "Выкл.", px + pw - 14.0, py + ph / 2.0, font_size=13.0, bold=True, color=col, alpha=alpha, align="right", valign="center")

    def render_shelf(self, cr: cairo.Context, px: float, py: float, pw: float, ph: float, alpha: float) -> None:
        if alpha <= 0.001:
            return

        render_icon(cr, Glyph.Back, px + 20.0, py + 18.0, 10.0, COLOR_DIM[:3], alpha=0.6 * alpha)
        draw_text(cr, "ПОЛКА", px + 36.0, py + 23.0, font_size=10.5, bold=True, color=COLOR_DIM[:3], alpha=0.6 * alpha, align="left", valign="center")

        text_w, _ = measure_text(cr, "Очистить", pw, 10.5 * Settings.text_factor())
        btn_clear_w = max(66.0, text_w + 16.0)
        btn_clear_x = px + pw - 18.0 - btn_clear_w
        btn_clear_y = py + 12.0
        btn_add_x = btn_clear_x - 8.0 - 24.0
        btn_add_y = py + 12.0

        self._shelf_btn_add_rect = (btn_add_x, btn_add_y, 24.0, 24.0)
        cr.save()
        draw_rounded_rect(cr, btn_add_x, btn_add_y, 24.0, 24.0, 12.0)
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.12 * alpha)
        cr.fill()
        render_icon(cr, Glyph.Plus, btn_add_x + 6.0, btn_add_y + 6.0, 12.0, COLOR_WHITE[:3], alpha=alpha)
        cr.restore()

        self._shelf_btn_clear_rect = (btn_clear_x, btn_clear_y, btn_clear_w, 24.0)
        cr.save()
        draw_rounded_rect(cr, btn_clear_x, btn_clear_y, btn_clear_w, 24.0, 12.0)
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.12 * alpha)
        cr.fill()
        draw_text(cr, "Очистить", btn_clear_x + btn_clear_w / 2.0, btn_clear_y + 12.0, font_size=10.5, bold=False, color=COLOR_WHITE[:3], alpha=alpha, align="center", valign="center")
        cr.restore()

        strip_x = px + 18.0
        strip_y = py + 42.0
        strip_w = pw - 36.0
        strip_h = 80.0

        if not self._shelf.items:
            draw_text(cr, "Перетащите сюда файлы", px + pw / 2.0, strip_y + 24.0, font_size=12.5, bold=False, color=COLOR_WHITE[:3], alpha=0.6 * alpha, align="center", valign="center")
            draw_text(cr, "или нажмите, чтобы выбрать", px + pw / 2.0, strip_y + 44.0, font_size=11.0, bold=False, color=COLOR_WHITE[:3], alpha=0.35 * alpha, align="center", valign="center")
            return

        cr.save()
        clip_rounded_rect(cr, strip_x, strip_y, strip_w, strip_h, 14.0)

        offset_x = self._shelf_scroll.value
        for idx, item in enumerate(self._shelf.items):
            tx = strip_x - offset_x + idx * 68.0
            ty = strip_y + 4.0
            if tx + 64.0 < strip_x or tx > strip_x + strip_w:
                continue

            cr.save()
            cx = tx + 28.0
            cy = ty + 28.0
            cr.translate(cx, cy)
            swell = item.swell.value
            cr.scale(swell, swell)
            cr.translate(-28.0, -28.0)

            draw_rounded_rect(cr, 0.0, 0.0, 56.0, 56.0, 13.0)
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.12 * alpha)
            cr.fill()

            if item.surface is not None:
                cr.save()
                draw_rounded_rect(cr, 0.0, 0.0, 56.0, 56.0, 13.0)
                cr.clip()
                sw = item.surface.get_width()
                sh = item.surface.get_height()
                if sw > 0 and sh > 0:
                    scale_img = max(56.0 / sw, 56.0 / sh)
                    cr.scale(scale_img, scale_img)
                    cr.set_source_surface(item.surface, (56.0 / scale_img - sw) / 2.0, (56.0 / scale_img - sh) / 2.0)
                    cr.paint_with_alpha(alpha)
                cr.restore()
            else:
                render_icon(cr, Glyph.Tray, 14.0, 14.0, 28.0, COLOR_DIM[:3], alpha=alpha)

            cr.restore()

            draw_text(cr, item.name, tx + 28.0, ty + 64.0, font_size=10.0, bold=False, color=COLOR_WHITE[:3], alpha=0.7 * alpha, align="center", valign="center", max_w=60.0)

            cross_a = item.cross.value * alpha
            if cross_a > 0.01:
                cross_x = tx + 44.0
                cross_y = ty - 4.0
                cr.save()
                cr.new_sub_path()
                cr.arc(cross_x + 9.0, cross_y + 9.0, 9.0, 0.0, 2.0 * math.pi)
                cr.set_source_rgba(0.28, 0.28, 0.29, cross_a)
                cr.fill_preserve()
                cr.set_source_rgba(0.0, 0.0, 0.0, cross_a)
                cr.set_line_width(2.0)
                cr.stroke()

                render_icon(cr, Glyph.Cross, cross_x + 4.5, cross_y + 4.5, 9.0, COLOR_WHITE[:3], alpha=cross_a)
                cr.restore()

        cr.restore()

    def render_timer_big(self, cr: cairo.Context, px: float, py: float, pw: float, ph: float, alpha: float) -> None:
        p_cx = px + 45.0
        p_cy = py + ph / 2.0
        cr.new_sub_path()
        cr.arc(p_cx, p_cy, 25.0, 0, 2 * math.pi)
        cr.set_source_rgba(COLOR_ORANGE[0], COLOR_ORANGE[1], COLOR_ORANGE[2], 0.25 * alpha)
        cr.fill()

        if self._timer.total > 0:
            frac = max(0.0, min(1.0, self._timer.remaining / float(self._timer.total)))
            cr.save()
            cr.set_line_width(2.5)
            cr.set_line_cap(cairo.LINE_CAP_ROUND)
            cr.arc(p_cx, p_cy, 27.5, 0, 2 * math.pi)
            cr.set_source_rgba(COLOR_ORANGE[0], COLOR_ORANGE[1], COLOR_ORANGE[2], 0.15 * alpha)
            cr.stroke()
            if frac > 0.001:
                cr.arc(p_cx, p_cy, 27.5, -math.pi / 2.0, -math.pi / 2.0 + 2 * math.pi * frac)
                cr.set_source_rgba(self._timer_tint[0], self._timer_tint[1], self._timer_tint[2], 0.9 * alpha)
                cr.stroke()
            cr.restore()
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
        cr.new_sub_path()
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

        shelf_count_str = str(len(self._shelf.items)) if self._shelf.items else ""
        rows = [
            (Glyph.Clock, "Таймер", self._timer.formatted if self._timer.active else "", COLOR_ORANGE if self._timer.active else COLOR_DIM[:3]),
            (Glyph.Tray, "Полка", shelf_count_str, COLOR_DIM[:3]),
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
                if glyph == Glyph.Clock and self._timer.active:
                    self._digits_menu_timer.set_text(extra)
                    self._digits_menu_timer.render(cr, px + pw - 36.0, ry + 20.0, font_size=13.5, color=(tint[0], tint[1], tint[2], alpha), align="right", valign="center")
                elif glyph == Glyph.Tray and self._shelf.items:
                    self._digits_shelf_menu.set_text(extra)
                    self._digits_shelf_menu.render(cr, px + pw - 36.0, ry + 20.0, font_size=13.5, color=(tint[0], tint[1], tint[2], alpha), align="right", valign="center")
                else:
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
            (Glyph.Lines, "Заглавная буква в названии", "capitalize_title"),
        ]
        row_y_start = py + 44.0
        row_h = 40.0
        for idx, (glyph, label, key) in enumerate(rows):
            ry = row_y_start + idx * row_h
            render_icon(cr, glyph, px + 22.0, ry + 11.5, 17.0, COLOR_DIM[:3], alpha=alpha)
            draw_text(cr, label, px + 49.0, ry + 20.0, font_size=13.5, bold=False, color=COLOR_WHITE, alpha=alpha, align="left", valign="center")
            self._toggles[key].render(cr, px + pw - 50.0, ry + 10.0, w=38.0, h=22.0)

        # Update row (index 9)
        upd_ry = row_y_start + len(rows) * row_h
        render_icon(cr, Glyph.Sparkle, px + 22.0, upd_ry + 11.5, 17.0, COLOR_ORANGE if self._updater.state == UpdateState.AVAILABLE else COLOR_DIM[:3], alpha=alpha)
        draw_text(cr, "Обновление", px + 49.0, upd_ry + 20.0, font_size=13.5, bold=False, color=COLOR_WHITE, alpha=alpha, align="left", valign="center")
        draw_text(cr, f"v{self._updater.latest_version}", px + pw - 38.0, upd_ry + 20.0, font_size=13.0, bold=False, color=COLOR_DIM[:3], alpha=alpha, align="right", valign="center")
        render_icon(cr, Glyph.Chevron, px + pw - 26.0, upd_ry + 14.5, 11.0, COLOR_DIM[:3], alpha=alpha)

    def render_look(self, cr: cairo.Context, px: float, py: float, pw: float, ph: float, alpha: float) -> None:
        render_icon(cr, Glyph.Back, px + 20.0, py + 18.0, 10.0, COLOR_DIM[:3], alpha=0.6 * alpha)
        draw_text(cr, "ОФОРМЛЕНИЕ", px + 36.0, py + 23.0, font_size=10.5, bold=True, color=COLOR_DIM[:3], alpha=0.6 * alpha, align="left", valign="center")

        self._row_list_look.render_highlight(cr, w=pw - 20.0, x=px + 10.0)

        cur_accent_label = "Из обложки"
        for col, lbl in LOOK_COLORS:
            if col == Settings.accent:
                cur_accent_label = lbl
                break

        if Settings.material == MATERIAL_LIQUID:
            material_label = "Жидкое"
        elif Settings.material == MATERIAL_MATTE:
            material_label = "Матовое"
        else:
            material_label = "Отключено"

        pos_x_str = f"+{Settings.pos_x} px" if Settings.pos_x > 0 else f"{Settings.pos_x} px"
        seek_style_label = "По строкам" if Settings.line_bar else "Сплошная"
        eq_style_label = "Матрица" if Settings.equalizer_dots else "Полоски"
        rows = [
            (Glyph.Size, "Размер", f"{Settings.scale}%"),
            (Glyph.Gap, "Позиция Y (Отступ)", f"{Settings.pos_y} px"),
            (Glyph.Size, "Позиция X (Смещение)", pos_x_str),
            (Glyph.Rim, "Радиус скругления", f"{Settings.radius}%"),
            (Glyph.Expand, "Высота острова", f"{Settings.height} px"),
            (Glyph.Lines, "Размер текста", f"{Settings.text_scale}%"),
            (Glyph.Look, "Стиль стекла", material_label),
            (Glyph.Sparkle, "Сила стекла", f"{Settings.glass}%"),
            (Glyph.Lines, "Полоса трека", seek_style_label),
            (Glyph.Pulse, "Эквалайзер", eq_style_label),
            (Glyph.Drop, "Акцентный цвет", cur_accent_label),
        ]
        row_y_start = py + 44.0
        row_h = 40.0
        for idx, (glyph, label, val_text) in enumerate(rows):
            ry = row_y_start + idx * row_h
            render_icon(cr, glyph, px + 22.0, ry + 11.5, 17.0, COLOR_DIM[:3], alpha=alpha)
            draw_text(cr, label, px + 49.0, ry + 20.0, font_size=13.5, bold=False, color=COLOR_WHITE, alpha=alpha, align="left", valign="center")
            draw_text(cr, val_text, px + pw - 24.0, ry + 20.0, font_size=13.5, bold=False, color=COLOR_DIM[:3], alpha=alpha, align="right", valign="center")

        swatch_y = row_y_start + len(rows) * row_h + 18.0
        step_x = (pw - 20.0) / len(LOOK_COLORS)
        for idx, (col, _) in enumerate(LOOK_COLORS):
            sx = px + 10.0 + idx * step_x + step_x / 2.0
            is_checked = (col == Settings.accent)

            if is_checked:
                cr.new_sub_path()
                cr.arc(sx, swatch_y, 11.0, 0, 2 * math.pi)
                cr.set_source_rgba(1.0, 1.0, 1.0, alpha)
                cr.set_line_width(1.5)
                cr.stroke()

            cr.new_sub_path()
            cr.arc(sx, swatch_y, 7.0, 0, 2 * math.pi)
            if col is None:
                cr.set_source_rgba(1.0, 0.4, 0.7, alpha)
            else:
                cr.set_source_rgba(col[0], col[1], col[2], alpha)
            cr.fill()

    def render_update(self, cr: cairo.Context, px: float, py: float, pw: float, ph: float, alpha: float) -> None:
        render_icon(cr, Glyph.Back, px + 20.0, py + 18.0, 10.0, COLOR_DIM[:3], alpha=0.6 * alpha)
        draw_text(cr, "ОБНОВЛЕНИЕ", px + 36.0, py + 23.0, font_size=10.5, bold=True, color=COLOR_DIM[:3], alpha=0.6 * alpha, align="left", valign="center")

        state = self._updater.state
        latest = self._updater.latest_version
        curr = self._updater.current_version

        draw_text(cr, f"v{latest}", px + 22.0, py + 56.0, font_size=28.0, bold=True, color=COLOR_WHITE, alpha=alpha, align="left", valign="center")

        status_text = "У вас актуальная версия" if state == UpdateState.LATEST else \
                      "Доступно обновление!" if state == UpdateState.AVAILABLE else \
                      "Проверка обновлений..." if state == UpdateState.CHECKING else \
                      f"Загрузка... {int(self._updater.percent * 100)}%" if state == UpdateState.DOWNLOADING else \
                      "Обновление готово к установке" if state == UpdateState.READY else \
                      f"Ошибка: {self._updater.error_message}" if state == UpdateState.FAILED else f"Текущая версия: v{curr}"

        draw_text(cr, status_text, px + 22.0, py + 84.0, font_size=12.0, color=COLOR_DIM[:3], alpha=alpha, align="left", valign="center")

        ny = py + 106.0
        if self._updater.notes:
            for i, note in enumerate(self._updater.notes[:3]):
                draw_text(cr, f"• {note}", px + 22.0, ny + i * 20.0, font_size=11.5, color=COLOR_WHITE, alpha=0.85 * alpha, align="left", valign="center")

        btn_y = py + ph - 46.0
        btn_w = pw - 44.0
        btn_h = 36.0
        btn_x = px + 22.0
        self._btn_update_rect = (btn_x, btn_y, btn_w, btn_h)

        draw_rounded_rect(cr, btn_x, btn_y, btn_w, btn_h, 12.0)
        btn_color = COLOR_ORANGE if state in (UpdateState.AVAILABLE, UpdateState.READY) else COLOR_DIM[:3]
        cr.set_source_rgba(btn_color[0], btn_color[1], btn_color[2], 0.3 * alpha)
        cr.fill()

        if state == UpdateState.DOWNLOADING:
            btn_label = f"Загрузка... {int(self._updater.percent * 100)}%"
            Ring.draw_ring(cr, btn_x + 22.0, btn_y + btn_h / 2.0, radius=8.0, thickness=2.0, progress=self._updater.percent, color=COLOR_ORANGE, alpha=alpha)
        elif state == UpdateState.READY:
            btn_label = "Перезапустить остров"
        elif state == UpdateState.AVAILABLE:
            btn_label = "Обновить и перезапустить"
        elif state == UpdateState.CHECKING:
            btn_label = "Проверяем..."
        else:
            btn_label = "Проверить снова"

        draw_text(cr, btn_label, btn_x + btn_w / 2.0, btn_y + btn_h / 2.0, font_size=13.0, bold=True, color=COLOR_WHITE, alpha=alpha, align="center", valign="center")
