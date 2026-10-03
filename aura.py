
from __future__ import annotations

import math
from typing import Any, Sequence

import cairo

class Aura:

    PATCHES: int = 4
    ATTACK: float = 0.07
    RELEASE: float = 0.45
    DRIFT: float = 0.06

    ANCHOR: tuple[float, ...] = (0.40, 0.63, 0.15, 0.86)
    SPEED: tuple[float, ...] = (0.55, 0.43, 0.71, 0.62)
    PHASE: tuple[float, ...] = (0.0, 2.1, 4.0, 5.3)

    SHADE: tuple[int, ...] = (1, 2, 0, 0)

    FALLOFF: tuple[tuple[float, float], ...] = (
        (0.0, 1.0),
        (0.25, 0.7),
        (0.5, 0.3),
        (0.75, 0.07),
        (1.0, 0.0),
    )

    def __init__(self) -> None:
        self._levels: list[float] = [0.0] * self.PATCHES
        self._current_colors: list[list[float]] = [[1.0, 1.0, 1.0] for _ in range(self.PATCHES)]
        self._target_colors: list[list[float]] = [[1.0, 1.0, 1.0] for _ in range(self.PATCHES)]
        self._time: float = 0.0

    @property
    def levels(self) -> list[float]:
        return list(self._levels)

    def tint(self, colors: Sequence[tuple[float, float, float]]) -> None:
        if not colors:
            clean_colors = [(1.0, 1.0, 1.0)]
        else:
            clean_colors = []
            for col in colors:
                r, g, b = col
                if r > 1.0 or g > 1.0 or b > 1.0:
                    r /= 255.0
                    g /= 255.0
                    b /= 255.0
                clean_colors.append((float(r), float(g), float(b)))

        num_colors = len(clean_colors)
        for p in range(self.PATCHES):
            chosen = clean_colors[self.SHADE[p] % num_colors]
            self._target_colors[p] = [chosen[0], chosen[1], chosen[2]]

    def tick(self, equalizer: Any, t: float, dt: float) -> bool:
        dt = max(1e-4, float(dt))
        rise = 1.0 - math.exp(-dt / self.ATTACK)
        fall = 1.0 - math.exp(-dt / self.RELEASE)
        moved = False

        bars_count = getattr(equalizer, "bars", 5)

        for p in range(self.PATCHES):
            from_idx = p * bars_count // self.PATCHES
            to_idx = max((p + 1) * bars_count // self.PATCHES, from_idx + 1)
            target = sum(equalizer.level(b) for b in range(from_idx, to_idx)) / float(to_idx - from_idx)

            curr = self._levels[p]
            next_val = curr + (target - curr) * (rise if target > curr else fall)
            if abs(next_val - curr) > 0.002:
                moved = True
            self._levels[p] = next_val

        color_blend = 1.0 - math.exp(-dt / 0.35)
        for p in range(self.PATCHES):
            for c in range(3):
                diff = self._target_colors[p][c] - self._current_colors[p][c]
                if abs(diff) > 0.001:
                    moved = True
                self._current_colors[p][c] += diff * color_blend

        self._time = float(t)
        return moved

    def render(self, cr: cairo.Context, w: float, h: float) -> None:
        if w <= 0.0 or h <= 0.0:
            return

        cr.save()
        cr.rectangle(0.0, 0.0, w, h)
        cr.clip()

        for p in range(self.PATCHES):
            level = self._levels[p]
            x = w * (self.ANCHOR[p] + self.DRIFT * math.sin(self._time * self.SPEED[p] + self.PHASE[p]))
            y = h
            rx = w * (0.26 + 0.1 * level)
            ry = h * (0.30 + 0.4 * level)
            patch_opacity = 0.16 + 0.5 * level
            col = self._current_colors[p]

            cr.save()
            cr.translate(x, y)
            cr.scale(rx, ry)
            grad = cairo.RadialGradient(0.0, 0.0, 0.0, 0.0, 0.0, 1.0)
            for offset, alpha in self.FALLOFF:
                grad.add_color_stop_rgba(offset, col[0], col[1], col[2], alpha * patch_opacity)
            cr.set_source(grad)
            cr.arc(0.0, 0.0, 1.0, 0.0, 2.0 * math.pi)
            cr.fill()
            cr.restore()

        cr.restore()

if __name__ == "__main__":
    print("Testing Aura...")

    class MockEqualizer:
        bars = 5

        def __init__(self, lvl: float = 0.5) -> None:
            self._lvl = lvl

        def level(self, band: int) -> float:
            return self._lvl

    aura = Aura()
    eq = MockEqualizer(lvl=0.7)

    moved = aura.tick(eq, t=0.0, dt=1.0 / 60.0)
    assert moved, "Aura should move towards equalizer levels"
    print(f"Tick 1 levels: {[round(x, 4) for x in aura.levels]}")

    for step in range(15):
        aura.tick(eq, t=step * 0.016, dt=0.016)

    assert all(x > 0.0 for x in aura.levels), "All patches should bloom with equalizer input"
    print(f"Bloomed levels: {[round(x, 4) for x in aura.levels]}")

    colors = [(255, 60, 0), (200, 0, 255), (0, 150, 255)]
    aura.tint(colors)
    assert abs(aura._target_colors[0][0] - 200.0 / 255.0) < 1e-4
    assert abs(aura._target_colors[1][0] - 0.0 / 255.0) < 1e-4
    assert abs(aura._target_colors[2][0] - 255.0 / 255.0) < 1e-4
    print("Tint correctly mapped colors according to shades.")

    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 380, 180)
    cr = cairo.Context(surface)
    aura.render(cr, w=380.0, h=180.0)
    print("Rendered Aura to Cairo context successfully.")

    silent_eq = MockEqualizer(lvl=0.0)
    for _ in range(150):
        aura.tick(silent_eq, t=10.0, dt=0.05)
    assert all(x < 0.01 for x in aura.levels), "Aura patches should decay to near-zero when silent"
    print("Decay to rest: All aura patches < 0.01.")
    print("All Aura tests passed successfully!")
