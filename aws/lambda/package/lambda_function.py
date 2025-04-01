import json
import os
import sys
import boto3
import logging
from datetime import datetime

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize S3 client
s3 = boto3.client('s3')

def download_assets():
    """Download required assets from S3"""
    bucket = os.environ['S3_BUCKET_NAME']
    assets = [
        'assets/Iphone_Affirmation_Background.jpg',
        'assets/background_music_ambient.mp3',
        'assets/fonts/PlayfairDisplay-Regular.ttf'
    ]
    
    for asset in assets:
        try:
            s3.download_file(bucket, asset, asset)
            logger.info(f"Successfully downloaded {asset}")
        except Exception as e:
            logger.error(f"Error downloading {asset}: {str(e)}")
            raise

def lambda_handler(event, context):
    """Main Lambda handler function"""
    try:
        # Download assets from S3
        download_assets()
        
        # Import and run the affirmation script
        sys.path.append('/tmp')
        from generate_affirmation_video import generate_video
        
        # Generate the video
        video_path = generate_video()
        
        # Upload the generated video back to S3
        timestamp = datetime.now().strftime('%Y-%m-%d')
        s3_key = f'output/affirmation_{timestamp}.mp4'
        s3.upload_file(video_path, os.environ['S3_BUCKET_NAME'], s3_key)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Video generated and uploaded successfully',
                'video_path': s3_key
            })
        }
        
    except Exception as e:
        logger.error(f"Error in lambda_handler: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        } 