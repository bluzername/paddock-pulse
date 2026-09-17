# PaddockPulse

Command line pipeline that turns Formula 1 race data into social media content.
It pulls session and results data with [FastF1](https://docs.fastf1.dev/), asks an
OpenRouter-hosted LLM to pick the most interesting events, writes posts about them,
generates image prompts, and optionally renders images and voiceovers. A separate
helper stitches images and audio into captioned videos.

Pipeline: `f1_data_fetcher` -> `event_analyzer` -> `post_generator` -> `prompt_generator`
-> `image_generator` (optional) -> `voiceover_generator` (optional) -> `image_concat.py` (optional).

## Requirements

- Python 3.11 or newer
- `ffmpeg` on the PATH (used by moviepy and openai-whisper in `image_concat.py`)
- API keys for the providers you use (see the table below). OpenRouter is required
  for everything except `images` and `voiceovers` run on their own.

## Install

```bash
git clone https://github.com/bluzername/paddock-pulse.git
cd paddock-pulse
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # then fill in the keys you need
```

`./setup.sh` (or `make setup`) does the same on macOS/Linux. `pip install -e .`
additionally installs a `paddockpulse` console script that runs `paddock_pulse.main`.

## Environment variables

`run_all.py` loads `.env` with python-dotenv. Module CLIs read the same variables
from the environment. All model ids are optional and default to the values in
`paddock_pulse/config.py`.

| Variable | Used by | Required for |
|----------|---------|--------------|
| `OPENROUTER_API_KEY` | event_analyzer, post_generator, prompt_generator | posts, prompts, f1-101 and every `full-*` mode |
| `OPENAI_API_KEY` | image_generator (`--provider openai`) | images with the default provider |
| `SKIP_GPT_IMAGE_1` | image_generator | optional: `true` skips gpt-image-1 and uses the fallback model |
| `ELEVEN_LABS_API_KEY` | voiceover_generator | voiceovers, full-with-voiceovers, full-complete |
| `GOAPI_KEY` | image_generator (`--provider midjourney`) | Midjourney via GoAPI |
| `GOOGLE_API_KEY` | image_generator (`--provider imagen`) | Google Imagen |
| `HIVEAI_API_KEY` | image_generator (`--provider hiveai`), hiveai_demo | HiveAI |
| `UNSPLASH_ACCESS_KEY`, `PIXABAY_API_KEY`, `PEXELS_API_KEY` | photo_finder | optional stock photo lookup |
| `PP_ANALYSIS_MODEL` | event_analyzer | default `meta-llama/llama-4-maverick` (OpenRouter) |
| `PP_TEXT_MODEL` | post_generator | default `openai/gpt-4o` (OpenRouter) |
| `PP_PROMPT_MODEL` | prompt_generator | default `meta-llama/llama-4-maverick` (OpenRouter) |
| `PP_IMAGE_MODEL` | image_generator, run_all `--model` default | default `dall-e-3`; set `gpt-image-1` to try it first |
| `PP_IMAGE_FALLBACK_MODEL` | image_generator | default `dall-e-3`, used when gpt-image-1 fails |
| `PP_IMAGEN_MODEL` | image_generator | default `imagen-4.0-generate-001` |
| `PP_HIVEAI_MODEL` | image_generator, hiveai_demo | default `flux-schnell-enhanced` |
| `PP_TTS_MODEL` | voiceover_generator | default `eleven_turbo_v2` |

Keys can also be passed on the command line (`--api-key`, `--openai-api-key`,
`--eleven-labs-api-key`, `--goapi-key`, `--google-key`); the flag wins over the
environment. `python run_all.py --key-debug` prints masked diagnostics.

## Usage

`run_all.py` is the main entry point. Every run writes to
`output/<YYYYMMDD_HHMMSS>/{posts,prompts,images,voiceovers}/`. F1 data is cached
under `data/` (use `--refresh` to refetch).

```bash
python run_all.py                       # no subcommand: fetch data, write posts and prompts
python run_all.py posts --latest-race-only --num-posts 3
python run_all.py prompts --posts-file output/<ts>/posts/f1_posts.txt
python run_all.py images --provider openai --model dall-e-3 --size 1024x1024
python run_all.py voiceovers --posts-folder output/<ts>/posts
python run_all.py full-with-images --latest-race-only
python run_all.py full-with-voiceovers
python run_all.py full-complete --provider imagen --google-key ...
python run_all.py f1-101 --num-topics 5 --with-images --with-voiceovers
```

| Subcommand | What it does | Notable flags |
|------------|--------------|---------------|
| `posts` | Fetch F1 data, analyse events, write posts | `--refresh`, `--latest-race-only`, `--historical-years`, `--max-events`, `--num-posts`, `--technical` |
| `prompts` | Generate image prompts for a posts file | `--posts-file`, `--technical` |
| `images` | Render images for the latest (or given) prompts | `--provider {openai,midjourney,imagen}`, `--model`, `--size`, `--aspect-ratio`, `--quality`, `--style`, `--skip-gpt-image-1`, `--goapi-key`, `--google-key` |
| `voiceovers` | ElevenLabs narration for each post | `--posts-file` or `--posts-folder`, `--eleven-labs-api-key` |
| `full-with-images` | posts + prompts + images | posts flags plus images flags |
| `full-with-voiceovers` | posts + prompts + voiceovers | posts flags plus `--eleven-labs-api-key` |
| `full-complete` | posts + prompts + images + voiceovers | all of the above |
| `f1-101` | Educational "F1 basics" posts without race data | `--num-topics`, `--with-images`, `--with-voiceovers`, image flags |

Global flags (before the subcommand): `--api-key`, `--openai-api-key`, `--data-dir`,
`--output-dir`, `--posts-folder`, `--key-debug`, `--latest-race-only`.

### Module command lines

Each stage can also run on its own:

```bash
python -m paddock_pulse.main --latest-race-only --max-events 5   # data + analysis + posts (also: --101)
python -m paddock_pulse.prompt_generator --posts-file <posts.txt> [--model ...] [--technical]
python -m paddock_pulse.image_generator --provider {openai,midjourney,imagen,hiveai} --prompts-dir <dir>
python -m paddock_pulse.voiceover_generator --posts-file <posts.txt>
python -m paddock_pulse.photo_finder --posts-file <posts.txt>       # stock photos, optional
python paddock_pulse/hiveai_demo.py                                  # single HiveAI test image
```

### Video assembly

`image_concat.py` combines a folder of images with a voiceover into a vertical
(1080x1920) video with Whisper-timed captions, either for one post or for a whole
`output/<ts>` directory in batch mode:

```bash
python image_concat.py --images <dir> --audio <file.mp3> --output <out.mp4> \
    --template-image <logo.png> --template-audio <outro.mp3>
python image_concat.py --batch-directory output/<ts> --simple-mode
```

`--template-image` and `--template-audio` default to paths that only exist on the
original author's machine; pass your own or expect the outro to be skipped.
`scripts/background_coloring.py` flattens a transparent PNG onto a solid colour.
`example_prompts.py` and `example_images.py` run the prompt and image stages on a
built-in sample post.

## Development

```bash
pip install ruff
make lint            # ruff check . && python -m compileall -q .
```

CI (`.github/workflows/ci.yml`) runs exactly those two checks on Python 3.11.
There is no automated test suite. Dependabot watches pip and GitHub Actions weekly.

A `Dockerfile` is included (`docker build -t paddockpulse .` then
`docker run --env-file .env paddockpulse posts`). It builds against the current
layout but is not built in CI.

## Known limitations

- No tests; the pipeline is exercised only manually against live APIs.
- Google says Imagen models on the Gemini API are deprecated (shutdown announced
  for 2026-08-17). `--provider imagen` may stop working; the model id is
  configurable via `PP_IMAGEN_MODEL`.
- The gpt-image-1 path expects an image URL in the response and falls back to
  `PP_IMAGE_FALLBACK_MODEL` when none is returned, so `--model gpt-image-1` can
  bill one extra request per image.
- `image_concat.py` is a 2500-line single file with machine-specific defaults.
- `photo_finder.py` is optional and not wired into `run_all.py`.

## License

MIT, see `LICENSE`.
