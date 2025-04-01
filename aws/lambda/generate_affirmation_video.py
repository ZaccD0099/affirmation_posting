import os
import json
import time
import requests
import subprocess
from datetime import datetime
from moviepy.editor import *
from PIL import Image
import openai
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API Keys and Credentials
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
FACEBOOK_ACCESS_TOKEN = os.getenv('FACEBOOK_ACCESS_TOKEN')
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME')
AWS_REGION = os.getenv('AWS_REGION')

# Video Settings
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
FPS = 30
TOTAL_DURATION = 30  # Total video duration in seconds
AFFIRMATION_DURATION = 6  # Duration for each affirmation in seconds
BACKGROUND_MUSIC_VOLUME = 0.3  # Volume level for background music (0.0 to 1.0)

# API URLs
FACEBOOK_API_URL = "https://graph.facebook.com/v18.0"

def generate_affirmations_and_caption():
    """Generate affirmations and caption using OpenAI API."""
    openai.api_key = OPENAI_API_KEY
    
    # First, generate a theme
    theme_prompt = """Generate a single word theme for daily affirmations. The theme should be:
    1. Positive and uplifting
    2. Universal and relatable
    3. Simple and clear
    4. Suitable for personal development
    
    Examples: Growth, Courage, Peace, Joy, Strength, Balance, Wisdom, Love, Hope, Power
    
    Return just the single word theme."""
    
    theme_response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a professional content creator."},
            {"role": "user", "content": theme_prompt}
        ]
    )
    
    theme = theme_response.choices[0].message['content'].strip()
    
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
    
    affirmations_response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a professional affirmation writer."},
            {"role": "user", "content": affirmations_prompt}
        ]
    )
    
    affirmations = json.loads(affirmations_response.choices[0].message['content'])["affirmations"]
    
    # Generate short caption
    caption_prompt = f"""Create a short, engaging Instagram caption for a video with theme "{theme}" containing these affirmations:
    {', '.join(affirmations)}
    
    The caption should:
    1. Be under 100 characters
    2. NOT include any quotation marks
    3. Be uplifting and relatable
    4. Focus on the theme: {theme}
    5. End with these hashtags: #Affirmations #dailyAffirmations #DailyAffirmationJournal"""
    
    caption_response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a professional social media content creator."},
            {"role": "user", "content": caption_prompt}
        ]
    )
    
    caption = caption_response.choices[0].message['content'].strip()
    
    return theme, affirmations, caption

def create_affirmation_clip(affirmation, start_time, duration, is_first=False):
    """Create a clip for a single affirmation with fade in/out effects."""
    # Create text clip with fade in/out
    text_clip = TextClip(
        affirmation,
        fontsize=70,
        color='white',
        font='Arial-Bold',
        size=(VIDEO_WIDTH * 0.8, None),  # Width is 80% of video width
        method='caption',
        align='center'
    )
    
    # Position the text in the center
    text_clip = text_clip.set_position('center')
    
    # Set duration and timing
    text_clip = text_clip.set_duration(duration)
    text_clip = text_clip.set_start(start_time)
    
    # Add fade in/out effects
    fade_duration = 1.0  # Duration of fade in/out in seconds
    
    if is_first:
        # First clip: fade in only
        text_clip = text_clip.fadein(fade_duration)
    else:
        # Other clips: fade in and out
        text_clip = text_clip.fadein(fade_duration).fadeout(fade_duration)
    
    return text_clip

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

def encode_video_for_instagram(input_path):
    """
    Re-encode video to meet Instagram Reels requirements with updated settings.
    """
    output_path = input_path.replace('.mp4', '_instagram.mp4')
    try:
        # FFmpeg command with updated Instagram Reels settings
        cmd = [
            'ffmpeg', '-i', input_path,
            '-vf', 'scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2',
            '-c:v', 'libx264',
            '-preset', 'medium',     # Better quality preset
            '-profile:v', 'main',    # Main profile instead of baseline
            '-level:v', '4.0',       # Higher level for better compatibility
            '-b:v', '4M',            # Higher bitrate for better quality
            '-maxrate', '5M',
            '-bufsize', '5M',
            '-r', '30',
            '-fps_mode', 'cfr',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-ar', '44100',
            '-ac', '2',
            '-pix_fmt', 'yuv420p',
            '-movflags', '+faststart',
            '-y',
            output_path
        ]
        
        print("\nRe-encoding video for Instagram Reels with updated settings:")
        print("- Resolution: 1080x1920 (9:16 aspect ratio)")
        print("- Video codec: H.264 (libx264) main profile")
        print("- Profile/Level: main/4.0")
        print("- Frame rate: 30 fps (constant)")
        print("- Video bitrate: 4 Mbps")
        print("- Audio codec: AAC-LC")
        print("- Audio bitrate: 128 Kbps")
        print("- Audio sample rate: 44.1 kHz")
        print("- Audio channels: Stereo")
        print("- Fast start enabled for streaming")
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"\n❌ Error encoding video: {result.stderr}")
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
        return None

def upload_to_s3(file_path):
    """Upload video to S3 and return the public URL."""
    try:
        # Create S3 client
        s3_client = boto3.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION
        )
        
        # Get the filename from the path
        file_name = os.path.basename(file_path)
        
        # Upload the file with public-read ACL
        print(f"Uploading {file_name} to S3...")
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
        public_url = f"https://{S3_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{file_name}"
        print(f"Successfully uploaded to S3. Public URL: {public_url}")
        
        # Verify the file is accessible
        try:
            response = requests.head(public_url)
            print(f"URL Verification - Status Code: {response.status_code}")
            print(f"URL Verification - Content Type: {response.headers.get('Content-Type')}")
            if response.status_code != 200:
                print(f"Warning: URL is not publicly accessible (Status: {response.status_code})")
        except Exception as e:
            print(f"Warning: Could not verify URL accessibility: {str(e)}")
        
        return public_url
        
    except ClientError as e:
        print(f"Error uploading to S3: {str(e)}")
        return None

def post_to_facebook(video_path, caption, access_token, page_id):
    """Post a video to Facebook"""
    try:
        print("\n=== Starting Facebook Post Process ===")
        
        # Check if video file exists
        if not os.path.exists(video_path):
            print(f"Error: Video file not found at {video_path}")
            return False
        
        # Upload to S3 and get the URL
        s3_url = upload_to_s3(video_path)
        if not s3_url:
            print("Error: Failed to upload video to S3")
            return False
            
        print("\nDebug - Facebook credentials:")
        print(f"Page ID: {page_id}")
        print(f"Access Token exists: {bool(access_token)}")
        
        # Check access token permissions
        print("\nChecking access token permissions...")
        token_response = requests.get(
            f"{FACEBOOK_API_URL}/me",
            params={'access_token': access_token, 'fields': 'id,name,permissions'}
        )
        
        if token_response.status_code != 200:
            print(f"Error checking token: {token_response.text}")
            return False
            
        token_data = token_response.json()
        print("\nToken Debug Info:")
        print(json.dumps(token_data, indent=2))
        
        # Get page access token
        print("\nGetting page access token...")
        page_token_response = requests.get(
            f"{FACEBOOK_API_URL}/{page_id}",
            params={'access_token': access_token, 'fields': 'access_token'}
        )
        
        if page_token_response.status_code != 200:
            print(f"Error getting page token: {page_token_response.text}")
            return False
            
        page_token = page_token_response.json().get('access_token')
        if not page_token:
            print("Error: No page access token in response")
            return False
            
        print("Successfully retrieved page access token")
        
        # Upload video to Facebook
        print("\nUploading video to Facebook...")
        print("\nSending request to Facebook API...")
        
        # Create video upload session
        upload_response = requests.post(
            f"{FACEBOOK_API_URL}/{page_id}/videos",
            params={'access_token': page_token},
            data={
                'file_url': s3_url,
                'description': caption,
                'privacy': {'value': 'PUBLIC'},
                'target_id': page_id
            }
        )
        
        print(f"\nFacebook Response Status: {upload_response.status_code}")
        print(f"Facebook Response Body: {json.dumps(upload_response.json(), indent=2)}")
        
        if upload_response.status_code != 200:
            print(f"\n❌ Error uploading to Facebook: {upload_response.text}")
            return False
            
        post_id = upload_response.json().get('id')
        if not post_id:
            print("\n❌ Error: No post ID in response")
            return False
            
        print(f"\n✅ Successfully created Facebook post!")
        print(f"Post ID: {post_id}")
        return True
        
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

def main():
    try:
        print("Generating theme, affirmations, and caption using OpenAI...")
        theme, affirmations, caption = generate_affirmations_and_caption()
        
        print(f"Generated Theme: {theme}")
        print(f"Generated Affirmations: {affirmations}")
        print(f"\nGenerated Caption:\n{caption}")
        
        print("\nCreating video...")
        final_video = create_video(affirmations)
        
        # Generate output filename with date
        date_str = datetime.now().strftime("%Y-%m-%d")
        output_filename = f"{theme}_{date_str}.mp4"
        output_path = os.path.join("output", output_filename)
        
        print(f"Writing video to {output_path}...")
        final_video.write_videofile(
            output_path,
            fps=FPS,
            codec='libx264',
            audio_codec='aac',
            temp_audiofile="temp-audio.m4a",
            remove_temp=True
        )
        
        print("\nScheduling posts on social media...")
        
        # Post to Facebook
        facebook_page_id = "677046102147244"  # Your Facebook page ID
        facebook_success = post_to_facebook(output_path, caption, FACEBOOK_ACCESS_TOKEN, facebook_page_id)
        
        # Post to Instagram
        instagram_account_id = "17841473640524473"  # Your Instagram account ID
        instagram_success = post_to_instagram(output_path, caption, FACEBOOK_ACCESS_TOKEN, instagram_account_id)
        
        if not facebook_success or not instagram_success:
            print("\nFailed to schedule social media posts")
        else:
            print("\nSuccessfully scheduled all social media posts")
            
        print("\nVideo generation complete!")
        
    except Exception as e:
        print(f"\n❌ Error in main process: {str(e)}")
        raise

if __name__ == "__main__":
    main() 