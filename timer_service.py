#!/usr/bin/env python3

from __future__ import annotations

import math
import time

class Countdown:

    def __init__(self, total_seconds: float = 0.0) -> None:
        self.total: float = max(0.0, float(total_seconds))
        self._left: float = self.total
        self.active: bool = False
        self.running: bool = False
        self.resumed_at: float = 0.0

    @property
    def left(self) -> float:
        if not self.active:
            return 0.0
        if self.running:
            elapsed = time.monotonic() - self.resumed_at
            rem = self._left - elapsed
            return max(0.0, rem)
        return max(0.0, self._left)

    @left.setter
    def left(self, value: float) -> None:
        self._left = max(0.0, float(value))
        self.resumed_at = time.monotonic()

    @property
    def remaining(self) -> float:
        return self.left

    @property
    def share(self) -> float:
        if self.total > 0.0 and self.active:
            return max(0.0, min(1.0, self.left / self.total))
        return 0.0

    @property
    def is_urgent(self) -> bool:
        return self.active and 0.0 < self.left <= 10.0

    @property
    def formatted(self) -> str:
        if self.active:
            secs = max(0, int(math.ceil(self.left)))
        elif self._left > 0.0:
            secs = max(0, int(math.ceil(self._left)))
        elif self.total > 0.0:
            secs = max(0, int(math.ceil(self.total)))
        else:
            secs = 0
        hours = secs // 3600
        minutes = (secs % 3600) // 60
        seconds = secs % 60
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    @property
    def formatted_human(self) -> str:
        if self.active:
            secs = max(0, int(math.ceil(self.left)))
        elif self._left > 0.0:
            secs = max(0, int(math.ceil(self._left)))
        elif self.total > 0.0:
            secs = max(0, int(math.ceil(self.total)))
        else:
            secs = 0
        hours = secs // 3600
        minutes = (secs % 3600) // 60
        s = secs % 60
        if hours > 0 and minutes > 0:
            return f"{hours} ч {minutes} мин"
        elif hours > 0:
            return f"{hours} ч"
        elif minutes > 0:
            return f"{minutes} мин"
        return f"{s} с"

    def start(self, total_seconds: float) -> None:
        secs = max(0.0, float(total_seconds))
        self.total = secs
        self._left = secs
        self.resumed_at = time.monotonic()
        self.active = True
        self.running = True

    def toggle(self) -> None:
        if not self.active:
            return
        if self.running:
            self._left = self.left
        else:
            self.resumed_at = time.monotonic()
        self.running = not self.running

    def stop(self) -> None:
        self.active = False
        self.running = False
        self._left = 0.0

    def add_minute(self, delta: int) -> None:
        secs = delta * 60.0
        if self.active:
            current = self.left
            new_left = max(0.0, current + secs)
            self._left = new_left
            self.resumed_at = time.monotonic()
            if new_left > self.total:
                self.total = new_left
            elif self.total + secs > 0:
                self.total = max(new_left, self.total + secs)
        else:
            base = self.total if self.total > 0.0 else 0.0
            new_total = max(60.0, base + secs)
            self.total = new_total
            self._left = new_total

    def tick(self) -> bool:
        if not self.active or not self.running:
            return False
        if self.left <= 0.0:
            self.stop()
            return True
        return False

TimerService = Countdown

if __name__ == "__main__":
    print("Testing timer_service.Countdown...")
    timer = Countdown()

    assert not timer.active
    assert not timer.running
    assert timer.left == 0.0
    assert timer.remaining == 0.0
    assert timer.share == 0.0
    assert not timer.is_urgent
    assert timer.formatted == "00:00"

    timer.start(65.0)
    assert timer.active
    assert timer.running
    assert 64.0 < timer.left <= 65.0
    assert timer.formatted == "01:05"
    assert not timer.is_urgent
    assert 0.99 <= timer.share <= 1.0

    timer.add_minute(1)
    assert 124.0 < timer.left <= 125.0
    assert timer.formatted == "02:05"

    timer.add_minute(-1)
    assert 64.0 < timer.left <= 65.0
    assert timer.formatted == "01:05"

    timer.toggle()
    assert not timer.running
    assert timer.active
    saved_left = timer.left
    time.sleep(0.05)
    assert timer.left == saved_left

    timer.toggle()
    assert timer.running

    timer.start(9.5)
    assert timer.is_urgent
    assert timer.formatted == "00:10"

    short_timer = Countdown()
    short_timer.start(0.1)
    assert not short_timer.tick()
    time.sleep(0.12)
    assert short_timer.tick()
    assert not short_timer.active
    assert not short_timer.tick()

    print("All timer_service tests passed successfully!")
