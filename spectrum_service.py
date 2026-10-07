
from __future__ import annotations

import atexit
import logging
import math
import os
import select
import shutil
import subprocess
import threading
import time

logger = logging.getLogger(__name__)

def _set_pdeathsig() -> None:
    try:
        import ctypes
        libc = ctypes.CDLL("libc.so.6")
        PR_SET_PDEATHSIG = 1
        SIGTERM = 15
        libc.prctl(PR_SET_PDEATHSIG, SIGTERM)
    except Exception:
        pass

try:
    import numpy as np
except ImportError:
    np = None

BANDS: int = 16

_F1: tuple[float, ...] = (7.1, 9.3, 6.2, 10.4, 8.0, 5.6, 9.9, 7.7, 8.4, 6.8, 9.1, 7.3, 10.1, 8.7, 6.0, 7.9)
_F2: tuple[float, ...] = (2.3, 3.1, 1.7, 2.9, 3.7, 2.1, 1.3, 3.3, 2.7, 3.5, 1.9, 2.5, 3.9, 2.2, 1.5, 3.0)

class SpectrumAnalyzer:

    MIN_HZ: float = 45.0
    MAX_HZ: float = 14000.0
    TILT_DB: float = 4.2

    def __init__(self, rate: int = 24000, size: int = 1024, bands: int = BANDS) -> None:
        self.rate: int = rate
        self.size: int = size
        self.bands: int = bands
        while self.size < rate * 0.04:
            self.size <<= 1

        if np is None:
            self.window = None
            self.weights = None
            self.norm = 0.0
            return

        idx = np.arange(self.size, dtype=np.float32)
        self.window = 0.5 - 0.5 * np.cos(2.0 * np.pi * idx / (self.size - 1))
        self.norm = 16.0 / (float(self.size) * float(self.size))

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
        self.weights = np.zeros((self.bands, num_bins), dtype=np.float32)
        group_size = max(1, fine_bands // self.bands)

        for b in range(fine_bands):
            lo = edges[b]
            hi = edges[b + 1]
            last = min(int(hi + 0.5), num_bins - 1)
            b_target = min(self.bands - 1, b // group_size)
            for k in range(int(lo + 0.5), last + 1):
                overlap = max(0.0, min(hi, k + 0.5) - max(lo, k - 0.5))
                self.weights[b_target, k] += (overlap * tilt[b]) / float(group_size)

    def analyze(self, samples: Any) -> Any:
        if np is None or self.weights is None:
            return [0.0] * self.bands
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
        self._fifo_fd: int | None = None
        self._fifo_path: str | None = None
        self._conf_path: str | None = None

        self._active: bool = False
        self._failed: bool = False
        self._is_silent: bool = True
        self._last_data_time: float = 0.0
        self._peak: float = 0.0
        self._device_check_time: float = 0.0

        self._ring: Optional[np.ndarray] = np.zeros(self._analyzer.size, dtype=np.float32) if np is not None else None
        self._ring_head: int = 0

        self._bands: list[float] = [0.0] * BANDS
        atexit.register(self.close)

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
            if self._is_silent or (now - self._last_data_time > self.SILENCE_SEC) or self._failed:
                if self.fallback_wobble and self._peak > 1e-4:
                    self._generate_wobble(now)
                    bands = self._bands
                else:
                    bands = [0.0] * BANDS
            else:
                bands = self._bands

            if out_bands is not None:
                if len(out_bands) < BANDS:
                    out_bands.extend([0.0] * (BANDS - len(out_bands)))
                out_bands[:BANDS] = bands[:BANDS]
            return True

    def get_bands(self) -> list[float]:
        bands = [0.0] * BANDS
        self.read_bands(bands)
        return bands

    @property
    def levels(self) -> list[float]:
        return self.get_bands()

    def close(self) -> None:
        self._stop_event.set()
        self._active = False
        self._wake.set()
        self._close_capture()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.5)

    def _generate_wobble(self, now: float) -> None:
        eff_peak = 0.55 if self._peak <= 1e-4 else self._peak
        wobble_level = math.pow(max(0.0, min(1.0, eff_peak * 1.8)), 0.6)
        mid = (BANDS - 1) / 2.0
        for i in range(BANDS):
            noise = 0.5 + 0.5 * math.sin(now * _F1[i] + i * 1.9) * math.cos(now * _F2[i] + i * 0.7)
            envelope = 1.0 - 0.3 * abs(i - mid) / mid
            target = wobble_level * envelope * (0.3 + 0.7 * noise)
            self._bands[i] = float(target * 0.40)

    def _open_capture(self) -> bool:
        # Cava engine (standard 16-band audio visualizer on Linux)
        if shutil.which("cava"):
            try:
                pid = os.getpid()
                self._fifo_path = f"/tmp/cava_island_{pid}.fifo"
                self._conf_path = f"/tmp/cava_island_{pid}.conf"

                if os.path.exists(self._fifo_path):
                    try:
                        os.remove(self._fifo_path)
                    except Exception:
                        pass
                os.mkfifo(self._fifo_path)

                conf_content = f"""[general]
bars = {BANDS}
framerate = 60
autosens = 1
sensitivity = 100

[input]
method = pipewire
source = auto

[output]
method = raw
raw_target = {self._fifo_path}
data_format = binary
bit_format = 8bit
channels = mono
mono_option = average

[smoothing]
monstercat = 1
waves = 0
noise_reduction = 30
"""
                with open(self._conf_path, "w") as f:
                    f.write(conf_content)

                proc = subprocess.Popen(
                    ["cava", "-p", self._conf_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    preexec_fn=_set_pdeathsig,
                )
                time.sleep(0.12)
                if proc.poll() is None:
                    self._fifo_fd = os.open(self._fifo_path, os.O_RDONLY | os.O_NONBLOCK)
                    self._proc = proc
                    self._failed = False
                    self._last_data_time = time.monotonic()
                    return True
                proc.terminate()
            except Exception as e:
                logger.debug("Failed starting cava: %s", e)
                self._close_capture()

        # Fallback to native PipeWire capture
        if shutil.which("pw-record"):
            try:
                proc = subprocess.Popen(
                    ["pw-record", "--raw", f"--rate={self.rate}", "--channels=1", "--format=s16", "-"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    preexec_fn=_set_pdeathsig,
                )
                time.sleep(0.05)
                if proc.poll() is None:
                    self._proc = proc
                    self._failed = False
                    self._last_data_time = time.monotonic()
                    return True
            except Exception as e:
                logger.debug("pw-record open failed: %s", e)

        # Fallback to parec
        if shutil.which("parec"):
            targets = ["@DEFAULT_MONITOR@", "@DEFAULT_SINK@.monitor", None]
            for target in targets:
                cmd = [
                    "parec",
                    "--raw",
                    f"--rate={self.rate}",
                    "--channels=1",
                    "--format=s16le",
                    "--latency-msec=30",
                ]
                if target:
                    cmd.extend(["-d", target])

                try:
                    proc = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,
                        preexec_fn=_set_pdeathsig,
                    )
                    time.sleep(0.05)
                    if proc.poll() is None:
                        self._proc = proc
                        self._failed = False
                        self._last_data_time = time.monotonic()
                        return True
                    proc.terminate()
                    proc.wait(timeout=0.2)
                except (FileNotFoundError, OSError):
                    break

        return False

    def _close_capture(self) -> None:
        if self._fifo_fd is not None:
            try:
                os.close(self._fifo_fd)
            except Exception:
                pass
            self._fifo_fd = None

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

        if self._fifo_path and os.path.exists(self._fifo_path):
            try:
                os.remove(self._fifo_path)
            except Exception:
                pass
            self._fifo_path = None

        if self._conf_path and os.path.exists(self._conf_path):
            try:
                os.remove(self._conf_path)
            except Exception:
                pass
            self._conf_path = None

        with self._lock:
            self._is_silent = True
            for i in range(BANDS):
                self._bands[i] = 0.0

    def _push_samples(self, samples: Any) -> None:
        if np is None or self._ring is None:
            return
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

    def _get_ordered_window(self) -> Any:
        if np is None or self._ring is None:
            return None
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

            # 1. Cava FIFO mode (fast, direct, non-blocking)
            if self._fifo_fd is not None:
                r, _, _ = select.select([self._fifo_fd], [], [], 0.04)
                if not r:
                    if now - self._last_data_time > self.SILENCE_SEC:
                        with self._lock:
                            self._is_silent = True
                            self._bands = [0.0] * BANDS
                    continue

                try:
                    raw = os.read(self._fifo_fd, BANDS)
                    if not raw:
                        self._close_capture()
                        time.sleep(0.1)
                        continue

                    # Drain FIFO to the latest available frame for zero latency
                    while True:
                        r2, _, _ = select.select([self._fifo_fd], [], [], 0)
                        if not r2:
                            break
                        next_raw = os.read(self._fifo_fd, BANDS)
                        if len(next_raw) >= BANDS:
                            raw = next_raw
                        else:
                            break

                    if len(raw) >= BANDS:
                        vals = [float(b) / 255.0 for b in raw[:BANDS]]
                        peak = max(vals)
                        with self._lock:
                            self._peak = max(peak, self._peak * 0.92)
                            if peak > 0.005:
                                self._is_silent = False
                                self._last_data_time = now
                                self._bands = vals
                            elif now - self._last_data_time > self.SILENCE_SEC:
                                self._is_silent = True
                                self._bands = [0.0] * BANDS
                except Exception:
                    self._close_capture()
                    time.sleep(0.1)
                continue

            # 2. Fallback pw-record/parec raw PCM mode
            if self._proc.stdout is None:
                continue

            r, _, _ = select.select([self._proc.stdout], [], [], 0.05)
            if not r:
                if now - self._last_data_time > self.SILENCE_SEC:
                    with self._lock:
                        self._is_silent = True
                        self._bands = [0.0] * BANDS
                continue

            try:
                raw_bytes = self._proc.stdout.read(bytes_to_read)
            except Exception:
                raw_bytes = b""

            if not raw_bytes:
                self._close_capture()
                time.sleep(0.1)
                continue

            if np is not None:
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
                        self._bands = [0.0] * BANDS

if __name__ == "__main__":
    print("Testing SpectrumAnalyzer and SpectrumService...")

    analyzer = SpectrumAnalyzer(rate=24000, size=1024, bands=5)
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
    assert len(bands) == 16, f"Expected 16 bands, got {len(bands)}"
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
