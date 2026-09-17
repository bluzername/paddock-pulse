"""
Voiceover Generator Module

This module is responsible for generating voiceovers for Formula 1 posts
using the Eleven Labs API to create natural-sounding audio.
"""

import os
import sys
import json
import logging
import requests
from paddock_pulse import config
from pathlib import Path
import colorama
from colorama import Fore, Style
import re

# Initialize colorama for colored terminal output
colorama.init(autoreset=True)

# Custom ColoredFormatter for logging
class ColoredFormatter(logging.Formatter):
    """Custom formatter to add colors to log messages based on level."""
    
    FORMATS = {
        logging.DEBUG: Style.DIM + "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        logging.INFO: "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        logging.WARNING: Fore.YELLOW + "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        logging.ERROR: Fore.RED + "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        logging.CRITICAL: Fore.RED + Style.BRIGHT + "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    }
    
    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)

# Set up logging with colored output
handler = logging.StreamHandler()
handler.setFormatter(ColoredFormatter())
logging.basicConfig(
    level=logging.INFO,
    handlers=[handler]
)
logger = logging.getLogger("voiceover_generator")

class VoiceoverGenerator:
    """
    Class to generate realistic F1 commentary-style voiceovers using Eleven Labs.
    Optimized to sound like Will Buxton, a popular F1 commentator.
    """
    
    def __init__(self, api_key, output_dir='output'):
        """
        Initialize the VoiceoverGenerator.
        
        Args:
            api_key: Eleven Labs API key
            output_dir: Directory where voiceovers will be stored
        """
        self.api_key = api_key
        self.output_dir = output_dir
        self.api_url = "https://api.elevenlabs.io/v1"
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Verify API key
        if not api_key:
            logger.error("No Eleven Labs API key provided. Voiceover generation will fail.")
            raise ValueError("Eleven Labs API key is required")
        
        # Settings optimized for Will Buxton-like voice
        # "Adam" voice is the most similar to Buxton with adjustments for pitch and clarity
        #self.voice_id = "pNInz6obpgDQGcFmaJgB"  # Adam voice ID
        self.voice_id = "UEKYgullGqaF0keqT8Bu" # Chris Brift voice ID
        
        # Voice settings to make it closer to Will Buxton's style
        # - Slight British accent 
        # - Enthusiastic intonation
        # - Clear pronunciation
        self.voice_settings = {
            "stability": 0.6,           # Lower stability for more natural variation
            "similarity_boost": 0.8,    # Higher similarity for more consistent style
            "style": 0.5,               # Mid-level style for balanced expressiveness
            "use_speaker_boost": True   # Enhanced clarity
        }
        
        # Model optimized for sports commentary
        self.model_id = config.TTS_MODEL
    
    def _clean_text_for_voiceover(self, text):
        """
        Clean the text for better voiceover quality.
        
        Args:
            text: The text to clean
            
        Returns:
            Cleaned text
        """
        # Remove hashtags completely
        text = re.sub(r'#\w+', '', text)
        
        # Remove all emojis completely
        # This pattern covers most emojis including skin tone modifiers and ZWJ sequences
        emoji_pattern = re.compile(
            "["
            "\U0001F1E0-\U0001F1FF"  # flags (iOS)
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F700-\U0001F77F"  # alchemical symbols
            "\U0001F780-\U0001F7FF"  # Geometric Shapes
            "\U0001F800-\U0001F8FF"  # Supplemental Arrows-C
            "\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
            "\U0001FA00-\U0001FA6F"  # Chess Symbols
            "\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
            "\U00002702-\U000027B0"  # Dingbats
            "\U000024C2-\U0001F251" 
            "]+", flags=re.UNICODE)
        
        text = emoji_pattern.sub(r'', text)
        
        # Improve pronunciations for F1-specific terms
        pronunciation_fixes = {
            "F1": "Formula 1",
            "DRS": "D R S",
            "DNF": "D N F",
            "P1": "position 1",
            "P2": "position 2",
            "P3": "position 3",
            "P4": "position 4",
            "P5": "position 5",
            "Q1": "qualifying 1",
            "Q2": "qualifying 2",
            "Q3": "qualifying 3"
        }
        
        for term, pronunciation in pronunciation_fixes.items():
            text = text.replace(f" {term} ", f" {pronunciation} ")
        
        # Remove any XML/HTML-like tags that might already be in the text
        text = re.sub(r'<[^>]+>', '', text)
        
        return text.strip()
    
    def generate_voiceover(self, text, output_path, title=None):
        """
        Generate a voiceover for the given text.
        
        Args:
            text: The text to generate a voiceover for
            output_path: The full path where the generated audio will be saved
            title: Optional title to add at the beginning (now ignored)
            
        Returns:
            Path to the saved audio file or None if generation failed
        """
        try:
            # Clean the text for better voiceover quality
            voiceover_text = self._clean_text_for_voiceover(text)
            
            # Log the final text being sent to the API
            logger.info(f"Sending to ElevenLabs API: '{voiceover_text}'")
            
            # Prepare the API request
            headers = {
                "xi-api-key": self.api_key,
                "Content-Type": "application/json"
            }
            
            data = {
                "text": voiceover_text,
                "model_id": self.model_id,
                "voice_settings": self.voice_settings
            }
            
            # Make the API request
            logger.info(f"Generating voiceover for: {os.path.basename(output_path)}")
            url = f"{self.api_url}/text-to-speech/{self.voice_id}"
            
            response = requests.post(url, json=data, headers=headers)
            
            if response.status_code == 200:
                # Ensure the directory exists
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                
                # Save the audio file
                with open(output_path, "wb") as f:
                    f.write(response.content)
                logger.info(f"Voiceover saved to {output_path}")
                return output_path
            else:
                logger.error(f"Error generating voiceover: {response.status_code}")
                logger.error(f"Response: {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error in voiceover generation: {str(e)}")
            return None
    
    def generate_voiceovers_for_posts_file(self, posts_file):
        """
        Generate voiceovers for all posts in a posts file.
        
        Args:
            posts_file: Path to the posts text file
            
        Returns:
            Dictionary mapping post titles to paths of generated audio files
        """
        # Extract base name of posts file without extension
        base_name = os.path.splitext(os.path.basename(posts_file))[0]
        
        # New structure: extract timestamp from base_name (e.g., f1_posts_20250401_144720)
        # and use as main folder
        timestamp = base_name.replace("f1_posts_", "")
        main_output_dir = os.path.join(self.output_dir, timestamp)
        voiceovers_dir = os.path.join(main_output_dir, "voiceovers")
        
        logger.info(f"Generating voiceovers for posts in {posts_file}")
        logger.info(f"Voiceovers will be saved to {voiceovers_dir}")
        
        # Create directory for voiceovers
        os.makedirs(voiceovers_dir, exist_ok=True)
        
        # Check if there's a JSON file available (preferred format with separated hashtags)
        json_file = os.path.splitext(posts_file)[0] + ".json"
        
        if os.path.exists(json_file):
            # Use JSON file with separated hashtags
            logger.info(f"Using JSON posts file: {json_file}")
            with open(json_file, 'r') as f:
                posts_data = json.load(f)
            
            posts = []
            for post in posts_data:
                # Only use post_text for voiceover, NOT content (which includes hashtags)
                # Do not use a fallback to "content" as it includes hashtags
                post_text = post.get("post_text", "")
                
                # Debug: Log what we're using for voiceover
                logger.debug(f"Post text for voiceover: {post_text}")
                
                posts.append({
                    "title": post.get("event_title", ""),  # Still needed for file naming
                    "text": post_text  # Only use post_text, not content
                })
        else:
            # Use text file format
            logger.info(f"Using text posts file: {posts_file}")
            # Read posts file
            with open(posts_file, 'r') as f:
                content = f.read()
            
            # Parse posts
            post_sections = content.split("\n\n")
            posts = []
            
            i = 0
            while i < len(post_sections):
                if i + 2 < len(post_sections) and post_sections[i].startswith("Post "):
                    title_line = post_sections[i]
                    separator_line = post_sections[i+1]
                    post_text = post_sections[i+2]
                    
                    # Extract title from "Post N: Title"
                    title_match = re.match(r"Post \d+: (.*)", title_line)
                    if title_match:
                        title = title_match.group(1)
                        # Remove hashtags from text for voiceover
                        clean_text = re.sub(r'#\w+', '', post_text)
                        posts.append({"title": title, "text": clean_text.strip()})
                    
                    i += 3
                else:
                    i += 1
        
        voiceover_paths = {}
        
        # Generate voiceovers for each post
        for i, post in enumerate(posts):
            post_title = post["title"]
            post_text = post["text"]
            
            # Debug: Log the text before it goes to the clean function
            logger.debug(f"Pre-cleaning text for {post_title}: {post_text[:50]}...")
            
            # Create safe filename
            safe_title = "".join(c if c.isalnum() or c in [' ', '_'] else '_' for c in post_title)
            safe_title = safe_title.replace(' ', '_')[:50]  # Limit length
            
            # Generate voiceover
            audio_filename = f"{i+1}_{safe_title}.mp3"
            full_output_path = os.path.join(voiceovers_dir, audio_filename)
            audio_path = self.generate_voiceover(
                post_text, 
                full_output_path,
                title=post_title
            )
            
            if audio_path:
                voiceover_paths[post_title] = audio_path
                logger.info(f"Generated voiceover for post: {post_title}")
            else:
                logger.warning(f"Failed to generate voiceover for post: {post_title}")
        
        # Save a summary file
        summary_path = os.path.join(voiceovers_dir, "summary.json")
        with open(summary_path, 'w') as f:
            json.dump(voiceover_paths, f, indent=2)
        
        logger.info(f"Voiceover generation completed. Results saved to {voiceovers_dir}")
        return voiceover_paths

def main():
    """Main function to generate voiceovers for the most recent posts file."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate voiceovers for F1 social media posts")
    parser.add_argument("--api-key", help="Eleven Labs API key (overrides ELEVEN_LABS_API_KEY environment variable)")
    parser.add_argument("--posts-file", help="Path to the posts text file")
    parser.add_argument("--output-dir", default="output", help="Directory to save voiceovers (default: output)")
    args = parser.parse_args()
    
    # Load environment variables from .env file
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        logger.warning("python-dotenv is not installed. Will rely on environment variables already set.")
    
    # Get API key from arguments or environment variable
    api_key = args.api_key or os.environ.get("ELEVEN_LABS_API_KEY")
    
    if not api_key:
        logger.error("No Eleven Labs API key provided. Please provide an API key using --api-key or set the ELEVEN_LABS_API_KEY environment variable.")
        return 1
    
    generator = VoiceoverGenerator(api_key=api_key, output_dir=args.output_dir)
    
    # If posts file is provided, use it
    if args.posts_file:
        posts_file = args.posts_file
    else:
        # Otherwise, find the most recent posts file
        output_dir = args.output_dir
        posts_files = [f for f in os.listdir(output_dir) if f.startswith("f1_posts_") and f.endswith(".txt")]
        
        if not posts_files:
            logger.error(f"No posts files found in {output_dir}. Run the main script first to generate posts.")
            return 1
        
        # Sort by timestamp in filename
        posts_files.sort(reverse=True)
        posts_file = os.path.join(output_dir, posts_files[0])
    
    # Generate voiceovers for all posts in the file
    generator.generate_voiceovers_for_posts_file(posts_file)
    return 0

if __name__ == "__main__":
    sys.exit(main()) 