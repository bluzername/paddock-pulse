#!/usr/bin/env python3
"""
PaddockPulse Complete Workflow Script

This script orchestrates the complete workflow:
1. Fetch F1 data from FastF1 API
2. Analyze interesting events using LLM
3. Generate social media posts about the events
4. Generate image prompts for each post to be used with GenAI tools
5. (Optional) Generate actual images using OpenAI's DALL-E model
"""

import os
import sys
import logging
import argparse
from datetime import datetime
import colorama
from colorama import Fore, Style
import json

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
logger = logging.getLogger("paddock_pulse_all")

def mask_api_key(api_key):
    """Mask an API key for secure display, showing only first 4 and last 4 characters."""
    if not api_key:
        return "None"
    if len(api_key) <= 8:
        return "****"
    return f"{api_key[:4]}...{api_key[-4:]}"

def sanitize_api_key(api_key):
    """
    Sanitize an API key by removing unwanted characters and validating it.
    
    Args:
        api_key: API key to sanitize
        
    Returns:
        tuple: (cleaned_key, is_valid, message)
    """
    if not api_key:
        return None, False, "API key is empty"
    
    # Trim whitespace
    cleaned_key = api_key.strip()
    
    # Check for placeholder patterns
    placeholder_patterns = [
        "your", "api", "key", "openai", "sk-your", "example", "place", "holder",
        "demo", "test", "change", "replace"
    ]
    
    for pattern in placeholder_patterns:
        if pattern.lower() in cleaned_key.lower():
            return cleaned_key, False, f"API key appears to be a placeholder (contains '{pattern}')"
    
    # Check for proper format
    if not cleaned_key.startswith("sk-"):
        return cleaned_key, False, "API key should start with 'sk-'"
    
    # Check reasonable length
    if len(cleaned_key) < 20:
        return cleaned_key, False, "API key is too short"
    
    return cleaned_key, True, "API key appears valid"

def create_output_structure(output_dir, timestamp=None, create_dirs=True):
    """
    Create the new output directory structure with separate folders for each content type.
    
    Args:
        output_dir: Base output directory
        timestamp: Optional timestamp string (if None, a new one will be generated)
        create_dirs: Whether to actually create the directories (default: True)
        
    Returns:
        dict: Dictionary with paths for different content types
    """
    import datetime
    
    # Generate timestamp if not provided
    if not timestamp:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    elif timestamp.startswith("f1_posts_"):
        # Extract timestamp from existing filename
        timestamp = timestamp.replace("f1_posts_", "")
    
    # Create main output directory with timestamp
    main_output_dir = os.path.join(output_dir, timestamp)
    
    # Create subdirectories for different content types
    posts_dir = os.path.join(main_output_dir, "posts")
    prompts_dir = os.path.join(main_output_dir, "prompts")
    images_dir = os.path.join(main_output_dir, "images")
    voiceovers_dir = os.path.join(main_output_dir, "voiceovers")
    
    # Only create directories if requested
    if create_dirs:
        os.makedirs(posts_dir, exist_ok=True)
        os.makedirs(prompts_dir, exist_ok=True)
        os.makedirs(images_dir, exist_ok=True)
        os.makedirs(voiceovers_dir, exist_ok=True)
    
    # Return paths
    return {
        "timestamp": timestamp,
        "main_dir": main_output_dir,
        "posts_dir": posts_dir,
        "prompts_dir": prompts_dir,
        "images_dir": images_dir,
        "voiceovers_dir": voiceovers_dir,
        "posts_file": os.path.join(posts_dir, f"f1_posts.txt"),
        "posts_json": os.path.join(posts_dir, f"f1_posts.json")
    }

def debug_api_keys(openrouter_key, openai_key):
    """Print API key information for debugging."""
    print(f"\n{Style.BRIGHT}{Fore.YELLOW}API Key Debug Information:{Style.RESET_ALL}")
    print(f"OpenRouter API Key: {mask_api_key(openrouter_key)}")
    print(f"OpenAI API Key: {mask_api_key(openai_key)}")
    print(f"OpenRouter Key Length: {len(openrouter_key) if openrouter_key else 0} characters")
    print(f"OpenAI Key Length: {len(openai_key) if openai_key else 0} characters")
    
    # Get the raw environment variables to check for quotation marks or whitespace
    raw_env_openai = os.environ.get('OPENAI_API_KEY', 'Not set')
    if raw_env_openai != 'Not set':
        print(f"\n{Fore.CYAN}Raw OPENAI_API_KEY from environment:")
        print(f"Length: {len(raw_env_openai)} characters")
        print(f"Has leading whitespace: {raw_env_openai[0].isspace() if raw_env_openai else False}")
        print(f"Has trailing whitespace: {raw_env_openai[-1].isspace() if raw_env_openai else False}")
        if "'" in raw_env_openai or '"' in raw_env_openai:
            print(f"{Fore.RED}Warning: API key contains quote characters!")
    
    if openai_key:
        # Perform sanitization check
        _, is_valid, message = sanitize_api_key(openai_key)
        if is_valid:
            print(f"{Fore.GREEN}OpenAI Key Format: {message}")
        else:
            print(f"{Fore.RED}OpenAI Key Format: {message}")
    
    # Check environment variables
    env_openrouter = os.environ.get('OPENROUTER_API_KEY', 'Not set')
    env_openai = os.environ.get('OPENAI_API_KEY', 'Not set')
    
    print(f"\n{Fore.CYAN}Environment Variables:")
    print(f"OPENROUTER_API_KEY in env: {'Yes' if env_openrouter != 'Not set' else 'No'}")
    print(f"OPENAI_API_KEY in env: {'Yes' if env_openai != 'Not set' else 'No'}")
    
    if env_openai != 'Not set':
        if env_openai == openai_key:
            print(f"{Fore.GREEN}OpenAI Key matches environment variable")
        else:
            print(f"{Fore.YELLOW}OpenAI Key is different from environment variable")
            print(f"Environment: {mask_api_key(env_openai)}")
            print(f"Argument/Sanitized: {mask_api_key(openai_key)}")
    
    # Check dotenv file if it exists
    dotenv_path = '.env'
    if os.path.exists(dotenv_path):
        print(f"\n{Fore.CYAN}Checking .env file:")
        with open(dotenv_path, 'r') as f:
            env_content = f.readlines()
        
        openai_lines = [line for line in env_content if 'OPENAI_API_KEY' in line]
        if openai_lines:
            for line in openai_lines:
                # Mask the key in the output
                censored_line = line
                if '=' in line:
                    key_part = line.split('=', 1)[1].strip()
                    if key_part:
                        censored_line = line.replace(key_part, mask_api_key(key_part))
                print(f"  {censored_line.strip()}")
                
                # Check for common issues in the line
                if '#' in line and not line.startswith('#'):
                    print(f"{Fore.YELLOW}  Warning: Line contains comments after the key")
                if '"' in line or "'" in line:
                    print(f"{Fore.YELLOW}  Warning: Line contains quote characters")
                if line.strip().endswith('\\'):
                    print(f"{Fore.YELLOW}  Warning: Line ends with escape character")
        else:
            print("  No OPENAI_API_KEY found in .env file")
    
    print("\n")
    return

def run_image_prompt_generation(api_key, output_dir):
    """
    Generate image prompts for F1-101 educational content.
    
    Args:
        api_key: OpenRouter API key
        output_dir: Directory where the posts are located
    
    Returns:
        bool: Success or failure
    """
    from paddock_pulse.prompt_generator import OpenRouterPromptGenerator
    
    logger.info("Starting image prompt generation for F1-101 educational content...")
    
    # Find the most recent F1-101 posts file
    timestamp_dirs = [d for d in os.listdir(output_dir) 
                    if os.path.isdir(os.path.join(output_dir, d)) and not d.startswith('.')]
    
    if not timestamp_dirs:
        logger.error(f"No output directories found in {output_dir}. Run F1-101 post generation first.")
        return False
    
    # Sort by timestamp in descending order to get the latest
    timestamp_dirs.sort(reverse=True)
    
    # Initialize variables for tracking
    posts_file = None
    posts_dir = None
    prompts_dir = None
    
    # Search for the F1-101 posts file in the latest directories
    for timestamp_dir in timestamp_dirs:
        full_timestamp_dir = os.path.join(output_dir, timestamp_dir)
        potential_posts_dir = os.path.join(full_timestamp_dir, "posts")
        
        if os.path.exists(potential_posts_dir):
            # Check for F1-101 posts file
            potential_posts_file = os.path.join(potential_posts_dir, "f1_101_posts.txt")
            if os.path.exists(potential_posts_file):
                posts_file = potential_posts_file
                posts_dir = potential_posts_dir
                prompts_dir = os.path.join(full_timestamp_dir, "prompts")
                # Create prompts directory if it doesn't exist
                os.makedirs(prompts_dir, exist_ok=True)
                break
    
    if not posts_file:
        # Try the legacy format with timestamp in filename
        legacy_posts_files = [f for f in os.listdir(output_dir) 
                             if f.startswith("f1_101_posts_") and f.endswith(".txt")]
        
        if not legacy_posts_files:
            logger.error(f"No F1-101 posts files found in {output_dir}. Run F1-101 post generation first.")
            return False
        
        # Sort by timestamp in filename
        legacy_posts_files.sort(reverse=True)
        posts_file = os.path.join(output_dir, legacy_posts_files[0])
        
        # Create prompts directory based on the timestamp in the filename
        timestamp = legacy_posts_files[0].replace("f1_101_posts_", "").replace(".txt", "")
        parent_dir = os.path.join(output_dir, timestamp)
        prompts_dir = os.path.join(parent_dir, "prompts")
        os.makedirs(prompts_dir, exist_ok=True)
    
    logger.info(f"Using F1-101 posts file: {posts_file}")
    logger.info(f"Generating prompts in: {prompts_dir}")
    
    # Create prompt generator and generate prompts
    try:
        # Use OpenRouterPromptGenerator with the API key
        prompt_gen = OpenRouterPromptGenerator(api_key=api_key, output_dir=prompts_dir)
        
        # Read and parse posts file to generate prompts manually
        with open(posts_file, 'r') as f:
            content = f.read()
        
        # Parse the posts - pattern matches "Post X: Title" followed by dashed line and content
        import re
        post_pattern = r"Post (\d+): (.*?)\n[-=]{10,}\n(.*?)\n\n(#.*?)(?:\n\n|$)"
        posts = re.findall(post_pattern, content, re.DOTALL)
        
        if not posts:
            logger.error("Could not parse any posts from the F1-101 file.")
            return False
        
        # Generate prompts for each post
        for index, title, text, hashtags in posts:
            logger.info(f"Generating image prompt for F1-101 topic: {title}")
            
            # Create a simulated event for the OpenRouterPromptGenerator
            event = {
                "title": title,
                "description": text,
                "significance": f"Educational content about {title} for F1 newcomers",
                "stats": "",
                "circuit": "Generic F1 Track",
                "country": "International",
                "weather": "Clear",
                "hashtags": hashtags
            }
            
            # Create directory for this post's prompts if needed
            post_dir = os.path.join(prompts_dir, title.replace(' ', '_'))
            os.makedirs(post_dir, exist_ok=True)
            
            # Generate a prompt using the OpenRouterPromptGenerator
            clean_title = re.sub(r'[^a-zA-Z0-9_]+', '_', title)
            prompt_filename = f"f1_101_{index}_{clean_title}.txt"
            prompt_path = os.path.join(prompts_dir, prompt_filename)
            
            # Generate the prompt using the event
            prompt_gen.generate_prompt_from_event(event, prompt_path)
            logger.info(f"Saved prompt to {prompt_path}")
        
        logger.info(f"Successfully generated {len(posts)} image prompts for F1-101 educational content")
        return True
    except Exception as e:
        logger.error(f"Error generating prompts for F1-101 content: {str(e)}")
        return False

def run_image_generation(api_key, output_dir, model="dall-e-3", size="1024x1024", provider="openai", aspect_ratio="16:9", skip_gpt_image_1=False, quality="standard", style="vivid"):
    """
    Generate images for F1-101 educational content.
    
    Args:
        api_key: API key for the specified provider
        output_dir: Directory where the posts and prompts are located
        model: Image generation model to use
        size: Image size to generate
        provider: Image generation provider (openai, midjourney, or imagen)
        aspect_ratio: Aspect ratio for images
        skip_gpt_image_1: Whether to skip GPT-Image-1 and use DALL-E 3 instead
        quality: Quality for DALL-E models (standard or hd)
        style: Style for DALL-E models (vivid or natural)
    
    Returns:
        bool: Success or failure
    """
    from paddock_pulse.image_generator import ImageGenerator
    
    logger.info(f"Starting image generation for F1-101 educational content using {provider}...")
    
    # Set environment variable to skip GPT-Image-1 if requested
    if skip_gpt_image_1:
        os.environ["SKIP_GPT_IMAGE_1"] = "true"
        logger.info("Setting SKIP_GPT_IMAGE_1=true to use DALL-E 3 instead of GPT-Image-1")
    
    # Find the most recent F1-101 posts and prompts
    timestamp_dirs = [d for d in os.listdir(output_dir) 
                    if os.path.isdir(os.path.join(output_dir, d)) and not d.startswith('.')]
    
    if not timestamp_dirs:
        logger.error(f"No output directories found in {output_dir}. Run F1-101 post generation first.")
        return False
    
    # Sort by timestamp in descending order to get the latest
    timestamp_dirs.sort(reverse=True)
    
    # Initialize variables for tracking
    prompts_dir = None
    posts_file = None
    images_dir = None
    
    # Search for the F1-101 prompts or posts in the latest directories
    for timestamp_dir in timestamp_dirs:
        full_timestamp_dir = os.path.join(output_dir, timestamp_dir)
        potential_prompts_dir = os.path.join(full_timestamp_dir, "prompts")
        
        if os.path.exists(potential_prompts_dir):
            # Check if there are any prompt files for F1-101
            prompt_files = [f for f in os.listdir(potential_prompts_dir) 
                          if f.startswith("f1_101_") and f.endswith(".txt")]
            
            if prompt_files:
                prompts_dir = potential_prompts_dir
                images_dir = os.path.join(full_timestamp_dir, "images")
                os.makedirs(images_dir, exist_ok=True)
                break
        
        # If no prompts found, check for posts to generate prompts first
        potential_posts_dir = os.path.join(full_timestamp_dir, "posts")
        if not prompts_dir and os.path.exists(potential_posts_dir):
            potential_posts_file = os.path.join(potential_posts_dir, "f1_101_posts.txt")
            if os.path.exists(potential_posts_file):
                posts_file = potential_posts_file
                prompts_dir = os.path.join(full_timestamp_dir, "prompts")
                images_dir = os.path.join(full_timestamp_dir, "images", "f1_101")
                # Create directories if they don't exist
                os.makedirs(prompts_dir, exist_ok=True)
                os.makedirs(images_dir, exist_ok=True)
                break
    
    # If no prompts found in the timestamped directories, try running prompt generation first
    if not prompts_dir and not posts_file:
        logger.info("No F1-101 prompts found. Running prompt generation first...")
        if run_image_prompt_generation(api_key, output_dir):
            # Try searching again after generating prompts
            for timestamp_dir in timestamp_dirs:
                full_timestamp_dir = os.path.join(output_dir, timestamp_dir)
                potential_prompts_dir = os.path.join(full_timestamp_dir, "prompts")
                
                if os.path.exists(potential_prompts_dir):
                    prompt_files = [f for f in os.listdir(potential_prompts_dir) 
                                  if f.startswith("f1_101_") and f.endswith(".txt")]
                    
                    if prompt_files:
                        prompts_dir = potential_prompts_dir
                        images_dir = os.path.join(full_timestamp_dir, "images", "f1_101")
                        os.makedirs(images_dir, exist_ok=True)
                        break
        else:
            logger.error("Failed to generate prompts for F1-101 content.")
            return False
    
    if not prompts_dir:
        logger.error("Could not find or generate F1-101 prompts.")
        return False
    
    # Set up additional provider-specific keys
    goapi_key = os.getenv('GOAPI_KEY', '') if provider == 'midjourney' else None
    google_key = os.getenv('GOOGLE_API_KEY', '') if provider == 'imagen' else None
    
    # Create image generator
    try:
        # Override the API key based on the provider
        if provider == 'imagen':
            actual_api_key = google_key or api_key
        elif provider == 'midjourney':
            actual_api_key = goapi_key or api_key
        else:
            actual_api_key = api_key
        
        # If provider is imagen, use imagen-3.0-generate-002 model
        if provider == 'imagen':
            model = 'imagen-3.0-generate-002'
        
        # Set environment variable to skip GPT-Image-1 if requested
        skip_gpt_image_1 = getattr(args, 'skip_gpt_image_1', False)
        if skip_gpt_image_1:
            os.environ["SKIP_GPT_IMAGE_1"] = "true"
            logger.info("Setting SKIP_GPT_IMAGE_1=true to use DALL-E 3 instead of GPT-Image-1")
        
        image_gen = ImageGenerator(
            api_key=actual_api_key,
            output_dir=images_dir,
            model=model,
            size=size,
            provider=provider,
            goapi_key=goapi_key,
            google_key=google_key,
            aspect_ratio=aspect_ratio,
            quality=quality,
            style=style
        )
        
        # Generate images from prompts
        logger.info(f"Generating images from prompts in: {prompts_dir}")
        # Filter for F1-101 prompt files only
        educational_prompts = [f for f in os.listdir(prompts_dir) 
                             if f.startswith("f1_101_") and f.endswith(".txt")]
        
        if not educational_prompts:
            logger.error("No F1-101 prompt files found in prompts directory.")
            return False
        
        for prompt_file in educational_prompts:
            with open(os.path.join(prompts_dir, prompt_file), 'r') as f:
                prompt_text = f.read().strip()
            
            # Generate image using the prompt
            base_filename = prompt_file.replace(".txt", "")
            output_path = os.path.join(images_dir, f"{base_filename}.png")
            
            logger.info(f"Generating image for {prompt_file}...")
            image_gen.generate_image_from_prompt(prompt_text, output_path)
            logger.info(f"Image saved to {output_path}")
        
        logger.info(f"Successfully generated images for {len(educational_prompts)} F1-101 topics")
        return True
        
    except Exception as e:
        logger.error(f"Error generating images for F1-101 content: {str(e)}")
        return False

def run_voiceover_generation(api_key, output_dir):
    """
    Generate voiceovers for F1-101 educational content.
    
    Args:
        api_key: Eleven Labs API key
        output_dir: Directory where the posts are located
    
    Returns:
        bool: Success or failure
    """
    from paddock_pulse.voiceover_generator import VoiceoverGenerator
    
    logger.info("Starting voiceover generation for F1-101 educational content...")
    
    # Find the most recent F1-101 posts file
    timestamp_dirs = [d for d in os.listdir(output_dir) 
                    if os.path.isdir(os.path.join(output_dir, d)) and not d.startswith('.')]
    
    if not timestamp_dirs:
        logger.error(f"No output directories found in {output_dir}. Run F1-101 post generation first.")
        return False
    
    # Sort by timestamp in descending order to get the latest
    timestamp_dirs.sort(reverse=True)
    
    # Initialize variables for tracking
    posts_file = None
    voiceovers_dir = None
    
    # Search for the F1-101 posts file in the latest directories
    for timestamp_dir in timestamp_dirs:
        full_timestamp_dir = os.path.join(output_dir, timestamp_dir)
        potential_posts_dir = os.path.join(full_timestamp_dir, "posts")
        
        if os.path.exists(potential_posts_dir):
            # Check for F1-101 posts file
            potential_posts_file = os.path.join(potential_posts_dir, "f1_101_posts.txt")
            if os.path.exists(potential_posts_file):
                posts_file = potential_posts_file
                voiceovers_dir = os.path.join(full_timestamp_dir, "voiceovers", "f1_101")
                # Create voiceovers directory if it doesn't exist
                os.makedirs(voiceovers_dir, exist_ok=True)
                break
    
    if not posts_file:
        # Try the legacy format with timestamp in filename
        legacy_posts_files = [f for f in os.listdir(output_dir) 
                             if f.startswith("f1_101_posts_") and f.endswith(".txt")]
        
        if not legacy_posts_files:
            logger.error(f"No F1-101 posts files found in {output_dir}. Run F1-101 post generation first.")
            return False
        
        # Sort by timestamp in filename
        legacy_posts_files.sort(reverse=True)
        posts_file = os.path.join(output_dir, legacy_posts_files[0])
        
        # Create voiceovers directory based on the timestamp in the filename
        timestamp = legacy_posts_files[0].replace("f1_101_posts_", "").replace(".txt", "")
        parent_dir = os.path.join(output_dir, timestamp)
        voiceovers_dir = os.path.join(parent_dir, "voiceovers", "f1_101")
        os.makedirs(voiceovers_dir, exist_ok=True)
    
    logger.info(f"Using F1-101 posts file: {posts_file}")
    logger.info(f"Generating voiceovers in: {voiceovers_dir}")
    
    # Create voiceover generator and generate voiceovers
    try:
        voiceover_gen = VoiceoverGenerator(api_key=api_key, output_dir=voiceovers_dir)
        
        # Read the posts file to extract content for voiceovers
        with open(posts_file, 'r') as f:
            content = f.read()
        
        # Parse the posts - try multiple patterns to handle different formats
        import re
        
        # Try different patterns to match the post format
        patterns = [
            # Pattern 1: Standard format with dashes
            r"Post (\d+): (.*?)\n-{10,}\n(.*?)\n\n(#.*?)(?:\n\n|$)",
            # Pattern 2: Format with equal signs
            r"Post (\d+): (.*?)\n={10,}\n(.*?)\n\n(#.*?)(?:\n\n|$)",
            # Pattern 3: Format without separator line
            r"Post (\d+): (.*?)\n\n(.*?)\n\n(#.*?)(?:\n\n|$)"
        ]
        
        posts = []
        for pattern in patterns:
            posts = re.findall(pattern, content, re.DOTALL)
            if posts:
                logger.info(f"Found {len(posts)} posts using pattern {patterns.index(pattern) + 1}")
                break
        
        if not posts:
            logger.error("Could not parse any posts from the file. Trying an alternative approach...")
            # Try a more generic approach - split by "Post X:" headers
            sections = re.split(r"Post \d+:", content)[1:]  # Skip first empty section
            if sections:
                posts = []
                for i, section in enumerate(sections):
                    # Extract title from the first line
                    title_match = re.match(r"\s*(.*?)\n", section)
                    if title_match:
                        title = title_match.group(1).strip()
                        # Try to extract the content and hashtags
                        parts = section.split("\n\n")
                        if len(parts) >= 2:
                            text = parts[0].strip()
                            # Look for hashtags
                            hashtag_line = ""
                            for part in parts:
                                if part.strip().startswith("#"):
                                    hashtag_line = part.strip()
                                    break
                            
                            posts.append((str(i+1), title, text, hashtag_line))
        
        if not posts:
            logger.error("Could not parse any posts from the file using multiple methods.")
            return False
        
        # Create a summary.json file to track generated voiceovers
        summary_data = {}
        
        # Generate voiceovers for each post
        for index, title, text, hashtags in posts:
            logger.info(f"Generating voiceover for post {index}: {title}")
            clean_title = re.sub(r'[^a-zA-Z0-9_]+', '_', title)
            output_file = os.path.join(voiceovers_dir, f"{index}_{clean_title}.mp3")
            
            # Generate the voiceover
            result = voiceover_gen.generate_voiceover(text, output_file, title)
            
            if result:
                # Record in summary data
                summary_data[title] = {
                    "audio_file": os.path.basename(output_file),
                    "duration_seconds": None  # This would be filled by analyzing the audio file
                }
                logger.info(f"Voiceover generated: {output_file}")
            else:
                logger.warning(f"Failed to generate voiceover for post {index}: {title}")
        
        # Save summary data
        summary_path = os.path.join(voiceovers_dir, "summary.json")
        with open(summary_path, 'w') as f:
            json.dump(summary_data, f, indent=2)
        
        logger.info(f"Successfully generated voiceovers for {len(summary_data)} F1-101 topics")
        logger.info(f"Summary saved to {summary_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error generating voiceovers for F1-101 content: {str(e)}")
        return False

def main():
    """Main entry point for the complete workflow."""
    # Load environment variables from .env file first
    from dotenv import load_dotenv
    load_dotenv()
    
    parser = argparse.ArgumentParser(description="PaddockPulse - F1 Social Media Content Generator")
    
    # Add general arguments
    parser.add_argument(
        "--api-key", 
        dest="api_key",
        help="OpenRouter API key (overrides OPENROUTER_API_KEY environment variable)"
    )
    
    parser.add_argument(
        "--openai-api-key", 
        dest="openai_api_key",
        help="OpenAI API key (overrides OPENAI_API_KEY environment variable)"
    )
    
    parser.add_argument(
        "--data-dir",
        default="data",
        help="Directory to store F1 data (default: data)"
    )
    
    parser.add_argument(
        "--output-dir",
        default="output",
        help="Directory to store generated content (default: output)"
    )
    
    parser.add_argument(
        "--posts-folder",
        help="Path to the folder containing posts files (e.g., output/20250401_221621/posts)"
    )
    
    parser.add_argument(
        "--key-debug",
        action="store_true",
        help="Print API key debug information (masked for security)"
    )
    
    parser.add_argument(
        "--latest-race-only",
        action="store_true",
        help="Focus only on the most recent race when generating content"
    )
    
    # Add subparsers for different modes
    subparsers = parser.add_subparsers(dest="mode", help="Operation mode")
    
    # Parser for post generation mode
    posts_parser = subparsers.add_parser("posts", help="Generate social media posts")
    posts_parser.add_argument(
        "--refresh", 
        action="store_true",
        help="Force refresh of F1 data even if cached data exists"
    )
    posts_parser.add_argument(
        "--latest-race-only",
        action="store_true",
        help="Focus only on the most recent race when generating content"
    )
    posts_parser.add_argument(
        "--historical-years",
        type=int,
        default=3,
        help="Number of historical years to fetch data for (default: 3)"
    )
    posts_parser.add_argument(
        "--max-events",
        type=int,
        default=5,
        help="Maximum number of interesting events to identify (default: 5)"
    )
    posts_parser.add_argument(
        "--num-posts",
        type=int,
        default=5,
        help="Number of posts to generate (default: 5)"
    )
    posts_parser.add_argument(
        "--key-debug",
        action="store_true",
        help="Print API key debug information (masked for security)"
    )
    posts_parser.add_argument(
        "--technical",
        action="store_true",
        help="Generate technical content focused on telemetry data and engineering insights"
    )
    
    # Parser for prompt generation mode
    prompts_parser = subparsers.add_parser("prompts", help="Generate image prompts for posts")
    prompts_parser.add_argument(
        "--posts-file",
        help="Path to the posts text file (if not provided, the most recent one will be used)"
    )
    prompts_parser.add_argument(
        "--key-debug",
        action="store_true",
        help="Print API key debug information (masked for security)"
    )
    prompts_parser.add_argument(
        "--technical",
        action="store_true",
        help="Generate technical data visualization prompts instead of photo-realistic prompts"
    )
    
    # Parser for image generation mode
    images_parser = subparsers.add_parser("images", help="Generate images from prompts")
    images_parser.add_argument('--posts-file', help='Path to the posts file')
    images_parser.add_argument('--model', default='dall-e-3', help='Image generation model')
    images_parser.add_argument('--size', default='1024x1024', help='Image size')
    images_parser.add_argument('--provider', default='openai', help='Image generation provider (openai, midjourney, imagen)')
    images_parser.add_argument('--aspect-ratio', default='16:9', help='Aspect ratio for the images')
    images_parser.add_argument('--quality', default='standard', choices=['standard', 'hd'], help='Quality for DALL-E models (standard or hd)')
    images_parser.add_argument('--style', default='vivid', choices=['vivid', 'natural'], help='Style for DALL-E models (vivid or natural)')
    images_parser.add_argument(
        "--key-debug",
        action="store_true",
        help="Print API key debug information (masked for security)"
    )
    images_parser.add_argument(
        "--skip-gpt-image-1",
        action="store_true",
        help="Skip using GPT-Image-1 model and use DALL-E 3 instead, even when gpt-image-1 is specified"
    )
    images_parser.add_argument(
        "--goapi-key",
        help="GoAPI key for Midjourney integration (overrides GOAPI_KEY environment variable)"
    )
    images_parser.add_argument(
        "--google-key",
        help="Google API key for Imagen integration (overrides GOOGLE_API_KEY environment variable)"
    )
    
    # Parser for voiceover generation mode
    voiceover_parser = subparsers.add_parser("voiceovers", help="Generate voiceovers for posts using Eleven Labs API")
    voiceover_parser.add_argument(
        "--eleven-labs-api-key", 
        dest="eleven_labs_api_key",
        help="Eleven Labs API key (overrides ELEVEN_LABS_API_KEY environment variable)"
    )
    voiceover_parser.add_argument(
        "--posts-file",
        help="Path to the posts text file (if not provided, the most recent one will be used)"
    )
    voiceover_parser.add_argument(
        "--posts-folder",
        help="Path to the folder containing posts files (e.g., output/20250401_221621/posts)"
    )
    voiceover_parser.add_argument(
        "--key-debug",
        action="store_true",
        help="Print API key debug information (masked for security)"
    )
    
    # Parser for full workflow mode without images
    full_with_voiceovers_parser = subparsers.add_parser("full-with-voiceovers", help="Run the complete workflow: data, posts, prompts, and voiceovers (no images)")
    full_with_voiceovers_parser.add_argument(
        "--refresh", 
        action="store_true",
        help="Force refresh of F1 data even if cached data exists"
    )
    full_with_voiceovers_parser.add_argument(
        "--latest-race-only",
        action="store_true",
        help="Focus only on the most recent race when generating content"
    )
    full_with_voiceovers_parser.add_argument(
        "--historical-years",
        type=int,
        default=3,
        help="Number of historical years to fetch data for (default: 3)"
    )
    full_with_voiceovers_parser.add_argument(
        "--max-events",
        type=int,
        default=5,
        help="Maximum number of interesting events to identify (default: 5)"
    )
    full_with_voiceovers_parser.add_argument(
        "--num-posts",
        type=int,
        default=5,
        help="Number of posts to generate (default: 5)"
    )
    full_with_voiceovers_parser.add_argument(
        "--eleven-labs-api-key", 
        dest="eleven_labs_api_key",
        help="Eleven Labs API key (overrides ELEVEN_LABS_API_KEY environment variable)"
    )
    full_with_voiceovers_parser.add_argument(
        "--posts-folder",
        help="Path to the folder containing posts files for voiceover generation"
    )
    full_with_voiceovers_parser.add_argument(
        "--key-debug",
        action="store_true",
        help="Print API key debug information (masked for security)"
    )
    full_with_voiceovers_parser.add_argument(
        "--technical",
        action="store_true",
        help="Generate technical content focused on telemetry data and engineering insights"
    )
    
    # Parser for full workflow mode with images
    full_with_images_parser = subparsers.add_parser("full-with-images", help="Run the complete workflow: data, posts, prompts, and images")
    full_with_images_parser.add_argument(
        "--refresh", 
        action="store_true",
        help="Force refresh of F1 data even if cached data exists"
    )
    full_with_images_parser.add_argument(
        "--latest-race-only",
        action="store_true",
        help="Focus only on the most recent race when generating content"
    )
    full_with_images_parser.add_argument(
        "--historical-years",
        type=int,
        default=3,
        help="Number of historical years to fetch data for (default: 3)"
    )
    full_with_images_parser.add_argument(
        "--max-events",
        type=int,
        default=5,
        help="Maximum number of interesting events to identify (default: 5)"
    )
    full_with_images_parser.add_argument(
        "--num-posts",
        type=int,
        default=5,
        help="Number of posts to generate (default: 5)"
    )
    full_with_images_parser.add_argument(
        "--model",
        default="dall-e-3",
        help="OpenAI model to use (default: dall-e-3) or 'midjourney' for Midjourney"
    )
    full_with_images_parser.add_argument(
        "--size",
        default="1024x1024",
        help="Image size to generate (default: 1024x1024)"
    )
    full_with_images_parser.add_argument(
        "--key-debug",
        action="store_true",
        help="Print API key debug information (masked for security)"
    )
    full_with_images_parser.add_argument(
        "--provider",
        default="openai",
        choices=["openai", "midjourney", "imagen"],
        help="Image generation provider (default: openai)"
    )
    full_with_images_parser.add_argument(
        "--goapi-key",
        help="GoAPI key for Midjourney integration (overrides GOAPI_KEY environment variable)"
    )
    full_with_images_parser.add_argument(
        "--google-key",
        help="Google API key for Imagen integration (overrides GOOGLE_API_KEY environment variable)"
    )
    full_with_images_parser.add_argument(
        "--aspect-ratio",
        default="16:9",
        help="Aspect ratio for images (options: '16:9', '1:1', '4:3', etc.)"
    )
    full_with_images_parser.add_argument(
        "--skip-gpt-image-1",
        action="store_true",
        help="Skip using GPT-Image-1 model and use DALL-E 3 instead, even when gpt-image-1 is specified"
    )
    full_with_images_parser.add_argument(
        "--technical",
        action="store_true",
        help="Generate technical content focused on telemetry data and engineering insights"
    )
    
    # Parser for full workflow mode with images and voiceovers
    full_complete_parser = subparsers.add_parser("full-complete", help="Run the complete workflow: data, posts, prompts, images, and voiceovers")
    full_complete_parser.add_argument(
        "--refresh", 
        action="store_true",
        help="Force refresh of F1 data even if cached data exists"
    )
    full_complete_parser.add_argument(
        "--latest-race-only",
        action="store_true",
        help="Focus only on the most recent race when generating content"
    )
    full_complete_parser.add_argument(
        "--historical-years",
        type=int,
        default=3,
        help="Number of historical years to fetch data for (default: 3)"
    )
    full_complete_parser.add_argument(
        "--max-events",
        type=int,
        default=5,
        help="Maximum number of interesting events to identify (default: 5)"
    )
    full_complete_parser.add_argument(
        "--num-posts",
        type=int,
        default=5,
        help="Number of posts to generate (default: 5)"
    )
    full_complete_parser.add_argument(
        "--model",
        default="dall-e-3",
        help="OpenAI model to use (default: dall-e-3) or 'midjourney' for Midjourney"
    )
    full_complete_parser.add_argument(
        "--size",
        default="1024x1024",
        help="Image size to generate (default: 1024x1024)"
    )
    full_complete_parser.add_argument(
        "--provider",
        default="openai",
        choices=["openai", "midjourney", "imagen"],
        help="Image generation provider (default: openai)"
    )
    full_complete_parser.add_argument(
        "--goapi-key",
        help="GoAPI key for Midjourney integration (overrides GOAPI_KEY environment variable)"
    )
    full_complete_parser.add_argument(
        "--google-key",
        help="Google API key for Imagen integration (overrides GOOGLE_API_KEY environment variable)"
    )
    full_complete_parser.add_argument(
        "--aspect-ratio",
        default="16:9",
        help="Aspect ratio for images (options: '16:9', '1:1', '4:3', etc.)"
    )
    full_complete_parser.add_argument(
        "--skip-gpt-image-1",
        action="store_true",
        help="Skip using GPT-Image-1 model and use DALL-E 3 instead, even when gpt-image-1 is specified"
    )
    full_complete_parser.add_argument(
        "--eleven-labs-api-key", 
        dest="eleven_labs_api_key",
        help="Eleven Labs API key (overrides ELEVEN_LABS_API_KEY environment variable)"
    )
    full_complete_parser.add_argument(
        "--posts-folder",
        help="Path to the folder containing posts files for voiceover generation"
    )
    full_complete_parser.add_argument(
        "--key-debug",
        action="store_true",
        help="Print API key debug information (masked for security)"
    )
    full_complete_parser.add_argument(
        "--technical",
        action="store_true",
        help="Generate technical content focused on telemetry data and engineering insights"
    )
    full_complete_parser.add_argument(
        "--quality",
        default="standard",
        choices=["standard", "hd"],
        help="Quality for DALL-E models (standard or hd)"
    )
    full_complete_parser.add_argument(
        "--style",
        default="vivid",
        choices=["vivid", "natural"],
        help="Style for DALL-E models (vivid or natural)"
    )
    
    # Parser for F1 educational content (F1-101) mode
    f1_101_parser = subparsers.add_parser("f1-101", help="Generate educational content about F1 basics for new fans")
    f1_101_parser.add_argument(
        "--api-key", 
        dest="api_key",
        help="OpenRouter API key (overrides OPENROUTER_API_KEY environment variable)"
    )
    f1_101_parser.add_argument(
        "--num-topics",
        type=int,
        default=5,
        help="Number of educational topics to generate (default: 5)"
    )
    f1_101_parser.add_argument(
        "--output-dir",
        default="output",
        help="Directory to store generated content (default: output)"
    )
    f1_101_parser.add_argument(
        "--key-debug",
        action="store_true",
        help="Print API key debug information (masked for security)"
    )
    f1_101_parser.add_argument(
        "--with-images",
        action="store_true",
        help="Generate images for educational content"
    )
    f1_101_parser.add_argument(
        "--with-voiceovers",
        action="store_true",
        help="Generate voiceovers for educational content"
    )
    f1_101_parser.add_argument(
        "--eleven-labs-api-key", 
        dest="eleven_labs_api_key",
        help="Eleven Labs API key (overrides ELEVEN_LABS_API_KEY environment variable)"
    )
    f1_101_parser.add_argument(
        "--model",
        default="dall-e-3",
        help="Image generation model to use (default: dall-e-3)"
    )
    f1_101_parser.add_argument(
        "--size",
        default="1024x1024",
        help="Image size to generate (default: 1024x1024)"
    )
    f1_101_parser.add_argument(
        "--provider",
        default="openai",
        choices=["openai", "midjourney", "imagen"],
        help="Image generation provider (default: openai)"
    )
    f1_101_parser.add_argument(
        "--google-key",
        help="Google API key for Imagen integration (overrides GOOGLE_API_KEY environment variable)"
    )
    f1_101_parser.add_argument(
        "--aspect-ratio",
        default="16:9",
        help="Aspect ratio for images (options: '16:9', '1:1', '4:3', etc.)"
    )
    f1_101_parser.add_argument(
        "--skip-gpt-image-1",
        action="store_true",
        help="Skip using GPT-Image-1 model and use DALL-E 3 instead, even when gpt-image-1 is specified"
    )
    f1_101_parser.add_argument(
        "--quality",
        default="standard",
        choices=["standard", "hd"],
        help="Quality for DALL-E models (standard or hd)"
    )
    f1_101_parser.add_argument(
        "--style",
        default="vivid",
        choices=["vivid", "natural"],
        help="Style for DALL-E models (vivid or natural)"
    )
    
    args = parser.parse_args()
    
    # If no mode is specified, run the full workflow
    if not args.mode:
        args.mode = "full"
        args.refresh = False
        args.historical_years = 3
        args.max_events = 5
        args.num_posts = 5
    
    # Get API keys from arguments or environment variables
    api_key = args.api_key or os.getenv('OPENROUTER_API_KEY', '')
    raw_openai_api_key = args.openai_api_key or os.getenv('OPENAI_API_KEY', '')
    eleven_labs_api_key = getattr(args, 'eleven_labs_api_key', None) or os.getenv('ELEVEN_LABS_API_KEY', '')
    
    # Debug the GoAPI key loading
    goapi_env = os.getenv('GOAPI_KEY', '')
    goapi_arg = getattr(args, 'goapi_key', None)
    logger.debug(f"GOAPI_KEY from environment: {mask_api_key(goapi_env)}")
    logger.debug(f"GOAPI_KEY from arguments: {mask_api_key(goapi_arg)}")
    
    goapi_key = goapi_arg or goapi_env
    logger.debug(f"Final GOAPI_KEY: {mask_api_key(goapi_key)}")
    
    # Get Google API key for Imagen
    google_key_env = os.getenv('GOOGLE_API_KEY', '')
    google_key_arg = getattr(args, 'google_key', None)
    logger.debug(f"GOOGLE_API_KEY from environment: {mask_api_key(google_key_env)}")
    logger.debug(f"GOOGLE_API_KEY from arguments: {mask_api_key(google_key_arg)}")
    
    google_key = google_key_arg or google_key_env
    logger.debug(f"Final GOOGLE_API_KEY: {mask_api_key(google_key)}")

    # Sanitize the OpenAI API key
    openai_api_key, is_valid, message = sanitize_api_key(raw_openai_api_key)
    
    # If key-debug is enabled, print API key information
    if hasattr(args, 'key_debug') and args.key_debug:
        debug_api_keys(api_key, openai_api_key)
        
        if raw_openai_api_key != openai_api_key:
            logger.warning(f"OpenAI API key was sanitized: {message}")
    
    # Validate the API keys if we're going to use them
    if args.mode in ["images", "full-with-images", "full-complete"]:
        provider = getattr(args, 'provider', 'openai')
        
        if provider == 'openai':
            if not is_valid:
                logger.error(f"Invalid OpenAI API key: {message}")
                logger.error("Please provide a valid OpenAI API key to generate images.")
                return 1
        elif provider == 'midjourney':
            if not goapi_key:
                logger.error("No GoAPI key provided. Please set GOAPI_KEY environment variable or use --goapi-key")
                return 1
        elif provider == 'imagen':
            if not google_key:
                logger.error("No Google API key provided. Please set GOOGLE_API_KEY environment variable or use --google-key")
                return 1

    # Set to track the generated files for reference in later steps
    generated_files = {}
    
    # Create the output directory structure
    output_structure = create_output_structure(args.output_dir)
    
    # Run the selected mode
    if args.mode in ["posts", "full", "full-with-images", "full-complete", "full-with-voiceovers"]:
        # Import the main module for post generation
        from paddock_pulse.main import run_paddock_pulse
        
        # Ensure compatible arguments
        posts_args = argparse.Namespace(
            api_key=api_key,
            refresh=getattr(args, 'refresh', False),
            latest_race_only=getattr(args, 'latest_race_only', False),
            historical_years=getattr(args, 'historical_years', 3),
            max_events=getattr(args, 'max_events', 5),
            num_posts=getattr(args, 'num_posts', 5),
            data_dir=args.data_dir,
            output_dir=output_structure["posts_dir"],
            posts_file=output_structure["posts_file"],
            posts_json=output_structure["posts_json"],
            output_structure=output_structure,
            technical=getattr(args, 'technical', False)
        )
        
        # Run post generation
        logger.info("Starting post generation workflow...")
        result, posts_file = run_paddock_pulse(posts_args)
        
        if result != 0:
            logger.error("Post generation failed")
            return result
        
        generated_files['posts_file'] = posts_file
        generated_files['output_structure'] = output_structure
    
    elif args.mode == "f1-101":
        # Run F1-101 educational content mode
        from paddock_pulse.main import run_f1_101_mode
        
        # Generate educational content
        logger.info("Starting F1-101 educational content generation...")
        run_f1_101_mode(output_dir=args.output_dir, num_topics=args.num_topics)
        
        # Generate images if requested
        if args.with_images:
            # Pass appropriate image generation parameters
            run_image_prompt_generation(api_key=api_key, output_dir=args.output_dir)
            run_image_generation(
                api_key=api_key if args.provider == "openai" else google_key,
                output_dir=args.output_dir,
                model=args.model,
                size=args.size,
                provider=args.provider,
                aspect_ratio=args.aspect_ratio,
                skip_gpt_image_1=args.skip_gpt_image_1,
                quality=args.quality,
                style=args.style
            )
        
        # Generate voiceovers if requested
        if args.with_voiceovers:
            run_voiceover_generation(api_key=eleven_labs_api_key, output_dir=args.output_dir)
    
    if args.mode in ["prompts", "full", "full-with-images", "full-complete", "full-with-voiceovers"]:
        # Import the prompt generator module
        from paddock_pulse.prompt_generator import OpenRouterPromptGenerator
        
        # Find posts file to use
        posts_file = None
        
        if args.mode in ["full", "full-with-images", "full-complete", "full-with-voiceovers"]:
            # Use posts file from previous step
            if 'posts_file' in generated_files:
                posts_file = generated_files['posts_file']
            else:
                logger.error("No posts file available from previous step")
                return 1
        elif args.mode == "prompts":
            # Standalone prompt generation
            if hasattr(args, 'posts_file') and args.posts_file:
                posts_file = args.posts_file
            else:
                # Find most recent posts file
                posts_dir = output_structure["posts_dir"]
                if os.path.exists(posts_dir):
                    posts_files = [f for f in os.listdir(posts_dir) if f.endswith('.txt')]
                    if posts_files:
                        posts_files.sort(reverse=True)
                        posts_file = os.path.join(posts_dir, posts_files[0])
                
                # Fall back to legacy structure
                if not posts_file:
                    posts_files = [f for f in os.listdir(args.output_dir) if f.startswith('f1_posts_') and f.endswith('.txt')]
                    if posts_files:
                        posts_files.sort(reverse=True)
                        posts_file = os.path.join(args.output_dir, posts_files[0])
        
        if not posts_file or not os.path.exists(posts_file):
            logger.error("No valid posts file found for prompt generation")
            return 1
        
        # Create the prompt generator with the new prompts directory
        prompts_dir = output_structure["prompts_dir"]
        
        # Check if the technical mode flag is set
        technical_mode = getattr(args, 'technical', False)
        
        # Run prompt generation
        logger.info("Starting prompt generation workflow...")
        # Use OpenRouterPromptGenerator instead of legacy PromptGenerator
        api_key = api_key or os.environ.get('OPENROUTER_API_KEY')
        prompt_gen = OpenRouterPromptGenerator(api_key=api_key, output_dir=prompts_dir)
        
        # Generate prompts for all posts in the posts file
        try:
            prompt_gen.generate_prompts_from_posts_file(posts_file, technical_mode=technical_mode)
            logger.info("Prompt generation completed successfully")
            generated_files['prompts_dir'] = prompts_dir
        except Exception as e:
            logger.error(f"Prompt generation failed: {str(e)}")
            return 1
    
    if args.mode in ["images", "full-with-images", "full-complete"]:
        # Import the image generator module
        from paddock_pulse.image_generator import ImageGenerator
        
        # Get provider from args
        provider = getattr(args, 'provider', 'openai')
        
        # If key-debug is enabled, print API key information again for this specific action
        if hasattr(args, 'key_debug') and args.key_debug:
            logger.info("API Key debug for image generation")
            debug_api_keys(api_key, openai_api_key)
            if provider == 'midjourney':
                logger.info(f"GoAPI key: {mask_api_key(goapi_key)}")
            elif provider == 'imagen':
                logger.info(f"Google API key: {mask_api_key(google_key)}")
        
        if provider == 'openai' and not openai_api_key:
            logger.error("No OpenAI API key provided. Please provide an API key using --openai-api-key or set the OPENAI_API_KEY environment variable.")
            return 1
            
        if provider == 'openai' and not is_valid:
            logger.error(f"Invalid OpenAI API key: {message}")
            return 1
            
        if provider == 'midjourney' and not goapi_key:
            logger.error("No GoAPI key provided. Please set GOAPI_KEY environment variable or use --goapi-key")
            return 1
        
        if provider == 'imagen' and not google_key:
            logger.error("No Google API key provided. Please set GOOGLE_API_KEY environment variable or use --google-key")
            return 1
        
        # Create an image generator instance with the new images directory
        try:
            if provider == 'openai':
                logger.info(f"Creating OpenAI ImageGenerator with API key: {mask_api_key(openai_api_key)}")
                actual_api_key = openai_api_key
            elif provider == 'midjourney':
                logger.info(f"Creating Midjourney ImageGenerator with GoAPI key: {mask_api_key(goapi_key)}")
                actual_api_key = goapi_key
            elif provider == 'imagen':
                logger.info(f"Creating Imagen ImageGenerator with Google API key: {mask_api_key(google_key)}")
                actual_api_key = google_key
            else:
                # Default to OpenAI
                logger.info(f"Creating default OpenAI ImageGenerator with API key: {mask_api_key(openai_api_key)}")
                actual_api_key = openai_api_key
            
            # Set output directory to the images subdirectory
            images_output_dir = output_structure["images_dir"] if 'output_structure' in generated_files else args.output_dir
            
            # Get model and size parameters
            model = getattr(args, 'model', 'dall-e-3')
            size = getattr(args, 'size', '1024x1024')
            aspect_ratio = getattr(args, 'aspect_ratio', '16:9')
            quality = getattr(args, 'quality', 'standard')
            style = getattr(args, 'style', 'vivid')
            
            # If provider is midjourney, override model
            if provider == 'midjourney':
                model = 'midjourney'
            
            # If provider is imagen, use imagen-3.0-generate-002 model
            elif provider == 'imagen':
                model = 'imagen-3.0-generate-002'
            
            # Set environment variable to skip GPT-Image-1 if requested
            skip_gpt_image_1 = getattr(args, 'skip_gpt_image_1', False)
            if skip_gpt_image_1:
                os.environ["SKIP_GPT_IMAGE_1"] = "true"
                logger.info("Setting SKIP_GPT_IMAGE_1=true to use DALL-E 3 instead of GPT-Image-1")
            
            image_gen = ImageGenerator(
                api_key=actual_api_key,
                output_dir=images_output_dir,
                model=model,
                size=size,
                provider=provider,
                goapi_key=goapi_key,
                google_key=google_key,
                aspect_ratio=aspect_ratio,
                quality=quality,
                style=style
            )
            
            # Determine the prompts directory or posts file to use
            prompts_dir = None
            posts_file = None
            
            if 'prompts_dir' in generated_files:
                prompts_dir = generated_files['prompts_dir']
            elif 'posts_file' in generated_files:
                posts_file = generated_files['posts_file']
            elif args.mode == "images":
                if hasattr(args, 'prompts_dir') and args.prompts_dir:
                    prompts_dir = args.prompts_dir
                elif hasattr(args, 'posts_file') and args.posts_file:
                    posts_file = args.posts_file
                else:
                    # Find the most recent prompts directory
                    timestamp_dirs = [d for d in os.listdir(args.output_dir) 
                                    if os.path.isdir(os.path.join(args.output_dir, d)) and not d.startswith('.')]
                    
                    if timestamp_dirs:
                        # Sort by timestamp
                        timestamp_dirs.sort(reverse=True)
                        latest_dir = os.path.join(args.output_dir, timestamp_dirs[0])
                        
                        # Check for prompts directory in the latest timestamp directory
                        potential_prompts_dir = os.path.join(latest_dir, "prompts")
                        if os.path.exists(potential_prompts_dir):
                            prompts_dir = potential_prompts_dir
                        else:
                            # Check for posts file in the latest timestamp directory
                            posts_dir = os.path.join(latest_dir, "posts")
                            potential_posts_file = os.path.join(posts_dir, "f1_posts.txt")
                            if os.path.exists(potential_posts_file):
                                posts_file = potential_posts_file
                            else:
                                logger.error(f"No prompts or posts found in the latest output directory: {latest_dir}")
                                return 1
                    else:
                        logger.error(f"No output directories found in {args.output_dir}. Run post or prompt generation first.")
                        return 1
            
            # Run image generation
            logger.info("Starting image generation workflow...")
            
            if prompts_dir:
                # Generate images from existing prompts directory
                image_gen.generate_images_from_prompts_dir(prompts_dir)
            elif posts_file:
                # Generate images from posts file (first generates prompts if needed)
                image_gen.generate_images_from_posts_file(posts_file)
            else:
                logger.error("No prompts directory or posts file could be determined. Please run post or prompt generation first.")
                return 1
                
        except Exception as e:
            logger.error(f"Error initializing image generator: {str(e)}")
            logger.error("Please check your OpenAI API key and try again.")
            return 1
        except Exception as e:
            logger.error(f"Unexpected error in image generation: {str(e)}")
            return 1
    
    if args.mode in ["voiceovers", "full-complete", "full-with-voiceovers"]:
        # Import the voiceover generator module
        from paddock_pulse.voiceover_generator import VoiceoverGenerator
        
        # Validate the Eleven Labs API key
        if not eleven_labs_api_key:
            logger.error("No Eleven Labs API key provided. Please provide an API key using --eleven-labs-api-key or set the ELEVEN_LABS_API_KEY environment variable.")
            return 1
        
        try:
            # Set output directory to the voiceovers subdirectory
            voiceovers_output_dir = output_structure["voiceovers_dir"] if 'output_structure' in generated_files else args.output_dir
            
            # Create a voiceover generator instance with the new voiceovers directory
            voiceover_gen = VoiceoverGenerator(api_key=eleven_labs_api_key, output_dir=voiceovers_output_dir)
            
            # Determine the posts file to use
            posts_file = None
            
            # First priority: Check if user specified a posts folder directly
            if args.posts_folder:
                logger.info(f"Using specified posts folder: {args.posts_folder}")
                # Look for f1_posts.txt in the specified folder
                potential_posts_file = os.path.join(args.posts_folder, "f1_posts.txt")
                if os.path.exists(potential_posts_file):
                    posts_file = potential_posts_file
                    # Extract parent directory for setting the output structure
                    parent_dir = os.path.dirname(args.posts_folder)
                    if os.path.basename(parent_dir).replace("_", "").isdigit():  # Check if it's a timestamp folder
                        timestamp = os.path.basename(parent_dir)
                        # Create output structure based on the specified folder, but don't create new directories
                        new_output_structure = create_output_structure(args.output_dir, timestamp, create_dirs=False)
                        voiceovers_output_dir = new_output_structure["voiceovers_dir"]
                        # Update voiceover generator with the new output directory
                        voiceover_gen = VoiceoverGenerator(api_key=eleven_labs_api_key, output_dir=voiceovers_output_dir)
                else:
                    logger.error(f"No f1_posts.txt file found in the specified folder: {args.posts_folder}")
                    return 1
            # Second priority: Use the file from generated_files
            elif 'posts_file' in generated_files:
                posts_file = generated_files['posts_file']
            # Third priority: Use explicit posts_file argument if in voiceovers mode
            elif args.mode == "voiceovers" and hasattr(args, 'posts_file') and args.posts_file:
                posts_file = args.posts_file
            else:
                # Find posts file in the latest timestamp directory
                timestamp_dirs = [d for d in os.listdir(args.output_dir) 
                                if os.path.isdir(os.path.join(args.output_dir, d)) and not d.startswith('.')]
                
                if timestamp_dirs:
                    # Sort by timestamp
                    timestamp_dirs.sort(reverse=True)
                    latest_dir = os.path.join(args.output_dir, timestamp_dirs[0])
                    
                    # Check for posts file in the latest timestamp directory
                    posts_dir = os.path.join(latest_dir, "posts")
                    potential_posts_file = os.path.join(posts_dir, "f1_posts.txt")
                    if os.path.exists(potential_posts_file):
                        posts_file = potential_posts_file
                    else:
                        # Fall back to old structure
                        posts_files = [f for f in os.listdir(args.output_dir) if f.startswith("f1_posts_") and f.endswith(".txt")]
                        
                        if not posts_files:
                            logger.error(f"No posts files found in {args.output_dir}. Run post generation first.")
                            return 1
                        
                        # Sort by timestamp in filename
                        posts_files.sort(reverse=True)
                        posts_file = os.path.join(args.output_dir, posts_files[0])
                else:
                    # Fall back to old structure
                    posts_files = [f for f in os.listdir(args.output_dir) if f.startswith("f1_posts_") and f.endswith(".txt")]
                    
                    if not posts_files:
                        logger.error(f"No posts files found in {args.output_dir}. Run post generation first.")
                        return 1
                    
                    # Sort by timestamp in filename
                    posts_files.sort(reverse=True)
                    posts_file = os.path.join(args.output_dir, posts_files[0])
                
                logger.info(f"Using posts file: {posts_file}")
            
            # Generate voiceovers
            logger.info("Starting voiceover generation workflow...")
            voiceover_gen.generate_voiceovers_for_posts_file(posts_file)
            
        except Exception as e:
            logger.error(f"Error in voiceover generation: {str(e)}")
            if args.mode != "full-complete":  # Don't fail the whole workflow if just this part fails
                return 1
    
    logger.info("Workflow completed successfully!")
    return 0

if __name__ == "__main__":
    sys.exit(main()) 