#!/usr/bin/env bash
# Render build script

set -e

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

echo "Build complete!"
