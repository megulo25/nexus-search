# Nexus Music Player - Search Module

Download audio from YouTube based on your Spotify playlists.

## Overview

This module takes Spotify playlist exports (CSV files) and:
1. Searches YouTube for matching tracks and downloads audio in high-quality m4a format to a global `songs/` directory
2. Retries any failed downloads
3. Exports playlist metadata for use in the Nexus backend

All scripts download directly to `search/songs/`, so songs are deduplicated across playlists automatically.

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

## Quick Start — Unified Migration

The easiest way to go from Spotify CSVs to fully imported backend data is the **unified migration script** at the project root:

```bash
# From the project root
./migrate.sh
```

### Directory Convention

Organize your Spotify CSV exports by username:

```
search/spotify_playlists/
└── matthews/              ← directory name = backend username
    ├── Liked_Songs.csv
    ├── Old_school_funk.csv
    └── StreamBeats_Hiphop.csv
```

The script prompts for:
- **Playlist directory** — path to a `spotify_playlists/{username}/` directory containing `.csv` files
- **Download delay** — seconds between downloads (default: 2)

The directory name is used as the backend username (validated against `backend/data/users.json`). Each `.csv` file becomes a separate playlist named after the file.

The script then runs the full pipeline automatically for each CSV:
1. YouTube search & download (`.m4a` files → `search/songs/`)
2. Auto-retry failed downloads (once)
3. Update track durations from actual audio metadata
4. Export playlist JSON to `search/playlists/`

Then once for all playlists:
5. Copy songs to `backend/songs/` (no-clobber)
6. Copy playlist JSONs to `backend/playlists/{username}/`
7. Run `yarn import:playlists` to update `backend/data/tracks.json` and `playlists.json`

### Prerequisites

- `python3` with `yt-dlp` and `mutagen` installed
- `node` and `yarn`
- Spotify CSV exports with columns: `Track Name`, `Artist Name(s)`, `Album Name`, `Release Date`, `Duration (ms)` 
  (Use [Exportify](https://exportify.net/) to export from Spotify)

---

## Manual Workflow (Advanced)

If you need more control over individual steps, you can run them manually:

### 1. Export Your Spotify Playlist

Use a tool like [Exportify](https://exportify.net/) to export your Spotify playlist as a CSV file. Save it to the `spotify_playlists/` folder.

### 2. Search YouTube & Download Audio

```bash
python youtube-search.py spotify_playlists/My_Playlist.csv
```

Searches YouTube for each track, downloads audio as `.m4a` to `search/songs/`, and saves metadata to a timestamped output folder:

```
songs/
├── Artist_Name-Track_Title.m4a
└── ...

output/My_Playlist/2026-02-04T12-30/
├── output.json       # Track metadata + YouTube URLs + local_path references
└── failures.json     # Failed downloads (if any)
```

The `output.json` is saved after each successful download, so the process is **resumable**.

### 3. Retry Failed Downloads (if needed)

```bash
python retry_failures.py output/My_Playlist/2026-02-04T12-30/failures.json
```

### 4. Re-download from Existing URLs (optional)

```bash
python download.py output/My_Playlist/2026-02-04T12-30/output.json
```

### 5. Update Duration Metadata (optional)

```bash
python update_duration.py output/My_Playlist/2026-02-04T12-30/output.json
```

### 6. Export Final Playlists

```bash
python export_playlists.py
```

Copies each `output.json` to `playlists/<Playlist_Name>.json`.

### 7. Migrate to Backend

```bash
cp playlists/My_Playlist.json ../backend/playlists/{username}/My_Playlist.json
cp -n songs/*.m4a ../backend/songs/
cd ../backend && yarn import:playlists
```

## Scripts

| Script                | Purpose                                                          |
| --------------------- | ---------------------------------------------------------------- |
| `../migrate.sh`       | **Unified script** — runs the entire pipeline interactively      |
| `youtube-search.py`   | Search YouTube for Spotify tracks, download audio, save metadata |
| `retry_failures.py`   | Retry failed downloads from failures.json                        |
| `download.py`         | Re-download audio from existing URLs in output.json              |
| `update_duration.py`  | Update duration_ms with actual audio file durations              |
| `export_playlists.py` | Export playlist JSON files to `playlists/` directory             |
| `migrate_songs.py`    | Legacy: move songs from old per-playlist dirs to `songs/`        |

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

### export_playlists.py
```bash
python export_playlists.py [--dry-run]
```
- `--dry-run`: Preview changes without copying files

## Playlist JSON Format

Playlist files use relative paths pointing to the global `songs/` directory:

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
- **Dry run first**: Use `--dry-run` with `export_playlists.py` to preview changes before committing.

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
