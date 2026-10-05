#!/usr/bin/env python3

from __future__ import annotations

import logging
import math
import os
import shutil
import struct
import subprocess
import threading
import wave
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

CACHE_DIR = Path.home() / ".cache" / "dynamic-island" / "sounds"
SAMPLE_RATE = 44100

class SoundService:
    _instance: Optional[SoundService] = None

    @classmethod
    def get(cls) -> SoundService:
        if cls._instance is None:
            cls._instance = SoundService()
        return cls._instance

    def __init__(self) -> None:
        self._sound_paths: dict[str, str] = {}
        self._init_sounds()

    def _init_sounds(self) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            self._ensure_chime("charging", [(523.25, 0.12), (659.25, 0.12), (783.99, 0.22)])
            self._ensure_chime("unplugged", [(659.25, 0.10), (523.25, 0.18)])
            self._ensure_chime("battery_low", [(440.0, 0.14), (392.0, 0.25)])
            self._ensure_chime("battery_critical", [(880.0, 0.10), (0.0, 0.05), (880.0, 0.18)])
            self._ensure_chime("battery_full", [(523.25, 0.10), (659.25, 0.10), (783.99, 0.10), (1046.50, 0.28)])
        except Exception as e:
            logger.debug("Failed initializing custom sounds: %s", e)

    def _ensure_chime(self, name: str, notes: list[tuple[float, float]]) -> None:
        wav_path = CACHE_DIR / f"{name}.wav"
        if not wav_path.exists():
            with wave.open(str(wav_path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(SAMPLE_RATE)
                for freq, dur in notes:
                    num_samples = int(SAMPLE_RATE * dur)
                    for i in range(num_samples):
                        t = i / float(SAMPLE_RATE)
                        if freq > 1.0:
                            env = math.exp(-3.5 * (t / dur))
                            val = int(32767.0 * 0.40 * env * math.sin(2.0 * math.pi * freq * t))
                        else:
                            val = 0
                        wf.writeframes(struct.pack("<h", max(-32768, min(32767, val))))
        self._sound_paths[name] = str(wav_path)

    def play(self, sound_name: str) -> None:
        threading.Thread(target=self._play_worker, args=(sound_name,), daemon=True).start()

    def _play_worker(self, sound_name: str) -> None:
        try:
            # 1. Check system sounds if available
            system_sound = self._find_system_sound(sound_name)
            target = system_sound or self._sound_paths.get(sound_name)
            if not target or not os.path.exists(target):
                return

            if shutil.which("pw-play"):
                subprocess.run(["pw-play", target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2.5)
            elif shutil.which("paplay"):
                subprocess.run(["paplay", target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2.5)
            elif shutil.which("aplay"):
                subprocess.run(["aplay", "-q", target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2.5)
            elif shutil.which("canberra-gtk-play"):
                event_map = {
                    "charging": "device-added",
                    "unplugged": "device-removed",
                    "battery_low": "dialog-warning",
                    "battery_critical": "suspend-error",
                    "battery_full": "complete",
                }
                ev = event_map.get(sound_name)
                if ev:
                    subprocess.run(["canberra-gtk-play", "-i", ev], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2.5)
        except Exception as exc:
            logger.debug("Error playing sound %s: %s", sound_name, exc)

    def _find_system_sound(self, name: str) -> Optional[str]:
        candidates: dict[str, list[str]] = {
            "battery_low": [
                "/usr/share/sounds/ocean/stereo/battery-low.oga",
                "/usr/share/sounds/freedesktop/stereo/dialog-warning.oga",
            ],
            "battery_critical": [
                "/usr/share/sounds/ocean/stereo/battery-caution.oga",
                "/usr/share/sounds/freedesktop/stereo/suspend-error.oga",
            ],
            "battery_full": [
                "/usr/share/sounds/ocean/stereo/battery-full.oga",
                "/usr/share/sounds/freedesktop/stereo/complete.oga",
            ],
            "charging": [
                "/usr/share/sounds/freedesktop/stereo/device-added.oga",
            ],
            "unplugged": [
                "/usr/share/sounds/freedesktop/stereo/device-removed.oga",
            ],
        }
        for path in candidates.get(name, []):
            if os.path.exists(path):
                return path
        return None

def play_sound(sound_name: str) -> None:
    SoundService.get().play(sound_name)
