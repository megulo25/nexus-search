# Nexus Music Player - Search Module

Download audio from YouTube based on your Spotify playlists.

## Overview

This module takes Spotify playlist exports (CSV files) and:
1. Searches YouTube for matching tracks and downloads audio in high-quality m4a format
2. Retries any failed downloads
3. Consolidates all songs into a global library (deduplicated)
4. Exports playlist metadata for use in the Nexus backend

## Requirements

- Python 3.10+
- yt-dlp
- mutagen

## Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Workflow

### 1. Export Your Spotify Playlist

Use a tool like [Exportify](https://exportify.net/) to export your Spotify playlist as a CSV file. Save it to the `spotify_playlists/` folder.

The CSV must include these columns: `Track Name`, `Artist Name(s)`, `Album Name`, `Release Date`, `Duration (ms)`.

### 2. Search YouTube & Download Audio

```bash
python youtube-search.py spotify_playlists/My_Playlist.csv
```

This searches YouTube for each track, downloads the audio as `.m4a`, and saves everything to a timestamped output folder:

```
output/My_Playlist/2026-02-04T12-30/
├── output.json       # Track metadata + YouTube URLs + local file paths
├── failures.json     # Failed downloads (if any)
├── Artist_Name-Track_Title.m4a
├── Another_Artist-Another_Song.m4a
└── ...
```

The `output.json` is saved after each successful download, so the process is **resumable** — just run the same command again to pick up where you left off.

### 3. Retry Failed Downloads (if needed)

If some downloads failed (check `failures.json`), retry them:

```bash
python retry_failures.py output/My_Playlist/2026-02-04T12-30/failures.json
```

This retries each failed track, updates `output.json` on success, and removes `failures.json` if all retries succeed.

### 4. Re-download from Existing URLs (optional)

If you need to re-download audio from URLs already saved in `output.json` (e.g., after clearing downloads), use:

```bash
python download.py output/My_Playlist/2026-02-04T12-30/output.json
```

Downloads are saved to a `downloads/` subdirectory and `output.json` is updated with the new `local_path` values.

### 5. Update Duration Metadata (optional)

The original `duration_ms` comes from Spotify. To replace it with the actual audio file duration:

```bash
python update_duration.py output/My_Playlist/2026-02-04T12-30/output.json
```

### 6. Migrate Songs to Global Directory

After processing all your playlists, consolidate songs into a single `songs/` folder:

```bash
python migrate_songs.py --cleanup
```

This:
- Moves all audio files from per-playlist output dirs into `search/songs/`
- Deduplicates across playlists (same song in multiple playlists is stored once)
- Updates all `output.json` files to reference the new `songs/` paths
- With `--cleanup`, removes empty download directories

### 7. Export Final Playlists

Export playlist metadata to a clean `playlists/` folder:

```bash
python export_playlists.py
```

This copies each `output.json` to `playlists/<Playlist_Name>.json`, named after the playlist directory.

### Final Structure

```
search/
├── songs/                          # All audio files (deduplicated)
│   ├── Artist1-Track1.m4a
│   ├── Artist2-Track2.m4a
│   └── ...
├── playlists/                      # Playlist metadata for the backend
│   ├── My_Playlist.json
│   ├── Another_Playlist.json
│   └── ...
└── output/                         # Intermediate files (can be deleted)
```

## Scripts

| Script                | Step | Purpose                                                          |
| --------------------- | ---- | ---------------------------------------------------------------- |
| `youtube-search.py`   | 1    | Search YouTube for Spotify tracks, download audio, save metadata |
| `download.py`         | -    | Re-download audio from existing URLs in output.json              |
| `retry_failures.py`   | 2    | Retry failed downloads from failures.json                        |
| `update_duration.py`  | 3    | Update duration_ms with actual audio file durations              |
| `migrate_songs.py`    | 4    | Move all songs to global `songs/` directory, deduplicate         |
| `export_playlists.py` | 5    | Export playlist JSON files to `playlists/` directory             |

## Command Line Options

### youtube-search.py
```bash
python youtube-search.py <csv_file> [--delay SECONDS]
```
- `csv_file`: Path to Spotify CSV export
- `--delay`: Seconds between downloads (default: 2)

### download.py
```bash
python download.py <output_json> [--delay SECONDS]
```
- `output_json`: Path to output.json file
- `--delay`: Seconds between downloads (default: 5)

### retry_failures.py
```bash
python retry_failures.py <failures_json> [--delay SECONDS]
```
- `failures_json`: Path to failures.json file
- `--delay`: Seconds between retries (default: 5)

### update_duration.py
```bash
python update_duration.py <output_json>
```
- `output_json`: Path to output.json file

### migrate_songs.py
```bash
python migrate_songs.py [--dry-run] [--cleanup]
```
- `--dry-run`: Preview changes without moving files
- `--cleanup`: Remove empty download directories after migration

### export_playlists.py
```bash
python export_playlists.py [--dry-run]
```
- `--dry-run`: Preview changes without copying files

## Output Structure

### After Search & Download (per playlist)

```
output/
└── Playlist_Name/
    └── 2026-02-04T12-30/           # Timestamp of search
        ├── output.json              # Track metadata + YouTube URLs + local paths
        ├── failures.json            # Failed downloads (if any)
        ├── Artist-Track.m4a         # Audio files (from youtube-search.py)
        └── downloads/               # Audio files (from download.py, if used)
            └── Artist-Track.m4a
```

### After Migration

```
search/
├── songs/                          # All audio files (deduplicated)
│   ├── Artist1-Track1.m4a
│   └── ...
├── playlists/                      # Playlist metadata
│   ├── Playlist1.json
│   └── ...
└── output/                         # Can be deleted after migration
```

## Playlist JSON Format

After migration, playlist files use relative paths:

```json
[
  {
    "track_name": "Song Title",
    "artist": "Artist Name",
    "album": "Album Name",
    "release_date": "2024-01-15",
    "duration_ms": "234567",
    "url": "https://www.youtube.com/watch?v=abc123",
    "local_path": "songs/Artist_Name-Song_Title.m4a"
  }
]
```

## Tips

- **Avoid rate limiting**: Use the `--delay` flag to add time between downloads. Default is 2 seconds for search, 5 seconds for download/retry. Increase if you encounter errors.
- **Resume interrupted downloads**: `youtube-search.py` saves `output.json` after each successful download. Just run the same command again to continue.
- **Check failures**: Look at `failures.json` for error details. Common issues include region-restricted videos or removed content.
- **Dry run first**: Use `--dry-run` with `migrate_songs.py` and `export_playlists.py` to preview changes before committing.

## Troubleshooting

### "Sign in to confirm you're not a bot"
YouTube is rate limiting requests. Wait a few minutes and try again with a longer delay:
```bash
python youtube-search.py spotify_playlists/My_Playlist.csv --delay 10
```

### Download times out
The video may be very long or there may be network issues. The script has a 5-minute timeout per download. Try again later.

### "No local_path" in update_duration.py
The track hasn't been downloaded yet. Run `youtube-search.py` or `download.py` first.

## License

MIT
