#!/usr/bin/env python3

from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional

logger = logging.getLogger(__name__)

class SystemInfo:
    __slots__ = ("cpu_percent", "ram_percent", "ram_used_gb", "ram_total_gb")

    def __init__(self, cpu_percent: int, ram_percent: int, ram_used_gb: float, ram_total_gb: float) -> None:
        self.cpu_percent: int = cpu_percent
        self.ram_percent: int = ram_percent
        self.ram_used_gb: float = ram_used_gb
        self.ram_total_gb: float = ram_total_gb

class SystemService:

    def __init__(
        self,
        on_changed: Optional[Callable[[SystemInfo], None]] = None,
        poll_interval: float = 1.8,
        auto_start: bool = True,
    ) -> None:
        self.poll_interval = max(0.5, float(poll_interval))
        self._lock = threading.RLock()
        self._on_changed = on_changed
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_cpu_times: Optional[tuple[float, float]] = None
        self._current_info: SystemInfo = SystemInfo(0, 0, 0.0, 0.0)

        # Initial sample
        self.sample()

        if auto_start:
            self.start()

    @property
    def current(self) -> SystemInfo:
        with self._lock:
            return self._current_info

    @property
    def cpu_percent(self) -> int:
        return self.current.cpu_percent

    @property
    def ram_percent(self) -> int:
        return self.current.ram_percent

    def sample(self) -> SystemInfo:
        cpu_pct = self._read_cpu_percent()
        ram_pct, used_gb, tot_gb = self._read_ram_info()
        info = SystemInfo(cpu_pct, ram_pct, used_gb, tot_gb)
        with self._lock:
            self._current_info = info
        return info

    def _read_cpu_percent(self) -> int:
        try:
            with open("/proc/stat", "r", encoding="utf-8") as f:
                fields = [float(x) for x in f.readline().split()[1:8]]
            idle = fields[3] + fields[4]
            total = sum(fields)
            if self._last_cpu_times is not None:
                prev_idle, prev_total = self._last_cpu_times
                delta_idle = idle - prev_idle
                delta_total = total - prev_total
                self._last_cpu_times = (idle, total)
                if delta_total > 0:
                    pct = int(round((1.0 - delta_idle / delta_total) * 100.0))
                    return max(0, min(100, pct))
            self._last_cpu_times = (idle, total)
            return 0
        except Exception as e:
            logger.debug("Failed reading CPU stats: %s", e)
            return 0

    def _read_ram_info(self) -> tuple[int, float, float]:
        try:
            with open("/proc/meminfo", "r", encoding="utf-8") as f:
                info = dict(line.split(":", 1) for line in f if ":" in line)
            tot_kb = float(info["MemTotal"].split()[0])
            avail_kb = float(info["MemAvailable"].split()[0])
            used_kb = max(0.0, tot_kb - avail_kb)
            pct = int(round((used_kb / tot_kb) * 100.0)) if tot_kb > 0 else 0
            used_gb = round(used_kb / (1024.0 * 1024.0), 1)
            tot_gb = round(tot_kb / (1024.0 * 1024.0), 1)
            return pct, used_gb, tot_gb
        except Exception as e:
            logger.debug("Failed reading RAM stats: %s", e)
            return 0, 0.0, 0.0

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(target=self._worker, daemon=True, name="system-monitor")
            self._thread.start()

    def stop(self) -> None:
        with self._lock:
            self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.5)

    def _worker(self) -> None:
        while self._running:
            info = self.sample()
            if self._on_changed:
                try:
                    self._on_changed(info)
                except Exception as e:
                    logger.debug("Error in system on_changed callback: %s", e)
            time.sleep(self.poll_interval)
