
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import requests
from gi.repository import GLib

logger = logging.getLogger(__name__)

xdg_cache = os.environ.get("XDG_CACHE_HOME")
LYRICS_CACHE_DIR: Path = (
    Path(xdg_cache) if xdg_cache else (Path.home() / ".cache")
) / "dynamic-island" / "lyrics"
LYRICS_CACHE_TTL: float = 30 * 86400.0  # 30 days
LYRICS_CACHE_NEGATIVE_TTL: float = 2 * 86400.0  # 2 days for empty results

REWORK: str = (
    r"remix|rmx|sped\s*up|speed\s*up|slowed|reverb|nightcore|hardstyle|phonk|bootleg|mashup|ремикс"
)

NOISE: re.Pattern[str] = re.compile(
    rf"\s*[\(\[][^\)\]]*\b(official|video|audio|lyrics?|visuali[sz]er|remaster(ed)?|hd|hq|4k|mv|feat|ft|prod|edit|mix|version|cover|клип|премьера|{REWORK})\b[^\)\]]*[\)\]]",
    re.IGNORECASE,
)
REWORKED: re.Pattern[str] = re.compile(rf"\b({REWORK})\b", re.IGNORECASE)
REWORK_TAIL: re.Pattern[str] = re.compile(rf"\s*[-–—+]?\s*\b({REWORK})\b.*$", re.IGNORECASE)
PIPES: re.Pattern[str] = re.compile(r"\s*\|[^|]*\|\s*|\s+\|\s.*$")
CHANNEL: re.Pattern[str] = re.compile(r"\s*-\s*Topic$|\s*VEVO$", re.IGNORECASE)
STAMPED: re.Pattern[str] = re.compile(r"^((?:\[\d+:\d+(?:\.\d+)?\])+)(.*)$")
STAMP: re.Pattern[str] = re.compile(r"\[(\d+):(\d+(?:\.\d+)?)\]")
OFFSET_TAG: re.Pattern[str] = re.compile(r"^\[offset:\s*([+-]?\d+)\]", re.IGNORECASE)

@dataclass(frozen=True)
class Candidate:

    duration: float
    end: float
    lines: list[tuple[float, str]]
    synced: bool = True

class LyricsService:

    TOLERANCE: float = 4.0

    def __init__(self, timeout: float = 10.0) -> None:
        self._timeout: float = float(timeout)
        self._session: requests.Session = requests.Session()
        self._session.headers.update({"User-Agent": "DynamicIsland/1.0"})

        LYRICS_CACHE_DIR.mkdir(parents=True, exist_ok=True)

        self._lock: threading.Lock = threading.Lock()
        self._candidates: list[Candidate] = []
        self._stretched: list[tuple[float, str]] = []
        self._stretched_for: float = 0.0
        self._synced_lrc: str = ""
        self._plain_lyrics: str = ""
        self._reworked: bool = False
        self._key: str = ""
        self._version: int = 0
        self._pending: bool = False

        self._cache: dict[str, list[Candidate]] = {}
        self._callbacks: list[Callable[[], None]] = []
        self._changed_handler: Callable[[], None] | None = None

    def _put_cache(self, key: str, val: list[Candidate]) -> None:
        self._cache[key] = val
        if len(self._cache) > 50:
            old_k = next(iter(self._cache))
            del self._cache[old_k]

    def clear_cache(self) -> None:
        with self._lock:
            self._cache.clear()
            self._candidates.clear()
            self._stretched.clear()

    @property
    def synced_lrc(self) -> str:
        with self._lock:
            return self._synced_lrc

    @property
    def plain_lyrics(self) -> str:
        with self._lock:
            return self._plain_lyrics

    @property
    def pending(self) -> bool:
        with self._lock:
            return self._pending

    @property
    def reworked(self) -> bool:
        with self._lock:
            return self._reworked

    @property
    def candidates(self) -> list[Candidate]:
        with self._lock:
            return list(self._candidates)

    @property
    def is_synced(self) -> bool:
        with self._lock:
            if not self._candidates:
                return False
            return getattr(self._candidates[0], "synced", True)

    @property
    def on_changed(self) -> Callable[[], None] | None:
        return self._changed_handler

    @on_changed.setter
    def on_changed(self, handler: Callable[[], None] | None) -> None:
        self._changed_handler = handler

    def add_callback(self, callback: Callable[[], None]) -> None:
        with self._lock:
            if callback not in self._callbacks:
                self._callbacks.append(callback)

    def remove_callback(self, callback: Callable[[], None]) -> None:
        with self._lock:
            if callback in self._callbacks:
                self._callbacks.remove(callback)

    @classmethod
    def get_cache_key(cls, artist: str, title: str) -> str:
        clean_a = cls.clean_artist(artist).strip().lower()
        clean_t = cls.clean_title(title).strip().lower()
        if not clean_a and " - " in clean_t:
            parts = clean_t.split(" - ", 1)
            clean_a = parts[0].strip()
            clean_t = parts[1].strip()
        norm = f"{clean_a} - {clean_t}" if clean_a else clean_t
        if not norm:
            return ""
        return hashlib.sha256(norm.encode("utf-8")).hexdigest()

    @classmethod
    def get_cache_keys(cls, artist: str, title: str) -> list[str]:
        keys: list[str] = []
        primary = cls.get_cache_key(artist, title)
        if primary:
            keys.append(primary)
        raw_a = artist.strip().lower()
        raw_t = title.strip().lower()
        if not raw_a and " - " in raw_t:
            parts = raw_t.split(" - ", 1)
            raw_a = parts[0].strip()
            raw_t = parts[1].strip()
        norm_raw = f"{raw_a} - {raw_t}" if raw_a else raw_t
        if norm_raw:
            raw_key = hashlib.sha256(norm_raw.encode("utf-8")).hexdigest()
            if raw_key not in keys:
                keys.append(raw_key)
        return keys

    def _load_from_disk_cache(
        self, title: str, artist: str
    ) -> tuple[list[Candidate], str, str] | None:
        keys = self.get_cache_keys(artist, title)
        now = time.time()
        for k in keys:
            cache_file = LYRICS_CACHE_DIR / f"{k}.json"
            if not cache_file.is_file():
                continue
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                saved_at = float(data.get("saved_at", 0.0))
                candidates_raw = data.get("candidates", [])
                ttl = LYRICS_CACHE_NEGATIVE_TTL if not candidates_raw else LYRICS_CACHE_TTL
                if now - saved_at > ttl:
                    continue
                candidates = [
                    Candidate(
                        duration=float(c["duration"]),
                        end=float(c["end"]),
                        lines=[(float(s), str(txt)) for s, txt in c["lines"]],
                        synced=bool(c.get("synced", True)),
                    )
                    for c in candidates_raw
                ]
                synced_lrc = str(data.get("synced_lrc", "") or "")
                plain_lyrics = str(data.get("plain_lyrics", "") or "")
                return candidates, synced_lrc, plain_lyrics
            except Exception as exc:
                logger.debug("Failed reading lyrics cache %s: %s", cache_file, exc)
        return None

    def _save_to_disk_cache(
        self,
        title: str,
        artist: str,
        candidates: list[Candidate],
        synced_lrc: str = "",
        plain_lyrics: str = "",
    ) -> None:
        primary = self.get_cache_key(artist, title)
        if not primary:
            return
        cache_file = LYRICS_CACHE_DIR / f"{primary}.json"
        data = {
            "title": title,
            "artist": artist,
            "saved_at": time.time(),
            "synced_lrc": synced_lrc,
            "plain_lyrics": plain_lyrics,
            "candidates": [
                {
                    "duration": c.duration,
                    "end": c.end,
                    "lines": c.lines,
                    "synced": c.synced,
                }
                for c in candidates
            ],
        }
        try:
            tmp_file = cache_file.with_suffix(".tmp")
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            tmp_file.replace(cache_file)
        except Exception as exc:
            logger.debug("Failed to write lyrics cache for %r - %r: %s", artist, title, exc)

    def clear(self) -> None:
        with self._lock:
            self._key = ""
            self._candidates = []
            self._stretched = []
            self._stretched_for = 0.0
            self._synced_lrc = ""
            self._plain_lyrics = ""
            self._reworked = False
            self._pending = False
            self._version += 1
        self._notify_changed()

    def track(self, title: str, artist: str, duration: float = 0.0) -> None:
        clean_t = title.strip()
        clean_a = artist.strip()
        key = f"{clean_t}\n{clean_a}"

        with self._lock:
            if key == self._key:
                return

            self._key = key
            self._candidates = []
            self._stretched = []
            self._stretched_for = 0.0
            self._synced_lrc = ""
            self._plain_lyrics = ""
            self._reworked = bool(REWORKED.search(clean_t))
            self._version += 1
            version = self._version

            if key in self._cache:
                self._candidates = self._cache[key]
                self._pending = False
                self._notify_changed()
                return

            if not clean_t:
                self._pending = False
                self._notify_changed()
                return

        # Instant load from disk cache if present
        cached = self._load_from_disk_cache(clean_t, clean_a)
        if cached is not None:
            cached_candidates, cached_synced, cached_plain = cached
            with self._lock:
                if version == self._version:
                    self._put_cache(key, cached_candidates)
                    self._candidates = cached_candidates
                    self._synced_lrc = cached_synced
                    self._plain_lyrics = cached_plain
                    self._pending = False
            self._notify_changed()
            return

        with self._lock:
            self._pending = True
        self._notify_changed()

        thread = threading.Thread(
            target=self._load_async,
            args=(clean_t, clean_a, duration, version, key),
            daemon=True,
            name=f"LyricsFetch-{version}",
        )
        thread.start()

    def fetch_sync(
        self, title: str, artist: str, duration: float = 0.0
    ) -> list[Candidate]:
        clean_t = title.strip()
        clean_a = artist.strip()
        key = f"{clean_t}\n{clean_a}"

        with self._lock:
            if key in self._cache:
                self._candidates = self._cache[key]
                return list(self._candidates)

        cached = self._load_from_disk_cache(clean_t, clean_a)
        if cached is not None:
            cached_candidates, cached_synced, cached_plain = cached
            with self._lock:
                self._put_cache(key, cached_candidates)
                self._key = key
                self._candidates = cached_candidates
                self._synced_lrc = cached_synced
                self._plain_lyrics = cached_plain
                self._reworked = bool(REWORKED.search(clean_t))
                self._stretched = []
                self._stretched_for = 0.0
                self._pending = False
            self._notify_changed()
            return list(cached_candidates)

        found, synced_lrc, plain_lyrics = self._fetch_with_raw(clean_t, clean_a, duration)
        with self._lock:
            self._put_cache(key, found)
            self._key = key
            self._candidates = found
            self._synced_lrc = synced_lrc
            self._plain_lyrics = plain_lyrics
            self._reworked = bool(REWORKED.search(clean_t))
            self._stretched = []
            self._stretched_for = 0.0
            self._pending = False

        self._notify_changed()
        return found

    def for_duration(self, duration: float) -> list[tuple[float, str]]:
        with self._lock:
            candidates = list(self._candidates)
            reworked = self._reworked

        if not candidates:
            return []

        if duration < 1.0:
            return candidates[0].lines

        best: list[tuple[float, str]] = []
        best_gap = self.TOLERANCE
        for c in candidates:
            if c.end > duration + 3.5:
                continue
            gap = abs(c.duration - duration)
            if gap > best_gap or (gap == best_gap and len(best) > 0):
                continue
            best = c.lines
            best_gap = gap

        if not best:
            fallback_gap = 15.0
            for c in candidates:
                if c.end > max(duration, c.duration) + 3.5:
                    continue
                gap = abs(c.duration - duration)
                if gap <= fallback_gap:
                    if gap < fallback_gap or len(best) == 0:
                        best = c.lines
                        fallback_gap = gap

        if len(best) > 0 or not reworked:
            return best

        with self._lock:
            if abs(duration - self._stretched_for) > 0.5:
                self._stretched = self._stretch(duration, candidates)
                self._stretched_for = duration
            return list(self._stretched)

    def get_current_line(
        self, position: float, duration: float, lead: float = 0.0
    ) -> tuple[int, tuple[float, str] | None]:
        lines = self.for_duration(duration)
        if not lines:
            return -1, None

        at = position + lead
        index = len(lines) - 1
        while index >= 0 and lines[index][0] > at:
            index -= 1

        if index < 0:
            return -1, None
        return index, lines[index]

    def _stretch(
        self, seconds: float, candidates: list[Candidate]
    ) -> list[tuple[float, str]]:
        valid = [c for c in candidates if c.duration >= 30.0 and c.end <= c.duration + 1.0]
        if not valid:
            return []

        groups: dict[int, list[Candidate]] = {}
        for c in valid:
            r = round(c.duration)
            groups.setdefault(r, []).append(c)

        sorted_groups = sorted(groups.values(), key=len, reverse=True)
        if not sorted_groups or not sorted_groups[0]:
            return []

        usual = sorted_groups[0][0]
        if usual.duration <= 0.0:
            return []

        ratio = seconds / usual.duration
        if ratio < 0.5 or ratio > 2.0:
            return []

        return [(round(sec * ratio, 3), text) for sec, text in usual.lines]

    def _load_async(
        self, title: str, artist: str, duration: float, version: int, key: str
    ) -> None:
        found: list[Candidate] = []
        synced_lrc: str = ""
        plain_lyrics: str = ""
        try:
            found, synced_lrc, plain_lyrics = self._fetch_with_raw(title, artist, duration)
        except Exception as exc:
            logger.debug("Lyrics fetch error for %r by %r: %s", title, artist, exc)

        with self._lock:
            self._put_cache(key, found)
            if version != self._version:
                return
            self._candidates = found
            self._synced_lrc = synced_lrc
            self._plain_lyrics = plain_lyrics
            self._stretched = []
            self._stretched_for = 0.0
            self._pending = False

        self._notify_changed()

    def _notify_changed(self) -> None:
        def _emit() -> bool:
            if self._changed_handler:
                try:
                    self._changed_handler()
                except Exception as exc:
                    logger.error("Error in lyrics on_changed handler: %s", exc)

            for cb in list(self._callbacks):
                try:
                    cb()
                except Exception as exc:
                    logger.error("Error in lyrics callback: %s", exc)
            return False

        GLib.idle_add(_emit)

    def _fetch(self, title: str, artist: str, duration: float = 0.0) -> list[Candidate]:
        candidates, _, _ = self._fetch_with_raw(title, artist, duration)
        return candidates

    def _fetch_with_raw(
        self, title: str, artist: str, duration: float = 0.0
    ) -> tuple[list[Candidate], str, str]:
        cached = self._load_from_disk_cache(title, artist)
        if cached is not None:
            return cached

        candidates: list[Candidate] = []
        seen: set[str] = set()
        best_synced_lrc: str = ""
        best_plain_lyrics: str = ""

        def add_candidate(dur: float, lrc_text: str, synced: bool = True) -> None:
            nonlocal best_synced_lrc
            lines = self.parse(lrc_text)
            if not lines:
                return
            if not best_synced_lrc and synced:
                best_synced_lrc = lrc_text
            end = 0.0
            for sec, txt in reversed(lines):
                if len(txt) > 0:
                    end = sec
                    break
            fingerprint = f"{dur:.1f}_{end:.1f}_{len(lines)}"
            if fingerprint not in seen:
                seen.add(fingerprint)
                candidates.append(Candidate(duration=dur, end=end, lines=lines, synced=synced))

        def add_plain_candidate(dur: float, plain_text: str) -> None:
            nonlocal best_plain_lyrics
            if not best_plain_lyrics:
                best_plain_lyrics = plain_text
            raw_lines = [
                line.strip()
                for line in plain_text.splitlines()
                if line.strip() and not (line.strip().startswith("[") and line.strip().endswith("]"))
            ]
            if not raw_lines or dur <= 10.0:
                return
            intro_t = min(12.0, dur * 0.1)
            avail_t = max(10.0, dur - intro_t - min(12.0, dur * 0.08))
            step_t = avail_t / max(1, len(raw_lines))
            timed_lines = []
            cur_t = intro_t
            for txt in raw_lines:
                timed_lines.append((round(cur_t, 2), txt))
                cur_t += step_t
            end = timed_lines[-1][0] if timed_lines else dur
            fingerprint = f"{dur:.1f}_{end:.1f}_{len(timed_lines)}_plain"
            if fingerprint not in seen:
                seen.add(fingerprint)
                candidates.append(Candidate(duration=dur, end=end, lines=timed_lines, synced=False))

        if duration > 0.0:
            song = self.clean_title(title)
            by = self.clean_artist(artist)
            if song:
                try:
                    data = self._get_json(
                        "https://lrclib.net/api/get",
                        params={
                            "track_name": song,
                            "artist_name": by,
                            "duration": round(duration),
                        },
                    )
                    if isinstance(data, dict):
                        synced = data.get("syncedLyrics")
                        plain = data.get("plainLyrics")
                        dur_val = data.get("duration")
                        if isinstance(plain, str) and plain.strip() and not best_plain_lyrics:
                            best_plain_lyrics = plain
                        if isinstance(synced, str) and isinstance(dur_val, (int, float)):
                            add_candidate(float(dur_val), synced, synced=True)
                        elif isinstance(plain, str) and isinstance(dur_val, (int, float)):
                            add_plain_candidate(float(dur_val), plain)
                except Exception:
                    pass

        for query_params in self.get_queries(title, artist):
            data = self._get_json("https://lrclib.net/api/search", params=query_params)
            if isinstance(data, list):
                for item in data:
                    if not isinstance(item, dict):
                        continue
                    synced = item.get("syncedLyrics")
                    plain = item.get("plainLyrics")
                    dur_val = item.get("duration")
                    if isinstance(plain, str) and plain.strip() and not best_plain_lyrics:
                        best_plain_lyrics = plain
                    if isinstance(synced, str) and isinstance(dur_val, (int, float)):
                        add_candidate(float(dur_val), synced, synced=True)
                    elif isinstance(plain, str) and isinstance(dur_val, (int, float)):
                        add_plain_candidate(float(dur_val), plain)
            if candidates:
                self._save_to_disk_cache(title, artist, candidates, best_synced_lrc, best_plain_lyrics)
                return candidates, best_synced_lrc, best_plain_lyrics

        song = self.clean_title(title)
        by = self.clean_artist(artist)

        try:
            self._fetch_netease(song, by, duration, add_candidate)
            if candidates:
                self._save_to_disk_cache(title, artist, candidates, best_synced_lrc, best_plain_lyrics)
                return candidates, best_synced_lrc, best_plain_lyrics
        except Exception as exc:
            logger.debug("NetEase fetch error: %s", exc)

        try:
            self._fetch_lyrics_ovh(song, by, duration, candidates, seen)
            if candidates:
                if not best_plain_lyrics and candidates:
                    best_plain_lyrics = "\n".join(txt for _, txt in candidates[0].lines if txt)
                self._save_to_disk_cache(title, artist, candidates, best_synced_lrc, best_plain_lyrics)
                return candidates, best_synced_lrc, best_plain_lyrics
        except Exception as exc:
            logger.debug("Lyrics.ovh fetch error: %s", exc)

        self._save_to_disk_cache(title, artist, [], "", "")
        return candidates, best_synced_lrc, best_plain_lyrics

    def _fetch_netease(
        self,
        song: str,
        by: str,
        duration: float,
        add_candidate: Callable[[float, str], None],
    ) -> None:
        query = f"{by} {song}".strip() if by else song
        if not query:
            return
        data = self._get_json(
            "https://music-api.gdstudio.xyz/api.php",
            params={
                "types": "search",
                "count": "3",
                "source": "netease",
                "pages": "1",
                "name": query,
            },
        )
        if not isinstance(data, list):
            return
        for item in data[:3]:
            if not isinstance(item, dict):
                continue
            sid = item.get("id")
            if not sid:
                continue
            lrc_data = self._get_json(
                "https://music-api.gdstudio.xyz/api.php",
                params={
                    "types": "lyric",
                    "id": str(sid),
                    "source": "netease",
                },
            )
            if isinstance(lrc_data, dict):
                lrc_text = lrc_data.get("lyric")
                if isinstance(lrc_text, str) and lrc_text.strip():
                    dur = float(duration) if duration > 0.0 else 0.0
                    add_candidate(dur, lrc_text)
                    return

    def _fetch_lyrics_ovh(
        self,
        song: str,
        by: str,
        duration: float,
        candidates: list[Candidate],
        seen: set[str],
    ) -> None:
        if not by or not song or duration <= 10.0:
            return
        url = f"https://api.lyrics.ovh/v1/{requests.utils.quote(by)}/{requests.utils.quote(song)}"
        data = self._get_json(url)
        if not isinstance(data, dict):
            return
        raw_lyrics = data.get("lyrics")
        if not isinstance(raw_lyrics, str) or not raw_lyrics.strip():
            return

        raw_lines = [
            line.strip()
            for line in raw_lyrics.splitlines()
            if line.strip() and not (line.strip().startswith("[") and line.strip().endswith("]"))
        ]
        if not raw_lines:
            return

        intro_t = min(12.0, duration * 0.1)
        avail_t = max(10.0, duration - intro_t - min(12.0, duration * 0.08))
        step_t = avail_t / max(1, len(raw_lines))

        timed_lines: list[tuple[float, str]] = []
        cur_t = intro_t
        for txt in raw_lines:
            timed_lines.append((round(cur_t, 2), txt))
            cur_t += step_t

        end = timed_lines[-1][0] if timed_lines else duration
        fp = f"{duration:.1f}_{end:.1f}_{len(timed_lines)}"
        if fp not in seen:
            seen.add(fp)
            candidates.append(Candidate(duration=duration, end=end, lines=timed_lines, synced=False))

    def _get_json(self, url: str, params: dict[str, str] | None = None) -> Any:
        for attempt in range(2):
            try:
                resp = self._session.get(url, params=params, timeout=self._timeout)
                if resp.status_code == 200:
                    return resp.json()
                elif resp.status_code == 503:
                    time.sleep(1.5)
                    continue
                else:
                    return None
            except requests.RequestException:
                if attempt == 0:
                    time.sleep(1.5)
                else:
                    return None
        return None

    @classmethod
    def clean_title(cls, title: str) -> str:
        s = NOISE.sub("", title)
        s = PIPES.sub(" ", s)
        s = REWORK_TAIL.sub("", s)
        s = s.replace("—", "-").replace("–", "-").strip()
        return s if s else title.strip()

    @classmethod
    def clean_artist(cls, artist: str) -> str:
        return CHANNEL.sub("", artist).strip()

    @classmethod
    def get_queries(cls, title: str, artist: str) -> list[dict[str, str]]:
        song = cls.clean_title(title)
        by = cls.clean_artist(artist)
        if not song:
            song = title

        queries: list[dict[str, str]] = []
        if by:
            queries.append({"track_name": song, "artist_name": by})

        dash = song.find(" - ")
        if dash > 0:
            queries.append({
                "track_name": song[dash + 3:].strip(),
                "artist_name": song[:dash].strip(),
            })
            queries.append({"q": song.replace(" - ", " ")})
        else:
            q_val = f"{by} {song}".strip() if by else song
            queries.append({"q": q_val})

        return queries

    @staticmethod
    def parse(lrc: str) -> list[tuple[float, str]]:
        offset_sec = 0.0
        lines: list[tuple[float, str]] = []
        for raw in lrc.splitlines():
            s = raw.strip()
            off_m = OFFSET_TAG.match(s)
            if off_m:
                try:
                    offset_sec = float(off_m.group(1)) / 1000.0
                except ValueError:
                    pass
                continue

            m = STAMPED.match(s)
            if not m:
                continue

            text = m.group(2).strip()
            for stamp in STAMP.finditer(m.group(1)):
                try:
                    mins = int(stamp.group(1))
                    secs = float(stamp.group(2))
                    seconds = mins * 60.0 + secs + offset_sec
                    lines.append((max(0.0, round(seconds, 3)), text))
                except ValueError:
                    continue

        lines.sort(key=lambda item: item[0])
        return lines

if __name__ == "__main__":
    print("Testing LyricsService...")

    test_titles = [
        ("In The End (Official HD Video) [feat. Chester]", "Linkin Park - Topic"),
        ("Numb | 4K 60FPS Remastered", "Linkin Park VEVO"),
        ("Song (slowed + reverb)", "Artist"),
        ("Track sped up", "Artist"),
        ("Another Song | Channel", "Artist"),
    ]
    print("\n--- Regex Cleaning Tests ---")
    for t, a in test_titles:
        c_t = LyricsService.clean_title(t)
        c_a = LyricsService.clean_artist(a)
        is_rew = bool(REWORKED.search(t))
        print(f"Original: {t!r} by {a!r}")
        print(f"Cleaned : {c_t!r} by {c_a!r} (reworked={is_rew})")

    sample_lrc = """
[00:00.00]
[00:15.30]First line of the song
[00:20.50][01:10.20]Chorus sung twice
[00:28.95]
[00:32.10]Second verse line
"""
    print("\n--- LRC Parsing Test ---")
    parsed = LyricsService.parse(sample_lrc)
    for sec, txt in parsed:
        print(f"  [{sec:6.2f}s] {txt!r}")
    assert len(parsed) == 6, f"Expected 6 parsed lines, got {len(parsed)}"

    print("\n--- LRCLIB API Search Test ---")
    svc = LyricsService()
    candidates = svc.fetch_sync("In The End", "Linkin Park", duration=216.0)
    print(f"Found {len(candidates)} candidates")
    if candidates:
        print(f"Candidate 0: duration={candidates[0].duration}s, end={candidates[0].end}s, lines={len(candidates[0].lines)}")
        lines = svc.for_duration(216.0)
        print(f"Lines matching duration 216s: {len(lines)}")
        if lines:
            print("First 3 matched lines:")
            for s, line_text in lines[:3]:
                print(f"  [{s:6.2f}s] {line_text}")

            idx, cur = svc.get_current_line(position=25.0, duration=216.0)
            print(f"At position 25.0s: index={idx}, line={cur}")

    print("\n--- Background Thread Fetch Test ---")
    done_event = threading.Event()
    call_count = 0
    def on_lyrics_ready():
        global call_count
        call_count += 1
        print(f"Callback fired (#{call_count}): lyrics notification! pending={svc2.pending}")
        if not svc2.pending:
            done_event.set()

    svc2 = LyricsService()
    svc2.add_callback(on_lyrics_ready)
    svc2.track("Numb", "Linkin Park", duration=187.0)
    print("track() called non-blocking, waiting on background thread...")
    ctx = GLib.MainContext.default()
    start_t = time.time()
    while not done_event.is_set() and (time.time() - start_t < 6.0):
        ctx.iteration(False)
        time.sleep(0.02)
    ready = done_event.is_set()
    print(f"Finished waiting, ready={ready}, pending={svc2.pending}")
    lines2 = svc2.for_duration(187.0)
    print(f"Fetched lines count: {len(lines2)}")

    print("\n--- Edge Case Duration Tests ---")
    if candidates:
        zero_lines = svc.for_duration(0.0)
        print(f"for_duration(0.0): {len(zero_lines)} lines returned (expected > 0)")
        assert len(zero_lines) > 0, "for_duration(0.0) should return candidate lines!"

        fallback_lines = svc.for_duration(210.0)
        print(f"for_duration(210.0 for 216s track): {len(fallback_lines)} lines returned (expected > 0)")
        assert len(fallback_lines) > 0, "for_duration should match within 15.0s fallback!"

    print("\n--- Track Change Immediate Flush Test ---")
    v_before = svc2._version
    svc2.track("Brand New Track", "Brand New Artist", duration=200.0)
    assert len(svc2._candidates) == 0, "Candidates should immediately be empty on track change"
    assert len(svc2._stretched) == 0, "Stretched should immediately be empty on track change"
    assert svc2._version == v_before + 1, "Version should be incremented immediately on track change"
    print("Track change immediately flushed candidates and incremented version.")

    print("\nLyricsService tests completed successfully!")
