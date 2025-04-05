import os
from dotenv import load_dotenv
import logging
import time
import json
import requests
import boto3
from botocore.exceptions import ClientError
from openai import OpenAI
from generate_overlay_affirmation_video import create_video, get_predefined_affirmations

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
FACEBOOK_API_URL = 'https://graph.facebook.com/v18.0'

def format_affirmations_for_caption(affirmations):
    """Format affirmations as a bulleted list for the caption."""
    return "\n".join(f"• {affirmation}" for affirmation in affirmations)

def generate_ai_caption(affirmations):
    """Use OpenAI to generate a contextual caption based on the affirmations."""
    try:
        client = OpenAI()
        affirmations_text = "\n".join(affirmations)
        
        prompt = f"""Given these affirmations:

{affirmations_text}

Write a single engaging sentence (max 150 characters) for an Instagram caption that captures the theme and emotion of these affirmations.
The tone should be uplifting, inspiring, and personal. Do not include hashtags or emojis in your response."""

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a social media expert who writes engaging, personal captions."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=100,
            temperature=0.7
        )
        
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Error generating AI caption: {str(e)}")
        # Fallback caption if AI generation fails
        return "Start your day with these powerful affirmations to uplift your spirit. 🌟"

def get_caption(affirmations):
    """Generate the complete caption with AI-generated text, affirmations, and hashtags."""
    # Get AI-generated caption
    ai_caption = generate_ai_caption(affirmations)
    
    # Build full caption
    caption = f"{ai_caption}\n\n"
    caption += format_affirmations_for_caption(affirmations)
    caption += "\n\n"
    caption += "#selfcare #selfcaretips #selfcarequotes #mentalhealth #selfcarejourney #selflove "
    caption += "#glowup #glowuptips #selfcareroutine #selfdevelopment #growth #mindset #dailyquotes "
    caption += "#dailymotivationalquotes #healthylifestyle #selflove #selflovequotes #mentalhealth2024 "
    caption += "#glowup #glowuptips #innerhealing #healingquotes #positivemindset #affirmations "
    caption += "#affirmationjournal #selfloveclub #mentalwellness #wellness #dailymantra #manifestation"
    return caption

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
            logger.error("No Instagram Business Account found for this Facebook Page")
            return None
            
    except Exception as e:
        logger.error(f"Error getting Instagram Account ID: {str(e)}")
        return None

def upload_to_s3(video_path):
    """Upload video to S3 and return the public URL."""
    try:
        bucket_name = os.getenv('S3_BUCKET_NAME')
        s3_client = boto3.client(
            's3',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_DEFAULT_REGION')
        )
        
        # Upload the file
        file_name = os.path.basename(video_path)
        s3_client.upload_file(
            video_path, 
            bucket_name, 
            file_name,
            ExtraArgs={'ACL': 'public-read', 'ContentType': 'video/mp4'}
        )
        
        # Generate the URL
        url = f"https://{bucket_name}.s3.amazonaws.com/{file_name}"
        logger.info(f"Video uploaded to S3: {url}")
        return url
        
    except Exception as e:
        logger.error(f"Error uploading to S3: {str(e)}")
        return None

def post_to_facebook(video_path, caption):
    """Post video to Facebook."""
    try:
        logger.info("=== Starting Facebook Post Process ===")
        
        # Initialize Facebook API
        access_token = os.getenv('FACEBOOK_ACCESS_TOKEN')
        page_id = os.getenv('FACEBOOK_PAGE_ID')
        
        # Get page access token
        logger.info("Getting page access token...")
        page_token_response = requests.get(
            f"{FACEBOOK_API_URL}/{page_id}",
            params={
                'fields': 'access_token',
                'access_token': access_token
            }
        )
        
        if page_token_response.status_code != 200:
            logger.error(f"Error getting page access token: {page_token_response.text}")
            return False
            
        page_token = page_token_response.json().get('access_token')
        if not page_token:
            logger.error("No page access token in response")
            return False
            
        logger.info("Successfully retrieved page access token")
        
        # Upload video to Facebook
        logger.info("Uploading video to Facebook...")
        with open(video_path, 'rb') as video_file:
            files = {
                'source': (os.path.basename(video_path), video_file, 'video/mp4')
            }
            data = {
                'access_token': page_token,
                'description': caption,
                'published': 'true'
            }
            
            fb_response = requests.post(
                f"{FACEBOOK_API_URL}/{page_id}/videos",
                files=files,
                data=data
            )
            
            if fb_response.status_code != 200:
                logger.error(f"Error: Facebook API returned status code {fb_response.status_code}")
                return False
            
            response_data = fb_response.json()
            if 'id' in response_data:
                logger.info(f"Successfully created Facebook post! Post ID: {response_data['id']}")
                return True
            else:
                logger.error("No post ID in response")
                return False
                
    except Exception as e:
        logger.error(f"Error posting to Facebook: {str(e)}")
        return False

def post_to_instagram(video_path, caption):
    """Post video to Instagram."""
    try:
        logger.info("=== Starting Instagram Post Process ===")
        
        access_token = os.getenv('FACEBOOK_ACCESS_TOKEN')
        page_id = os.getenv('FACEBOOK_PAGE_ID')
        
        # Get Instagram account ID
        instagram_account_id = get_instagram_account_id(page_id, access_token)
        if not instagram_account_id:
            logger.error("Could not get Instagram account ID")
            return False
            
        # Upload video to S3 first
        logger.info("Uploading video to S3...")
        video_url = upload_to_s3(video_path)
        if not video_url:
            logger.error("Failed to upload video to S3")
            return False
            
        logger.info(f"Video URL: {video_url}")
        
        # Create media container
        data = {
            'access_token': access_token,
            'media_type': 'REELS',
            'video_url': video_url,
            'caption': caption,
            'share_to_feed': 'true'
        }
        
        container_response = requests.post(
            f"{FACEBOOK_API_URL}/{instagram_account_id}/media",
            data=data
        )
        
        if container_response.status_code != 200:
            logger.error(f"Error creating media container: {container_response.text}")
            return False
            
        container_data = container_response.json()
        if 'id' not in container_data:
            logger.error("No creation ID in response")
            return False
            
        creation_id = container_data['id']
        logger.info(f"Created Instagram media container with ID: {creation_id}")
        
        # Wait for video processing
        logger.info("Waiting for Instagram to process the video...")
        max_attempts = 30
        for attempt in range(max_attempts):
            status_response = requests.get(
                f"{FACEBOOK_API_URL}/{creation_id}",
                params={
                    'access_token': access_token,
                    'fields': 'status_code,status'
                }
            )
            
            status_data = status_response.json()
            logger.info(f"Status check attempt {attempt + 1}: {status_data}")
            
            if status_data.get('status_code') == 'FINISHED':
                logger.info("Video processing complete!")
                break
            elif status_data.get('status_code') == 'ERROR':
                logger.error(f"Error processing video: {status_data}")
                return False
            else:
                logger.info(f"Video still processing... (attempt {attempt + 1}/{max_attempts})")
                time.sleep(10)
        
        # Publish the container
        publish_data = {
            'access_token': access_token,
            'creation_id': creation_id
        }
        
        logger.info("Publishing to Instagram...")
        publish_response = requests.post(
            f"{FACEBOOK_API_URL}/{instagram_account_id}/media_publish",
            data=publish_data
        )
        
        if publish_response.status_code != 200:
            logger.error(f"Error publishing to Instagram: {publish_response.text}")
            return False
            
        publish_data = publish_response.json()
        if 'id' in publish_data:
            logger.info(f"Successfully posted to Instagram! Post ID: {publish_data['id']}")
            return True
        else:
            logger.error("No post ID in publish response")
            return False
        
    except Exception as e:
        logger.error(f"Error posting to Instagram: {str(e)}")
        return False

def main():
    try:
        # Load environment variables
        load_dotenv()
        
        # Get affirmations and create video
        affirmations = get_predefined_affirmations()
        video_path = create_video(affirmations)
        
        # Generate caption
        caption = get_caption(affirmations)
        
        # Post to social media
        facebook_success = post_to_facebook(video_path, caption)
        instagram_success = post_to_instagram(video_path, caption)
        
        if facebook_success and instagram_success:
            logger.info("Successfully posted to all platforms")
        else:
            logger.error("Failed to post to one or more platforms")
        
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        raise

if __name__ == "__main__":
    main() 