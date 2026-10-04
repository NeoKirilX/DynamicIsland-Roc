
from __future__ import annotations

import logging
import re
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable

import requests
from gi.repository import GLib

logger = logging.getLogger(__name__)

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

        self._lock: threading.Lock = threading.Lock()
        self._candidates: list[Candidate] = []
        self._stretched: list[tuple[float, str]] = []
        self._stretched_for: float = 0.0
        self._reworked: bool = False
        self._key: str = ""
        self._version: int = 0
        self._pending: bool = False

        self._cache: dict[str, list[Candidate]] = {}
        self._callbacks: list[Callable[[], None]] = []
        self._changed_handler: Callable[[], None] | None = None

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

    def clear(self) -> None:
        with self._lock:
            self._key = ""
            self._candidates = []
            self._stretched = []
            self._stretched_for = 0.0
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

        found = self._fetch(clean_t, clean_a, duration)
        with self._lock:
            self._cache[key] = found
            self._key = key
            self._candidates = found
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
        try:
            found = self._fetch(title, artist, duration)
        except Exception as exc:
            logger.debug("Lyrics fetch error for %r by %r: %s", title, artist, exc)

        with self._lock:
            self._cache[key] = found
            if version != self._version:
                return
            self._candidates = found
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
        candidates: list[Candidate] = []
        seen: set[str] = set()

        def add_candidate(dur: float, lrc_text: str, synced: bool = True) -> None:
            lines = self.parse(lrc_text)
            if not lines:
                return
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
                        dur_val = data.get("duration")
                        if isinstance(synced, str) and isinstance(dur_val, (int, float)):
                            add_candidate(float(dur_val), synced, synced=True)
                        elif isinstance(data.get("plainLyrics"), str) and isinstance(dur_val, (int, float)):
                            add_plain_candidate(float(dur_val), data["plainLyrics"])
                except Exception:
                    pass

        for query_params in self.get_queries(title, artist):
            data = self._get_json("https://lrclib.net/api/search", params=query_params)
            if isinstance(data, list):
                for item in data:
                    if not isinstance(item, dict):
                        continue
                    synced = item.get("syncedLyrics")
                    dur_val = item.get("duration")
                    if isinstance(synced, str) and isinstance(dur_val, (int, float)):
                        add_candidate(float(dur_val), synced, synced=True)
                    elif isinstance(item.get("plainLyrics"), str) and isinstance(dur_val, (int, float)):
                        add_plain_candidate(float(dur_val), item["plainLyrics"])
            if candidates:
                return candidates

        song = self.clean_title(title)
        by = self.clean_artist(artist)

        try:
            self._fetch_netease(song, by, duration, add_candidate)
            if candidates:
                return candidates
        except Exception as exc:
            logger.debug("NetEase fetch error: %s", exc)

        try:
            self._fetch_lyrics_ovh(song, by, duration, candidates, seen)
            if candidates:
                return candidates
        except Exception as exc:
            logger.debug("Lyrics.ovh fetch error: %s", exc)

        return candidates

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
