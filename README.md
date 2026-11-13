# Arabic PDF Reader (macOS)

A lightweight Acrobat-style PDF reader with built-in OCR, made for Arabic (and English) text.

## Features
- Open and read any PDF — page navigation, zoom, scroll
- **Select text with the mouse** — works on both:
  - normal PDFs (native text layer), and
  - **scanned PDFs** (OCR runs automatically on your selection)
- Arabic presentation forms are normalized so copied text pastes correctly
- OCR results are cached per page, so re-selecting on the same page is instant
- OCR language configurable (default `ara`; use `ara+eng` for mixed text)
- Copy selection with ⌘C; OCR a whole page with the "OCR الصفحة" button
- Shortcuts: ⌘O open, ←/→ or PageUp/PageDown navigate, scroll wheel to scroll

## Setup on macOS (easy way)

Run the launcher — it handles everything (virtual environment, tkinter,
dependencies, OCR data) and remembers it after the first run:

```sh
chmod +x run.sh
./run.sh                # or: ./run.sh كتابك.pdf
```

## Setup on macOS (manual way)

Homebrew's Python needs two extra steps: tkinter comes as a separate
package (`python-tk`), and pip refuses system-wide installs (PEP 668),
so use a virtual environment:

1. Install tkinter for your Homebrew Python:
   ```sh
   brew install python-tk
   ```
   (If you use the python.org installer instead, tkinter is already included
   and you can skip this step.)

2. Create a virtual environment and install dependencies:
   ```sh
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. Download the Arabic OCR data (one time, ~17 MB):
   ```sh
   python download_tessdata.py
   ```
   (Alternative: `brew install tesseract tesseract-lang` and the reader will
   find the Homebrew tessdata automatically.)

4. Run:
   ```sh
   python pdf_reader.py [file.pdf]
   ```

> Note: activate the environment (`source venv/bin/activate`) in each new
> terminal session, or just use `./run.sh` which does it for you.

## How text selection works
Drag the mouse over any text. If the page has a real text layer, the text is
extracted directly. If the page is a scan (no text layer), the whole page is
OCR'd once with Tesseract (Arabic, 300 dpi, high-quality `tessdata_best`
models) and your selection is taken from it — rebuilt line by line,
right-to-left. The result appears in the bottom panel; ⌘C copies it to the
clipboard.

## Tested with
Scanned Arabic books (image-only PDFs, no text layer) — e.g. a 465-page
scanned Arabic philosophy book: selections OCR in ~5 s per page (cached
afterwards) and produce readable Arabic text.

## Troubleshooting
- **"لا توجد بيانات OCR"** → run `python3 download_tessdata.py` once, or
  `brew install tesseract tesseract-lang`.
- **OCR quality is poor** → the scan itself may be low quality; try selecting
  smaller regions, or switch the OCR langs field to `ara` (avoids Latin noise).
- **Copied Arabic looks reversed/unshaped** → paste into Notes/Word/Google
  Docs, which handle right-to-left shaping; the clipboard holds logical
  Unicode.
