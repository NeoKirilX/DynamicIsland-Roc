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
        changed = False
        for item in items:
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
                        item._data = data
                        item.surface = surf
                        item.photo = True
                        changed = True
                except Exception:
                    item.surface = None
                    item.photo = False
        if changed:
            try:
                from gi.repository import GLib
                GLib.idle_add(self._notify)
            except Exception:
                self._notify()

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
