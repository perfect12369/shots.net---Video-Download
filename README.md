# Shots Downloader

A local Mac tool to download videos from [magazine.shots.net/the-work](https://magazine.shots.net/the-work).

## Features
- Select a date range to filter videos.
- Automatically scrapes the website for videos within that range.
- Downloads videos using `yt-dlp` (supports Vimeo, YouTube, etc.).
- Saves videos as `Title_YYYY-MM-DD.mp4` in the `downloads` folder.
- Skips downloads if a file with the same name already exists.

## How to Run

1. Open your terminal in this directory.
2. Run the following command:
   ```bash
   streamlit run app.py
   ```
3. A new tab will open in your browser with the application.

## Troubleshooting
- If the browser doesn't open, copy the "Local URL" shown in the terminal (e.g., `http://localhost:8501`) and paste it into your browser.
- If downloads fail, check the logs in the app interface.
