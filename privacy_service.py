#!/usr/bin/env python3

from __future__ import annotations

import glob
import logging
import os
import re
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class PrivacyState:
    mic_active: bool = False
    camera_active: bool = False
    mic_apps: tuple[str, ...] = ()
    camera_apps: tuple[str, ...] = ()

    @property
    def active(self) -> bool:
        return self.mic_active or self.camera_active

    @property
    def summary(self) -> str:
        if self.camera_active and self.mic_active:
            return "Камера и микрофон"
        if self.camera_active:
            return "Камера"
        if self.mic_active:
            return "Микрофон"
        return ""

    @property
    def primary_app(self) -> str:
        if self.camera_active and self.camera_apps:
            return self.camera_apps[0]
        if self.mic_active and self.mic_apps:
            return self.mic_apps[0]
        return ""


def _check_alsa_pcm_capture() -> bool:
    try:
        paths = glob.glob("/proc/asound/card*/pcm*c/sub*/status")
        for p in paths:
            try:
                with open(p, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read(256)
                    if "state: RUNNING" in content:
                        return True
            except (OSError, FileNotFoundError):
                continue
    except Exception as e:
        logger.debug("Error checking ALSA status: %s", e)
    return False


def _check_v4l2_video_devices() -> tuple[bool, list[str]]:
    try:
        vdevs = set(glob.glob("/dev/video*"))
        if not vdevs:
            return False, []

        apps: list[str] = []
        for pid in os.listdir("/proc"):
            if not pid.isdigit():
                continue
            fd_dir = f"/proc/{pid}/fd"
            try:
                for fd in os.listdir(fd_dir):
                    try:
                        target = os.readlink(f"{fd_dir}/{fd}")
                        if target in vdevs:
                            cmdline_path = f"/proc/{pid}/cmdline"
                            app_name = ""
                            try:
                                with open(cmdline_path, "rb") as cf:
                                    raw = cf.read().replace(b"\x00", b" ").decode(errors="ignore").strip()
                                    if raw:
                                        bin_name = raw.split()[0].split("/")[-1]
                                        app_name = bin_name
                            except (OSError, FileNotFoundError):
                                pass

                            if not app_name:
                                app_name = f"PID {pid}"

                            # Ignore background sound/pipewire daemons holding device idle
                            if app_name.lower() in ("pipewire", "wireplumber"):
                                continue

                            if app_name not in apps:
                                apps.append(app_name)
                    except (OSError, FileNotFoundError):
                        pass
            except (OSError, PermissionError, FileNotFoundError):
                pass

        return (len(apps) > 0), apps
    except Exception as e:
        logger.debug("Error checking /dev/video*: %s", e)
        return False, []


def _parse_wpctl_status(out: str) -> tuple[bool, bool, list[str], list[str]]:
    mic_active = False
    camera_active = False
    mic_apps: list[str] = []
    camera_apps: list[str] = []

    current_section = None
    current_app = ""

    for line in out.splitlines():
        trimmed = line.strip()
        if line.startswith("Audio") and not line.startswith(" "):
            current_section = "audio"
            current_app = ""
        elif line.startswith("Video") and not line.startswith(" "):
            current_section = "video"
            current_app = ""
        elif line.startswith("Settings") and not line.startswith(" "):
            current_section = None

        if current_section == "audio":
            if line.startswith("       ") and not line.startswith("            "):
                parts = trimmed.split(".", 1)
                if len(parts) > 1:
                    current_app = parts[1].strip()
            elif line.startswith("            "):
                if ("input_" in line or "<" in line or "capture" in line) and "[active]" in line:
                    mic_active = True
                    if current_app and current_app not in mic_apps:
                        mic_apps.append(current_app)

        elif current_section == "video":
            if line.startswith("       ") and not line.startswith("            "):
                parts = trimmed.split(".", 1)
                if len(parts) > 1:
                    current_app = parts[1].strip()
            elif line.startswith("            "):
                if "[active]" in line or ">" in line or "<" in line:
                    camera_active = True
                    if current_app and current_app not in camera_apps:
                        camera_apps.append(current_app)

    return mic_active, camera_active, mic_apps, camera_apps


class PrivacyService:

    def __init__(
        self,
        on_changed: Optional[Callable[[PrivacyState], None]] = None,
        poll_interval: float = 0.4,
        auto_start: bool = True,
    ) -> None:
        self._lock = threading.RLock()
        self._on_changed = on_changed
        self.poll_interval = max(0.1, poll_interval)
        self._has_wpctl = shutil.which("wpctl") is not None

        self._current_state = PrivacyState()
        self._simulated: Optional[PrivacyState] = None
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None

        self._last_mic_seen: float = 0.0
        self._last_cam_seen: float = 0.0
        self._linger_seconds: float = 0.6

        if auto_start:
            self.start()

    @property
    def state(self) -> PrivacyState:
        with self._lock:
            if self._simulated is not None:
                return self._simulated
            return self._current_state

    @property
    def mic_active(self) -> bool:
        return self.state.mic_active

    @property
    def camera_active(self) -> bool:
        return self.state.camera_active

    def simulate(self, mic: Optional[bool] = None, camera: Optional[bool] = None, apps: Optional[list[str]] = None) -> None:
        with self._lock:
            if mic is None and camera is None:
                self._simulated = None
                new_state = self._current_state
            else:
                m = mic if mic is not None else self._current_state.mic_active
                c = camera if camera is not None else self._current_state.camera_active
                a_list = tuple(apps) if apps else ()
                new_state = PrivacyState(
                    mic_active=m,
                    camera_active=c,
                    mic_apps=a_list if m else (),
                    camera_apps=a_list if c else (),
                )
                self._simulated = new_state

        if self._on_changed:
            try:
                self._on_changed(new_state)
            except Exception as e:
                logger.error("Error in on_changed simulation callback: %s", e)

    def query_status(self) -> PrivacyState:
        with self._lock:
            if self._simulated is not None:
                return self._simulated

        wp_mic = False
        wp_cam = False
        mic_apps: list[str] = []
        cam_apps: list[str] = []

        if self._has_wpctl:
            try:
                res = subprocess.run(
                    ["wpctl", "status"],
                    capture_output=True,
                    text=True,
                    timeout=0.6,
                    check=False,
                )
                if res.returncode == 0 and res.stdout:
                    wp_mic, wp_cam, mic_apps, cam_apps = _parse_wpctl_status(res.stdout)
            except Exception as e:
                logger.debug("wpctl status check failed: %s", e)

        alsa_mic = _check_alsa_pcm_capture()
        v4l_cam, v4l_apps = _check_v4l2_video_devices()

        now = time.monotonic()
        raw_mic = wp_mic or alsa_mic
        raw_cam = wp_cam or v4l_cam

        if raw_mic:
            self._last_mic_seen = now
        if raw_cam:
            self._last_cam_seen = now

        eff_mic = raw_mic or (now - self._last_mic_seen < self._linger_seconds)
        eff_cam = raw_cam or (now - self._last_cam_seen < self._linger_seconds)

        all_mic_apps = list(mic_apps)
        if eff_mic and not all_mic_apps and alsa_mic:
            all_mic_apps.append("Audio Capture")

        all_cam_apps = list(cam_apps)
        for ca in v4l_apps:
            if ca not in all_cam_apps:
                all_cam_apps.append(ca)

        return PrivacyState(
            mic_active=eff_mic,
            camera_active=eff_cam,
            mic_apps=tuple(all_mic_apps),
            camera_apps=tuple(all_cam_apps),
        )

    def check_and_update(self) -> PrivacyState:
        new_state = self.query_status()
        changed = False

        with self._lock:
            if self._simulated is not None:
                return self._simulated

            if (new_state.mic_active != self._current_state.mic_active or
                new_state.camera_active != self._current_state.camera_active or
                new_state.mic_apps != self._current_state.mic_apps or
                new_state.camera_apps != self._current_state.camera_apps):
                changed = True
                self._current_state = new_state

        if changed and self._on_changed:
            try:
                self._on_changed(new_state)
            except Exception as e:
                logger.error("Error in PrivacyService on_changed callback: %s", e)

        return new_state

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True

        self._monitor_thread = threading.Thread(
            target=self._monitor_worker,
            daemon=True,
            name="PrivacyServiceMonitor",
        )
        self._monitor_thread.start()

    def stop(self) -> None:
        with self._lock:
            self._running = False

    def _monitor_worker(self) -> None:
        while self._running:
            try:
                self.check_and_update()
            except Exception as e:
                logger.debug("Error in PrivacyService loop: %s", e)
            time.sleep(self.poll_interval)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Testing PrivacyService...")
    ps = PrivacyService(auto_start=False)
    st = ps.query_status()
    print("Initial status:", st)
    ps.simulate(mic=True, camera=False, apps=["Discord"])
    print("Simulated mic:", ps.state)
    ps.simulate(mic=False, camera=True, apps=["OBS"])
    print("Simulated cam:", ps.state)
    ps.simulate()
    print("Reset simulation:", ps.state)
    print("PrivacyService tests passed!")
