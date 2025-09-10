#!/usr/bin/env python3
"""
Simple test script to create a video from an image and audio file using MoviePy.
This is a minimal test to isolate issues with the MoviePy library.
"""

import os
import sys
import argparse
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips

def create_simple_video(image_path, audio_path, output_path):
    """
    Create a simple video from one image and an audio file.
    
    Args:
        image_path: Path to the image
        audio_path: Path to the audio file
        output_path: Path to save the output video
        
    Returns:
        str: Path to the output video or None if failed
    """
    print(f"Creating video from image {image_path} and audio {audio_path}")
    
    try:
        # Create an image clip
        img_clip = ImageClip(image_path)
        
        # Load audio
        audio_clip = AudioFileClip(audio_path)
        duration = audio_clip.duration
        print(f"Audio duration: {duration:.2f} seconds")
        
        # Set duration of image clip to match audio
        img_clip = img_clip.set_duration(duration)
        
        # Set audio on the image clip
        video = img_clip.set_audio(audio_clip)
        
        # Write video file
        print(f"Writing video to {output_path}")
        video.write_videofile(
            output_path,
            codec='libx264',
            audio_codec='aac',
            fps=24
        )
        
        print(f"Video created successfully: {output_path}")
        return output_path
        
    except Exception as e:
        print(f"Error creating video: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    parser = argparse.ArgumentParser(description="Create a simple video from an image and audio file")
    parser.add_argument("--image", required=True, help="Path to the image")
    parser.add_argument("--audio", required=True, help="Path to the audio file")
    parser.add_argument("--output", default="simple_output.mp4", help="Path to the output video")
    
    args = parser.parse_args()
    
    create_simple_video(args.image, args.audio, args.output)

if __name__ == "__main__":
    main() 