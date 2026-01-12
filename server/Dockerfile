FROM python:3.11-slim

# Install LibreOffice and Chromium for pyppeteer
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice-writer \
    libreoffice-impress \
    libreoffice-calc \
    chromium \
    chromium-driver \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set Chromium path for pyppeteer
ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium
ENV PYPPETEER_CHROMIUM_REVISION=1

# Set working directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Use fixed port 8080 (Railway will map it)
EXPOSE 8080

# Start server on port 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
