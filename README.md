# Nexus Music Player - Search Module

Download audio from YouTube based on your Spotify playlists.

## Overview

This module takes Spotify playlist exports (CSV files) and:
1. Searches YouTube for matching tracks
2. Downloads audio in high-quality m4a format
3. Organizes files by playlist with full metadata

## Requirements

- Python 3.10+
- yt-dlp
- mutagen

## Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Quick Start

### 1. Export Your Spotify Playlist

Use a tool like [Exportify](https://exportify.net/) to export your Spotify playlist as a CSV file. Save it to the `spotify_playlists/` folder.

### 2. Search YouTube for Tracks

```bash
python main.py spotify_playlists/My_Playlist.csv
```

This creates an output folder with YouTube URLs for each track:
```
output/My_Playlist/2026-02-04T12-30/output.json
```

### 3. Download Audio Files

```bash
python download.py output/My_Playlist/2026-02-04T12-30/output.json
```

Downloads are saved to:
```
output/My_Playlist/2026-02-04T12-30/downloads/
├── Artist_Name-Track_Title.m4a
├── Another_Artist-Another_Song.m4a
└── ...
```

### 4. Retry Failed Downloads (if any)

```bash
python retry_failures.py output/My_Playlist/2026-02-04T12-30/failures.json
```

### 5. Update Duration Metadata (optional)

The original duration comes from Spotify. To update it with the actual audio duration:

```bash
python update_duration.py output/My_Playlist/2026-02-04T12-30/output.json
```

## Scripts

| Script               | Purpose                                                     |
| -------------------- | ----------------------------------------------------------- |
| `main.py`            | Search YouTube for Spotify tracks, save URLs to output.json |
| `download.py`        | Download audio from YouTube URLs in output.json             |
| `retry_failures.py`  | Retry failed downloads from failures.json                   |
| `update_duration.py` | Update duration_ms with actual audio file durations         |

## Command Line Options

### main.py
```bash
python main.py <csv_file> [--delay SECONDS]
```
- `csv_file`: Path to Spotify CSV export
- `--delay`: Seconds between searches (default: 2)

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
- `--delay`: Seconds between downloads (default: 5)

### update_duration.py
```bash
python update_duration.py <output_json>
```
- `output_json`: Path to output.json file

## Output Structure

```
output/
└── Playlist_Name/
    └── 2026-02-04T12-30/           # Timestamp of search
        ├── output.json              # Track metadata + URLs + local paths
        ├── failures.json            # Failed downloads (if any)
        └── downloads/               # Audio files
            ├── Artist-Track.m4a
            └── ...
```

## Output.json Format

```json
[
  {
    "track_name": "Song Title",
    "artist": "Artist Name",
    "album": "Album Name",
    "release_date": "2024-01-15",
    "duration_ms": "234567",
    "url": "https://www.youtube.com/watch?v=abc123",
    "local_path": "/path/to/downloads/Artist_Name-Song_Title.m4a"
  }
]
```

## Tips

- **Avoid rate limiting**: Use the `--delay` flag to add time between downloads. Default is 5 seconds, increase if you encounter errors.
- **Resume interrupted downloads**: The scripts save progress after each successful download. Just run again to continue.
- **Check failures**: Look at `failures.json` for error details. Common issues include region-restricted videos or removed content.

## Troubleshooting

### "Sign in to confirm you're not a bot"
YouTube is rate limiting requests. Wait a few minutes and try again with a longer delay:
```bash
python download.py output.json --delay 10
```

### Download times out
The video may be very long or there may be network issues. The script has a 5-minute timeout per download. Try again later.

### "No local_path" in update_duration.py
The track hasn't been downloaded yet. Run `download.py` first.

## License

MIT
