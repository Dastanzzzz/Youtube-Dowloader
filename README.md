# YouTube GUI Downloader

Desktop GUI downloader for YouTube links with:

- Video or audio-only mode
- Selectable quality options (fetched from the URL)
- Folder picker for choosing where files are saved
- Progress bar and live log output
- Pause and cancel controls while downloading
- Download history panel with persistent storage
- Filename template options with automatic safe filename cleanup

## Requirements

- Python 3.10+
- `yt-dlp`

Optional but recommended:

- `ffmpeg` in PATH (improves format merging support for some video/audio combinations)

## Install

```bash
pip install -r requirements.txt
```

## Run

```bash
python main.py
```

## Build EXE (Windows)

Install dependencies first, then run:

```bash
pyinstaller --noconfirm --windowed --onefile --name YouTubeDownloader main.py
```

Output executable:

- `dist/YouTubeDownloader.exe`

## How To Use

1. Paste a YouTube URL.
2. Click **Fetch Qualities**.
3. Choose **Video** or **Audio Only** mode.
4. Choose a quality from the dropdown.
5. Choose output folder with **Browse**.
6. Click **Start Download**.
7. Use **Pause/Resume** or **Cancel** while active if needed.

## Notes

- If you paste a playlist URL, the app uses the first entry.
- Available quality options depend on what YouTube provides for that specific video.
- Download history is saved in `download_history.json` beside the app.
