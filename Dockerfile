FROM python:3.11-slim

# Install system dependencies including ffmpeg and build tools
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    wget \
    gcc \
    g++ \
    python3-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies with verbose output
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir --force-reinstall moviepy && \
    python -c "import moviepy.editor; print('MoviePy installed successfully')"

# Copy application code
COPY . .

# Create temp directory for video processing
RUN mkdir -p /tmp/video_processing

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV IMAGEIO_FFMPEG_EXE=/usr/bin/ffmpeg

# Run the bot
CMD ["python", "spoof_bot.py"]