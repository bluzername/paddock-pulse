#!/usr/bin/env python
"""
HiveAI Demo Script

This script demonstrates how to use the HiveAI API for generating Formula 1 images.
"""

import os
import requests
import json
import logging
from pathlib import Path

# Setup basic logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("hiveai_demo")

# HiveAI API Key
HIVEAI_API_KEY = "GUW7pxBW503hGHTsAD3yyypkNB4zxPhn"
HIVEAI_MODEL = "hive/flux-schnell-enhanced"  # Updated model name with vendor

def generate_image_with_hiveai(prompt, output_path, width=768, height=1344, num_images=2):
    """
    Generate an image using HiveAI's flux-schnell-enhanced model.
    
    Args:
        prompt: The prompt to use for image generation
        output_path: Path where the image will be saved
        width: Image width (default: 768)
        height: Image height (default: 1344)
        num_images: Number of images to generate (default: 2)
        
    Returns:
        List of paths to the saved images or empty list if generation failed
    """
    logger.info(f"Generating HiveAI image with prompt: {prompt[:100]}...")
    
    # Create directory for image if it doesn't exist
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # HiveAI API endpoint for image generation
    url = "https://api.thehive.ai/api/v2/task/sync"  # Updated endpoint
    logger.info(f"Using API endpoint: {url}")
    logger.info(f"Using API key: {HIVEAI_API_KEY[:5]}...{HIVEAI_API_KEY[-5:]}")
    
    # Request headers - try different formats for authorization
    headers = {
        "Authorization": "Token " + HIVEAI_API_KEY,  # Use the required 'Token' format
        "Content-Type": "application/json"
    }
    
    # Request payload (updated based on docs)
    payload = {
        "model_name": HIVEAI_MODEL,
        "params": {
            "prompt": prompt,
            "width": width,
            "height": height,
            "num_outputs": num_images,
            "guidance_scale": 7.5,
            "num_inference_steps": 30
        }
    }
    
    logger.info(f"Request payload: {json.dumps(payload, indent=2)}")
    
    try:
        # Send request to HiveAI
        logger.info("Sending request to HiveAI API...")
        response = requests.post(url, headers=headers, json=payload, timeout=120)
        
        # Log response details
        logger.info(f"Response status code: {response.status_code}")
        logger.info(f"Response headers: {response.headers}")
        
        # Try to log response text even if not JSON
        try:
            response_text = response.text[:500]  # Limit to first 500 chars
            logger.info(f"Response text (truncated): {response_text}")
        except Exception as e:
            logger.warning(f"Could not log response text: {e}")
        
        if response.status_code != 200:
            logger.error(f"Error from HiveAI API: {response.status_code}, {response.text}")
            return []
        
        # Parse the response
        try:
            response_data = response.json()
        except Exception as e:
            logger.error(f"Error parsing JSON response: {e}")
            logger.error(f"Response text: {response.text[:500]}")
            return []
        
        # Save response to debug log
        debug_path = os.path.splitext(output_path)[0] + "_response.json"
        with open(debug_path, 'w') as f:
            json.dump(response_data, f, indent=2)
            logger.info(f"Saved API response to {debug_path}")
        
        # Check if generation was successful
        status = response_data.get("status", "")
        if status.lower() != "success":
            logger.error(f"HiveAI generation failed: {response_data}")
            return []
        
        # Get the list of image data
        outputs = response_data.get("output", [])
        if not outputs:
            logger.error("No images returned from HiveAI API")
            return []
        
        saved_images = []
        
        # Save all generated images
        for i, output in enumerate(outputs):
            image_url = output.get("image_url")  # Updated field name
            
            if not image_url:
                logger.warning(f"Missing image URL in output {i+1}")
                continue
            
            # Create unique path for each image if more than one is generated
            if i == 0:
                image_save_path = output_path
            else:
                # Add index to filename for additional images
                base_name, ext = os.path.splitext(output_path)
                image_save_path = f"{base_name}_{i+1}{ext}"
            
            # Save image
            try:
                response = requests.get(image_url, stream=True)
                if response.status_code == 200:
                    with open(image_save_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=1024):
                            f.write(chunk)
                    logger.info(f"Saved HiveAI image {i+1} to {image_save_path}")
                    saved_images.append(image_save_path)
                else:
                    logger.error(f"Failed to download image: {response.status_code}")
            except Exception as e:
                logger.error(f"Error downloading image: {str(e)}")
        
        return saved_images
        
    except Exception as e:
        logger.error(f"Error generating HiveAI image: {str(e)}")
        return []

def main():
    """Main function demonstrating HiveAI image generation."""
    # Create output directory
    output_dir = os.path.join("output", "hiveai_demo")
    os.makedirs(output_dir, exist_ok=True)
    
    # Example Formula 1 prompt (using the enhanced prompt format)
    prompt = """
    A professional sports photograph showing Formula 1 race victory, 
    at Circuit de Monaco, Monte Carlo, 
    during sunny conditions with clear blue skies, 
    featuring Ferrari car and driver with helmet, 
    showing a moment of celebration, 
    F1 race track, low angle tracking shot, 
    photorealistic, professional photography, 
    drivers with racing helmets on. 
    Clean scene with no text, no watermarks, no borders, 
    like a professional sports magazine cover shot.
    """
    
    # Generate image with HiveAI
    output_path = os.path.join(output_dir, "monaco_race_victory.png")
    saved_images = generate_image_with_hiveai(prompt, output_path)
    
    if saved_images:
        logger.info(f"Successfully generated {len(saved_images)} images!")
        for img_path in saved_images:
            logger.info(f"- {img_path}")
        return 0
    else:
        logger.warning("HiveAI image generation failed, would fall back to OpenAI in production")
        
        # Explanation for the user
        print("\n" + "*"*80)
        print("HIVEAI INTEGRATION EXPLANATION")
        print("*"*80)
        print("This demo script shows how to integrate with HiveAI's image generation API.")
        print("The API key provided may be expired or invalid, resulting in authentication errors.")
        print("\nTo properly implement this in image_generator.py:")
        print("1. Add the HiveAI provider option to the ImageGenerator class")
        print("2. Add appropriate error handling and fallback to other providers")
        print("3. Update the main() function to use HiveAI as default")
        print("\nHere's how to use it once implemented:")
        print("  python image_concat.py --provider hiveai --hiveai-key YOUR_API_KEY")
        print("\nThe implementation should include proper validation and error handling")
        print("to ensure reliable image generation even when one API fails.")
        print("*"*80)
        
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())


