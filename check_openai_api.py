#!/usr/bin/env python3
"""
Check OpenAI API Key

This script tests if an OpenAI API key can authenticate correctly and
identifies common issues with the key configuration.
"""

import os
import sys
import httpx
import argparse
import colorama
from colorama import Fore, Style
from openai import OpenAI

# Initialize colorama
colorama.init(autoreset=True)

def check_api_key(api_key):
    """
    Test if an OpenAI API key can authenticate correctly.
    
    Args:
        api_key: OpenAI API key to test
    
    Returns:
        bool: True if authentication was successful, False otherwise
    """
    print(f"{Style.BRIGHT}Testing OpenAI API Key: {api_key[:4]}...{api_key[-4:]}")
    
    if not api_key:
        print(f"{Fore.RED}Error: No API key provided")
        return False
    
    if "your-" in api_key.lower() or "openai" in api_key.lower() or "key" in api_key.lower():
        print(f"{Fore.RED}Error: API key appears to contain placeholder text")
        return False
    
    if not api_key.startswith("sk-"):
        print(f"{Fore.RED}Error: API key should start with 'sk-'")
        return False
    
    # Create HTTP client
    http_client = httpx.Client(timeout=60.0)
    
    try:
        # Initialize OpenAI client
        client = OpenAI(
            api_key=api_key,
            http_client=http_client
        )
        
        # Make a simple API call to test authentication
        print(f"{Fore.CYAN}Making test API call...")
        # Use a simple model list request to check if the API key works
        models = client.models.list()
        
        # If we get here, authentication was successful
        print(f"{Fore.GREEN}Success! Authentication successful.")
        
        # Print some available models
        print(f"\nAvailable models:")
        for model in models.data[:5]:  # Show only first 5 models
            print(f"- {model.id}")
        print("...")
        
        # Try to list DALL-E models specifically
        dalle_models = [m for m in models.data if 'dall-e' in m.id.lower()]
        if dalle_models:
            print(f"\n{Fore.GREEN}DALL-E models available:")
            for model in dalle_models:
                print(f"- {model.id}")
        else:
            print(f"\n{Fore.YELLOW}No DALL-E models found.")
            print("Your API key may not have access to DALL-E services.")
        
        return True
    
    except Exception as e:
        print(f"{Fore.RED}Error: Authentication failed")
        print(f"Details: {str(e)}")
        
        if "authentication" in str(e).lower() or "key" in str(e).lower():
            print(f"\n{Fore.YELLOW}Possible issues:")
            print("1. The API key is incorrect")
            print("2. The API key has expired")
            print("3. The account has billing issues")
            
        return False

def main():
    parser = argparse.ArgumentParser(description="Check OpenAI API Key")
    parser.add_argument("--api-key", help="OpenAI API key to test")
    
    args = parser.parse_args()
    
    # Get API key from arguments or environment variable
    api_key = args.api_key or os.environ.get("OPENAI_API_KEY")
    
    if not api_key:
        print(f"{Fore.YELLOW}No API key provided via argument or environment variable.")
        api_key = input("Enter your OpenAI API key: ")
    
    result = check_api_key(api_key)
    return 0 if result else 1

if __name__ == "__main__":
    sys.exit(main()) 