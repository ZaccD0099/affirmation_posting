# Affirmation Video Generator

An automated system that generates and posts daily affirmation videos to Facebook and Instagram. The system uses AI to generate unique affirmations and creates visually appealing videos with background music.

## Features

- AI-powered affirmation generation using GPT-4
- Automated video creation with text overlays and background music
- Direct posting to Facebook and Instagram
- Memory-optimized video processing
- S3 integration for video storage
- Automated scheduling capabilities

## Prerequisites

- Python 3.8+
- FFMPEG
- AWS S3 account
- Facebook Developer account
- Instagram Business account
- OpenAI API key

## Environment Variables

Create a `.env` file with the following variables:

```env
OPENAI_API_KEY=your_openai_api_key
FACEBOOK_PAGE_ID=your_facebook_page_id
FACEBOOK_ACCESS_TOKEN=your_facebook_access_token
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_DEFAULT_REGION=your_aws_region
S3_BUCKET_NAME=your_s3_bucket_name
```

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/affirmation-video-generator.git
cd affirmation-video-generator
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up your environment variables in `.env`

## Usage

Run the script to generate and post a video:
```bash
python generate_affirmation_video.py
```

## Project Structure

- `generate_affirmation_video.py`: Main script for video generation and posting
- `assets/`: Directory containing fonts, background images, and music
- `output/`: Directory for generated videos
- `.env`: Environment variables (not included in repository)
- `requirements.txt`: Python dependencies

## Memory Optimization

The script includes several memory optimization features:
- Efficient video processing with FFMPEG
- Resource cleanup after video generation
- Memory usage monitoring and logging
- Optimized video encoding settings

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 