#!/usr/bin/env python3
"""
Fetch YouTube Thumbnails

Reads backend/data/tracks.json, downloads YouTube video thumbnails for each track,
saves them to backend/thumbnails/{video_id}.jpg, and updates tracks.json with the
thumbnailPath field.

Usage:
    python3 fetch_thumbnails.py [--delay SECONDS] [--dry-run]

Thumbnails are fetched from YouTube's static image servers:
    1. maxresdefault.jpg (1280x720) — preferred
    2. hqdefault.jpg (480x360) — fallback if maxres not available
"""

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from urllib.parse import urlparse, parse_qs


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Fetch YouTube thumbnails for all tracks in tracks.json"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Delay in seconds between downloads (default: 0.5)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be done without downloading",
    )
    parser.add_argument(
        "--tracks-json",
        type=str,
        default=None,
        help="Path to tracks.json (default: ../backend/data/tracks.json)",
    )
    parser.add_argument(
        "--thumbnails-dir",
        type=str,
        default=None,
        help="Path to thumbnails output directory (default: ../backend/thumbnails)",
    )
    return parser.parse_args()


def extract_video_id(source_url: str) -> str | None:
    """Extract the YouTube video ID from a URL."""
    if not source_url:
        return None
    try:
        parsed = urlparse(source_url)
        if parsed.hostname in ("www.youtube.com", "youtube.com", "m.youtube.com"):
            qs = parse_qs(parsed.query)
            video_ids = qs.get("v")
            if video_ids:
                return video_ids[0]
        elif parsed.hostname in ("youtu.be",):
            return parsed.path.lstrip("/")
    except Exception:
        pass
    return None


def download_thumbnail(video_id: str, output_path: Path) -> bool:
    """
    Download the best available YouTube thumbnail for a video.
    Tries maxresdefault first, falls back to hqdefault.

    Returns True if downloaded successfully.
    """
    resolutions = [
        f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
        f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
    ]

    for url in resolutions:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as response:
                # YouTube returns a small grey placeholder for missing thumbnails
                # maxresdefault returns 404 for some videos, but sometimes returns
                # a 120-byte placeholder. Check content length.
                data = response.read()
                if len(data) < 1000:
                    # Likely a placeholder, try next resolution
                    continue

                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, "wb") as f:
                    f.write(data)
                return True
        except urllib.error.HTTPError as e:
            if e.code == 404:
                continue
            # Other HTTP errors — try next resolution
            continue
        except Exception:
            continue

    return False


def main():
    args = parse_args()

    # Resolve paths
    script_dir = Path(__file__).parent.resolve()
    project_root = script_dir.parent

    tracks_json_path = Path(args.tracks_json) if args.tracks_json else project_root / "backend" / "data" / "tracks.json"
    thumbnails_dir = Path(args.thumbnails_dir) if args.thumbnails_dir else project_root / "backend" / "thumbnails"

    # Validate
    if not tracks_json_path.exists():
        print(f"Error: tracks.json not found at {tracks_json_path}", file=sys.stderr)
        sys.exit(1)

    # Load tracks
    print(f"Loading tracks from: {tracks_json_path}")
    with open(tracks_json_path, "r", encoding="utf-8") as f:
        tracks = json.load(f)

    print(f"Found {len(tracks)} tracks")

    if not args.dry_run:
        thumbnails_dir.mkdir(parents=True, exist_ok=True)
        print(f"Thumbnails directory: {thumbnails_dir}")

    # Process tracks
    downloaded = 0
    skipped = 0
    failed = 0
    no_url = 0
    already_has = 0

    for i, track in enumerate(tracks, 1):
        track_name = track.get("trackName", "Unknown")
        artist = track.get("artist", "Unknown")
        source_url = track.get("sourceUrl", "")

        # Extract video ID
        video_id = extract_video_id(source_url)
        if not video_id:
            no_url += 1
            print(f"[{i}/{len(tracks)}] ✗ No YouTube URL: {artist} - {track_name}")
            continue

        thumbnail_filename = f"{video_id}.jpg"
        thumbnail_path = thumbnails_dir / thumbnail_filename

        # Check if already downloaded
        if thumbnail_path.exists() and thumbnail_path.stat().st_size > 1000:
            # Already have the file — just ensure the field is set
            if track.get("thumbnailPath") != thumbnail_filename:
                track["thumbnailPath"] = thumbnail_filename
            already_has += 1
            if already_has <= 5 or already_has % 50 == 0:
                print(f"[{i}/{len(tracks)}] ● Already exists: {artist} - {track_name}")
            continue

        if args.dry_run:
            print(f"[{i}/{len(tracks)}] Would download: {artist} - {track_name} → {thumbnail_filename}")
            skipped += 1
            continue

        # Download
        success = download_thumbnail(video_id, thumbnail_path)

        if success:
            track["thumbnailPath"] = thumbnail_filename
            downloaded += 1
            print(f"[{i}/{len(tracks)}] ✓ Downloaded: {artist} - {track_name}")
        else:
            failed += 1
            print(f"[{i}/{len(tracks)}] ✗ Failed: {artist} - {track_name} (video: {video_id})")

        # Rate limiting (skip on last track)
        if i < len(tracks):
            time.sleep(args.delay)

        # Periodically save progress (every 50 tracks)
        if not args.dry_run and downloaded > 0 and downloaded % 50 == 0:
            with open(tracks_json_path, "w", encoding="utf-8") as f:
                json.dump(tracks, f, indent=2, ensure_ascii=False)
            print(f"   💾 Progress saved ({downloaded} downloaded so far)")

    # Final save
    if not args.dry_run:
        with open(tracks_json_path, "w", encoding="utf-8") as f:
            json.dump(tracks, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Updated tracks.json with thumbnailPath fields")

    # Summary
    print(f"\n--- Summary ---")
    print(f"Total tracks:     {len(tracks)}")
    print(f"Downloaded:       {downloaded}")
    print(f"Already existed:  {already_has}")
    print(f"Failed:           {failed}")
    print(f"No YouTube URL:   {no_url}")
    if args.dry_run:
        print(f"(Dry run — nothing was downloaded)")


if __name__ == "__main__":
    main()
