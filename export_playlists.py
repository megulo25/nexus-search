#!/usr/bin/env python3
"""
Export output.json files to a playlists/ directory with playlist names.
Copies output.json files and renames them to {playlist_name}.json.
"""

import argparse
import shutil
import sys
from pathlib import Path


def find_output_json_files(output_dir: Path) -> list[tuple[str, Path]]:
    """
    Find all output.json files and extract playlist names.
    
    Returns:
        list of (playlist_name, output_json_path) tuples
    """
    results = []
    
    for json_path in output_dir.rglob('output.json'):
        # Structure: output/{playlist_name}/{timestamp}/output.json
        # Parent is timestamp folder, grandparent is playlist folder
        timestamp_dir = json_path.parent
        playlist_dir = timestamp_dir.parent
        
        # Verify structure (playlist_dir should be under output_dir)
        if playlist_dir.parent == output_dir:
            playlist_name = playlist_dir.name
            results.append((playlist_name, json_path))
    
    return results


def export_playlists(playlists_dir: Path, output_dir: Path, dry_run: bool) -> None:
    """Export output.json files to playlists/ directory."""
    
    # Validate playlists directory exists
    if not playlists_dir.exists():
        print(f"Error: Playlists directory does not exist: {playlists_dir}")
        print("Please create it first: mkdir playlists")
        sys.exit(1)
    
    if not playlists_dir.is_dir():
        print(f"Error: {playlists_dir} is not a directory")
        sys.exit(1)
    
    # Find all output.json files
    playlist_files = find_output_json_files(output_dir)
    
    if not playlist_files:
        print("No output.json files found")
        return
    
    print(f"Found {len(playlist_files)} playlist(s)")
    print("-" * 50)
    
    # Track statistics
    exported_count = 0
    error_count = 0
    
    for playlist_name, source_path in sorted(playlist_files):
        dest_path = playlists_dir / f"{playlist_name}.json"
        
        if dry_run:
            print(f"[dry-run] Would copy: {playlist_name}.json")
            exported_count += 1
        else:
            try:
                shutil.copy2(str(source_path), str(dest_path))
                print(f"✓ Exported: {playlist_name}.json")
                exported_count += 1
            except Exception as e:
                print(f"✗ {playlist_name}.json: {e}")
                error_count += 1
    
    # Print summary
    print("-" * 50)
    print(f"Summary:")
    print(f"  Exported: {exported_count}")
    print(f"  Errors: {error_count}")


def main():
    parser = argparse.ArgumentParser(
        description='Export output.json files to playlists/ directory'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without copying files'
    )
    
    args = parser.parse_args()
    
    # Determine paths relative to script location
    script_dir = Path(__file__).parent.resolve()
    playlists_dir = script_dir / 'playlists'
    output_dir = script_dir / 'output'
    
    if args.dry_run:
        print("=== DRY RUN MODE ===\n")
    
    export_playlists(playlists_dir, output_dir, args.dry_run)


if __name__ == '__main__':
    main()
