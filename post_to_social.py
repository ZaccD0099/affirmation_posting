import os
from dotenv import load_dotenv
import logging
import requests
import boto3
from botocore.exceptions import ClientError
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
FACEBOOK_API_URL = 'https://graph.facebook.com/v18.0'

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
        
        if not page_id or not access_token:
            logger.error("Missing Facebook credentials")
            return False
            
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

def get_instagram_account_id(page_id, access_token):
    """Get Instagram Business Account ID from Facebook Page ID."""
    try:
        url = f"{FACEBOOK_API_URL}/{page_id}"
        params = {
            'access_token': access_token,
            'fields': 'instagram_business_account'
        }
        
        response = requests.get(url, params=params)
        data = response.json()
        
        if 'instagram_business_account' in data:
            return data['instagram_business_account']['id']
        else:
            logger.error("No Instagram Business Account found")
            return None
            
    except Exception as e:
        logger.error(f"Error getting Instagram account ID: {str(e)}")
        return None

def post_to_instagram(video_path, caption):
    """Post video to Instagram."""
    try:
        logger.info("=== Starting Instagram Post Process ===")
        
        # Get Facebook page ID and access token
        page_id = os.getenv('FACEBOOK_PAGE_ID')
        access_token = os.getenv('FACEBOOK_ACCESS_TOKEN')
        
        if not page_id or not access_token:
            logger.error("Facebook Page ID or Access Token not found")
            return False
            
        # Get Instagram account ID
        instagram_account_id = get_instagram_account_id(page_id, access_token)
        if not instagram_account_id:
            logger.error("Failed to get Instagram account ID")
            return False
            
        # Upload video to S3 first
        logger.info("Uploading video to S3...")
        video_url = upload_to_s3(video_path)
        if not video_url:
            return False
            
        logger.info(f"Video URL: {video_url}")
        
        # Create media container
        container_url = f"{FACEBOOK_API_URL}/{instagram_account_id}/media"
        data = {
            'access_token': access_token,
            'media_type': 'REELS',
            'video_url': video_url,
            'caption': caption,
            'share_to_feed': 'true'
        }
        
        response = requests.post(container_url, data=data)
        response_data = response.json()
        
        if 'id' not in response_data:
            logger.error(f"Failed to create Instagram media container: {response_data}")
            return False
            
        # Wait for media to be ready
        creation_id = response_data['id']
        status_url = f"{FACEBOOK_API_URL}/{creation_id}"
        params = {
            'access_token': access_token,
            'fields': 'status_code'
        }
        
        # Check status for up to 5 minutes
        for _ in range(30):  # 30 attempts, 10 seconds each
            status_response = requests.get(status_url, params=params)
            status_data = status_response.json()
            
            if status_data.get('status_code') == 'FINISHED':
                # Publish the media
                publish_url = f"{FACEBOOK_API_URL}/{instagram_account_id}/media_publish"
                publish_data = {
                    'access_token': access_token,
                    'creation_id': creation_id
                }
                
                publish_response = requests.post(publish_url, data=publish_data)
                publish_data = publish_response.json()
                
                if 'id' in publish_data:
                    logger.info(f"Successfully posted to Instagram. Post ID: {publish_data['id']}")
                    return True
                else:
                    logger.error(f"Failed to publish to Instagram: {publish_data}")
                    return False
                    
            time.sleep(10)  # Wait 10 seconds before checking again
            
        logger.error("Media processing timed out")
        return False
        
    except Exception as e:
        logger.error(f"Error posting to Instagram: {str(e)}")
        return False

def post_to_social_media(video_path, caption):
    """Post video to both Facebook and Instagram."""
    try:
        # Load environment variables
        load_dotenv()
        
        # Post to both platforms
        facebook_success = post_to_facebook(video_path, caption)
        instagram_success = post_to_instagram(video_path, caption)
        
        if facebook_success and instagram_success:
            logger.info("Successfully posted to all platforms")
            return True
        else:
            logger.error("Failed to post to one or more platforms")
            return False
            
    except Exception as e:
        logger.error(f"Error in post_to_social_media: {str(e)}")
        return False 