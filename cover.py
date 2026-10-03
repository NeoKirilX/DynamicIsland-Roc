
from __future__ import annotations

import math

import cairo

def _ease_out_quartic(t: float) -> float:
    t = max(0.0, min(1.0, float(t)))
    return 1.0 - (1.0 - t) ** 4

def _clip_rounded_rect(
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

class Cover:

    SMALL: float = 0.88
    DURATION: float = 0.46
    FADE_IN_DURATION: float = 0.30
    FADE_OUT_DURATION: float = 0.24

    def __init__(self) -> None:
        self._current_surface: cairo.Surface | None = None
        self._old_surface: cairo.Surface | None = None

        self._mode: str = "idle"
        self._direction: int = 0
        self._elapsed: float = 0.0
        self._animating: bool = False

    @property
    def surface(self) -> cairo.Surface | None:
        return self._current_surface

    @property
    def is_animating(self) -> bool:
        return self._animating

    def show(self, image_surface: cairo.Surface | None, direction: int = 0) -> None:
        old = self._current_surface
        self._old_surface = old
        self._current_surface = image_surface
        self._elapsed = 0.0
        self._animating = True

        if image_surface is None:
            if old is None:
                self._mode = "idle"
                self._animating = False
            else:
                self._mode = "leave"
                self._direction = 1 if direction == 0 else direction
            return

        if old is None or direction == 0:
            self._mode = "grow"
            self._direction = 0
            self._old_surface = None
        else:
            self._mode = "slide"
            self._direction = 1 if direction >= 0 else -1

    def tick(self, dt: float) -> bool:
        if not self._animating:
            return False

        self._elapsed += max(0.0, float(dt))
        if self._elapsed >= self.DURATION:
            self._animating = False
            self._old_surface = None
            if self._mode == "leave":
                self._current_surface = None
            self._mode = "idle"
            return False
        return True

    def render(
        self,
        cr: cairo.Context,
        x: float,
        y: float,
        size: float,
        radius: float,
        dt: float = 0.0,
    ) -> None:
        if dt > 0.0:
            self.tick(dt)

        if size <= 0.0:
            return
        if self._current_surface is None and self._old_surface is None:
            return

        cr.save()
        _clip_rounded_rect(cr, x, y, size, size, radius)

        progress = (
            min(1.0, self._elapsed / self.DURATION) if self.DURATION > 0.0 else 1.0
        )
        ease = _ease_out_quartic(progress)

        if self._mode == "grow":
            scale = self.SMALL + (1.0 - self.SMALL) * ease
            opacity = (
                min(1.0, self._elapsed / self.FADE_IN_DURATION)
                if self.FADE_IN_DURATION > 0.0
                else 1.0
            )
            if self._current_surface is not None:
                self._draw_surface(
                    cr, self._current_surface, x, y, size, 0.0, scale, opacity
                )
        elif self._mode == "slide":
            far = size * (1.0 if self._direction >= 0 else -1.0)
            old_offset_x = -far * ease
            new_offset_x = far * (1.0 - ease)

            if self._old_surface is not None:
                self._draw_surface(
                    cr, self._old_surface, x, y, size, old_offset_x, 1.0, 1.0
                )
            if self._current_surface is not None:
                self._draw_surface(
                    cr, self._current_surface, x, y, size, new_offset_x, 1.0, 1.0
                )
        elif self._mode == "leave":
            far = size * (1.0 if self._direction >= 0 else -1.0)
            old_offset_x = -far * ease
            opacity = (
                max(0.0, 1.0 - self._elapsed / self.FADE_OUT_DURATION)
                if self.FADE_OUT_DURATION > 0.0
                else 0.0
            )
            if self._old_surface is not None:
                self._draw_surface(
                    cr, self._old_surface, x, y, size, old_offset_x, 1.0, opacity
                )
        else:
            if self._current_surface is not None:
                self._draw_surface(
                    cr, self._current_surface, x, y, size, 0.0, 1.0, 1.0
                )

        cr.restore()

    @staticmethod
    def _draw_surface(
        cr: cairo.Context,
        surface: cairo.Surface,
        x: float,
        y: float,
        size: float,
        offset_x: float,
        scale: float,
        opacity: float,
    ) -> None:
        if opacity <= 0.0 or scale <= 0.0:
            return

        cr.save()
        cr.translate(x + offset_x, y)

        if scale != 1.0:
            cr.translate(size / 2.0, size / 2.0)
            cr.scale(scale, scale)
            cr.translate(-size / 2.0, -size / 2.0)

        w = float(surface.get_width()) if hasattr(surface, "get_width") else size
        h = float(surface.get_height()) if hasattr(surface, "get_height") else size
        if w > 0.0 and h > 0.0:
            s = max(size / w, size / h)
            cr.translate((size - w * s) / 2.0, (size - h * s) / 2.0)
            cr.scale(s, s)
            cr.set_source_surface(surface, 0.0, 0.0)
            if opacity < 1.0:
                cr.paint_with_alpha(max(0.0, min(1.0, opacity)))
            else:
                cr.paint()

        cr.restore()

if __name__ == "__main__":
    print("Testing Cover component...")

    surf1 = cairo.ImageSurface(cairo.FORMAT_ARGB32, 120, 120)
    cr1 = cairo.Context(surf1)
    cr1.set_source_rgb(0.8, 0.2, 0.2)
    cr1.paint()

    surf2 = cairo.ImageSurface(cairo.FORMAT_ARGB32, 120, 120)
    cr2 = cairo.Context(surf2)
    cr2.set_source_rgb(0.2, 0.6, 0.9)
    cr2.paint()

    dest_surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 200, 200)
    dest_cr = cairo.Context(dest_surf)

    cover = Cover()

    cover.show(surf1, direction=0)
    assert cover.is_animating, "Cover should be animating upon show(direction=0)"
    assert cover._mode == "grow", f"Expected mode 'grow', got {cover._mode}"

    cover.render(dest_cr, x=20, y=20, size=80, radius=12, dt=0.0)
    print("First cover initial frame rendered successfully.")

    cover.tick(0.23)
    assert cover.is_animating, "Cover should still be animating halfway"
    cover.render(dest_cr, x=20, y=20, size=80, radius=12, dt=0.0)

    cover.tick(0.30)
    assert not cover.is_animating, "Cover should be finished animating"
    assert cover._mode == "idle", f"Expected mode 'idle', got {cover._mode}"
    print("First cover grow animation completed.")

    cover.show(surf2, direction=1)
    assert cover.is_animating, "Cover should animate on next track slide"
    assert cover._mode == "slide", f"Expected mode 'slide', got {cover._mode}"
    assert cover._direction == 1, f"Expected direction 1, got {cover._direction}"

    cover.tick(0.23)
    cover.render(dest_cr, x=20, y=20, size=80, radius=12, dt=0.0)
    print("Slide next animation halfway frame rendered.")

    cover.tick(0.30)
    assert not cover.is_animating, "Cover should complete slide transition"
    assert cover.surface == surf2, "Current surface should be surf2"

    cover.show(surf1, direction=-1)
    assert cover.is_animating
    assert cover._direction == -1
    cover.render(dest_cr, x=20, y=20, size=80, radius=12, dt=0.23)
    cover.tick(0.30)
    assert not cover.is_animating

    cover.show(None, direction=1)
    assert cover.is_animating
    assert cover._mode == "leave"
    cover.tick(0.50)
    assert not cover.is_animating
    assert cover.surface is None

    print("All Cover component tests passed successfully!")
