FROM python:3.11-slim

# Install uv using pip
RUN pip install --no-cache-dir uv

# Verify uv installation
RUN uv --version

# Set working directory
WORKDIR /app

# Create non-root user and pre-configure cache directory
RUN mkdir -p /root/.cache/uv /app/bin/

# Copy all files from the dist directory built by CI
COPY dist/ .
COPY tools/ffprobe /app/bin/ffprobe

# Install dependencies (still using root to ensure permissions)
RUN uv sync

# Add permissions
RUN chmod 0755 /app/bin/*

# Expose application port
EXPOSE 30000

# Set environment variables, specifying uv cache directory and user home directory
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:/app/bin:$PATH" \
    HOME="/root" \
    UV_CACHE_DIR="/root/.cache/uv"

# Startup command
CMD ["uv", "run", "main.py", "--workers", "4"]
