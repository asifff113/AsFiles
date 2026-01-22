FROM python:3.11-slim

# Lightweight deployment without LibreOffice (saves ~600MB RAM)
# PPTX→PDF will use CloudConvert API or slide rendering instead
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

# Pre-download rembg model during build to avoid runtime download
# This caches the U2-Net model in the image
RUN python -c "from rembg import new_session; new_session('u2net')" || true

# Copy app code
COPY . .

# Use fixed port 8080 (Railway will map it)
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
# --limit-max-requests 50: Restart worker after 50 requests to prevent memory leaks
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1", "--limit-max-requests", "50"]
