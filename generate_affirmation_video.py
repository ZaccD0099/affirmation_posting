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
        
        # Upload the file with public-read ACL
        s3_client.upload_file(
            file_path,
            S3_BUCKET_NAME,
            file_name,
            ExtraArgs={
                'ACL': 'public-read',
                'ContentType': 'video/mp4'
            }
        )
        
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
    """Post a video to Instagram."""
    try:
        print("\nCreating Instagram post...")
        
        # First, upload the video to S3 with specific Instagram settings
        s3_url = upload_to_s3(video_path)
        if not s3_url:
            print("Failed to upload video to S3")
            return False
            
        print(f"Using video URL: {s3_url}")
        
        # Test the S3 URL accessibility
        print("\nTesting S3 URL accessibility...")
        response = requests.head(s3_url)
        print(f"S3 URL Test Results:")
        print(f"Status Code: {response.status_code}")
        print(f"Content Type: {response.headers.get('content-type', 'unknown')}")
        print(f"Content Length: {response.headers.get('content-length', 'None')} bytes")
        
        # Prepare the request data
        data = {
            'access_token': access_token,
            'media_type': 'REELS',
            'video_url': s3_url,
            'caption': caption
        }
        
        print("\nInstagram Request Data:")
        print(json.dumps(data, indent=2))
        
        # Make the API request
        url = f"{FACEBOOK_API_URL}/{instagram_account_id}/media"
        print(f"\nSending request to: {url}")
        
        response = requests.post(url, json=data)
        print(f"\nInstagram Response Status: {response.status_code}")
        print("Instagram Response Headers:", json.dumps(dict(response.headers), indent=2))
        
        if response.status_code != 200:
            print(f"Error creating Instagram media container: {response.text}")
            return False
            
        result = response.json()
        print(f"Instagram Response Body: {json.dumps(result, indent=2)}")
        
        if 'id' not in result:
            print("No media container ID in response")
            return False
            
        media_container_id = result['id']
        print(f"\n✅ Created Instagram media container with ID: {media_container_id}")
        
        # Wait for media to be ready
        print("\nWaiting for media to be ready...")
        max_attempts = 30
        for attempt in range(max_attempts):
            # Check media status
            status_url = f"{FACEBOOK_API_URL}/{media_container_id}"
            status_params = {
                'access_token': access_token,
                'fields': 'status_code,status'
            }
            
            status_response = requests.get(status_url, params=status_params)
            status_data = status_response.json()
            
            print(f"\nStatus Check (Attempt {attempt + 1}/{max_attempts}):")
            print(json.dumps(status_data, indent=2))
            
            if 'status_code' in status_data:
                if status_data['status_code'] == 'FINISHED':
                    print("\n✅ Media is ready for publishing!")
                    break
                elif status_data['status_code'] == 'ERROR':
                    print(f"\n❌ Error processing media: {status_data}")
                    return False
                else:
                    print(f"\nℹ️ Media still processing... Status: {status_data['status_code']}")
                    time.sleep(10)  # Wait 10 seconds before next check
            else:
                print(f"\n⚠️ Unexpected status response: {status_data}")
                time.sleep(10)
                
            if attempt == max_attempts - 1:
                print("\n❌ Timeout waiting for media to be ready")
                return False
        
        # Publish the media container
        print("\nPublishing media container...")
        publish_url = f"{FACEBOOK_API_URL}/{instagram_account_id}/media_publish"
        publish_data = {
            'access_token': access_token,
            'creation_id': media_container_id
        }
        
        publish_response = requests.post(publish_url, json=publish_data)
        print(f"Publish Response Status: {publish_response.status_code}")
        print(f"Publish Response Body: {publish_response.text}")
        
        if publish_response.status_code != 200:
            print("Failed to publish media container")
            return False
            
        print("\n✅ Successfully published to Instagram!")
        return True
        
    except Exception as e:
        print(f"Error posting to Instagram: {str(e)}")
        traceback.print_exc()
        return False

@log_memory_usage
def encode_video_for_instagram(input_path):
    """
    Re-encode video to meet Instagram Reels requirements with updated settings.
    """
    output_path = input_path.replace('.mp4', '_instagram.mp4')
    try:
        # FFmpeg command with more memory-efficient settings
        cmd = [
            'ffmpeg', '-i', input_path,
            '-vf', 'scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2',
            '-c:v', 'libx264',
            '-preset', 'veryfast',     # Faster encoding with less memory usage
            '-profile:v', 'baseline',   # More compatible profile
            '-level:v', '3.1',          # Level 3.1 supports 1080x1920
            '-b:v', '1.5M',             # Lower bitrate
            '-maxrate', '2M',
            '-bufsize', '2M',
            '-r', '30',
            '-fps_mode', 'cfr',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-ar', '44100',
            '-ac', '2',
            '-pix_fmt', 'yuv420p',
            '-movflags', '+faststart',
            '-threads', '4',            # Limit number of threads
            '-y',
            output_path
        ]
        
        print("\nRe-encoding video for Instagram Reels with updated settings:")
        print("- Resolution: 1080x1920 (9:16 aspect ratio)")
        print("- Video codec: H.264 (libx264) baseline profile")
        print("- Profile/Level: baseline/3.1")
        print("- Frame rate: 30 fps (constant)")
        print("- Video bitrate: 1.5 Mbps")
        print("- Audio codec: AAC-LC")
        print("- Audio bitrate: 128 Kbps")
        print("- Audio sample rate: 44.1 kHz")
        print("- Audio channels: Stereo")
        print("- Fast start enabled for streaming")
        print("- Thread count: 4")
        
        # Run FFmpeg with output capture and timeout
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        # Read output in real-time with timeout
        start_time = time.time()
        while True:
            if time.time() - start_time > 300:  # 5-minute timeout
                process.terminate()
                print("\n❌ Error: Video encoding timed out after 5 minutes")
                return None
                
            output = process.stderr.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                print(output.strip())
        
        # Get the return code
        return_code = process.poll()
        
        if return_code != 0:
            print(f"\n❌ Error encoding video (return code: {return_code})")
            return None
            
        print("\n✅ Video re-encoding complete")
        
        # Verify the output file exists and has a reasonable size
        if not os.path.exists(output_path):
            print("\n❌ Error: Output file was not created")
            return None
            
        file_size = os.path.getsize(output_path)
        print(f"\nOutput file size: {file_size / (1024*1024):.2f} MB")
        
        if file_size > 100 * 1024 * 1024:  # 100MB
            print("\n❌ Error: Output file is too large for Instagram (>100MB)")
            return None
            
        return output_path
    except Exception as e:
        print(f"\n❌ Error encoding video: {str(e)}")
        traceback.print_exc()
        return None

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
        
        # Encode video specifically for Instagram
        instagram_video_path = encode_video_for_instagram(video_path)
        if instagram_video_path:
            post_to_instagram(instagram_video_path, caption, FACEBOOK_ACCESS_TOKEN, instagram_account_id)
        else:
            print("Failed to encode video for Instagram")
        
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