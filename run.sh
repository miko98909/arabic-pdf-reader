#!/bin/bash
# Setup and run the Arabic PDF Reader (macOS).
# Creates a virtual environment on first run, installs dependencies,
# downloads OCR data if missing, then launches the reader.

set -e
cd "$(dirname "$0")"

# Homebrew Python ships tkinter separately
if ! python3 -c "import tkinter" >/dev/null 2>&1; then
    echo "tkinter missing — installing python-tk via Homebrew..."
    brew install python-tk || brew install "python-tk@$(python3 -c 'import sys;print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
fi

if [ ! -d venv ]; then
    echo "creating virtual environment..."
    python3 -m venv venv
fi
source venv/bin/activate

pip install -q -r requirements.txt

if [ ! -f tessdata/ara.traineddata ]; then
    echo "downloading Arabic OCR data..."
    python download_tessdata.py
fi

python pdf_reader.py "$@"
