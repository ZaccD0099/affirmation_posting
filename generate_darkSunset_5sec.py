import os
from dotenv import load_dotenv
from openai import OpenAI
import json
import time
import psutil
import logging
from moviepy.editor import VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip, ColorClip
from functools import wraps
from PIL import Image
import numpy as np
import random
from post_to_social import post_to_social_media
import gc
import requests
import boto3
from datetime import datetime

# Create necessary directories
os.makedirs('temp', exist_ok=True)
os.makedirs('output', exist_ok=True)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def log_memory_usage(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        process = psutil.Process()
        before_mem = process.memory_info().rss / 1024 / 1024
        logger.info(f"Memory usage before {func.__name__}: {before_mem:.2f} MB")
        
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        
        after_mem = process.memory_info().rss / 1024 / 1024
        duration = end_time - time.time()
        
        logger.info(f"Memory usage after {func.__name__}: {after_mem:.2f} MB")
        logger.info(f"Memory difference: {after_mem - before_mem:.2f} MB")
        logger.info(f"Duration: {duration:.2f} seconds")
        
        return result
    return wrapper

# Load environment variables
load_dotenv()

# Constants
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
BACKGROUND_MUSIC_VOLUME = 0.3

def resize_frame(frame, size):
    """Resize a single frame using PIL with high-quality resampling."""
    img = Image.fromarray(frame)
    img = img.resize(size, Image.Resampling.LANCZOS)
    return np.array(img)

def resize_video_clip(clip, target_size):
    """Resize a video clip to the target size using high-quality resampling."""
    resized_clip = clip.fl_image(lambda frame: resize_frame(frame, target_size))
    return resized_clip

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
    """Generate affirmations based on the selected theme using OpenAI."""
    try:
        client = OpenAI()
        
        prompt = f"""Generate 5 affirmations about {theme}. Each affirmation must:
1. Be a maximum of 30 characters (including spaces)
2. Start with "I" and be in present tense
3. Be personal and positive
4. Be easy to read quickly
5. Not use the word "{theme}" directly

Example affirmations for different themes:
- For "Confidence": "I trust my inner wisdom" (22 chars)
- For "Abundance": "I attract prosperity daily" (24 chars)
- For "Self-Love": "I honor my worth always" (23 chars)

Respond with ONLY a valid JSON object containing an array of exactly 5 affirmations, like this:
{{
    "affirmations": [
        "I trust my inner wisdom",
        "I attract prosperity daily",
        "I honor my worth always",
        "I am strong and capable",
        "I create my own success"
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
            "I am enough"
        ]

def get_predefined_affirmations():
    """Return a list of predefined affirmations as a fallback."""
    return [
        "I am worthy of all good things",
        "My potential is limitless",
        "I radiate confidence and grace",
        "Every day I grow stronger",
        "I create my own happiness"
    ]

@log_memory_usage
def create_affirmation_clips(affirmations, duration):
    """Create text clips for all affirmations."""
    text_clips = []
    
    # Calculate vertical spacing
    total_height = VIDEO_HEIGHT * 0.7  # Use 70% of video height
    spacing = total_height / (len(affirmations) + 1)
    
    # Calculate starting Y position to center the text block
    start_y = (VIDEO_HEIGHT - total_height) / 2
    
    for i, text in enumerate(affirmations):
        text_clip = TextClip(
            text,
            fontsize=65,
            color='white',
            font='assets/fonts/Playfair_Display/static/PlayfairDisplay-Regular.ttf',
            size=(VIDEO_WIDTH-100, None),
            method='caption',
            align='center'
        )
        
        # Position text vertically with equal spacing, starting from the calculated start_y
        y_position = start_y + (spacing * (i + 1)) - (text_clip.h / 2)
        positioned_clip = text_clip.set_position(('center', y_position))
        positioned_clip = positioned_clip.set_duration(duration)
        
        text_clips.append(positioned_clip)
    
    return text_clips

@log_memory_usage
def create_video(affirmations, output_path='output/overlay_affirmation.mp4'):
    """Create video with all affirmations overlaid on the background."""
    try:
        # Load background video
        background = VideoFileClip("assets/dark_sunrise.mov")
        video_duration = background.duration
        logger.info(f"Using background video duration: {video_duration} seconds")
        logger.info(f"Original video dimensions: {background.w}x{background.h}")
        
        # Directly resize to target dimensions while maintaining aspect ratio
        background = resize_video_clip(background, (VIDEO_WIDTH, VIDEO_HEIGHT))
        logger.info(f"Final dimensions: {background.w}x{background.h}")
        
        # Load and set up audio
        audio = AudioFileClip("assets/background_music_ambient.mp3")
        audio = audio.subclip(0, video_duration)  # Trim audio to match video
        audio = audio.volumex(BACKGROUND_MUSIC_VOLUME)
        
        # Create text clips
        text_clips = create_affirmation_clips(affirmations, video_duration)
        
        # Combine all elements
        final_video = CompositeVideoClip(
            [background] + text_clips,
            size=(VIDEO_WIDTH, VIDEO_HEIGHT)
        )
        final_video = final_video.set_audio(audio)
        final_video = final_video.set_duration(video_duration)
        
        # Ensure output directory exists
        os.makedirs('output', exist_ok=True)
        
        # Write the final video
        final_video.write_videofile(
            output_path,
            fps=30,
            codec='libx264',
            audio_codec='aac',
            temp_audiofile='temp/temp-audio.m4a',
            remove_temp=True
        )
        
        # Clean up
        background.close()
        audio.close()
        final_video.close()
        for clip in text_clips:
            clip.close()
            
        logger.info(f"Video successfully created at {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"Error creating video: {str(e)}")
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
        
        # Create video
        video_path = create_video(affirmations)
        
        # Generate caption
        caption = get_caption(affirmations, theme)
        
        # Post to social media
        post_to_social_media(video_path, caption)
        
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        raise

if __name__ == "__main__":
    main() 