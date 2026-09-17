"""
Image Generator Module

This module is responsible for generating images using OpenAI's GPT-Image-1 model (default)
based on prompts created for Formula 1 posts.

It also supports:
- OpenAI's DALL-E model
- Midjourney image generation via GoAPI
- Google's Gemini API for text descriptions
- HiveAI's Flux Schnell Enhanced model
"""

import os
import re
import sys
import logging
import json
import base64
from pathlib import Path
import requests
from urllib.parse import quote_plus
from openai import OpenAI
import httpx
import colorama
from colorama import Fore, Style
import time
from datetime import datetime
from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
    retry_if_exception_type,
    wait_exponential,
    RetryError
)
import google.generativeai as genai
from paddock_pulse.prompt_generator import OpenRouterPromptGenerator

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
logger = logging.getLogger("image_generator")

def validate_api_key(api_key, provider="openai"):
    """
    Validate that an API key is not a placeholder.
    
    Args:
        api_key: API key to validate
        provider: The API provider (openai, goapi, google, or hiveai)
        
    Returns:
        tuple: (is_valid, message) where is_valid is a boolean and message is a string
    """
    if not api_key:
        return False, "API key is empty or None"
    
    # Check if key is a placeholder
    placeholder_patterns = [
        "your", "api", "key", "openai", "sk-your", "example", "place", "holder",
        "demo", "test", "change", "replace"
    ]
    
    for pattern in placeholder_patterns:
        if pattern.lower() in api_key.lower():
            return False, f"API key appears to be a placeholder (contains '{pattern}')"
    
    # Provider-specific validation
    if provider == "openai":
        # Check for proper format
        if not api_key.startswith("sk-"):
            return False, "OpenAI API key should start with 'sk-'"
        
        # Check reasonable length
        if len(api_key) < 20:
            return False, "API key is too short"
    elif provider == "google":
        # Check for proper format for Google API keys
        if not api_key.startswith("AIza"):
            return False, "Google API key should start with 'AIza'"
        
        # Check reasonable length
        if len(api_key) < 30:
            return False, "Google API key is too short"
    elif provider == "hiveai":
        # HiveAI keys are typically alphanumeric
        if len(api_key) < 20:
            return False, "HiveAI API key appears to be too short"
    
    return True, "API key appears valid"

def is_rate_limit_error(exception):
    """Check if the exception is a rate limit error."""
    error_str = str(exception)
    return (
        "rate_limit_exceeded" in error_str.lower() or
        "too many requests" in error_str.lower() or
        "429" in error_str or
        "rate limit" in error_str.lower()
    )

class ImageGenerator:
    """
    Class to generate images using OpenAI's GPT-Image-1 model (default),
    OpenAI's DALL-E model, Midjourney via GoAPI, Google's Imagen, or
    HiveAI's Flux Schnell Enhanced model for F1 social media posts.
    """
    
    def __init__(self, api_key=None, output_dir='output', model="gpt-image-1", size="1024x1536", 
                 provider="openai", goapi_key=None, google_key=None, hiveai_key=None, aspect_ratio="16:9", 
                 num_images=2, quality="standard", style="vivid"):
        """
        Initialize the ImageGenerator.
        
        Args:
            api_key: API key (used if provider-specific key not provided)
            output_dir: Directory where images will be stored
            model: Model to use (default: 'gpt-image-1' for OpenAI)
            size: Image size to generate (default: 1024x1536 for OpenAI)
            provider: Image generation provider ('openai', 'hiveai', 'midjourney', or 'imagen')
            goapi_key: GoAPI API key (used if provider is 'midjourney')
            google_key: Google API key (used if provider is 'imagen')
            hiveai_key: HiveAI API key (used if provider is 'hiveai')
            aspect_ratio: Aspect ratio for images (default: "16:9", other options: "1:1", "4:3", etc.)
            num_images: Number of images to generate per prompt (default: 2)
            quality: Quality of DALL-E images (standard or hd)
            style: Style of DALL-E images (vivid or natural)
        """
        self.output_dir = output_dir
        self.provider = provider.lower()
        self.goapi_key = goapi_key
        self.google_key = google_key
        self.hiveai_key = hiveai_key or os.environ.get("HIVEAI_API_KEY")
        self.aspect_ratio = aspect_ratio
        self.num_images = num_images
        self.quality = quality
        self.style = style
        
        os.makedirs(output_dir, exist_ok=True)
        
        if self.provider == "openai":
            # Validate API key
            is_valid, message = validate_api_key(api_key, "openai")
            if not is_valid:
                logger.error(f"Invalid API key: {message}")
                logger.error(f"API key starts with: '{api_key[:10]}...'")
                raise ValueError(f"Invalid OpenAI API key: {message}")
            
            logger.info(f"API key validation passed: {message}")
            
            # Create custom HTTP client without proxies
            http_client = httpx.Client(timeout=60.0)
            
            # Create OpenAI client with custom HTTP client
            try:
                # Double-check that the API key is set properly before creating the client
                logger.debug(f"API key type: {type(api_key)}")
                logger.debug(f"API key length: {len(api_key)}")
                logger.debug(f"API key prefix: {api_key[:4]}...")
                
                self.client = OpenAI(
                    api_key=api_key,
                    http_client=http_client
                )
                logger.info("Successfully initialized OpenAI client")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {str(e)}")
                logger.error(f"API key prefix: {api_key[:4]}...")
                raise
            
            self.model = model
            self.size = size
            
            # Check if API key is valid
            if not api_key:
                logger.error("No OpenAI API key provided. Image generation will fail.")
                
        elif self.provider == "midjourney":
            if not goapi_key:
                logger.error("No GoAPI key provided. Midjourney image generation will fail.")
                raise ValueError("GoAPI key required for Midjourney integration")
                
            logger.info("Successfully initialized Midjourney via GoAPI")
            self.model = "midjourney"
            self.size = size
            
        elif self.provider == "imagen":
            if not google_key:
                logger.error("No Google API key provided. Imagen image generation will fail.")
                raise ValueError("Google API key required for Imagen integration")
            
            # Validate Google API key
            is_valid, message = validate_api_key(google_key, "google")
            if not is_valid:
                logger.error(f"Invalid Google API key: {message}")
                logger.error(f"API key starts with: '{google_key[:10]}...'")
                raise ValueError(f"Invalid Google API key: {message}")
            
            try:
                # Configure the Google AI client
                genai.configure(api_key=google_key)
                logger.info("Successfully initialized Google Imagen client")
            except Exception as e:
                logger.error(f"Failed to initialize Google Imagen client: {str(e)}")
                raise
            
            # Don't set self.model = "imagen" here, as we'll use the full model path in the API call
            self.size = size
            
        elif self.provider == "hiveai":
            if not self.hiveai_key:
                logger.error("No HiveAI API key provided. HiveAI image generation will fail.")
                raise ValueError("HiveAI API key required for HiveAI integration")
            
            # Validate HiveAI API key
            is_valid, message = validate_api_key(self.hiveai_key, "hiveai")
            if not is_valid:
                logger.error(f"Invalid HiveAI API key: {message}")
                logger.error(f"API key starts with: '{self.hiveai_key[:10]}...'")
                raise ValueError(f"Invalid HiveAI API key: {message}")
            
            # Parse model name to format for API
            if model in ["flux-schnell", "flux-schnell-enhanced"]:
                if model == "flux-schnell":
                    self.hiveai_model = "flux-schnell"
                else:
                    self.hiveai_model = "flux-schnell-enhanced"
            elif model in ["sdxl", "sdxl-enhanced"]:
                if model == "sdxl":
                    self.hiveai_model = "sdxl"
                else:
                    self.hiveai_model = "sdxl-enhanced"
            else:
                # Default to flux-schnell-enhanced if model not recognized
                self.hiveai_model = "flux-schnell-enhanced"
                
            logger.info(f"Using HiveAI model: {self.hiveai_model}")
            self.model = model
            
            # Parse size string to get width and height
            if "x" in size:
                width, height = map(int, size.split("x"))
                self.width = width
                self.height = height
            else:
                # Default to 768x1344 if size format is invalid
                self.width = 768
                self.height = 1344
                logger.warning(f"Invalid size format: {size}, using default 768x1344")
                
            logger.info(f"Image size set to: {self.width}x{self.height}")
            logger.info("Successfully initialized HiveAI client")
            
        else:
            raise ValueError(f"Unsupported provider: {provider}. Use 'openai', 'hiveai', 'midjourney', or 'imagen'")

    def _save_image(self, image_url, output_path):
        """
        Download and save an image from a URL.
        
        Args:
            image_url: URL of the image to download
            output_path: Path where the image will be saved
            
        Returns:
            True if download was successful, False otherwise
        """
        try:
            response = requests.get(image_url, stream=True)
            if response.status_code == 200:
                with open(output_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=1024):
                        f.write(chunk)
                return True
            else:
                logger.error(f"Failed to download image: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Error downloading image: {str(e)}")
            return False
    
    def _save_b64_image(self, b64_json, output_path):
        """
        Save an image from base64 JSON data.
        
        Args:
            b64_json: Base64 encoded image data
            output_path: Path where the image will be saved
            
        Returns:
            True if save was successful, False otherwise
        """
        try:
            with open(output_path, 'wb') as f:
                f.write(base64.b64decode(b64_json))
            return True
        except Exception as e:
            logger.error(f"Error saving base64 image: {str(e)}")
            return False

    @retry(
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.ConnectTimeout)), 
        wait=wait_exponential(multiplier=1, min=2, max=60),
        stop=stop_after_attempt(5),
        before_sleep=lambda retry_state: logger.warning(
            f"Rate limited or connection error. Retrying in {retry_state.next_action.sleep} seconds. "
            f"Attempt {retry_state.attempt_number}/{5}")
    )
    def _call_gpt_image_1_api(self, prompt, size):
        """Make API call to GPT-Image-1 with retry logic."""
        try:
            response = self.client.images.generate(
                model="gpt-image-1",
                prompt=prompt,
                size=size,
                n=1
            )
            return response
        except Exception as e:
            if is_rate_limit_error(e):
                logger.warning(f"Rate limit exceeded, retrying... Error: {str(e)}")
                raise
            raise

    def generate_image_from_prompt_gpt_image_1(self, prompt, output_path):
        """
        Generate an image using OpenAI's GPT-Image-1 model.
        
        Args:
            prompt: The prompt to use for image generation
            output_path: Path where the image will be saved
            
        Returns:
            Path to the saved image or None if generation failed
        """
        logger.info(f"Generating GPT-Image-1 image with prompt: {prompt[:100]}...")
        
        # Handle size format for GPT-Image-1
        size_regex = r"^(\d+)x(\d+)$"
        size_match = re.match(size_regex, self.size)
        
        if not size_match:
            logger.warning(f"Invalid size format for GPT-Image-1: {self.size}. Using default 1024x1024.")
            width, height = 1024, 1024
        else:
            width, height = int(size_match.group(1)), int(size_match.group(2))
            
            # Validate size limits for GPT-Image-1
            if width < 128 or width > 4096 or height < 128 or height > 4096:
                logger.warning(f"Size {width}x{height} outside GPT-Image-1 limits. Using default 1024x1024.")
                width, height = 1024, 1024
        
        # Define retry configuration for rate limiting
        @retry(
            retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.ConnectTimeout)), 
            wait=wait_exponential(multiplier=1, min=2, max=60),
            stop=stop_after_attempt(5),
            before_sleep=lambda retry_state: logger.warning(
                f"Rate limited or connection error. Retrying in {retry_state.next_action.sleep} seconds. "
                f"Attempt {retry_state.attempt_number}/{5}")
        )
        def call_api_with_retry():
            try:
                # Call OpenAI API to generate image using GPT-Image-1
                response = self.client.images.generate(
                    model="gpt-image-1",
                    prompt=prompt,
                    size=f"{width}x{height}",
                    n=1,
                )
                
                # Extract image URL from response
                image_url = response.data[0].url
                
                # Check if image URL is None (common with organization verification issues)
                if image_url is None:
                    logger.error("Received None as image URL in GPT-Image-1 response.")
                    logger.error("This usually indicates your organization hasn't been verified for GPT-Image-1 access.")
                    logger.error("Please verify your organization at: https://platform.openai.com/settings/organization")
                    logger.error("You may need to add a payment method and wait up to 24 hours after verification.")
                    logger.error("In the meantime, set SKIP_GPT_IMAGE_1=true as an environment variable to use DALL-E 3 instead.")
                    logger.info("Falling back to DALL-E 3 for this request...")
                    
                    # Try with DALL-E 3 as fallback
                    original_model = self.model
                    self.model = "dall-e-3"
                    result = self.generate_image_from_prompt_openai(prompt, output_path)
                    self.model = original_model
                    return result
                
                return image_url
                
            except httpx.HTTPStatusError as e:
                # Handle API-specific errors
                status_code = e.response.status_code
                if status_code == 429:
                    # Rate limit error - this will be retried
                    logger.warning(f"Rate limit exceeded (429). Response: {e.response.text}")
                    raise e
                elif status_code == 401:
                    # Authentication error - no need to retry
                    logger.error(f"Authentication error (401): {e.response.text}")
                    # Fall back to DALL-E
                    logger.info("Authentication error with GPT-Image-1. Falling back to DALL-E 3...")
                    original_model = self.model
                    self.model = "dall-e-3"
                    result = self.generate_image_from_prompt_openai(prompt, output_path)
                    self.model = original_model
                    return result
                else:
                    # Other HTTP errors - will be retried
                    logger.error(f"HTTP error {status_code}: {e.response.text}")
                    raise e
            except Exception as e:
                # Other unexpected errors
                logger.error(f"Unexpected error in GPT-Image-1 API call: {str(e)}")
                raise e
        
        try:
            # Call the API with retry logic
            image_url = call_api_with_retry()
            
            # If None was returned, it means we've already handled the error and fallen back
            if image_url is None:
                return None
                
            # If image_url is a file path, it means we've already fallen back to DALL-E and saved the image
            if isinstance(image_url, str) and os.path.exists(image_url):
                return image_url
                
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Save image to output path
            if self._save_image(image_url, output_path):
                logger.info(f"Saved GPT-Image-1 image to {output_path}")
                return output_path
            else:
                logger.error(f"Failed to save GPT-Image-1 image to {output_path}")
                return None
                
        except RetryError:
            # All retries exhausted
            logger.error("All retry attempts failed for GPT-Image-1. Falling back to DALL-E 3...")
            original_model = self.model
            self.model = "dall-e-3"
            result = self.generate_image_from_prompt_openai(prompt, output_path)
            self.model = original_model
            return result
            
        except Exception as e:
            logger.error(f"Error generating GPT-Image-1 image: {str(e)}")
            
            # Fall back to DALL-E 3
            logger.info("Falling back to DALL-E 3...")
            original_model = self.model
            self.model = "dall-e-3"
            result = self.generate_image_from_prompt_openai(prompt, output_path)
            self.model = original_model
            return result
    
    def generate_image_from_prompt(self, prompt, output_path, allow_fallback=True):
        """
        Generate an image from a prompt, using the provider specified during initialization.
        
        Args:
            prompt: The prompt to use for image generation
            output_path: Path where the image will be saved
            allow_fallback: Whether to allow fallback to another provider if the primary one fails
            
        Returns:
            Path to the saved image or None if generation failed
        """
        try:
            # Check if we should skip GPT-Image-1 attempts based on environment variable
            skip_gpt_image_1 = os.environ.get("SKIP_GPT_IMAGE_1", "").lower() in ("true", "1", "yes")
            if skip_gpt_image_1 and self.model == "gpt-image-1":
                logger.info("Skipping GPT-Image-1 attempt as SKIP_GPT_IMAGE_1 is set. Using DALL-E 3 instead.")
                original_model = self.model
                self.model = "dall-e-3" 
                result = self.generate_image_from_prompt_openai(prompt, output_path)
                self.model = original_model
                return result
                
            # Generate image based on provider
            if self.provider == "openai":
                return self.generate_image_from_prompt_openai(prompt, output_path)
            elif self.provider == "google":
                return self.generate_image_from_prompt_google(prompt, output_path)
            elif self.provider == "midjourney":
                return self.generate_image_from_prompt_midjourney(prompt, output_path)
            elif self.provider == "hiveai":
                return self.generate_image_from_prompt_hiveai(prompt, output_path)
            else:
                logger.error(f"Unsupported provider: {self.provider}")
                
                # Fall back to OpenAI if fallback is allowed
                if allow_fallback:
                    logger.info(f"Falling back to OpenAI for image generation")
                    original_provider = self.provider
                    self.provider = "openai"
                    result = self.generate_image_from_prompt_openai(prompt, output_path)
                    self.provider = original_provider
                    return result
                
                return None
                
        except Exception as e:
            logger.error(f"Error generating image: {str(e)}")
            return None
            
    def generate_image_from_prompt_openai(self, prompt, output_path):
        """
        Generate an image using OpenAI's image generation models (GPT-Image-1, DALL-E 2/3).
        
        Args:
            prompt: The prompt to use for image generation
            output_path: Path where the image will be saved
            
        Returns:
            Path to the saved image or None if generation failed
        """
        try:
            # Check if we should skip GPT-Image-1 attempts based on environment variable
            skip_gpt_image_1 = os.environ.get("SKIP_GPT_IMAGE_1", "").lower() in ("true", "1", "yes")
            
            # Check if model is GPT-Image-1 and not skipped
            if self.model == "gpt-image-1" and not skip_gpt_image_1:
                return self.generate_image_from_prompt_gpt_image_1(prompt, output_path)
                
            # For all other OpenAI models or if GPT-Image-1 should be skipped
            if self.model == "gpt-image-1" and skip_gpt_image_1:
                logger.info("Skipping GPT-Image-1 as requested by environment variable. Using DALL-E 3 instead.")
                model = "dall-e-3"
            else:
                model = self.model
                
            logger.info(f"Generating {model} image with prompt: {prompt[:100]}...")
            
            # Configure API call parameters based on model
            api_params = {
                "model": model,
                "prompt": prompt,
                "size": self.size,
                "n": 1,
            }
            
            # Add DALL-E specific parameters if using DALL-E models
            if model.startswith("dall-e"):
                api_params["quality"] = self.quality
                api_params["style"] = self.style
                
            # Call OpenAI API to generate image
            response = self.client.images.generate(**api_params)
            
            # Extract image URL from response
            image_url = response.data[0].url
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Save image to output path
            if self._save_image(image_url, output_path):
                logger.info(f"Saved {model} image to {output_path}")
                return output_path
            else:
                logger.error(f"Failed to save {model} image to {output_path}")
                return None
                
        except Exception as e:
            logger.error(f"Error generating image with OpenAI: {str(e)}")
            return None

    def generate_image_from_prompt_hiveai(self, prompt, output_path):
        """
        Generate an image using HiveAI's V3 API.
        
        Args:
            prompt: The prompt to use for image generation
            output_path: Path where the image will be saved
            
        Returns:
            Path to the saved image or None if generation failed
        """
        try:
            logger.info(f"Generating HiveAI image with prompt: {prompt[:100]}...")
            
            # HiveAI API endpoint for image generation
            url = "https://api.thehive.ai/api/v2/generation/image"
            
            # Request headers
            headers = {
                "Authorization": f"Token {self.hiveai_key}",
                "Content-Type": "application/json"
            }
            
            # Request payload
            payload = {
                "image_generation": {
                    "prompt": prompt,
                    "width": self.width,
                    "height": self.height,
                    "num_images": self.num_images,
                    "model": self.hiveai_model
                }
            }
            
            logger.debug(f"Request payload: {json.dumps(payload, indent=2)}")
            
            # Send request to HiveAI
            response = requests.post(url, headers=headers, json=payload, timeout=120)
            
            if response.status_code != 200:
                error_msg = f"Error from HiveAI API: {response.status_code}, {response.text}"
                logger.error(error_msg)
                raise Exception(f"HiveAI image generation failed: {error_msg}")
            
            # Parse response JSON
            response_data = response.json()
            logger.debug(f"Response data: {json.dumps(response_data, indent=2)}")
            
            # Get the list of image data from the response
            status = response_data.get("status", {}).get("status", "")
            
            if status != "DONE":
                error_msg = f"HiveAI API returned non-success status: {status}"
                logger.error(error_msg)
                raise Exception(f"HiveAI image generation failed: {error_msg}")
            
            # Get the list of generated images
            images = response_data.get("result", {}).get("images", [])
            
            if not images:
                error_msg = "No images returned from HiveAI API"
                logger.error(error_msg)
                raise Exception(f"HiveAI image generation failed: {error_msg}")
            
            # Create directory for image if it doesn't exist
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            saved_images = []
            
            # Save all generated images
            for i, image_data in enumerate(images):
                image_url = image_data.get("url")
                
                if not image_url:
                    logger.warning(f"Missing image URL in output {i+1}")
                    continue
                
                # Create unique path for each image if more than one is generated
                if i == 0:
                    current_output_path = output_path
                else:
                    file_name, file_ext = os.path.splitext(output_path)
                    current_output_path = f"{file_name}_{i+1}{file_ext}"
                
                # Save the image
                if self._save_image(image_url, current_output_path):
                    logger.info(f"Saved HiveAI image to {current_output_path}")
                    saved_images.append(current_output_path)
                else:
                    logger.error(f"Failed to save HiveAI image {i+1}")
            
            # Return the first saved image path, or None if no images were saved
            if saved_images:
                return saved_images[0]
            
            error_msg = "Failed to save any HiveAI images"
            logger.error(error_msg)
            raise Exception(f"HiveAI image generation failed: {error_msg}")
            
        except Exception as e:
            logger.error(f"Error generating HiveAI image: {str(e)}")
            # Instead of fallback, propagate the error
            raise Exception(f"HiveAI image generation failed: {str(e)}")

    def generate_image_from_prompt_midjourney(self, prompt, output_path):
        """
        Generate an image using Midjourney via GoAPI.
        
        Note: As of April 2025, the GoAPI Midjourney integration appears to have changed 
        or requires different credentials than what was previously documented.
        If you encounter errors with this provider, consider using one of the alternatives:
        - OpenAI DALL-E: Set provider='openai' and provide an OpenAI API key
        - HiveAI: Set provider='hiveai' and provide a HiveAI API key
        - Google Imagen: Set provider='imagen' and provide a Google API key
        
        Args:
            prompt: The prompt to use for image generation
            output_path: Path where the image will be saved
            
        Returns:
            Path to the saved image or None if generation failed
        """
        try:
            logger.info(f"Generating Midjourney image with prompt: {prompt[:100]}...")
            logger.warning("The Midjourney API integration may be outdated. See documentation for alternatives.")
            
            # Try to discover the correct API endpoint
            endpoint_info = self._discover_goapi_midjourney_endpoints()
            
            if not endpoint_info or not endpoint_info.get("working_endpoints"):
                error_msg = "Could not find any working GoAPI Midjourney endpoints. Consider using an alternative provider such as 'openai', 'hiveai', or 'imagen'."
                logger.error(error_msg)
                raise Exception(f"Midjourney image generation failed: {error_msg}")
            
            # Use the discovered imagine endpoint
            imagine_endpoint = endpoint_info.get("imagine_endpoint")
            if not imagine_endpoint:
                error_msg = "Could not find a working 'imagine' endpoint"
                logger.error(error_msg)
                raise Exception(f"Midjourney image generation failed: {error_msg}")
                
            logger.info(f"Using Midjourney imagine endpoint: {imagine_endpoint}")
            
            # Request headers
            headers = {
                "Authorization": f"Bearer {self.goapi_key}",
                "Content-Type": "application/json"
            }
            
            # Parse the aspect ratio
            aspect_ratio = self.aspect_ratio or "1:1"
            
            # Format varies by endpoint
            payload = {
                "prompt": prompt
            }
            
            # Add aspect ratio with the right key name
            if endpoint_info.get("aspect_ratio_key"):
                payload[endpoint_info.get("aspect_ratio_key")] = aspect_ratio
            else:
                # Try both common keys
                payload["aspect_ratio"] = aspect_ratio
                payload["aspect"] = aspect_ratio
            
            logger.debug(f"Request payload: {json.dumps(payload, indent=2)}")
            
            # Send request to GoAPI
            response = requests.post(imagine_endpoint, headers=headers, json=payload, timeout=120)
            
            if response.status_code != 200:
                error_msg = f"Error from GoAPI: {response.status_code}, {response.text}"
                logger.error(error_msg)
                raise Exception(f"Midjourney image generation failed: {error_msg}")
            
            # Parse the response
            try:
                response_data = response.json()
            except Exception as e:
                error_msg = f"Error parsing JSON response: {e}, Response text: {response.text[:500]}"
                logger.error(error_msg)
                raise Exception(f"Midjourney image generation failed: {error_msg}")
            
            logger.debug(f"Response data: {json.dumps(response_data, indent=2)}")
            
            # Extract task ID from various possible fields
            task_id = None
            id_field = endpoint_info.get("id_field", "")
            
            # Try the discovered ID field first
            if id_field and id_field in response_data:
                task_id = response_data[id_field]
            else:
                # Try all possible ID fields
                for field in ["task_id", "id", "messageId", "message_id"]:
                    if field in response_data:
                        task_id = response_data[field]
                        break
            
            if not task_id:
                error_msg = "No task ID in response. Available fields: " + ", ".join(response_data.keys())
                logger.error(error_msg)
                raise Exception(f"Midjourney image generation failed: {error_msg}")
            
            logger.info(f"GoAPI task initiated successfully. Task ID: {task_id}")
            
            # Use the discovered fetch endpoint and approach
            result_endpoint = endpoint_info.get("result_endpoint")
            fetch_method = endpoint_info.get("fetch_method", "GET")
            
            # Poll for task completion
            task_result = self._wait_for_midjourney_task_adaptive(
                task_id, 
                result_endpoint=result_endpoint,
                fetch_method=fetch_method,
                id_field=id_field
            )
            
            # Try to find image URL in the response based on discovered field
            image_url_field = endpoint_info.get("image_url_field")
            image_url = None
            
            # Try the discovered field first
            if image_url_field:
                if "." in image_url_field:
                    # Handle nested fields like "result.imageUrl"
                    parts = image_url_field.split(".")
                    data = task_result
                    for part in parts:
                        if isinstance(data, dict) and part in data:
                            data = data[part]
                        else:
                            data = None
                            break
                    if data and isinstance(data, str):
                        image_url = data
                    elif isinstance(data, list) and len(data) > 0:
                        image_url = data[0]
                else:
                    # Direct field
                    if image_url_field in task_result:
                        image_url = task_result[image_url_field]
            
            # If we couldn't find it using the discovered field, try all possibilities
            if not image_url:
                if "imageUrl" in task_result:
                    image_url = task_result["imageUrl"]
                elif "image_url" in task_result:
                    image_url = task_result["image_url"]
                elif "result" in task_result and "imageUrl" in task_result["result"]:
                    image_url = task_result["result"]["imageUrl"]
                elif "result" in task_result and "image_url" in task_result["result"]:
                    image_url = task_result["result"]["image_url"]
                elif "result" in task_result and "images" in task_result["result"] and len(task_result["result"]["images"]) > 0:
                    image_url = task_result["result"]["images"][0]
                elif "images" in task_result and len(task_result["images"]) > 0:
                    image_url = task_result["images"][0]
            
            if not image_url:
                error_msg = "No image URL in task result. Available fields: " + ", ".join(task_result.keys())
                logger.error(error_msg)
                raise Exception(f"Midjourney image generation failed: {error_msg}")
            
            # Create directory for image if it doesn't exist
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Save image
            if self._save_image(image_url, output_path):
                logger.info(f"Saved Midjourney image to {output_path}")
                return output_path
            else:
                error_msg = f"Failed to save Midjourney image to {output_path}"
                logger.error(error_msg)
                raise Exception(f"Midjourney image generation failed: {error_msg}")
            
        except Exception as e:
            logger.error(f"Error generating Midjourney image: {str(e)}")
            # Instead of fallback, propagate the error
            raise Exception(f"Midjourney image generation failed: {str(e)}")
    
    def _discover_goapi_midjourney_endpoints(self):
        """
        Attempt to discover the correct GoAPI Midjourney endpoints by testing various possibilities.
        
        Returns:
            dict: Information about discovered endpoints and their characteristics
        """
        logger.info("Discovering available GoAPI Midjourney endpoints...")
        
        # Headers for all requests
        headers = {
            "Authorization": f"Bearer {self.goapi_key}",
            "Content-Type": "application/json"
        }
        
        # Endpoints to test
        test_endpoints = [
            "https://api.goapi.io/midjourney/imagine",
            "https://api.goapi.io/midjourney/v1/imagine", 
            "https://api.goapi.io/midjourney/v2/imagine",
            "https://api.goapi.io/api/midjourney/imagine",
            "https://api.goapi.io/api/v1/midjourney/imagine",
            "https://api.goapi.io/task/midjourney/imagine"
        ]
        
        working_endpoints = []
        best_endpoint = None
        response_data = None
        
        # First, test the base API endpoint to see if it gives us any clues
        try:
            base_response = requests.get("https://api.goapi.io", headers=headers, timeout=10)
            if base_response.status_code == 200:
                logger.info("GoAPI base endpoint is available")
                try:
                    base_data = base_response.json()
                    logger.debug(f"Base API response: {json.dumps(base_data, indent=2)}")
                    # Check if the response contains API documentation or endpoint hints
                    if "endpoints" in base_data:
                        for endpoint in base_data["endpoints"]:
                            if "midjourney" in endpoint and "imagine" in endpoint:
                                test_endpoints.insert(0, endpoint)  # Prioritize discovered endpoints
                except:
                    pass
        except Exception as e:
            logger.warning(f"Could not check base API endpoint: {str(e)}")
        
        # Test each endpoint
        for endpoint in test_endpoints:
            try:
                # Use a minimal test request
                test_payload = {
                    "prompt": "test prompt - not for actual generation"
                }
                
                # Set timeout to 5 seconds for discovery
                response = requests.post(
                    endpoint, 
                    headers=headers, 
                    json=test_payload, 
                    timeout=5
                )
                
                # Even errors can be informative - if it's a 400 but mentions parameters,
                # it might be the right endpoint with wrong parameters
                if response.status_code == 400:
                    logger.info(f"Endpoint {endpoint} returned 400 - might be valid with correct parameters")
                    working_endpoints.append({
                        "endpoint": endpoint,
                        "status": 400,
                        "notes": "Returns 400 but might be valid with correct parameters"
                    })
                    
                    # This could be our best endpoint if we don't find a 200
                    if not best_endpoint:
                        best_endpoint = endpoint
                        try:
                            response_data = response.json()
                        except:
                            pass
                elif response.status_code == 200:
                    logger.info(f"Endpoint {endpoint} is available!")
                    working_endpoints.append({
                        "endpoint": endpoint,
                        "status": 200,
                        "notes": "Returns 200 success"
                    })
                    
                    # This is definitely our best endpoint
                    best_endpoint = endpoint
                    try:
                        response_data = response.json()
                    except:
                        pass
                    break  # Found a working endpoint, no need to test more
                
            except Exception as e:
                logger.debug(f"Endpoint {endpoint} test failed: {str(e)}")
        
        # If we found at least one working endpoint
        if best_endpoint:
            logger.info(f"Found best endpoint: {best_endpoint}")
            
            # Analyze response data if we have it
            id_field = "id"  # Default
            image_url_field = "imageUrl"  # Default
            aspect_ratio_key = "aspect_ratio"  # Default
            fetch_method = "GET"  # Default
            result_endpoint_template = "{base_url}/result/{task_id}"  # Default
            
            # Try to determine field names from response
            if response_data:
                logger.debug(f"Analyzing response data: {json.dumps(response_data, indent=2)}")
                
                # Check for task ID field
                for field in ["task_id", "id", "messageId", "message_id"]:
                    if field in response_data:
                        id_field = field
                        break
                
                # Check for any image URL fields
                for field in ["imageUrl", "image_url", "image", "url"]:
                    if field in response_data:
                        image_url_field = field
                        break
                    elif "result" in response_data and field in response_data["result"]:
                        image_url_field = f"result.{field}"
                        break
                
                # Look for clues about what fields are expected
                if "error" in response_data and "message" in response_data:
                    message = response_data["message"]
                    if "aspect_ratio" in message:
                        aspect_ratio_key = "aspect_ratio"
                    elif "aspect" in message:
                        aspect_ratio_key = "aspect"
            
            # Extract base URL to help construct result endpoint
            base_url_parts = best_endpoint.split("/")
            base_url = "/".join(base_url_parts[:-1])  # Remove the last part (imagine)
            
            # Construct result endpoint
            result_endpoint = result_endpoint_template.format(
                base_url=base_url,
                task_id="{task_id}"  # This will be replaced later with the actual task ID
            )
            
            # Return the discovered information
            return {
                "working_endpoints": working_endpoints,
                "imagine_endpoint": best_endpoint,
                "result_endpoint": result_endpoint,
                "id_field": id_field,
                "image_url_field": image_url_field,
                "aspect_ratio_key": aspect_ratio_key,
                "fetch_method": fetch_method
            }
        else:
            logger.warning("No working GoAPI Midjourney endpoints found")
            return {"working_endpoints": []}
            
    def _wait_for_midjourney_task_adaptive(self, task_id, result_endpoint=None, fetch_method="GET", id_field="id", max_attempts=30, delay=10):
        """
        Poll the GoAPI for task completion with adaptive endpoint handling.
        
        Args:
            task_id: Task ID to check
            result_endpoint: Endpoint template for checking results, with {task_id} placeholder
            fetch_method: HTTP method to use (GET or POST)
            id_field: Field name used for the task ID
            max_attempts: Maximum number of polling attempts
            delay: Delay between polling attempts in seconds
            
        Returns:
            Task result data or None if failed
        """
        logger.info(f"Waiting for Midjourney task {task_id} to complete...")
        
        # Set up the endpoint URL
        url = result_endpoint.format(task_id=task_id) if result_endpoint else f"https://api.goapi.io/midjourney/fetch"
        
        # Request headers
        headers = {
            "Authorization": f"Bearer {self.goapi_key}",
            "Content-Type": "application/json"
        }
        
        # For POST requests, prepare payload
        payload = {id_field: task_id} if fetch_method.upper() == "POST" else None
        
        for attempt in range(max_attempts):
            try:
                logger.debug(f"Checking task status (attempt {attempt+1}/{max_attempts})...")
                
                # Send request to GoAPI with appropriate method
                if fetch_method.upper() == "GET":
                    response = requests.get(url, headers=headers, timeout=30)
                else:  # POST
                    response = requests.post(url, headers=headers, json=payload, timeout=30)
                
                # If we get a 404 on the first attempt, try alternative approaches
                if response.status_code == 404 and attempt == 0:
                    logger.warning(f"Endpoint {url} not found. Trying alternative endpoints...")
                    
                    # Try the other HTTP method
                    if fetch_method.upper() == "GET":
                        new_method = "POST"
                        response = requests.post(url, headers=headers, json=payload, timeout=30)
                    else:
                        new_method = "GET"
                        # Try constructing a GET URL with the task ID in it
                        base_url = url.split("/fetch")[0]
                        new_url = f"{base_url}/result/{task_id}"
                        response = requests.get(new_url, headers=headers, timeout=30)
                    
                    # If that worked, update our approach
                    if response.status_code == 200:
                        fetch_method = new_method
                        if new_method == "GET":
                            url = new_url
                            payload = None
                        logger.info(f"Switched to {new_method} method with endpoint {url}")
                
                if response.status_code != 200:
                    logger.warning(f"Error checking task status: {response.status_code}, {response.text}")
                    time.sleep(delay)
                    continue
                
                # Parse the response
                response_data = response.json()
                
                # Try to determine if the task is complete
                if "imageUrl" in response_data or "image_url" in response_data:
                    logger.info(f"Task {task_id} completed successfully after {attempt+1} attempts")
                    return response_data
                
                # Check for result.images field in response
                if "result" in response_data:
                    if "images" in response_data["result"] and response_data["result"]["images"]:
                        logger.info(f"Task {task_id} completed successfully after {attempt+1} attempts")
                        return response_data
                    elif "imageUrl" in response_data["result"] or "image_url" in response_data["result"]:
                        logger.info(f"Task {task_id} completed successfully after {attempt+1} attempts")
                        return response_data
                
                # Check for images directly
                if "images" in response_data and response_data["images"]:
                    logger.info(f"Task {task_id} completed successfully after {attempt+1} attempts")
                    return response_data
                
                # Check for status fields
                status = None
                if "status" in response_data:
                    status = response_data["status"]
                elif "result" in response_data and "status" in response_data["result"]:
                    status = response_data["result"]["status"]
                
                if status and status.lower() in ["completed", "done", "success", "successful"]:
                    logger.info(f"Task {task_id} completed successfully after {attempt+1} attempts")
                    return response_data
                elif status and status.lower() in ["failed", "error"]:
                    error_msg = f"Task {task_id} failed with status: {status}"
                    if "error" in response_data:
                        error_msg += f", error: {response_data['error']}"
                    logger.error(error_msg)
                    raise Exception(error_msg)
                
                # Check for progress percentage
                progress = None
                if "progress" in response_data:
                    progress = response_data["progress"]
                elif "result" in response_data and "progress" in response_data["result"]:
                    progress = response_data["result"]["progress"]
                
                if progress:
                    logger.debug(f"Task {task_id} progress: {progress}% (attempt {attempt+1}/{max_attempts})")
                
                # Check for explicit error
                error = None
                if "error" in response_data:
                    error = response_data["error"]
                elif "result" in response_data and "error" in response_data["result"]:
                    error = response_data["result"]["error"]
                
                if error:
                    error_msg = f"Task {task_id} failed: {error}"
                    logger.error(error_msg)
                    raise Exception(error_msg)
                
                # Wait before next attempt
                time.sleep(delay)
                
            except Exception as e:
                if "Task completed" in str(e):
                    # This is actually a success case
                    logger.info(f"Task {task_id} completed successfully after {attempt+1} attempts")
                    break
                
                logger.error(f"Error checking task status: {str(e)}")
                time.sleep(delay)
        
        # If we've exhausted all attempts
        error_msg = f"Task {task_id} did not complete after {max_attempts} attempts"
        logger.error(error_msg)
        raise Exception(error_msg)

    def generate_image_from_prompt_imagen(self, prompt, output_path):
        """
        Generate an image using Google's Imagen 3.0 model for high-quality image generation.
        
        Note: Imagen API is only accessible to users on the paid tier.
        
        Args:
            prompt: The prompt to use for image generation
            output_path: Path where the image will be saved
            
        Returns:
            Path to the saved image or None if generation failed
        """
        try:
            logger.info(f"Generating Google Imagen image with prompt: {prompt[:100]}...")
            
            # Configure the Google AI client if not already done
            genai.configure(api_key=self.google_key)
            
            # Instead of using GenerativeModel for Imagen, we need to use the REST API directly
            logger.info("Using Imagen REST API for image generation")
            
            import requests
            
            # Build the API URL
            # Documentation: https://ai.google.dev/gemini-api/docs/image-generation
            base_url = "https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-002:predict"
            
            # Set up the request headers
            headers = {
                "Content-Type": "application/json",
            }
            
            # Set up the request payload
            payload = {
                "instances": [
                    {
                        "prompt": prompt
                    }
                ],
                "parameters": {
                    "sampleCount": 1
                }
            }
            
            # Add aspect ratio if valid
            aspect_ratio = self.aspect_ratio or "1:1"
            if aspect_ratio in ["1:1", "3:4", "4:3", "9:16", "16:9"]:
                payload["parameters"]["aspectRatio"] = aspect_ratio
            
            # Add API key as a query parameter
            url = f"{base_url}?key={self.google_key}"
            
            # Make the API request
            logger.info("Sending request to Imagen REST API")
            response = requests.post(url, headers=headers, json=payload)
            
            # Check for errors
            if response.status_code != 200:
                error_msg = f"Error from Imagen API: {response.status_code}, {response.text}"
                
                # Check for billing error
                if "only accessible to billed users" in response.text:
                    error_msg = "ERROR: Imagen API is only accessible to paid tier users. Please sign up for the paid tier at https://ai.google.dev/pricing or use another provider."
                
                logger.error(error_msg)
                raise Exception(f"Google Imagen image generation failed: {error_msg}")
            
            # Parse the response
            response_data = response.json()
            
            # Extract the image data
            if not response_data or "predictions" not in response_data or not response_data["predictions"]:
                error_msg = "No predictions in Imagen API response"
                logger.error(error_msg)
                raise Exception(f"Google Imagen image generation failed: {error_msg}")
            
            # Get the first prediction
            prediction = response_data["predictions"][0]
            
            if "bytesBase64Encoded" not in prediction:
                error_msg = "No image data in Imagen API response"
                logger.error(error_msg)
                raise Exception(f"Google Imagen image generation failed: {error_msg}")
            
            # Get the base64 encoded image
            image_data = prediction["bytesBase64Encoded"]
            
            # Create directory for image if it doesn't exist
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Save image from base64 data
            if self._save_b64_image(image_data, output_path):
                logger.info(f"Saved Google Imagen image to {output_path}")
                return output_path
            else:
                error_msg = f"Failed to save Google Imagen image to {output_path}"
                logger.error(error_msg)
                raise Exception(f"Google Imagen image generation failed: {error_msg}")
            
        except Exception as e:
            error_msg = str(e)
            
            # Provide a more helpful message for billing errors
            if "only accessible to billed users" in error_msg or "paid tier" in error_msg:
                logger.error("Imagen API requires a paid account. See: https://ai.google.dev/pricing")
                raise Exception("Imagen API requires a paid account. Please upgrade to the paid tier at https://ai.google.dev/pricing or use an alternative provider.")
            else:
                logger.error(f"Error generating Google Imagen image: {error_msg}")
                raise Exception(f"Google Imagen image generation failed: {error_msg}")

    def generate_images_for_post(self, prompts, post_title, output_dir):
        """
        Generate images for a post using the provided prompts.
        
        Args:
            prompts: List of prompts to use for image generation
            post_title: The title of the post
            output_dir: Directory to save the generated images
            
        Returns:
            List of paths to the generated images
        """
        os.makedirs(output_dir, exist_ok=True)
        
        logger.info(f"Generating images for post: {post_title}")
        
        image_paths = []
        
        # For Midjourney provider, limit to 3 concurrent requests
        if self.provider == "midjourney":
            import concurrent.futures
            import time
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                futures = []
                
                for i, prompt in enumerate(prompts):
                    # Create output path for this image
                    image_filename = f"{i+1}_{post_title.replace(' ', '_')[:30]}.png"
                    image_path = os.path.join(output_dir, image_filename)
                    
                    # Submit the task to the executor
                    future = executor.submit(self.generate_image_from_prompt, prompt, image_path)
                    futures.append((future, image_path))
                
                # Wait for all futures to complete
                for future, image_path in futures:
                    try:
                        saved_path = future.result()
                        if saved_path:
                            image_paths.append(saved_path)
                    except Exception as e:
                        logger.error(f"Error in concurrent image generation: {str(e)}")
                        # The exception is already handled in generate_image_from_prompt
                        # so we don't need to handle it again here
        else:
            # For other providers, use simple sequential processing
            for i, prompt in enumerate(prompts):
                # Create output path for this image
                image_filename = f"{i+1}_{post_title.replace(' ', '_')[:30]}.png"
                image_path = os.path.join(output_dir, image_filename)
                
                # Generate image
                saved_path = self.generate_image_from_prompt(prompt, image_path)
                
                if saved_path:
                    image_paths.append(saved_path)
            
        return image_paths
    
    def generate_images_from_prompts_dir(self, prompts_dir):
        """
        Generate images from prompt files in a directory.
        
        The method supports multiple directory structures:
        
        1. Traditional structure:
           - post_dir1/
             - prompt1.txt
             - prompt2.txt
           - post_dir2/
             - prompt1.txt
             - prompt2.txt
             
        2. New structure with summary.json:
           - summary.json (contains mapping of post titles to prompt files)
           - 1_Post_Title_prompt.txt
           - 2_Post_Title_prompt.txt
           - 3_Another_Post_prompt.txt
        
        Args:
            prompts_dir: Directory containing prompt files
            
        Returns:
            Dictionary mapping post titles to lists of image paths
        """
        # When using the new structure, self.output_dir is already set to the correct images directory
        images_dir = self.output_dir
        
        logger.info(f"Generating images from prompts in {prompts_dir}")
        logger.info(f"Images will be saved to {images_dir}")
        
        # Create directory for images
        os.makedirs(images_dir, exist_ok=True)
        
        # Check if there's a summary file
        summary_path = os.path.join(prompts_dir, "summary.json")
        
        image_paths = {}
        
        if os.path.exists(summary_path):
            logger.info(f"Found summary file: {summary_path}, using new directory structure")
            try:
                # Load summary file to get post titles and prompts
                with open(summary_path, 'r') as f:
                    summary_data = json.load(f)
                
                if "posts" in summary_data:
                    posts = summary_data["posts"]
                    logger.info(f"Found {len(posts)} posts in summary file")
                    
                    for post in posts:
                        if "title" not in post or "prompts" not in post:
                            logger.warning(f"Skipping post with missing title or prompts: {post}")
                            continue
                        
                        post_title = post["title"]
                        logger.info(f"Processing post: {post_title}")
                        
                        prompt_files = post["prompts"]
                        prompts = []
                        
                        for prompt_file in prompt_files:
                            prompt_path = os.path.join(prompts_dir, prompt_file)
                            if os.path.exists(prompt_path):
                                with open(prompt_path, 'r') as f:
                                    prompt_text = f.read().strip()
                                    if prompt_text:
                                        prompts.append(prompt_text)
                                        logger.debug(f"Loaded prompt from {prompt_path}: {prompt_text[:50]}...")
                            else:
                                logger.warning(f"Prompt file not found: {prompt_path}")
                        
                        if not prompts:
                            logger.warning(f"No valid prompts found for post: {post_title}")
                            continue
                        
                        # Create directory for this post's images
                        post_dir_name = post_title.replace(' ', '_')
                        post_images_dir = os.path.join(images_dir, post_dir_name)
                        os.makedirs(post_images_dir, exist_ok=True)
                        
                        # Generate images
                        logger.info(f"Generating images for post: {post_title} with {len(prompts)} prompts")
                        paths = self.generate_images_for_post(prompts, post_title, post_images_dir)
                        
                        if paths:
                            image_paths[post_title] = paths
                            logger.info(f"Generated {len(paths)} images for post: {post_title}")
                        else:
                            logger.warning(f"No images generated for post: {post_title}")
                else:
                    # New format: Check if keys in summary_data might be post titles
                    potential_posts = {k: v for k, v in summary_data.items() if isinstance(v, list)}
                    
                    if potential_posts:
                        logger.info(f"Found {len(potential_posts)} posts in summary file (alternative format)")
                        
                        for post_title, prompts in potential_posts.items():
                            logger.info(f"Processing post: {post_title}")
                            
                            if not prompts:
                                logger.warning(f"No prompts found for post: {post_title}")
                                continue
                                
                            # Create directory for this post's images
                            post_dir_name = post_title.replace(' ', '_')
                            post_images_dir = os.path.join(images_dir, post_dir_name)
                            os.makedirs(post_images_dir, exist_ok=True)
                            
                            # Generate images
                            logger.info(f"Generating images for post: {post_title} with {len(prompts)} prompts")
                            paths = self.generate_images_for_post(prompts, post_title, post_images_dir)
                            
                            if paths:
                                image_paths[post_title] = paths
                                logger.info(f"Generated {len(paths)} images for post: {post_title}")
                            else:
                                logger.warning(f"No images generated for post: {post_title}")
                    else:
                        logger.warning("Summary file does not contain a 'posts' key or any valid post titles")
            except Exception as e:
                logger.error(f"Error processing summary file: {str(e)}")
        else:
            # Check for traditional directory structure with post subdirectories
            logger.info("No summary file found, checking for traditional directory structure")
            post_dirs = [d for d in os.listdir(prompts_dir) 
                       if os.path.isdir(os.path.join(prompts_dir, d)) and d != "__pycache__"]
            
            if post_dirs:
                logger.info(f"Found {len(post_dirs)} post directories")
                
                # Generate images for each post
                for post_dir in post_dirs:
                    # Extract post title from directory name
                    post_title = post_dir.replace('_', ' ')
                    logger.info(f"Processing post directory: {post_dir}")
                    
                    # Get prompt files for this post
                    prompt_dir = os.path.join(prompts_dir, post_dir)
                    prompt_files = [f for f in os.listdir(prompt_dir) if f.endswith("_prompt.txt") or f.endswith(".txt")]
                    
                    if not prompt_files:
                        logger.warning(f"No prompt files found for post: {post_title}")
                        continue
                    
                    # Load prompts from files
                    prompts = []
                    for prompt_file in sorted(prompt_files):
                        with open(os.path.join(prompt_dir, prompt_file), 'r') as f:
                            prompt_text = f.read().strip()
                            if prompt_text:
                                prompts.append(prompt_text)
                                logger.debug(f"Loaded prompt from {prompt_file}: {prompt_text[:50]}...")
                    
                    if not prompts:
                        logger.warning(f"No valid prompts found for post: {post_title}")
                        continue
                    
                    # Create directory for this post's images
                    post_images_dir = os.path.join(images_dir, post_dir)
                    os.makedirs(post_images_dir, exist_ok=True)
                    
                    # Generate images
                    logger.info(f"Generating images for post: {post_title} with {len(prompts)} prompts")
                    paths = self.generate_images_for_post(prompts, post_title, post_images_dir)
                    
                    if paths:
                        image_paths[post_title] = paths
                        logger.info(f"Generated {len(paths)} images for post: {post_title}")
                    else:
                        logger.warning(f"No images generated for post: {post_title}")
            else:
                # No post directories, check for direct prompt files
                logger.info("No post directories found, checking for prompt files directly in prompts directory")
                prompt_files = [f for f in os.listdir(prompts_dir) if f.endswith("_prompt.txt") or f.endswith(".txt")]
                
                if prompt_files:
                    logger.info(f"Found {len(prompt_files)} prompt files in root directory")
                    # Create a single post from all prompt files
                    prompts = []
                    for prompt_file in sorted(prompt_files):
                        with open(os.path.join(prompts_dir, prompt_file), 'r') as f:
                            prompt_text = f.read().strip()
                            if prompt_text:
                                prompts.append(prompt_text)
                                logger.debug(f"Loaded prompt from {prompt_file}: {prompt_text[:50]}...")
                    
                    if prompts:
                        # Extract a post title from the first prompt file name
                        first_file = prompt_files[0]
                        # Try to extract a meaningful title
                        if "_prompt.txt" in first_file:
                            title_part = first_file.replace("_prompt.txt", "")
                            # Remove any leading numbers and underscores
                            title_part = re.sub(r'^\d+_', '', title_part)
                            post_title = title_part.replace('_', ' ')
                        else:
                            # Use a generic title
                            post_title = "Generated Post " + datetime.now().strftime("%Y%m%d_%H%M%S")
                        
                        logger.info(f"Creating images for post: {post_title} with {len(prompts)} prompts")
                        
                        # Create directory for this post's images
                        post_dir_name = post_title.replace(' ', '_')
                        post_images_dir = os.path.join(images_dir, post_dir_name)
                        os.makedirs(post_images_dir, exist_ok=True)
                        
                        # Generate images
                        paths = self.generate_images_for_post(prompts, post_title, post_images_dir)
                        
                        if paths:
                            image_paths[post_title] = paths
                            logger.info(f"Generated {len(paths)} images for post: {post_title}")
                        else:
                            logger.warning(f"No images generated for post: {post_title}")
                else:
                    logger.warning(f"No prompt files found in {prompts_dir}")
        
        # Save a summary file
        if image_paths:
            summary_path = os.path.join(images_dir, "summary.json")
            with open(summary_path, 'w') as f:
                json.dump(image_paths, f, indent=2)
            logger.info(f"Image generation completed. Results saved to {images_dir}")
        else:
            logger.warning(f"No images were generated from {prompts_dir}")
        
        return image_paths

    def generate_images_from_posts_file(self, posts_file, prompts_dir=None):
        """
        Generate images for posts by first generating prompts if needed.
        
        Args:
            posts_file: Path to the posts text file
            prompts_dir: Directory containing prompt files (optional)
            
        Returns:
            Dictionary mapping post titles to lists of image paths
        """
        # If prompts directory not provided, try to find the prompts directory using the same timestamp
        if not prompts_dir:
            # Extract timestamp from directory structure
            post_dir = os.path.dirname(posts_file)
            timestamp_dir = os.path.dirname(post_dir)
            
            if os.path.basename(post_dir) == "posts" and os.path.basename(timestamp_dir) != "output":
                # Using new structure - find the prompts directory with the same timestamp
                prompts_dir = os.path.join(timestamp_dir, "prompts")
                if not os.path.exists(prompts_dir):
                    logger.info(f"Generating prompts for posts in {posts_file}")
                    # Create a prompt generator that will save to the prompts subdirectory
                    generator = OpenRouterPromptGenerator(output_dir=prompts_dir)
                    generator.generate_prompts_from_posts_file(posts_file)
            else:
                # Using old structure or custom path - use default based on posts file
                base_name = os.path.splitext(os.path.basename(posts_file))[0]
                prompts_dir = os.path.join(self.output_dir, f"{base_name}_prompts")
                
                # Generate prompts if directory doesn't exist
                if not os.path.exists(prompts_dir):
                    logger.info(f"Generating prompts for posts in {posts_file}")
                    generator = OpenRouterPromptGenerator(output_dir=self.output_dir)
                    generator.generate_prompts_from_posts_file(posts_file)
        
        # Generate images from prompts
        return self.generate_images_from_prompts_dir(prompts_dir)

def main():
    """Main function to generate images for the most recent prompts directory."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate images for F1 social media posts using various image generation APIs")
    parser.add_argument("--api-key", help="API key (overrides OPENAI_API_KEY or HIVEAI_API_KEY environment variable)")
    parser.add_argument("--goapi-key", help="GoAPI key for Midjourney integration (overrides GOAPI_KEY environment variable)")
    parser.add_argument("--google-key", help="Google API key for Imagen integration (overrides GOOGLE_API_KEY environment variable)")
    parser.add_argument("--hiveai-key", help="HiveAI API key (overrides HIVEAI_API_KEY environment variable)")
    parser.add_argument("--provider", default="openai", choices=["openai", "midjourney", "imagen", "hiveai"], help="Image generation provider (default: openai)")
    parser.add_argument("--prompts-dir", help="Directory containing prompt files")
    parser.add_argument("--posts-file", help="Path to the posts text file (if prompts don't exist yet)")
    parser.add_argument("--output-dir", default="output", help="Directory to save images (default: output)")
    parser.add_argument("--model", default="gpt-image-1", help="Model to use (default: gpt-image-1 for OpenAI, but will fall back to DALL-E 3 if not available)")
    parser.add_argument("--size", default="1024x1024", help="Image size to generate (default: 1024x1024, use 1024x1536 for GPT-Image-1)")
    parser.add_argument("--aspect-ratio", default="16:9", help="Aspect ratio for images (options: '16:9', '1:1', '4:3', etc.)")
    parser.add_argument("--num-images", type=int, default=2, help="Number of images to generate per prompt (default: 2)")
    parser.add_argument("--quality", default="standard", choices=["standard", "hd"], help="Quality of DALL-E images (options: 'standard', 'hd', default: standard)")
    parser.add_argument("--style", default="vivid", choices=["vivid", "natural"], help="Style of DALL-E images (options: 'vivid', 'natural', default: vivid)")
    args = parser.parse_args()
    
    # Get API keys from arguments or environment variables
    api_key = args.api_key
    goapi_key = args.goapi_key or os.environ.get("GOAPI_KEY")
    google_key = args.google_key or os.environ.get("GOOGLE_API_KEY")
    hiveai_key = args.hiveai_key or os.environ.get("HIVEAI_API_KEY") or (args.api_key if args.provider == "hiveai" else None)
    
    # For OpenAI, try environment variable if not provided
    if args.provider == "openai" and not api_key:
        api_key = os.environ.get("OPENAI_API_KEY")
    
    # Validate required API keys based on provider
    if args.provider == "openai" and not api_key:
        logger.error("No OpenAI API key provided. Please set OPENAI_API_KEY environment variable or use --api-key")
        return 1
    
    if args.provider == "midjourney" and not goapi_key:
        logger.error("No GoAPI key provided. Please set GOAPI_KEY environment variable or use --goapi-key")
        return 1
    
    if args.provider == "imagen" and not google_key:
        logger.error("No Google API key provided. Please set GOOGLE_API_KEY environment variable or use --google-key")
        return 1
    
    if args.provider == "hiveai" and not hiveai_key:
        logger.error("No HiveAI API key provided. Please set HIVEAI_API_KEY environment variable, use --hiveai-key, or use --api-key")
        return 1
    
    # Initialize image generator
    try:
        # Set model based on provider if not specified
        model = args.model
        if args.provider == "openai" and not model:
            model = "gpt-image-1"
            logger.info("Using GPT-Image-1 by default. Note that if your account doesn't have access to GPT-Image-1, it will automatically fall back to DALL-E 3.")
        elif args.provider == "hiveai" and model == "gpt-image-1":
            model = "flux-schnell-enhanced"
        
        # Check if size is appropriate for the model
        size = args.size
        if args.provider == "openai":
            # Recommended sizes for GPT-Image-1
            if model == "gpt-image-1" and size == "1024x1024":
                logger.info("For GPT-Image-1, consider using size 1024x1536 or 1536x1024 for better results.")
            # Valid sizes for DALL-E 3
            elif model in ["dall-e-2", "dall-e-3"] and size not in ["1024x1024", "1024x1792", "1792x1024"]:
                logger.warning(f"Size {size} is not valid for {model}. Will use 1024x1024 instead.")
                size = "1024x1024"
        
        generator = ImageGenerator(
            api_key=api_key, 
            output_dir=args.output_dir, 
            model=model, 
            size=size,
            provider=args.provider,
            goapi_key=goapi_key,
            google_key=google_key,
            hiveai_key=hiveai_key,
            aspect_ratio=args.aspect_ratio,
            num_images=args.num_images,
            quality=args.quality,
            style=args.style
        )
    except Exception as e:
        logger.error(f"Failed to initialize image generator: {str(e)}")
        return 1
    
    # Generate images
    if args.prompts_dir:
        # Generate images from existing prompts
        generator.generate_images_from_prompts_dir(args.prompts_dir)
    elif args.posts_file:
        # Generate prompts and then images
        generator.generate_images_from_posts_file(args.posts_file)
    else:
        # Find the most recent prompts directory
        prompts_dirs = sorted([d for d in os.listdir(args.output_dir) 
                            if os.path.isdir(os.path.join(args.output_dir, d)) and "prompts" in d], 
                            reverse=True)
        
        if not prompts_dirs:
            logger.error(f"No prompts directories found in {args.output_dir}. Please generate prompts first or specify a prompts directory using --prompts-dir")
            return 1
        
        prompts_dir = os.path.join(args.output_dir, prompts_dirs[0])
        logger.info(f"Using most recent prompts directory: {prompts_dir}")
        
        # Generate images
        generator.generate_images_from_prompts_dir(prompts_dir)
    
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main()) 