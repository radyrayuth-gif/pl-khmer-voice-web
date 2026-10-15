FROM python:3.11-slim

# Install system dependencies (ffmpeg is essential for audio merging & conversion)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency definition and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all application code
COPY . .

# Create audio output directory
RUN mkdir -p audio_output

# Expose port (Render/Koyeb/HuggingFace automatically injects PORT or uses 8000/10000)
ENV PORT=8000
EXPOSE 8000

# Start FastAPI server via uvicorn
CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${PORT:-8000}"]
