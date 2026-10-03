
from __future__ import annotations

import math
from typing import Sequence

import cairo

class Equalizer:

    BAR_WIDTH: float = 3.0
    ATTACK: float = 0.03
    RELEASE: float = 0.17

    RANGE_DB: float = 10.0
    CENTER: float = 0.5
    RISE: float = 0.8
    SINK: float = 2.5
    SPREAD_DB: float = 12.0
    FLOOR_DB: float = -70.0

    F1: tuple[float, ...] = (7.1, 9.3, 6.2, 10.4, 8.0, 5.6, 9.9, 7.7)
    F2: tuple[float, ...] = (2.3, 3.1, 1.7, 2.9, 3.7, 2.1, 1.3, 3.3)

    def __init__(self, bars: int = 5, bar_width: float = 3.0) -> None:
        self._bar_width: float = float(bar_width)
        self._bars: int = 0
        self._levels: list[float] = []
        self._targets: list[float] = []
        self._db: list[float] = []
        self._base: list[float] = []
        self._rank: list[int] = []
        self._slot: list[int] = []

        self.bars = bars

    @property
    def bars(self) -> int:
        return self._bars

    @bars.setter
    def bars(self, value: int) -> None:
        count = max(2, int(value))
        if self._bars == count:
            return
        self._bars = count
        self._levels = [0.0] * self._bars
        self._targets = [0.0] * self._bars
        self._db = [self.FLOOR_DB] * self._bars
        self._base = [self.FLOOR_DB] * self._bars

        self._rank = [0] * self._bars
        self._slot = [0] * self._bars
        center = (self._bars - 1) // 2
        for k in range(self._bars):
            self._slot[k] = center + ((k + 1) // 2 if k % 2 == 1 else -k // 2)
            self._rank[self._slot[k]] = k

    @property
    def bar_width(self) -> float:
        return self._bar_width

    @bar_width.setter
    def bar_width(self, value: float) -> None:
        self._bar_width = max(1.0, float(value))

    @property
    def levels(self) -> list[float]:
        return list(self._levels)

    def level(self, band: int) -> float:
        if 0 <= band < self._bars:
            return self._levels[self._slot[band]]
        return 0.0

    def tick(
        self,
        spectrum_bands: Sequence[float] | None,
        peak: float,
        playing: bool,
        t: float,
        dt: float,
    ) -> bool:
        dt = max(1e-4, float(dt))

        if not playing:
            for i in range(self._bars):
                self._targets[i] = 0.0
        elif spectrum_bands is not None and any(b > 1e-9 for b in spectrum_bands):
            self._update_levels(spectrum_bands, dt)
        else:
            self._wobble(peak, t)

        rise = 1.0 - math.exp(-dt / self.ATTACK)
        fall = 1.0 - math.exp(-dt / self.RELEASE)
        moved = False

        for i in range(self._bars):
            target = self._targets[i]
            curr = self._levels[i]
            next_val = curr + (target - curr) * (rise if target > curr else fall)
            if abs(next_val - curr) > 0.002:
                moved = True
            self._levels[i] = next_val

        return moved

    def _update_levels(self, spectrum: Sequence[float], dt: float) -> None:
        headroom = self.RANGE_DB * (1.0 - self.CENTER)
        top = self.FLOOR_DB
        spectrum_len = len(spectrum)

        for i in range(self._bars):
            from_b = self._rank[i] * spectrum_len // self._bars
            to_b = max((self._rank[i] + 1) * spectrum_len // self._bars, from_b + 1)
            power = sum(spectrum[b] for b in range(from_b, to_b))
            db = 10.0 * math.log10(power / float(to_b - from_b) + 1e-14)
            self._db[i] = db

            if db > self.FLOOR_DB:
                b = self._base[i]
                b += (db - b) * (1.0 - math.exp(-dt / (self.RISE if db > b else self.SINK)))
                self._base[i] = max(b, db - headroom)
            top = max(top, self._base[i])

        for i in range(self._bars):
            reference = max(self._base[i], top - self.SPREAD_DB)
            val = self.CENTER + (self._db[i] - reference) / self.RANGE_DB
            self._targets[i] = max(0.0, min(1.0, val))

    def _wobble(self, peak: float, t: float) -> None:
        level = math.pow(max(0.0, min(1.0, peak * 1.8)), 0.6)
        mid = (self._bars - 1) / 2.0
        for i in range(self._bars):
            f_idx = i % 8
            noise = 0.5 + 0.5 * math.sin(t * self.F1[f_idx] + i * 1.9) * math.cos(t * self.F2[f_idx] + i * 0.7)
            envelope = 1.0 - 0.3 * abs(i - mid) / mid if mid > 0 else 1.0
            self._targets[i] = level * envelope * (0.3 + 0.7 * noise)

    def render(
        self,
        cr: cairo.Context,
        x: float,
        y: float,
        w: float,
        h: float,
        color: tuple[float, float, float] = (1.0, 1.0, 1.0),
        alpha: float = 1.0,
    ) -> None:
        if w <= 0.0 or h <= 0.0:
            return

        cr_r, cr_g, cr_b = color
        if cr_r > 1.0 or cr_g > 1.0 or cr_b > 1.0:
            cr_r /= 255.0
            cr_g /= 255.0
            cr_b /= 255.0

        bar_w = self._bar_width
        if w <= self._bars * bar_w:
            bar_w = max(1.0, w / (self._bars * 1.8))
        gap = (w - self._bars * bar_w) / max(1, self._bars - 1) if self._bars > 1 else 0.0

        for i in range(self._bars):
            bh = max(bar_w, bar_w + self._levels[i] * (h - bar_w))
            bx = x + i * (bar_w + gap)
            by = y + (h - bh) / 2.0

            bar_alpha = max(0.0, min(1.0, alpha * (0.55 + 0.45 * self._levels[i])))
            cr.set_source_rgba(cr_r, cr_g, cr_b, bar_alpha)

            rad = min(bar_w / 2.0, bh / 2.0)
            cr.new_sub_path()
            cr.arc(bx + rad, by + rad, rad, math.pi, 1.5 * math.pi)
            cr.arc(bx + bar_w - rad, by + rad, rad, 1.5 * math.pi, 2.0 * math.pi)
            cr.arc(bx + bar_w - rad, by + bh - rad, rad, 0.0, 0.5 * math.pi)
            cr.arc(bx + rad, by + bh - rad, rad, 0.5 * math.pi, math.pi)
            cr.close_path()
            cr.fill()

if __name__ == "__main__":
    print("Testing Equalizer...")

    eq = Equalizer(bars=5)
    assert eq.bars == 5, f"Expected 5 bars, got {eq.bars}"

    assert eq._slot[0] == 2, f"Lowest band should sit in center (slot 2), got {eq._slot[0]}"
    assert eq._rank[2] == 0, f"Center bar should represent band 0, got {eq._rank[2]}"
    print("Slot and rank mapping verified: Lowest band is centered.")

    spectrum = [0.1, 0.05, 0.01, 0.001, 0.0001]
    moved = eq.tick(spectrum, peak=0.5, playing=True, t=0.0, dt=1.0 / 60.0)
    assert moved, "Equalizer should move on first active tick"
    lvl0 = eq.level(0)
    print(f"Tick 1 levels: {[round(x, 4) for x in eq.levels]}, center band level: {lvl0:.4f}")

    for step in range(10):
        eq.tick(spectrum, peak=0.5, playing=True, t=step * 0.016, dt=0.016)

    assert eq.level(0) > 0.0, "Center bar level should rise with active bass"

    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 60, 30)
    cr = cairo.Context(surface)
    eq.render(cr, x=5.0, y=5.0, w=50.0, h=20.0, color=(1.0, 1.0, 1.0), alpha=0.9)
    print("Rendered Equalizer to Cairo context successfully.")

    eq2 = Equalizer(bars=5)
    moved_wobble = eq2.tick(None, peak=0.7, playing=True, t=1.0, dt=0.016)
    assert moved_wobble, "Wobble should produce movement"
    assert any(x > 0.0 for x in eq2.levels), "Wobble should produce non-zero bar levels"
    print(f"Wobble levels: {[round(x, 4) for x in eq2.levels]}")

    for _ in range(100):
        eq2.tick(None, peak=0.0, playing=False, t=2.0, dt=0.05)
    assert all(x < 0.01 for x in eq2.levels), "Bars should decay to rest when not playing"
    print("Decay to rest: All bars < 0.01.")
    print("All Equalizer tests passed successfully!")
