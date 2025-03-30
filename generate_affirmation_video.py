import os
from datetime import datetime, timedelta
from moviepy.editor import VideoFileClip, AudioFileClip, ImageClip, TextClip, CompositeVideoClip, concatenate_videoclips
from moviepy.video.tools.segmenting import findObjects
import tempfile
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import pickle
from PIL import Image, ImageOps
import json
import openai
import requests
import time
import boto3
from botocore.exceptions import ClientError
import subprocess
from dotenv import load_dotenv
import traceback

# Load environment variables
load_dotenv()

# Constants
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
AFFIRMATION_DURATION = 6  # seconds per affirmation
TOTAL_DURATION = 30  # total video duration
BACKGROUND_MUSIC_VOLUME = 0.3  # 30% volume for background music

# API Keys and Credentials from environment variables
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
SPREADSHEET_ID = os.getenv('GOOGLE_SHEETS_SPREADSHEET_ID')
SHEET_NAME = 'Video Captions'

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

def get_predefined_affirmations():
    """Return a list of predefined affirmations."""
    return [
        "I am capable of achieving great things",
        "I choose to be confident and self-assured",
        "I attract positive energy and opportunities",
        "I am worthy of love and respect",
        "I trust in my journey and growth"
    ]

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

def upload_to_google_drive(file_path):
    """Upload the video to Google Drive."""
    try:
        SCOPES = ['https://www.googleapis.com/auth/drive.file']
        creds = None
        
        # Load saved credentials if they exist
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
        
        # If credentials are invalid or don't exist, let the user authenticate
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
            
            # Save credentials for future use
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)
        
        # Create Drive API service
        service = build('drive', 'v3', credentials=creds)
        
        # Get the filename from the path
        file_name = os.path.basename(file_path)
        
        # Prepare the file metadata
        file_metadata = {
            'name': file_name,
            'parents': ['16j0edDvMlMes_LUWOni8qStK4qEQS8TK']  # Updated folder ID
        }
        
        # Upload the file
        media = MediaFileUpload(file_path, resumable=True)
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        
        print(f"File uploaded successfully. File ID: {file.get('id')}")
        return file.get('id')
        
    except Exception as e:
        print(f"Error uploading to Google Drive: {str(e)}")
        return None

def update_spreadsheet(video_name, caption):
    """Update the Google Sheet with video name and caption."""
    try:
        SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
        creds = None
        
        # Load saved credentials if they exist
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
        
        # If credentials are invalid or don't exist, let the user authenticate
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
            
            # Save credentials for future use
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)
        
        # Create Sheets API service
        service = build('sheets', 'v4', credentials=creds)
        
        # First, verify the spreadsheet exists and is accessible
        try:
            spreadsheet = service.spreadsheets().get(
                spreadsheetId=SPREADSHEET_ID
            ).execute()
            print(f"Successfully connected to spreadsheet: {spreadsheet.get('properties', {}).get('title')}")
        except Exception as e:
            print(f"Error accessing spreadsheet: {str(e)}")
            return False
        
        # Get the next empty row
        range_name = f'{SHEET_NAME}!A:B'
        try:
            result = service.spreadsheets().values().get(
                spreadsheetId=SPREADSHEET_ID,
                range=range_name
            ).execute()
            
            values = result.get('values', [])
            next_row = len(values) + 1
            
            # Prepare the data
            body = {
                'values': [[video_name, caption]]
            }
            
            # Update the sheet
            result = service.spreadsheets().values().update(
                spreadsheetId=SPREADSHEET_ID,
                range=f'{SHEET_NAME}!A{next_row}:B{next_row}',
                valueInputOption='RAW',
                body=body
            ).execute()
            
            print(f"Updated spreadsheet at row {next_row}")
            return True
            
        except Exception as e:
            print(f"Error updating sheet values: {str(e)}")
            return False
        
    except Exception as e:
        print(f"Error updating spreadsheet: {str(e)}")
        return False

def upload_to_imgbb(file_path):
    """Upload video to ImgBB and return the public URL."""
    try:
        with open(file_path, 'rb') as f:
            files = {'image': f}
            response = requests.post(
                'https://api.imgbb.com/1/upload',
                files=files,
                data={'key': IMGBB_API_KEY}
            )
            response.raise_for_status()
            data = response.json()
            if data.get('success'):
                return data['data']['url']
            else:
                print("Error uploading to ImgBB:", data.get('error'))
                return None
    except Exception as e:
        print(f"Error uploading to ImgBB: {str(e)}")
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

def schedule_social_media_post(video_path, caption):
    """Schedule a post on social media platforms"""
    try:
        # Upload to Google Drive
        file_id = upload_to_google_drive(video_path)
        print(f"Video uploaded to Google Drive with ID: {file_id}")
        
        # Update spreadsheet
        try:
            update_spreadsheet(video_path, caption)
        except Exception as e:
            print(f"Error accessing spreadsheet: {str(e)}")
        
        # Upload to S3
        s3_url = upload_to_s3(video_path)
        print(f"Video uploaded to S3: {s3_url}")
        
        # Post to Facebook
        facebook_success = post_to_facebook(video_path, caption)
        
        # Get Instagram account ID
        instagram_account_id = get_instagram_account_id(FACEBOOK_PAGE_ID, FACEBOOK_ACCESS_TOKEN)
        print(f"Debug - Instagram Account ID: {instagram_account_id}")
        
        if instagram_account_id:
            # Post to Instagram
            instagram_success = post_to_instagram(video_path, caption, FACEBOOK_ACCESS_TOKEN, instagram_account_id)
        
        if not facebook_success or not instagram_success:
            print("Failed to schedule social media posts")
        
        return True
        
    except Exception as e:
        print(f"Error scheduling social media post: {str(e)}")
        return False

def main():
    """Main function to generate and post affirmation video."""
    try:
        # Generate affirmations and caption
        theme, affirmations, caption = generate_affirmations_and_caption()
        print(f"Generated Theme: {theme}")
        print("Generated Affirmations:", affirmations)
        print("\nGenerated Caption:")
        print(caption)
        
        # Create video
        print("\nCreating video...")
        video = create_video(affirmations)
        
        # Save video
        output_dir = "output"
        os.makedirs(output_dir, exist_ok=True)
        video_path = os.path.join(output_dir, f"{theme}_{datetime.now().strftime('%Y-%m-%d')}.mp4")
        print(f"Writing video to {video_path}...")
        video.write_videofile(
            video_path,
            fps=30,
            codec='libx264',
            audio_codec='aac',
            temp_audiofile="temp-audio.m4a",
            remove_temp=True
        )
        
        print("\nScheduling posts on social media...")
        
        # Upload to S3 and get URL
        s3_url = upload_to_s3(video_path)
        if not s3_url:
            print("Failed to upload video to S3")
            return
        print(f"Video uploaded to S3: {s3_url}")
        
        # Post to Facebook
        facebook_success = post_to_facebook(video_path, caption)
        
        # Post to Instagram
        instagram_success = post_to_instagram(video_path, caption, FACEBOOK_ACCESS_TOKEN, get_instagram_account_id(FACEBOOK_PAGE_ID, FACEBOOK_ACCESS_TOKEN))
        
        if not facebook_success or not instagram_success:
            print("Failed to schedule social media posts")
        
        # Clean up temporary files
        if os.path.exists("temp_background.jpg"):
            os.remove("temp_background.jpg")
        video.close()
        
        print("Video generation complete!")
        
    except Exception as e:
        print(f"Error in main function: {str(e)}")
        traceback.print_exc()

if __name__ == "__main__":
    main() 