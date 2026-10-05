#!/usr/bin/env python3

from __future__ import annotations

import array
import fcntl
import glob
import json
import logging
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

_xdg_config = os.environ.get("XDG_CONFIG_HOME")
AUTOSTART_DIR = (Path(_xdg_config) if _xdg_config else (Path.home() / ".config")) / "autostart"
AUTOSTART_FILE = AUTOSTART_DIR / "dynamic-island.desktop"

_EVIOCGKEY_64 = (2 << 30) | (ord("E") << 8) | 0x18 | (64 << 16)
_KEY_LEFTCTRL = 29
_KEY_RIGHTCTRL = 97

def _query_hyprland_fullscreen(exclude_pid: Optional[int] = None) -> Optional[bool]:
    if "HYPRLAND_INSTANCE_SIGNATURE" not in os.environ and not shutil.which("hyprctl"):
        return None

    try:
        res = subprocess.run(
            ["hyprctl", "activewindow", "-j"],
            capture_output=True,
            text=True,
            timeout=0.6,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            data = json.loads(res.stdout)
            if isinstance(data, dict) and data:
                pid = data.get("pid")
                if exclude_pid is not None and pid == exclude_pid:
                    return False

                cls = str(data.get("class", "")).lower()
                initial_cls = str(data.get("initialClass", "")).lower()
                island_names = ("dynamic-island", "dynamicisland", "dynamic_island")
                if any(k in cls or k in initial_cls for k in island_names):
                    return False

                fs = data.get("fullscreen")
                fs_client = data.get("fullscreenClient")
                # In Hyprland:
                # 0 = not fullscreen
                # 1 = maximized (super+D / super+F maximized) -> DO NOT HIDE ISLAND!
                # 2 = true fullscreen (games, video player, F11) -> HIDE ISLAND!
                if fs == 1 or fs_client == 1:
                    return False
                if fs == 2 or fs_client == 2:
                    return True

        res_ws = subprocess.run(
            ["hyprctl", "activeworkspace", "-j"],
            capture_output=True,
            text=True,
            timeout=0.6,
            check=False,
        )
        if res_ws.returncode == 0 and res_ws.stdout.strip():
            ws_data = json.loads(res_ws.stdout)
            if isinstance(ws_data, dict) and ws_data.get("hasfullscreen") is True:
                last_title = str(ws_data.get("lastwindowtitle", "")).lower()
                if any(k in last_title for k in ("dynamic-island", "dynamicisland")):
                    return False

                try:
                    res_clients = subprocess.run(
                        ["hyprctl", "clients", "-j"],
                        capture_output=True,
                        text=True,
                        timeout=0.6,
                        check=False,
                    )
                    if res_clients.returncode == 0 and res_clients.stdout.strip():
                        clients = json.loads(res_clients.stdout)
                        ws_id = ws_data.get("id")
                        for c in clients:
                            if c.get("workspace", {}).get("id") == ws_id:
                                c_fs = c.get("fullscreen")
                                c_fsc = c.get("fullscreenClient")
                                if c_fs == 1 or c_fsc == 1:
                                    return False
                                if c_fs == 2 or c_fsc == 2:
                                    return True
                except Exception:
                    pass

        return False
    except Exception as e:
        logger.debug("Hyprland fullscreen query failed: %s", e)
        return None

def _query_sway_fullscreen() -> Optional[bool]:
    if "SWAYSOCK" not in os.environ and not shutil.which("swaymsg"):
        return None

    try:
        res = subprocess.run(
            ["swaymsg", "-t", "get_tree", "-r"],
            capture_output=True,
            text=True,
            timeout=1.0,
            check=False,
        )
        if res.returncode != 0 or not res.stdout.strip():
            return None

        tree = json.loads(res.stdout)

        def find_focused(node: dict) -> Optional[dict]:
            if node.get("focused"):
                return node
            for child in node.get("nodes", []) + node.get("floating_nodes", []):
                found = find_focused(child)
                if found:
                    return found
            return None

        focused = find_focused(tree)
        if focused:
            mode = focused.get("fullscreen_mode", 0)
            return mode != 0

        return False
    except Exception as e:
        logger.debug("Sway fullscreen query failed: %s", e)
        return None

def _query_xwayland_fullscreen() -> Optional[bool]:
    if not shutil.which("xprop"):
        return None

    try:
        res_root = subprocess.run(
            ["xprop", "-root", "_NET_ACTIVE_WINDOW"],
            capture_output=True,
            text=True,
            timeout=1.0,
            check=False,
        )
        if res_root.returncode != 0 or not res_root.stdout:
            return None

        line = res_root.stdout.strip()
        if "window id #" not in line and "0x" not in line:
            return None

        win_id = line.split()[-1]
        if win_id.startswith("0x") and int(win_id, 16) > 0:
            res_state = subprocess.run(
                ["xprop", "-id", win_id, "_NET_WM_STATE"],
                capture_output=True,
                text=True,
                timeout=1.0,
                check=False,
            )
            if res_state.returncode == 0 and "_NET_WM_STATE_FULLSCREEN" in res_state.stdout:
                return True

        return False
    except Exception as e:
        logger.debug("xprop fullscreen query failed: %s", e)
        return None

def is_fullscreen(exclude_pid: Optional[int] = None) -> bool:
    res = _query_hyprland_fullscreen(exclude_pid=exclude_pid)
    if res is not None:
        return res

    res = _query_sway_fullscreen()
    if res is not None:
        return res

    res = _query_xwayland_fullscreen()
    if res is not None:
        return res

    return False

def is_foreground_fullscreen(self_hwnd_or_pid: Optional[int] = None) -> bool:
    return is_fullscreen(exclude_pid=self_hwnd_or_pid)

class FullscreenWatcher:

    def __init__(
        self,
        on_fullscreen_changed: Optional[Callable[[bool], None]] = None,
        poll_interval: float = 0.3,
        auto_start: bool = True,
    ) -> None:
        self.on_fullscreen_changed = on_fullscreen_changed
        self.poll_interval = max(0.05, float(poll_interval))
        self._lock = threading.RLock()
        self._listeners: list[Callable[[bool], None]] = []
        if on_fullscreen_changed:
            self._listeners.append(on_fullscreen_changed)

        self._is_fullscreen: bool = is_fullscreen()
        self._running: bool = False
        self._thread: Optional[threading.Thread] = None

        if auto_start:
            self.start()

    @property
    def is_active(self) -> bool:
        with self._lock:
            return self._is_fullscreen

    def add_listener(self, callback: Callable[[bool], None]) -> None:
        with self._lock:
            if callback not in self._listeners:
                self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[bool], None]) -> None:
        with self._lock:
            if callback in self._listeners:
                self._listeners.remove(callback)

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True

        self._thread = threading.Thread(
            target=self._worker,
            daemon=True,
            name="FullscreenWatcher",
        )
        self._thread.start()

    def stop(self) -> None:
        with self._lock:
            self._running = False

    def _notify(self, fs: bool) -> None:
        with self._lock:
            if fs == self._is_fullscreen:
                return
            self._is_fullscreen = fs
            listeners = list(self._listeners)

        for listener in listeners:
            try:
                listener(fs)
            except Exception as e:
                logger.error("Error in fullscreen listener: %s", e)

    def _worker(self) -> None:
        his = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
        xdg = os.environ.get("XDG_RUNTIME_DIR")
        sock_path = f"{xdg}/hypr/{his}/.socket2.sock" if (xdg and his) else None

        while self._running:
            if sock_path and os.path.exists(sock_path):
                try:
                    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    s.settimeout(1.0)
                    s.connect(sock_path)
                    buffer = ""
                    while self._running:
                        try:
                            chunk = s.recv(1024).decode("utf-8", errors="replace")
                            if not chunk:
                                break
                            buffer += chunk
                            while "\n" in buffer:
                                line, buffer = buffer.split("\n", 1)
                                if "fullscreen>>" in line or "activewindow>>" in line or "workspace>>" in line:
                                    fs = is_fullscreen()
                                    self._notify(fs)
                        except socket.timeout:
                            fs = is_fullscreen()
                            self._notify(fs)
                    s.close()
                except Exception as e:
                    logger.debug("Hyprland socket2 disconnected: %s", e)

            fs = is_fullscreen()
            self._notify(fs)
            time.sleep(self.poll_interval)

def is_ctrl_down() -> bool:
    try:
        buf = array.array("B", [0] * 64)
        for dev_path in glob.glob("/dev/input/event*"):
            try:
                fd = os.open(dev_path, os.O_RDONLY | os.O_NONBLOCK)
                try:
                    fcntl.ioctl(fd, _EVIOCGKEY_64, buf, True)
                    left_down = bool(buf[_KEY_LEFTCTRL // 8] & (1 << (_KEY_LEFTCTRL % 8)))
                    right_down = bool(buf[_KEY_RIGHTCTRL // 8] & (1 << (_KEY_RIGHTCTRL % 8)))
                    if left_down or right_down:
                        return True
                finally:
                    os.close(fd)
            except Exception:
                continue
    except Exception:
        pass

    try:
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QGuiApplication
        mods = QGuiApplication.keyboardModifiers()
        if bool(mods & Qt.KeyboardModifier.ControlModifier):
            return True
    except Exception:
        pass

    return False

ctrl_down = is_ctrl_down

def query_do_not_disturb() -> Optional[bool]:
    try:
        import gi
        gi.require_version("Gio", "2.0")
        from gi.repository import Gio, GLib
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        res = bus.call_sync(
            "org.freedesktop.Notifications",
            "/org/freedesktop/Notifications",
            "org.freedesktop.DBus.Properties",
            "Get",
            GLib.Variant("(ss)", ("org.freedesktop.Notifications", "Inhibited")),
            GLib.VariantType("(v)"),
            Gio.DBusCallFlags.NONE,
            200,
            None,
        )
        if res:
            val = res.unpack()[0]
            if isinstance(val, bool):
                return val
    except Exception:
        pass

    if shutil.which("swaync-client"):
        try:
            res = subprocess.run(["swaync-client", "-D"], capture_output=True, text=True, timeout=0.3)
            if res.returncode == 0:
                txt = res.stdout.strip().lower()
                if txt in ("true", "1"):
                    return True
                if txt in ("false", "0"):
                    return False
        except Exception:
            pass

    if shutil.which("dunstctl"):
        try:
            res = subprocess.run(["dunstctl", "is-paused"], capture_output=True, text=True, timeout=0.3)
            if res.returncode == 0:
                txt = res.stdout.strip().lower()
                if txt == "true":
                    return True
                if txt == "false":
                    return False
        except Exception:
            pass

    if shutil.which("gsettings"):
        try:
            res = subprocess.run(
                ["gsettings", "get", "org.gnome.desktop.notifications", "show-banners"],
                capture_output=True,
                text=True,
                timeout=0.3,
            )
            if res.returncode == 0:
                return res.stdout.strip().lower() == "false"
        except Exception:
            pass

    return None

class Autostart:

    DESKTOP_PATH = AUTOSTART_FILE

    @classmethod
    def is_enabled(cls) -> bool:
        if not cls.DESKTOP_PATH.is_file():
            return False

        try:
            content = cls.DESKTOP_PATH.read_text(encoding="utf-8")
            if "X-GNOME-Autostart-enabled=false" in content:
                return False
            return True
        except Exception:
            return False

    @classmethod
    def enable(cls, exec_cmd: Optional[str] = None) -> bool:
        return cls.set(True, exec_cmd=exec_cmd)

    @classmethod
    def disable(cls) -> bool:
        return cls.set(False)

    @classmethod
    def set(cls, enabled: bool, exec_cmd: Optional[str] = None) -> bool:
        try:
            if not enabled:
                if cls.DESKTOP_PATH.is_file():
                    cls.DESKTOP_PATH.unlink()
                return True

            if not exec_cmd:
                script_dir = Path(__file__).resolve().parent
                island_py = script_dir / "dynamic_island.py"
                main_py = script_dir / "main.py"
                python_bin = sys.executable
                if island_py.is_file():
                    exec_cmd = f"{python_bin} {island_py}"
                elif main_py.is_file():
                    exec_cmd = f"{python_bin} {main_py}"
                else:
                    exec_cmd = "dynamic-island"

            AUTOSTART_DIR.mkdir(parents=True, exist_ok=True)

            desktop_content = f"""[Desktop Entry]
Type=Application
Name=Dynamic Island
Comment=Dynamic Island status bar for Wayland
Exec={exec_cmd}
Terminal=false
Categories=Utility;
X-GNOME-Autostart-enabled=true
StartupNotify=false
"""
            cls.DESKTOP_PATH.write_text(desktop_content, encoding="utf-8")
            logger.info("Created autostart entry: %s", cls.DESKTOP_PATH)
            return True
        except Exception as e:
            logger.error("Failed setting autostart: %s", e)
            return False

def is_autostart_enabled() -> bool:
    return Autostart.is_enabled()

def set_autostart(enabled: bool, exec_cmd: Optional[str] = None) -> bool:
    return Autostart.set(enabled, exec_cmd=exec_cmd)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    print("=" * 60)
    print("DynamicIsland Linux - Native Wayland Integration Test")
    print("=" * 60)

    fs_active = is_fullscreen()
    print(f"Foreground Fullscreen : {fs_active}")
    print(f"  (Island will {'HIDE' if fs_active else 'SHOW'} when Settings.HideFullscreen is active)")

    ctrl_pressed = is_ctrl_down()
    print(f"Control Key Held      : {ctrl_pressed}")

    autostart_active = Autostart.is_enabled()
    print(f"Autostart Enabled     : {autostart_active}")
    print(f"Autostart Desktop Path: {Autostart.DESKTOP_PATH}")

    print("\nTesting Autostart helper (enable -> check -> disable):")
    import tempfile
    test_island_cmd = f"python3 {Path(tempfile.gettempdir()) / 'test-island.py'}"
    Autostart.set(True, exec_cmd=test_island_cmd)
    print(f"  After enable : Autostart.is_enabled() = {Autostart.is_enabled()}")
    if Autostart.DESKTOP_PATH.is_file():
        print("  File contents preview:")
        for line in Autostart.DESKTOP_PATH.read_text().splitlines():
            print(f"    | {line}")

    Autostart.set(False)
    print(f"  After disable: Autostart.is_enabled() = {Autostart.is_enabled()}")
    print("=" * 60)
