#!/usr/bin/env python3

from __future__ import annotations

import base64
import colorsys
import hashlib
import json
import logging
import shutil
import subprocess
import threading
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from PIL import Image
from gi.repository import Gio, GLib

logger = logging.getLogger(__name__)

COVER_CACHE_DIR = Path("/tmp/dynamic_island_covers")

TURN_DEGREES: float = 28.0

DEFAULT_PALETTE: list[tuple[float, float, float]] = [(1.0, 1.0, 1.0)]
DEFAULT_ACCENT: tuple[float, float, float] = (1.0, 1.0, 1.0)

def turn_hue(rgb: tuple[float, float, float], degrees: float) -> tuple[float, float, float]:
    r, g, b = rgb
    h, lum, s = colorsys.rgb_to_hls(r, g, b)
    new_h = (h + degrees / 360.0) % 1.0
    nr, ng, nb = colorsys.hls_to_rgb(new_h, lum, s)
    return (max(0.0, min(1.0, nr)), max(0.0, min(1.0, ng)), max(0.0, min(1.0, nb)))

def lift_color(rgb: tuple[float, float, float]) -> tuple[float, float, float]:
    r, g, b = rgb
    peak = max(r, max(g, b))
    if peak < 0.01:
        return (0.75, 0.75, 0.75)
    
    if peak < 0.50:
        factor = 0.50 / peak
        r, g, b = r * factor, g * factor, b * factor

    h, lum, s = colorsys.rgb_to_hls(r, g, b)
    if lum < 0.35:
        lum = 0.35
        r, g, b = colorsys.hls_to_rgb(h, lum, s)

    white_blend = 0.15
    r = r + (1.0 - r) * white_blend
    g = g + (1.0 - g) * white_blend
    b = b + (1.0 - b) * white_blend
    return (max(0.0, min(1.0, r)), max(0.0, min(1.0, g)), max(0.0, min(1.0, b)))

def color_distance(c1: tuple[float, float, float], c2: tuple[float, float, float]) -> float:
    return (sum((a - b) ** 2 for a, b in zip(c1, c2))) ** 0.5

def extract_dominant_palette(
    image_path: str | Path,
) -> tuple[list[tuple[float, float, float]], tuple[float, float, float]]:
    path_obj = Path(image_path)
    if not path_obj.exists() or path_obj.stat().st_size == 0:
        return list(DEFAULT_PALETTE), DEFAULT_ACCENT

    try:
        with Image.open(path_obj) as img:
            if img.mode in ("RGBA", "LA") or ("transparency" in img.info):
                bg = Image.new("RGB", img.size, (24, 24, 28))
                alpha = img.convert("RGBA").split()[3]
                bg.paste(img.convert("RGB"), mask=alpha)
                img = bg
            else:
                img = img.convert("RGB")

            img = img.resize((64, 64), Image.Resampling.BILINEAR)

            quantized = img.quantize(colors=16, method=Image.Quantize.MEDIANCUT)
            raw_palette = quantized.getpalette() or []
            color_counts = quantized.getcolors() or []

        if not color_counts:
            return list(DEFAULT_PALETTE), DEFAULT_ACCENT

        entries: list[dict[str, Any]] = []
        for count, idx in color_counts:
            r = raw_palette[idx * 3] / 255.0
            g = raw_palette[idx * 3 + 1] / 255.0
            b = raw_palette[idx * 3 + 2] / 255.0
            h, lum, s = colorsys.rgb_to_hls(r, g, b)
            entries.append({"rgb": (r, g, b), "count": count, "h": h, "l": lum, "s": s})

        by_count = sorted(entries, key=lambda e: e["count"], reverse=True)
        dominant_bg = by_count[0]["rgb"] if by_count else (0.08, 0.08, 0.08)

        accent_candidates: list[tuple[float, tuple[float, float, float]]] = []
        for e in entries:
            is_extreme_black = (e["l"] < 0.12) or (max(e["rgb"]) < 0.14)
            is_extreme_white = (e["l"] > 0.88) and (e["s"] < 0.20)
            is_extreme_gray = (e["s"] < 0.08)

            if not (is_extreme_black or is_extreme_white or is_extreme_gray):
                score = (e["s"] ** 1.6) * (1.0 - abs(e["l"] - 0.55)) * (e["count"] ** 0.5)
                accent_candidates.append((score, e["rgb"]))

        accent_candidates.sort(key=lambda x: x[0], reverse=True)

        if accent_candidates:
            primary_accent = lift_color(accent_candidates[0][1])
        else:
            primary_accent = lift_color(dominant_bg) if max(dominant_bg) > 0.1 else (1.0, 1.0, 1.0)

        secondary: Optional[tuple[float, float, float]] = None
        for _, candidate in accent_candidates[1:]:
            lifted = lift_color(candidate)
            if color_distance(lifted, primary_accent) > 0.24:
                secondary = lifted
                break

        if not secondary:
            secondary = lift_color(turn_hue(primary_accent, TURN_DEGREES))

        tertiary: Optional[tuple[float, float, float]] = None
        for _, candidate in accent_candidates[1:]:
            lifted = lift_color(candidate)
            if color_distance(lifted, primary_accent) > 0.20 and color_distance(lifted, secondary) > 0.20:
                tertiary = lifted
                break

        if not tertiary:
            tertiary = lift_color(turn_hue(primary_accent, -TURN_DEGREES))

        palette = [primary_accent, secondary, dominant_bg, tertiary]
        return palette, primary_accent

    except Exception as e:
        logger.warning("Error extracting palette from %s: %s", image_path, e)
        return list(DEFAULT_PALETTE), DEFAULT_ACCENT

def resolve_desktop_friendly_name(desktop_entry: str, identity: str = "", bus_name: str = "") -> str:
    if identity and identity.strip():
        return identity.strip()

    entry_clean = desktop_entry.strip()
    if entry_clean:
        candidates = [f"{entry_clean}.desktop", entry_clean]
        search_dirs = [
            Path.home() / ".local/share/applications",
            Path("/usr/local/share/applications"),
            Path("/usr/share/applications"),
            Path.home() / ".local/share/flatpak/exports/share/applications",
            Path("/var/lib/flatpak/exports/share/applications"),
        ]
        for sdir in search_dirs:
            for cand in candidates:
                cand_path = sdir / cand
                if cand_path.is_file():
                    try:
                        with open(cand_path, "r", encoding="utf-8", errors="ignore") as f:
                            in_desktop_entry = False
                            for line in f:
                                line = line.strip()
                                if line == "[Desktop Entry]":
                                    in_desktop_entry = True
                                elif line.startswith("[") and in_desktop_entry:
                                    break
                                elif in_desktop_entry and line.startswith("Name="):
                                    name_val = line.split("=", 1)[1].strip()
                                    if name_val:
                                        return name_val
                    except Exception:
                        pass

    bus_part = bus_name
    if bus_part.startswith("org.mpris.MediaPlayer2."):
        bus_part = bus_part[len("org.mpris.MediaPlayer2."):]
    bus_part = bus_part.split(".instance")[0]
    bus_part = bus_part.split(".")[0]

    known_map = {
        "spotify": "Spotify",
        "firefox": "Firefox",
        "chromium": "Chromium",
        "chrome": "Google Chrome",
        "google-chrome": "Google Chrome",
        "vlc": "VLC",
        "mpv": "mpv",
        "ayugramdesktop": "AyuGram Desktop",
        "ayugram": "AyuGram",
        "telegramdesktop": "Telegram",
        "rhythmbox": "Rhythmbox",
        "audacious": "Audacious",
        "amberol": "Amberol",
        "elisa": "Elisa",
        "clementine": "Clementine",
        "strawberry": "Strawberry",
    }
    return known_map.get(bus_part.lower(), bus_part.capitalize() if bus_part else "Media Player")

@dataclass
class PlayerSession:
    bus_name: str
    owner: str = ""
    identity: str = ""
    desktop_entry: str = ""
    friendly_name: str = ""
    is_playing: bool = False
    playback_status: str = "Stopped"
    title: str = ""
    artist: str = ""
    album: str = ""
    art_url: str = ""
    art_path: Optional[str] = None
    duration: float = 0.0
    position: float = 0.0
    position_at: float = field(default_factory=time.monotonic)
    rate: float = 1.0
    volume: float = 1.0
    can_go_next: bool = False
    can_go_previous: bool = False
    can_play: bool = False
    can_pause: bool = False
    can_seek: bool = False
    can_control: bool = False
    can_raise: bool = False
    track_id: Optional[str] = None
    last_active: float = field(default_factory=time.monotonic)

class MediaService:

    def __init__(self, on_changed: Optional[Callable[[], None]] = None) -> None:
        self._lock = threading.RLock()
        self.changed: list[Callable[[], None]] = []
        if on_changed:
            self.changed.append(on_changed)

        COVER_CACHE_DIR.mkdir(parents=True, exist_ok=True)

        self._players: dict[str, PlayerSession] = {}
        self._owner_to_bus: dict[str, str] = {}
        self._bus_to_owner: dict[str, str] = {}
        self._chosen: Optional[str] = None
        self._current_player: Optional[str] = None

        self._title: str = ""
        self._artist: str = ""
        self._album: str = ""
        self._art_url: str = ""
        self._art_path: Optional[str] = None
        self._palette: list[tuple[float, float, float]] = list(DEFAULT_PALETTE)
        self._accent: tuple[float, float, float] = DEFAULT_ACCENT
        self._is_playing: bool = False
        self._duration: float = 0.0
        self._position: float = 0.0
        self._position_at: float = time.monotonic()
        self._rate: float = 1.0
        self._volume: float = 1.0
        self._source: str = ""
        self._source_id: str = ""
        self._version: int = 0
        self._last_playing: float = 0.0

        self._context = GLib.MainContext()
        self._loop = GLib.MainLoop(self._context)
        self._running: bool = True
        self._thread: Optional[threading.Thread] = None

        self._bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        self._scan_all_players_sync()
        self._pick_and_attach()

        self._thread = threading.Thread(target=self._worker_loop, daemon=True, name="MediaService-DBus")
        self._thread.start()

    @property
    def is_playing(self) -> bool:
        with self._lock:
            return self._is_playing

    @property
    def title(self) -> str:
        with self._lock:
            return self._title

    @property
    def artist(self) -> str:
        with self._lock:
            return self._artist

    @property
    def album(self) -> str:
        with self._lock:
            return self._album

    @property
    def art_url(self) -> str:
        with self._lock:
            return self._art_url

    @property
    def art_path(self) -> Optional[str]:
        with self._lock:
            return self._art_path

    @property
    def duration(self) -> float:
        with self._lock:
            return self._duration

    @property
    def position(self) -> float:
        with self._lock:
            pos = self._position
            if self._is_playing:
                delta = time.monotonic() - self._position_at
                pos += delta * self._rate
            if pos < 0.0:
                return 0.0
            if self._duration > 0.0 and pos > self._duration:
                return self._duration
            return pos

    @property
    def rate(self) -> float:
        with self._lock:
            return self._rate

    @property
    def volume(self) -> float:
        with self._lock:
            return self._volume

    @property
    def palette(self) -> list[tuple[float, float, float]]:
        with self._lock:
            return list(self._palette)

    @property
    def accent(self) -> tuple[float, float, float]:
        with self._lock:
            return self._accent

    @property
    def source(self) -> str:
        with self._lock:
            return self._source

    @property
    def source_id(self) -> str:
        with self._lock:
            return self._source_id

    @property
    def player_name(self) -> str:
        with self._lock:
            return self._current_player or ""

    @property
    def current_player(self) -> Optional[str]:
        with self._lock:
            return self._current_player

    @property
    def available_players(self) -> list[str]:
        with self._lock:
            return sorted(self._players.keys())

    @property
    def has_track(self) -> bool:
        with self._lock:
            return bool(self._current_player and self._title)

    @property
    def last_playing(self) -> float:
        with self._lock:
            return self._last_playing

    def add_callback(self, fn: Callable[[], None]) -> None:
        with self._lock:
            if fn not in self.changed:
                self.changed.append(fn)

    def remove_callback(self, fn: Callable[[], None]) -> None:
        with self._lock:
            if fn in self.changed:
                self.changed.remove(fn)

    def _notify_changed(self) -> None:
        with self._lock:
            callbacks = list(self.changed)
        for cb in callbacks:
            try:
                cb()
            except Exception as e:
                logger.error("Error in MediaService callback: %s", e)

    @staticmethod
    def around(color: tuple[float, float, float]) -> list[tuple[float, float, float]]:
        return [color, turn_hue(color, TURN_DEGREES), turn_hue(color, -TURN_DEGREES)]

    def _worker_loop(self) -> None:
        self._context.push_thread_default()
        try:
            self._bus.signal_subscribe(
                "org.freedesktop.DBus",
                "org.freedesktop.DBus",
                "NameOwnerChanged",
                "/org/freedesktop/DBus",
                None,
                Gio.DBusSignalFlags.NONE,
                self._on_name_owner_changed,
                None,
            )

            self._bus.signal_subscribe(
                None,
                "org.freedesktop.DBus.Properties",
                "PropertiesChanged",
                "/org/mpris/MediaPlayer2",
                None,
                Gio.DBusSignalFlags.NONE,
                self._on_properties_changed,
                None,
            )

            self._bus.signal_subscribe(
                None,
                "org.mpris.MediaPlayer2.Player",
                "Seeked",
                "/org/mpris/MediaPlayer2",
                None,
                Gio.DBusSignalFlags.NONE,
                self._on_seeked,
                None,
            )

            self._loop.run()
        except Exception as e:
            logger.error("Exception in MediaService worker loop: %s", e)
        finally:
            self._context.pop_thread_default()

    def _on_name_owner_changed(
        self,
        connection: Gio.DBusConnection,
        sender: str,
        object_path: str,
        interface_name: str,
        signal_name: str,
        parameters: GLib.Variant,
        user_data: Any,
    ) -> None:
        name, old_owner, new_owner = parameters.unpack()
        if not name.startswith("org.mpris.MediaPlayer2."):
            return

        with self._lock:
            if not new_owner:
                self._owner_to_bus.pop(old_owner, None)
                self._bus_to_owner.pop(name, None)
                self._players.pop(name, None)
                if self._chosen == name:
                    self._chosen = None
                if self._current_player == name:
                    self._current_player = None
                    self._pick_and_attach()
                self._notify_changed()
                return

            if old_owner:
                self._owner_to_bus.pop(old_owner, None)
            self._owner_to_bus[new_owner] = name
            self._bus_to_owner[name] = new_owner

        self._query_player_session(name, new_owner)
        with self._lock:
            session = self._players.get(name)
            if session and session.is_playing:
                self._yield(name)
            elif not self._current_player:
                self._pick_and_attach()
            self._notify_changed()

    def _on_properties_changed(
        self,
        connection: Gio.DBusConnection,
        sender: str,
        object_path: str,
        interface_name: str,
        signal_name: str,
        parameters: GLib.Variant,
        user_data: Any,
    ) -> None:
        iface, changed_props, _invalidated = parameters.unpack()
        bus_name = self._resolve_sender_bus_name(sender)
        if not bus_name:
            return

        with self._lock:
            session = self._players.get(bus_name)
            if not session:
                return

            needs_refresh = False

            if iface == "org.mpris.MediaPlayer2.Player":
                if "PlaybackStatus" in changed_props:
                    status = str(changed_props["PlaybackStatus"])
                    was_playing = session.is_playing
                    session.playback_status = status
                    session.is_playing = (status.lower() == "playing")
                    if was_playing and not session.is_playing:
                        session.position += (time.monotonic() - session.position_at) * session.rate
                        session.position_at = time.monotonic()
                    elif not was_playing and session.is_playing:
                        session.position_at = time.monotonic()

                    if session.is_playing:
                        session.last_active = time.monotonic()
                        if not was_playing and bus_name != self._chosen:
                            self._yield(bus_name)
                    needs_refresh = True

                if "Rate" in changed_props:
                    session.rate = float(changed_props["Rate"])
                    needs_refresh = True

                if "Volume" in changed_props:
                    session.volume = float(changed_props["Volume"])
                    needs_refresh = True

                if "Metadata" in changed_props:
                    self._parse_metadata(session, changed_props["Metadata"])
                    needs_refresh = True

                if "Position" in changed_props:
                    pos_us = int(changed_props["Position"])
                    session.position = pos_us / 1_000_000.0
                    session.position_at = time.monotonic()
                    needs_refresh = True

                flag_attrs = {
                    "CanGoNext": "can_go_next",
                    "CanGoPrevious": "can_go_previous",
                    "CanPlay": "can_play",
                    "CanPause": "can_pause",
                    "CanSeek": "can_seek",
                    "CanControl": "can_control",
                }
                for flag, attr_name in flag_attrs.items():
                    if flag in changed_props:
                        setattr(session, attr_name, bool(changed_props[flag]))

            elif iface == "org.mpris.MediaPlayer2":
                if "Identity" in changed_props:
                    session.identity = str(changed_props["Identity"])
                    session.friendly_name = resolve_desktop_friendly_name(
                        session.desktop_entry, session.identity, session.bus_name
                    )
                    needs_refresh = True
                if "DesktopEntry" in changed_props:
                    session.desktop_entry = str(changed_props["DesktopEntry"])
                    session.friendly_name = resolve_desktop_friendly_name(
                        session.desktop_entry, session.identity, session.bus_name
                    )
                    needs_refresh = True
                if "CanRaise" in changed_props:
                    session.can_raise = bool(changed_props["CanRaise"])

            if needs_refresh and self._current_player == bus_name:
                self._sync_current_from_session(session)
                self._notify_changed()

    def _on_seeked(
        self,
        connection: Gio.DBusConnection,
        sender: str,
        object_path: str,
        interface_name: str,
        signal_name: str,
        parameters: GLib.Variant,
        user_data: Any,
    ) -> None:
        pos_us = parameters.unpack()[0]
        bus_name = self._resolve_sender_bus_name(sender)
        with self._lock:
            if bus_name and bus_name in self._players:
                session = self._players[bus_name]
                session.position = pos_us / 1_000_000.0
                session.position_at = time.monotonic()
                if self._current_player == bus_name:
                    self._position = session.position
                    self._position_at = session.position_at
                    self._notify_changed()

    def _resolve_sender_bus_name(self, sender: str) -> Optional[str]:
        with self._lock:
            if sender in self._owner_to_bus:
                return self._owner_to_bus[sender]
            if sender.startswith("org.mpris.MediaPlayer2."):
                return sender
        try:
            for bname in list(self._players.keys()):
                owner = self._get_name_owner(bname)
                if owner == sender:
                    with self._lock:
                        self._owner_to_bus[sender] = bname
                        self._bus_to_owner[bname] = sender
                    return bname
        except Exception:
            pass
        return None

    def _get_name_owner(self, name: str) -> str:
        try:
            reply = self._bus.call_sync(
                "org.freedesktop.DBus",
                "/org/freedesktop/DBus",
                "org.freedesktop.DBus",
                "GetNameOwner",
                GLib.Variant("(s)", (name,)),
                GLib.VariantType("(s)"),
                Gio.DBusCallFlags.NONE,
                500,
                None,
            )
            return reply.unpack()[0]
        except Exception:
            return ""

    def _scan_all_players_sync(self) -> None:
        try:
            reply = self._bus.call_sync(
                "org.freedesktop.DBus",
                "/org/freedesktop/DBus",
                "org.freedesktop.DBus",
                "ListNames",
                None,
                GLib.VariantType("(as)"),
                Gio.DBusCallFlags.NONE,
                1000,
                None,
            )
            names = reply.unpack()[0]
            for name in names:
                if name.startswith("org.mpris.MediaPlayer2."):
                    owner = self._get_name_owner(name)
                    if owner:
                        with self._lock:
                            self._owner_to_bus[owner] = name
                            self._bus_to_owner[name] = owner
                    self._query_player_session(name, owner)
        except Exception as e:
            logger.error("Failed to scan MPRIS players: %s", e)

    def _query_player_session(self, bus_name: str, owner: str = "") -> None:
        session = PlayerSession(bus_name=bus_name, owner=owner)

        try:
            rep = self._bus.call_sync(
                bus_name,
                "/org/mpris/MediaPlayer2",
                "org.freedesktop.DBus.Properties",
                "GetAll",
                GLib.Variant("(s)", ("org.mpris.MediaPlayer2",)),
                GLib.VariantType("(a{sv})"),
                Gio.DBusCallFlags.NONE,
                800,
                None,
            )
            props = rep.unpack()[0]
            session.identity = str(props.get("Identity", ""))
            session.desktop_entry = str(props.get("DesktopEntry", ""))
            session.can_raise = bool(props.get("CanRaise", False))
        except Exception as e:
            logger.debug("Failed querying root props for %s: %s", bus_name, e)

        session.friendly_name = resolve_desktop_friendly_name(
            session.desktop_entry, session.identity, bus_name
        )

        try:
            rep = self._bus.call_sync(
                bus_name,
                "/org/mpris/MediaPlayer2",
                "org.freedesktop.DBus.Properties",
                "GetAll",
                GLib.Variant("(s)", ("org.mpris.MediaPlayer2.Player",)),
                GLib.VariantType("(a{sv})"),
                Gio.DBusCallFlags.NONE,
                800,
                None,
            )
            props = rep.unpack()[0]
            status = str(props.get("PlaybackStatus", "Stopped"))
            session.playback_status = status
            session.is_playing = (status.lower() == "playing")
            session.rate = float(props.get("Rate", 1.0))
            session.volume = float(props.get("Volume", 1.0))
            session.can_go_next = bool(props.get("CanGoNext", False))
            session.can_go_previous = bool(props.get("CanGoPrevious", False))
            session.can_play = bool(props.get("CanPlay", False))
            session.can_pause = bool(props.get("CanPause", False))
            session.can_seek = bool(props.get("CanSeek", False))
            session.can_control = bool(props.get("CanControl", False))

            if "Metadata" in props:
                self._parse_metadata(session, props["Metadata"])

            pos_us = int(props.get("Position", 0))
            if pos_us > 0:
                session.position = pos_us / 1_000_000.0
                session.position_at = time.monotonic()
        except Exception as e:
            logger.debug("Failed querying player props for %s: %s", bus_name, e)

        with self._lock:
            self._players[bus_name] = session

    def _parse_metadata(self, session: PlayerSession, meta: dict[str, Any]) -> None:
        old_title = session.title
        old_track_id = session.track_id

        new_title = str(meta.get("xesam:title", "") or "")
        track_id = meta.get("mpris:trackid")
        new_track_id = str(track_id) if track_id else None

        if (new_title and new_title != old_title) or (new_track_id and new_track_id != old_track_id):
            session.position = 0.0
            session.position_at = time.monotonic()

        session.title = new_title

        artists = meta.get("xesam:artist") or meta.get("xesam:albumArtist") or []
        if isinstance(artists, (list, tuple)):
            session.artist = ", ".join(str(a) for a in artists if a)
        else:
            session.artist = str(artists or "")

        session.album = str(meta.get("xesam:album", "") or "")

        track_id = meta.get("mpris:trackid")
        session.track_id = str(track_id) if track_id else None

        length_us = meta.get("mpris:length", 0)
        session.duration = max(0.0, float(length_us) / 1_000_000.0) if length_us else 0.0

        new_art_url = str(meta.get("mpris:artUrl", "") or "")
        if new_art_url or session.title != self._title:
            session.art_url = new_art_url
            session.art_path = self._process_art_url(new_art_url)

    def _process_art_url(self, art_url: str) -> Optional[str]:
        if not art_url:
            return None

        try:
            url_hash = hashlib.sha256(art_url.encode("utf-8")).hexdigest()[:16]

            if art_url.startswith("file://") or art_url.startswith("/"):
                if art_url.startswith("file://"):
                    parsed = urllib.parse.urlparse(art_url)
                    local_path = Path(urllib.parse.unquote(parsed.path))
                else:
                    local_path = Path(art_url)

                if local_path.is_file():
                    cached_file = COVER_CACHE_DIR / f"{url_hash}{local_path.suffix or '.jpg'}"
                    if not cached_file.exists():
                        try:
                            shutil.copyfile(local_path, cached_file)
                        except Exception:
                            return str(local_path)
                    return str(cached_file)

            elif art_url.startswith("data:image/"):
                cached_file = COVER_CACHE_DIR / f"{url_hash}.png"
                if not cached_file.exists():
                    _header, data = art_url.split(",", 1)
                    img_bytes = base64.b64decode(data)
                    with open(cached_file, "wb") as f:
                        f.write(img_bytes)
                return str(cached_file)

            elif art_url.startswith("http://") or art_url.startswith("https://"):
                ext = ".jpg"
                clean_path = urllib.parse.urlsplit(art_url).path
                if "." in clean_path:
                    cand_ext = "." + clean_path.rsplit(".", 1)[-1].lower()
                    if cand_ext in (".jpg", ".jpeg", ".png", ".webp"):
                        ext = cand_ext
                cached_file = COVER_CACHE_DIR / f"{url_hash}{ext}"
                if cached_file.exists() and cached_file.stat().st_size > 0:
                    return str(cached_file)

                threading.Thread(
                    target=self._async_download_cover,
                    args=(art_url, cached_file),
                    daemon=True,
                ).start()
                return None

        except Exception as e:
            logger.debug("Failed processing art URL %s: %s", art_url, e)
        return None

    def _async_download_cover(self, url: str, target_path: Path) -> None:
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "DynamicIsland/1.0 (Linux Wayland MPRIS)"},
            )
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                data = resp.read()
            with open(target_path, "wb") as f:
                f.write(data)

            with self._lock:
                if self._art_url == url:
                    self._art_path = str(target_path)
                    self._palette, self._accent = extract_dominant_palette(target_path)
                    self._notify_changed()
        except Exception as e:
            logger.debug("Async cover download failed for %s: %s", url, e)

    def _yield(self, playing_bus_name: str) -> None:
        if self._chosen != playing_bus_name:
            self._chosen = None
            self._attach_player(playing_bus_name)
            self._notify_changed()

    def _pick_player(self) -> Optional[str]:
        if self._chosen and self._chosen in self._players:
            return self._chosen
        self._chosen = None

        for bname, sess in self._players.items():
            if sess.is_playing:
                return bname

        if self._players:
            sorted_by_activity = sorted(
                self._players.items(), key=lambda item: item[1].last_active, reverse=True
            )
            return sorted_by_activity[0][0]

        return None

    def _pick_and_attach(self) -> None:
        picked = self._pick_player()
        self._attach_player(picked)

    def _attach_player(self, bus_name: Optional[str]) -> None:
        with self._lock:
            self._version += 1
            if not bus_name or bus_name not in self._players:
                self._current_player = None
                self._title = ""
                self._artist = ""
                self._album = ""
                self._art_url = ""
                self._art_path = None
                self._palette = list(DEFAULT_PALETTE)
                self._accent = DEFAULT_ACCENT
                self._is_playing = False
                self._duration = 0.0
                self._position = 0.0
                self._position_at = time.monotonic()
                self._rate = 1.0
                self._volume = 1.0
                self._source = ""
                self._source_id = ""
                return

            self._current_player = bus_name
            session = self._players[bus_name]
            self._sync_current_from_session(session)

    def _sync_current_from_session(self, session: PlayerSession) -> None:
        was_playing = self._is_playing
        self._title = session.title
        self._artist = session.artist
        self._album = session.album
        self._duration = session.duration
        self._rate = session.rate if session.rate > 0 else 1.0
        self._volume = session.volume
        self._source = session.friendly_name
        self._source_id = session.desktop_entry or session.bus_name

        if session.is_playing != was_playing:
            self._position = session.position
            self._position_at = time.monotonic()
            self._is_playing = session.is_playing
            if self._is_playing:
                self._last_playing = time.monotonic()
        else:
            self._position = session.position
            self._position_at = session.position_at

        if session.art_path and session.art_path != self._art_path:
            self._art_url = session.art_url
            self._art_path = session.art_path
            self._palette, self._accent = extract_dominant_palette(session.art_path)
        elif not session.art_path:
            self._art_url = session.art_url
            self._art_path = None
            self._palette = list(DEFAULT_PALETTE)
            self._accent = DEFAULT_ACCENT

    def next_player(self) -> bool:
        return self.switch(1)

    def prev_player(self) -> bool:
        return self.switch(-1)

    def switch(self, direction: int) -> bool:
        with self._lock:
            players = self.available_players
            if len(players) < 2:
                return False

            current = self._current_player
            try:
                at = players.index(current) if current in players else -1
            except ValueError:
                at = -1

            if at < 0:
                next_idx = 0 if direction > 0 else len(players) - 1
            else:
                next_idx = (at + direction) % len(players)

            self._chosen = players[next_idx]
            self._attach_player(self._chosen)
            self._notify_changed()
            return True

    def _call_player_method(self, method: str, params: Optional[GLib.Variant] = None) -> bool:
        with self._lock:
            player = self._current_player
        if not player:
            return False

        try:
            self._bus.call_sync(
                player,
                "/org/mpris/MediaPlayer2",
                "org.mpris.MediaPlayer2.Player",
                method,
                params,
                None,
                Gio.DBusCallFlags.NONE,
                1500,
                None,
            )
            return True
        except Exception as e:
            logger.debug("Player method %s failed on %s: %s", method, player, e)
            return False

    def play_pause(self) -> None:
        self._call_player_method("PlayPause")

    def toggle_play(self) -> None:
        self.play_pause()

    def play(self) -> None:
        self._call_player_method("Play")

    def pause(self) -> None:
        self._call_player_method("Pause")

    def next(self) -> None:
        self._call_player_method("Next")

    def previous(self) -> None:
        self._call_player_method("Previous")

    def stop(self) -> None:
        self._call_player_method("Stop")

    def seek(self, position_seconds: float) -> None:
        with self._lock:
            if not self._current_player or self._duration <= 0.0:
                return
            session = self._players.get(self._current_player)
            track_id = session.track_id if session else None
            player = self._current_player
            target_sec = max(0.0, min(self._duration, float(position_seconds)))

        target_us = int(target_sec * 1_000_000)
        success = False

        if track_id and isinstance(track_id, str) and track_id.startswith("/"):
            try:
                self._bus.call_sync(
                    player,
                    "/org/mpris/MediaPlayer2",
                    "org.mpris.MediaPlayer2.Player",
                    "SetPosition",
                    GLib.Variant("(ox)", (track_id, target_us)),
                    None,
                    Gio.DBusCallFlags.NONE,
                    1200,
                    None,
                )
                success = True
            except Exception as e:
                logger.debug("SetPosition failed, trying Seek: %s", e)

        if not success:
            current_sec = self.position
            offset_us = int((target_sec - current_sec) * 1_000_000)
            try:
                self._bus.call_sync(
                    player,
                    "/org/mpris/MediaPlayer2",
                    "org.mpris.MediaPlayer2.Player",
                    "Seek",
                    GLib.Variant("(x)", (offset_us,)),
                    None,
                    Gio.DBusCallFlags.NONE,
                    1200,
                    None,
                )
                success = True
            except Exception as e:
                logger.warning("Seek failed on %s: %s", player, e)

        if success:
            with self._lock:
                self._position = target_sec
                self._position_at = time.monotonic()
                if session:
                    session.position = target_sec
                    session.position_at = self._position_at
            self._notify_changed()

    def seek_fraction(self, fraction: float) -> None:
        with self._lock:
            dur = self._duration
        if dur > 0.0:
            self.seek(max(0.0, min(1.0, float(fraction))) * dur)

    def set_volume(self, level: float) -> None:
        with self._lock:
            player = self._current_player
        if not player:
            return

        level_val = max(0.0, min(1.0, float(level)))
        try:
            self._bus.call_sync(
                player,
                "/org/mpris/MediaPlayer2",
                "org.freedesktop.DBus.Properties",
                "Set",
                GLib.Variant("(ssv)", ("org.mpris.MediaPlayer2.Player", "Volume", GLib.Variant("d", level_val))),
                None,
                Gio.DBusCallFlags.NONE,
                1000,
                None,
            )
            with self._lock:
                self._volume = level_val
                if player in self._players:
                    self._players[player].volume = level_val
            self._notify_changed()
        except Exception as e:
            logger.debug("Failed setting volume: %s", e)

    def raise_player(self) -> None:
        with self._lock:
            player = self._current_player
            session = self._players.get(player) if player else None
            desktop_entry = session.desktop_entry if session else ""
            identity = session.identity if session else ""
            title = self._title

        if player:
            try:
                self._bus.call_sync(
                    player,
                    "/org/mpris/MediaPlayer2",
                    "org.mpris.MediaPlayer2",
                    "Raise",
                    None,
                    None,
                    Gio.DBusCallFlags.NONE,
                    1000,
                    None,
                )
            except Exception as e:
                logger.debug("D-Bus Raise failed: %s", e)

        if shutil.which("hyprctl"):
            try:
                res = subprocess.run(
                    ["hyprctl", "clients", "-j"],
                    capture_output=True,
                    text=True,
                    timeout=1.5,
                    check=False,
                )
                if res.returncode == 0 and res.stdout:
                    clients = json.loads(res.stdout)
                    matched_addr: Optional[str] = None
                    matched_class: Optional[str] = None

                    player_clean = player.split(".")[-1].lower() if player else ""
                    targets = [
                        t.lower()
                        for t in (desktop_entry, player_clean, identity)
                        if t
                    ]

                    for c in clients:
                        cls = c.get("class", "").lower()
                        initial_cls = c.get("initialClass", "").lower()
                        win_title = c.get("title", "").lower()
                        addr = c.get("address")

                        for t in targets:
                            if t in cls or t in initial_cls:
                                matched_addr = addr
                                matched_class = c.get("class")
                                break
                        if matched_addr:
                            if title and title.lower() in win_title:
                                break

                    if matched_addr:
                        subprocess.run(
                            ["hyprctl", "dispatch", "focuswindow", f"address:{matched_addr}"],
                            capture_output=True,
                            timeout=1.0,
                            check=False,
                        )
                    elif matched_class:
                        subprocess.run(
                            ["hyprctl", "dispatch", "focuswindow", f"class:{matched_class}"],
                            capture_output=True,
                            timeout=1.0,
                            check=False,
                        )
                    elif desktop_entry:
                        subprocess.run(
                            ["hyprctl", "dispatch", "focuswindow", f"class:{desktop_entry}"],
                            capture_output=True,
                            timeout=1.0,
                            check=False,
                        )
            except Exception as e:
                logger.debug("Hyprland focuswindow dispatch failed: %s", e)

    def close(self) -> None:
        self._running = False
        try:
            self._loop.quit()
        except Exception:
            pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    print("=" * 60)
    print("DynamicIsland MPRIS MediaService Test")
    print("=" * 60)

    event_count = 0
    def on_change():
        global event_count
        event_count += 1
        print(f"[CALLBACK] State changed (#{event_count})")

    service = MediaService(on_changed=on_change)

    time.sleep(0.5)

    print(f"Available players ({len(service.available_players)}): {service.available_players}")
    print(f"Active player: {service.player_name}")
    print(f"Source App: {service.source} (ID: {service.source_id})")
    print(f"Has track: {service.has_track}")
    print(f"Title: '{service.title}'")
    print(f"Artist: '{service.artist}'")
    print(f"Album: '{service.album}'")
    print(f"Playing: {service.is_playing}")
    print(f"Duration: {service.duration:.1f}s")
    print(f"Position (initial): {service.position:.2f}s")
    print(f"Volume: {service.volume:.2f}")
    print(f"Accent: {tuple(round(x, 3) for x in service.accent)}")
    print(f"Palette: {[tuple(round(x, 3) for x in c) for c in service.palette]}")

    print("\nTesting position interpolation over 1.2 seconds:")
    p0 = service.position
    time.sleep(1.2)
    p1 = service.position
    print(f"  t=0.0s: {p0:.2f}s")
    print(f"  t=1.2s: {p1:.2f}s (delta = {p1 - p0:.2f}s, is_playing={service.is_playing})")

    print("\nTesting cover art cache & dominant palette extraction:")
    test_img_path = Path("/tmp/dynamic_island_covers/test_cover.png")
    test_img = Image.new("RGB", (64, 64), (18, 22, 36))
    for x in range(15, 35):
        for y in range(15, 35):
            test_img.putpixel((x, y), (230, 45, 60))
    for x in range(35, 55):
        for y in range(35, 55):
            test_img.putpixel((x, y), (250, 195, 35))
    test_img.save(test_img_path)

    test_pal, test_acc = extract_dominant_palette(test_img_path)
    print(f"  Synthetic cover palette colors: {len(test_pal)}")
    print(f"  Primary accent: {tuple(round(x, 3) for x in test_acc)}")
    for i, col in enumerate(test_pal):
        print(f"    Color {i}: {tuple(round(x, 3) for x in col)}")

    around_cols = MediaService.around(test_acc)
    print(f"  MediaService.around(accent): {[tuple(round(x, 3) for x in c) for c in around_cols]}")

    print("\nTesting player cycling:")
    switched = service.next_player()
    print(f"  next_player() returned: {switched}")
    switched_back = service.prev_player()
    print(f"  prev_player() returned: {switched_back}")

    service.close()
    print("\nMediaService test completed successfully!")
