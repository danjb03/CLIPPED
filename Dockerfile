# Hosted Clip Engine worker: Python API + ffmpeg + Node/Remotion (headless Chrome).
# Transcription is via AssemblyAI (TRANSCRIBE_BACKEND=assemblyai), so no heavy ML.
FROM node:20-bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1

# System deps: python, ffmpeg, OpenCV/MediaPipe libs, and the libraries
# Remotion's headless Chrome needs.
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv \
    ffmpeg ca-certificates \
    fonts-liberation fonts-dejavu-core fonts-noto-core \
    libgl1 libglib2.0-0 \
    libnss3 libdbus-1-3 libatk1.0-0 libgbm1 libasound2 \
    libxrandr2 libxkbcommon0 libxfixes3 libxcomposite1 libxdamage1 \
    libatk-bridge2.0-0 libpango-1.0-0 libcairo2 libcups2 \
    && rm -rf /var/lib/apt/lists/*

# Nicer caption fonts (optional — don't fail the build if a package is missing).
# Open Sans is the carousel default (close to the iOS reference); Inter is the
# open-source SF Pro alternative — even closer; Montserrat for variety.
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-montserrat fonts-open-sans fonts-inter \
    || true; rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps (slim, managed-transcription stack)
COPY worker/requirements.docker.txt worker/requirements.docker.txt
RUN pip3 install --no-cache-dir --break-system-packages \
    -r worker/requirements.docker.txt

# Web deps for Remotion, then bake the headless browser into the image
COPY web/package.json web/package-lock.json web/
RUN cd web && npm ci
COPY web web
RUN cd web && npx remotion browser ensure

# Worker code
COPY worker worker

ENV TRANSCRIBE_BACKEND=assemblyai
EXPOSE 8000
WORKDIR /app/worker
# Render/Railway/Fly inject $PORT; default to 8000 locally.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
