# Agent Documentation: Nexus Music Player - Search Module

## Project Overview

This module searches for YouTube URLs matching Spotify playlist tracks and downloads them as m4a audio files.

## File Structure

```
search/
├── main.py              # Step 1: Search Spotify CSV → YouTube URLs
├── download.py          # Step 2: Download audio from output.json URLs
├── retry_failures.py    # Step 3: Retry failed downloads
├── update_duration.py   # Step 4: Update duration_ms with actual audio durations
├── migrate_songs.py     # Step 5: Move songs to global songs/ directory
├── export_playlists.py  # Step 6: Export playlists to playlists/ directory
├── requirements.txt     # Dependencies: yt-dlp, mutagen
├── spotify_playlists/   # Input CSV files exported from Spotify
│   └── *.csv
├── songs/               # Global directory for all downloaded audio files
│   └── *.m4a
├── playlists/           # Final playlist JSON files
│   └── {Playlist_Name}.json
└── output/              # Intermediate output folders (can be deleted after migration)
    └── {playlist_name}/
        └── {timestamp}/
            ├── output.json      # Track metadata + YouTube URLs + local_path
            ├── failures.json    # Failed downloads with error messages
            └── downloads/       # Downloaded m4a audio files (before migration)
```

## Scripts

### main.py

**Purpose:** Search YouTube for tracks from a Spotify CSV export and save URLs.

**Usage:**
```bash
python main.py spotify_playlists/{Playlist}.csv [--delay SECONDS]
```

**Input:** Spotify CSV with columns: Track Name, Album Name, Artist Name(s), Release Date, Duration (ms)

**Output:** Creates `output/{playlist_name}/{timestamp}/output.json` with track metadata and YouTube URLs.

---

### download.py

**Purpose:** Download audio files from YouTube URLs in output.json.

**Usage:**
```bash
python download.py output/{playlist}/{timestamp}/output.json [--delay SECONDS]
```

**Behavior:**
- Downloads each track as m4a format using yt-dlp
- Creates `downloads/` subfolder for audio files
- Updates `output.json` with `local_path` field after each successful download
- Writes `failures.json` for failed downloads with error messages
- Default 5-second delay between downloads to avoid throttling

**Filename format:** `{Artist}-{Track_Name}.m4a` (spaces → underscores, invalid chars removed)

---

### retry_failures.py

**Purpose:** Retry failed downloads and update output.json with successes.

**Usage:**
```bash
python retry_failures.py output/{playlist}/{timestamp}/failures.json [--delay SECONDS]
```

**Behavior:**
- Reads failures.json and retries each download
- On success: adds `local_path` to matching track in output.json
- On failure: keeps track in failures.json with updated error
- Deletes failures.json if all retries succeed

---

### update_duration.py

**Purpose:** Update duration_ms in output.json with actual audio file durations.

**Usage:**
```bash
python update_duration.py output/{playlist}/{timestamp}/output.json
```

**Behavior:**
- Reads m4a files using mutagen library
- Updates `duration_ms` field (stored as string) for tracks with `local_path`
- Skips tracks without `local_path` (not yet downloaded)

---

### migrate_songs.py

**Purpose:** Move all downloaded songs to a global `songs/` directory, deduplicating across playlists.

**Usage:**
```bash
mkdir songs  # Create directory first
python migrate_songs.py [--dry-run] [--cleanup]
```

**Behavior:**
- Scans all `output.json` files under `output/`
- Moves unique songs to `songs/` directory (flat structure)
- Deduplicates: same filename across playlists = same song, keeps only one copy
- Updates `local_path` in all `output.json` files to relative paths: `songs/{filename}.m4a`
- `--dry-run`: Preview changes without moving files
- `--cleanup`: Remove empty `downloads/` directories after migration

---

### export_playlists.py

**Purpose:** Export output.json files to `playlists/` directory with playlist names.

**Usage:**
```bash
mkdir playlists  # Create directory first
python export_playlists.py [--dry-run]
```

**Behavior:**
- Finds all `output.json` files under `output/`
- Copies each to `playlists/{Playlist_Name}.json`
- Playlist name derived from parent folder structure

## Data Schemas

### output.json entry (before migration)

```json
{
  "track_name": "Song Title",
  "artist": "Artist Name",
  "album": "Album Name",
  "release_date": "YYYY-MM-DD",
  "duration_ms": "123456",
  "url": "https://www.youtube.com/watch?v=...",
  "local_path": "/absolute/path/to/downloads/Artist_Name-Song_Title.m4a"
}
```

### output.json entry (after migration)

```json
{
  "track_name": "Song Title",
  "artist": "Artist Name",
  "album": "Album Name",
  "release_date": "YYYY-MM-DD",
  "duration_ms": "123456",
  "url": "https://www.youtube.com/watch?v=...",
  "local_path": "songs/Artist_Name-Song_Title.m4a"
}
```

- `duration_ms`: String (not int) - original from Spotify, updated by update_duration.py
- `local_path`: Absolute path before migration, relative path (`songs/...`) after migration

### failures.json entry

```json
{
  "track_name": "Song Title",
  "artist": "Artist Name",
  "url": "https://www.youtube.com/watch?v=...",
  "error": "Error message from yt-dlp"
}
```

## Workflow

The scripts are designed to run in a specific order. Steps 1-4 are run per playlist, steps 5-6 are run once after all playlists are processed.

### Per-Playlist Steps (repeat for each playlist)

1. **Export playlist** from Spotify as CSV → `spotify_playlists/`
2. **Run `main.py`** to search YouTube and generate output.json
   ```bash
   python main.py spotify_playlists/My_Playlist.csv
   ```
3. **Run `download.py`** to download audio files
   ```bash
   python download.py output/My_Playlist/{timestamp}/output.json
   ```
4. **Run `retry_failures.py`** if any downloads failed
   ```bash
   python retry_failures.py output/My_Playlist/{timestamp}/failures.json
   ```

### Global Steps (run once after all playlists)

5. **Run `update_duration.py`** for each playlist to fix duration metadata
   ```bash
   python update_duration.py output/My_Playlist/{timestamp}/output.json
   ```
6. **Run `migrate_songs.py`** to consolidate all songs into `songs/` directory
   ```bash
   mkdir songs
   python migrate_songs.py --cleanup
   ```
7. **Run `export_playlists.py`** to create final playlist files
   ```bash
   mkdir playlists
   python export_playlists.py
   ```

### Final Directory Structure

```
search/
├── songs/                    # All audio files (deduplicated)
│   ├── Artist1-Track1.m4a
│   └── Artist2-Track2.m4a
├── playlists/                # Final playlist metadata
│   ├── My_Playlist.json
│   └── Another_Playlist.json
└── output/                   # Can be deleted after migration
```

## Key Patterns

- **Filename sanitization:** Replace `<>:"/\|?*` and spaces with underscores, collapse double underscores
- **Rate limiting:** Configurable `--delay` flag (default 5s) between downloads
- **Progress format:** `[current/total] ✓/✗ Artist - Track`
- **Incremental saves:** output.json saved after each successful operation
- **Timeout:** 5-minute timeout per download operation

## Dependencies

```
yt-dlp>=2026.2.4    # YouTube downloading
mutagen>=1.47.0     # Audio metadata reading
```

## Common Issues

- **"Sign in to confirm you're not a bot"**: YouTube rate limiting - increase delay or wait before retrying
- **Timeout errors**: Video may be very long or network issues - retry later
- **File not found in update_duration.py**: Run download.py first to create local files
