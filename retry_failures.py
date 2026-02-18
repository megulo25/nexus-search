#!/usr/bin/env python3
"""
Retry failed downloads from failures.json files.
Updates output.json with successful retries and keeps remaining failures.
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


def process_failures(failures_path: Path, delay: float) -> None:
    """Process a failures.json file and retry all failed downloads."""
    
    # Validate input file
    if not failures_path.exists():
        print(f"Error: File not found: {failures_path}")
        sys.exit(1)
    
    # Determine paths
    output_dir = failures_path.parent
    output_json_path = output_dir / 'output.json'
    
    # Use global songs/ directory relative to script location
    songs_dir = Path(__file__).parent.resolve() / 'songs'
    songs_dir.mkdir(exist_ok=True)
    
    # Load failures
    with open(failures_path, 'r', encoding='utf-8') as f:
        failures = json.load(f)
    
    if not failures:
        print("No failures found in failures.json")
        return
    
    # Load output.json
    if not output_json_path.exists():
        print(f"Error: output.json not found at: {output_json_path}")
        sys.exit(1)
    
    with open(output_json_path, 'r', encoding='utf-8') as f:
        tracks = json.load(f)
    
    print(f"Retrying {len(failures)} failed downloads")
    print(f"Output directory: {output_dir}")
    print(f"Delay between downloads: {delay}s")
    print("-" * 50)
    
    remaining_failures = []
    success_count = 0
    
    for i, failure in enumerate(failures, 1):
        track_name = failure.get('track_name', 'Unknown')
        artist = failure.get('artist', 'Unknown')
        url = failure.get('url', '')
        prev_error = failure.get('error', failure.get('error_reason', ''))
        duration_ms = failure.get('duration_ms')
        
        # If no URL, perform a fresh YouTube search
        if not url:
            print(f"[{i}/{len(failures)}] Searching: {artist} - {track_name}...")
            try:
                dur = int(duration_ms) if duration_ms else None
            except (ValueError, TypeError):
                dur = None
            url, strategy = search_youtube(track_name, artist, duration_ms=dur)
            if not url:
                print(f"[{i}/{len(failures)}] ✗ {artist} - {track_name}: {strategy}")
                remaining_failures.append({
                    'track_name': track_name,
                    'artist': artist,
                    'url': '',
                    'error': strategy
                })
                if i < len(failures):
                    time.sleep(delay)
                continue
            print(f"[{i}/{len(failures)}]   Found via {strategy}")
        
        # Create sanitized filename
        filename = f"{sanitize_filename(artist)}-{sanitize_filename(track_name)}.m4a"
        output_path = songs_dir / filename
        relative_path = f"songs/{filename}"
        
        print(f"[{i}/{len(failures)}] Retrying: {artist} - {track_name}...")
        
        success, error = download_audio(url, output_path)
        
        if success:
            print(f"[{i}/{len(failures)}] ✓ {artist} - {track_name}")
            success_count += 1
            
            # Find and update matching track in output.json
            # Match by URL first, then by artist+track_name for re-searched tracks
            matched = False
            for track in tracks:
                if track.get('url') == url:
                    track['local_path'] = relative_path
                    matched = True
                    break
            if not matched:
                # Track was re-searched (had no URL before) — match by metadata
                for track in tracks:
                    if (track.get('track_name', '').lower() == track_name.lower()
                            and track.get('artist', '').lower() == artist.lower()):
                        track['url'] = url
                        track['local_path'] = relative_path
                        matched = True
                        break
            if not matched:
                # Track doesn't exist in output.json yet — append it
                tracks.append({
                    'track_name': track_name,
                    'artist': artist,
                    'url': url,
                    'local_path': relative_path,
                })
            
            # Save output.json after each successful download
            with open(output_json_path, 'w', encoding='utf-8') as f:
                json.dump(tracks, f, indent=2, ensure_ascii=False)
        else:
            print(f"[{i}/{len(failures)}] ✗ {artist} - {track_name}: {error}")
            remaining_failures.append({
                'track_name': track_name,
                'artist': artist,
                'url': url,
                'error': error
            })
        
        # Rate limiting - don't delay after the last track
        if i < len(failures):
            time.sleep(delay)
    
    # Update or remove failures.json
    if remaining_failures:
        with open(failures_path, 'w', encoding='utf-8') as f:
            json.dump(remaining_failures, f, indent=2, ensure_ascii=False)
        print(f"\nRemaining failures saved to: {failures_path}")
    else:
        # Remove failures.json if all retries succeeded
        failures_path.unlink()
        print(f"\nAll retries successful - removed: {failures_path}")
    
    # Print summary
    print("-" * 50)
    print(f"Complete: {success_count}/{len(failures)} successful")
    if remaining_failures:
        print(f"Still failed: {len(remaining_failures)} tracks")


def main():
    parser = argparse.ArgumentParser(
        description='Retry failed downloads from failures.json files'
    )
    parser.add_argument(
        'failures_json',
        type=Path,
        help='Path to failures.json file containing failed downloads'
    )
    parser.add_argument(
        '--delay',
        type=float,
        default=5.0,
        help='Delay in seconds between downloads (default: 5.0)'
    )
    
    args = parser.parse_args()
    
    process_failures(args.failures_json, args.delay)


if __name__ == '__main__':
    main()
