FROM python:3.11-slim

# Lightweight deployment for Fly.io free tier (256MB)
# Using remove.bg API for background removal instead of heavy rembg
RUN apt-get update && apt-get install -y --no-install-recommends \
    # lxml dependencies (required for XML processing)
    libxml2-dev \
    libxslt1-dev \
    # Poppler for pdf2image (PDF rendering)
    poppler-utils \
    # Basic fonts
    fonts-liberation \
    fonts-dejavu-core \
    fontconfig \
    # Clean up aggressively
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* \
    && rm -rf /usr/share/doc /usr/share/man

# Set working directory
WORKDIR /app

# Copy requirements and install with optimizations
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && rm -rf ~/.cache/pip /root/.cache

# Copy app code
COPY . .

# Use fixed port 8080
EXPOSE 8080

# Memory-efficient environment variables
ENV MALLOC_ARENA_MAX=2
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
# Use pure Python slide renderer (no LibreOffice needed, unlimited & free)
ENV PPTX_CONVERT_METHOD=sliderender
# Disable pyppeteer auto-download
ENV PYPPETEER_SKIP_CHROMIUM_DOWNLOAD=true

# Start server with memory management
# --workers 1: Single worker to reduce memory
# --limit-max-requests 100: Restart worker periodically to prevent memory leaks
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1", "--limit-max-requests", "100"]
