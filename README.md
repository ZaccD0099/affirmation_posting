# Daily Affirmation Video Generator

This project automatically generates and posts daily affirmation videos to Facebook and Instagram using AI-generated content.

## Features

- Generates unique daily affirmations using OpenAI's GPT-4
- Creates beautiful video content with affirmations
- Posts automatically to Facebook and Instagram
- Runs daily via GitHub Actions
- Stores videos in AWS S3

## Setup

1. Clone the repository:
```bash
git clone https://github.com/ZaccD0099/affirmation_posting.git
cd affirmation_posting
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file with your API keys:
```
OPENAI_API_KEY=your_openai_key
FACEBOOK_ACCESS_TOKEN=your_facebook_token
AWS_ACCESS_KEY_ID=your_aws_key
AWS_SECRET_ACCESS_KEY=your_aws_secret
S3_BUCKET_NAME=your_bucket_name
AWS_REGION=your_aws_region
```

4. Add your assets:
- Place your background image as `assets/Iphone_Affirmation_Background.jpg`
- Place your background music as `assets/background_music_ambient.mp3`

## GitHub Actions Setup

1. Go to your repository's Settings > Secrets and Variables > Actions
2. Add the following secrets:
   - `OPENAI_API_KEY`
   - `FACEBOOK_ACCESS_TOKEN`
   - `AWS_ACCESS_KEY_ID`
   - `AWS_SECRET_ACCESS_KEY`
   - `S3_BUCKET_NAME`
   - `AWS_REGION`

The workflow will run daily at 9:00 AM UTC (4:00 AM EST) and can also be triggered manually.

## Local Development

To run the script locally:
```bash
python generate_affirmation_video.py
```

## Project Structure

- `generate_affirmation_video.py`: Main script for video generation and posting
- `assets/`: Directory containing background image and music
- `output/`: Directory where generated videos are saved
- `.github/workflows/`: GitHub Actions workflow configuration
- `requirements.txt`: Python dependencies

## License

MIT License 