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
                '-o', str(output_path),
                url
            ],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        if result.returncode != 0:
            return False, result.stderr.strip() or result.stdout.strip()
        
        return True, ''
        
    except subprocess.TimeoutExpired:
        return False, 'Download timed out (5 minutes)'
    except Exception as e:
        return False, str(e)


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
    
    # Create downloads directory
    output_dir = json_path.parent
    downloads_dir = output_dir / 'downloads'
    downloads_dir.mkdir(exist_ok=True)
    
    print(f"Downloading {len(tracks)} tracks to: {downloads_dir}")
    print(f"Delay between downloads: {delay}s")
    print("-" * 50)
    
    failures = []
    success_count = 0
    
    for i, track in enumerate(tracks, 1):
        track_name = track.get('track_name', 'Unknown')
        artist = track.get('artist', 'Unknown')
        url = track.get('url', '')
        
        if not url:
            print(f"[{i}/{len(tracks)}] ✗ {artist} - {track_name}: No URL")
            failures.append({
                'track_name': track_name,
                'artist': artist,
                'url': url,
                'error': 'No URL provided'
            })
            continue
        
        # Create sanitized filename
        filename = f"{sanitize_filename(artist)}-{sanitize_filename(track_name)}.m4a"
        output_path = downloads_dir / filename
        
        print(f"[{i}/{len(tracks)}] Downloading: {artist} - {track_name}...")
        
        success, error = download_audio(url, output_path)
        
        if success:
            print(f"[{i}/{len(tracks)}] ✓ {artist} - {track_name}")
            success_count += 1
            
            # Update track with local path
            track['local_path'] = str(output_path.resolve())
            
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
    failures_path = output_dir / 'failures.json'
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
