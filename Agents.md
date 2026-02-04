# Agent Documentation: Nexus Music Player - Search Module

## Project Overview

This module searches for YouTube URLs matching Spotify playlist tracks and downloads them as m4a audio files.

## File Structure

```
search/
├── main.py              # Search Spotify CSV → YouTube URLs
├── download.py          # Download audio from output.json URLs
├── retry_failures.py    # Retry failed downloads
├── update_duration.py   # Update duration_ms with actual audio durations
├── requirements.txt     # Dependencies: yt-dlp, mutagen
├── spotify_playlists/   # Input CSV files exported from Spotify
│   └── *.csv
└── output/              # Generated output folders
    └── {playlist_name}/
        └── {timestamp}/
            ├── output.json      # Track metadata + YouTube URLs + local_path
            ├── failures.json    # Failed downloads with error messages
            └── downloads/       # Downloaded m4a audio files
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

## Data Schemas

### output.json entry

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

- `duration_ms`: String (not int) - original from Spotify, updated by update_duration.py
- `local_path`: Only present after successful download

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

1. Export playlist from Spotify as CSV → `spotify_playlists/`
2. Run `main.py` to search YouTube and generate output.json
3. Run `download.py` to download audio files
4. Run `retry_failures.py` if any downloads failed
5. Run `update_duration.py` to fix duration metadata

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
