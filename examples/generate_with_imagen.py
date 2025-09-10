#!/usr/bin/env python3
"""
Example script for generating text descriptions using Google's Gemini model.

Note: Google's Generative AI SDK doesn't currently support direct image generation.
This script demonstrates how to use the ImageGenerator class with the 'imagen' provider
to generate Formula 1 related text descriptions that could be used for image generation.
"""

import os
import sys
import argparse
import logging
from pathlib import Path

# Add the parent directory to the path so we can import from paddock_pulse
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paddock_pulse.image_generator import ImageGenerator

def main():
    """Generate a text description using Google's Gemini model."""
    parser = argparse.ArgumentParser(description="Generate F1 text descriptions using Google's Gemini model")
    parser.add_argument("--api-key", help="Google API key (overrides GOOGLE_API_KEY environment variable)")
    parser.add_argument("--prompt", default="A Formula 1 car racing through Monaco at sunset, photorealistic style", 
                        help="The prompt to use for text description generation")
    parser.add_argument("--output-dir", default="output/imagen_test", 
                        help="Directory to save the generated text (default: output/imagen_test)")
    parser.add_argument("--size", default="1024x1024", 
                        help="Size parameter (for compatibility, not actually used)")
    parser.add_argument("--aspect-ratio", default="1:1", 
                        help="Aspect ratio parameter (for compatibility, not actually used)")
    args = parser.parse_args()
    
    # Get the API key from the argument or environment variable
    google_key = args.api_key or os.environ.get("GOOGLE_API_KEY")
    if not google_key:
        print("Error: No Google API key provided. Please set GOOGLE_API_KEY environment variable or use --api-key")
        return 1
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Create output path
    output_path = os.path.join(args.output_dir, "imagen_test.jpg")
    
    # Initialize the image generator
    generator = ImageGenerator(
        api_key="not-used-for-imagen",  # Dummy value, not used for Imagen
        output_dir=args.output_dir,
        provider="imagen",
        google_key=google_key,
        size=args.size,
        aspect_ratio=args.aspect_ratio
    )
    
    # Generate the text description
    print(f"Generating text description with prompt: {args.prompt}")
    print("Note: This generates a text file, not an actual image.")
    text_path = generator.generate_image_from_prompt(args.prompt, output_path)
    
    if text_path:
        print(f"Successfully generated text description: {text_path}")
        try:
            # Display a portion of the generated text
            with open(text_path, 'r') as f:
                content = f.read()
                print("\nExcerpt of the generated content:")
                print("-" * 50)
                print(content[:400] + "..." if len(content) > 400 else content)
                print("-" * 50)
        except Exception as e:
            print(f"Could not read the generated text: {e}")
        return 0
    else:
        print("Failed to generate text description.")
        return 1

if __name__ == "__main__":
    sys.exit(main())