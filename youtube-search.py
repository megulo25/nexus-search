#!/usr/bin/env python3
"""
YouTube Song Downloader

Reads a Spotify export CSV, searches YouTube using yt-dlp, downloads audio as m4a,
and outputs JSON with essential metadata plus YouTube URLs.
"""

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from yt_search import search_youtube


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Download songs from YouTube based on a Spotify CSV export"
    )
    parser.add_argument(
        "csv_file",
        type=str,
        help="Path to the input CSV file (Spotify export)"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Delay in seconds between downloads (default: 2.0)"
    )
    return parser.parse_args()


def create_output_directory(csv_path: str) -> Path:
    """Create the output directory structure based on CSV name and current timestamp."""
    csv_name = Path(csv_path).stem
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M")
    output_dir = Path("output") / csv_name / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def parse_csv(csv_path: str) -> list[dict]:
    """Parse the Spotify CSV and extract essential fields."""
    songs = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            song = {
                "track_name": row.get("Track Name", "").strip(),
                "artist": row.get("Artist Name(s)", "").strip(),
                "album": row.get("Album Name", "").strip(),
                "release_date": row.get("Release Date", "").strip(),
                "duration_ms": row.get("Duration (ms)", "").strip(),
            }
            songs.append(song)
    return songs


def sanitize_filename(name: str) -> str:
    """Remove or replace characters that are invalid in filenames."""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, '_')
    # Replace spaces with underscores for robustness
    name = name.replace(' ', '_')
    # Replace semicolons (used for multiple artists) with underscores
    name = name.replace(';', '_')
    # Remove any double underscores
    while '__' in name:
        name = name.replace('__', '_')
    return name.strip('_')


def get_songs_dir() -> Path:
    """Get the global songs/ directory relative to the script location."""
    songs_dir = Path(__file__).parent.resolve() / 'songs'
    songs_dir.mkdir(exist_ok=True)
    return songs_dir


def get_thumbnails_dir() -> Path:
    """Get the global thumbnails/ directory relative to the script location."""
    thumbnails_dir = Path(__file__).parent.resolve() / 'thumbnails'
    thumbnails_dir.mkdir(exist_ok=True)
    return thumbnails_dir


def download_thumbnail(url: str, thumbnails_dir: Path) -> str:
    """
    Download the YouTube video thumbnail.
    Extracts the video ID from the URL and downloads the best available thumbnail.

    Returns:
        str: Relative path to thumbnail (e.g., 'thumbnails/VIDEO_ID.jpg') or empty string on failure.
    """
    import urllib.request
    import urllib.error
    from urllib.parse import urlparse, parse_qs

    try:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        video_id = qs.get('v', [None])[0]
        if not video_id:
            return ""

        thumbnail_path = thumbnails_dir / f"{video_id}.jpg"
        if thumbnail_path.exists() and thumbnail_path.stat().st_size > 1000:
            return f"thumbnails/{video_id}.jpg"

        # Try maxresdefault first, then hqdefault
        for res in ('maxresdefault', 'hqdefault'):
            thumb_url = f"https://img.youtube.com/vi/{video_id}/{res}.jpg"
            try:
                req = urllib.request.Request(thumb_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=15) as response:
                    data = response.read()
                    if len(data) < 1000:
                        continue
                    with open(thumbnail_path, 'wb') as f:
                        f.write(data)
                    return f"thumbnails/{video_id}.jpg"
            except (urllib.error.HTTPError, Exception):
                continue

    except Exception:
        pass
    return ""


def download_song(song: dict, songs_dir: Path) -> tuple[bool, str, str, str]:
    """
    Search and download a song from YouTube using yt-dlp.
    Uses progressive multi-strategy search with duration-based ranking.
    Downloads to the global songs/ directory.
    
    Returns:
        tuple: (success: bool, url: str, local_path: str, error_reason: str)
    """
    track_name = song["track_name"]
    artist = song["artist"]
    
    # Parse duration_ms for candidate ranking
    try:
        duration_ms = int(song.get("duration_ms") or 0)
    except (ValueError, TypeError):
        duration_ms = None
    
    # Sanitize filename
    base = f"{sanitize_filename(artist)}-{sanitize_filename(track_name)}"
    filename = f"{base}.m4a"
    output_template = str(songs_dir / f"{base}.%(ext)s")
    expected_path = songs_dir / filename
    relative_path = f"songs/{filename}"
    
    try:
        # Step 1: Search YouTube using progressive strategies
        url, strategy = search_youtube(
            track_name, artist, duration_ms=duration_ms
        )
        
        if not url:
            return False, "", "", strategy  # contains error description
        
        # Step 2: Download audio using the resolved URL
        dl_result = subprocess.run(
            [
                "yt-dlp",
                "-x",
                "--audio-format", "m4a",
                "--audio-quality", "0",
                "-o", output_template,
                url
            ],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout per song
        )
        
        if dl_result.returncode != 0:
            error_msg = dl_result.stderr.strip() if dl_result.stderr else "Unknown error"
            return False, url, "", error_msg
        
        # Verify the file was actually written to disk
        if not expected_path.exists():
            # Check if yt-dlp left the file with a different extension
            stem = expected_path.stem
            alt_files = list(songs_dir.glob(f"{stem}.*"))
            if alt_files:
                alt_files[0].rename(expected_path)
            else:
                return False, url, "", f"File not found after download at {expected_path}"
        
        return True, url, relative_path, ""
        
    except subprocess.TimeoutExpired:
        return False, "", "", "Download timed out"
    except FileNotFoundError:
        return False, "", "", "yt-dlp not found. Please install it: pip install yt-dlp"
    except Exception as e:
        return False, "", "", str(e)


def main():
    args = parse_args()
    csv_path = args.csv_file
    delay = args.delay
    
    # Validate input file
    if not os.path.exists(csv_path):
        print(f"Error: File not found: {csv_path}", file=sys.stderr)
        sys.exit(1)
    
    # Create output directory
    output_dir = create_output_directory(csv_path)
    songs_dir = get_songs_dir()
    print(f"Output directory: {output_dir}")
    print(f"Songs directory: {songs_dir}")
    
    # Parse CSV
    print(f"Parsing CSV: {csv_path}")
    songs = parse_csv(csv_path)
    print(f"Found {len(songs)} songs")
    
    # Process each song
    thumbnails_dir = get_thumbnails_dir()
    output_json_path = output_dir / "output.json"
    failures_json_path = output_dir / "failures.json"
    successful = []
    failures = []
    
    for i, song in enumerate(songs, 1):
        track_name = song["track_name"]
        artist = song["artist"]
        
        print(f"[{i}/{len(songs)}] Downloading: {artist} - {track_name}")
        
        success, url, local_path, error_reason = download_song(song, songs_dir)
        
        if success:
            entry = {
                **song,
                "url": url,
                "local_path": local_path
            }
            # Download thumbnail
            thumb_path = download_thumbnail(url, thumbnails_dir)
            if thumb_path:
                entry["thumbnail_path"] = thumb_path
            successful.append(entry)
            print(f"  ✓ {url}")
            
            # Save output.json after each successful download (resumable)
            with open(output_json_path, "w", encoding="utf-8") as f:
                json.dump(successful, f, indent=2, ensure_ascii=False)
        else:
            failures.append({
                "track_name": track_name,
                "artist": artist,
                "album": song.get("album", ""),
                "duration_ms": song.get("duration_ms", ""),
                "url": url,
                "error": error_reason
            })
            print(f"  ✗ Failed: {error_reason}")
            
            # Save failures.json after each failure
            with open(failures_json_path, "w", encoding="utf-8") as f:
                json.dump(failures, f, indent=2, ensure_ascii=False)
        
        # Rate limiting (skip delay on last song)
        if i < len(songs):
            time.sleep(delay)
    
    print(f"\nWrote {len(successful)} successful downloads to: {output_json_path}")
    if failures:
        print(f"Wrote {len(failures)} failures to: {failures_json_path}")
    
    # Summary
    print(f"\n--- Summary ---")
    print(f"Total songs: {len(songs)}")
    print(f"Successful: {len(successful)}")
    print(f"Failed: {len(failures)}")


if __name__ == "__main__":
    main()
