# Daily Affirmation Video Generator

This script automatically generates daily affirmation videos suitable for Instagram Reels and TikTok. It creates 30-second videos with 5 affirmations, background music, and smooth transitions.

## Features

- Generates 5 unique affirmations using OpenAI API
- Creates vertical (1080x1920) videos
- Includes background music and image
- Smooth fade transitions between affirmations
- Automatic upload to Google Drive
- Daily date-stamped output files

## Setup

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

2. Create an `assets` folder in the project directory and add:
   - `background_image_standard.jpg` - Your background image
   - `background_music_ambient.mp3` - Your background music track

3. Set up Google Drive API:
   - Go to the Google Cloud Console
   - Create a new project
   - Enable the Google Drive API
   - Create credentials (OAuth 2.0 Client ID)
   - Download the credentials and save as `credentials.json` in the project directory

4. The first time you run the script, it will prompt you to authenticate with Google Drive.

## Usage

Run the script:
```bash
python generate_affirmation_video.py
```

The script will:
1. Generate 5 affirmations using OpenAI
2. Create a video with the affirmations
3. Save the video to `~/Google Drive/My Drive/Affirmation_Videos/`
4. Upload the video to Google Drive

The output video will be named `affirmation_YYYY-MM-DD.mp4`.

## Requirements

- Python 3.7+
- OpenAI API key
- Google Drive API credentials
- Background image and music files 