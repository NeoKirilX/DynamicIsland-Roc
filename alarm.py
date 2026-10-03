#!/usr/bin/env python3

from __future__ import annotations

import logging
import math
import os
import shutil
import struct
import subprocess
import threading
import time
import wave
from typing import Optional

try:
    from .timer_service import Countdown
except ImportError:
    from timer_service import Countdown

logger = logging.getLogger(__name__)

SOUND_CANDIDATES = (
    "/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga",
    "/usr/share/sounds/freedesktop/stereo/bell.oga",
    "/usr/share/sounds/freedesktop/stereo/complete.oga",
    "/usr/share/sounds/freedesktop/stereo/message.oga",
)
FALLBACK_WAV_PATH = "/tmp/dynamic_island_alarm_fallback.wav"

def _generate_fallback_wav(path: str = FALLBACK_WAV_PATH) -> str:
    try:
        if os.path.exists(path) and os.path.getsize(path) > 0:
            return path
        sample_rate = 44100
        duration = 0.35
        num_samples = int(sample_rate * duration)
        with wave.open(path, "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            raw = bytearray()
            for i in range(num_samples):
                t = i / sample_rate
                freq = 880.0 if t < 0.18 else 1174.66
                envelope = max(0.0, 1.0 - (t % 0.18) / 0.18)
                val = int(32767.0 * 0.4 * envelope * math.sin(2.0 * math.pi * freq * t))
                raw.extend(struct.pack("<h", val))
            wf.writeframes(raw)
        return path
    except Exception as e:
        logger.error("Failed to generate fallback wav: %s", e)
        return ""

def find_sound_file(custom_path: Optional[str] = None) -> str:
    if custom_path and os.path.isfile(custom_path) and os.access(custom_path, os.R_OK):
        return custom_path

    for candidate in SOUND_CANDIDATES:
        if os.path.isfile(candidate) and os.access(candidate, os.R_OK):
            return candidate

    return _generate_fallback_wav()

def find_audio_player() -> Optional[str]:
    for player in ("pw-play", "paplay", "gst-play-1.0", "aplay"):
        path = shutil.which(player)
        if path:
            return path
    return None

class Alarm:

    def __init__(self, sound_path: Optional[str] = None) -> None:
        self._custom_sound: Optional[str] = sound_path
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._proc: Optional[subprocess.Popen] = None
        self._is_ringing: bool = False

    @property
    def is_ringing(self) -> bool:
        return self._is_ringing

    def ring(self) -> None:
        self.stop()

        sound_file = find_sound_file(self._custom_sound)
        player = find_audio_player()
        if not sound_file or not player:
            logger.warning(
                "Cannot start alarm: sound_file=%s, player=%s", sound_file, player
            )
            return

        self._stop_event.clear()
        self._is_ringing = True
        self._thread = threading.Thread(
            target=self._loop_worker,
            args=(player, sound_file),
            name="AlarmPlaybackThread",
            daemon=True,
        )
        self._thread.start()

    def _loop_worker(self, player: str, sound_file: str) -> None:
        cmd = [player]
        if os.path.basename(player) == "pw-play":
            cmd.extend(["--media-role=Alarm", "--media-category=Playback"])
        cmd.append(sound_file)

        while not self._stop_event.is_set():
            try:
                with self._lock:
                    if self._stop_event.is_set():
                        break
                    self._proc = subprocess.Popen(
                        cmd,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )

                while not self._stop_event.is_set():
                    ret = self._proc.poll()
                    if ret is not None:
                        break
                    time.sleep(0.03)

            except Exception as e:
                logger.error("Error during alarm playback: %s", e)
                break
            finally:
                with self._lock:
                    if self._proc is not None:
                        try:
                            if self._proc.poll() is None:
                                self._proc.terminate()
                                self._proc.wait(timeout=0.2)
                        except Exception:
                            pass
                        self._proc = None

            if not self._stop_event.is_set():
                self._stop_event.wait(timeout=0.15)

        self._is_ringing = False

    def stop(self) -> None:
        self._stop_event.set()
        with self._lock:
            if self._proc is not None:
                try:
                    if self._proc.poll() is None:
                        self._proc.terminate()
                        try:
                            self._proc.wait(timeout=0.2)
                        except subprocess.TimeoutExpired:
                            self._proc.kill()
                except Exception:
                    pass
                self._proc = None
        self._is_ringing = False
        if self._thread is not None and self._thread.is_alive():
            if threading.current_thread() != self._thread:
                self._thread.join(timeout=0.5)
            self._thread = None

if __name__ == "__main__":
    print("Testing alarm.Alarm & timer_service integration...")

    alarm = Alarm()
    assert not alarm.is_ringing
    sound = find_sound_file()
    player = find_audio_player()
    print(f"Alarm sound file resolved: {sound}")
    print(f"Audio player resolved: {player}")
    assert sound and os.path.exists(sound)
    assert player and shutil.which(player)

    print("Testing ring() and stop()...")
    alarm.ring()
    assert alarm.is_ringing
    time.sleep(0.3)
    alarm.stop()
    assert not alarm.is_ringing
    print("Alarm ring/stop verified successfully.")

    print("Testing Countdown integration with Alarm...")
    countdown = Countdown()
    countdown.start(0.2)
    assert countdown.active
    assert countdown.running
    print(
        f"Timer started: formatted='{countdown.formatted}', urgent={countdown.is_urgent}"
    )
    assert countdown.formatted == "00:01" or countdown.formatted == "00:00"

    expired = False
    for _ in range(30):
        if countdown.tick():
            expired = True
            alarm.ring()
            break
        time.sleep(0.02)

    assert expired, "Countdown should have expired!"
    assert alarm.is_ringing, "Alarm should be ringing upon timer expiration!"
    print(f"Timer expired! Alarm ringing: {alarm.is_ringing}")

    time.sleep(0.3)
    alarm.stop()
    assert not alarm.is_ringing
    print("Alarm silenced successfully.")

    print("All tests in alarm.py passed successfully!")
