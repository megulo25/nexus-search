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
        name = name.replace(char, "_")
    return name.strip()


def download_song(song: dict, output_dir: Path) -> tuple[bool, str, str]:
    """
    Search and download a song from YouTube using yt-dlp.
    
    Returns:
        tuple: (success: bool, url: str, error_reason: str)
    """
    track_name = song["track_name"]
    artist = song["artist"]
    search_query = f"{track_name} {artist}"
    
    # Sanitize filename
    filename = sanitize_filename(f"{artist} - {track_name}")
    output_template = str(output_dir / f"{filename}.%(ext)s")
    
    try:
        # Run yt-dlp to search, download, and get the URL
        result = subprocess.run(
            [
                "yt-dlp",
                "-x",
                "--audio-format", "m4a",
                "--audio-quality", "0",
                "--print", "webpage_url",
                "-o", output_template,
                f"ytsearch1:{search_query}"
            ],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout per song
        )
        
        if result.returncode != 0:
            error_msg = result.stderr.strip() if result.stderr else "Unknown error"
            # Check for common error patterns
            if "No video formats found" in error_msg or "no results" in error_msg.lower():
                return False, "", "No results found"
            return False, "", error_msg
        
        # Extract URL from stdout (first line should be the URL)
        url = result.stdout.strip().split("\n")[0]
        
        if not url or not url.startswith("http"):
            return False, "", "Could not extract YouTube URL"
        
        return True, url, ""
        
    except subprocess.TimeoutExpired:
        return False, "", "Download timed out"
    except FileNotFoundError:
        return False, "", "yt-dlp not found. Please install it: pip install yt-dlp"
    except Exception as e:
        return False, "", str(e)


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
    print(f"Output directory: {output_dir}")
    
    # Parse CSV
    print(f"Parsing CSV: {csv_path}")
    songs = parse_csv(csv_path)
    print(f"Found {len(songs)} songs")
    
    # Process each song
    successful = []
    failures = []
    
    for i, song in enumerate(songs, 1):
        track_name = song["track_name"]
        artist = song["artist"]
        
        print(f"[{i}/{len(songs)}] Downloading: {artist} - {track_name}")
        
        success, url, error_reason = download_song(song, output_dir)
        
        if success:
            successful.append({
                **song,
                "url": url
            })
            print(f"  ✓ Success: {url}")
        else:
            failures.append({
                "track_name": track_name,
                "artist": artist,
                "error_reason": error_reason
            })
            print(f"  ✗ Failed: {error_reason}")
        
        # Rate limiting (skip delay on last song)
        if i < len(songs):
            time.sleep(delay)
    
    # Write output JSON
    output_json_path = output_dir / "output.json"
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(successful, f, indent=2, ensure_ascii=False)
    print(f"\nWrote {len(successful)} successful downloads to: {output_json_path}")
    
    # Write failures JSON (if any)
    if failures:
        failures_json_path = output_dir / "failures.json"
        with open(failures_json_path, "w", encoding="utf-8") as f:
            json.dump(failures, f, indent=2, ensure_ascii=False)
        print(f"Wrote {len(failures)} failures to: {failures_json_path}")
    
    # Summary
    print(f"\n--- Summary ---")
    print(f"Total songs: {len(songs)}")
    print(f"Successful: {len(successful)}")
    print(f"Failed: {len(failures)}")


if __name__ == "__main__":
    main()
