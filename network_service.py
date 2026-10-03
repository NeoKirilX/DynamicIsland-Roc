#!/usr/bin/env python3

from __future__ import annotations

import glob
import logging
import os
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from enum import IntEnum
from typing import Callable, Optional

logger = logging.getLogger(__name__)

SETTLE_DELAY: float = 1.5

VPN_HINTS = (
    "vpn",
    "wireguard",
    "wg",
    "tun",
    "tap",
    "tailscale",
    "zerotier",
    "openvpn",
    "ppp",
    "proton",
    "nord",
    "mullvad",
    "ipsec",
)

NM_CONNECTIVITY_UNKNOWN = 0
NM_CONNECTIVITY_NONE = 1
NM_CONNECTIVITY_PORTAL = 2
NM_CONNECTIVITY_LIMITED = 3
NM_CONNECTIVITY_FULL = 4

NM_ACTIVE_CONNECTION_STATE_UNKNOWN = 0
NM_ACTIVE_CONNECTION_STATE_ACTIVATING = 1
NM_ACTIVE_CONNECTION_STATE_ACTIVATED = 2
NM_ACTIVE_CONNECTION_STATE_DEACTIVATING = 3
NM_ACTIVE_CONNECTION_STATE_DEACTIVATED = 4

class Link(IntEnum):
    NONE = 0
    WIFI = 1
    WIRED = 2
    MOBILE = 3

setattr(Link, "None", Link.NONE)
setattr(Link, "Wifi", Link.WIFI)
setattr(Link, "Wired", Link.WIRED)
setattr(Link, "Mobile", Link.MOBILE)

@dataclass(frozen=True)
class State:
    link: Link = Link.NONE
    name: str = ""
    internet: bool = False
    vpn: str = ""

    @property
    def Link(self) -> Link:
        return self.link

    @property
    def Name(self) -> str:
        return self.name

    @property
    def Internet(self) -> bool:
        return self.internet

    @property
    def Vpn(self) -> str:
        return self.vpn

def _get_active_vpn_interfaces() -> list[str]:
    tunnels: list[str] = []
    try:
        for iface_path in glob.glob("/sys/class/net/*"):
            iface = os.path.basename(iface_path)
            iface_lower = iface.lower()
            if iface_lower in ("lo", "docker0") or iface_lower.startswith("veth") or iface_lower.startswith("br-"):
                continue

            is_tunnel_name = any(iface_lower.startswith(h) or h in iface_lower for h in ("wg", "tun", "tap", "tailscale", "proton", "ppp"))
            if not is_tunnel_name:
                continue

            try:
                with open(os.path.join(iface_path, "flags"), "r") as f:
                    flags = int(f.read().strip(), 16)
                    if flags & 0x1:
                        tunnels.append(iface)
            except Exception:
                pass
    except Exception as e:
        logger.debug("Failed scanning /sys/class/net: %s", e)

    return tunnels

def _read_via_dbus() -> Optional[State]:
    try:
        import dbus
    except ImportError:
        return None

    try:
        bus = dbus.SystemBus()
        nm_obj = bus.get_object("org.freedesktop.NetworkManager", "/org/freedesktop/NetworkManager")
        nm_props = dbus.Interface(nm_obj, "org.freedesktop.DBus.Properties")

        try:
            connectivity = int(nm_props.Get("org.freedesktop.NetworkManager", "Connectivity"))
            internet = (connectivity == NM_CONNECTIVITY_FULL)
        except Exception:
            internet = False

        try:
            primary_path = str(nm_props.Get("org.freedesktop.NetworkManager", "PrimaryConnection"))
        except Exception:
            primary_path = "/"

        try:
            active_paths = nm_props.Get("org.freedesktop.NetworkManager", "ActiveConnections")
        except Exception:
            active_paths = []

        link = Link.NONE
        name = ""
        vpn_names: set[str] = set()
        covered_devices: set[str] = set()

        def get_wifi_ssid(dev_paths: list[str]) -> Optional[str]:
            for dev_path in dev_paths:
                try:
                    dev_obj = bus.get_object("org.freedesktop.NetworkManager", dev_path)
                    dev_p = dbus.Interface(dev_obj, "org.freedesktop.DBus.Properties")
                    ap_path = str(dev_p.Get("org.freedesktop.NetworkManager.Device.Wireless", "ActiveAccessPoint"))
                    if ap_path and ap_path != "/":
                        ap_obj = bus.get_object("org.freedesktop.NetworkManager", ap_path)
                        ap_p = dbus.Interface(ap_obj, "org.freedesktop.DBus.Properties")
                        ssid_bytes = ap_p.Get("org.freedesktop.NetworkManager.AccessPoint", "Ssid")
                        ssid_str = bytes(ssid_bytes).decode("utf-8", errors="replace").strip()
                        if ssid_str:
                            return ssid_str
                except Exception:
                    pass
            return None

        primary_props: Optional[dict] = None

        for path in active_paths:
            try:
                ac_obj = bus.get_object("org.freedesktop.NetworkManager", path)
                ac_props_iface = dbus.Interface(ac_obj, "org.freedesktop.DBus.Properties")
                props = ac_props_iface.GetAll("org.freedesktop.NetworkManager.Connection.Active")

                conn_id = str(props.get("Id", "")).strip()
                conn_type = str(props.get("Type", "")).lower()
                is_vpn = bool(props.get("Vpn", 0))
                state = int(props.get("State", 0))
                default_route = bool(props.get("Default", 0)) or bool(props.get("Default6", 0))
                devices = [str(d) for d in props.get("Devices", [])]

                for dev_path in devices:
                    try:
                        dev_obj = bus.get_object("org.freedesktop.NetworkManager", dev_path)
                        dev_p = dbus.Interface(dev_obj, "org.freedesktop.DBus.Properties")
                        iface_name = str(dev_p.Get("org.freedesktop.NetworkManager.Device", "Interface"))
                        if iface_name:
                            covered_devices.add(iface_name.lower())
                    except Exception:
                        pass

                if state != NM_ACTIVE_CONNECTION_STATE_ACTIVATED:
                    continue

                is_tunnel = (
                    is_vpn
                    or conn_type in ("vpn", "wireguard", "tun", "tap", "ppp")
                    or any(h in conn_type for h in ("wireguard", "tun", "tap", "vpn"))
                    or (any(h in conn_id.lower() for h in VPN_HINTS) and conn_type not in ("802-3-ethernet", "802-11-wireless", "loopback", "dummy"))
                )

                if is_tunnel and conn_id and conn_type != "loopback":
                    vpn_names.add(conn_id)

                if str(path) == primary_path:
                    primary_props = props
                elif not primary_props and default_route and not is_tunnel and conn_type not in ("loopback", "dummy"):
                    primary_props = props
            except Exception as e:
                logger.debug("Error reading active connection %s: %s", path, e)

        if primary_props:
            conn_id = str(primary_props.get("Id", "")).strip()
            conn_type = str(primary_props.get("Type", "")).lower()
            devices = [str(d) for d in primary_props.get("Devices", [])]

            if any(k in conn_type for k in ("wireless", "wifi", "802-11")):
                link = Link.WIFI
                ssid = get_wifi_ssid(devices)
                name = ssid if ssid else conn_id
            elif any(k in conn_type for k in ("ethernet", "802-3", "wired")):
                link = Link.WIRED
                name = conn_id or "Ethernet"
            elif any(k in conn_type for k in ("gsm", "cdma", "wwan", "modem", "mobile", "broadband")):
                link = Link.MOBILE
                name = conn_id or "Mobile Broadband"
            elif conn_id:
                link = Link.WIRED
                name = conn_id

        for kernel_tunnel in _get_active_vpn_interfaces():
            kt_lower = kernel_tunnel.lower()
            if kt_lower in covered_devices:
                continue
            if not any(kt_lower == v.lower() or kt_lower in v.lower() for v in vpn_names):
                vpn_names.add(kernel_tunnel)

        sorted_vpns = sorted(vpn_names)
        vpn_str = "\n".join(sorted_vpns)

        return State(link=link, name=name, internet=internet, vpn=vpn_str)

    except Exception as e:
        logger.debug("D-Bus network query error: %s", e)
        return None

def _read_via_nmcli() -> Optional[State]:
    if not shutil.which("nmcli"):
        return None

    try:
        res_conn = subprocess.run(
            ["nmcli", "-t", "-f", "CONNECTIVITY", "general", "status"],
            capture_output=True,
            text=True,
            timeout=1.5,
            check=False,
        )
        internet = "full" in res_conn.stdout.lower()

        res_act = subprocess.run(
            ["nmcli", "-t", "-f", "TYPE,NAME,DEVICE,STATE", "connection", "show", "--active"],
            capture_output=True,
            text=True,
            timeout=1.5,
            check=False,
        )

        link = Link.NONE
        name = ""
        vpn_names: set[str] = set()
        covered_devices: set[str] = set()

        if res_act.returncode == 0:
            for raw_line in res_act.stdout.strip().splitlines():
                parts = raw_line.split(":")
                if len(parts) < 3:
                    continue
                c_type = parts[0].strip().lower()
                c_name = parts[1].strip()
                c_dev = parts[2].strip()

                if c_type == "loopback" or c_dev == "lo":
                    continue

                if c_dev:
                    covered_devices.add(c_dev.lower())

                is_tunnel = (
                    c_type in ("vpn", "wireguard", "tun", "tap", "ppp")
                    or any(h in c_type for h in ("wireguard", "tun", "tap", "vpn"))
                    or any(h in c_name.lower() for h in VPN_HINTS)
                )

                if is_tunnel:
                    vpn_names.add(c_name)
                    continue

                if link == Link.NONE:
                    if any(k in c_type for k in ("wireless", "wifi", "802-11")):
                        link = Link.WIFI
                        name = c_name
                    elif any(k in c_type for k in ("ethernet", "802-3", "wired")):
                        link = Link.WIRED
                        name = c_name
                    elif any(k in c_type for k in ("gsm", "cdma", "wwan", "modem", "mobile")):
                        link = Link.MOBILE
                        name = c_name

        if link == Link.WIFI:
            try:
                res_wifi = subprocess.run(
                    ["nmcli", "-t", "-f", "active,ssid", "dev", "wifi"],
                    capture_output=True,
                    text=True,
                    timeout=1.5,
                    check=False,
                )
                if res_wifi.returncode == 0:
                    for line in res_wifi.stdout.strip().splitlines():
                        if line.startswith("yes:"):
                            ssid = line[4:].strip()
                            if ssid:
                                name = ssid
                                break
            except Exception:
                pass

        for kernel_tunnel in _get_active_vpn_interfaces():
            kt_lower = kernel_tunnel.lower()
            if kt_lower in covered_devices:
                continue
            if not any(kt_lower == v.lower() or kt_lower in v.lower() for v in vpn_names):
                vpn_names.add(kernel_tunnel)

        sorted_vpns = sorted(vpn_names)
        vpn_str = "\n".join(sorted_vpns)

        return State(link=link, name=name, internet=internet, vpn=vpn_str)

    except Exception as e:
        logger.debug("nmcli network query error: %s", e)
        return None

def _read_via_sysfs() -> State:
    link = Link.NONE
    name = ""
    internet = False

    tunnels = _get_active_vpn_interfaces()
    vpn_str = "\n".join(sorted(tunnels))

    try:
        with open("/proc/net/route", "r") as f:
            for line in f.readlines()[1:]:
                fields = line.strip().split()
                if len(fields) >= 2 and fields[1] == "00000000":
                    iface = fields[0]
                    if iface.startswith("wl") or "wifi" in iface:
                        link = Link.WIFI
                        name = iface
                    elif iface.startswith("en") or iface.startswith("eth"):
                        link = Link.WIRED
                        name = iface
                    elif iface.startswith("ww"):
                        link = Link.MOBILE
                        name = iface
                    internet = True
                    break
    except Exception:
        pass

    return State(link=link, name=name, internet=internet, vpn=vpn_str)

def read_network_state() -> State:
    state = _read_via_dbus()
    if state is not None:
        return state

    state = _read_via_nmcli()
    if state is not None:
        return state

    return _read_via_sysfs()

class NetworkService:

    def __init__(
        self,
        on_changed: Optional[Callable[[State, State], None]] = None,
        settle_delay: float = SETTLE_DELAY,
        auto_start: bool = True,
    ) -> None:
        self.settle_delay = max(0.1, float(settle_delay))
        self._lock = threading.RLock()
        self._listeners: list[Callable[[State, State], None]] = []
        if on_changed:
            self._listeners.append(on_changed)

        self._state: State = read_network_state()
        self._reading: bool = False
        self._settle_timer: Optional[threading.Timer] = None

        self._running: bool = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._nmcli_proc: Optional[subprocess.Popen] = None

        if auto_start:
            self.start()

    @property
    def state(self) -> State:
        with self._lock:
            return self._state

    def get_state(self) -> State:
        return self.state

    def add_listener(self, callback: Callable[[State, State], None]) -> None:
        with self._lock:
            if callback not in self._listeners:
                self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[State, State], None]) -> None:
        with self._lock:
            if callback in self._listeners:
                self._listeners.remove(callback)

    def poke(self) -> None:
        with self._lock:
            if self._settle_timer:
                try:
                    self._settle_timer.cancel()
                except Exception:
                    pass
            self._settle_timer = threading.Timer(self.settle_delay, self._on_settle_timeout)
            self._settle_timer.daemon = True
            self._settle_timer.start()

    def _on_settle_timeout(self) -> None:
        with self._lock:
            if self._reading:
                self.poke()
                return
            self._reading = True

        try:
            now = read_network_state()
        finally:
            with self._lock:
                self._reading = False

        with self._lock:
            if now == self._state:
                return
            was = self._state
            self._state = now
            listeners = list(self._listeners)

        for listener in listeners:
            try:
                listener(was, now)
            except Exception as e:
                logger.error("Error in NetworkService listener: %s", e)

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True

        self._monitor_thread = threading.Thread(
            target=self._monitor_worker,
            daemon=True,
            name="NetworkServiceMonitor",
        )
        self._monitor_thread.start()

    def stop(self) -> None:
        with self._lock:
            self._running = False
            if self._settle_timer:
                try:
                    self._settle_timer.cancel()
                except Exception:
                    pass
                self._settle_timer = None

        if self._nmcli_proc:
            try:
                self._nmcli_proc.terminate()
            except Exception:
                pass
            self._nmcli_proc = None

    def _monitor_worker(self) -> None:
        has_nmcli = shutil.which("nmcli") is not None

        while self._running:
            if has_nmcli:
                try:
                    self._nmcli_proc = subprocess.Popen(
                        ["nmcli", "monitor"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,
                        text=True,
                        bufsize=1,
                    )
                    while self._running and self._nmcli_proc.stdout:
                        line = self._nmcli_proc.stdout.readline()
                        if not line:
                            break
                        self.poke()
                except Exception as e:
                    logger.debug("nmcli monitor exception: %s", e)
                finally:
                    if self._nmcli_proc:
                        try:
                            self._nmcli_proc.terminate()
                        except Exception:
                            pass
                        self._nmcli_proc = None

            poll_count = 0
            while self._running and poll_count < 10:
                time.sleep(2.0)
                poll_count += 1
                current = read_network_state()
                if current != self._state:
                    self.poke()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    print("=" * 60)
    print("DynamicIsland Linux - NetworkService Test")
    print("=" * 60)

    current_state = read_network_state()
    print(f"Link Type : {current_state.link.name} ({current_state.link.value})")
    print(f"Profile   : {current_state.name or '<None>'}")
    print(f"Internet  : {'Yes (Full Connectivity)' if current_state.internet else 'No Internet'}")
    vpn_list = current_state.vpn.split("\n") if current_state.vpn else []
    print(f"VPN Tunnels ({len(vpn_list)} active):")
    for v in vpn_list:
        print(f"  • {v}")

    events_received: list[tuple[State, State]] = []

    def on_network_change(was: State, now: State) -> None:
        print(f"\n[EVENT] Network changed!")
        print(f"  Was: Link={was.link.name}, Name='{was.name}', Internet={was.internet}, VPNs={len(was.vpn.splitlines())}")
        print(f"  Now: Link={now.link.name}, Name='{now.name}', Internet={now.internet}, VPNs={len(now.vpn.splitlines())}")
        events_received.append((was, now))

    service = NetworkService(on_changed=on_network_change, settle_delay=0.3, auto_start=False)
    print("\nInitial Service State:", service.state)
    print("Testing settle debounce poke()...")
    service.poke()
    time.sleep(0.4)
    print(f"Debounce cycle complete. Events triggered: {len(events_received)} (expected 0 if state unchanged)")
    service.stop()
    print("=" * 60)
