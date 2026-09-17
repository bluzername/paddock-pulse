"""
Central model configuration for PaddockPulse.

Every LLM, image and TTS model id used by the pipeline is defined here once.
Each value can be overridden with an environment variable (loaded from .env by
run_all.py via python-dotenv). Empty values fall back to the default.
"""

import os


def _env(name, default):
    """Return the environment value for name, or default when unset or empty."""
    value = os.environ.get(name, "")
    return value.strip() or default


# OpenRouter chat models (https://openrouter.ai/models)
ANALYSIS_MODEL = _env("PP_ANALYSIS_MODEL", "meta-llama/llama-4-maverick")  # event_analyzer
TEXT_MODEL = _env("PP_TEXT_MODEL", "openai/gpt-4o")  # post_generator
PROMPT_MODEL = _env("PP_PROMPT_MODEL", "meta-llama/llama-4-maverick")  # prompt_generator

# OpenAI image models. IMAGE_MODEL is the default for --model; when it is
# gpt-image-1 the generator falls back to IMAGE_FALLBACK_MODEL on failure.
IMAGE_MODEL = _env("PP_IMAGE_MODEL", "dall-e-3")
IMAGE_FALLBACK_MODEL = _env("PP_IMAGE_FALLBACK_MODEL", "dall-e-3")

# Google Imagen model used with the generativelanguage :predict endpoint
IMAGEN_MODEL = _env("PP_IMAGEN_MODEL", "imagen-4.0-generate-001")

# HiveAI model used when --provider hiveai gets an unrecognised --model
HIVEAI_MODEL = _env("PP_HIVEAI_MODEL", "flux-schnell-enhanced")

# ElevenLabs TTS model
TTS_MODEL = _env("PP_TTS_MODEL", "eleven_turbo_v2")
