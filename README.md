# Quordle Video Automation

An automated Quordle solver that generates daily gameplay videos and uploads them to YouTube.

## Features
- **Playwright-Powered**: Uses Playwright for fast, reliable browser automation.
- **Strategic Solver**: Uses mathematical likelihoods to solve Quordle puzzles with high accuracy.
- **Video Generation**: Automatically records gameplay and adds random background music.
- **YouTube Integration**: Seamlessly uploads the final video to YouTube using OAuth2.
- **GitHub Actions**: Fully automated daily runs via GitHub Actions.

## Setup

### 1. Requirements
- Python 3.11+
- Playwright
- FFmpeg (for video/audio processing)

```powershell
pip install -r requirements.txt
playwright install chromium
playwright install-deps
```

### 2. YouTube Authentication
To enable automated uploads, you need to provide a YouTube OAuth token.

1. Place your `client-secret.json` (from Google Cloud Console) in the root folder.
2. Run the token generator:
   ```powershell
   python generate_youtube_token.py
   ```
3. Copy the contents of the generated `youtube_token.json` file.
4. Add it as a GitHub Secret named `YOUTUBE_CLIENT_SECRET` in your repository.

## Project Structure
- `solver.py`: The main automation script.
- `youtube_upload.py`: Module for handling YouTube API interactions.
- `generate_youtube_token.py`: Utility to generate credentials for CI/CD.
- `wordListsMethods.py`: Logic for word selection and strategy.
- `.github/workflows/`: GitHub Actions configuration for daily runs.

## License
MIT License - Created for YouTube Automation.
