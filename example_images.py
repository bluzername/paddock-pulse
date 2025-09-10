#!/usr/bin/env python3
"""
Example script to demonstrate the image generator with a sample post
"""

import os
import argparse
import colorama
from colorama import Fore, Style
from paddock_pulse.prompt_generator import PromptGenerator
from paddock_pulse.image_generator import ImageGenerator

# Initialize colorama for colored terminal output
colorama.init(autoreset=True)

# Sample F1 post
SAMPLE_POST_TITLE = "Mercedes' Masterclass in the Rain at Spa"
SAMPLE_POST_TEXT = """The Mercedes team showcased their wet-weather prowess once again with a dominant drive at Spa-Francorchamps! 🌧️ #BelgianGP

Starting from P3, the Silver Arrows expertly navigated treacherous conditions to take the lead by lap 10, demonstrating why they're considered one of F1's greatest rain specialists. 

The Mercedes driver built a commanding 22-second lead over Red Bull, who put in a stellar performance themselves to secure P2 despite challenging handling issues.

Ferrari rounded out the podium, benefiting from a perfectly timed pit stop as the rain intensity changed.

Mercedes' victory marks their 6th win at Spa and extends their championship lead. A truly masterful display of car control and tactical brilliance! 🏆 #F1 #Mercedes #F1Racing"""

# Output directory
OUTPUT_DIR = "example_output"

def main():
    """Generate images for a sample post"""
    parser = argparse.ArgumentParser(description="Generate images for a sample F1 post using OpenAI DALL-E")
    parser.add_argument("--api-key", required=True, help="OpenAI API key")
    parser.add_argument("--model", default="dall-e-3", help="OpenAI model to use (default: dall-e-3)")
    parser.add_argument("--size", default="1024x1024", help="Image size to generate (default: 1024x1024)")
    args = parser.parse_args()
    
    # Create the output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print(f"{Style.BRIGHT}Generating prompts and images for sample F1 post...\n")
    
    try:
        # Step 1: Generate prompts
        print(f"{Fore.CYAN}Step 1: Generating prompts")
        prompt_gen = PromptGenerator(output_dir=OUTPUT_DIR)
        post_prompts_dir = os.path.join(OUTPUT_DIR, "sample_post_prompts")
        prompts = prompt_gen.generate_prompts_for_post(SAMPLE_POST_TEXT, SAMPLE_POST_TITLE, post_prompts_dir)
        
        print(f"\n{Fore.GREEN}Generated {len(prompts)} image prompts for the sample post:\n")
        for i, prompt in enumerate(prompts):
            print(f"{Fore.YELLOW}PROMPT {i+1}:")
            print("-" * 80)
            print(prompt)
            print("-" * 80)
            print()
        
        # Step 2: Generate images from prompts
        print(f"{Fore.CYAN}Step 2: Generating images with DALL-E")
        
        try:
            image_gen = ImageGenerator(api_key=args.api_key, output_dir=OUTPUT_DIR, model=args.model, size=args.size)
            post_images_dir = os.path.join(OUTPUT_DIR, "sample_post_images")
            image_paths = image_gen.generate_images_for_post(prompts, SAMPLE_POST_TITLE, post_images_dir)
            
            if image_paths:
                print(f"\n{Fore.GREEN}Successfully generated {len(image_paths)} images for the sample post:\n")
                for i, image_path in enumerate(image_paths):
                    print(f"{Fore.CYAN}IMAGE {i+1}: {image_path}")
            else:
                print(f"\n{Fore.RED}Failed to generate any images. Check your API key and try again.")
        except Exception as e:
            print(f"\n{Fore.RED}Error generating images: {str(e)}")
            print(f"{Fore.YELLOW}This may be due to an issue with the OpenAI API or your API key.")
        
        print(f"\n{Fore.CYAN}Prompt files saved to: {post_prompts_dir}")
        if 'post_images_dir' in locals():
            print(f"{Fore.CYAN}Image files saved to: {post_images_dir}")
    
    except Exception as e:
        print(f"\n{Fore.RED}Error: {str(e)}")
    
if __name__ == "__main__":
    main() 