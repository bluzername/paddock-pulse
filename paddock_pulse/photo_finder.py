"""
Photo Finder Module

This module is responsible for finding and downloading relevant public photos 
for Formula 1 posts that can be used on Instagram.
"""

import os
import re
import logging
import requests
import json
import time
from datetime import datetime
from urllib.parse import urlencode, quote_plus
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("photo_finder")

class PhotoFinder:
    """
    Class to find and download relevant public F1 photos for social media posts.
    """
    
    def __init__(self, output_dir='output'):
        """
        Initialize the PhotoFinder.
        
        Args:
            output_dir: Directory where post text files and images will be stored
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.unsplash_api_url = "https://api.unsplash.com/search/photos"
        self.pixabay_api_url = "https://pixabay.com/api/"
        self.pexels_api_url = "https://api.pexels.com/v1/search"
        
        # Load API keys from environment variables if available
        self.unsplash_api_key = os.environ.get('UNSPLASH_ACCESS_KEY')
        self.pixabay_api_key = os.environ.get('PIXABAY_API_KEY')
        self.pexels_api_key = os.environ.get('PEXELS_API_KEY')
        
        # Fallback to some free public APIs or search engines if API keys are not available
        if not (self.unsplash_api_key or self.pixabay_api_key or self.pexels_api_key):
            logger.warning("No photo API keys provided. Will use public web search as fallback.")
    
    def _extract_keywords(self, post_text, post_title):
        """
        Extract relevant keywords from post text and title.
        
        Args:
            post_text: The social media post text
            post_title: The title of the post/event
            
        Returns:
            List of relevant keywords for photo search
        """
        # Extract hashtags as keywords
        hashtags = re.findall(r'#(\w+)', post_text)
        
        # Extract team names, driver names, and other F1 related terms
        f1_terms = [
            "Formula 1", "F1", "Grand Prix", "GP", "Race", "Podium", "Circuit",
            "McLaren", "Mercedes", "Red Bull", "Ferrari", "Aston Martin", "Alpine",
            "Haas", "Williams", "Sauber", "Stake", "RB", "AlphaTauri"
        ]
        
        # Extract driver names
        driver_names = [
            "Verstappen", "Hamilton", "Leclerc", "Norris", "Russell", "Sainz",
            "Piastri", "Alonso", "Stroll", "Tsunoda", "Albon", "Gasly", "Ocon",
            "Magnussen", "Hulkenberg", "Ricciardo", "Zhou", "Bottas", "Sargeant",
            "Bearman", "Antonelli", "Max", "Lewis", "Charles", "Lando", "George",
            "Carlos", "Oscar", "Fernando", "Lance", "Yuki", "Alex", "Pierre", "Esteban",
            "Kevin", "Nico", "Daniel", "Guanyu", "Valtteri", "Logan", "Oliver", "Kimi"
        ]
        
        # Get words from the title and post
        title_words = [word for word in re.findall(r'\b(\w+)\b', post_title) if len(word) > 3]
        
        # Build up the final keyword list
        keywords = []
        
        # Add the most specific terms first
        if hashtags:
            keywords.extend(hashtags)
        
        # Add team and driver names found in the title or post
        for name in driver_names + f1_terms:
            if name.lower() in post_title.lower() or name.lower() in post_text.lower():
                keywords.append(name)
        
        # Add significant words from the title
        keywords.extend(title_words)
        
        # Make sure we have "Formula 1" or "F1" in the keywords
        if not any(k for k in keywords if "f1" in k.lower() or "formula" in k.lower()):
            keywords.append("Formula 1")
        
        # Remove duplicates while preserving order
        unique_keywords = []
        for kw in keywords:
            if kw not in unique_keywords:
                unique_keywords.append(kw)
        
        return unique_keywords[:5]  # Limit to top 5 keywords to avoid overly specific searches
    
    def _search_unsplash(self, query, per_page=3):
        """
        Search for photos on Unsplash.
        
        Args:
            query: Search query string
            per_page: Number of photos to return
            
        Returns:
            List of photo URLs or empty list if search failed
        """
        if not self.unsplash_api_key:
            return []
        
        params = {
            'query': query,
            'per_page': per_page,
            'client_id': self.unsplash_api_key
        }
        
        try:
            response = requests.get(f"{self.unsplash_api_url}?{urlencode(params)}")
            
            if response.status_code == 200:
                data = response.json()
                return [photo['urls']['regular'] for photo in data.get('results', [])]
            else:
                logger.error(f"Unsplash API error: {response.status_code} - {response.text}")
                return []
        except Exception as e:
            logger.error(f"Error searching Unsplash: {str(e)}")
            return []
    
    def _search_pixabay(self, query, per_page=3):
        """
        Search for photos on Pixabay.
        
        Args:
            query: Search query string
            per_page: Number of photos to return
            
        Returns:
            List of photo URLs or empty list if search failed
        """
        if not self.pixabay_api_key:
            return []
        
        params = {
            'q': query,
            'per_page': per_page,
            'key': self.pixabay_api_key,
            'image_type': 'photo'
        }
        
        try:
            response = requests.get(f"{self.pixabay_api_url}?{urlencode(params)}")
            
            if response.status_code == 200:
                data = response.json()
                return [photo['largeImageURL'] for photo in data.get('hits', [])]
            else:
                logger.error(f"Pixabay API error: {response.status_code} - {response.text}")
                return []
        except Exception as e:
            logger.error(f"Error searching Pixabay: {str(e)}")
            return []
    
    def _search_pexels(self, query, per_page=3):
        """
        Search for photos on Pexels.
        
        Args:
            query: Search query string
            per_page: Number of photos to return
            
        Returns:
            List of photo URLs or empty list if search failed
        """
        if not self.pexels_api_key:
            return []
        
        headers = {
            'Authorization': self.pexels_api_key
        }
        
        params = {
            'query': query,
            'per_page': per_page
        }
        
        try:
            response = requests.get(f"{self.pexels_api_url}?{urlencode(params)}", headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                return [photo['src']['large'] for photo in data.get('photos', [])]
            else:
                logger.error(f"Pexels API error: {response.status_code} - {response.text}")
                return []
        except Exception as e:
            logger.error(f"Error searching Pexels: {str(e)}")
            return []
    
    def _search_google_images(self, query, num_images=3):
        """
        Fallback method to search Google Images (without API).
        This is a simple implementation and should only be used as last resort.
        
        Args:
            query: Search query string
            num_images: Number of photos to return
            
        Returns:
            List of photo URLs or empty list if search failed
        """
        # We'll use a custom search engine instead of scraping to avoid issues
        # This simulates a search without requiring an API key but is limited
        base_url = "https://serpapi.com/search.json"
        
        query = f"{query} formula 1 high quality"
        params = {
            'q': query,
            'tbm': 'isch',  # Image search
            'api_key': "demo"  # Demo key, very limited
        }
        
        try:
            response = requests.get(f"{base_url}?{urlencode(params)}")
            
            if response.status_code == 200:
                data = response.json()
                images = data.get('images_results', [])
                return [img.get('original') for img in images[:num_images] if img.get('original')]
            else:
                logger.warning(f"Google image search failed: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Error searching Google Images: {str(e)}")
            return []
    
    def _fallback_search_f1_images(self, keywords):
        """
        Fallback method that returns URLs to public F1 images.
        
        Args:
            keywords: List of search keywords
            
        Returns:
            List of public F1 image URLs
        """
        # These are public domain or Creative Commons F1 images
        f1_public_images = [
            "https://upload.wikimedia.org/wikipedia/commons/6/62/Formel1_Ferrari_2018_%2842076248360%29.jpg",
            "https://upload.wikimedia.org/wikipedia/commons/2/26/Zhou_Guanyu_-_Alfa_Romeo_-_2023_Monaco_Grand_Prix_%28Qualifying%29.jpg",
            "https://upload.wikimedia.org/wikipedia/commons/e/e0/Carlos_Sainz_Jr._2021_Spanish_GP.jpg",
            "https://upload.wikimedia.org/wikipedia/commons/7/7a/FIA_F1_Austria_2022_Nr._1_Verstappen.jpg",
            "https://upload.wikimedia.org/wikipedia/commons/6/61/Max_Verstappen_2017_Malaysia_FP1_1.jpg",
            "https://upload.wikimedia.org/wikipedia/commons/3/36/Fernando_Alonso_2017_Malaysia_FP1.jpg",
            "https://upload.wikimedia.org/wikipedia/commons/9/9a/Lewis_Hamilton_2021_Austrian_GP.jpg",
            "https://upload.wikimedia.org/wikipedia/commons/2/28/Charles_Leclerc_2019_in_Austria.jpg",
            "https://upload.wikimedia.org/wikipedia/commons/a/ac/Lando_Norris_2019_in_Austria.jpg",
            "https://upload.wikimedia.org/wikipedia/commons/e/e3/George_Russell_2021_Austrian_GP.jpg",
            "https://upload.wikimedia.org/wikipedia/commons/8/81/Sergio_Perez_2019_in_Austria.jpg",
            "https://upload.wikimedia.org/wikipedia/commons/3/35/Pit_stop_for_Valtteri_Bottas_in_2022_United_States_Grand_Prix.jpg",
            "https://upload.wikimedia.org/wikipedia/commons/2/2b/Mercedes_W13_at_2022_British_Grand_Prix_%283%29.jpg",
            "https://upload.wikimedia.org/wikipedia/commons/f/f9/McLaren_MCL36_at_2022_British_Grand_Prix.jpg",
            "https://upload.wikimedia.org/wikipedia/commons/0/01/Red_Bull_RB18_Bahrain_GP_2022_perspective.jpg"
        ]
        
        # Team-specific images
        team_images = {
            "mclaren": [
                "https://upload.wikimedia.org/wikipedia/commons/f/f9/McLaren_MCL36_at_2022_British_Grand_Prix.jpg",
                "https://upload.wikimedia.org/wikipedia/commons/a/ac/Lando_Norris_2019_in_Austria.jpg",
                "https://upload.wikimedia.org/wikipedia/commons/0/08/Oscar_Piastri_at_the_2023_Monaco_Grand_Prix.jpg"
            ],
            "mercedes": [
                "https://upload.wikimedia.org/wikipedia/commons/2/2b/Mercedes_W13_at_2022_British_Grand_Prix_%283%29.jpg",
                "https://upload.wikimedia.org/wikipedia/commons/9/9a/Lewis_Hamilton_2021_Austrian_GP.jpg",
                "https://upload.wikimedia.org/wikipedia/commons/e/e3/George_Russell_2021_Austrian_GP.jpg"
            ],
            "red bull": [
                "https://upload.wikimedia.org/wikipedia/commons/0/01/Red_Bull_RB18_Bahrain_GP_2022_perspective.jpg",
                "https://upload.wikimedia.org/wikipedia/commons/7/7a/FIA_F1_Austria_2022_Nr._1_Verstappen.jpg",
                "https://upload.wikimedia.org/wikipedia/commons/8/81/Sergio_Perez_2019_in_Austria.jpg"
            ],
            "ferrari": [
                "https://upload.wikimedia.org/wikipedia/commons/6/62/Formel1_Ferrari_2018_%2842076248360%29.jpg",
                "https://upload.wikimedia.org/wikipedia/commons/2/28/Charles_Leclerc_2019_in_Austria.jpg",
                "https://upload.wikimedia.org/wikipedia/commons/e/e0/Carlos_Sainz_Jr._2021_Spanish_GP.jpg"
            ],
            "williams": [
                "https://upload.wikimedia.org/wikipedia/commons/4/42/FW43B_On_Transporter_%28cropped%29.jpg",
                "https://upload.wikimedia.org/wikipedia/commons/f/f1/Alex_Albon_2019_Italy.jpg",
                "https://upload.wikimedia.org/wikipedia/commons/1/18/Nicholas_Latifi_Williams_British_GP_2022.jpg"
            ],
            "haas": [
                "https://upload.wikimedia.org/wikipedia/commons/a/a0/Kevin_Magnussen_%2852859801257%29.jpg",
                "https://upload.wikimedia.org/wikipedia/commons/4/49/Haas_VF-23_2023_British_GP.jpg",
                "https://upload.wikimedia.org/wikipedia/commons/2/23/Nico_H%C3%BClkenberg_2022_Bahrain_Grand_Prix.jpg"
            ]
        }
        
        # Select images based on keywords
        selected_images = []
        
        # Check if any keywords match specific teams
        for keyword in keywords:
            for team, images in team_images.items():
                if team.lower() in keyword.lower():
                    # Add team-specific images
                    selected_images.extend(images)
                    break
        
        # If we don't have enough team-specific images, add generic F1 images
        while len(selected_images) < 3:
            for img in f1_public_images:
                if img not in selected_images:
                    selected_images.append(img)
                    if len(selected_images) >= 3:
                        break
        
        return selected_images[:3]  # Return only 3 images
    
    def _download_image(self, url, output_path):
        """
        Download an image from a URL.
        
        Args:
            url: URL of the image to download
            output_path: Path where the image will be saved
            
        Returns:
            True if download was successful, False otherwise
        """
        try:
            response = requests.get(url, stream=True)
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
    
    def find_photos_for_post(self, post_text, post_title, output_dir):
        """
        Find and download relevant photos for a social media post.
        
        Args:
            post_text: The text content of the post
            post_title: The title of the post/event
            output_dir: Directory to save the downloaded photos
            
        Returns:
            List of paths to the downloaded photos
        """
        os.makedirs(output_dir, exist_ok=True)
        
        # Extract keywords from the post
        keywords = self._extract_keywords(post_text, post_title)
        query = " ".join(keywords[:3])  # Use top 3 keywords for the search
        
        logger.info(f"Searching for photos with keywords: {keywords}")
        
        # Try different photo APIs
        photo_urls = []
        
        # Try Unsplash first
        unsplash_results = self._search_unsplash(f"{query} Formula 1")
        if unsplash_results:
            photo_urls.extend(unsplash_results)
        
        # Then try Pixabay
        if len(photo_urls) < 3:
            pixabay_results = self._search_pixabay(f"{query} Formula 1")
            if pixabay_results:
                photo_urls.extend(pixabay_results)
        
        # Then try Pexels
        if len(photo_urls) < 3:
            pexels_results = self._search_pexels(f"{query} Formula 1")
            if pexels_results:
                photo_urls.extend(pexels_results)
        
        # If we still don't have enough photos, use Google Images
        if len(photo_urls) < 3:
            google_results = self._search_google_images(f"{query} Formula 1")
            if google_results:
                photo_urls.extend(google_results)
        
        # If all else fails, use our fallback public F1 images
        if len(photo_urls) < 3:
            fallback_results = self._fallback_search_f1_images(keywords)
            if fallback_results:
                photo_urls.extend(fallback_results)
        
        # Ensure we only have 3 unique URLs
        unique_urls = []
        for url in photo_urls:
            if url not in unique_urls and len(unique_urls) < 3:
                unique_urls.append(url)
        
        # Download the photos
        downloaded_paths = []
        for i, url in enumerate(unique_urls[:3]):
            image_filename = f"{i+1}_{post_title.replace(' ', '_')[:30]}.jpg"
            image_path = os.path.join(output_dir, image_filename)
            
            if self._download_image(url, image_path):
                downloaded_paths.append(image_path)
                logger.info(f"Downloaded image {i+1} to {image_path}")
            else:
                logger.error(f"Failed to download image {i+1} from {url}")
        
        return downloaded_paths
    
    def find_photos_for_posts_file(self, posts_file):
        """
        Find photos for all posts in a posts file.
        
        Args:
            posts_file: Path to the posts text file
            
        Returns:
            Dictionary mapping post titles to lists of photo paths
        """
        # Extract base name of posts file without extension
        base_name = os.path.splitext(os.path.basename(posts_file))[0]
        photos_dir = os.path.join(self.output_dir, f"{base_name}_photos")
        
        logger.info(f"Finding photos for posts in {posts_file}")
        logger.info(f"Photos will be saved to {photos_dir}")
        
        # Create directory for photos
        os.makedirs(photos_dir, exist_ok=True)
        
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
                    posts.append({"title": title, "text": post_text})
                
                i += 3
            else:
                i += 1
        
        photo_paths = {}
        
        # Find photos for each post
        for post in posts:
            post_title = post["title"]
            post_text = post["text"]
            
            # Create directory for this post's photos
            post_dir = os.path.join(photos_dir, re.sub(r'[^\w\s-]', '', post_title).replace(' ', '_'))
            
            # Find and download photos
            paths = self.find_photos_for_post(post_text, post_title, post_dir)
            
            if paths:
                photo_paths[post_title] = paths
                logger.info(f"Found {len(paths)} photos for post: {post_title}")
            else:
                logger.warning(f"No photos found for post: {post_title}")
        
        # Save a summary file
        summary_path = os.path.join(photos_dir, "summary.json")
        with open(summary_path, 'w') as f:
            json.dump(photo_paths, f, indent=2)
        
        logger.info(f"Photo search completed. Results saved to {photos_dir}")
        return photo_paths

def main():
    """Main function to find photos for the most recent posts file."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Find and download photos for F1 social media posts")
    parser.add_argument("--posts-file", help="Path to the posts text file")
    parser.add_argument("--output-dir", default="output", help="Directory to save photos (default: output)")
    args = parser.parse_args()
    
    finder = PhotoFinder(output_dir=args.output_dir)
    
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
    
    # Find photos for all posts in the file
    finder.find_photos_for_posts_file(posts_file)
    return 0

if __name__ == "__main__":
    main() 