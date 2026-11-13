#!/usr/bin/env python3
"""Download Arabic (and English) Tesseract OCR data into ./tessdata.

Uses the high-quality 'tessdata_best' models. Run once before using the
reader on scanned PDFs:
    python3 download_tessdata.py
"""

import os
import urllib.request

BASE = "https://github.com/tesseract-ocr/tessdata_best/raw/main"
LANGS = ["ara", "eng"]
DEST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tessdata")


def main():
    os.makedirs(DEST, exist_ok=True)
    for lang in LANGS:
        dest = os.path.join(DEST, f"{lang}.traineddata")
        if os.path.exists(dest):
            print(f"{lang}: already present, skipping")
            continue
        url = f"{BASE}/{lang}.traineddata"
        print(f"downloading {lang} ...")
        urllib.request.urlretrieve(url, dest)
        print(f"  saved {os.path.getsize(dest)} bytes -> {dest}")
    print("done. TESSDATA is ready at", DEST)


if __name__ == "__main__":
    main()
