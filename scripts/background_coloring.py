import sys
from PIL import Image

def hex_to_rgb(hex_color):
    """Convert hex color string like '#f5f5f5' to RGB tuple."""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def replace_background(input_path, output_path, hex_color):
    img = Image.open(input_path).convert("RGBA")
    background_color = hex_to_rgb(hex_color)

    # Create a new background image with the specified color
    background = Image.new("RGBA", img.size, background_color + (255,))

    # Composite the image onto the background (preserving alpha)
    combined = Image.alpha_composite(background, img)

    # Save the result (convert to RGB to remove alpha)
    combined.convert("RGB").save(output_path, "PNG")
    print(f"Saved with new background color to: {output_path}")

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python replace_background.py <input.png> <output.png> <#hexcolor>")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]
    hex_color = sys.argv[3]

    replace_background(input_path, output_path, hex_color)