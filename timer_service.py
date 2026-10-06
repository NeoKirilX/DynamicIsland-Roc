#!/usr/bin/env python3

from __future__ import annotations

import math
import time
from enum import Enum


class TimerState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    EXPIRED = "expired"


class Countdown:
    """Bulletproof precision countdown timer engine.

    Uses monotonic timestamps to prevent clock drift, handles seamless
    pause/resume, dynamic time additions (+1m / +5m / -1m), and clean
    progress ring calculation without jumps or distortion.
    """

    def __init__(self, total_seconds: float = 0.0) -> None:
        self.initial_total: float = max(0.0, float(total_seconds))
        self.total: float = self.initial_total
        self.state: TimerState = TimerState.IDLE
        self._end_time: float = 0.0
        self._frozen_left: float = 0.0

    @property
    def active(self) -> bool:
        return self.state in (TimerState.RUNNING, TimerState.PAUSED)

    @property
    def running(self) -> bool:
        return self.state == TimerState.RUNNING

    @property
    def is_paused(self) -> bool:
        return self.state == TimerState.PAUSED

    @property
    def left(self) -> float:
        if self.state == TimerState.RUNNING:
            rem = self._end_time - time.monotonic()
            return max(0.0, rem)
        elif self.state == TimerState.PAUSED:
            return max(0.0, self._frozen_left)
        return 0.0

    @left.setter
    def left(self, value: float) -> None:
        val = max(0.0, float(value))
        if self.state == TimerState.RUNNING:
            self._end_time = time.monotonic() + val
        else:
            self._frozen_left = val
        if val > self.total:
            self.total = val

    @property
    def remaining(self) -> float:
        return self.left

    @property
    def elapsed(self) -> float:
        if self.total <= 0.0:
            return 0.0
        return max(0.0, self.total - self.left)

    @property
    def share(self) -> float:
        """Fraction of time remaining (1.0 at start -> 0.0 at end)."""
        if self.total > 0.0 and self.active:
            return max(0.0, min(1.0, self.left / self.total))
        return 0.0

    @property
    def is_urgent(self) -> bool:
        """True when timer has 10 seconds or less remaining."""
        return self.active and 0.0 < self.left <= 10.0

    @property
    def formatted(self) -> str:
        """Standard digital display format (MM:SS or HH:MM:SS)."""
        secs = max(0, int(math.ceil(self.left))) if self.active else max(0, int(math.ceil(self.total)))
        hours = secs // 3600
        minutes = (secs % 3600) // 60
        seconds = secs % 60
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    @property
    def formatted_human(self) -> str:
        """Natural language formatted string ('1 ч 15 мин', '5 мин 20 с')."""
        secs = max(0, int(math.ceil(self.left))) if self.active else max(0, int(math.ceil(self.total)))
        hours = secs // 3600
        minutes = (secs % 3600) // 60
        s = secs % 60
        if hours > 0 and minutes > 0:
            return f"{hours} ч {minutes} мин"
        elif hours > 0:
            return f"{hours} ч"
        elif minutes > 0 and s > 0:
            return f"{minutes} мин {s} с"
        elif minutes > 0:
            return f"{minutes} мин"
        return f"{s} с"

    def start(self, total_seconds: float) -> None:
        """Start countdown with given duration in seconds."""
        secs = max(0.0, float(total_seconds))
        self.initial_total = secs
        self.total = secs
        self._end_time = time.monotonic() + secs
        self._frozen_left = secs
        self.state = TimerState.RUNNING

    def toggle(self) -> None:
        """Toggle between Running and Paused."""
        if self.state == TimerState.RUNNING:
            self._frozen_left = max(0.0, self._end_time - time.monotonic())
            self.state = TimerState.PAUSED
        elif self.state == TimerState.PAUSED:
            self._end_time = time.monotonic() + self._frozen_left
            self.state = TimerState.RUNNING

    def pause(self) -> None:
        if self.state == TimerState.RUNNING:
            self._frozen_left = max(0.0, self._end_time - time.monotonic())
            self.state = TimerState.PAUSED

    def resume(self) -> None:
        if self.state == TimerState.PAUSED:
            self._end_time = time.monotonic() + self._frozen_left
            self.state = TimerState.RUNNING

    def reset(self) -> None:
        """Reset back to the original configured duration."""
        if self.initial_total > 0:
            self.start(self.initial_total)

    def stop(self) -> None:
        """Stop and reset timer to idle."""
        self.state = TimerState.IDLE
        self._end_time = 0.0
        self._frozen_left = 0.0

    def add_seconds(self, delta_secs: float) -> None:
        """Add or subtract seconds on the fly."""
        if not self.active:
            base = self.total if self.total > 0.0 else 0.0
            new_tot = max(1.0, base + delta_secs)
            self.initial_total = new_tot
            self.total = new_tot
            return

        if self.state == TimerState.RUNNING:
            cur_left = max(0.0, self._end_time - time.monotonic())
            new_left = max(0.0, cur_left + delta_secs)
            self._end_time = time.monotonic() + new_left
        else:
            new_left = max(0.0, self._frozen_left + delta_secs)
            self._frozen_left = new_left

        if delta_secs > 0:
            self.total += delta_secs
        else:
            self.total = max(new_left, self.total + delta_secs)

    def add_minute(self, delta: int) -> None:
        """Add or subtract whole minutes."""
        self.add_seconds(float(delta) * 60.0)

    def tick(self) -> bool:
        """Called on frame/interval tick. Returns True when timer completes."""
        if self.state == TimerState.RUNNING:
            if time.monotonic() >= self._end_time:
                self.state = TimerState.EXPIRED
                self._end_time = 0.0
                self._frozen_left = 0.0
                return True
        return False


TimerService = Countdown

if __name__ == "__main__":
    print("Testing rewritten timer_service.Countdown...")
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
    assert 0.98 <= timer.share <= 1.0

    timer.add_minute(1)
    assert 124.0 < timer.left <= 125.0
    assert timer.formatted == "02:05"

    timer.add_minute(-1)
    assert 64.0 < timer.left <= 65.0
    assert timer.formatted == "01:05"

    # Test precise pausing
    timer.toggle()
    assert not timer.running
    assert timer.is_paused
    assert timer.active
    saved_left = timer.left
    time.sleep(0.05)
    assert timer.left == saved_left

    # Adding time while paused
    timer.add_seconds(30.0)
    assert abs(timer.left - (saved_left + 30.0)) < 0.01

    timer.toggle()
    assert timer.running

    # Urgency check
    timer.start(9.5)
    assert timer.is_urgent
    assert timer.formatted == "00:10"

    # Expiry tick
    short_timer = Countdown()
    short_timer.start(0.1)
    assert not short_timer.tick()
    time.sleep(0.12)
    assert short_timer.tick()
    assert short_timer.state == TimerState.EXPIRED
    assert not short_timer.active
    assert not short_timer.tick()

    print("All timer_service tests passed successfully!")
