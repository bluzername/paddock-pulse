# PaddockPulse Image Generation Examples

This directory contains examples for generating images with different providers in the PaddockPulse project.

## Available Examples

### 1. Generate with Gemini/Imagen

```bash
./test_imagen.sh
```

**Note:** The current implementation using Google's Generative AI SDK only generates text descriptions, not actual images. This is because the Python SDK doesn't directly support image generation.

For actual image generation with Google's APIs, you would need to use the Vertex AI API as detailed in [Google's documentation](https://cloud.google.com/vertex-ai/docs/generative-ai/image/generate-images).

### 2. Generate with Midjourney

```bash
# This requires a GoAPI key
./test_midjourney.sh  # (if available)
```

### 3. Generate with OpenAI DALL-E

```bash
# This requires an OpenAI API key
./test_dalle.sh  # (if available)
```

## Image Generation Providers

The PaddockPulse project supports different image generation providers:

1. **OpenAI DALL-E** - Direct image generation through OpenAI's API
2. **Midjourney** - Image generation through GoAPI as a proxy to Midjourney
3. **Google Imagen/Gemini** - Currently only generates text descriptions due to SDK limitations

## Environment Variables

The examples use environment variables for API keys:

- `OPENAI_API_KEY` - Your OpenAI API key
- `GOAPI_KEY` - Your GoAPI key (for Midjourney)
- `GOOGLE_API_KEY` - Your Google API key (for Gemini/Imagen)

You can also pass these keys directly using command-line arguments. 