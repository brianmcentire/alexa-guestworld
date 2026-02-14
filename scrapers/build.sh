#!/bin/bash
# Build the scraper Lambda deployment package.
# Output: build/scraper-lambda.zip

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="$SCRIPT_DIR/build"
PKG_DIR="$BUILD_DIR/package"

rm -rf "$BUILD_DIR"
mkdir -p "$PKG_DIR"

# Install dependencies
pip install -r "$SCRIPT_DIR/requirements.txt" -t "$PKG_DIR" --quiet

# Copy handlers and core modules
cp "$SCRIPT_DIR/guestworld_scraper_handler.py" "$PKG_DIR/"
cp "$SCRIPT_DIR/guestworld_scraper_core.py" "$PKG_DIR/"
cp "$SCRIPT_DIR/challenge_scraper_handler.py" "$PKG_DIR/"
cp "$SCRIPT_DIR/challenge_scraper_core.py" "$PKG_DIR/"

# Create zip
cd "$PKG_DIR"
zip -r "$BUILD_DIR/scraper-lambda.zip" . --quiet

echo "Built: $BUILD_DIR/scraper-lambda.zip"
