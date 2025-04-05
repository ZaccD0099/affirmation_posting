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
    """Generate affirmations based on the given theme using OpenAI."""
    client = OpenAI()
    
    prompt = f"""Generate 5 powerful affirmations based on the theme "{theme}" that are:
    1. Maximum 30 characters each (aim for 25-28 characters)
    2. Personal and in first person ("I" statements)
    3. Present tense
    4. Easy to read quickly in a video
    5. Positive and uplifting
    6. Avoid assumptions about health, wealth, or relationships

    Example character counts:
    "I am worthy of all good things" (27)
    "I choose joy in every moment" (28)
    "I trust my inner wisdom now" (26)
    "I radiate peace and strength" (28)
    "My heart is full of gratitude" (27)
    
    Respond with ONLY a valid JSON object in this exact format:
    {{"affirmations": [
        "I embrace my inner strength",
        "I choose joy every day",
        "I am worthy of greatness",
        "I radiate peace and calm",
        "I trust my journey forward"
    ]}}
    
    Make the affirmations specific to the {theme} theme.
    Each affirmation MUST be 30 characters or less (aim for 25-28).
    Do not include any comments, line numbers, or additional text."""
    
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a professional affirmation writer. You respond with only valid JSON."},
                {"role": "user", "content": prompt}
            ]
        )
        
        # Parse the response and extract affirmations
        content = response.choices[0].message.content.strip()
        affirmations = json.loads(content)["affirmations"]
        
        # Validate character length
        for aff in affirmations:
            if len(aff) > 30:
                logger.warning(f"Affirmation too long ({len(aff)} chars): {aff}")
                
        return affirmations
        
    except Exception as e:
        logger.error(f"Error generating affirmations: {str(e)}")
        # Fallback to predefined affirmations if OpenAI fails
        return get_predefined_affirmations()

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

def main():
    try:
        # Get a random theme and generate affirmations
        theme = get_random_theme()
        logger.info(f"Selected theme: {theme}")
        
        # Generate themed affirmations
        affirmations = generate_themed_affirmations(theme)
        logger.info("Generated affirmations:")
        for aff in affirmations:
            logger.info(f"  - {aff}")
        
        # Create the video
        output_path = create_video(affirmations)
        logger.info(f"Video creation completed. Output saved to: {output_path}")
        
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        raise

if __name__ == "__main__":
    main() 