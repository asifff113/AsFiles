#!/usr/bin/env bash
# Render build script - installs LibreOffice for PPTX/DOCX conversion

set -e

# Install LibreOffice (minimal)
apt-get update
apt-get install -y --no-install-recommends \
    libreoffice-writer \
    libreoffice-impress \
    libreoffice-calc \
    libreoffice-common

# Clean up to reduce image size
apt-get clean
rm -rf /var/lib/apt/lists/*

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

echo "Build complete! LibreOffice installed for document conversions."
