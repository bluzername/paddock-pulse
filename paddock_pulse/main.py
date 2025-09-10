#!/usr/bin/env python3
"""
PaddockPulse Main Script

This script orchestrates the end-to-end workflow:
1. Fetch F1 data from FastF1 API
2. Analyze interesting events using LLM
3. Generate social media posts about the events
4. Save the posts to text files
"""

import os
import logging
import argparse
import sys
import json
from datetime import datetime

from paddock_pulse.f1_data_fetcher import F1DataFetcher
from paddock_pulse.event_analyzer import F1EventAnalyzer
from paddock_pulse.post_generator import F1PostGenerator

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("paddock_pulse")

def setup_arg_parser():
    """Set up command line argument parser."""
    parser = argparse.ArgumentParser(description="PaddockPulse - F1 Social Media Content Generator")
    
    parser.add_argument(
        "--api-key", 
        dest="api_key",
        help="OpenRouter API key (overrides OPENROUTER_API_KEY environment variable)"
    )
    
    parser.add_argument(
        "--refresh", 
        action="store_true",
        help="Force refresh of F1 data even if cached data exists"
    )
    
    parser.add_argument(
        "--latest-race-only",
        action="store_true",
        help="Focus only on the most recent race when generating content"
    )
    
    parser.add_argument(
        "--historical-years",
        type=int,
        default=3,
        help="Number of historical years to fetch data for (default: 3)"
    )
    
    parser.add_argument(
        "--max-events",
        type=int,
        default=5,
        help="Maximum number of interesting events to identify (default: 5)"
    )
    
    parser.add_argument(
        "--data-dir",
        default="data",
        help="Directory to store F1 data (default: data)"
    )
    
    parser.add_argument(
        "--output-dir",
        default="output",
        help="Directory to store generated posts (default: output)"
    )
    
    parser.add_argument(
        "--posts-file",
        help="Path to a specific posts file to use instead of generating a new one"
    )
    
    parser.add_argument(
        "--posts-json",
        help="Path to save the posts in JSON format"
    )
    
    parser.add_argument(
        "--technical",
        action="store_true",
        help="Generate technical content focused on telemetry data and engineering insights"
    )
    
    parser.add_argument(
        "--101",
        action="store_true",
        help="Generate educational content about F1 basics for new fans"
    )
    
    parser.add_argument(
        "--num-topics",
        type=int,
        default=5,
        help="Number of educational topics to generate (only with --101)"
    )
    
    return parser

def run_paddock_pulse(posts_args):
    """
    Run the full PaddockPulse workflow: fetch data, analyze events, and generate posts.
    
    Args:
        posts_args: Namespace containing all arguments for the workflow
    
    Returns:
        Path to the generated posts JSON file
    """
    start_time = datetime.now()
    logger.info("Starting PaddockPulse workflow")
    
    # Check for API key
    api_key = posts_args.api_key or os.environ.get('OPENROUTER_API_KEY')
    if not api_key:
        logger.error("No OpenRouter API key provided. Please set OPENROUTER_API_KEY environment variable or use --api-key")
        return 1, None
    
    # Get the technical mode flag
    technical_mode = getattr(posts_args, 'technical', False)
    if technical_mode:
        logger.info("Running in TECHNICAL mode - focusing on telemetry data and engineering insights")
    
    # Step 1: Fetch F1 data
    logger.info("STEP 1: Fetching F1 data from FastF1 API")
    fetcher = F1DataFetcher(save_dir=posts_args.data_dir)
    
    # Check if we need to refresh or if we can use cached data
    f1_data = None
    if not posts_args.refresh:
        f1_data = fetcher.load_data()
        if f1_data:
            logger.info("Using cached F1 data")
    
    if not f1_data:
        logger.info("Fetching fresh F1 data")
        latest_race_only = posts_args.latest_race_only
        current_data, historical_data = fetcher.fetch_all_data(latest_race_only=latest_race_only)
        f1_data = {
            'current_season': current_data,
            'historical_data': historical_data,
            'fetch_time': datetime.now().isoformat()
        }
    
    # Step 2: Analyze interesting events
    logger.info("STEP 2: Analyzing interesting events with LLM")
    analyzer = F1EventAnalyzer(api_key=api_key, save_dir=posts_args.data_dir)
    events = analyzer.analyze_f1_data(f1_data, max_events=posts_args.max_events, technical_mode=technical_mode)
    
    if not events:
        logger.error("No interesting events found or LLM analysis failed")
        return 1, None
    
    logger.info(f"Identified {len(events)} interesting F1 events")
    
    # Step 3: Generate posts
    logger.info("STEP 3: Generating social media posts")
    generator = F1PostGenerator(api_key=api_key, save_dir=posts_args.output_dir)
    
    # Use num_posts if defined, otherwise fall back to max_events
    max_posts = getattr(posts_args, 'num_posts', posts_args.max_events)
    logger.info(f"Generating posts for {max_posts} events")
    
    posts = generator.generate_posts_from_events(events, max_posts=max_posts, technical_mode=technical_mode)
    
    if not posts:
        logger.error("Failed to generate any posts")
        return 1, None
    
    # Step 4: Display results
    logger.info("STEP 4: Workflow completed")
    logger.info(f"Generated {len(posts)} posts")
    
    # Print summary
    for i, post in enumerate(posts):
        logger.info(f"Post {i+1}: {post['event_title']}")
    
    # Get path to output files
    # Check if we're using the new output structure
    if hasattr(posts_args, 'posts_file') and posts_args.posts_file:
        # New structure - use the predetermined file paths
        posts_file = posts_args.posts_file
        # Make sure the parent directory exists
        os.makedirs(os.path.dirname(posts_file), exist_ok=True)
    else:
        # Legacy structure - create timestamp-based filenames in output_dir
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        mode_suffix = "_technical" if technical_mode else ""
        posts_file = os.path.join(posts_args.output_dir, f"f1_posts{mode_suffix}_{timestamp}.txt")
        # Make sure output directory exists
        os.makedirs(posts_args.output_dir, exist_ok=True)
    
    # Write the posts to the output file
    with open(posts_file, 'w') as f:
        for i, post in enumerate(posts):
            f.write(f"Post {i+1}: {post['event_title']}\n")
            f.write("=" * len(f"Post {i+1}: {post['event_title']}") + "\n")
            f.write(post['content'])
            f.write("\n\n")
    
    # Save JSON format if path provided
    if hasattr(posts_args, 'posts_json') and posts_args.posts_json:
        with open(posts_args.posts_json, 'w') as f:
            json.dump(posts, f, indent=2)
    
    logger.info(f"Posts saved to {posts_file}")
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    logger.info(f"Total runtime: {duration:.2f} seconds")
    
    return 0, posts_file

def run_f1_101_mode(output_dir='output', num_topics=5):
    """
    Run the F1 educational content generation workflow.
    
    Args:
        output_dir: Directory to store output files
        num_topics: Number of educational topics to generate
    
    Returns:
        Path to the generated posts JSON file
    """
    logging.info("Starting F1 educational content generation workflow")
    
    # Create output directory if it doesn't exist
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    posts_dir = os.path.join(output_dir, timestamp, 'posts')
    os.makedirs(posts_dir, exist_ok=True)
    
    # Initialize the post generator
    post_generator = F1PostGenerator(save_dir=posts_dir)
    
    # Generate F1 educational posts
    logging.info(f"Generating {num_topics} F1 educational topics for new fans")
    posts = post_generator.generate_f1_101_posts(num_topics=num_topics)
    
    # Save posts to a file
    if posts:
        output_file = os.path.join(posts_dir, 'f1_101_posts.txt')
        with open(output_file, 'w') as f:
            for i, post in enumerate(posts):
                f.write(f"Post {i+1}: {post['event_title']}\n")
                f.write(f"{'-' * 50}\n")
                f.write(f"{post['post_text']}\n\n")
                f.write(f"{post['hashtags']}\n\n")
        
        # Also save as JSON
        json_file = os.path.join(posts_dir, 'f1_101_posts.json')
        with open(json_file, 'w') as f:
            json.dump(posts, f, indent=2)
        
        logging.info(f"Successfully generated {len(posts)} F1 educational posts")
        logging.info(f"Posts saved to {output_file} and {json_file}")
        
        return json_file
    else:
        logging.error("Failed to generate F1 educational posts")
        return None

def main():
    """Main entry point for the PaddockPulse CLI"""
    parser = setup_arg_parser()
    args = parser.parse_args()
    
    try:
        # Check for incompatible options
        if args._101 and (args.refresh or args.latest_race_only):
            logging.warning("The --101 option is independent of --refresh and --latest-race-only. Those options will be ignored.")
        
        # Run the appropriate workflow
        if args._101:
            # Run F1 educational content generation workflow
            run_f1_101_mode(output_dir=args.output_dir, num_topics=args.num_topics)
        else:
            # Run the standard PaddockPulse workflow
            run_paddock_pulse(args)
        
        logging.info("PaddockPulse workflow completed successfully")
        return 0
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
        return 130  # Standard UNIX code for SIGINT
    except Exception as e:
        logger.exception(f"Unhandled exception: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 