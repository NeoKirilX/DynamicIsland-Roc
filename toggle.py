
from __future__ import annotations

import math

import cairo

class Toggle:

    DEFAULT_WIDTH: float = 36.0
    DEFAULT_HEIGHT: float = 20.0
    INSET: float = 2.0
    DURATION: float = 0.22

    COLOR_OFF: tuple[float, float, float] = (0.22, 0.22, 0.24)
    COLOR_ON: tuple[float, float, float] = (0.19, 0.82, 0.35)

    def __init__(self, initial_state: bool = False) -> None:
        self._on: bool = bool(initial_state)
        self._progress: float = 1.0 if self._on else 0.0
        self._from_progress: float = self._progress
        self._target_progress: float = self._progress
        self._elapsed: float = 0.0
        self._animating: bool = False

    @property
    def on(self) -> bool:
        return self._on

    @property
    def is_on(self) -> bool:
        return self._on

    @property
    def progress(self) -> float:
        return self._progress

    @property
    def is_animating(self) -> bool:
        return self._animating

    def set_state(self, on: bool, animate: bool = True) -> None:
        on = bool(on)
        self._on = on
        target = 1.0 if on else 0.0

        if not animate:
            self._progress = target
            self._from_progress = target
            self._target_progress = target
            self._animating = False
            return

        if abs(self._progress - target) < 1e-4 and not self._animating:
            return

        self._from_progress = self._progress
        self._target_progress = target
        self._elapsed = 0.0
        self._animating = True

    def toggle(self, animate: bool = True) -> None:
        self.set_state(not self._on, animate=animate)

    def tick(self, dt: float) -> bool:
        if not self._animating:
            return False

        self._elapsed += max(0.0, float(dt))
        t = (
            min(1.0, self._elapsed / self.DURATION)
            if self.DURATION > 0.0
            else 1.0
        )
        ease = 1.0 - (1.0 - t) ** 3
        self._progress = (
            self._from_progress
            + (self._target_progress - self._from_progress) * ease
        )

        if self._elapsed >= self.DURATION:
            self._progress = self._target_progress
            self._animating = False
            return False

        return True

    def render(
        self,
        cr: cairo.Context,
        x: float,
        y: float,
        w: float = DEFAULT_WIDTH,
        h: float = DEFAULT_HEIGHT,
    ) -> None:
        if w <= 0.0 or h <= 0.0:
            return

        share = max(0.0, min(1.0, self._progress))

        track_r = self.COLOR_OFF[0] + (self.COLOR_ON[0] - self.COLOR_OFF[0]) * share
        track_g = self.COLOR_OFF[1] + (self.COLOR_ON[1] - self.COLOR_OFF[1]) * share
        track_b = self.COLOR_OFF[2] + (self.COLOR_ON[2] - self.COLOR_OFF[2]) * share

        cr.save()

        radius = h / 2.0
        cr.new_sub_path()
        cr.arc(x + w - radius, y + radius, radius, -math.pi / 2.0, math.pi / 2.0)
        cr.arc(x + radius, y + radius, radius, math.pi / 2.0, 3.0 * math.pi / 2.0)
        cr.close_path()
        cr.set_source_rgb(track_r, track_g, track_b)
        cr.fill()

        inset = self.INSET * (h / self.DEFAULT_HEIGHT)
        knob_r = max(1.0, radius - inset)
        knob_cx = x + radius + (w - 2.0 * radius) * share
        knob_cy = y + radius

        cr.new_sub_path()
        cr.arc(knob_cx, knob_cy, knob_r, 0.0, 2.0 * math.pi)
        cr.set_source_rgb(1.0, 1.0, 1.0)
        cr.fill()

        cr.restore()

if __name__ == "__main__":
    print("Testing Toggle component...")

    toggle = Toggle(initial_state=False)
    assert not toggle.on, "Expected initial state OFF"
    assert toggle.progress == 0.0, "Expected initial progress 0.0"

    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 100, 50)
    cr = cairo.Context(surf)

    toggle.render(cr, x=10, y=10, w=36, h=20)
    print("Rendered OFF state successfully.")

    toggle.set_state(True, animate=True)
    assert toggle.on, "Expected state ON"
    assert toggle.is_animating, "Toggle should be animating after set_state(True)"

    moved = toggle.tick(0.11)
    assert moved, "tick should return True while animating"
    assert 0.4 < toggle.progress < 0.9, f"Mid progress expected ~0.7, got {toggle.progress:.3f}"
    toggle.render(cr, x=10, y=10, w=36, h=20)
    print(f"Mid-animation frame rendered at progress={toggle.progress:.3f}.")

    toggle.tick(0.15)
    assert not toggle.is_animating, "Toggle animation should be complete"
    assert toggle.progress == 1.0, f"Expected final progress 1.0, got {toggle.progress}"
    toggle.render(cr, x=10, y=10, w=36, h=20)
    print("Rendered ON state successfully.")

    toggle.set_state(False, animate=False)
    assert not toggle.on
    assert not toggle.is_animating
    assert toggle.progress == 0.0
    toggle.render(cr, x=10, y=10, w=36, h=20)
    print("Rendered instant OFF state successfully.")

    toggle.toggle(animate=True)
    assert toggle.on
    assert toggle.is_animating

    print("All Toggle component tests passed successfully!")
