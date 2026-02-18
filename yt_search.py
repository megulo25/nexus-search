#!/usr/bin/env python3
"""
Shared YouTube search utilities for Nexus Music Player.

Provides progressive multi-strategy YouTube search with duration-based
candidate ranking. Used by youtube-search.py, retry_failures.py, and
download.py to reliably find the correct video for a given track.
"""

import re
import subprocess
from dataclasses import dataclass


# ─── Query cleaning helpers ─────────────────────────────────────────────────

_FEAT_RE = re.compile(
    r'\s*[\(\[]\s*(?:feat\.?|ft\.?|featuring|with)\s+[^\)\]]+[\)\]]',
    re.IGNORECASE,
)
_PARENS_RE = re.compile(r'\s*[\(\[][^\)\]]*[\)\]]')


def _primary_artist(artist: str) -> str:
    """Return just the first artist from a semicolon-separated list."""
    return artist.split(';')[0].strip()


def _strip_featured(name: str) -> str:
    """Strip '(feat. …)' / '[ft. …]' from a track name."""
    return _FEAT_RE.sub('', name).strip()


def _strip_all_parens(name: str) -> str:
    """Strip all parenthetical/bracket content (Remix, Deluxe, etc.)."""
    return _PARENS_RE.sub('', name).strip()


def _all_artists_spaced(artist: str) -> str:
    """Convert 'A;B;C' → 'A B C' for use in a search query."""
    return ' '.join(a.strip() for a in artist.split(';') if a.strip())


def build_search_queries(track_name: str, artist: str) -> list[str]:
    """
    Build a prioritised list of YouTube search queries for a track.

    Strategies (tried in order):
      1. Full track name + all artists (spaces instead of semicolons)
      2. Full track name + primary artist only
      3. Track name with (feat …) stripped + primary artist
      4. Track name with ALL parenthetical content stripped + primary artist
      5. Track name + primary artist + "audio"
      6. Track name + primary artist + "lyrics"  (lyric videos are common)
    """
    primary = _primary_artist(artist)
    all_artists = _all_artists_spaced(artist)
    clean_feat = _strip_featured(track_name)
    clean_all = _strip_all_parens(track_name)

    queries: list[str] = []
    seen: set[str] = set()

    for q in [
        f"{track_name} {all_artists}",
        f"{track_name} {primary}",
        f"{clean_feat} {primary}",
        f"{clean_all} {primary}",
        f"{track_name} {primary} audio",
        f"{track_name} {primary} lyrics",
    ]:
        norm = ' '.join(q.split()).lower()
        if norm not in seen:
            seen.add(norm)
            queries.append(' '.join(q.split()))

    return queries


# ─── yt-dlp search helpers ──────────────────────────────────────────────────

@dataclass
class SearchCandidate:
    url: str
    duration_s: float  # seconds


def _yt_search(query: str, n: int = 3, timeout: int = 60) -> list[SearchCandidate]:
    """
    Run yt-dlp ytsearch and return up to *n* candidates with URLs and durations.
    """
    try:
        result = subprocess.run(
            [
                'yt-dlp',
                '--print', '%(webpage_url)s %(duration)s',
                '--no-download',
                f'ytsearch{n}:{query}',
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            return []

        candidates: list[SearchCandidate] = []
        for line in result.stdout.strip().splitlines():
            parts = line.rsplit(None, 1)
            if len(parts) == 2:
                url, dur_str = parts
                try:
                    dur = float(dur_str)
                except ValueError:
                    dur = 0.0
            else:
                url = parts[0] if parts else ''
                dur = 0.0
            if url.startswith('http'):
                candidates.append(SearchCandidate(url=url, duration_s=dur))
        return candidates

    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def _pick_best(candidates: list[SearchCandidate], target_ms: int | None) -> str | None:
    """Pick the candidate whose duration is closest to *target_ms* (if known)."""
    if not candidates:
        return None
    if target_ms is None or target_ms <= 0:
        return candidates[0].url  # no duration info → take top result

    target_s = target_ms / 1000.0
    # Filter out extremely long videos (> 3× expected) to skip compilations
    reasonable = [c for c in candidates if c.duration_s <= target_s * 3]
    if not reasonable:
        reasonable = candidates  # fall back to originals

    best = min(reasonable, key=lambda c: abs(c.duration_s - target_s))
    return best.url


# ─── Public API ──────────────────────────────────────────────────────────────

def search_youtube(
    track_name: str,
    artist: str,
    duration_ms: int | None = None,
    candidates_per_query: int = 3,
) -> tuple[str, str]:
    """
    Search YouTube for a track using progressive query strategies.

    Args:
        track_name:  Song title (may include '(feat. …)' etc.)
        artist:      Artist string, possibly ';'-separated for multiple artists.
        duration_ms: Expected duration in milliseconds (from Spotify metadata).
                     Used to rank candidates and filter out compilations.
        candidates_per_query: How many results to fetch per search query (default 3).

    Returns:
        (url, strategy_description)   on success
        ('', error_description)       on failure
    """
    queries = build_search_queries(track_name, artist)

    for idx, query in enumerate(queries, 1):
        candidates = _yt_search(query, n=candidates_per_query)
        url = _pick_best(candidates, duration_ms)
        if url:
            strategy = f"strategy {idx}/{len(queries)}: \"{query}\""
            return url, strategy

    return '', f"No results after {len(queries)} search strategies"
