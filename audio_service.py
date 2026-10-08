#!/usr/bin/env python3

from __future__ import annotations

import atexit
import json
import logging
import re
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

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

@dataclass
class AudioDevice:
    name: str
    kind: str
    is_headphones: bool
    sink_name: str = ""
    container: str = ""

class AudioService:

    def __init__(self, on_device_changed: Optional[Callable[[str, bool], None]] = None) -> None:
        self._lock = threading.RLock()
        self._has_wpctl = shutil.which("wpctl") is not None
        self._has_pactl = shutil.which("pactl") is not None

        self._callbacks: list[Callable[[str, bool], None]] = []
        self.on_device_changed = on_device_changed

        self._current_device: AudioDevice = self._query_default_device()
        self._switched: Optional[AudioDevice] = None
        self._seen: bool = False
        self._last_checked: float = 0.0

        self._cached_volume: float = 0.5
        self._cached_muted: bool = False
        init_vol, init_muted = self._query_volume_raw()
        self._cached_volume = init_vol
        self._cached_muted = init_muted

        self._pending_volume: Optional[float] = None
        self._pending_mute: Optional[bool] = None
        self._last_internal_change: float = 0.0
        self._apply_event = threading.Event()

        self._cached_app_streams: list[dict] = []
        self._last_app_streams_time: float = 0.0
        self._app_streams_ttl: float = 0.5
        self._pending_app_volumes: dict[int, tuple[float, bool]] = {}
        self._querying_app_streams: bool = False
        self._ensuring: bool = False

        self._running: bool = True
        self._apply_thread: Optional[threading.Thread] = None
        self._start_apply_worker()

        self._sub_proc: Optional[subprocess.Popen] = None
        self._monitor_thread: Optional[threading.Thread] = None
        self._start_monitor()
        atexit.register(self.close)

    def _query_volume_raw(self) -> tuple[float, bool]:
        if self._has_wpctl:
            try:
                res = subprocess.run(
                    ["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"],
                    capture_output=True,
                    text=True,
                    timeout=1.5,
                    check=False,
                )
                if res.returncode == 0 and res.stdout:
                    match = re.search(r"Volume:\s*([0-9.]+)", res.stdout)
                    if match:
                        vol = float(match.group(1))
                        muted = "[MUTED]" in res.stdout
                        return max(0.0, min(1.0, vol)), muted
            except Exception as e:
                logger.debug("wpctl get-volume failed: %s", e)

        if self._has_pactl:
            try:
                vol_res = subprocess.run(
                    ["pactl", "get-sink-volume", "@DEFAULT_SINK@"],
                    capture_output=True,
                    text=True,
                    timeout=1.5,
                    check=False,
                )
                mute_res = subprocess.run(
                    ["pactl", "get-sink-mute", "@DEFAULT_SINK@"],
                    capture_output=True,
                    text=True,
                    timeout=1.5,
                    check=False,
                )
                if vol_res.returncode == 0:
                    match = re.search(r"/\s*([0-9]+)%\s*/", vol_res.stdout)
                    vol = float(match.group(1)) / 100.0 if match else 0.0
                    muted = "yes" in mute_res.stdout.lower() if mute_res.returncode == 0 else False
                    return max(0.0, min(1.0, vol)), muted
            except Exception as e:
                logger.debug("pactl get-sink-volume fallback failed: %s", e)

        return 0.5, False

    def get_volume(self) -> tuple[float, bool]:
        with self._lock:
            return self._cached_volume, self._cached_muted

    def try_get_volume(self) -> tuple[bool, float, bool]:
        vol, muted = self.get_volume()
        return True, vol, muted

    def set_volume(self, level: float) -> None:
        clamped = max(0.0, min(1.0, float(level)))
        with self._lock:
            self._cached_volume = clamped
            self._pending_volume = clamped
            self._last_internal_change = time.monotonic()
        self._apply_event.set()

    def nudge_volume(self, delta: float) -> float:
        with self._lock:
            new_vol = max(0.0, min(1.0, self._cached_volume + delta))
            self._cached_volume = new_vol
            self._pending_volume = new_vol
            if delta > 0 and self._cached_muted:
                self._cached_muted = False
                self._pending_mute = False
            self._last_internal_change = time.monotonic()
        self._apply_event.set()
        return new_vol

    def toggle_mute(self) -> bool:
        with self._lock:
            new_muted = not self._cached_muted
            self._cached_muted = new_muted
            self._pending_mute = new_muted
            self._last_internal_change = time.monotonic()
        self._apply_event.set()
        return new_muted

    def set_mute(self, muted: bool) -> None:
        with self._lock:
            self._cached_muted = bool(muted)
            self._pending_mute = bool(muted)
            self._last_internal_change = time.monotonic()
        self._apply_event.set()

    def _start_apply_worker(self) -> None:
        self._apply_thread = threading.Thread(
            target=self._apply_worker,
            daemon=True,
            name="AudioServiceApplyWorker",
        )
        self._apply_thread.start()

    def _apply_worker(self) -> None:
        while self._running:
            if not self._apply_event.wait(timeout=0.1):
                continue
            if not self._running:
                break

            time.sleep(0.01)
            self._apply_event.clear()

            with self._lock:
                target_vol = self._pending_volume
                target_mute = self._pending_mute
                self._pending_volume = None
                self._pending_mute = None

                app_vol_changes = dict(self._pending_app_volumes)
                self._pending_app_volumes.clear()

            if target_vol is not None:
                self._apply_volume_raw(target_vol)

            if target_mute is not None:
                self._apply_mute_raw(target_mute)

            if app_vol_changes:
                for idx, (app_vol, unmute) in app_vol_changes.items():
                    self._apply_app_volume_raw(idx, app_vol, unmute)

        with self._lock:
            target_vol = self._pending_volume
            target_mute = self._pending_mute
            self._pending_volume = None
            self._pending_mute = None
            app_vol_changes = dict(self._pending_app_volumes)
            self._pending_app_volumes.clear()

        if target_vol is not None:
            self._apply_volume_raw(target_vol)
        if target_mute is not None:
            self._apply_mute_raw(target_mute)
        if app_vol_changes:
            for idx, (app_vol, unmute) in app_vol_changes.items():
                self._apply_app_volume_raw(idx, app_vol, unmute)

    def _apply_volume_raw(self, clamped: float) -> None:
        if self._has_wpctl:
            try:
                res = subprocess.run(
                    ["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{clamped:.4f}"],
                    capture_output=True,
                    timeout=1.5,
                    check=False,
                )
                if res.returncode == 0:
                    return
            except Exception as e:
                logger.debug("wpctl set-volume failed: %s", e)

        if self._has_pactl:
            try:
                pct = int(round(clamped * 100))
                subprocess.run(
                    ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{pct}%"],
                    capture_output=True,
                    timeout=1.5,
                    check=False,
                )
            except Exception as e:
                logger.debug("pactl set-sink-volume failed: %s", e)

    def _apply_mute_raw(self, muted: bool) -> None:
        val = "1" if muted else "0"
        if self._has_wpctl:
            try:
                res = subprocess.run(
                    ["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", val],
                    capture_output=True,
                    timeout=1.5,
                    check=False,
                )
                if res.returncode == 0:
                    return
            except Exception as e:
                logger.debug("wpctl set-mute failed: %s", e)

        if self._has_pactl:
            try:
                subprocess.run(
                    ["pactl", "set-sink-mute", "@DEFAULT_SINK@", val],
                    capture_output=True,
                    timeout=1.5,
                    check=False,
                )
            except Exception as e:
                logger.debug("pactl set-sink-mute failed: %s", e)

    def _apply_app_volume_raw(self, idx: int, vol: float, unmute: bool) -> None:
        if not self._has_pactl:
            return
        pct = int(round(vol * 100))
        try:
            subprocess.run(
                ["pactl", "set-sink-input-volume", str(idx), f"{pct}%"],
                capture_output=True,
                timeout=1.5,
                check=False,
            )
            if unmute:
                subprocess.run(
                    ["pactl", "set-sink-input-mute", str(idx), "0"],
                    capture_output=True,
                    timeout=1.5,
                    check=False,
                )
        except Exception as e:
            logger.debug("Failed setting sink-input %d volume: %s", idx, e)

    def peak(self) -> float:
        return -1.0

    def list_app_streams(self, force: bool = False) -> list[dict]:
        now = time.monotonic()
        with self._lock:
            cached = list(self._cached_app_streams)
            is_stale = force or (now - self._last_app_streams_time >= self._app_streams_ttl)
            if not is_stale or self._querying_app_streams:
                return cached
            self._querying_app_streams = True

        def _worker():
            try:
                streams = self._query_app_streams_raw()
                with self._lock:
                    for s in streams:
                        idx = s["index"]
                        if idx in self._pending_app_volumes:
                            pending_vol, pending_unmute = self._pending_app_volumes[idx]
                            s["volume"] = pending_vol
                            if pending_unmute:
                                s["mute"] = False
                    self._cached_app_streams = streams
                    self._last_app_streams_time = time.monotonic()
            finally:
                with self._lock:
                    self._querying_app_streams = False

        if not cached:
            _worker()
            with self._lock:
                return list(self._cached_app_streams)
        else:
            threading.Thread(target=_worker, daemon=True, name="AppStreamsWorker").start()
            return cached

    def _query_app_streams_raw(self) -> list[dict]:
        if self._has_pactl:
            try:
                res = subprocess.run(
                    ["pactl", "--format=json", "list", "sink-inputs"],
                    capture_output=True,
                    text=True,
                    timeout=2.0,
                    check=False,
                )
                if res.returncode == 0 and res.stdout.strip():
                    raw_data = json.loads(res.stdout)
                    if isinstance(raw_data, list):
                        parsed = []
                        for item in raw_data:
                            idx = int(item.get("index", 0))
                            mute = bool(item.get("mute", False))
                            props = item.get("properties", {})

                            vol = 1.0
                            vol_dict = item.get("volume", {})
                            if isinstance(vol_dict, dict) and vol_dict:
                                ch = next(iter(vol_dict.values()))
                                if isinstance(ch, dict):
                                    if "value_percent" in ch:
                                        vol = float(str(ch["value_percent"]).rstrip("%")) / 100.0
                                    elif "value" in ch:
                                        vol = float(ch["value"]) / 65536.0

                            parsed.append({
                                "index": idx,
                                "volume": max(0.0, min(1.0, vol)),
                                "mute": mute,
                                "properties": props,
                                "name": props.get("application.name") or props.get("node.name") or "",
                                "binary": props.get("application.process.binary") or "",
                                "pid": props.get("application.process.id") or "",
                            })
                        return parsed
            except Exception as e:
                logger.debug("pactl json list sink-inputs failed: %s", e)

            try:
                res = subprocess.run(
                    ["pactl", "list", "sink-inputs"],
                    capture_output=True,
                    text=True,
                    timeout=2.0,
                    check=False,
                )
                if res.returncode == 0 and res.stdout.strip():
                    return self._parse_pactl_text_sink_inputs(res.stdout)
            except Exception as e:
                logger.debug("pactl text list sink-inputs failed: %s", e)

        return []

    def _parse_pactl_text_sink_inputs(self, text: str) -> list[dict]:
        streams = []
        current: Optional[dict] = None

        for line in text.splitlines():
            idx_match = re.match(r"^Sink Input #(\d+)", line)
            if idx_match:
                if current:
                    streams.append(current)
                current = {
                    "index": int(idx_match.group(1)),
                    "volume": 1.0,
                    "mute": False,
                    "properties": {},
                    "name": "",
                    "binary": "",
                    "pid": "",
                }
                continue

            if current is None:
                continue

            if "Mute:" in line:
                current["mute"] = "yes" in line.lower()
            elif "Volume:" in line:
                m = re.search(r"/\s*([0-9]+)%\s*/", line)
                if m:
                    current["volume"] = float(m.group(1)) / 100.0
            else:
                pm = re.match(r"^\s*([a-zA-Z0-9._-]+)\s*=\s*\"?(.*?)\"?$", line)
                if pm:
                    key = pm.group(1)
                    val = pm.group(2).strip('"')
                    current["properties"][key] = val
                    if key == "application.name" or (key == "node.name" and not current["name"]):
                        current["name"] = val
                    elif key == "application.process.binary":
                        current["binary"] = val
                    elif key == "application.process.id":
                        current["pid"] = val

        if current:
            streams.append(current)

        return streams

    def _matches_app(self, stream: dict, app_id: str) -> bool:
        if not app_id:
            return False

        app_id_clean = app_id.strip()
        props = stream.get("properties", {})

        if app_id_clean.isdigit():
            if str(stream.get("pid", "")).strip() == app_id_clean:
                return True
            if str(props.get("application.process.id", "")).strip() == app_id_clean:
                return True
            if str(props.get("client.id", "")).strip() == app_id_clean:
                return True

        target = app_id_clean.lower()
        if target.startswith("org.mpris.mediaplayer2."):
            target = target[len("org.mpris.mediaplayer2."):]
        if target.endswith(".desktop"):
            target = target[:-8]
        if target.endswith(".exe"):
            target = target[:-4]

        tokens = [target]
        if "." in target:
            tokens.append(target.split(".")[0])
            tokens.append(target.split(".")[-1])

        candidates = [
            stream.get("name", ""),
            stream.get("binary", ""),
            props.get("application.name", ""),
            props.get("application.process.binary", ""),
            props.get("application.icon_name", ""),
            props.get("node.name", ""),
            props.get("media.name", ""),
            props.get("device.description", ""),
            props.get("pipewire.access.portal.app_id", ""),
            props.get("application.id", ""),
        ]

        for cand in candidates:
            if not cand:
                continue
            cand_lower = str(cand).lower()
            for token in tokens:
                if not token:
                    continue
                if token == cand_lower or token in cand_lower:
                    return True

        return False

    def find_app_sink_inputs(self, app_id: str) -> list[dict]:
        streams = self.list_app_streams()
        return [s for s in streams if self._matches_app(s, app_id)]

    def get_app_volume(self, app_id: str) -> tuple[bool, float, bool]:
        matched = self.find_app_sink_inputs(app_id)
        if not matched:
            return False, 0.0, False
        first = matched[0]
        return True, first["volume"], first["mute"]

    def set_app_volume(self, app_id: str, level: float) -> bool:
        matched = self.find_app_sink_inputs(app_id)
        if not matched:
            return False

        clamped = max(0.0, min(1.0, float(level)))
        with self._lock:
            for s in matched:
                s["volume"] = clamped
                self._pending_app_volumes[s["index"]] = (clamped, False)
            self._last_internal_change = time.monotonic()

        self._apply_event.set()
        return True

    def nudge_app_volume(self, app_id: str, delta: float) -> tuple[bool, float]:
        matched = self.find_app_sink_inputs(app_id)
        if not matched:
            return False, 0.0

        current_vol = matched[0]["volume"]
        new_vol = max(0.0, min(1.0, current_vol + delta))
        unmute = delta > 0

        with self._lock:
            for s in matched:
                s["volume"] = new_vol
                if unmute:
                    s["mute"] = False
                self._pending_app_volumes[s["index"]] = (new_vol, unmute)
            self._last_internal_change = time.monotonic()

        self._apply_event.set()
        return True, new_vol

    def nudge(self, *args, **kwargs) -> tuple[bool, float] | float:
        if len(args) == 1 and isinstance(args[0], (int, float)):
            return self.nudge_volume(float(args[0]))
        if len(args) == 2 and isinstance(args[0], str) and isinstance(args[1], (int, float)):
            return self.nudge_app_volume(args[0], float(args[1]))
        if "app_id" in kwargs:
            return self.nudge_app_volume(kwargs["app_id"], float(kwargs.get("delta", 0.02)))
        if "delta" in kwargs:
            return self.nudge_volume(float(kwargs["delta"]))
        raise ValueError("Invalid arguments for nudge")

    def _query_default_device(self) -> AudioDevice:
        if self._has_pactl:
            try:
                info_res = subprocess.run(
                    ["pactl", "--format=json", "info"],
                    capture_output=True,
                    text=True,
                    timeout=1.5,
                    check=False,
                )
                sinks_res = subprocess.run(
                    ["pactl", "--format=json", "list", "sinks"],
                    capture_output=True,
                    text=True,
                    timeout=1.5,
                    check=False,
                )

                if info_res.returncode == 0 and sinks_res.returncode == 0:
                    info_data = json.loads(info_res.stdout)
                    def_sink_name = info_data.get("default_sink_name", "")
                    sinks = json.loads(sinks_res.stdout)

                    for s in sinks:
                        if s.get("name") == def_sink_name:
                            return self._build_device_from_pactl_sink(s)
            except Exception as e:
                logger.debug("Failed querying devices via pactl json: %s", e)

        if self._has_wpctl:
            try:
                res = subprocess.run(
                    ["wpctl", "inspect", "@DEFAULT_AUDIO_SINK@"],
                    capture_output=True,
                    text=True,
                    timeout=1.5,
                    check=False,
                )
                if res.returncode == 0 and res.stdout:
                    return self._build_device_from_wpctl_inspect(res.stdout)
            except Exception as e:
                logger.debug("Failed querying devices via wpctl: %s", e)

        return AudioDevice(name="Default Playback Device", kind="Speaker", is_headphones=False)

    def _build_device_from_pactl_sink(self, sink: dict) -> AudioDevice:
        sink_name = sink.get("name", "")
        desc = sink.get("description", "")
        active_port = sink.get("active_port", "")
        ports = sink.get("ports", [])
        props = sink.get("properties", {})

        form_factor = str(props.get("device.form_factor", "")).lower()
        icon = str(props.get("device.icon_name", "")).lower()
        bus = str(props.get("device.bus", "")).lower()
        dev_desc = props.get("device.description") or desc

        is_headphones = False

        if active_port:
            p_lower = active_port.lower()
            if "headphone" in p_lower or "headset" in p_lower:
                is_headphones = True

        for p in ports:
            if p.get("name") == active_port:
                p_desc = str(p.get("description", "")).lower()
                p_type = str(p.get("type", "")).lower()
                if "headphone" in p_desc or "headset" in p_desc or "headphone" in p_type or "headset" in p_type:
                    is_headphones = True

        if form_factor in ("headphone", "headset") or "headphone" in icon or "headset" in icon:
            is_headphones = True

        combined_text = f"{desc} {sink_name}".lower()
        keywords = ("headphone", "headset", "earphone", "earbuds", "airpods", "buds")
        if any(k in combined_text for k in keywords):
            is_headphones = True

        container = (
            props.get("device.string")
            or props.get("device.bus_path")
            or props.get("sysfs.path")
            or sink_name
        )

        if is_headphones:
            kind = "Headphones"
            if form_factor in ("headphone", "headset") or bus == "bluetooth":
                name = dev_desc or desc or "Headphones"
            else:
                name = f"Headphones ({dev_desc})" if dev_desc else "Headphones"
        elif "hdmi" in sink_name.lower() or "hdmi" in desc.lower() or "displayport" in desc.lower():
            kind = "HDMI"
            name = dev_desc or desc or "HDMI Audio"
        else:
            kind = "Speaker"
            name = dev_desc or desc or "Speakers"

        return AudioDevice(
            name=name,
            kind=kind,
            is_headphones=is_headphones,
            sink_name=sink_name,
            container=container,
        )

    def _build_device_from_wpctl_inspect(self, text: str) -> AudioDevice:
        props = {}
        for line in text.splitlines():
            m = re.match(r"^\s*[*]?\s*([a-zA-Z0-9._-]+)\s*=\s*\"?(.*?)\"?$", line)
            if m:
                props[m.group(1)] = m.group(2).strip('"')

        desc = props.get("node.description") or props.get("device.description") or "Default Audio Sink"
        sink_name = props.get("node.name", "")
        form_factor = props.get("device.form-factor", "").lower()
        icon = props.get("device.icon-name", "").lower()
        container = props.get("device.bus_path") or props.get("object.path") or sink_name

        is_headphones = (
            form_factor in ("headphone", "headset")
            or "headphone" in icon
            or "headset" in icon
            or any(k in desc.lower() for k in ("headphone", "headset", "buds", "airpods"))
        )

        kind = "Headphones" if is_headphones else "Speaker"
        name = desc if (not is_headphones or form_factor in ("headphone", "headset")) else f"Headphones ({desc})"

        return AudioDevice(
            name=name,
            kind=kind,
            is_headphones=is_headphones,
            sink_name=sink_name,
            container=container,
        )

    @property
    def device(self) -> AudioDevice:
        if not (self._monitor_thread and self._monitor_thread.is_alive()):
            self.ensure()
        with self._lock:
            return self._current_device

    def get_default_device(self) -> AudioDevice:
        return self.device

    def take_switch(self) -> tuple[bool, Optional[AudioDevice]]:
        if not (self._monitor_thread and self._monitor_thread.is_alive()):
            if not self._ensuring:
                self._ensuring = True
                def _ensure_worker():
                    try:
                        self.ensure()
                    finally:
                        self._ensuring = False
                threading.Thread(target=_ensure_worker, daemon=True, name="AudioEnsureWorker").start()
        with self._lock:
            if self._switched is not None:
                dev = self._switched
                self._switched = None
                return True, dev
            return False, None

    def add_device_changed_callback(self, callback: Callable[[str, bool], None]) -> None:
        with self._lock:
            if callback not in self._callbacks:
                self._callbacks.append(callback)

    def remove_device_changed_callback(self, callback: Callable[[str, bool], None]) -> None:
        with self._lock:
            if callback in self._callbacks:
                self._callbacks.remove(callback)

    def _notify_device_changed(self, device: AudioDevice) -> None:
        if callable(self.on_device_changed):
            try:
                self.on_device_changed(device.name, device.is_headphones)
            except Exception as e:
                logger.exception("Error in on_device_changed handler: %s", e)

        with self._lock:
            cbs = list(self._callbacks)
        for cb in cbs:
            try:
                cb(device.name, device.is_headphones)
            except Exception as e:
                logger.exception("Error in device change callback: %s", e)

    def ensure(self) -> None:
        now = time.monotonic()
        if now - self._last_checked < 1.0:
            return
        self._last_checked = now

        try:
            new_dev = self._query_default_device()
            with self._lock:
                if self._seen and (
                    new_dev.sink_name != self._current_device.sink_name
                    or new_dev.is_headphones != self._current_device.is_headphones
                    or new_dev.kind != self._current_device.kind
                ):
                    self._switched = new_dev
                    self._current_device = new_dev
                    self._notify_device_changed(new_dev)
                elif not self._seen:
                    self._current_device = new_dev
                    self._seen = True
        except Exception as e:
            logger.debug("Error in AudioService.ensure: %s", e)

    def _start_monitor(self) -> None:
        if not self._has_pactl:
            return

        def monitor_worker():
            while self._running:
                try:
                    self._sub_proc = subprocess.Popen(
                        ["pactl", "subscribe"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,
                        text=True,
                        bufsize=1,
                        preexec_fn=_set_pdeathsig,
                    )
                    while self._running and self._sub_proc.stdout:
                        line = self._sub_proc.stdout.readline()
                        if not line:
                            break
                        line_lower = line.lower()

                        if "sink-input" in line_lower:
                            with self._lock:
                                self._last_app_streams_time = 0.0
                        elif "server" in line_lower or "card" in line_lower or ("sink" in line_lower and ("'new'" in line_lower or "'remove'" in line_lower)):
                            self._check_device_switch()
                        elif "sink" in line_lower:
                            now = time.monotonic()
                            with self._lock:
                                has_pending = (self._pending_volume is not None or self._pending_mute is not None)
                                recent_internal = (now - self._last_internal_change < 0.25)

                            if not has_pending and not recent_internal:
                                vol, muted = self._query_volume_raw()
                                with self._lock:
                                    if (self._pending_volume is None and self._pending_mute is None and
                                            (time.monotonic() - self._last_internal_change >= 0.25)):
                                        self._cached_volume = vol
                                        self._cached_muted = muted
                except Exception as e:
                    logger.debug("pactl subscribe monitor encountered: %s", e)
                finally:
                    if self._sub_proc:
                        try:
                            self._sub_proc.terminate()
                        except Exception:
                            pass
                        self._sub_proc = None
                if self._running:
                    time.sleep(1.0)

        self._monitor_thread = threading.Thread(target=monitor_worker, daemon=True, name="AudioServiceMonitor")
        self._monitor_thread.start()

    def _check_device_switch(self) -> None:
        new_dev = self._query_default_device()
        with self._lock:
            if (
                new_dev.sink_name != self._current_device.sink_name
                or new_dev.is_headphones != self._current_device.is_headphones
                or new_dev.kind != self._current_device.kind
            ):
                self._switched = new_dev
                self._current_device = new_dev
                self._notify_device_changed(new_dev)

    def close(self) -> None:
        self._running = False
        self._apply_event.set()
        if self._apply_thread and self._apply_thread.is_alive():
            self._apply_thread.join(timeout=1.0)
        if self._sub_proc:
            try:
                self._sub_proc.terminate()
            except Exception:
                pass
            self._sub_proc = None
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=1.0)

_default_service: Optional[AudioService] = None

def get_service() -> AudioService:
    global _default_service
    if _default_service is None:
        _default_service = AudioService()
    return _default_service

def get_volume() -> tuple[float, bool]:
    return get_service().get_volume()

def set_volume(level: float) -> None:
    get_service().set_volume(level)

def nudge_volume(delta: float) -> float:
    return get_service().nudge_volume(delta)

def toggle_mute() -> bool:
    return get_service().toggle_mute()

def set_mute(muted: bool) -> None:
    get_service().set_mute(muted)

def get_default_device() -> AudioDevice:
    return get_service().get_default_device()

def nudge_app_volume(app_id: str, delta: float) -> tuple[bool, float]:
    return get_service().nudge_app_volume(app_id, delta)

def get_app_volume(app_id: str) -> tuple[bool, float, bool]:
    return get_service().get_app_volume(app_id)

def set_app_volume(app_id: str, level: float) -> bool:
    return get_service().set_app_volume(app_id, level)

if __name__ == "__main__":
    print("=== Testing AudioService (Linux PipeWire/PulseAudio) ===")
    svc = AudioService()

    vol, muted = svc.get_volume()
    print(f"[Master Volume] Current: {vol * 100:.1f}%, Muted: {muted}")

    test_delta = 0.02
    print(f"[Master Volume] Testing nudge +{test_delta * 100:.0f}%...")
    new_vol = svc.nudge_volume(test_delta)
    print(f"  -> Volume after nudge: {new_vol * 100:.1f}%")
    print(f"[Master Volume] Restoring original volume: {vol * 100:.1f}%...")
    svc.set_volume(vol)
    restored_vol, _ = svc.get_volume()
    print(f"  -> Restored volume: {restored_vol * 100:.1f}%")

    dev = svc.get_default_device()
    print(f"[Output Device] Name: {dev.name}")
    print(f"  Kind: {dev.kind}, IsHeadphones: {dev.is_headphones}")
    print(f"  Sink: {dev.sink_name}")
    print(f"  Container/ID: {dev.container}")

    switched, switch_dev = svc.take_switch()
    print(f"[Device Switch] TakeSwitch: switched={switched}, device={switch_dev}")

    streams = svc.list_app_streams()
    print(f"[App Streams] Found {len(streams)} active sink-input(s):")
    for s in streams:
        print(f"  - [{s['index']}] Name='{s['name']}', Binary='{s['binary']}', PID={s['pid']}, Vol={s['volume'] * 100:.0f}%")

    if streams:
        first_app = streams[0]["name"] or streams[0]["binary"] or str(streams[0]["index"])
        orig_app_vol = streams[0]["volume"]
        print(f"[Per-App Volume] Testing nudge on '{first_app}'...")
        ok, n_vol = svc.nudge_app_volume(first_app, 0.02)
        print(f"  -> App nudge success: {ok}, New Vol: {n_vol * 100:.0f}%")
        print(f"[Per-App Volume] Restoring app volume to {orig_app_vol * 100:.0f}%...")
        svc.set_app_volume(first_app, orig_app_vol)
        print("  -> Restored successfully")
    else:
        print("[Per-App Volume] No active playback apps found to test nudge.")

    last_notified = []

    def on_change(name, is_hp):
        last_notified.append((name, is_hp))

    svc.add_device_changed_callback(on_change)
    print(f"[Callbacks] Registered test callback. Total registered: {len(svc._callbacks)}")

    svc.close()
    print("=== AudioService test completed successfully! ===")
