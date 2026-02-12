#!/usr/bin/env python3
"""
Migrate downloaded songs to a global songs/ directory.
Deduplicates files and updates output.json with relative paths.
"""

import argparse
import json
import shutil
import sys
from pathlib import Path


def find_output_json_files(output_dir: Path) -> list[Path]:
    """Find all output.json files under the output directory."""
    return list(output_dir.rglob('output.json'))


def build_file_map(output_json_files: list[Path]) -> dict[str, list[tuple[Path, dict]]]:
    """
    Build a map of filename -> list of (output_json_path, track) tuples.
    This identifies duplicates and tracks that need updating.
    """
    file_map: dict[str, list[tuple[Path, dict]]] = {}
    
    for json_path in output_json_files:
        with open(json_path, 'r', encoding='utf-8') as f:
            tracks = json.load(f)
        
        for track in tracks:
            local_path = track.get('local_path')
            if not local_path:
                continue
            
            # Extract filename from the path
            filename = Path(local_path).name
            
            if filename not in file_map:
                file_map[filename] = []
            
            file_map[filename].append((json_path, track))
    
    return file_map


def migrate_songs(songs_dir: Path, output_dir: Path, dry_run: bool, cleanup: bool) -> None:
    """Migrate all songs to the global songs/ directory."""
    
    # Create songs directory if it doesn't exist
    songs_dir.mkdir(exist_ok=True)
    
    if not songs_dir.is_dir():
        print(f"Error: {songs_dir} is not a directory")
        sys.exit(1)
    
    # Find all output.json files
    output_json_files = find_output_json_files(output_dir)
    
    if not output_json_files:
        print("No output.json files found")
        return
    
    print(f"Found {len(output_json_files)} output.json files")
    
    # Build file map for deduplication
    file_map = build_file_map(output_json_files)
    
    if not file_map:
        print("No tracks with local_path found")
        return
    
    print(f"Found {len(file_map)} unique songs across all playlists")
    print("-" * 50)
    
    # Track statistics
    moved_count = 0
    duplicate_count = 0
    error_count = 0
    updated_json_files: set[Path] = set()
    downloads_dirs: set[Path] = set()
    
    # Process each unique file
    for filename, track_entries in file_map.items():
        # Find the first entry with an existing file to use as source
        source_path = None
        for json_path, track in track_entries:
            candidate = Path(track['local_path'])
            if candidate.exists():
                source_path = candidate
                break
            # Try resolving relative to the output.json's directory
            candidate = json_path.parent / Path(track['local_path']).name
            if candidate.exists():
                source_path = candidate
                break
        
        if source_path is None:
            print(f"✗ {filename}: Source file not found")
            error_count += 1
            continue
        
        dest_path = songs_dir / filename
        relative_path = f"songs/{filename}"
        
        # Move or copy the file (only once per unique filename)
        if not dry_run:
            try:
                if not dest_path.exists():
                    shutil.move(str(source_path), str(dest_path))
                    print(f"✓ Moved: {filename}")
                    moved_count += 1
                else:
                    print(f"⊘ Already exists: {filename}")
                    duplicate_count += 1
            except Exception as e:
                print(f"✗ {filename}: {e}")
                error_count += 1
                continue
        else:
            if not dest_path.exists():
                print(f"[dry-run] Would move: {filename}")
                moved_count += 1
            else:
                print(f"[dry-run] Already exists: {filename}")
                duplicate_count += 1
        
        # Update all output.json entries that reference this file
        for json_path, track in track_entries:
            old_path = Path(track['local_path'])
            
            # Track downloads directories for cleanup
            if old_path.parent.name == 'downloads':
                downloads_dirs.add(old_path.parent)
            
            # Delete duplicate source files (not the first one we moved)
            if not dry_run and old_path.exists() and old_path != source_path:
                try:
                    old_path.unlink()
                    duplicate_count += 1
                except Exception:
                    pass
            
            # Update track's local_path to relative path
            track['local_path'] = relative_path
            updated_json_files.add(json_path)
    
    # Save updated output.json files
    if not dry_run:
        for json_path in updated_json_files:
            with open(json_path, 'r', encoding='utf-8') as f:
                tracks = json.load(f)
            
            # Re-apply the relative paths (we modified the track dicts in memory)
            for track in tracks:
                local_path = track.get('local_path')
                if local_path and not local_path.startswith('songs/'):
                    filename = Path(local_path).name
                    track['local_path'] = f"songs/{filename}"
            
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(tracks, f, indent=2, ensure_ascii=False)
        
        print(f"\nUpdated {len(updated_json_files)} output.json files")
    else:
        print(f"\n[dry-run] Would update {len(updated_json_files)} output.json files")
    
    # Cleanup empty downloads directories
    if cleanup and not dry_run:
        cleaned_count = 0
        for downloads_dir in downloads_dirs:
            if downloads_dir.exists() and not any(downloads_dir.iterdir()):
                try:
                    downloads_dir.rmdir()
                    cleaned_count += 1
                except Exception:
                    pass
        if cleaned_count > 0:
            print(f"Removed {cleaned_count} empty downloads/ directories")
    elif cleanup and dry_run:
        print(f"[dry-run] Would check {len(downloads_dirs)} downloads/ directories for cleanup")
    
    # Print summary
    print("-" * 50)
    print(f"Summary:")
    print(f"  Moved: {moved_count}")
    print(f"  Duplicates (skipped/removed): {duplicate_count}")
    print(f"  Errors: {error_count}")
    print(f"  JSON files updated: {len(updated_json_files)}")


def main():
    parser = argparse.ArgumentParser(
        description='Migrate songs to a global songs/ directory'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without moving files'
    )
    parser.add_argument(
        '--cleanup',
        action='store_true',
        help='Remove empty downloads/ directories after migration'
    )
    
    args = parser.parse_args()
    
    # Determine paths relative to script location
    script_dir = Path(__file__).parent.resolve()
    songs_dir = script_dir / 'songs'
    output_dir = script_dir / 'output'
    
    if args.dry_run:
        print("=== DRY RUN MODE ===\n")
    
    migrate_songs(songs_dir, output_dir, args.dry_run, args.cleanup)


if __name__ == '__main__':
    main()
