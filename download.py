#!/usr/bin/env python3
"""
Download audio files from YouTube URLs in output.json files.
Uses yt-dlp to download audio in m4a format.
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from yt_search import search_youtube


def sanitize_filename(name: str) -> str:
    """Remove invalid characters and replace spaces with underscores."""
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


def download_audio(url: str, output_path: Path) -> tuple[bool, str]:
    """
    Download audio from YouTube URL using yt-dlp.
    
    Returns:
        tuple: (success: bool, error_message: str)
    """
    try:
        result = subprocess.run(
            [
                'yt-dlp',
                '--extract-audio',
                '--audio-format', 'm4a',
                '--audio-quality', '0',
                '-o', str(output_path.with_suffix('.%(ext)s')),
                url
            ],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        if result.returncode != 0:
            return False, result.stderr.strip() or result.stdout.strip()
        
        # Verify the file was actually written to disk
        if not output_path.exists():
            # Check if yt-dlp left the file with a different extension
            stem = output_path.stem
            alt_files = list(output_path.parent.glob(f"{stem}.*"))
            if alt_files:
                alt_files[0].rename(output_path)
            else:
                return False, f'Download succeeded but file not found at {output_path}'
        
        return True, ''
        
    except subprocess.TimeoutExpired:
        return False, 'Download timed out (5 minutes)'
    except Exception as e:
        return False, str(e)


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


def process_output_json(json_path: Path, delay: float) -> None:
    """Process an output.json file and download all tracks."""
    
    # Validate input file
    if not json_path.exists():
        print(f"Error: File not found: {json_path}")
        sys.exit(1)
    
    if not json_path.name == 'output.json':
        print(f"Warning: Expected 'output.json', got '{json_path.name}'")
    
    # Load tracks
    with open(json_path, 'r', encoding='utf-8') as f:
        tracks = json.load(f)
    
    if not tracks:
        print("No tracks found in output.json")
        return
    
    # Use global songs/ directory relative to script location
    songs_dir = Path(__file__).parent.resolve() / 'songs'
    songs_dir.mkdir(exist_ok=True)

    thumbnails_dir = Path(__file__).parent.resolve() / 'thumbnails'
    thumbnails_dir.mkdir(exist_ok=True)
    
    print(f"Downloading {len(tracks)} tracks to: {songs_dir}")
    print(f"Delay between downloads: {delay}s")
    print("-" * 50)
    
    failures = []
    success_count = 0
    
    for i, track in enumerate(tracks, 1):
        track_name = track.get('track_name', 'Unknown')
        artist = track.get('artist', 'Unknown')
        url = track.get('url', '')
        
        # If no URL, perform a fresh YouTube search
        if not url:
            print(f"[{i}/{len(tracks)}] Searching: {artist} - {track_name}...")
            try:
                dur = int(track.get('duration_ms') or 0)
            except (ValueError, TypeError):
                dur = None
            url, strategy = search_youtube(track_name, artist, duration_ms=dur)
            if not url:
                print(f"[{i}/{len(tracks)}] ✗ {artist} - {track_name}: {strategy}")
                failures.append({
                    'track_name': track_name,
                    'artist': artist,
                    'url': '',
                    'error': strategy
                })
                if i < len(tracks):
                    time.sleep(delay)
                continue
            # Store the resolved URL back on the track
            track['url'] = url
            print(f"[{i}/{len(tracks)}]   Found via {strategy}")
        
        # Create sanitized filename
        filename = f"{sanitize_filename(artist)}-{sanitize_filename(track_name)}.m4a"
        output_path = songs_dir / filename
        relative_path = f"songs/{filename}"
        
        print(f"[{i}/{len(tracks)}] Downloading: {artist} - {track_name}...")
        
        success, error = download_audio(url, output_path)
        
        if success:
            print(f"[{i}/{len(tracks)}] ✓ {artist} - {track_name}")
            success_count += 1
            
            # Update track with local path
            track['local_path'] = relative_path

            # Download thumbnail
            thumb_path = download_thumbnail(url, thumbnails_dir)
            if thumb_path:
                track['thumbnail_path'] = thumb_path
            
            # Save output.json after each successful download
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(tracks, f, indent=2, ensure_ascii=False)
        else:
            print(f"[{i}/{len(tracks)}] ✗ {artist} - {track_name}: {error}")
            failures.append({
                'track_name': track_name,
                'artist': artist,
                'url': url,
                'error': error
            })
        
        # Rate limiting - don't delay after the last track
        if i < len(tracks):
            time.sleep(delay)
    
    # Save failures
    failures_path = json_path.parent / 'failures.json'
    if failures:
        with open(failures_path, 'w', encoding='utf-8') as f:
            json.dump(failures, f, indent=2, ensure_ascii=False)
        print(f"\nFailures saved to: {failures_path}")
    elif failures_path.exists():
        # Remove old failures file if all downloads succeeded
        failures_path.unlink()
    
    # Print summary
    print("-" * 50)
    print(f"Complete: {success_count}/{len(tracks)} successful")
    if failures:
        print(f"Failed: {len(failures)} tracks")


def main():
    parser = argparse.ArgumentParser(
        description='Download audio from YouTube URLs in output.json files'
    )
    parser.add_argument(
        'output_json',
        type=Path,
        help='Path to output.json file containing YouTube URLs'
    )
    parser.add_argument(
        '--delay',
        type=float,
        default=5.0,
        help='Delay in seconds between downloads (default: 5.0)'
    )
    
    args = parser.parse_args()
    
    process_output_json(args.output_json, args.delay)


if __name__ == '__main__':
    main()
