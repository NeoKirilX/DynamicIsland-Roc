#!/usr/bin/env python3

from __future__ import annotations

import base64
import colorsys
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
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

xdg_cache = os.environ.get("XDG_CACHE_HOME")
COVER_CACHE_DIR = (
    Path(xdg_cache) if xdg_cache else (Path.home() / ".cache")
) / "dynamic-island" / "covers"

TURN_DEGREES: float = 28.0
MIN_MUSIC_DURATION: float = 30.0

DEFAULT_PALETTE: list[tuple[float, float, float]] = [(1.0, 1.0, 1.0)]
DEFAULT_ACCENT: tuple[float, float, float] = (1.0, 1.0, 1.0)

def crop_to_square(src_path: Path, dst_path: Optional[Path] = None) -> bool:
    if Image is None or not src_path.exists():
        return False
    target = dst_path or src_path
    try:
        with Image.open(src_path) as im:
            w, h = im.size
            if w == h and (dst_path is None or src_path == dst_path):
                return True
            min_dim = min(w, h)
            left = (w - min_dim) // 2
            top = (h - min_dim) // 2
            right = left + min_dim
            bottom = top + min_dim
            cropped = im.crop((left, top, right, bottom))

            if cropped.mode in ("RGBA", "LA", "P"):
                bg = Image.new("RGB", cropped.size, (24, 24, 28))
                if cropped.mode == "P":
                    cropped = cropped.convert("RGBA")
                bg.paste(cropped, mask=cropped.split()[-1])
                cropped = bg
            elif cropped.mode != "RGB":
                cropped = cropped.convert("RGB")

            tmp_target = target.with_suffix(".tmp.jpg")
            cropped.save(tmp_target, format="JPEG", quality=92)
            tmp_target.replace(target)
            return True
    except Exception as e:
        logger.debug("Crop to square failed for %s -> %s: %s", src_path, target, e)
        return False

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
        xdg_data = os.environ.get("XDG_DATA_HOME")
        local_data = Path(xdg_data) if xdg_data else (Path.home() / ".local/share")
        search_dirs = [
            local_data / "applications",
            Path("/usr/local/share/applications"),
            Path("/usr/share/applications"),
            local_data / "flatpak/exports/share/applications",
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

TRACK_TAGS_PATTERN = re.compile(
    r"\s*[\(\[][^\)\]]*\b(?:"
    r"official\s*(music|video|audio)?|"
    r"video|"
    r"audio|"
    r"lyrics?|"
    r"visuali[sz]er|"
    r"remaster(?:ed)?|"
    r"hd|hq|4k|8k|"
    r"mv|"
    r"feat(?:uring|\.)?|"
    r"ft\.?|"
    r"prod\.?|"
    r"edit|"
    r"mix|"
    r"version|"
    r"cover|"
    r"sped\s*up|"
    r"speed\s*up|"
    r"spedup|"
    r"slowed\s*(?:[\+&]\s*reverb)?|"
    r"клип|"
    r"премьера|"
    r"аудио"
    r")\b[^\)\]]*[\)\]]",
    re.IGNORECASE,
)
TRACK_PIPES_PATTERN = re.compile(r"\s*\|[^|]*\|\s*|\s+\|\s.*$")
TRACK_JUNK_CHARS = " \t\r\n-–—―:()[]{}"

def clean_track_title(raw_title: str) -> str:
    if not raw_title:
        return ""
    cleaned = TRACK_TAGS_PATTERN.sub("", raw_title)
    cleaned = TRACK_PIPES_PATTERN.sub(" ", cleaned)
    cleaned = re.sub(r"[\(\[]\s*[\)\]]", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = cleaned.strip(TRACK_JUNK_CHARS)
    return cleaned

def format_display_title(
    title: str,
    artist: Optional[str] = None,
    capitalize_first: bool = True,
) -> str:
    songname = clean_track_title(title) if title else ""
    if not songname:
        return ""
    if capitalize_first:
        for idx, ch in enumerate(songname):
            if ch.isalpha():
                songname = songname[:idx] + ch.upper() + songname[idx + 1 :]
                break
    author = artist.strip() if artist else ""
    if not author:
        return songname
    return f"{songname} — {author}"

def get_track_cache_key(artist: str, title: str) -> str:
    art = artist.strip()
    tit = clean_track_title(title).strip() or title.strip()
    if not art and " - " in tit:
        parts = tit.split(" - ", 1)
        art = parts[0].strip()
        tit = clean_track_title(parts[1]).strip() or parts[1].strip()

    if art and tit:
        norm = f"{art.lower()} - {tit.lower()}"
    elif tit:
        norm = tit.lower()
    elif art:
        norm = art.lower()
    else:
        return ""

    return hashlib.sha256(norm.encode("utf-8")).hexdigest()

def get_track_cache_keys(artist: str, title: str) -> list[str]:
    keys: list[str] = []
    primary = get_track_cache_key(artist, title)
    if primary:
        keys.append(primary)

    art_raw = artist.strip().lower()
    tit_raw = title.strip().lower()
    if not art_raw and " - " in tit_raw:
        parts = tit_raw.split(" - ", 1)
        art_raw = parts[0].strip()
        tit_raw = parts[1].strip()
    if art_raw and tit_raw:
        raw_norm = f"{art_raw} - {tit_raw}"
    elif tit_raw:
        raw_norm = tit_raw
    elif art_raw:
        raw_norm = art_raw
    else:
        raw_norm = ""

    if raw_norm:
        raw_key = hashlib.sha256(raw_norm.encode("utf-8")).hexdigest()
        if raw_key not in keys:
            keys.append(raw_key)

    return keys

def find_cached_cover(artist: str, title: str) -> Optional[Path]:
    if not artist and not title:
        return None
    for k in get_track_cache_keys(artist, title):
        for ext in (".jpg", ".jpeg", ".png", ".webp"):
            cand = COVER_CACHE_DIR / f"{k}{ext}"
            if cand.is_file() and cand.stat().st_size > 0:
                return cand
            cand_short = COVER_CACHE_DIR / f"{k[:16]}{ext}"
            if cand_short.is_file() and cand_short.stat().st_size > 0:
                return cand_short
            cand_ytdlp = COVER_CACHE_DIR / f"ytdlp_{k[:16]}{ext}"
            if cand_ytdlp.is_file() and cand_ytdlp.stat().st_size > 0:
                return cand_ytdlp
    return None

def find_cached_cover_by_url(art_url: str) -> Optional[Path]:
    if not art_url:
        return None
    h16 = hashlib.sha256(art_url.encode("utf-8")).hexdigest()[:16]
    h64 = hashlib.sha256(art_url.encode("utf-8")).hexdigest()
    for h in (h64, h16):
        for ext in (".jpg", ".jpeg", ".png", ".webp"):
            cand = COVER_CACHE_DIR / f"{h}{ext}"
            if cand.is_file() and cand.stat().st_size > 0:
                return cand
    return None

__all__ = [
    "MediaService",
    "PlayerSession",
    "clean_track_title",
    "format_display_title",
    "extract_dominant_palette",
    "resolve_desktop_friendly_name",
    "crop_to_square",
    "get_track_cache_key",
    "get_track_cache_keys",
    "find_cached_cover",
    "find_cached_cover_by_url",
    "COVER_CACHE_DIR",
]

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
    url: str = ""
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

        self._active_ytdlp_proc: Optional[subprocess.Popen] = None
        self._ytdlp_timer: Optional[threading.Timer] = None
        self._in_flight_queries: set[str] = set()
        self._in_flight_urls: set[str] = set()
        self._failed_queries: set[str] = set()
        self._failed_urls: set[str] = set()
        self._ytdlp_bin: Optional[str] = None

        self._context = GLib.MainContext()
        self._loop = GLib.MainLoop(self._context)
        self._poll_source: Optional[GLib.Source] = None
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
                rate = self._rate if self._rate > 0.0 else 1.0
                delta = time.monotonic() - self._position_at
                pos += delta * rate
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
            return sorted([
                bname for bname, sess in self._players.items()
                if not (0.0 < sess.duration < MIN_MUSIC_DURATION)
            ])

    @property
    def has_track(self) -> bool:
        with self._lock:
            if not (self._current_player and self._title):
                return False
            if 0.0 < self._duration < MIN_MUSIC_DURATION:
                return False
            return True

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

    def _query_player_position_sync(self, bus_name: str) -> Optional[float]:
        try:
            reply = self._bus.call_sync(
                bus_name,
                "/org/mpris/MediaPlayer2",
                "org.freedesktop.DBus.Properties",
                "Get",
                GLib.Variant("(ss)", ("org.mpris.MediaPlayer2.Player", "Position")),
                GLib.VariantType("(v)"),
                Gio.DBusCallFlags.NONE,
                250,
                None,
            )
            pos_us = reply.unpack()[0]
            return float(pos_us) / 1_000_000.0
        except Exception:
            return None

    def _on_poll_timer(self) -> bool:
        if not self._running:
            return False
        with self._lock:
            player = self._current_player
            if not player or player not in self._players:
                return True
            session = self._players[player]
            is_playing = session.is_playing
            old_pos = self._position
            if is_playing:
                rate = self._rate if self._rate > 0.0 else 1.0
                old_pos += (time.monotonic() - self._position_at) * rate

        real_pos = self._query_player_position_sync(player)
        if real_pos is None:
            return True

        now = time.monotonic()
        needs_notify = False
        with self._lock:
            if self._current_player != player:
                return True
            session = self._players.get(player)
            if not session:
                return True

            drift = real_pos - old_pos
            if abs(drift) >= 1.2:
                self._position = real_pos
                self._position_at = now
                session.position = real_pos
                session.position_at = now
                needs_notify = True

        if needs_notify:
            self._notify_changed()

        return True

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

            self._poll_source = GLib.timeout_source_new(500)
            self._poll_source.set_callback(self._on_poll_timer)
            self._poll_source.attach(self._context)

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
                    self._cancel_active_ytdlp()
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
                if not (0.0 < session.duration < MIN_MUSIC_DURATION):
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
                    real_pos = self._query_player_position_sync(bus_name)
                    if real_pos is not None:
                        session.position = real_pos
                        session.position_at = time.monotonic()
                    elif was_playing and not session.is_playing:
                        session.position += (time.monotonic() - session.position_at) * session.rate
                        session.position_at = time.monotonic()
                    elif not was_playing and session.is_playing:
                        session.position_at = time.monotonic()

                    if session.is_playing:
                        session.last_active = time.monotonic()
                        if not was_playing and bus_name != self._chosen:
                            if not (0.0 < session.duration < MIN_MUSIC_DURATION):
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
                    real_pos = self._query_player_position_sync(bus_name)
                    if real_pos is not None:
                        session.position = real_pos
                        session.position_at = time.monotonic()
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

            if needs_refresh:
                if self._current_player == bus_name:
                    if 0.0 < session.duration < MIN_MUSIC_DURATION:
                        self._pick_and_attach()
                    else:
                        self._sync_current_from_session(session)
                    self._notify_changed()
                elif session.is_playing and not (0.0 < session.duration < MIN_MUSIC_DURATION):
                    if not self._current_player:
                        self._pick_and_attach()
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
            if pos_us >= 0:
                session.position = pos_us / 1_000_000.0
                session.position_at = time.monotonic()
        except Exception as e:
            logger.debug("Failed querying player props for %s: %s", bus_name, e)

        with self._lock:
            self._players[bus_name] = session

    def _find_ytdlp_bin(self) -> Optional[str]:
        if self._ytdlp_bin and os.path.isfile(self._ytdlp_bin) and os.access(self._ytdlp_bin, os.X_OK):
            return self._ytdlp_bin
        bin_path = shutil.which("yt-dlp")
        if bin_path:
            self._ytdlp_bin = bin_path
            return bin_path
        for cand in (
            Path.home() / ".local" / "bin" / "yt-dlp",
            Path("/usr/local/bin/yt-dlp"),
            Path("/usr/bin/yt-dlp"),
        ):
            if cand.is_file() and os.access(cand, os.X_OK):
                self._ytdlp_bin = str(cand)
                return self._ytdlp_bin
        return None

    def _cancel_active_ytdlp(self) -> None:
        with self._lock:
            if self._ytdlp_timer is not None:
                self._ytdlp_timer.cancel()
                self._ytdlp_timer = None

            proc = self._active_ytdlp_proc
            self._active_ytdlp_proc = None

        if proc and proc.poll() is None:
            try:
                proc.terminate()
                try:
                    proc.wait(timeout=0.15)
                except subprocess.TimeoutExpired:
                    proc.kill()
            except Exception:
                pass

    def _download_image_file(self, url: str, target_path: Path) -> bool:
        tmp_path = target_path.with_name(f"{target_path.stem}.tmp.{os.getpid()}_{threading.get_ident()}{target_path.suffix}")
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "DynamicIsland/1.0 (Linux Wayland MPRIS)"},
            )
            with urllib.request.urlopen(req, timeout=6.0) as resp:
                data = resp.read()
            if not data:
                return False
            with open(tmp_path, "wb") as f:
                f.write(data)
            crop_to_square(tmp_path)
            tmp_path.replace(target_path)
            return True
        except Exception as e:
            logger.debug("Failed downloading image %s: %s", url, e)
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except Exception:
                pass
            return False

    def _parse_metadata(self, session: PlayerSession, meta: dict[str, Any]) -> None:
        old_title = session.title
        old_artist = session.artist
        old_track_id = session.track_id
        old_art_url = session.art_url

        new_title = str(meta.get("xesam:title", "") or "")
        track_id = meta.get("mpris:trackid")
        new_track_id = str(track_id) if track_id else None

        artists = meta.get("xesam:artist") or meta.get("xesam:albumArtist") or []
        if isinstance(artists, (list, tuple)):
            new_artist = ", ".join(str(a) for a in artists if a)
        else:
            new_artist = str(artists or "")

        new_album = str(meta.get("xesam:album", "") or "")
        raw_url = str(meta.get("xesam:url", "") or "")

        track_changed = (
            (new_title and new_title != old_title)
            or (new_track_id and new_track_id != old_track_id)
            or (new_artist != old_artist)
        )

        if track_changed:
            session.position = 0.0
            session.position_at = time.monotonic()
            if self._current_player == session.bus_name:
                self._cancel_active_ytdlp()

        session.title = new_title
        session.artist = new_artist
        session.album = new_album
        session.track_id = new_track_id
        session.url = raw_url

        length_us = meta.get("mpris:length", 0)
        session.duration = max(0.0, float(length_us) / 1_000_000.0) if length_us else 0.0

        # Fast path: instant disk cache lookup by deterministic artist - title key
        # Skips all network requests and subprocess calls (playerctl, yt-dlp)
        cached_cover = find_cached_cover(new_artist, new_title)
        if cached_cover:
            crop_to_square(cached_cover)
            session.art_path = str(cached_cover)
            new_art_url = str(meta.get("mpris:artUrl", "") or meta.get("artUrl", "") or meta.get("xesam:artUrl", "") or "")
            session.art_url = new_art_url or cached_cover.as_uri()
            return

        new_art_url = str(meta.get("mpris:artUrl", "") or "")
        if not new_art_url:
            new_art_url = str(meta.get("artUrl", "") or meta.get("xesam:artUrl", "") or "")

        if not new_art_url and shutil.which("playerctl"):
            try:
                pname = session.bus_name.replace("org.mpris.MediaPlayer2.", "")
                res = subprocess.run(
                    ["playerctl", "-p", pname, "metadata", "mpris:artUrl"],
                    capture_output=True,
                    text=True,
                    timeout=0.5,
                    check=False,
                )
                if res.returncode == 0 and res.stdout.strip():
                    new_art_url = res.stdout.strip()
            except Exception:
                pass

        if not new_art_url:
            if raw_url.startswith("file://"):
                local_music = Path(urllib.parse.unquote(urllib.parse.urlsplit(raw_url).path))
            elif raw_url.startswith("/"):
                local_music = Path(raw_url)
            else:
                local_music = None

            if local_music and local_music.is_file():
                music_dir = local_music.parent
                for cand in ("cover.jpg", "cover.png", "folder.jpg", "folder.png", "album.jpg", "album.png", "front.jpg"):
                    cand_path = music_dir / cand
                    if cand_path.is_file():
                        new_art_url = cand_path.as_uri()
                        break

        if track_changed:
            session.art_url = new_art_url
            session.art_path = None
            if new_art_url:
                session.art_path = self._process_art_url(new_art_url, session=session)
            else:
                self._resolve_session_art(session)
        else:
            if new_art_url and (new_art_url != old_art_url or not session.art_path):
                session.art_url = new_art_url
                session.art_path = self._process_art_url(new_art_url, session=session)
            elif not session.art_path and not session.art_url:
                self._resolve_session_art(session)

    def _process_art_url(self, art_url: str, session: Optional[PlayerSession] = None) -> Optional[str]:
        if not art_url:
            return None

        try:
            title = session.title if session else ""
            artist = session.artist if session else ""

            cached_track = find_cached_cover(artist, title)
            if cached_track:
                crop_to_square(cached_track)
                return str(cached_track)

            cached_by_url = find_cached_cover_by_url(art_url)
            if cached_by_url:
                crop_to_square(cached_by_url)
                return str(cached_by_url)

            track_key = get_track_cache_key(artist, title)
            url_hash = hashlib.sha256(art_url.encode("utf-8")).hexdigest()[:16]
            file_name = f"{track_key}.jpg" if track_key else f"{url_hash}.jpg"
            cached_file = COVER_CACHE_DIR / file_name

            if art_url.startswith("file://") or art_url.startswith("/"):
                if art_url.startswith("file://"):
                    parsed = urllib.parse.urlparse(art_url)
                    local_path = Path(urllib.parse.unquote(parsed.path))
                else:
                    local_path = Path(art_url)

                if local_path.is_file():
                    if not cached_file.exists():
                        if not crop_to_square(local_path, dst_path=cached_file):
                            try:
                                shutil.copyfile(local_path, cached_file)
                                crop_to_square(cached_file)
                            except Exception:
                                return str(local_path)
                    else:
                        crop_to_square(cached_file)
                    return str(cached_file)

            elif art_url.startswith("data:image/"):
                if not cached_file.exists():
                    _header, data = art_url.split(",", 1)
                    img_bytes = base64.b64decode(data)
                    tmp_file = cached_file.with_name(f"{cached_file.stem}.tmp.{os.getpid()}_{threading.get_ident()}.raw")
                    with open(tmp_file, "wb") as f:
                        f.write(img_bytes)
                    crop_to_square(tmp_file, dst_path=cached_file)
                    if tmp_file.exists():
                        try:
                            tmp_file.unlink()
                        except Exception:
                            pass
                else:
                    crop_to_square(cached_file)
                return str(cached_file)

            elif art_url.startswith("http://") or art_url.startswith("https://"):
                if cached_file.is_file() and cached_file.stat().st_size > 0:
                    crop_to_square(cached_file)
                    return str(cached_file)

                with self._lock:
                    if art_url in self._failed_urls or art_url in self._in_flight_urls:
                        return None
                    self._in_flight_urls.add(art_url)

                title = session.title if session else ""
                artist = session.artist if session else ""
                threading.Thread(
                    target=self._async_download_cover,
                    args=(art_url, cached_file, session, title, artist),
                    daemon=True,
                    name=f"MediaService-HttpCover-{url_hash}",
                ).start()
                return None

        except Exception as e:
            logger.debug("Failed processing art URL %s: %s", art_url, e)
        return None

    def _async_download_cover(
        self,
        url: str,
        target_path: Path,
        session: Optional[PlayerSession] = None,
        expected_title: str = "",
        expected_artist: str = "",
    ) -> None:
        try:
            ok = self._download_image_file(url, target_path)
            with self._lock:
                self._in_flight_urls.discard(url)
                if not ok:
                    self._failed_urls.add(url)
                    if len(self._failed_urls) > 200:
                        self._failed_urls.pop()
                    return

                if not (target_path.is_file() and target_path.stat().st_size > 0):
                    return

                for s in self._players.values():
                    if s.art_url == url:
                        if not expected_title or (s.title == expected_title and s.artist == expected_artist):
                            s.art_path = str(target_path)

                if session is not None and session.art_url == url:
                    if not expected_title or (session.title == expected_title and session.artist == expected_artist):
                        session.art_path = str(target_path)

                cur_sess = self._players.get(self._current_player) if self._current_player else None
                if (
                    cur_sess
                    and cur_sess.art_url == url
                    and (not expected_title or (cur_sess.title == expected_title and cur_sess.artist == expected_artist))
                ):
                    self._art_path = str(target_path)
                    self._palette, self._accent = extract_dominant_palette(target_path)
                    GLib.idle_add(self._notify_changed)
        except Exception as e:
            logger.debug("Async cover download failed for %s: %s", url, e)
            with self._lock:
                self._in_flight_urls.discard(url)
                self._failed_urls.add(url)

    def _resolve_session_art(self, session: PlayerSession) -> None:
        if session.art_path and Path(session.art_path).is_file():
            return
        if session.art_url:
            return
        if not session.title or not session.title.strip():
            return
        if not (session.is_playing or session.bus_name == self._current_player):
            return

        cached = find_cached_cover(session.artist, session.title)
        if cached:
            crop_to_square(cached)
            session.art_path = str(cached)
            if self._current_player == session.bus_name and self._title == session.title:
                self._art_path = str(cached)
                self._palette, self._accent = extract_dominant_palette(cached)
                GLib.idle_add(self._notify_changed)
            return

        query_key = f"{session.artist} - {session.title}" if session.artist else session.title
        with self._lock:
            if query_key in self._failed_queries or query_key in self._in_flight_queries:
                return

        self._schedule_ytdlp_fetch(session)

    def _schedule_ytdlp_fetch(self, session: PlayerSession) -> None:
        if not session.title or not session.title.strip():
            return
        if session.art_url:
            return
        if session.art_path and Path(session.art_path).is_file():
            return
        if not (session.is_playing or session.bus_name == self._current_player):
            return

        query_key = f"{session.artist} - {session.title}" if session.artist else session.title
        with self._lock:
            if query_key in self._failed_queries or query_key in self._in_flight_queries:
                return

            if self._ytdlp_timer is not None:
                self._ytdlp_timer.cancel()
                self._ytdlp_timer = None

            proc = self._active_ytdlp_proc
            self._active_ytdlp_proc = None
            if proc and proc.poll() is None:
                try:
                    proc.terminate()
                except Exception:
                    pass

            bus_name = session.bus_name
            track_title = session.title
            track_artist = session.artist
            track_url = getattr(session, "url", "")

            self._ytdlp_timer = threading.Timer(
                0.35,
                self._execute_ytdlp_fetch,
                args=(bus_name, track_title, track_artist, query_key, track_url),
            )
            self._ytdlp_timer.daemon = True
            self._ytdlp_timer.name = "MediaService-YtDlpTimer"
            self._ytdlp_timer.start()

    def _execute_ytdlp_fetch(
        self,
        bus_name: str,
        expected_title: str,
        expected_artist: str,
        query_key: str,
        track_url: str,
    ) -> None:
        with self._lock:
            self._ytdlp_timer = None
            sess = self._players.get(bus_name)
            if not sess or sess.title != expected_title or sess.artist != expected_artist:
                return
            if sess.art_path and Path(sess.art_path).is_file():
                return
            if sess.art_url:
                return
            if query_key in self._failed_queries or query_key in self._in_flight_queries:
                return
            self._in_flight_queries.add(query_key)

        url_hash = hashlib.sha256(query_key.encode("utf-8")).hexdigest()[:16]
        cached_file = find_cached_cover(expected_artist, expected_title)
        if not cached_file:
            track_key = get_track_cache_key(expected_artist, expected_title)
            cached_file = COVER_CACHE_DIR / f"{track_key}.jpg" if track_key else COVER_CACHE_DIR / f"ytdlp_{url_hash}.jpg"

        if cached_file.is_file() and cached_file.stat().st_size > 0:
            crop_to_square(cached_file)
            with self._lock:
                self._in_flight_queries.discard(query_key)
                sess = self._players.get(bus_name)
                if (
                    sess
                    and sess.title == expected_title
                    and sess.artist == expected_artist
                    and (not sess.art_path or not Path(sess.art_path).is_file())
                ):
                    sess.art_path = str(cached_file)
                if (
                    self._current_player == bus_name
                    and self._title == expected_title
                    and (not self._art_path or not Path(self._art_path).is_file())
                ):
                    self._art_path = str(cached_file)
                    self._palette, self._accent = extract_dominant_palette(cached_file)
                    GLib.idle_add(self._notify_changed)
            return

        threading.Thread(
            target=self._ytdlp_worker,
            args=(bus_name, expected_title, expected_artist, query_key, track_url, cached_file),
            daemon=True,
            name=f"MediaService-YtDlpWorker-{url_hash}",
        ).start()

    def _ytdlp_worker(
        self,
        bus_name: str,
        expected_title: str,
        expected_artist: str,
        query_key: str,
        track_url: str,
        cached_file: Path,
    ) -> None:
        thumb_url: Optional[str] = None
        ytdlp_bin = self._find_ytdlp_bin()
        was_cancelled = False

        if ytdlp_bin:
            target = track_url if (track_url and track_url.startswith("http")) else f"ytsearch1:{query_key}"
            try:
                cmd = [
                    ytdlp_bin,
                    "--no-update",
                    "--no-warnings",
                    "--get-thumbnail",
                    "--socket-timeout", "6",
                    target,
                ]
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                with self._lock:
                    self._active_ytdlp_proc = proc

                try:
                    stdout, _ = proc.communicate(timeout=8.0)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    stdout, _ = proc.communicate()
                finally:
                    with self._lock:
                        if self._active_ytdlp_proc is proc:
                            self._active_ytdlp_proc = None

                if proc.returncode != 0:
                    was_cancelled = True
                elif stdout:
                    for line in stdout.strip().splitlines():
                        line_s = line.strip()
                        if line_s.startswith("http://") or line_s.startswith("https://"):
                            thumb_url = line_s
                            break
            except Exception as e:
                logger.debug("yt-dlp CLI query failed for %s: %s", query_key, e)
        else:
            try:
                import yt_dlp
                ydl_opts = {
                    "quiet": True,
                    "skip_download": True,
                    "extract_flat": True,
                    "noplaylist": True,
                    "socket_timeout": 6,
                }
                target = track_url if (track_url and track_url.startswith("http")) else f"ytsearch1:{query_key}"
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(target, download=False)
                    if info:
                        item = info["entries"][0] if ("entries" in info and info["entries"]) else info
                        thumbs = item.get("thumbnails")
                        if isinstance(thumbs, list) and thumbs:
                            thumb_url = thumbs[-1].get("url") or thumbs[0].get("url")
                        elif isinstance(thumbs, str):
                            thumb_url = thumbs
                        elif item.get("thumbnail"):
                            thumb_url = item.get("thumbnail")
            except Exception as e:
                logger.debug("yt_dlp python module query failed for %s: %s", query_key, e)

        with self._lock:
            sess = self._players.get(bus_name)
            if (
                was_cancelled
                or not sess
                or sess.title != expected_title
                or sess.artist != expected_artist
                or (sess.art_path and Path(sess.art_path).is_file())
            ):
                self._in_flight_queries.discard(query_key)
                return

        if thumb_url:
            download_ok = self._download_image_file(thumb_url, cached_file)
            if download_ok and cached_file.is_file() and cached_file.stat().st_size > 0:
                with self._lock:
                    self._in_flight_queries.discard(query_key)
                    sess = self._players.get(bus_name)
                    if (
                        sess
                        and sess.title == expected_title
                        and sess.artist == expected_artist
                        and (not sess.art_path or not Path(sess.art_path).is_file())
                    ):
                        sess.art_path = str(cached_file)
                    if (
                        self._current_player == bus_name
                        and self._title == expected_title
                        and (not self._art_path or not Path(self._art_path).is_file())
                    ):
                        self._art_path = str(cached_file)
                        self._palette, self._accent = extract_dominant_palette(cached_file)
                        GLib.idle_add(self._notify_changed)
                return

        with self._lock:
            self._in_flight_queries.discard(query_key)
            if not was_cancelled:
                self._failed_queries.add(query_key)
                if len(self._failed_queries) > 200:
                    self._failed_queries.pop()

    def _async_fetch_ytdlp_cover(self, session: PlayerSession) -> None:
        self._resolve_session_art(session)

    def _yield(self, playing_bus_name: str) -> None:
        sess = self._players.get(playing_bus_name)
        if sess and 0.0 < sess.duration < MIN_MUSIC_DURATION:
            return
        if self._chosen != playing_bus_name:
            self._chosen = None
            self._attach_player(playing_bus_name)
            self._notify_changed()

    def _pick_player(self) -> Optional[str]:
        if self._chosen and self._chosen in self._players:
            sess = self._players[self._chosen]
            if not (0.0 < sess.duration < MIN_MUSIC_DURATION):
                return self._chosen
        self._chosen = None

        for bname, sess in self._players.items():
            if sess.is_playing:
                if 0.0 < sess.duration < MIN_MUSIC_DURATION:
                    continue
                return bname

        if self._players:
            valid_players = [
                (b, s) for b, s in self._players.items()
                if not (0.0 < s.duration < MIN_MUSIC_DURATION)
            ]
            if valid_players:
                sorted_by_activity = sorted(
                    valid_players, key=lambda item: item[1].last_active, reverse=True
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
                self._cancel_active_ytdlp()
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

            if self._current_player != bus_name:
                self._cancel_active_ytdlp()

            self._current_player = bus_name
            session = self._players[bus_name]
            self._sync_current_from_session(session)
            if not session.art_path and not session.art_url:
                self._resolve_session_art(session)

    def _sync_current_from_session(self, session: PlayerSession) -> None:
        was_playing = self._is_playing
        track_changed = (self._title != session.title or self._artist != session.artist)

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

        if not (session.art_path and Path(session.art_path).is_file()):
            cached = find_cached_cover(session.artist, session.title)
            if cached:
                crop_to_square(cached)
                session.art_path = str(cached)
            elif session.art_url:
                cached_url = find_cached_cover_by_url(session.art_url)
                if cached_url:
                    crop_to_square(cached_url)
                    session.art_path = str(cached_url)

        if session.art_path and Path(session.art_path).is_file():
            if session.art_path != self._art_path:
                self._art_url = session.art_url
                self._art_path = session.art_path
                self._palette, self._accent = extract_dominant_palette(session.art_path)
        else:
            if track_changed or not self._art_path:
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
        self._cancel_active_ytdlp()
        if hasattr(self, "_poll_source") and self._poll_source:
            try:
                self._poll_source.destroy()
            except Exception:
                pass
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
    test_img_path = COVER_CACHE_DIR / "test_cover.png"
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
