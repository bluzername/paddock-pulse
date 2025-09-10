"""
Image Concatenation Helper

This script combines a folder of images with an audio file to create a slideshow video.
The images will be distributed evenly across the audio duration.
A template image and audio can be appended to each clip.
Captions can be synchronized with the voiceover audio.

Usage:
    # Single video mode
    python image_concat.py --images path/to/images --output output.mp4 --audio audio.wav

    # Batch processing mode
    python image_concat.py --batch-directory path/to/batch_dir --font-name "BebasNeue-Regular"

    # Simple batch processing (no captions, just image+audio)
    python image_concat.py --batch-directory path/to/batch_dir --simple-mode

    # Specify a custom output directory
    python image_concat.py --batch-directory path/to/batch_dir --output-directory path/to/output

    # Use a custom timestamp for filenames
    python image_concat.py --batch-directory path/to/batch_dir --timestamp "20250408"

Supported Directory Structures for Batch Processing:

1. Traditional Structure:
    - batch_directory/
      - post_id1/
        - images/  (folder containing images)
        - audio.wav  (or audio.mp3, etc.)
        - post.txt  (text file with captions)
      - post_id2/
        - images/
        - audio.wav
        - post.txt

2. New Structure (as in output/20250408_101522):
    - batch_directory/
      - posts/
        - f1_posts.json  (JSON file with post texts)
      - voiceovers/
        - f1_posts/
          - voiceovers/
            - 1_Post_Name.mp3
            - 2_Post_Name.mp3
      - images/
        - Post_Name/
          - 1_Post_Name.png
          - 2_Post_Name.png
          - 3_Post_Name.png

Output Directory Structure:
    By default, videos will be saved to:
    - PaddockPulse/output/TIMESTAMP/reel/TIMESTAMP_post1_PostName_reel.mp4

    This mimics the structure used in the production environment:
    - output/20250407_104824/reel/20250407_104824_post1_PostName_reel.mp4

    If a custom output directory is specified with --output-directory:
    - custom_output_directory/reel/TIMESTAMP_post1_PostName_reel.mp4
"""

import os
import sys
import argparse
import logging
import json
import tempfile
from pathlib import Path
from typing import List, Tuple, Dict, Optional
import numpy as np
from moviepy import editor as mpy
from moviepy.config import get_setting, change_settings
import colorama
from colorama import Fore, Style
import re
import glob
import whisper
import difflib
import time
import math
import traceback
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips, CompositeVideoClip, ColorClip

# Set ImageMagick binary name for Mac compatibility
if sys.platform == 'darwin':  # macOS
    try:
        # Try both possible binary locations
        if os.path.exists('/opt/homebrew/bin/magick'):
            magick_binary = '/opt/homebrew/bin/magick'
            change_settings({"IMAGEMAGICK_BINARY": magick_binary})
        elif os.path.exists('/usr/local/bin/magick'):
            magick_binary = '/usr/local/bin/magick'
            change_settings({"IMAGEMAGICK_BINARY": magick_binary})
        else:
            print("ImageMagick not found in standard locations. Text rendering may be limited.")
    except Exception as e:
        print(f"Warning: Could not set ImageMagick binary: {e}")

# Import additional libraries for custom text rendering
try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("Warning: PIL not available for custom text rendering")

# Initialize colorama for colored terminal output
colorama.init(autoreset=True)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format=f"{Fore.CYAN}%(asctime)s{Style.RESET_ALL} - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("image_concat")

def get_image_files(folder_path: str) -> List[str]:
    """
    Get a list of image files from the specified folder and its subfolders.
    
    Args:
        folder_path: Path to the folder containing images
        
    Returns:
        List of image file paths
    """
    valid_extensions = ['.jpg', '.jpeg', '.png', '.webp']
    
    image_files = []
    
    # Check if the directory exists
    if not os.path.isdir(folder_path):
        logger.error(f"Directory does not exist: {folder_path}")
        return image_files
    
    # Recursively walk through all subdirectories
    for root, _, files in os.walk(folder_path):
        # Sort files to ensure consistent ordering
        for file in sorted(files):
            ext = os.path.splitext(file)[1].lower()
            if ext in valid_extensions:
                image_files.append(os.path.join(root, file))
    
    logger.info(f"Found {len(image_files)} images in {folder_path} and its subfolders")
    return image_files

def calculate_durations(audio_duration: float, num_images: int) -> List[float]:
    """
    Calculate how long each image should be displayed.
    
    Args:
        audio_duration: Duration of the audio in seconds
        num_images: Number of images to display
        
    Returns:
        List of durations for each image
    """
    # Simple even distribution
    return [audio_duration / num_images] * num_images

def create_text_clip_pil(text, font_size=70, font_name="Arial", color="white", bg_color="black", 
                        bg_opacity=0.5, size=(720, 80), align='center', 
                        stroke_width=3, stroke_color="black", max_zoom=1.08):
    """
    Create a text clip using PIL instead of ImageMagick.
    
    Args:
        text: Text to display
        font_size: Font size
        font_name: Font name (will use default if not found)
        color: Text color
        bg_color: Background color
        bg_opacity: Background opacity (0-1)
        size: Size of the text clip (width, height)
        align: Text alignment
        stroke_width: Width of text outline/stroke (0 for none)
        stroke_color: Color of text outline/stroke
        max_zoom: Maximum zoom factor for animation padding
        
    Returns:
        MoviePy ImageClip with the rendered text
    """
    if not HAS_PIL:
        logger.error("PIL not available for custom text rendering")
        return None
        
    # Debug information
    logger.info(f"Creating text clip for: '{text}'")
    logger.info(f"Parameters: size={size}, font_size={font_size}, color={color}, stroke={stroke_width}")
    
    # Ensure stroke width is at least 3 for visibility
    stroke_width = max(3, stroke_width)
    
    # Calculate padding to handle max_zoom without clipping
    padding_for_zoom = int(max(size) * (max_zoom - 1.0) * 0.5) + stroke_width * 4
    
    # Create a transparent background image with padding for zoom
    padded_width = size[0] + padding_for_zoom * 2
    padded_height = size[1] + padding_for_zoom * 2
    bg_img = Image.new('RGBA', (padded_width, padded_height), color=(0, 0, 0, 0))
    draw = ImageDraw.Draw(bg_img)
    
    # Common system fonts that look like Instagram captions
    common_fonts = [
        "Bebas Neue",         # Primary choice
        "BebasNeue-Regular",  # Alternative spelling
        "Arial Rounded MT Bold",  # Fallback
        "Arial Bold",         # Another fallback
        font_name            # User specified
    ]
    
    # Load the most Instagram-like font available on the system
    font = None
    for font_name in common_fonts:
        try:
            font = ImageFont.truetype(font_name, font_size)
            logger.info(f"Using font: {font_name}")
            break
        except:
            continue
    
    # If none of the preferred fonts are available, use default
    if font is None:
        font = ImageFont.load_default()
        font_size = max(font_size // 2, 24)  # Adjust size for default font
        logger.info("Using default font")
    
    # Convert color strings to RGB
    try:
        if color.startswith('#'):
            r = int(color[1:3], 16)
            g = int(color[3:5], 16)
            b = int(color[5:7], 16)
            text_color = (r, g, b, 255)
        elif color == "white":
            text_color = (255, 255, 255, 255)
        elif color == "instagram":
            # Instagram gradient-like color (bright white with slight blue tint)
            text_color = (240, 240, 255, 255)
        else:
            text_color = (245, 245, 245, 255)  # Default to smoke white
    except:
        text_color = (245, 245, 245, 255)  # Default to smoke white
    
    # Convert stroke color
    try:
        if stroke_color.startswith('#'):
            r = int(stroke_color[1:3], 16)
            g = int(stroke_color[3:5], 16)
            b = int(stroke_color[5:7], 16)
            outline_color = (r, g, b, 255)
        elif stroke_color == "black":
            outline_color = (0, 0, 0, 255)
        else:
            outline_color = (31, 31, 31, 255)  # Default to carbon gray
    except:
        outline_color = (31, 31, 31, 255)  # Default to carbon gray
        
    # Get text size
    try:
        text_width, text_height = draw.textsize(text, font=font)
        logger.info(f"Text dimensions: {text_width}x{text_height}")
    except:
        try:
            # For newer PIL versions
            text_width, text_height = draw.textbbox((0, 0), text, font=font)[2:4]
            logger.info(f"Text dimensions (textbbox): {text_width}x{text_height}")
        except:
            # Approximate if all methods fail
            text_width = len(text) * (font_size // 2)
            text_height = font_size * 1.2
            logger.info(f"Text dimensions (approximated): {text_width}x{text_height}")
    
    # Handle text that's too wide for the specified width
    if text_width > padded_width - 60:  # More padding for better fit
        # Adjust font size to fit within width
        scale_factor = (padded_width - 60) / text_width
        new_font_size = int(font_size * scale_factor * 0.95)  # 5% extra margin
        logger.info(f"Text too wide, scaling font from {font_size} to {new_font_size}")
        
        # Recreate font with new size
        try:
            font = ImageFont.truetype(font_name, new_font_size)
            
            # Recalculate text dimensions
            try:
                text_width, text_height = draw.textsize(text, font=font)
            except:
                try:
                    text_width, text_height = draw.textbbox((0, 0), text, font=font)[2:4]
                except:
                    text_width = len(text) * (new_font_size // 2)
                    text_height = new_font_size * 1.2
            
            logger.info(f"New text dimensions: {text_width}x{text_height}")
        except Exception as e:
            logger.warning(f"Error adjusting font size: {e}")
    
    # Create text with stroke at center of image with transparent background
    text_x = (padded_width - text_width) // 2
    text_y = (padded_height - text_height) // 2
    
    # Draw text stroke/outline
    if stroke_width > 0:
        # For thick stroke, draw multiple offset versions
        for offset in range(1, stroke_width + 1):
            for dx, dy in [(-offset, -offset), (-offset, offset), (offset, -offset), (offset, offset),
                          (-offset, 0), (offset, 0), (0, -offset), (0, offset)]:
                draw.text((text_x + dx, text_y + dy), text, font=font, fill=outline_color)
    
    # Draw the main text
    draw.text((text_x, text_y), text, font=font, fill=text_color)
    
    # Convert to RGB for MoviePy compatibility
    rgb_img = Image.new('RGB', bg_img.size, (0, 0, 0))
    try:
        # Make background transparent by using alpha channel as mask
        rgb_img.paste(bg_img, mask=bg_img.split()[3])  # Use alpha channel as mask
        logger.info("Image converted with alpha channel")
    except:
        # If alpha channel issues, just convert without transparency
        rgb_img = bg_img.convert('RGB')
        logger.info("Image converted without alpha channel")
    
    # Save a sample to debug directory
    debug_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug_captions")
    if not os.path.exists(debug_dir):
        try:
            os.makedirs(debug_dir)
        except:
            logger.warning(f"Could not create debug directory: {debug_dir}")
            debug_dir = tempfile.gettempdir()
    
    # Save a few examples for debugging
    if len(text) < 50:  # Only save short captions to avoid clutter
        debug_file = os.path.join(debug_dir, f"caption_{text.replace(' ', '_')[:20]}.png")
        try:
            bg_img.save(debug_file)  # Save the RGBA image for debugging
            logger.info(f"Debug caption saved to: {debug_file}")
        except Exception as e:
            logger.warning(f"Could not save debug caption: {e}")
    
    # Create a unique temporary filename
    temp_dir = tempfile.gettempdir()
    temp_file = os.path.join(temp_dir, f"temp_text_{abs(hash(text)) % 10000}.png")
    
    try:
        # Save with transparent background
        bg_img.save(temp_file, format='PNG')
        
        # Create the clip
        clip = mpy.ImageClip(temp_file)
        logger.info(f"Created clip with dimensions: {clip.size}")
        
        # Clean up the temp file
        try:
            os.remove(temp_file)
        except:
            pass
            
        return clip
    except Exception as e:
        logger.error(f"Error creating clip from PIL image: {e}")
        try:
            os.remove(temp_file)
        except:
            pass
        return None

def create_caption(text: str, size: Tuple[int, int], font: str = 'Bebas Neue', 
                  fontsize: int = 70, color: str = '#F5F5F5', 
                  bg_color: str = None, bg_opacity: float = 0,
                  position: str = 'bottom', stroke_width: int = 3,
                  stroke_color: str = '#1F1F1F', animate: bool = False,
                  max_zoom: float = 1.0, caption_start: float = 0.1,
                  caption_end: float = 0.9, caption_left: float = 0.15,
                  caption_width: float = 0.7):
    """
    Create a caption with the specified style.
    
    Args:
        text: The text to display
        size: Size of the video frame
        font: Font name
        fontsize: Font size
        color: Text color
        bg_color: Background color
        bg_opacity: Background opacity (0-1)
        position: Position of caption ('top', 'bottom', 'center')
        stroke_width: Width of text outline/stroke (0 for none)
        stroke_color: Color of text outline/stroke
        animate: Whether to animate the caption
        max_zoom: Maximum zoom factor (for padding calculation)
        caption_start: Caption start position from top (0.0-1.0)
        caption_end: Caption end position from top (0.0-1.0)
        caption_left: Caption left position (0.0-1.0)
        caption_width: Caption width as percentage of screen (0.0-1.0)
        
    Returns:
        TextClip with the caption
    """
    # Ensure the caption width fits within the video frame
    caption_height = fontsize + 80  # Add more padding for IG style
    caption_width = int(size[0] * caption_width)  # Use percentage of screen width
    
    # Try the custom PIL-based approach
    txt_clip = create_text_clip_pil(
        text, 
        font_size=fontsize,
        font_name=font,
        color=color,
        bg_color=bg_color,
        bg_opacity=bg_opacity,
        size=(caption_width, caption_height),
        stroke_width=stroke_width,
        stroke_color=stroke_color,
        max_zoom=max_zoom
    )
    
    if txt_clip is None:
        # Fall back to MoviePy approaches if custom rendering fails
        try:
            # Try PIL method first
            txt_clip = mpy.TextClip(text, fontsize=fontsize, color=color, method='pil')
        except Exception as e:
            logger.warning(f"PIL text rendering failed: {str(e)}, trying label method")
            try:
                # Try label method as fallback
                txt_clip = mpy.TextClip(text, fontsize=fontsize, color=color, method='label')
            except Exception as e2:
                logger.warning(f"Label text rendering failed: {str(e2)}, using default method")
                # Default method as last resort
                try:
                    txt_clip = mpy.TextClip(text, fontsize=fontsize, color=color)
                except Exception as e3:
                    logger.error(f"All text rendering methods failed: {str(e3)}")
                    # Create a blank clip as last resort
                    txt_clip = mpy.ColorClip(size=(caption_width, caption_height), color=(0, 0, 0))
    
    # Force clip size to match video width if it's wider
    if txt_clip.size[0] > caption_width:
        # Resize to fit caption width while preserving aspect ratio
        new_height = int(txt_clip.size[1] * (caption_width / txt_clip.size[0]))
        txt_clip = txt_clip.resize(width=caption_width, height=new_height)
        logger.info(f"Resized caption from {txt_clip.size} to ({caption_width}, {new_height})")
    
    # Calculate position based on the new parameters
    x_pos = int(size[0] * caption_left)  # Left position as percentage of screen width
    
    # Calculate vertical position based on caption_start and caption_end
    if position == 'top':
        y_pos = int(size[1] * caption_start)  # Position from top
    elif position == 'bottom':
        y_pos = int(size[1] * caption_end) - txt_clip.size[1]  # Position from bottom
    else:  # center
        y_pos = int(size[1] * (caption_start + caption_end) / 2) - (txt_clip.size[1] // 2)
    
    # Create the final clip with proper positioning
    caption = txt_clip.set_position((x_pos, y_pos))
    
    # Apply animation if requested
    if animate:
        # Instagram-style soft zoom with bouncing effect
        def zoom_effect(t):
            # Start small and zoom to full size, with slight bounce
            if t < 0.3:  # First 0.3 seconds
                scale = 0.7 + 0.3 * (t / 0.3)  # Scale from 0.7 to 1.0
            elif t < 0.4:  # Next 0.1 seconds
                scale = 1.0 + 0.08 * ((t - 0.3) / 0.1)  # Slight overshoot to 1.08
            elif t < 0.5:  # Final 0.1 seconds
                scale = 1.08 - 0.08 * ((t - 0.4) / 0.1)  # Settle back to 1.0
            else:
                scale = 1.0  # Stay at full size
                
            return scale
            
        caption = caption.fx(mpy.vfx.resize, lambda t: zoom_effect(t))
        logger.info("Applied Instagram-style zoom animation to caption")
    
    return caption

def chunk_text(text: str, chunk_size: int = 5) -> List[str]:
    """
    Split text into chunks of specified word size, with flexibility on chunk size.
    
    Args:
        text: Text to split
        chunk_size: Target number of words per chunk
        
    Returns:
        List of text chunks
    """
    # Remove extra whitespace and split text into words
    words = re.sub(r'\s+', ' ', text).strip().split()
    
    # Group words into chunks with dynamic sizing
    chunks = []
    current_chunk = []
    current_length = 0
    
    for word in words:
        # Add to current chunk if it doesn't exceed max characters
        if current_length + len(word) + len(current_chunk) <= 30:  # +len(current_chunk) accounts for spaces
            current_chunk.append(word)
            current_length += len(word) + (1 if current_length > 0 else 0)  # Add 1 for space
        else:
            # Store current chunk and start a new one
            if current_chunk:
                chunks.append(' '.join(current_chunk))
            current_chunk = [word]
            current_length = len(word)
        
        # If we've reached target chunk size and next word would make a good break
        if len(current_chunk) >= chunk_size and (len(word) > 3 or word.endswith(('.', ',', '!', '?'))):
            chunks.append(' '.join(current_chunk))
            current_chunk = []
            current_length = 0
    
    # Add any remaining words
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    
    return chunks

def combine_short_words(word_chunks: List[List[str]]) -> List[List[str]]:
    """
    Combine short words (3 characters or less) into pairs to display together.
    
    Args:
        word_chunks: List of lists of words
        
    Returns:
        Modified word_chunks with short words combined
    """
    result = []
    
    for chunk in word_chunks:
        new_chunk = []
        i = 0
        while i < len(chunk):
            current_word = chunk[i]
            
            # Check if this is a short word and there's a next word that's also short
            if (len(current_word) <= 3 and 
                i + 1 < len(chunk) and 
                len(chunk[i+1]) <= 3):
                
                # Combine the two short words
                combined = current_word + " " + chunk[i+1]
                new_chunk.append(combined)
                i += 2  # Skip the next word since we've combined it
            else:
                new_chunk.append(current_word)
                i += 1
        
        result.append(new_chunk)
    
    return result

def word_by_word_chunks(text: str) -> List[List[str]]:
    """
    Split text into chunks for 2-line captions with 3-5 words per line.
    Each chunk will be a list of individual words to animate.
    
    Args:
        text: Text to split
        
    Returns:
        List of lists, where each inner list contains words for one caption
    """
    # Remove extra whitespace and split text into words
    words = re.sub(r'\s+', ' ', text).strip().split()
    
    # Calculate how many chunks needed (max words per caption = ~10)
    max_words_per_caption = 10
    num_chunks = max(1, (len(words) + max_words_per_caption - 1) // max_words_per_caption)
    
    # Group words into chunks for 2-line captions
    chunks = []
    for i in range(0, len(words), max_words_per_caption):
        chunk = words[i:i+max_words_per_caption]
        if chunk:
            # Split each chunk into two lines of roughly equal word count
            line_break = (len(chunk) + 1) // 2  # Calculate middle point
            
            # Adjust line break to avoid splitting after 1-2 words or prepositions
            if line_break <= 2 and len(chunk) > 4:
                line_break = 3
            elif line_break >= len(chunk) - 1 and len(chunk) > 4:
                line_break = len(chunk) - 2
                
            # Create the two lines
            line1 = chunk[:line_break]
            line2 = chunk[line_break:]
            
            chunks.append(line1 + line2)  # Add as a single list for animation
            
    # Combine short words for better readability
    chunks = combine_short_words(chunks)
    
    return chunks

def estimate_chunk_durations(chunks: List[str], total_duration: float) -> List[float]:
    """
    Estimate duration for each text chunk based on word count.
    
    Args:
        chunks: List of text chunks
        total_duration: Total audio duration in seconds
        
    Returns:
        List of estimated durations for each chunk
    """
    # Count words in each chunk
    word_counts = [len(chunk.split()) for chunk in chunks]
    total_words = sum(word_counts)
    
    # Calculate durations proportionally by word count
    durations = []
    for count in word_counts:
        # Add a minimum duration of 1 second per chunk
        duration = max(1.0, (count / total_words) * total_duration)
        durations.append(duration)
    
    # Adjust to match total duration
    duration_sum = sum(durations)
    if duration_sum > 0:
        scale_factor = total_duration / duration_sum
        durations = [d * scale_factor for d in durations]
    
    return durations

def create_timed_captions(text, font_name, font_size, color, stroke_width, stroke_color, duration, video_width, video_height, bg_color=None, save_debug_images=False, debug_path=None, audio_file=None):
    """
    Create a series of caption clips that show one word at a time, centered on screen.
    Each word is perfectly synced with the voiceover using Whisper for timing.
    
    Args:
        text (str): The text to display
        font_name (str): Name of the font to use
        font_size (int): Font size
        color (str): Font color
        stroke_width (int): Width of text stroke
        stroke_color (str): Color of text stroke
        duration (float): Total duration for all captions
        video_width (int): Width of the video
        video_height (int): Height of the video
        bg_color (str, optional): Background color. Defaults to None (transparent).
        save_debug_images (bool, optional): Whether to save debug images. Defaults to False.
        debug_path (str, optional): Path to save debug images. Defaults to None.
        audio_file (str, optional): Path to the audio file for speech recognition. Required for precise sync.
        
    Returns:
        list: List of caption clips
    """
    # Make sure we have a valid duration
    if duration is None or duration <= 0:
        logging.warning("Invalid duration for captions. Using 5 seconds.")
        duration = 5.0
    
    # Clean and split the text from the original script
    original_words = text.split()
    
    # Remove any empty words
    original_words = [word for word in original_words if word.strip()]
    
    if not original_words:
        logging.warning("No words found in caption text")
        return []
    
    # If no audio file provided, fall back to simple timing distribution
    if not audio_file:
        logging.warning("*** WORD-BY-WORD MODE: No audio file provided for speech recognition. Using simple timing distribution.")
        return create_simple_timed_captions(
            text, font_name, font_size, color, stroke_width, stroke_color, 
            duration, video_width, video_height, bg_color, save_debug_images, debug_path
        )
    
    # Check if audio file exists
    if not os.path.exists(audio_file):
        logging.warning(f"*** WORD-BY-WORD MODE: Audio file does not exist: {audio_file}. Using simple timing distribution.")
        return create_simple_timed_captions(
            text, font_name, font_size, color, stroke_width, stroke_color, 
            duration, video_width, video_height, bg_color, save_debug_images, debug_path
        )
        
    logging.info(f"*** WORD-BY-WORD MODE: Using audio file for word timing: {audio_file}")
    
    # Available dimensions
    # Use 80% of video width for captions to avoid edges
    available_width = int(video_width * 0.8)
    
    # Calculate vertical position - place in lower third of video
    y_pos = int(video_height * 0.7)
    
    # Height of the caption area - leave some room
    caption_height = int(video_height * 0.2)
    
    try:
        # Check if whisper is installed
        try:
            import whisper
            logging.info("*** WORD-BY-WORD MODE: Whisper is installed. Will attempt to use it for word timing.")
        except ImportError:
            logging.warning("*** WORD-BY-WORD MODE: Whisper is not installed. Cannot use precise word timing.")
            logging.warning("Install whisper with: pip install -U openai-whisper")
            return create_simple_timed_captions(
                text, font_name, font_size, color, stroke_width, stroke_color, 
                duration, video_width, video_height, bg_color, save_debug_images, debug_path
            )
        
        # Load Whisper model (using 'base' for speed, can be 'tiny', 'base', 'small', 'medium', 'large')
        logging.info("*** WORD-BY-WORD MODE: Loading Whisper model for speech recognition...")
        model = whisper.load_model("base")
        
        # Process the audio file
        logging.info(f"*** WORD-BY-WORD MODE: Processing audio file with Whisper: {audio_file}")
        result = model.transcribe(
            audio_file,
            word_timestamps=True,  # Get word-level timestamps
            language="en"          # Specify English for better accuracy
        )
        
        # Extract words with timestamps
        whisper_words = []
        for segment in result['segments']:
            for word_info in segment.get('words', []):
                word_text = word_info.get('word', '').strip().lower()
                # Clean up Whisper's output (it often includes leading space)
                word_text = word_text.strip()
                if word_text:
                    start_time = word_info.get('start', 0)
                    end_time = word_info.get('end', 0)
                    whisper_words.append({
                        'word': word_text,
                        'start': start_time,
                        'end': end_time
                    })
        
        if not whisper_words:
            logging.warning("*** WORD-BY-WORD MODE: Whisper could not extract word timestamps. Falling back to simple timing.")
            return create_simple_timed_captions(
                text, font_name, font_size, color, stroke_width, stroke_color, 
                duration, video_width, video_height, bg_color, save_debug_images, debug_path
            )
        
        # Align Whisper words with original text
        # Convert original words to lowercase for better matching
        original_text_lower = ' '.join(w.lower() for w in original_words)
        whisper_text_lower = ' '.join(w['word'] for w in whisper_words)
        
        logging.info(f"*** WORD-BY-WORD MODE: Original text: {original_text_lower[:50]}...")
        logging.info(f"*** WORD-BY-WORD MODE: Whisper text: {whisper_text_lower[:50]}...")
        
        # Use sequence matcher to align the texts
        matcher = difflib.SequenceMatcher(None, whisper_text_lower.split(), original_text_lower.split())
        
        # Create a mapping from original words to timing
        word_timings = []
        
        # Process each match block
        for block in matcher.get_matching_blocks():
            whisper_idx, original_idx, length = block
            
            # Skip the last dummy block
            if length == 0:
                continue
                
            for i in range(length):
                if whisper_idx + i < len(whisper_words) and original_idx + i < len(original_words):
                    word_timings.append({
                        'word': original_words[original_idx + i],
                        'start': whisper_words[whisper_idx + i]['start'],
                        'end': whisper_words[whisper_idx + i]['end']
                    })
        
        # Handle unmatched words with proportional timing
        if len(word_timings) < len(original_words):
            logging.warning(f"*** WORD-BY-WORD MODE: Not all words could be matched ({len(word_timings)} of {len(original_words)}). Adding estimates for missing words.")
            
            # Get matched indices
            matched_indices = set(i for i, _ in enumerate(word_timings))
            
            # Estimate timing for unmatched words
            unmatched_count = len(original_words) - len(word_timings)
            if unmatched_count > 0:
                # Simple approach: distribute remaining words proportionally
                # This is a fallback for words Whisper couldn't align
                for i in range(len(original_words)):
                    if i not in matched_indices:
                        # Find nearest matched word
                        nearest_before = None
                        nearest_after = None
                        
                        for j, timing in enumerate(word_timings):
                            if j < i and (nearest_before is None or j > nearest_before):
                                nearest_before = j
                            if j > i and (nearest_after is None or j < nearest_after):
                                nearest_after = j
                        
                        # Estimate timing based on nearest words
                        if nearest_before is not None and nearest_after is not None:
                            # Interpolate between nearest words
                            before_end = word_timings[nearest_before]['end']
                            after_start = word_timings[nearest_after]['start']
                            start_time = before_end
                            end_time = after_start
                        elif nearest_before is not None:
                            # After the last matched word
                            before_end = word_timings[nearest_before]['end']
                            word_duration = word_timings[nearest_before]['end'] - word_timings[nearest_before]['start']
                            start_time = before_end
                            end_time = start_time + word_duration
                        elif nearest_after is not None:
                            # Before the first matched word
                            after_start = word_timings[nearest_after]['start']
                            word_duration = word_timings[nearest_after]['end'] - word_timings[nearest_after]['start']
                            end_time = after_start
                            start_time = end_time - word_duration
                        else:
                            # No matches at all - use simple distribution
                            start_time = (i / len(original_words)) * duration
                            end_time = ((i + 1) / len(original_words)) * duration
                        
                        word_timings.insert(i, {
                            'word': original_words[i],
                            'start': start_time,
                            'end': end_time
                        })
        
        # Sort by start time
        word_timings.sort(key=lambda x: x['start'])
        
        # Create clips for each word
        caption_clips = []
        
        for i, word_timing in enumerate(word_timings):
            try:
                word = word_timing['word']
                word_start = word_timing['start']
                word_end = word_timing['end']
                
                # Ensure word duration is not too short
                min_word_duration = 0.1  # Minimum 0.1 seconds per word
                word_duration = max(word_end - word_start, min_word_duration)
                
                # Create text clip for this word
                logging.info(f"*** WORD-BY-WORD MODE: Creating text clip for: '{word}' (time: {word_start:.2f} - {word_end:.2f})")
                
                # For single words, we can use larger font size
                word_font_size = min(font_size * 1.5, available_width // (len(word) + 2))
                
                # Ensure font size is reasonable
                word_font_size = max(min(word_font_size, 120), 40)
                
                # Create clip with some padding
                clip_size = (available_width, caption_height)
                
                # Create the text clip with only supported parameters
                word_clip = create_text_clip_pil(
                    word,
                    font_name=font_name,
                    font_size=int(word_font_size),
                    color=color,
                    stroke_width=stroke_width,
                    stroke_color=stroke_color,
                    size=clip_size,
                    bg_color=bg_color
                )
                
                # Center the clip on the screen (always at the exact same position)
                x_center = (video_width - word_clip.size[0]) // 2
                
                # Position with precise timing
                word_clip = word_clip.set_position((x_center, y_pos))
                word_clip = word_clip.set_start(word_start)
                word_clip = word_clip.set_duration(word_duration)
                
                # Explicitly set the duration attribute
                if not hasattr(word_clip, 'duration') or word_clip.duration is None:
                    word_clip.duration = word_duration
                    
                # Add a subtle fade in/out effect
                fade_time = min(0.05, word_duration / 4)  # Quick fade for smooth transitions
                if fade_time > 0:
                    try:
                        word_clip = word_clip.fadein(fade_time).fadeout(fade_time)
                    except Exception as e:
                        logging.warning(f"Could not add fade effect: {e}")
                
                caption_clips.append(word_clip)
                
            except Exception as e:
                logging.error(f"Error creating caption for word '{word}': {e}")
    
    except Exception as e:
        logging.error(f"*** WORD-BY-WORD MODE: Error during speech recognition: {str(e)}")
        logging.warning("*** WORD-BY-WORD MODE: Falling back to simple timing distribution.")
        return create_simple_timed_captions(
            text, font_name, font_size, color, stroke_width, stroke_color, 
            duration, video_width, video_height, bg_color, save_debug_images, debug_path
        )
    
    logging.info(f"*** WORD-BY-WORD MODE: Created {len(caption_clips)} word caption clips with precise timing")
    
    return caption_clips

def create_simple_timed_captions(text, font_name, font_size, color, stroke_width, stroke_color, duration, video_width, video_height, bg_color=None, save_debug_images=False, debug_path=None):
    """
    Fallback function to create captions with simple timing distribution.
    Used when speech recognition is not available or fails.
    
    Args:
        Same as create_timed_captions
        
    Returns:
        list: List of caption clips
    """
    logging.info("*** SIMPLE TIMING MODE: Creating captions with simple timing distribution (one word at a time)")
    
    # Clean and split the text
    words = text.split()
    
    # Remove any empty words
    words = [word for word in words if word.strip()]
    
    if not words:
        logging.warning("No words found in caption text")
        return []
        
    # Calculate timing per word
    word_count = len(words)
    word_duration = duration / word_count
    
    # Make sure word duration is not too short
    min_word_duration = 0.25  # Minimum 0.25 seconds per word
    word_duration = max(word_duration, min_word_duration)
    
    # Available dimensions
    # Use 80% of video width for captions to avoid edges
    available_width = int(video_width * 0.8)
    
    # Calculate vertical position - place in lower third of video
    y_pos = int(video_height * 0.7)
    
    # Height of the caption area - leave some room
    caption_height = int(video_height * 0.2)
    
    # Create clips for each word
    caption_clips = []
    
    for i, word in enumerate(words):
        try:
            # Calculate start time for this word
            word_start = i * word_duration
            
            # If we would exceed the total duration, adjust timing
            if word_start + word_duration > duration:
                # Ensure we don't exceed the total duration
                remaining_time = max(0.1, duration - word_start)
                word_duration = remaining_time
            
            # Create text clip for this word
            logging.info(f"*** SIMPLE TIMING MODE: Creating text clip for: '{word}' (time: {word_start:.2f} - {word_start+word_duration:.2f})")
            
            # For single words, we can use larger font size
            word_font_size = min(font_size * 1.5, available_width // (len(word) + 2))
            
            # Ensure font size is reasonable
            word_font_size = max(min(word_font_size, 120), 40)
            
            # Create clip with some padding
            clip_size = (available_width, caption_height)
            
            logging.info(f"Parameters: size={clip_size}, font_size={word_font_size}, color={color}, stroke={stroke_width}")
            
            # Create the text clip with only supported parameters
            word_clip = create_text_clip_pil(
                word,
                font_name=font_name,
                font_size=int(word_font_size),
                color=color,
                stroke_width=stroke_width,
                stroke_color=stroke_color,
                size=clip_size,
                bg_color=bg_color
            )
            
            # Center the clip on the screen
            x_center = (video_width - word_clip.size[0]) // 2
            
            # Position with proper timing
            word_clip = word_clip.set_position((x_center, y_pos))
            word_clip = word_clip.set_start(word_start)
            word_clip = word_clip.set_duration(word_duration)
            
            # Explicitly set the duration attribute
            if not hasattr(word_clip, 'duration') or word_clip.duration is None:
                word_clip.duration = word_duration
                
            # Add a subtle fade in/out effect
            fade_time = min(0.1, word_duration / 4)
            if fade_time > 0:
                try:
                    word_clip = word_clip.fadein(fade_time).fadeout(fade_time)
                except Exception as e:
                    logging.warning(f"Could not add fade effect: {e}")
            
            caption_clips.append(word_clip)
            
        except Exception as e:
            logging.error(f"Error creating caption for word '{word}': {e}")
    
    logging.info(f"*** SIMPLE TIMING MODE: Created {len(caption_clips)} word caption clips with simple timing")
    
    return caption_clips

def create_caption_clips(text, font_name, font_size, color, stroke_width, stroke_color, 
                        duration, video_width, video_height, chunk_size=5, animate=True, 
                        bg_color=None):
    """
    Create text clips from the caption text, split into chunks.
    This is the traditional captioning method showing multiple words at once.
    
    Args:
        text: The text to display
        font_name: Name of the font to use
        font_size: Font size
        color: Text color
        stroke_width: Width of text stroke
        stroke_color: Color of text stroke
        duration: Total duration for all captions
        video_width: Width of the video
        video_height: Height of the video
        chunk_size: Number of words per caption chunk
        animate: Whether to animate captions
        bg_color: Background color for captions
        
    Returns:
        list: List of caption clips
    """
    logging.info("Creating traditional caption clips (multiple words at once)")
    
    # Split text into chunks
    chunks = chunk_text(text, chunk_size)
    
    if not chunks:
        logging.warning("No text chunks created from caption text")
        return []
    
    # Estimate duration for each chunk based on word count
    chunk_durations = estimate_chunk_durations(chunks, duration)
    
    # Size for caption clips
    caption_width = int(video_width * 0.8)  # Use 80% of video width
    caption_height = int(video_height * 0.3)  # Use 30% of video height for caption area
    
    # Vertical position - place in lower third of video
    y_pos = int(video_height * 0.65) # Position at 65% from top
    
    # Create clips for each chunk
    caption_clips = []
    
    current_time = 0.0
    
    for i, (chunk, chunk_duration) in enumerate(zip(chunks, chunk_durations)):
        try:
            logging.info(f"Creating caption {i+1}/{len(chunks)}: '{chunk}' (duration: {chunk_duration:.2f}s)")
            
            # Create the caption clip
            caption = create_caption(
                text=chunk,
                size=(video_width, video_height),
                font=font_name,
                fontsize=font_size,
                color=color,
                bg_color=bg_color,
                stroke_width=stroke_width,
                stroke_color=stroke_color,
                animate=animate,
                position='bottom'
            )
            
            # Set timing
            caption = caption.set_start(current_time)
            caption = caption.set_duration(chunk_duration)
            current_time += chunk_duration
            
            # Add a subtle fade in/out effect
            fade_time = min(0.3, chunk_duration / 5)
            if fade_time > 0:
                try:
                    caption = caption.fadein(fade_time).fadeout(fade_time)
                except Exception as e:
                    logging.warning(f"Could not add fade effect: {e}")
            
            caption_clips.append(caption)
            
        except Exception as e:
            logging.error(f"Error creating caption for chunk '{chunk}': {e}")
    
    logging.info(f"Created {len(caption_clips)} caption clips")
    
    return caption_clips

def get_post_text(post_id=None, post_json=None, post_file=None, caption_text=None, data_dir=None):
    """
    Get the post text from various sources.
    
    Args:
        post_id (str): ID of the post to use from the JSON data
        post_json (dict): JSON data for posts
        post_file (str): Path to a file containing post text
        caption_text (str): Direct caption text
        data_dir (str): Directory containing post data
        
    Returns:
        str: The post text
    """
    # Use direct caption text if provided
    if caption_text:
        logging.info("Using provided caption text")
        return caption_text
    
    # Use post file if provided
    if post_file and os.path.exists(post_file):
        try:
            with open(post_file, 'r', encoding='utf-8') as f:
                text = f.read().strip()
                logging.info(f"Loaded text from {post_file}: {text[:50]}...")
                return text
        except Exception as e:
            logging.error(f"Error reading post file {post_file}: {e}")
    
    # Use JSON data if provided
    if post_json and post_id:
        try:
            # Find the post with the matching ID
            for post in post_json:
                if post.get("id") == post_id:
                    text = post.get("post_text", "")
                    logging.info(f"Using text from post {post_id} in JSON data")
                    return text
        except Exception as e:
            logging.error(f"Error extracting text from JSON: {e}")
    
    # Look for post files in the data directory
    if data_dir and post_id and os.path.isdir(data_dir):
        try:
            # Try different file patterns
            patterns = [
                f"{post_id}_*.txt",
                f"post_{post_id}.txt",
                f"post{post_id}.txt"
            ]
            
            for pattern in patterns:
                matching_files = glob.glob(os.path.join(data_dir, pattern))
                if matching_files:
                    with open(matching_files[0], 'r', encoding='utf-8') as f:
                        text = f.read().strip()
                        logging.info(f"Loaded text from {matching_files[0]}")
                        return text
        except Exception as e:
            logging.error(f"Error finding post file in data directory: {e}")
    
    logging.warning("No post text found from any source")
    return None

def find_font(font_name):
    """
    Find a font file by name, checking common system font locations.
    
    Args:
        font_name (str): Name of the font to find (with or without extension)
        
    Returns:
        str: Path to the font file or None if not found
    """
    logging.debug(f"Searching for font: {font_name}")
    
    # First check if the font_name is already a path to a file
    if os.path.isfile(font_name):
        logging.debug(f"Font is a direct file path: {font_name}")
        return font_name
    
    # Check with and without .ttf extension
    font_name_base = font_name.lower().replace('.ttf', '')
    
    # Common font locations
    font_locations = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts'),  # Local fonts folder
        os.path.expanduser('~/Library/Fonts'),  # macOS user fonts
        '/Library/Fonts',  # macOS system fonts
        '/System/Library/Fonts',  # macOS system fonts
        os.path.expanduser('~/.fonts'),  # Linux user fonts
        '/usr/share/fonts',  # Linux system fonts
        os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts')  # Windows fonts
    ]
    
    # Font name variations to try
    variations = [
        f"{font_name_base}.ttf",
        f"{font_name_base}.TTF",
        f"{font_name_base}.otf",
        f"{font_name_base}.OTF",
        f"{font_name_base}",
        # For fonts with spaces or special characters that might be in the filename
        f"{font_name_base.replace(' ', '')}.ttf",
        f"{font_name_base.replace(' ', '-')}.ttf",
        f"{font_name_base.replace(' ', '_')}.ttf"
    ]
    
    for location in font_locations:
        if not os.path.exists(location):
            continue
            
        for variation in variations:
            # Check direct match
            path = os.path.join(location, variation)
            if os.path.isfile(path):
                logging.debug(f"Found font at: {path}")
                return path
                
            # Check in subdirectories for Linux/Windows systems
            if os.path.isdir(location):
                for root, dirs, files in os.walk(location):
                    for file in files:
                        if file.lower() == variation.lower():
                            path = os.path.join(root, file)
                            logging.debug(f"Found font at: {path}")
                            return path
                            
                        # For macOS/Windows where fonts might have spaces
                        if font_name_base.lower() in file.lower() and (file.lower().endswith('.ttf') or file.lower().endswith('.otf')):
                            path = os.path.join(root, file)
                            logging.debug(f"Found font match at: {path}")
                            return path
    
    logging.warning(f"Font not found: {font_name}")
    # Return a default system font that should be available everywhere
    default_font = None
    for location in font_locations:
        for default in ['Arial.ttf', 'DejaVuSans.ttf', 'Helvetica.ttf', 'LiberationSans-Regular.ttf']:
            path = os.path.join(location, default)
            if os.path.isfile(path):
                logging.debug(f"Using default font: {path}")
                return path
                
    return None

def add_template(clip, template_path=None, template_audio_path=None):
    """
    Add a template image and audio as the final segment of the video.
    
    Args:
        clip (VideoClip): The main video clip
        template_path (str): Path to the template image file
        template_audio_path (str): Path to the template audio file
        
    Returns:
        VideoClip: The video clip with the template appended
    """
    if not template_path or not os.path.exists(template_path):
        logging.debug("No template specified or template not found, returning original clip")
        return clip
        
    logging.info(f"Adding template from {template_path}")
    try:
        # Load template image
        template_img = ImageClip(template_path)
        
        # Determine template duration based on audio or default
        template_duration = 3.0  # Default duration if no audio
        template_audio = None
        
        if template_audio_path and os.path.exists(template_audio_path):
            logging.info(f"Using template audio: {template_audio_path}")
            template_audio = AudioFileClip(template_audio_path)
            template_duration = template_audio.duration
            
        # Set template duration
        template_clip = template_img.set_duration(template_duration)
        
        # Add audio to template if available
        if template_audio:
            template_clip = template_clip.set_audio(template_audio)
        
        # Concatenate original clip and template
        final = concatenate_videoclips([clip, template_clip])
        
        return final
    except Exception as e:
        logging.error(f"Error adding template: {e}")
        traceback.print_exc()
        return clip

def batch_create_videos(directory, font_name="BebasNeue-Regular", font_size=70, color="white", 
                       stroke_width=3, stroke_color="black", caption_chunk_size=5, animate=True,
                       word_by_word=True, bg_color=None, save_debug_images=False, debug_path=None,
                       simple_mode=False, output_directory=None, timestamp=None, no_captions=False,
                       template_path=None, template_audio_path=None, target_width=1080, target_height=1920,
                       resize_mode=False):
    """
    Process multiple posts in batch from a directory.
    
    Args:
        directory: Directory containing the posts
        font_name: Name of the font to use for captions
        font_size: Font size for captions
        color: Text color for captions
        stroke_width: Width of text stroke
        stroke_color: Color of text stroke
        caption_chunk_size: Number of words per caption chunk
        animate: Whether to animate captions
        word_by_word: Whether to use word-by-word captioning
        bg_color: Background color for captions
        save_debug_images: Whether to save debug images
        debug_path: Path to save debug images
        simple_mode: Use simple mode (image + audio only)
        output_directory: Directory to save the output videos
        timestamp: Custom timestamp for output filenames
        no_captions: Skip caption generation
        template_path: Path to template image to show at end of video
        template_audio_path: Path to template audio to play with the template image
        target_width: Target width for the video
        target_height: Target height for the video
        resize_mode: If True, keep aspect ratio by resizing instead of cropping
    """
    logging.info(f"Processing directory in batch mode: {directory}")
    
    if simple_mode:
        logging.info("Running in simple mode - no captions will be added to videos")
    
    if no_captions:
        logging.info("Running with no captions - captions will be explicitly disabled")
    
    if template_path:
        logging.info(f"Using template image: {template_path}")
    
    if template_audio_path:
        logging.info(f"Using template audio: {template_audio_path}")
    
    logging.info(f"Target video dimensions: {target_width}x{target_height}")
    logging.info(f"*** Resize mode: {resize_mode}")
    
    if not os.path.isdir(directory):
        logging.error(f"Directory does not exist: {directory}")
        return []
    
    # Get current timestamp if not provided
    if timestamp is None:
        import time
        timestamp = time.strftime("%Y%m%d_%H%M%S")
    else:
        # Make sure timestamp doesn't have path separators
        timestamp = os.path.basename(timestamp)
    
    # Detect directory structure type
    # Check if directory has the new structure format
    posts_dir = os.path.join(directory, "posts")
    voiceovers_dir = os.path.join(directory, "voiceovers")
    images_dir = os.path.join(directory, "images")
    
    is_new_structure = (os.path.isdir(posts_dir) and 
                        os.path.isdir(voiceovers_dir) and 
                        os.path.isdir(images_dir))
    
    logging.info(f"Directory structure type: {'new' if is_new_structure else 'traditional'}")
    
    # Create the reel subdirectory directly within the input directory
    reel_dir = os.path.join(directory, "reel")
    
    try:
        os.makedirs(reel_dir, exist_ok=True)
        logging.info(f"Created reel directory: {reel_dir}")
    except Exception as e:
        logging.error(f"Failed to create reel directory: {e}")
        reel_dir = directory  # Fallback to main directory if we can't create reel subdirectory
    
    # Setup debug directory if needed
    if save_debug_images:
        if not debug_path:
            debug_path = os.path.join(directory, "debug")
        try:
            os.makedirs(debug_path, exist_ok=True)
        except Exception as e:
            logging.error(f"Failed to create debug directory: {e}")
            save_debug_images = False  # Disable debug images if we can't create the directory
    
    created_videos = []
    
    if is_new_structure:
        # Process using the new structure format
        logging.info("Using new directory structure format")
        
        # Find the JSON file with posts
        json_files = glob.glob(os.path.join(posts_dir, "*.json"))
        if not json_files:
            logging.error("No JSON files found in posts directory")
            return []
        
        # Use the first JSON file found
        posts_json_path = json_files[0]
        logging.info(f"Using posts from: {posts_json_path}")
        
        # Load posts from JSON
        try:
            with open(posts_json_path, 'r', encoding='utf-8') as f:
                posts_data = json.load(f)
                if isinstance(posts_data, dict) and 'posts' in posts_data:
                    posts = posts_data['posts']
                elif isinstance(posts_data, list):
                    posts = posts_data
                else:
                    logging.error("Invalid JSON format: expected list or dict with 'posts' key")
                    return []
        except Exception as e:
            logging.error(f"Failed to load posts from JSON: {e}")
            return []
        
        # Find the voiceovers directory
        voiceovers_subdirs = [d for d in os.listdir(voiceovers_dir) 
                             if os.path.isdir(os.path.join(voiceovers_dir, d))]
        
        if not voiceovers_subdirs:
            logging.error("No voiceovers subdirectories found")
            return []
        
        # Get the first voiceovers subdir (likely f1_posts)
        voiceovers_subdir = os.path.join(voiceovers_dir, voiceovers_subdirs[0], "voiceovers")
        if not os.path.exists(voiceovers_subdir):
            logging.error(f"Voiceovers directory not found: {voiceovers_subdir}")
            return []
        
        # Get image directories - each directory represents a post
        image_dirs = [d for d in os.listdir(images_dir) 
                     if os.path.isdir(os.path.join(images_dir, d)) and not d.startswith('.')]
        
        if not image_dirs:
            logging.error("No image directories found")
            return []
        
        logging.info(f"Found {len(image_dirs)} image directories")
        
        # Get audio files in voiceovers directory
        audio_files = []
        for ext in ["*.mp3", "*.wav", "*.m4a"]:
            audio_files.extend(glob.glob(os.path.join(voiceovers_subdir, ext)))
        
        # Load the summary.json file to get the mapping between post titles and audio files
        summary_path = os.path.join(voiceovers_subdir, "summary.json")
        title_to_audio = {}
        if os.path.exists(summary_path):
            try:
                with open(summary_path, 'r') as f:
                    summary_data = json.load(f)
                    title_to_audio = {title: path for title, path in summary_data.items()}
                logging.info(f"Loaded audio file mappings from {summary_path}")
            except Exception as e:
                logging.error(f"Error loading summary.json: {e}")
        
        # Process each post
        for post_idx, post_dir in enumerate(image_dirs, 1):
            try:
                # Extract post name from directory
                post_id = post_dir
                logging.info(f"Processing post {post_idx}: {post_id}")
                
                # Get images for this post
                post_images_dir = os.path.join(images_dir, post_dir)
                image_files = []
                for ext in ["*.png", "*.jpg", "*.jpeg"]:
                    image_files.extend(glob.glob(os.path.join(post_images_dir, ext)))
                
                # Sort images by numeric prefix
                image_files.sort(key=lambda x: int(os.path.basename(x).split('_')[0]) if os.path.basename(x).split('_')[0].isdigit() else 9999)
                
                if not image_files:
                    logging.warning(f"No images found for post {post_id}, skipping")
                    continue
                
                # Find corresponding audio file using semantic matching
                audio_path = None
                sanitized_post_id = post_id.replace('_', ' ')
                
                # First try to find an exact match in the summary.json mapping
                for title, path in title_to_audio.items():
                    if sanitized_post_id.lower() == title.lower():
                        audio_path = path
                        break
                
                # If no exact match, try partial matching
                if not audio_path:
                    for title, path in title_to_audio.items():
                        if sanitized_post_id.lower() in title.lower() or title.lower() in sanitized_post_id.lower():
                            audio_path = path
                            break
                
                # If still no match, try to find the audio file by index as fallback
                if not audio_path and post_idx <= len(audio_files):
                    audio_path = audio_files[post_idx-1]
                
                if not audio_path or not os.path.exists(audio_path):
                    logging.warning(f"No audio file found for post {post_id}, video will have no audio")
                
                # Find post text in JSON
                post_text = None
                
                # Try to match post title with directory name
                for post in posts:
                    post_title = post.get('title', '')
                    if sanitized_post_id.lower() in post_title.lower() or post_title.lower() in sanitized_post_id.lower():
                        post_text = post.get('post_text', '')
                        break
                
                if not post_text:
                    logging.warning(f"No post text found for {post_id}, using post index {post_idx}")
                    # Just use the post at the same index
                    if post_idx <= len(posts):
                        post_text = posts[post_idx-1].get('post_text', '')
                
                # Create a temporary text file for the post content
                post_file = None
                if post_text:
                    try:
                        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
                            f.write(post_text)
                            post_file = f.name
                    except Exception as e:
                        logging.error(f"Error creating temporary post file: {e}")
                
                # Create a formatted filename with timestamp and post details
                # Format: TIMESTAMP_postX_PostName_reel.mp4
                sanitized_post_id = post_dir.replace(' ', '_').replace('-', '_')
                output_filename = f"{timestamp}_post{post_idx}_{sanitized_post_id}_reel.mp4"
                output_path = os.path.join(reel_dir, output_filename)
                
                # Create individual debug path if needed
                post_debug_path = None
                if save_debug_images and debug_path:
                    post_debug_path = os.path.join(debug_path, post_id)
                    try:
                        os.makedirs(post_debug_path, exist_ok=True)
                    except Exception as e:
                        logging.warning(f"Could not create debug path for post {post_id}: {e}")
                        post_debug_path = None
                
                # Use a much simpler approach in simple mode to guarantee success
                if simple_mode and audio_path:
                    try:
                        # Use the first image
                        image_path = image_files[0]
                        
                        logging.info(f"Simple mode: Creating video from image {image_path} and audio {audio_path}")
                        
                        # Create the image clip
                        img_clip = ImageClip(image_path)
                        
                        # Get original dimensions
                        original_width, original_height = img_clip.size
                        
                        # Calculate target aspect ratio (9:16)
                        target_ratio = 9/16
                        
                        # Calculate current aspect ratio
                        current_ratio = original_width / original_height
                        
                        if resize_mode:
                            # Preserve aspect ratio by resizing, not cropping
                            if current_ratio > target_ratio:
                                # Image is wider than target ratio, constrain to target width
                                new_width = target_width
                                new_height = int(new_width / current_ratio)
                                img_clip = img_clip.resize((new_width, new_height))
                            else:
                                # Image is taller than target ratio, match height to target height
                                # but keep width proportional to maintain aspect ratio
                                new_height = target_height
                                new_width = int(new_height * current_ratio)
                                img_clip = img_clip.resize((new_width, new_height))
                        else:
                            # Original cropping behavior
                            if current_ratio > target_ratio:
                                # Image is too wide - crop sides
                                new_width = int(original_height * target_ratio)
                                x_offset = (original_width - new_width) // 2
                                img_clip = img_clip.crop(x1=x_offset, x2=x_offset + new_width)
                            else:
                                # Image is too tall - crop top and bottom
                                new_height = int(original_width / target_ratio)
                                y_offset = (original_height - new_height) // 2
                                img_clip = img_clip.crop(y1=y_offset, y2=y_offset + new_height)
                            
                            # Resize to target dimensions after cropping
                            img_clip = img_clip.resize((target_width, target_height))
                        
                        # Now resize to target dimensions
                        img_clip = img_clip.resize((target_width, target_height))
                        
                        # Create a background of target size
                        bg_clip = ColorClip(size=(target_width, target_height), color=(0, 0, 0))
                        bg_clip = bg_clip.set_duration(1)  # Duration will be set properly later
                        
                        # Center the image on the background
                        x_pos = (target_width - img_clip.size[0]) // 2
                        y_pos = (target_height - img_clip.size[1]) // 2
                        
                        img_clip = img_clip.set_position((x_pos, y_pos))
                        
                        # Load audio
                        audio_clip = AudioFileClip(audio_path)
                        audio_duration = audio_clip.duration
                        logging.info(f"Audio duration: {audio_duration:.2f} seconds")
                        
                        # Set duration of clips
                        bg_clip = bg_clip.set_duration(audio_duration)
                        img_clip = img_clip.set_duration(audio_duration)
                        
                        # Composite the image on the background
                        video = CompositeVideoClip([bg_clip, img_clip])
                        
                        # Set audio on the video
                        video = video.set_audio(audio_clip)
                        
                        # Add template if provided
                        if template_path:
                            video = add_template(video, template_path, template_audio_path)
                        
                        # Write video file
                        logging.info(f"Writing video to {output_path}")
                        video.write_videofile(
                            output_path,
                            codec='libx264',
                            audio_codec='aac',
                            fps=24
                        )
                        
                        logging.info(f"Video created successfully: {output_path}")
                        created_videos.append(output_path)
                        
                        # Clean up the temporary post file
                        if post_file and os.path.exists(post_file):
                            try:
                                os.unlink(post_file)
                            except:
                                pass
                            
                        continue  # Skip the complex method below
                    
                    except Exception as e:
                        logging.error(f"Error in simple mode: {e}")
                        # Continue to the normal processing method as fallback
                
                # Create the video with the complex method
                output_file = create_video(
                    images=image_files,
                    audio_path=audio_path,
                    output_path=output_path,
                    font_name=font_name,
                    font_size=font_size,
                    color=color,
                    stroke_width=stroke_width,
                    stroke_color=stroke_color,
                    caption_chunk_size=caption_chunk_size,
                    animate=animate,
                    post_id=post_id,
                    post_file=None if (simple_mode or no_captions) else post_file,  # Skip captions in simple mode or no_captions mode
                    caption_text=post_text if simple_mode else None,
                    word_by_word=word_by_word,
                    bg_color=bg_color,
                    save_debug_images=save_debug_images,
                    debug_path=post_debug_path,
                    no_captions=no_captions,
                    template_path=template_path,
                    template_audio_path=template_audio_path,
                    target_width=target_width,
                    target_height=target_height,
                    resize_mode=resize_mode
                )
                
                # Clean up the temporary post file
                if post_file and os.path.exists(post_file):
                    try:
                        os.unlink(post_file)
                    except:
                        pass
                
                if output_file:
                    logging.info(f"Successfully created video for post {post_id}: {output_file}")
                    created_videos.append(output_file)
                else:
                    logging.error(f"Failed to create video for post {post_id}")
                
            except Exception as e:
                logging.error(f"Error processing post directory {post_dir}: {e}")
                traceback.print_exc()
                # Continue with next post
    
    else:
        # Process using the traditional structure format
        logging.info("Using traditional directory structure format")
        
        # Get all subdirectories (each representing a post)
        try:
            post_dirs = [os.path.join(directory, d) for d in os.listdir(directory) 
                        if os.path.isdir(os.path.join(directory, d)) and not d.startswith('.') and d not in ['reel', 'debug']]
        except Exception as e:
            logging.error(f"Error listing directory contents: {e}")
            return []
        
        if not post_dirs:
            logging.error(f"No post directories found in: {directory}")
            return []
        
        logging.info(f"Found {len(post_dirs)} post directories to process")
    
        # Process each post directory
        for post_idx, post_dir in enumerate(post_dirs, 1):
            try:
                post_id = os.path.basename(post_dir)
                logging.info(f"Processing post {post_id} ({post_idx}/{len(post_dirs)})")
                
                # Check for images directory
                images_dir = os.path.join(post_dir, "images")
                if not os.path.isdir(images_dir):
                    # Try alternate names
                    for alt_dir in ["img", "image", "frames", "screenshots"]:
                        alt_path = os.path.join(post_dir, alt_dir)
                        if os.path.isdir(alt_path):
                            images_dir = alt_path
                            break
                    else:  # No directory found
                        logging.warning(f"No images directory found for post {post_id}, skipping")
                        continue
                
                # Look for audio file
                audio_path = None
                for audio_file in ["audio.wav", "audio.mp3", "audio.m4a", "voiceover.wav", "voiceover.mp3", "voice.wav", "voice.mp3"]:
                    path = os.path.join(post_dir, audio_file)
                    if os.path.exists(path):
                        audio_path = path
                        break
                
                if not audio_path:
                    logging.warning(f"No audio file found for post {post_id}, video will have no audio")
                
                # Look for post text file
                post_file = None
                for text_file in ["post.txt", "caption.txt", "text.txt", "script.txt", "captions.txt"]:
                    path = os.path.join(post_dir, text_file)
                    if os.path.exists(path):
                        post_file = path
                        break
                
                if not post_file:
                    logging.warning(f"No post text file found for post {post_id}, video will have no captions")
                
                # Create a formatted filename with timestamp and post details
                # Format: TIMESTAMP_postX_PostName_reel.mp4
                sanitized_post_id = post_id.replace(' ', '_').replace('-', '_')
                output_filename = f"{timestamp}_post{post_idx}_{sanitized_post_id}_reel.mp4"
                output_path = os.path.join(reel_dir, output_filename)
                
                # Create individual debug path if needed
                post_debug_path = None
                if save_debug_images and debug_path:
                    post_debug_path = os.path.join(debug_path, post_id)
                    try:
                        os.makedirs(post_debug_path, exist_ok=True)
                    except Exception as e:
                        logging.warning(f"Could not create debug path for post {post_id}: {e}")
                        post_debug_path = None
                
                # Use a much simpler approach in simple mode to guarantee success
                if simple_mode and audio_path:
                    try:
                        # Find the first image in the directory
                        image_files = []
                        for ext in ['*.jpg', '*.jpeg', '*.png', '*.gif']:
                            pattern = os.path.join(images_dir, ext)
                            image_files.extend(glob.glob(pattern))
                        
                        if not image_files:
                            logging.error(f"No image files found in {images_dir}")
                            continue
                        
                        # Sort and use the first image (most important one)
                        image_files = sorted(image_files)
                        image_path = image_files[0]
                        
                        logging.info(f"Simple mode: Creating video from image {image_path} and audio {audio_path}")
                        
                        # Create the image clip
                        img_clip = ImageClip(image_path)
                        
                        # Get original dimensions
                        original_width, original_height = img_clip.size
                        
                        # Calculate target aspect ratio (9:16)
                        target_ratio = 9/16
                        
                        # Calculate current aspect ratio
                        current_ratio = original_width / original_height
                        
                        if resize_mode:
                            # Preserve aspect ratio by resizing, not cropping
                            if current_ratio > target_ratio:
                                # Image is wider than target ratio, constrain to target width
                                new_width = target_width
                                new_height = int(new_width / current_ratio)
                                img_clip = img_clip.resize((new_width, new_height))
                            else:
                                # Image is taller than target ratio, match height to target height
                                # but keep width proportional to maintain aspect ratio
                                new_height = target_height
                                new_width = int(new_height * current_ratio)
                                img_clip = img_clip.resize((new_width, new_height))
                        else:
                            # Original cropping behavior
                            if current_ratio > target_ratio:
                                # Image is too wide - crop sides
                                new_width = int(original_height * target_ratio)
                                x_offset = (original_width - new_width) // 2
                                img_clip = img_clip.crop(x1=x_offset, x2=x_offset + new_width)
                            else:
                                # Image is too tall - crop top and bottom
                                new_height = int(original_width / target_ratio)
                                y_offset = (original_height - new_height) // 2
                                img_clip = img_clip.crop(y1=y_offset, y2=y_offset + new_height)
                            
                            # Resize to target dimensions after cropping
                            img_clip = img_clip.resize((target_width, target_height))
                        
                        # Now resize to target dimensions
                        img_clip = img_clip.resize((target_width, target_height))
                        
                        # Create a background of target size
                        bg_clip = ColorClip(size=(target_width, target_height), color=(0, 0, 0))
                        bg_clip = bg_clip.set_duration(1)  # Duration will be set properly later
                        
                        # Center the image on the background
                        x_pos = (target_width - img_clip.size[0]) // 2
                        y_pos = (target_height - img_clip.size[1]) // 2
                        
                        img_clip = img_clip.set_position((x_pos, y_pos))
                        
                        # Load audio
                        audio_clip = AudioFileClip(audio_path)
                        audio_duration = audio_clip.duration
                        logging.info(f"Audio duration: {audio_duration:.2f} seconds")
                        
                        # Set duration of clips
                        bg_clip = bg_clip.set_duration(audio_duration)
                        img_clip = img_clip.set_duration(audio_duration)
                        
                        # Composite the image on the background
                        video = CompositeVideoClip([bg_clip, img_clip])
                        
                        # Set audio on the video
                        video = video.set_audio(audio_clip)
                        
                        # Add template if provided
                        if template_path:
                            video = add_template(video, template_path, template_audio_path)
                        
                        # Write video file
                        logging.info(f"Writing video to {output_path}")
                        video.write_videofile(
                            output_path,
                            codec='libx264',
                            audio_codec='aac',
                            fps=24
                        )
                        
                        logging.info(f"Video created successfully: {output_path}")
                        created_videos.append(output_path)
                        continue  # Skip the complex method below
                    
                    except Exception as e:
                        logging.error(f"Error in simple mode: {e}")
                        # Continue to the normal processing method as fallback
                
                # Create the video with the complex method
                output_file = create_video(
                    images=images_dir,
                    audio_path=audio_path,
                    output_path=output_path,
                    font_name=font_name,
                    font_size=font_size,
                    color=color,
                    stroke_width=stroke_width,
                    stroke_color=stroke_color,
                    caption_chunk_size=caption_chunk_size,
                    animate=animate,
                    post_id=post_id,
                    post_file=None if (simple_mode or no_captions) else post_file,  # Skip captions in simple mode or no_captions mode
                    data_dir=post_dir,
                    word_by_word=word_by_word,
                    bg_color=bg_color,
                    save_debug_images=save_debug_images,
                    debug_path=post_debug_path,
                    no_captions=no_captions,
                    template_path=template_path,
                    template_audio_path=template_audio_path,
                    target_width=target_width,
                    target_height=target_height,
                    resize_mode=resize_mode
                )
                
                if output_file:
                    logging.info(f"Successfully created video for post {post_id}: {output_file}")
                    created_videos.append(output_file)
                else:
                    logging.error(f"Failed to create video for post {post_id}")
                
            except Exception as e:
                logging.error(f"Error processing post directory {post_dir}: {e}")
                traceback.print_exc()
                # Continue with next post
    
    successful_count = len(created_videos)
    total_posts = len(image_dirs) if is_new_structure else len(post_dirs)
    logging.info(f"Batch processing complete. Created {successful_count} of {total_posts} videos.")
    
    if successful_count > 0:
        logging.info(f"Videos saved to: {reel_dir}")
    
    return created_videos

def create_video(images, audio_path=None, output_path=None, caption_text=None, font_name="Arial", font_size=70, color="white", 
                stroke_width=3, stroke_color="black", image_duration=2.0, padding=10, caption_chunk_size=5, animate=True,
                post_id=None, post_json=None, post_file=None, data_dir=None, debug_path=None, bg_color=None, 
                word_by_word=True, save_debug_images=False, no_captions=False, template_path=None, template_audio_path=None,
                target_width=1080, target_height=1920, resize_mode=False):
    """
    Create a video from a series of images with captions and audio.
    
    Args:
        images: List of image paths or a directory containing images
        audio_path: Path to an audio file (optional)
        output_path: Path to save the output video
        caption_text: Text to display as captions (optional)
        font_name: Name of the font to use for captions
        font_size: Font size for captions
        color: Text color for captions
        stroke_width: Width of text stroke
        stroke_color: Color of text stroke
        image_duration: Duration for each image in seconds
        padding: Padding around images
        caption_chunk_size: Number of words per caption chunk
        animate: Whether to animate captions
        post_id: ID of the post (for batch processing)
        post_json: JSON data for the post (for batch processing)
        post_file: Path to a file containing post text (for batch processing)
        data_dir: Path to the data directory (for batch processing)
        debug_path: Path to save debug images
        bg_color: Background color for captions
        word_by_word: Whether to use word-by-word captioning (default: True)
        save_debug_images: Whether to save debug images
        no_captions: If True, explicitly skip caption generation
        template_path: Path to template image to show at the end
        template_audio_path: Path to template audio to play at the end
        target_width: Target width for the video (default: 1080 for Instagram)
        target_height: Target height for the video (default: 1920 for Instagram)
        resize_mode: If True, keep aspect ratio by resizing instead of cropping
        
    Returns:
        str: Path to the output video file
    """
    # Debug settings
    logging.info("=== VIDEO CREATION PARAMETERS ===")
    logging.info(f"*** Word-by-word mode: {word_by_word}")
    logging.info(f"*** Audio path: {audio_path}")
    logging.info(f"*** Font: {font_name}")
    logging.info(f"*** Stroke width: {stroke_width}")
    logging.info(f"*** Output path: {output_path}")
    logging.info(f"*** No captions mode: {no_captions}")
    logging.info(f"*** Target dimensions: {target_width}x{target_height}")
    logging.info(f"*** Resize mode: {resize_mode}")
    if template_path:
        logging.info(f"*** Template image: {template_path}")
    if template_audio_path:
        logging.info(f"*** Template audio: {template_audio_path}")
    
    # Get project root directory
    project_root = os.path.dirname(os.path.abspath(__file__))
    
    # Handle paths properly
    def resolve_path(path):
        """Resolve a path to absolute, handling relative paths correctly"""
        if path and not os.path.isabs(path):
            # Check if it's relative to current directory
            if os.path.exists(path):
                return os.path.abspath(path)
            # Or relative to project root
            project_relative = os.path.join(project_root, path)
            if os.path.exists(project_relative):
                return project_relative
        return path  # Return as is if it's absolute or doesn't exist
    
    # Make full paths absolute
    if audio_path:
        audio_path = resolve_path(audio_path)
        logging.info(f"*** Using audio: {audio_path}")
        if not os.path.exists(audio_path):
            logging.warning(f"*** WARNING: Audio file does not exist: {audio_path}")
    else:
        logging.warning("*** WARNING: No audio path provided - cannot use word-by-word timing with Whisper")

    if output_path:
        # For output path, we want to resolve the directory part
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.isabs(output_dir):
            # Make the directory part absolute
            project_relative_dir = os.path.join(project_root, output_dir)
            if not os.path.exists(project_relative_dir):
                try:
                    os.makedirs(project_relative_dir, exist_ok=True)
                except Exception as e:
                    logging.warning(f"Could not create output directory: {e}")
            output_path = os.path.join(project_relative_dir, os.path.basename(output_path))
        output_path = os.path.abspath(output_path)
        logging.info(f"*** Output will be saved to: {output_path}")
        
    if post_file:
        post_file = resolve_path(post_file)
        
    if template_path:
        template_path = resolve_path(template_path)
        if not os.path.exists(template_path):
            logging.warning(f"*** WARNING: Template image does not exist: {template_path}")
            template_path = None
            
    if template_audio_path:
        template_audio_path = resolve_path(template_audio_path)
        if not os.path.exists(template_audio_path):
            logging.warning(f"*** WARNING: Template audio does not exist: {template_audio_path}")
            template_audio_path = None

    # Get post text from various sources
    post_text = get_post_text(post_id, post_json, post_file, caption_text, data_dir)
    
    if not post_text:
        logging.warning("No caption text found, creating video without captions")
    else:
        logging.info(f"*** Caption text: {post_text[:100]}...")
    
    # Set target video dimensions to Instagram format
    size = (target_width, target_height)
    logging.info(f"Target video dimensions: {size}")
    
    # Setup debug dirs
    if save_debug_images and debug_path:
        debug_path = resolve_path(debug_path)
        os.makedirs(debug_path, exist_ok=True)
    
    # Load and process images
    video_clips = []
    
    # Check if images is a directory or a list
    if isinstance(images, str) and os.path.isdir(resolve_path(images)):
        # Get all images in the directory
        image_files = []
        images_path = resolve_path(images)
        for ext in ['*.jpg', '*.jpeg', '*.png', '*.gif']:
            pattern = os.path.join(images_path, ext)
            image_files.extend(glob.glob(pattern))
        
        # Sort alphabetically
        image_files = sorted(image_files)
        
        if not image_files:
            logging.error(f"No images found in directory: {images}")
            return None
        
        images = image_files
    
    # Ensure images is a list
    if not isinstance(images, list):
        images = [images]
    
    # Resolve image paths if they're relative
    images = [resolve_path(img) for img in images]
    
    logging.info(f"Processing {len(images)} images")
    
    # Loop through images and create clips
    for img_path in images:
        try:
            # Create image clip
            img_clip = ImageClip(img_path)
            
            # Get original dimensions
            original_width, original_height = img_clip.size
            
            # Calculate target aspect ratio (9:16)
            target_ratio = target_width / target_height
            
            # Calculate current aspect ratio
            current_ratio = original_width / original_height
            
            if resize_mode:
                # Preserve aspect ratio by resizing, not cropping
                if current_ratio > target_ratio:
                    # Image is wider than target ratio, constrain to target width
                    new_width = target_width
                    new_height = int(new_width / current_ratio)
                    img_clip = img_clip.resize((new_width, new_height))
                else:
                    # Image is taller than target ratio, match height to target height
                    # but keep width proportional to maintain aspect ratio
                    new_height = target_height
                    new_width = int(new_height * current_ratio)
                    img_clip = img_clip.resize((new_width, new_height))
            else:
                # Original cropping behavior
                if current_ratio > target_ratio:
                    # Image is too wide - crop sides
                    new_width = int(original_height * target_ratio)
                    x_offset = (original_width - new_width) // 2
                    img_clip = img_clip.crop(x1=x_offset, x2=x_offset + new_width)
                else:
                    # Image is too tall - crop top and bottom
                    new_height = int(original_width / target_ratio)
                    y_offset = (original_height - new_height) // 2
                    img_clip = img_clip.crop(y1=y_offset, y2=y_offset + new_height)
                
                # Resize to target dimensions after cropping
                img_clip = img_clip.resize((target_width, target_height))
            
            # Create a background of target size
            bg_clip = ColorClip(size=(target_width, target_height), color=(0, 0, 0))
            bg_clip = bg_clip.set_duration(1)  # Duration will be set properly later
            
            # Center the image on the background
            x_pos = (target_width - img_clip.size[0]) // 2
            y_pos = (target_height - img_clip.size[1]) // 2
            
            img_clip = img_clip.set_position((x_pos, y_pos))
            
            # Composite the image on the background
            composite_clip = CompositeVideoClip([bg_clip, img_clip])
            
            # Don't set duration yet - we'll calculate it based on total number of images and audio duration
            video_clips.append(composite_clip)
            
        except Exception as e:
            logging.error(f"Error processing image {img_path}: {e}")
    
    if not video_clips:
        logging.error("No valid image clips to process")
        return None
        
    # Get the audio duration or use a default if no audio
    audio_duration = None
    if audio_path and os.path.exists(audio_path):
        try:
            audio_clip = AudioFileClip(audio_path)
            audio_duration = audio_clip.duration
            logging.info(f"Audio duration: {audio_duration:.2f} seconds")
        except Exception as e:
            logging.error(f"Error loading audio: {e}")
    
    # Calculate proper duration for each image
    if audio_duration:
        # Distribute time evenly among images
        image_durations = calculate_durations(audio_duration, len(video_clips))
        # Apply durations to clips
        for i, clip in enumerate(video_clips):
            video_clips[i] = clip.set_duration(image_durations[i])
    else:
        # Use default duration if no audio
        for i, clip in enumerate(video_clips):
            video_clips[i] = clip.set_duration(image_duration)
    
    # Create the final video from the image clips
    video = concatenate_videoclips(video_clips)
    
    # Initialize duration with video duration as fallback
    duration = video.duration
    
    # Load audio if provided
    audio_clip = None
    if audio_path and os.path.exists(audio_path):
        try:
            audio_clip = AudioFileClip(audio_path)
            duration = audio_clip.duration
            
            # Set audio on the video
            video = video.set_audio(audio_clip)
            
        except Exception as e:
            logging.error(f"Error loading audio: {e}")
    else:
        # Use video duration if no audio
        logging.info(f"No audio provided, using video duration: {duration:.2f} seconds")
    
    # Create captions if text is provided and captions are not disabled
    caption_clips = []
    if post_text and not no_captions:
        try:
            logging.info("Creating captions...")
            # Create path for debug captions
            if save_debug_images:
                debug_caption_path = debug_path
            else:
                debug_caption_path = None
            
            # Check if font file exists
            font_file = find_font(font_name)
            
            if not font_file:
                logging.warning(f"Font '{font_name}' not found. Using system default.")
            else:
                logging.info(f"Using font: {font_name}")
                
            # Create captions with word-by-word animation if specified
            if word_by_word:
                logging.info("*** Creating word-by-word captions (each word appears individually)")
                # Check if audio file exists
                if audio_path and os.path.exists(audio_path):
                    logging.info(f"*** Using audio file for precise timing: {audio_path}")
                    try:
                        # Check if whisper is installed
                        try:
                            import whisper
                            logging.info("*** Whisper is installed for speech recognition")
                        except ImportError:
                            logging.warning("*** IMPORTANT: Whisper is not installed! Cannot use precise word timing.")
                            logging.warning("*** Install whisper with: pip install -U openai-whisper")
                    except Exception as e:
                        logging.error(f"*** Error checking for whisper: {e}")
                        
                    caption_clips = create_timed_captions(
                        post_text, font_name, font_size, color, stroke_width, stroke_color,
                        duration, size[0], size[1], bg_color, save_debug_images, debug_caption_path,
                        audio_file=audio_path
                    )
                else:
                    logging.warning("*** No audio file provided or file does not exist - using simple timing for word-by-word captions")
                    caption_clips = create_simple_timed_captions(
                        post_text, font_name, font_size, color, stroke_width, stroke_color,
                        duration, size[0], size[1], bg_color, save_debug_images, debug_caption_path
                    )
            else:
                logging.info("*** Creating traditional multi-word captions (chunks of text)")
                # Traditional style captions (multiple words at once)
                caption_clips = create_caption_clips(
                    post_text, font_name, font_size, color, stroke_width, stroke_color,
                    duration, size[0], size[1], caption_chunk_size, animate, bg_color
                )
            
            logging.info(f"Added {len(caption_clips)} caption clips")
            
            # Save debug caption images
            if save_debug_images and debug_caption_path:
                logging.info(f"Debug images saved to {debug_caption_path}")
        
        except Exception as e:
            logging.error(f"Error creating captions: {e}")
            traceback.print_exc()
    
    # Create final video with captions if available
    final = None
    if caption_clips:
        try:
            # Workaround for common MoviePy error with CompositeVideoClip
            # Instead of directly compositing all captions at once, we'll do it one by one
            
            # Start with the base video
            final = video.copy()
            
            # Add each caption clip individually
            for caption in caption_clips:
                try:
                    # Make sure the caption is set up correctly
                    if not hasattr(caption, 'duration') or caption.duration is None:
                        caption.duration = min(duration - caption.start, 0.5)  # Default to 0.5s if not set
                    
                    # Set duration of this specific overlay
                    overlay_duration = min(caption.duration, duration - caption.start)
                    if overlay_duration <= 0:
                        continue  # Skip captions that would start after the video ends
                    
                    # Create a temporary clip that only contains this caption
                    temp_clip = CompositeVideoClip([final.copy(), caption.set_duration(overlay_duration)], size=size)
                    temp_clip = temp_clip.set_start(caption.start).set_duration(overlay_duration)
                    
                    # Replace the corresponding segment in the final video
                    end_time = caption.start + overlay_duration
                    
                    # Create the pieces of the video
                    if caption.start > 0:
                        before_clip = final.subclip(0, caption.start)
                    else:
                        before_clip = None
                        
                    if end_time < duration:
                        after_clip = final.subclip(end_time, duration)
                    else:
                        after_clip = None
                    
                    # Reassemble the video with the new segment
                    clips_to_concat = []
                    if before_clip is not None:
                        clips_to_concat.append(before_clip)
                    clips_to_concat.append(temp_clip)
                    if after_clip is not None:
                        clips_to_concat.append(after_clip)
                    
                    if len(clips_to_concat) > 0:
                        final = concatenate_videoclips(clips_to_concat)
                    else:
                        final = temp_clip
                    
                    # Make sure audio is preserved
                    if video.audio is not None:
                        final = final.set_audio(video.audio)
                
                except Exception as e:
                    logging.error(f"Error compositing caption: {e}")
                    # Continue with the next caption
            
            # Ensure we have a final video even if all compositing failed
            if final is None:
                final = video
        
        except Exception as e:
            logging.error(f"Error compositing video with captions: {e}")
            final = video
    else:
        final = video
    
    # Explicitly set duration on the final composite
    final.duration = duration
    
    # Make sure audio has duration set
    if final.audio is not None:
        if not hasattr(final.audio, 'duration') or final.audio.duration is None:
            final.audio.duration = duration
    
    # Add final template/watermark if available
    if template_path:
        final = add_template(final, template_path, template_audio_path)
    
    # Write output
    if output_path:
        output_file = output_path
    else:
        output_file = "output.mp4"
    
    logging.info(f"Rendering video to {output_file}")
    print(f"Writing test video to {output_file}...")
    
    try:
        # Use a simpler approach for exporting to avoid potential errors
        final.write_videofile(
            output_file,
            codec='libx264',
            audio_codec='aac',
            fps=24,
            threads=2  # Limit threads to reduce complexity
        )
        
        print("Test complete!")
        return output_file
    except Exception as e:
        logging.error(f"Error writing video file: {e}")
        traceback.print_exc()
        
        # Try a fallback approach with just the base video
        try:
            logging.info("Trying fallback video rendering without captions")
            video.write_videofile(
                output_file,
                codec='libx264',
                audio_codec='aac', 
                fps=24
            )
            print("Fallback video created successfully (without captions)")
            return output_file
        except Exception as e2:
            logging.error(f"Fallback video rendering also failed: {e2}")
            return None

def main():
    """
    Main function to process command line arguments and create videos
    """
    parser = argparse.ArgumentParser(description='Create a video from images with captions.')
    parser.add_argument('--images', required=False, help='Path to the directory containing images or prefix of debug caption images')
    parser.add_argument('--output', required=False, help='Path to the output video file')
    parser.add_argument('--batch-directory', required=False, help='Process multiple posts in batch from this directory')
    parser.add_argument('--output-directory', required=False, help='Path to the output directory for batch processing (defaults to output/ in the project directory)')
    parser.add_argument('--font-name', default="BebasNeue-Regular", help='Font to use for captions')
    parser.add_argument('--font-size', type=int, default=70, help='Font size for captions')
    parser.add_argument('--color', default="white", help='Text color for captions')
    parser.add_argument('--stroke-width', type=int, default=3, help='Width of text stroke')
    parser.add_argument('--stroke-color', default="black", help='Color of text stroke')
    parser.add_argument('--bg-color', default=None, help='Background color for captions (e.g. black@0.5 for semi-transparent black)')
    parser.add_argument('--no-animate', action='store_true', help='Disable caption animation')
    parser.add_argument('--caption-chunk-size', type=int, default=5, help='Number of words per caption chunk')
    parser.add_argument('--audio', help='Path to the audio file')
    parser.add_argument('--post-file', help='Path to the post text file')
    parser.add_argument('--post-id', help='ID of the post')
    parser.add_argument('--json-file', help='Path to the JSON file containing post data')
    parser.add_argument('--caption-text', help='Direct caption text to use')
    parser.add_argument('--save-debug-images', action='store_true', help='Save debug images')
    parser.add_argument('--debug-path', help='Path to save debug images')
    parser.add_argument('--word-by-word', action='store_true', help='Use word-by-word captioning with Whisper')
    parser.add_argument('--simple-mode', action='store_true', help='Use simple mode for batch processing (image + audio only)')
    parser.add_argument('--no-captions', action='store_true', help='Create videos without captions while maintaining other processing')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--timestamp', help='Custom timestamp for output filenames (default: current time)')
    parser.add_argument('--template-image', default="/Users/xx/Documents/EB/Projects/PaddockPulse/Template/logo_IG.png", help='Path to the template image to show at end of video')
    parser.add_argument('--template-audio', default="/Users/xx/Documents/EB/Projects/PaddockPulse/Template/follow.mp3", help='Path to the template audio to play with the template image')
    parser.add_argument('--target-width', type=int, default=1080, help='Target width for the video (default: 1080 for Instagram)')
    parser.add_argument('--target-height', type=int, default=1920, help='Target height for the video (default: 1920 for Instagram)')
    parser.add_argument('--resize', action='store_true', help='Keep image aspect ratio by resizing instead of cropping')

    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=log_level, format='%(asctime)s - %(levelname)s - %(message)s')

    if args.debug:
        logging.debug("Debug logging enabled")
        logging.debug(f"Font: {args.font_name}, Size: {args.font_size}")
        logging.debug(f"Word-by-word mode: {args.word_by_word}")
        logging.debug(f"Target dimensions: {args.target_width}x{args.target_height}")
        logging.debug(f"Template image: {args.template_image}")
        logging.debug(f"Template audio: {args.template_audio}")

    # Check for batch mode
    if args.batch_directory:
        logging.info(f"Running in batch mode on directory: {args.batch_directory}")
        
        # Determine output directory
        output_directory = args.output_directory
        if not output_directory:
            # Default to the 'output' directory in the project root
            project_root = os.path.dirname(os.path.abspath(__file__))
            output_directory = os.path.join(project_root, "output")
            
            # Create a timestamped directory for this batch run
            import time
            timestamp = args.timestamp or time.strftime("%Y%m%d_%H%M%S")
            output_directory = os.path.join(output_directory, timestamp)
                
            logging.info(f"Using default output directory: {output_directory}")
        else:
            # Use the provided timestamp or get current time
            timestamp = args.timestamp or time.strftime("%Y%m%d_%H%M%S")
        
        # Pass all relevant arguments
        batch_create_videos(
            directory=args.batch_directory,
            font_name=args.font_name,
            font_size=args.font_size,
            color=args.color,
            stroke_width=args.stroke_width,
            stroke_color=args.stroke_color,
            caption_chunk_size=args.caption_chunk_size,
            animate=not args.no_animate,
            word_by_word=args.word_by_word,
            bg_color=args.bg_color,
            save_debug_images=args.save_debug_images,
            debug_path=args.debug_path,
            simple_mode=args.simple_mode,
            output_directory=output_directory,
            timestamp=timestamp,
            no_captions=args.no_captions,
            template_path=args.template_image,
            template_audio_path=args.template_audio,
            target_width=args.target_width,
            target_height=args.target_height,
            resize_mode=args.resize
        )
        return

    # For single video mode, check required parameters
    if not args.images:
        parser.error("--images is required for single video mode")
    if not args.output:
        parser.error("--output is required for single video mode")

    animate = not args.no_animate

    # Create the video
    create_video(
        images=args.images,
        audio_path=args.audio,
        output_path=args.output,
        font_name=args.font_name,
        font_size=args.font_size,
        color=args.color,
        stroke_width=args.stroke_width,
        stroke_color=args.stroke_color,
        caption_chunk_size=args.caption_chunk_size,
        animate=animate,
        post_id=args.post_id,
        post_file=args.post_file,
        post_json=args.json_file,
        caption_text=args.caption_text,
        word_by_word=args.word_by_word,
        bg_color=args.bg_color,
        save_debug_images=args.save_debug_images,
        debug_path=args.debug_path,
        no_captions=args.no_captions,
        template_path=args.template_image,
        template_audio_path=args.template_audio,
        target_width=args.target_width,
        target_height=args.target_height,
        resize_mode=args.resize
    )

if __name__ == "__main__":
    sys.exit(main()) 