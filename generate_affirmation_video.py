import os
import sys
import json
import time
import random
import subprocess
import traceback
import requests
import psutil
from datetime import datetime, timedelta
from moviepy.editor import VideoFileClip, AudioFileClip, ImageClip, TextClip, CompositeVideoClip, concatenate_videoclips
from moviepy.video.tools.segmenting import findObjects
import tempfile
from PIL import Image, ImageOps, ImageDraw, ImageFont
import boto3
from botocore.exceptions import ClientError
import logging
from dotenv import load_dotenv
from functools import wraps
from openai import OpenAI

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def log_memory_usage(func):
    """Decorator to log memory usage before and after function execution"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        process = psutil.Process()
        before_mem = process.memory_info().rss / 1024 / 1024  # Convert to MB
        logger.info(f"Memory usage before {func.__name__}: {before_mem:.2f} MB")
        
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        
        after_mem = process.memory_info().rss / 1024 / 1024  # Convert to MB
        duration = end_time - start_time
        
        logger.info(f"Memory usage after {func.__name__}: {after_mem:.2f} MB")
        logger.info(f"Memory difference: {after_mem - before_mem:.2f} MB")
        logger.info(f"Duration: {duration:.2f} seconds")
        
        return result
    return wrapper

def get_memory_usage():
    """Get current memory usage in MB"""
    process = psutil.Process()
    return process.memory_info().rss / 1024 / 1024

def log_memory_peak():
    """Log peak memory usage"""
    process = psutil.Process()
    peak_mem = process.memory_info().rss / 1024 / 1024
    logger.info(f"Peak memory usage: {peak_mem:.2f} MB")

# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Constants
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
AFFIRMATION_DURATION = 6  # seconds per affirmation
TOTAL_DURATION = 30  # total video duration
BACKGROUND_MUSIC_VOLUME = 0.3  # 30% volume for background music

# API Keys and Credentials from environment variables
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Facebook/Instagram API Configuration
FACEBOOK_API_URL = 'https://graph.facebook.com/v18.0'
FACEBOOK_PAGE_ID = os.getenv('FACEBOOK_PAGE_ID')
FACEBOOK_ACCESS_TOKEN = os.getenv('FACEBOOK_ACCESS_TOKEN')

# AWS S3 Configuration
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_REGION = os.getenv('AWS_DEFAULT_REGION')
S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME')

def generate_affirmations_and_caption():
    """Generate affirmations and caption using OpenAI API."""
    # First, generate a theme
    theme_prompt = """Generate a single word theme for daily affirmations. The theme should be:
    1. Positive and uplifting
    2. Universal and relatable
    3. Simple and clear
    4. Suitable for personal development
    
    Examples: Growth, Courage, Peace, Joy, Strength, Balance, Wisdom, Love, Hope, Power
    
    Return just the single word theme."""
    
    theme_response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a professional content creator."},
            {"role": "user", "content": theme_prompt}
        ]
    )
    
    theme = theme_response.choices[0].message.content.strip()
    
    # Generate affirmations based on theme
    affirmations_prompt = f"""Generate 5 unique, powerful affirmations based on the theme "{theme}" that are:
    1. Short and concise (3-12 words each)
    2. Positive and uplifting
    3. Personal and in first person
    4. Present tense
    5. Easy to read quickly in a video
    6. Avoid assumptions about health, wealth, or relationships
    
    Examples of good length:
    - "I am strong and capable"
    - "I choose happiness today"
    - "I trust my inner wisdom"
    - "I attract abundance and joy"
    - "I embrace my unique journey"
    
    Format your response as a JSON array of strings, like this:
    {{"affirmations": ["affirmation1", "affirmation2", "affirmation3", "affirmation4", "affirmation5"]}}"""
    
    affirmations_response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a professional affirmation writer."},
            {"role": "user", "content": affirmations_prompt}
        ]
    )
    
    affirmations = json.loads(affirmations_response.choices[0].message.content)["affirmations"]
    
    # Generate short caption
    caption_prompt = f"""Create a short, engaging Instagram caption for a video with theme "{theme}" containing these affirmations:
    {', '.join(affirmations)}
    
    The caption should:
    1. Be under 100 characters
    2. NOT include any quotation marks
    3. Be uplifting and relatable
    4. Focus on the theme: {theme}
    5. End with these hashtags: #Affirmations #dailyAffirmations #DailyAffirmationJournal"""
    
    caption_response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a professional social media content creator."},
            {"role": "user", "content": caption_prompt}
        ]
    )
    
    caption = caption_response.choices[0].message.content.strip()
    
    return theme, affirmations, caption

def get_predefined_affirmations():
    """Return a list of predefined affirmations."""
    return [
        "I am capable of achieving great things",
        "I choose to be confident and self-assured",
        "I attract positive energy and opportunities",
        "I am worthy of love and respect",
        "I trust in my journey and growth"
    ]

@log_memory_usage
def create_affirmation_clip(text, start_time, duration, is_first=False):
    """Create a video clip for a single affirmation with fade in/out effects."""
    # Create text clip with fade in/out
    text_clip = TextClip(
        text,
        fontsize=75,  # Increased from 60 to 75
        color='black',
        font='assets/fonts/Playfair_Display/PlayfairDisplay-VariableFont_wght.ttf',
        size=(VIDEO_WIDTH-100, None),
        method='caption',
        align='center',
        stroke_color='black',  # Adding a slight stroke for grainy/bold effect
        stroke_width=1.5  # Increased stroke width for more boldness
    )
    
    # Position the text in the center
    text_clip = text_clip.set_position('center')
    
    # Add fade in/out effects
    text_clip = text_clip.set_start(start_time)
    text_clip = text_clip.set_duration(duration)
    
    # Only add fade effects if it's not the first affirmation
    if not is_first:
        text_clip = text_clip.crossfadein(1.0)
    text_clip = text_clip.crossfadeout(1.0)
    
    return text_clip

@log_memory_usage
def create_video(affirmations):
    """Create the final video with all affirmations and background music."""
    # Load background image (expecting a JPG or PNG file)
    background_path = "assets/Iphone_Affirmation_Background.jpg"  # Updated filename
    if not os.path.exists(background_path):
        raise FileNotFoundError(f"Background image not found at {background_path}")
    
    # Load and resize background image using PIL
    with Image.open(background_path) as img:
        img = img.resize((VIDEO_WIDTH, VIDEO_HEIGHT), Image.Resampling.LANCZOS)
        img.save("temp_background.jpg")
    
    # Load background image
    background = ImageClip("temp_background.jpg")
    background = background.set_duration(TOTAL_DURATION)
    
    # Load background music
    background_music = AudioFileClip("assets/background_music_ambient.mp3")
    background_music = background_music.set_duration(TOTAL_DURATION)
    background_music = background_music.volumex(BACKGROUND_MUSIC_VOLUME)
    
    # Create clips for each affirmation
    affirmation_clips = []
    for i, affirmation in enumerate(affirmations):
        start_time = i * AFFIRMATION_DURATION
        clip = create_affirmation_clip(affirmation, start_time, AFFIRMATION_DURATION, is_first=(i == 0))
        affirmation_clips.append(clip)
    
    # Combine all clips
    final_video = CompositeVideoClip(
        [background] + affirmation_clips,
        size=(VIDEO_WIDTH, VIDEO_HEIGHT)
    )
    
    # Set audio
    final_video = final_video.set_audio(background_music)
    
    # Verify video meets Instagram requirements
    if final_video.duration < 3:
        print("Warning: Video duration is less than 3 seconds. Instagram requires at least 3 seconds.")
        # Extend the video to meet minimum duration
        final_video = final_video.set_duration(3)
    
    if final_video.audio is None:
        print("Warning: Video has no audio. Adding silent audio track.")
        # Add silent audio track
        silent_audio = AudioClip(lambda t: 0, duration=final_video.duration)
        final_video = final_video.set_audio(silent_audio)
    
    # Verify aspect ratio
    if final_video.w != 1080 or final_video.h != 1920:
        print("Warning: Video aspect ratio is not 9:16 (1080x1920). Resizing...")
        final_video = final_video.resize((1080, 1920))
    
    return final_video

def upload_to_s3(file_path):
    """Upload a file to AWS S3."""
    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION
        )
        
        # Get the filename from the path
        file_name = os.path.basename(file_path)
        
        # Upload the file
        s3_client.upload_file(file_path, S3_BUCKET_NAME, file_name)
        
        # Generate the public URL
        url = f"https://{S3_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{file_name}"
        
        # Verify the URL is accessible
        response = requests.head(url)
        if response.status_code == 200:
            print(f"Successfully uploaded to S3. Public URL: {url}")
            print(f"URL Verification - Status Code: {response.status_code}")
            print(f"URL Verification - Content Type: {response.headers.get('content-type', 'unknown')}")
            return url
        else:
            print(f"Warning: URL verification failed with status code {response.status_code}")
            return url
    except Exception as e:
        print(f"Error uploading to S3: {str(e)}")
        raise

def get_instagram_account_id(page_id, access_token):
    """Get the Instagram Business Account ID associated with the Facebook Page."""
    try:
        response = requests.get(
            f"{FACEBOOK_API_URL}/{page_id}",
            params={
                'access_token': access_token,
                'fields': 'instagram_business_account'
            }
        )
        response.raise_for_status()
        data = response.json()
        
        if 'instagram_business_account' in data:
            return data['instagram_business_account']['id']
        else:
            print("No Instagram Business Account found for this Facebook Page")
            return None
            
    except Exception as e:
        print(f"Error getting Instagram Account ID: {str(e)}")
        return None

def post_to_facebook(video_path, caption):
    """Post a video to Facebook"""
    try:
        print("\n=== Starting Facebook Post Process ===")
        
        # Check token permissions
        print("\nChecking access token permissions...")
        token_response = requests.get(
            f"{FACEBOOK_API_URL}/debug_token",
            params={
                'input_token': FACEBOOK_ACCESS_TOKEN,
                'access_token': FACEBOOK_ACCESS_TOKEN
            }
        )
        
        print("\nToken Debug Info:")
        print(json.dumps(token_response.json(), indent=2))
        
        if not token_response.json().get('data', {}).get('is_valid'):
            print("Error: Token is not valid")
            return False
            
        # Get page access token
        print("\nGetting page access token...")
        page_token_response = requests.get(
            f"{FACEBOOK_API_URL}/{FACEBOOK_PAGE_ID}",
            params={
                'fields': 'access_token',
                'access_token': FACEBOOK_ACCESS_TOKEN
            }
        )
        
        if page_token_response.status_code != 200:
            print(f"Error getting page access token: {page_token_response.text}")
            return False
            
        page_token_data = page_token_response.json()
        if 'access_token' not in page_token_data:
            print("Error: No page access token in response")
            return False
            
        page_access_token = page_token_data['access_token']
        print("Successfully retrieved page access token")
        
        print("\nUploading video to Facebook...")
        
        # Upload video to Facebook
        with open(video_path, 'rb') as video_file:
            files = {
                'source': (os.path.basename(video_path), video_file, 'video/mp4')
            }
            data = {
                'access_token': page_access_token,  # Use page access token
                'description': caption,
                'published': 'true'
            }
            
            print("\nSending request to Facebook API...")
            fb_response = requests.post(
                f"{FACEBOOK_API_URL}/{FACEBOOK_PAGE_ID}/videos",
                files=files,
                data=data
            )
            
            print("\nFacebook Response Status:", fb_response.status_code)
            print("Facebook Response Body:", json.dumps(fb_response.json(), indent=2))
            
            if fb_response.status_code != 200:
                print(f"\n❌ Error: Facebook API returned status code {fb_response.status_code}")
                return False
            
            response_data = fb_response.json()
            if 'id' in response_data:
                print("\n✅ Successfully created Facebook post!")
                print(f"Post ID: {response_data['id']}")
                return True
            else:
                print("\n❌ Error: No post ID in response")
                return False
                
    except Exception as e:
        print(f"\n❌ Error posting to Facebook: {str(e)}")
        return False

def post_to_instagram(video_path, caption, access_token, instagram_account_id):
    """Post a video to Instagram"""
    try:
        print("\n=== Starting Instagram Post Process ===")
        
        # Check if video file exists
        if not os.path.exists(video_path):
            print(f"Error: Video file not found at {video_path}")
            return False
        
        # Upload to S3 and get the URL
        instagram_s3_url = upload_to_s3(video_path)
        if not instagram_s3_url:
            print("Error: Failed to upload video to S3")
            return False
            
        print("\nCreating Instagram post...")
        print(f"Using video URL: {instagram_s3_url}")
        
        # Test S3 URL accessibility
        try:
            response = requests.head(instagram_s3_url)
            print(f"\nS3 URL Test Results:")
            print(f"Status Code: {response.status_code}")
            print(f"Content Type: {response.headers.get('Content-Type')}")
            print(f"Content Length: {response.headers.get('Content-Length')} bytes")
        except Exception as e:
            print(f"Warning: Could not verify S3 URL: {str(e)}")
        
        # Create media container with simplified payload
        data = {
            'access_token': access_token,
            'media_type': 'REELS',
            'video_url': instagram_s3_url,
            'caption': caption
        }
        
        print("\nInstagram Request Data:")
        print(json.dumps(data, indent=2))
        
        container_response = requests.post(
            f"{FACEBOOK_API_URL}/{instagram_account_id}/media",
            data=data
        )
        
        print("\nInstagram Response Status:", container_response.status_code)
        print("Instagram Response Headers:", json.dumps(dict(container_response.headers), indent=2))
        print("Instagram Response Body:", json.dumps(container_response.json(), indent=2))
        
        if container_response.status_code != 200:
            print(f"\n❌ Error creating media container: {container_response.text}")
            return False
            
        container_data = container_response.json()
        if 'id' not in container_data:
            print("\n❌ Error: No creation ID in response")
            return False
            
        creation_id = container_data['id']
        print(f"\n✅ Created Instagram media container with ID: {creation_id}")
        
        # Wait for video processing with extended timeout
        print("\nWaiting for Instagram to process the video...")
        max_attempts = 20  # Increased from 12 to 20
        for attempt in range(max_attempts):
            status_response = requests.get(
                f"{FACEBOOK_API_URL}/{creation_id}",
                params={'access_token': access_token, 'fields': 'status_code,status'}
            )
            
            if status_response.status_code != 200:
                print(f"\n❌ Error checking status: {status_response.text}")
                return False
                
            status_data = status_response.json()
            print(f"\nStatus Check Response (attempt {attempt + 1}):")
            print("Status Code:", status_response.status_code)
            print("Response Body:", json.dumps(status_data, indent=2))
            
            if status_data.get('status_code') == 'FINISHED':
                print("\n✅ Video processing complete!")
                break
            elif status_data.get('status_code') == 'ERROR':
                print(f"\n❌ Error processing video: {status_data}")
                return False
            else:
                print(f"\nℹ️ Video still processing... (attempt {attempt + 1}/{max_attempts})")
                print("Status:", status_data.get('status', 'Unknown'))
                time.sleep(8)  # Increased from 5 to 8 seconds
        
        # Publish the container
        publish_data = {
            'access_token': access_token,
            'creation_id': creation_id
        }
        
        print("\nPublishing to Instagram...")
        publish_response = requests.post(
            f"{FACEBOOK_API_URL}/{instagram_account_id}/media_publish",
            data=publish_data
        )
        
        print("\nPublish Response Status:", publish_response.status_code)
        print("Publish Response Body:", json.dumps(publish_response.json(), indent=2))
        
        if publish_response.status_code != 200:
            print(f"\n❌ Error publishing to Instagram: {publish_response.text}")
            return False
            
        publish_data = publish_response.json()
        if 'id' in publish_data:
            print("\n✅ Successfully posted to Instagram!")
            print(f"Post ID: {publish_data['id']}")
            return True
        else:
            print("\n❌ Error: No post ID in publish response")
            return False
        
    except Exception as e:
        print(f"\n❌ Error posting to Instagram: {str(e)}")
        return False

def schedule_social_media_post(video_path, caption):
    """Schedule posts on social media platforms."""
    try:
        # Upload video to S3
        print("\nScheduling posts on social media...")
        video_url = upload_to_s3(video_path)
        print(f"Video uploaded to S3: {video_url}")
        
        # Post to Facebook
        print("\n=== Starting Facebook Post Process ===")
        post_to_facebook(video_path, caption)
        
        # Post to Instagram
        print("\n=== Starting Instagram Post Process ===")
        instagram_account_id = get_instagram_account_id(FACEBOOK_PAGE_ID, FACEBOOK_ACCESS_TOKEN)
        post_to_instagram(video_path, caption, FACEBOOK_ACCESS_TOKEN, instagram_account_id)
        
    except Exception as e:
        print(f"Error in schedule_social_media_post: {str(e)}")
        traceback.print_exc()
        raise

def main():
    """Main function to generate and post affirmation video."""
    try:
        logger.info("Starting video generation process")
        initial_memory = get_memory_usage()
        logger.info(f"Initial memory usage: {initial_memory:.2f} MB")
        
        # Generate affirmations and caption
        theme, affirmations, caption = generate_affirmations_and_caption()
        logger.info(f"Generated Theme: {theme}")
        logger.info("Generated Affirmations: %s", affirmations)
        logger.info("\nGenerated Caption:\n%s", caption)
        
        # Create video
        logger.info("\nCreating video...")
        video = create_video(affirmations)
        
        # Save video
        output_dir = "output"
        os.makedirs(output_dir, exist_ok=True)
        video_path = os.path.join(output_dir, f"{theme}_{datetime.now().strftime('%Y-%m-%d')}.mp4")
        logger.info(f"Writing video to {video_path}...")
        
        # Monitor memory during video writing
        before_write = get_memory_usage()
        logger.info(f"Memory before video writing: {before_write:.2f} MB")
        
        video.write_videofile(
            video_path,
            fps=30,
            codec='libx264',
            audio_codec='aac',
            temp_audiofile="temp-audio.m4a",
            remove_temp=True,
            preset='ultrafast',  # Faster encoding, less memory usage
            threads=2,  # Limit thread usage
            bitrate='2000k',  # Lower bitrate for smaller file size
            ffmpeg_params=[
                '-movflags', '+faststart'  # Enable fast start for streaming
            ]
        )
        
        after_write = get_memory_usage()
        logger.info(f"Memory after video writing: {after_write:.2f} MB")
        logger.info(f"Memory difference during writing: {after_write - before_write:.2f} MB")
        
        logger.info("\nScheduling posts on social media...")
        
        # Post to social media
        schedule_social_media_post(video_path, caption)
        
        # Clean up temporary files
        if os.path.exists("temp_background.jpg"):
            os.remove("temp_background.jpg")
        video.close()
        
        # Log final memory usage
        final_memory = get_memory_usage()
        logger.info(f"Final memory usage: {final_memory:.2f} MB")
        logger.info(f"Total memory increase: {final_memory - initial_memory:.2f} MB")
        log_memory_peak()
        
        logger.info("Video generation complete!")
        
    except Exception as e:
        logger.error(f"Error in main function: {str(e)}")
        traceback.print_exc()
        log_memory_peak()  # Log peak memory even if there's an error

if __name__ == "__main__":
    main() 