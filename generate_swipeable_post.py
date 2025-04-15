import os
from dotenv import load_dotenv
from openai import OpenAI
import json
import time
import psutil
import logging
from PIL import Image, ImageDraw, ImageFont
import random
import subprocess
import requests
import boto3
from botocore.exceptions import NoCredentialsError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Constants
IMAGE_WIDTH = 1080
IMAGE_HEIGHT = 1350  # Changed from 1920 to 1350 for 4:5 aspect ratio
FACEBOOK_PAGE_ID = os.getenv('FACEBOOK_PAGE_ID')
FACEBOOK_ACCESS_TOKEN = os.getenv('FACEBOOK_ACCESS_TOKEN')

def get_random_theme():
    """Return a randomly selected theme from the most popular affirmation themes."""
    themes = [
        "Self-Love",      # Focus on accepting and loving oneself
        "Abundance",      # Focus on attracting prosperity and success
        "Growth",         # Focus on personal development and learning
        "Confidence",     # Focus on self-assurance and inner strength
        "Peace",          # Focus on inner calm and tranquility
        "Gratitude",      # Focus on appreciation and thankfulness
        "Resilience",     # Focus on overcoming challenges
        "Joy"            # Focus on happiness and positivity
    ]
    return random.choice(themes)

def generate_themed_affirmations(theme):
    """Generate 6 affirmations based on the selected theme using OpenAI."""
    try:
        client = OpenAI()
        
        prompt = f"""Generate 6 affirmations about {theme}. Each affirmation must:
1. Be a maximum of 30 characters (including spaces)
2. Start with "I" and be in present tense
3. Be personal and positive
4. Be easy to read quickly
5. Not use the word "{theme}" directly

Example affirmations for different themes:
- For "Confidence": "I trust my inner wisdom" (22 chars)
- For "Abundance": "I attract prosperity daily" (24 chars)
- For "Self-Love": "I honor my worth always" (23 chars)

Respond with ONLY a valid JSON object containing an array of exactly 6 affirmations, like this:
{{
    "affirmations": [
        "I trust my inner wisdom",
        "I attract prosperity daily",
        "I honor my worth always",
        "I am strong and capable",
        "I create my own success",
        "I embrace my true power"
    ]
}}"""
        
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an expert at creating short, powerful affirmations. Respond with ONLY valid JSON."},
                {"role": "user", "content": prompt}
            ]
        )
        
        # Parse the response and validate character limits
        affirmations = json.loads(response.choices[0].message.content)["affirmations"]
        
        # Validate each affirmation
        for aff in affirmations:
            if len(aff) > 30:
                logger.warning(f"Affirmation too long ({len(aff)} chars): {aff}")
                # Truncate to 30 characters if needed
                affirmations[affirmations.index(aff)] = aff[:30].strip()
        
        return affirmations
        
    except Exception as e:
        logger.error(f"Error generating affirmations: {str(e)}")
        # Fallback affirmations
        return [
            "I am worthy of love",
            "I trust my journey",
            "I embrace my power",
            "I choose happiness",
            "I am enough",
            "I create my joy"
        ]

def create_affirmation_image(affirmations, background_path, output_path):
    """Create an image with affirmations overlaid on the background."""
    try:
        # Load background image
        background = Image.open(background_path)
        background = background.resize((IMAGE_WIDTH, IMAGE_HEIGHT), Image.Resampling.LANCZOS)
        
        # Create a drawing context
        draw = ImageDraw.Draw(background)
        
        # Load font
        font = ImageFont.truetype('assets/fonts/Playfair_Display/static/PlayfairDisplay-Regular.ttf', 65)
        
        # Calculate vertical spacing
        total_height = IMAGE_HEIGHT * 0.8  # Use 80% of image height for text
        spacing = total_height / (len(affirmations) + 1)
        
        # Calculate starting Y position to center the text block
        start_y = (IMAGE_HEIGHT - total_height) / 2
        
        # Draw each affirmation
        for i, text in enumerate(affirmations):
            # Get text size
            text_bbox = draw.textbbox((0, 0), text, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
            
            # Calculate position
            x = (IMAGE_WIDTH - text_width) / 2
            y = start_y + (spacing * (i + 1)) - (text_height / 2)
            
            # Draw text in black
            draw.text((x, y), text, font=font, fill='black')
        
        # Save the image as JPEG
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        output_path = output_path.replace('.png', '.jpg')
        background.convert('RGB').save(output_path, 'JPEG', quality=95)
        logger.info(f"Image successfully created at {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"Error creating image: {str(e)}")
        raise

def get_caption(affirmations, theme):
    """Generate a caption for social media posts."""
    try:
        client = OpenAI()
        affirmations_text = "\n".join(affirmations)
        
        prompt = f"""Create a short, engaging caption for these affirmations:

{affirmations_text}

The caption should:
1. Be 1-2 sentences
2. Be positive and uplifting
3. Encourage engagement
4. Be under 200 characters

Respond with ONLY the caption text, no additional formatting or explanation."""
        
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an expert at creating engaging social media captions. Respond with ONLY the caption text."},
                {"role": "user", "content": prompt}
            ]
        )
        
        caption = response.choices[0].message.content.strip()
        
        # Add the standard hashtags
        standard_hashtags = "#Affirmations #DailyAffirmations #PositiveAffirmations #SelfLove #SelfCare #PositiveVibes #Motivation #Mindset #Gratitude #Positivity #Healing #Manifestation #Inspiration #Mindfulness #AffirmationOfTheDay #affirmationjournal"
        
        # Add theme-specific hashtag
        theme_hashtag = f"#{theme.replace('-', '')}"
        
        # Combine caption and hashtags
        full_caption = f"{caption}\n\n{standard_hashtags}\n{theme_hashtag}"
        
        return full_caption
        
    except Exception as e:
        logger.error(f"Error generating caption: {str(e)}")
        return "Start your day with positive affirmations! 🌟\n\n#Affirmations #DailyAffirmations #PositiveAffirmations #SelfLove #SelfCare #PositiveVibes #Motivation #Mindset #Gratitude #Positivity #Healing #Manifestation #Inspiration #Mindfulness #AffirmationOfTheDay #affirmationjournal"

def get_instagram_business_id():
    """Get the Instagram Business Account ID associated with the Facebook Page."""
    try:
        response = requests.get(
            f'https://graph.facebook.com/v18.0/{FACEBOOK_PAGE_ID}',
            params={
                'access_token': FACEBOOK_ACCESS_TOKEN,
                'fields': 'instagram_business_account'
            }
        )
        
        if response.status_code != 200:
            logger.error(f"Error getting Instagram Business Account ID: {response.text}")
            return None
            
        data = response.json()
        if 'instagram_business_account' not in data:
            logger.error("No Instagram Business Account found for this Facebook Page")
            return None
            
        return data['instagram_business_account']['id']
    except Exception as e:
        logger.error(f"Error getting Instagram Business Account ID: {str(e)}")
        return None

def upload_to_s3(image_path):
    """Upload an image to S3 and return its URL."""
    try:
        s3_client = boto3.client('s3')
        bucket_name = os.getenv('S3_BUCKET_NAME')
        file_name = os.path.basename(image_path)
        
        try:
            # Upload file with public-read ACL
            s3_client.upload_file(
                image_path, 
                bucket_name, 
                file_name,
                ExtraArgs={
                    'ACL': 'public-read',
                    'ContentType': 'image/jpeg',
                    'CacheControl': 'no-cache'  # Prevent caching
                }
            )
            
            url = f"https://{bucket_name}.s3.amazonaws.com/{file_name}"
            logger.info(f"Successfully uploaded image to S3: {url}")
            return url
        except NoCredentialsError:
            logger.error("AWS credentials not available")
            return None
        except Exception as e:
            logger.error(f"Error uploading to S3: {str(e)}")
            return None
            
    except Exception as e:
        logger.error(f"Error in upload_to_s3: {str(e)}")
        return None

def post_to_instagram(image_paths, caption):
    """Post images to Instagram using Facebook Graph API."""
    try:
        # Get Instagram Business Account ID
        instagram_id = get_instagram_business_id()
        if not instagram_id:
            return False
            
        # First, upload images to S3 to get URLs
        image_urls = []
        for image_path in image_paths:
            url = upload_to_s3(image_path)
            if not url:
                logger.error(f"Failed to upload image to S3: {image_path}")
                return False
            image_urls.append(url)
            
        # Create containers for each image
        media_ids = []
        
        for image_url in image_urls:
            # Create container for the image
            response = requests.post(
                f'https://graph.facebook.com/v18.0/{instagram_id}/media',
                data={
                    'access_token': FACEBOOK_ACCESS_TOKEN,
                    'caption': caption if image_url == image_urls[0] else '',  # Only add caption to first image
                    'media_type': 'IMAGE',
                    'is_carousel_item': 'true',
                    'image_url': image_url
                }
            )
            
            if response.status_code != 200:
                logger.error(f"Error creating media container: {response.text}")
                return False
            
            media_id = response.json()['id']
            media_ids.append(media_id)
            
            # Wait for the media to be ready
            status = 'IN_PROGRESS'
            while status == 'IN_PROGRESS':
                time.sleep(5)
                status_response = requests.get(
                    f'https://graph.facebook.com/v18.0/{media_id}',
                    params={
                        'access_token': FACEBOOK_ACCESS_TOKEN,
                        'fields': 'status_code'
                    }
                )
                if status_response.status_code == 200:
                    status = status_response.json().get('status_code', 'IN_PROGRESS')
                else:
                    logger.error(f"Error checking media status: {status_response.text}")
                    return False
        
        # Create the carousel post
        carousel_response = requests.post(
            f'https://graph.facebook.com/v18.0/{instagram_id}/media',
            data={
                'access_token': FACEBOOK_ACCESS_TOKEN,
                'media_type': 'CAROUSEL',
                'children': ','.join(media_ids),
                'caption': caption
            }
        )
        
        if carousel_response.status_code != 200:
            logger.error(f"Error creating carousel: {carousel_response.text}")
            return False
            
        carousel_id = carousel_response.json()['id']
        
        # Publish the carousel
        publish_response = requests.post(
            f'https://graph.facebook.com/v18.0/{instagram_id}/media_publish',
            data={
                'access_token': FACEBOOK_ACCESS_TOKEN,
                'creation_id': carousel_id
            }
        )
        
        if publish_response.status_code != 200:
            logger.error(f"Error publishing carousel: {publish_response.text}")
            return False
        
        logger.info("Successfully posted to Instagram")
        return True
        
    except Exception as e:
        logger.error(f"Error posting to Instagram: {str(e)}")
        return False

def main():
    try:
        # Get random theme
        theme = get_random_theme()
        logger.info(f"Selected theme: {theme}")
        
        # Generate affirmations
        affirmations = generate_themed_affirmations(theme)
        logger.info("Generated affirmations:")
        for aff in affirmations:
            logger.info(f"  - {aff}")
        
        # Split affirmations into two groups
        first_three = affirmations[:3]
        last_three = affirmations[3:]
        
        # Create two images
        image1_path = 'output/swipeable_1.jpg'
        image2_path = 'output/swipeable_2.jpg'
        
        create_affirmation_image(first_three, "assets/iphone_affirmation_background.jpg", image1_path)
        create_affirmation_image(last_three, "assets/iphone_affirmation_background.jpg", image2_path)
        
        # Generate caption
        caption = get_caption(affirmations, theme)
        
        # Post to Instagram
        post_success = post_to_instagram([image1_path, image2_path], caption)
        
        if post_success:
            logger.info("Successfully posted to Instagram")
        else:
            logger.error("Failed to post to Instagram")
        
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        raise

if __name__ == "__main__":
    main() 