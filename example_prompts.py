#!/usr/bin/env python3
"""
Example script to demonstrate the prompt generator with a sample post
"""

import os
from paddock_pulse.prompt_generator import PromptGenerator

# Sample F1 post
SAMPLE_POST_TITLE = "Hamilton's Masterclass in the Rain at Spa"
SAMPLE_POST_TEXT = """Lewis Hamilton showcased his wet-weather prowess once again with a dominant drive at Spa-Francorchamps! 🌧️ #BelgianGP

Starting from P3, Hamilton expertly navigated treacherous conditions to take the lead by lap 10, demonstrating why he's considered one of F1's greatest rain specialists. 

The Mercedes driver built a commanding 22-second lead over Max Verstappen, who put in a stellar performance himself to secure P2 for Red Bull despite challenging handling issues.

Charles Leclerc rounded out the podium for Ferrari, benefiting from a perfectly timed pit stop as the rain intensity changed.

Hamilton's victory marks his 6th win at Spa and extends his championship lead. A truly masterful display of car control and tactical brilliance! 🏆 #F1 #Hamilton #MercedesAMG"""

# Output directory
OUTPUT_DIR = "example_output"

def main():
    """Generate prompts for a sample post"""
    # Create the output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Create a prompt generator instance
    generator = PromptGenerator(output_dir=OUTPUT_DIR)
    
    # Generate prompts for the sample post
    post_dir = os.path.join(OUTPUT_DIR, "sample_post")
    prompts = generator.generate_prompts_for_post(SAMPLE_POST_TEXT, SAMPLE_POST_TITLE, post_dir)
    
    # Print the generated prompts
    print(f"\nGenerated {len(prompts)} image prompts for the sample post:\n")
    for i, prompt in enumerate(prompts):
        print(f"PROMPT {i+1}:")
        print("-" * 80)
        print(prompt)
        print("-" * 80)
        print()
    
    print(f"Prompt files have been saved to: {post_dir}")
    
if __name__ == "__main__":
    main() 