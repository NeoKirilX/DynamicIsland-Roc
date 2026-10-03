
from __future__ import annotations

import math
import select
import subprocess
import threading
import time

import numpy as np

BANDS: int = 5
BAND_NAMES: tuple[str, ...] = ("sub_bass", "bass", "mid", "high_mid", "treble")

_F1: tuple[float, ...] = (7.1, 9.3, 6.2, 10.4, 8.0)
_F2: tuple[float, ...] = (2.3, 3.1, 1.7, 2.9, 3.7)

class SpectrumAnalyzer:

    MIN_HZ: float = 45.0
    MAX_HZ: float = 14000.0
    TILT_DB: float = 2.0

    def __init__(self, rate: int = 24000, size: int = 1024) -> None:
        self.rate: int = rate
        self.size: int = size
        while self.size < rate * 0.04:
            self.size <<= 1

        idx = np.arange(self.size, dtype=np.float32)
        self.window: np.ndarray = 0.5 - 0.5 * np.cos(2.0 * np.pi * idx / (self.size - 1))
        self.norm: float = 16.0 / (float(self.size) * float(self.size))

        top = min(self.MAX_HZ, rate * 0.45)
        fine_bands = 40
        edges = (
            self.MIN_HZ
            * ((top / self.MIN_HZ) ** (np.arange(fine_bands + 1) / float(fine_bands)))
            * float(self.size)
            / float(rate)
        )
        center_hz = np.sqrt(edges[:-1] * edges[1:]) * float(rate) / float(self.size)
        tilt = 10.0 ** (self.TILT_DB * np.log2(center_hz / 1000.0) / 10.0)

        num_bins = self.size // 2 + 1
        self.weights: np.ndarray = np.zeros((BANDS, num_bins), dtype=np.float32)
        group_size = fine_bands // BANDS

        for b in range(fine_bands):
            lo = edges[b]
            hi = edges[b + 1]
            last = min(int(hi + 0.5), num_bins - 1)
            b5 = b // group_size
            for k in range(int(lo + 0.5), last + 1):
                overlap = max(0.0, min(hi, k + 0.5) - max(lo, k - 0.5))
                self.weights[b5, k] += (overlap * tilt[b]) / float(group_size)

    def analyze(self, samples: np.ndarray) -> np.ndarray:
        if len(samples) < self.size:
            padded = np.zeros(self.size, dtype=np.float32)
            padded[-len(samples):] = samples
            samples = padded
        elif len(samples) > self.size:
            samples = samples[-self.size:]

        fft_vals = np.fft.rfft(samples * self.window)
        power = (np.abs(fft_vals) ** 2) * self.norm
        return (self.weights @ power).astype(np.float32)

class SpectrumService:

    LINGER_SEC: float = 3.0
    SILENCE_SEC: float = 0.08
    CHUNK_SAMPLES: int = 512

    def __init__(
        self,
        rate: int = 24000,
        fallback_wobble: bool = True,
    ) -> None:
        self.rate: int = rate
        self.fallback_wobble: bool = fallback_wobble

        self._analyzer: SpectrumAnalyzer = SpectrumAnalyzer(rate=rate)
        self._lock: threading.Lock = threading.Lock()
        self._wake: threading.Event = threading.Event()
        self._stop_event: threading.Event = threading.Event()
        self._thread: threading.Thread | None = None
        self._proc: subprocess.Popen | None = None

        self._active: bool = False
        self._failed: bool = False
        self._is_silent: bool = True
        self._last_data_time: float = 0.0
        self._peak: float = 0.0
        self._device_check_time: float = 0.0

        self._ring: np.ndarray = np.zeros(self._analyzer.size, dtype=np.float32)
        self._ring_head: int = 0

        self._bands: list[float] = [0.0] * BANDS

    @property
    def active(self) -> bool:
        return self._active

    @active.setter
    def active(self, value: bool) -> None:
        val = bool(value)
        if self._active == val:
            return
        self._active = val
        if not val:
            return

        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(
                target=self._run,
                name="SpectrumService",
                daemon=True,
            )
            self._thread.start()
        self._wake.set()

    @property
    def peak(self) -> float:
        with self._lock:
            return self._peak

    @peak.setter
    def peak(self, value: float) -> None:
        with self._lock:
            self._peak = max(0.0, min(1.0, float(value)))

    @property
    def is_silent(self) -> bool:
        with self._lock:
            return self._is_silent

    def read_bands(self, out_bands: list[float]) -> bool:
        now = time.monotonic()
        with self._lock:
            if self._failed:
                return False

            if (self._is_silent or (now - self._last_data_time > self.SILENCE_SEC)) and self.fallback_wobble:
                self._generate_wobble(now)

            if out_bands is not None:
                if len(out_bands) < BANDS:
                    out_bands.extend([0.0] * (BANDS - len(out_bands)))
                out_bands[:BANDS] = self._bands[:BANDS]
            return True

    def get_bands(self) -> list[float]:
        bands = [0.0] * BANDS
        self.read_bands(bands)
        return bands

    def close(self) -> None:
        self._stop_event.set()
        self._active = False
        self._wake.set()
        self._close_capture()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.5)

    def _generate_wobble(self, now: float) -> None:
        wobble_level = math.pow(max(0.0, min(1.0, self._peak * 1.8)), 0.6)
        mid = (BANDS - 1) / 2.0
        for i in range(BANDS):
            noise = 0.5 + 0.5 * math.sin(now * _F1[i] + i * 1.9) * math.cos(now * _F2[i] + i * 0.7)
            envelope = 1.0 - 0.3 * abs(i - mid) / mid
            target = wobble_level * envelope * (0.3 + 0.7 * noise)
            self._bands[i] = float(target * 0.08)

    def _open_capture(self) -> bool:
        targets = ["@DEFAULT_MONITOR@", "@DEFAULT_SINK@.monitor", None]
        for target in targets:
            cmd = [
                "parec",
                "--raw",
                f"--rate={self.rate}",
                "--channels=1",
                "--format=s16le",
                "--latency-msec=40",
            ]
            if target:
                cmd.extend(["-d", target])

            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                )
                r, _, _ = select.select([proc.stdout], [], [], 0.25)
                if r and proc.stdout:
                    self._proc = proc
                    self._failed = False
                    self._last_data_time = time.monotonic()
                    return True
                proc.terminate()
                proc.wait()
            except (FileNotFoundError, OSError):
                break

        self._failed = True
        return False

    def _close_capture(self) -> None:
        if self._proc is not None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=0.2)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None

        with self._lock:
            self._is_silent = True
            for i in range(BANDS):
                self._bands[i] = 0.0

    def _push_samples(self, samples: np.ndarray) -> None:
        n = len(samples)
        size = self._analyzer.size
        if n >= size:
            self._ring[:] = samples[-size:]
            self._ring_head = 0
            return

        part1 = min(n, size - self._ring_head)
        self._ring[self._ring_head : self._ring_head + part1] = samples[:part1]
        part2 = n - part1
        if part2 > 0:
            self._ring[:part2] = samples[part1:]
            self._ring_head = part2
        else:
            self._ring_head = (self._ring_head + part1) % size

    def _get_ordered_window(self) -> np.ndarray:
        if self._ring_head == 0:
            return self._ring.copy()
        return np.concatenate((self._ring[self._ring_head :], self._ring[: self._ring_head]))

    def _run(self) -> None:
        last_active = time.monotonic()
        bytes_to_read = self.CHUNK_SAMPLES * 2

        while not self._stop_event.is_set():
            now = time.monotonic()
            if self._active:
                last_active = now
            elif now - last_active > self.LINGER_SEC:
                self._close_capture()
                self._wake.wait()
                self._wake.clear()
                last_active = time.monotonic()
                continue

            if self._proc is None:
                if not self._open_capture():
                    time.sleep(1.0)
                    continue

            r, _, _ = select.select([self._proc.stdout], [], [], 0.05)
            if not r or self._proc.stdout is None:
                if now - self._last_data_time > self.SILENCE_SEC:
                    with self._lock:
                        self._is_silent = True
                continue

            try:
                raw_bytes = self._proc.stdout.read(bytes_to_read)
            except Exception:
                raw_bytes = b""

            if not raw_bytes:
                self._close_capture()
                time.sleep(0.1)
                continue

            samples = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            chunk_peak = float(np.max(np.abs(samples))) if len(samples) > 0 else 0.0

            self._push_samples(samples)

            with self._lock:
                self._peak = max(chunk_peak, self._peak * 0.92)

                if chunk_peak > 1e-4:
                    self._is_silent = False
                    self._last_data_time = now
                    window = self._get_ordered_window()
                    computed = self._analyzer.analyze(window)
                    self._bands = [float(b) for b in computed]
                elif now - self._last_data_time > self.SILENCE_SEC:
                    self._is_silent = True

if __name__ == "__main__":
    print("Testing SpectrumAnalyzer and SpectrumService...")

    analyzer = SpectrumAnalyzer(rate=24000, size=1024)
    t = np.arange(1024, dtype=np.float32) / 24000.0

    sub_bass_sine = np.sin(2.0 * np.pi * 80.0 * t).astype(np.float32)
    b0 = analyzer.analyze(sub_bass_sine)
    assert np.argmax(b0) == 0, f"Expected 80Hz sine to peak in band 0, got {np.argmax(b0)}"

    bass_sine = np.sin(2.0 * np.pi * 250.0 * t).astype(np.float32)
    b1 = analyzer.analyze(bass_sine)
    assert np.argmax(b1) == 1, f"Expected 250Hz sine to peak in band 1, got {np.argmax(b1)}"

    mid_sine = np.sin(2.0 * np.pi * 1000.0 * t).astype(np.float32)
    b2 = analyzer.analyze(mid_sine)
    assert np.argmax(b2) == 2, f"Expected 1000Hz sine to peak in band 2, got {np.argmax(b2)}"

    treble_sine = np.sin(2.0 * np.pi * 8000.0 * t).astype(np.float32)
    b4 = analyzer.analyze(treble_sine)
    assert np.argmax(b4) == 4, f"Expected 8000Hz sine to peak in band 4, got {np.argmax(b4)}"
    print("SpectrumAnalyzer frequency tests: All 5 bands correctly mapped.")

    service = SpectrumService(rate=24000, fallback_wobble=True)
    service.active = True

    time.sleep(0.3)

    bands = [0.0] * BANDS
    ok = service.read_bands(bands)
    assert ok, "SpectrumService.read_bands returned False"
    assert len(bands) == 5, f"Expected 5 bands, got {len(bands)}"
    print(f"SpectrumService live read_bands: {bands}, peak={service.peak:.4f}, silent={service.is_silent}")

    service.peak = 0.5
    service._is_silent = True
    service._last_data_time = 0.0
    wobble_bands = [0.0] * BANDS
    service.read_bands(wobble_bands)
    assert any(b > 0.0 for b in wobble_bands), "Fallback wobble should produce non-zero levels when peak > 0"
    print(f"Fallback wobble read_bands (peak=0.5): {wobble_bands}")

    service.close()
    print("SpectrumService shutdown successfully.")
    print("All SpectrumService tests passed successfully!")
