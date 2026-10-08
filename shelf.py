from __future__ import annotations

import math
import os
import subprocess
import threading
from pathlib import Path
from typing import Callable, Optional, Sequence

import cairo

try:
    from PIL import Image
except ImportError:
    Image = None

from icon import Glyph, render_icon
from lyric import measure_text
from settings import Settings
from spring import Spring

TILE_WIDE = 64.0
TILE_SQUARE = 56.0
TILE_RADIUS = 13.0
TILE_STEP = 68.0
SHELF_WIDE = 380.0
SHELF_HIGH = 136.0
STRIP_MARGIN = 18.0
STRIP_WIDE = SHELF_WIDE - 2.0 * STRIP_MARGIN

COLOR_DIM = (1.0, 1.0, 1.0, 0.55)
COLOR_WHITE = (1.0, 1.0, 1.0, 1.0)

def _draw_rounded_rect(cr: cairo.Context, x: float, y: float, w: float, h: float, r: float) -> None:
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2.0, 0.0)
    cr.arc(x + w - r, y + h - r, r, 0.0, math.pi / 2.0)
    cr.arc(x + r, y + h - r, r, math.pi / 2.0, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3.0 * math.pi / 2.0)
    cr.close_path()

class ShelfItem:
    def __init__(self, path: str) -> None:
        self.path: str = os.path.abspath(os.path.expanduser(path))
        p = Path(self.path)
        self.name: str = p.name if p.name else self.path
        self.photo: bool = False
        self.is_config: bool = self.path.lower().endswith(".dni")
        self.surface: Optional[cairo.ImageSurface] = None
        self._data: Optional[bytearray] = None
        self.swell: Spring = Spring(1.0, 260.0, 24.0)
        self.cross: Spring = Spring(0.0, 320.0, 28.0)
        self.is_hovered: bool = False

    def tick(self, dt: float) -> bool:
        moving = False
        moving |= self.swell.advance(dt)
        moving |= self.cross.advance(dt)
        return moving

class Shelf:
    def __init__(self) -> None:
        self.items: list[ShelfItem] = []
        self._listeners: list[Callable[[], None]] = []
        self._load()

    def add_change_listener(self, cb: Callable[[], None]) -> None:
        if cb not in self._listeners:
            self._listeners.append(cb)

    def _notify(self) -> None:
        for cb in self._listeners:
            try:
                cb()
            except Exception:
                pass

    def _load(self) -> None:
        saved = Settings.shelf
        valid = [p for p in saved if os.path.exists(p)]
        self.items = [ShelfItem(p) for p in valid]
        self._start_thumbnails([it for it in self.items])

    def save(self) -> None:
        Settings.shelf = [it.path for it in self.items]
        self._notify()

    def add(self, paths: Sequence[str]) -> bool:
        added: list[ShelfItem] = []
        existing = {it.path for it in self.items}
        for p in paths:
            if not p:
                continue
            abs_p = os.path.abspath(os.path.expanduser(p))
            if os.path.exists(abs_p) and abs_p not in existing:
                item = ShelfItem(abs_p)
                self.items.append(item)
                added.append(item)
                existing.add(abs_p)
        if added:
            self.save()
            self._start_thumbnails(added)
            return True
        return False

    def remove(self, item: ShelfItem) -> None:
        if item in self.items:
            self.items.remove(item)
            self.save()

    def clear(self) -> None:
        if self.items:
            self.items.clear()
            self.save()

    def _start_thumbnails(self, items: list[ShelfItem]) -> None:
        if not items:
            return
        t = threading.Thread(target=self._generate_thumbnails, args=(items,), daemon=True)
        t.start()

    def _generate_thumbnails(self, items: list[ShelfItem]) -> None:
        image_exts = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".svg"}
        updates: list[tuple[ShelfItem, Optional[cairo.ImageSurface], Optional[bytearray], bool]] = []
        for item in items:
            if item.is_config:
                try:
                    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 112, 112)
                    cr = cairo.Context(surf)
                    # Rounded dark background
                    _draw_rounded_rect(cr, 4.0, 4.0, 104.0, 104.0, 24.0)
                    cr.set_source_rgba(0.12, 0.12, 0.15, 0.95)
                    cr.fill_preserve()
                    cr.set_source_rgba(1.0, 0.55, 0.0, 0.45)
                    cr.set_line_width(2.0)
                    cr.stroke()

                    # Pill graphic
                    _draw_rounded_rect(cr, 24.0, 28.0, 64.0, 28.0, 14.0)
                    cr.set_source_rgba(0.0, 0.0, 0.0, 0.9)
                    cr.fill_preserve()
                    cr.set_source_rgba(1.0, 0.55, 0.0, 0.8)
                    cr.set_line_width(1.5)
                    cr.stroke()
                    render_icon(cr, Glyph.Gear, 48.0, 34.0, 16.0, (1.0, 1.0, 1.0), 1.0)

                    # Text label
                    cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
                    cr.set_font_size(15.0)
                    cr.set_source_rgba(1.0, 1.0, 1.0, 0.95)
                    cr.move_to(38.0, 84.0)
                    cr.show_text(".DNI")
                    updates.append((item, surf, None, True))
                except Exception:
                    pass
                continue

            p = Path(item.path)
            if p.suffix.lower() in image_exts and Image is not None:
                try:
                    with Image.open(item.path) as img:
                        img = img.convert("RGBA")
                        img.thumbnail((112, 112), Image.Resampling.LANCZOS)
                        w, h = img.size
                        data = bytearray(img.tobytes("raw", "BGRA"))
                        stride = cairo.ImageSurface.format_stride_for_width(cairo.FORMAT_ARGB32, w)
                        surf = cairo.ImageSurface.create_for_data(data, cairo.FORMAT_ARGB32, w, h, stride)
                        updates.append((item, surf, data, True))
                except Exception:
                    updates.append((item, None, None, False))

        if updates:
            def _apply():
                for it, s, d, photo in updates:
                    it._data = d
                    it.surface = s
                    it.photo = photo
                self._notify()
                return False

            try:
                from gi.repository import GLib
                GLib.idle_add(_apply)
            except Exception:
                _apply()

    def open_item(self, item: ShelfItem) -> None:
        if not os.path.exists(item.path):
            self.remove(item)
            return
        try:
            subprocess.Popen(["xdg-open", item.path])
        except Exception:
            pass

    def tick(self, dt: float) -> bool:
        moving = False
        for it in self.items:
            moving |= it.tick(dt)
        return moving
