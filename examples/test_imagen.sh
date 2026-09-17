#!/bin/bash
# A simple script to test the Google Imagen/Gemini integration

echo "NOTE: This will generate a text response, not an actual image."
echo "Google's Generative AI SDK doesn't currently support direct image generation."
echo "The script will generate and save a descriptive text response from Gemini instead."
echo ""

# The API key is read from the GOOGLE_API_KEY environment variable (or pass --api-key).
if [ -z "$GOOGLE_API_KEY" ]; then
  echo "GOOGLE_API_KEY is not set. Export it and rerun." >&2
  exit 1
fi

# Create output directory
mkdir -p output/imagen_test

# Run the example script with a test prompt
python3 examples/generate_with_imagen.py \
  --prompt "A Formula 1 car racing on a rainy track, with dramatic lighting, photorealistic style" \
  --size "1024x1024"

echo "Test completed. Check the output/imagen_test directory for results."
echo "To implement actual image generation, you would need to use the Vertex AI API:"
echo "https://cloud.google.com/vertex-ai/docs/generative-ai/image/generate-images" 