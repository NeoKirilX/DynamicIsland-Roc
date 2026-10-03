
from __future__ import annotations

import math

import cairo

try:
    from spring import Spring
except ImportError:
    from .spring import Spring

def _draw_rounded_rect(
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

class RowList:

    RADIUS: float = 12.0
    HOVER: float = 0.12
    PRESS: float = 0.21
    SQUISH_X: float = 5.0
    SQUISH_Y: float = 2.0
    POP: float = 0.6

    def __init__(self) -> None:
        self._top: Spring = Spring(0.0)
        self._bottom: Spring = Spring(0.0)
        self._shown: Spring = Spring(0.0)
        self._squish: Spring = Spring(0.0)

        self._lit: bool = False
        self._pressed: bool = False
        self._hover_idx: int | None = None

    @property
    def hover_idx(self) -> int | None:
        return self._hover_idx

    @property
    def is_lit(self) -> bool:
        return self._lit

    @property
    def is_pressed(self) -> bool:
        return self._pressed

    def set_hover(self, row_idx: int, row_y: float, row_h: float) -> None:
        top = float(row_y)
        bottom = top + float(row_h)

        if self._shown.value < 0.05:
            self._top.value = self._top.target = top
            self._bottom.value = self._bottom.target = bottom
            self._top.velocity = self._bottom.velocity = 0.0
            self._squish.value = self.POP
        elif top != self._top.target:
            down = top > self._top.target
            if down:
                self._bottom.tune(560.0, 36.0)
                self._top.tune(230.0, 26.0)
            else:
                self._top.tune(560.0, 36.0)
                self._bottom.tune(230.0, 26.0)

        self._top.target = top
        self._bottom.target = bottom
        self._hover_idx = row_idx

        if not self._lit:
            self._shown.tune(420.0, 41.0)
            self._lit = True
        self._shown.target = 1.0

    def move_to(self, row_y: float, row_h: float, row_idx: int = 0) -> None:
        self.set_hover(row_idx, row_y, row_h)

    def set_pressed(self, pressed: bool) -> None:
        pressed = bool(pressed)
        if pressed != self._pressed:
            if pressed:
                self._squish.tune(700.0, 44.0)
            else:
                self._squish.tune(380.0, 16.0)
            self._pressed = pressed
            self._squish.target = 1.0 if pressed else 0.0

    def clear_hover(self) -> None:
        self._hover_idx = None
        if self._lit:
            self._shown.tune(90.0, 19.0)
            self._shown.target = 0.0
            self._lit = False
        if self._pressed:
            self._squish.tune(380.0, 16.0)
            self._squish.target = 0.0
            self._pressed = False

    def rest(self) -> None:
        self._lit = False
        self._pressed = False
        self._hover_idx = None
        self._shown.value = self._shown.target = self._shown.velocity = 0.0
        self._squish.value = self._squish.target = self._squish.velocity = 0.0

    def tick(self, dt: float) -> bool:
        dt = min(max(float(dt), 0.0), 0.05)
        if dt <= 0.0:
            return False

        moving = self._top.advance(dt)
        moving |= self._bottom.advance(dt)
        moving |= self._shown.advance(dt)
        moving |= self._squish.advance(dt)
        return moving

    def render_highlight(
        self, cr: cairo.Context, w: float, x: float = 0.0
    ) -> None:
        shown = max(0.0, min(1.0, self._shown.value))
        if shown <= 0.001 or w <= 0.0:
            return

        squish = max(0.0, min(1.0, self._squish.value))
        opacity = shown * (self.HOVER + (self.PRESS - self.HOVER) * squish)
        if opacity <= 0.001:
            return

        sx = self.SQUISH_X * self._squish.value
        sy = self.SQUISH_Y * self._squish.value

        rect_x = x + sx
        rect_y = self._top.value + sy
        rect_w = max(0.0, w - sx * 2.0)
        rect_h = max(0.0, self._bottom.value - self._top.value - sy * 2.0)

        if rect_w <= 0.0 or rect_h <= 0.0:
            return

        cr.save()
        r = min(self.RADIUS, min(rect_w, rect_h) / 2.0)
        _draw_rounded_rect(cr, rect_x, rect_y, rect_w, rect_h, r)
        cr.set_source_rgba(1.0, 1.0, 1.0, opacity)
        cr.fill()
        cr.restore()

if __name__ == "__main__":
    print("Testing RowList component...")

    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 200, 300)
    cr = cairo.Context(surf)

    row_list = RowList()
    assert not row_list.is_lit
    assert row_list.hover_idx is None

    row_list.set_hover(row_idx=0, row_y=10.0, row_h=40.0)
    assert row_list.is_lit
    assert row_list.hover_idx == 0
    assert row_list._top.target == 10.0
    assert row_list._bottom.target == 50.0

    for _ in range(10):
        row_list.tick(1.0 / 60.0)
        row_list.render_highlight(cr, w=180.0, x=10.0)
    print("Initial row hover spring animation stepped and rendered.")

    row_list.set_hover(row_idx=2, row_y=110.0, row_h=40.0)
    assert row_list._bottom.stiffness == 560.0, "Leading bottom edge should be tuned to 560"
    assert row_list._top.stiffness == 230.0, "Trailing top edge should be dragged with 230"

    stretching = False
    for step in range(30):
        row_list.tick(1.0 / 60.0)
        height = row_list._bottom.value - row_list._top.value
        if height > 42.0:
            stretching = True
        row_list.render_highlight(cr, w=180.0, x=10.0)

    assert stretching, "Magnetic highlight should dynamically stretch while traveling"
    print("Magnetic stretch behavior verified successfully.")

    for _ in range(60):
        row_list.tick(1.0 / 60.0)

    assert abs(row_list._top.value - 110.0) < 0.1
    assert abs(row_list._bottom.value - 150.0) < 0.1
    print("Springs settled accurately at target row position.")

    row_list.set_pressed(True)
    assert row_list.is_pressed
    assert row_list._squish.target == 1.0
    assert row_list._squish.stiffness == 700.0

    for _ in range(15):
        row_list.tick(1.0 / 60.0)
        row_list.render_highlight(cr, w=180.0, x=10.0)

    assert row_list._squish.value > 0.5, "Squish spring should compress under press"

    row_list.set_pressed(False)
    assert not row_list.is_pressed
    assert row_list._squish.stiffness == 380.0
    for _ in range(30):
        row_list.tick(1.0 / 60.0)

    row_list.clear_hover()
    assert not row_list.is_lit
    assert row_list.hover_idx is None
    for _ in range(60):
        row_list.tick(1.0 / 60.0)

    assert abs(row_list._shown.value) < 0.01, "Opacity spring should decay to 0"
    print("Row hover cleared and faded out.")

    print("All RowList component tests passed successfully!")
