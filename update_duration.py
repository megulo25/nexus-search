#!/usr/bin/env python3
"""
Update duration_ms in output.json files with actual audio file durations.
Uses mutagen to read m4a audio file metadata.
"""

import argparse
import json
import sys
from pathlib import Path

from mutagen.mp4 import MP4


def get_audio_duration(file_path: Path) -> tuple[int | None, str]:
    """
    Get audio duration in milliseconds from an m4a file.
    
    Returns:
        tuple: (duration_ms: int | None, error_message: str)
    """
    try:
        audio = MP4(str(file_path))
        duration_ms = int(audio.info.length * 1000)
        return duration_ms, ''
    except Exception as e:
        return None, str(e)


def process_output_json(json_path: Path) -> None:
    """Process an output.json file and update durations from local audio files."""
    
    # Validate input file
    if not json_path.exists():
        print(f"Error: File not found: {json_path}")
        sys.exit(1)
    
    # Load tracks
    with open(json_path, 'r', encoding='utf-8') as f:
        tracks = json.load(f)
    
    if not tracks:
        print("No tracks found in output.json")
        return
    
    print(f"Processing {len(tracks)} tracks in: {json_path}")
    print("-" * 50)
    
    updated_count = 0
    skipped_count = 0
    failed_count = 0
    
    for i, track in enumerate(tracks, 1):
        track_name = track.get('track_name', 'Unknown')
        artist = track.get('artist', 'Unknown')
        local_path = track.get('local_path')
        old_duration = track.get('duration_ms', 'N/A')
        
        # Skip entries without local_path
        if not local_path:
            print(f"[{i}/{len(tracks)}] ⊘ {artist} - {track_name}: No local_path (not downloaded)")
            skipped_count += 1
            continue
        
        file_path = Path(local_path)
        
        # If path doesn't exist as-is, try resolving relative to script directory
        if not file_path.exists():
            script_dir = Path(__file__).parent.resolve()
            file_path = script_dir / local_path
        
        # Check if file exists
        if not file_path.exists():
            print(f"[{i}/{len(tracks)}] ✗ {artist} - {track_name}: File not found")
            failed_count += 1
            continue
        
        # Get actual duration
        duration_ms, error = get_audio_duration(file_path)
        
        if duration_ms is not None:
            # Update duration (keep as string to match existing format)
            track['duration_ms'] = str(duration_ms)
            print(f"[{i}/{len(tracks)}] ✓ {artist} - {track_name}: {old_duration} → {duration_ms}")
            updated_count += 1
        else:
            print(f"[{i}/{len(tracks)}] ✗ {artist} - {track_name}: {error}")
            failed_count += 1
    
    # Save updated output.json
    if updated_count > 0:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(tracks, f, indent=2, ensure_ascii=False)
        print(f"\nUpdated: {json_path}")
    
    # Print summary
    print("-" * 50)
    print(f"Complete: {updated_count} updated, {skipped_count} skipped, {failed_count} failed")


def main():
    parser = argparse.ArgumentParser(
        description='Update duration_ms in output.json with actual audio file durations'
    )
    parser.add_argument(
        'output_json',
        type=Path,
        help='Path to output.json file containing tracks with local_path'
    )
    
    args = parser.parse_args()
    
    process_output_json(args.output_json)


if __name__ == '__main__':
    main()
