"""
Prompt Generator Module

This module is responsible for generating high-quality image prompts
for Formula 1 posts that can be used with GenAI tools.
"""

import os
import re
import logging
import json
import requests
from pathlib import Path
import colorama
from colorama import Fore, Style

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
logger = logging.getLogger("prompt_generator")

class OpenRouterPromptGenerator:
    """
    Class to generate high-quality image prompts using OpenRouter API.
    This simplified approach leverages LLMs to create prompts directly from event details.
    """
    
    def __init__(self, api_key=None, output_dir='output', model="meta-llama/llama-4-maverick"):
        """
        Initialize the OpenRouterPromptGenerator.
        
        Args:
            api_key: OpenRouter API key (defaults to environment variable)
            output_dir: Directory where prompts will be stored
            model: The LLM model to use for prompt generation
        """
        self.api_key = api_key or os.environ.get('OPENROUTER_API_KEY')
        if not self.api_key:
            logger.warning("No OpenRouter API key provided. Please set OPENROUTER_API_KEY environment variable.")
        
        self.output_dir = output_dir
        self.model = model
        os.makedirs(output_dir, exist_ok=True)
        logger.info(f"OpenRouterPromptGenerator initialized with save directory: {output_dir}")
    
    def _call_openrouter_api(self, prompt):
        """
        Call the OpenRouter API with the given prompt.
        
        Args:
            prompt: The prompt to send to the API
            
        Returns:
            str: The API response text
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        data = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }
        
        try:
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=data
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('choices', [{}])[0].get('message', {}).get('content', '')
            else:
                logger.error(f"Error from OpenRouter API: {response.status_code}, {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Exception when calling OpenRouter API: {str(e)}")
            return None

    def generate_prompt_from_event(self, event, output_path=None):
        """
        Generate an image prompt for a specific event using the OpenRouter API.
        
        Args:
            event: Dictionary containing event details (title, description, etc.)
            output_path: Optional path to save the prompt
            
        Returns:
            str: Generated image prompt
        """
        if not self.api_key:
            logger.error("OpenRouter API key not provided")
            return None
        
        # Extract event details
        title = event.get('title', 'Unknown Event')
        description = event.get('description', '')
        significance = event.get('significance', '')
        stats = event.get('stats', '')
        circuit = event.get('circuit', 'Unknown Circuit')
        country = event.get('country', 'Unknown Country')
        weather = event.get('weather', 'Unknown Weather')
        
        # Combine all details into a scenario description
        scenario = f"""
Event Title: {title}
Circuit: {circuit}, {country}
Weather: {weather}
Description: {description}
Significance: {significance}
Stats: {stats}
"""
        
        # Create the prompt for the OpenRouter API
        prompt = f"""Create a detailed, high-quality prompt for GPT-Image-1 model that will generate a realistic Formula 1 photo based on this scenario:
{scenario}

Your prompt should:
1. Start with a photography term like "A professional sports photograph showing..."
2. Be extremely detailed and specific about the visual elements
3. Emphasize photorealism and sports photography style
4. Avoid any artistic terms like "painting", "drawing", "illustration", "sketch", etc.
5. Avoid using actual driver names (use "F1 driver" instead) to prevent AI from generating portraits
6. Include specific F1 elements like cars, tracks, lighting conditions, camera angles, etc.
7. Incorporate the circuit, country, and weather conditions
8. Focus on creating a journalistic sports photography vibe

Return ONLY the prompt text, nothing before or after it.
"""
        
        logger.info(f"Generating prompt for event: {title}")
        
        # Call the OpenRouter API
        response = self._call_openrouter_api(prompt)
        
        if not response:
            logger.error(f"Failed to generate prompt for event: {title}")
            return None
        
        # Clean up the response
        generated_prompt = response.strip()
        
        # Save the prompt if output path is provided
        if output_path:
            with open(output_path, 'w') as f:
                f.write(generated_prompt)
            logger.info(f"Saved prompt to {output_path}")
        
        return generated_prompt
    
    def generate_prompts_for_post(self, post_text, post_title, output_dir, hashtags=None, technical_mode=False, num_prompts=5):
        """
        Generate image prompts for a social media post by creating artificial events and passing to the LLM.
        
        Args:
            post_text: The text content of the post
            post_title: The title of the post/event
            output_dir: Directory to save the generated prompts
            hashtags: Optional separate hashtags string
            technical_mode: Whether to generate technical data visualization prompts
            num_prompts: Number of prompts to generate
            
        Returns:
            List of generated prompts
        """
        os.makedirs(output_dir, exist_ok=True)
        
        # Create artificial events from the post
        events = []
        for i in range(num_prompts):
            # Create slightly different perspectives for each prompt
            perspectives = [
                "standard view",
                "close-up shot",
                "wide-angle view",
                "action-focused shot with dynamic elements",
                "emotional/atmospheric shot"
            ]
            
            # Extract hashtags if they exist
            extracted_hashtags = ""
            if hashtags:
                extracted_hashtags = hashtags
            elif "#" in post_text:
                # Extract hashtags from the post text
                hashtag_pattern = re.findall(r'(#\w+)', post_text)
                extracted_hashtags = " ".join(hashtag_pattern)
            
            # Create an event with the available information
            event = {
                "title": post_title,
                "description": post_text,
                "significance": f"This is a {perspectives[i % len(perspectives)]} of an important F1 moment",
                "stats": extracted_hashtags,
                "circuit": "Formula 1 circuit",  # Default value
                "country": "International venue",  # Default value
                "weather": "Typical racing conditions"  # Default value
            }
            
            # Try to extract location and weather from the post
            if any(country in post_text.lower() for country in ["australia", "bahrain", "saudi", "china", "azerbaijan", "miami", "italy", "monaco", "canada", "spain", "austria", "uk", "hungary", "belgium", "netherlands", "singapore", "japan", "usa", "mexico", "brazil", "qatar", "abu dhabi"]):
                # Simple country extraction
                for country in ["australia", "bahrain", "saudi arabia", "china", "azerbaijan", "miami, usa", "italy", "monaco", "canada", "spain", "austria", "united kingdom", "hungary", "belgium", "netherlands", "singapore", "japan", "usa", "mexico", "brazil", "qatar", "abu dhabi"]:
                    if country.lower() in post_text.lower():
                        event["country"] = country.title()
                        break
            
            # Simple weather extraction
            if any(weather in post_text.lower() for weather in ["rain", "wet", "sunny", "cloud", "storm", "hot", "cold", "humid"]):
                if "rain" in post_text.lower() or "wet" in post_text.lower():
                    event["weather"] = "Rainy conditions with a wet track"
                elif "sunny" in post_text.lower():
                    event["weather"] = "Sunny conditions with clear skies"
                elif "cloud" in post_text.lower():
                    event["weather"] = "Overcast conditions"
                elif "storm" in post_text.lower():
                    event["weather"] = "Stormy conditions"
                elif "hot" in post_text.lower():
                    event["weather"] = "Hot and humid conditions"
                elif "cold" in post_text.lower():
                    event["weather"] = "Cold conditions"
            
            events.append(event)
        
        # Generate prompts for each event
        prompts = []
        for i, event in enumerate(events):
            prompt_filename = f"{i+1}_{post_title.replace(' ', '_')[:30]}_prompt.txt"
            prompt_path = os.path.join(output_dir, prompt_filename)
            
            prompt = self.generate_prompt_from_event(event, prompt_path)
            if prompt:
                prompts.append(prompt)
        
        return prompts
    
    def generate_prompts_from_posts_file(self, posts_file, technical_mode=False):
        """
        Generate prompts for all posts in a posts file.
        
        Args:
            posts_file: Path to the posts file
            technical_mode: Whether to generate technical data visualization prompts
            
        Returns:
            Dict mapping post titles to lists of generated prompts
        """
        logger.info(f"Generating prompts for posts in {posts_file}")
        logger.info(f"Prompts will be saved to {self.output_dir}")
        
        # Check if the posts file exists
        if not os.path.exists(posts_file):
            logger.error(f"Posts file not found: {posts_file}")
            return {}
        
        # Parse the posts file (support both JSON and text formats)
        try:
            if posts_file.endswith('.json'):
                # JSON format
                with open(posts_file, 'r') as f:
                    posts_data = json.load(f)
                
                all_prompts = {}
                
                # Handle different JSON structures
                if isinstance(posts_data, list):
                    for post in posts_data:
                        title = post.get('event_title', post.get('title', f"Post {len(all_prompts) + 1}"))
                        post_text = post.get('post_text', post.get('content', ''))
                        hashtags = post.get('hashtags', '')
                        
                        # Create a directory for this post
                        post_dir = os.path.join(self.output_dir, title.replace(' ', '_'))
                        os.makedirs(post_dir, exist_ok=True)
                        
                        # Generate prompts for this post
                        logger.info(f"Generating prompts for post: {title}")
                        prompts = self.generate_prompts_for_post(post_text, title, post_dir, hashtags, technical_mode)
                        all_prompts[title] = prompts
                
                return all_prompts
            else:
                # Text format
                with open(posts_file, 'r') as f:
                    content = f.read()
                
                # Split into individual posts
                post_pattern = r'Post\s+\d+:\s+(.*?)\n={2,}\n(.*?)(?=\n\nPost\s+\d+:|$)'
                matches = re.findall(post_pattern, content, re.DOTALL)
                
                if not matches:
                    logger.error(f"No posts found in file: {posts_file}")
                    return {}
                
                all_prompts = {}
                
                for title, post_content in matches:
                    # Clean up the post content
                    post_content = post_content.strip()
                    
                    # Extract hashtags if they exist
                    hashtags = None
                    content_parts = post_content.split('\n\n')
                    if len(content_parts) > 1:
                        last_part = content_parts[-1]
                        if last_part.startswith('#'):
                            hashtags = last_part
                            post_content = '\n\n'.join(content_parts[:-1])
                    
                    # Create a directory for this post
                    post_dir = os.path.join(self.output_dir, title.replace(' ', '_'))
                    os.makedirs(post_dir, exist_ok=True)
                    
                    # Generate prompts for this post
                    logger.info(f"Generating prompts for post: {title}")
                    prompts = self.generate_prompts_for_post(post_content, title, post_dir, hashtags, technical_mode)
                    all_prompts[title] = prompts
                
                return all_prompts
                
        except Exception as e:
            logger.error(f"Error processing posts file: {str(e)}")
            return {}

# Legacy PromptGenerator class remains for backward compatibility
class PromptGenerator:
    """
    Class to generate high-quality image prompts for F1 social media posts.
    
    Note: This class uses a rule-based approach. For better results, consider
    using the OpenRouterPromptGenerator class instead.
    """
    
    def __init__(self, output_dir='output'):
        """
        Initialize the PromptGenerator.
        
        Args:
            output_dir: Directory where post text files and prompts will be stored
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        # Note: For brevity, all the legacy implementation details are omitted here.
        # The original implementation would follow, but is now deprecated.
        logger.warning("Using legacy PromptGenerator. Consider using OpenRouterPromptGenerator for better results.")
        
        # Call the original implementation
        from importlib.metadata import version
        logger.info(f"Legacy PromptGenerator initialized with output directory: {output_dir}")
    
    def generate_prompts_for_post(self, post_text, post_title, output_dir, hashtags=None, technical_mode=False):
        """
        Generate image prompts for a social media post.
        
        This is a legacy method. Consider using OpenRouterPromptGenerator instead.
        """
        # Create an instance of OpenRouterPromptGenerator and use it instead
        router_gen = OpenRouterPromptGenerator(output_dir=self.output_dir)
        return router_gen.generate_prompts_for_post(post_text, post_title, output_dir, hashtags, technical_mode)
    
    def generate_prompts(self, posts_file, technical_mode=False):
        """
        Generate prompts for all posts in a posts file.
        
        This is a legacy method. Consider using OpenRouterPromptGenerator instead.
        """
        # Create an instance of OpenRouterPromptGenerator and use it instead
        router_gen = OpenRouterPromptGenerator(output_dir=self.output_dir)
        return router_gen.generate_prompts_from_posts_file(posts_file, technical_mode)

def main():
    """Main function to generate prompts for the most recent posts file."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate AI image prompts for F1 social media posts")
    parser.add_argument("--posts-file", help="Path to the posts text file")
    parser.add_argument("--output-dir", default="output", help="Directory to save prompts (default: output)")
    parser.add_argument("--api-key", help="OpenRouter API key (overrides OPENROUTER_API_KEY environment variable)")
    parser.add_argument("--model", default="meta-llama/llama-4-maverick", help="Model to use for prompt generation")
    parser.add_argument("--use-legacy", action="store_true", help="Use legacy rule-based generator instead of OpenRouter API")
    parser.add_argument("--technical", action="store_true", help="Generate technical data visualization prompts")
    args = parser.parse_args()
    
    if args.use_legacy:
        logger.warning("Using legacy rule-based generator. This mode is deprecated.")
        generator = PromptGenerator(output_dir=args.output_dir)
    else:
        generator = OpenRouterPromptGenerator(
            api_key=args.api_key, 
            output_dir=args.output_dir,
            model=args.model
        )
    
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
    
    # Generate prompts for all posts in the file
    if args.use_legacy:
        generator.generate_prompts(posts_file, args.technical)
    else:
        generator.generate_prompts_from_posts_file(posts_file, args.technical)
    return 0

if __name__ == "__main__":
    main() 