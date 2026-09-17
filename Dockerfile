FROM python:3.11-slim

WORKDIR /app

# ffmpeg is needed by moviepy and openai-whisper (image_concat.py)
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# API keys are passed at run time, e.g. docker run --env-file .env paddockpulse posts
ENTRYPOINT ["python", "run_all.py"]
CMD ["--help"]
