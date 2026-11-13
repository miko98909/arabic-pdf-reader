#!/usr/bin/env python3
"""Arabic-friendly PDF reader with integrated OCR and text selection.

- Select text with the mouse on any PDF (native text layer or scanned page).
- Scanned pages are OCR'd on the fly with Tesseract (Arabic + English).
- Selected text is copied to the clipboard and shown in a panel.
"""

import os
import sys
import unicodedata
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import pymupdf

try:
    import pytesseract
    from PIL import Image
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False

OCR_LANG_DEFAULT = "ara"
OCR_DPI = 300  # resolution used when OCR-ing a scanned page


def find_tessdata():
    """Locate a tessdata directory (macOS Homebrew paths included)."""
    candidates = [
        os.environ.get("TESSDATA_PREFIX"),
        "/opt/homebrew/share/tessdata",
        "/usr/local/share/tessdata",
        os.path.expanduser("~/tessdata"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "tessdata"),
    ]
    for c in candidates:
        if c and os.path.isdir(c) and any(f.endswith(".traineddata") for f in os.listdir(c)):
            os.environ["TESSDATA_PREFIX"] = c
            return c
    return None


def normalize_text(text):
    """Convert Arabic presentation forms to logical Unicode letters."""
    return unicodedata.normalize("NFKC", text)


def words_to_text(words, clip):
    """Filter OCR words by selection and rebuild lines in RTL order."""
    sel = [w for w in words if pymupdf.Rect(w[:4]).intersects(clip)]
    if not sel:
        return ""
    sel.sort(key=lambda w: (w[1], -w[0]))
    lines, cur, cur_bottom = [], [], -1.0
    for w in sel:
        if cur and w[1] > cur_bottom:  # start a new line
            lines.append(cur)
            cur = []
        cur.append(w)
        cur_bottom = max(cur_bottom, (w[1] + w[3]) / 2)
    if cur:
        lines.append(cur)
    return "\n".join(" ".join(w[4] for w in line) for line in lines)


class PDFReader(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("قارئ PDF — Arabic PDF Reader")
        self.geometry("1100x800")

        self.doc = None
        self.path = None
        self.page_num = 0
        self.zoom = 1.5
        self.photo = None
        self.ocr_lang = tk.StringVar(value=OCR_LANG_DEFAULT)

        self.sel_start = None
        self.sel_rect = None
        self._ocr_textpage = None  # cached OCR textpage for current page
        self._ocr_page_num = None

        self._build_ui()
        self._bind_keys()

        if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
            self.open_path(sys.argv[1])

    # ---------- UI ----------

    def _build_ui(self):
        toolbar = ttk.Frame(self)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=6, pady=4)

        ttk.Button(toolbar, text="فتح Open", command=self.open_file).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="◀ السابق", command=lambda: self.goto_page(self.page_num - 1)).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="التالي ▶", command=lambda: self.goto_page(self.page_num + 1)).pack(side=tk.LEFT, padx=2)

        self.page_var = tk.StringVar(value="—")
        page_entry = ttk.Entry(toolbar, width=5, textvariable=self.page_var, justify="center")
        page_entry.pack(side=tk.LEFT, padx=2)
        page_entry.bind("<Return>", lambda e: self.goto_page(int(self.page_var.get()) - 1))
        self.page_label = ttk.Label(toolbar, text="/ 0")
        self.page_label.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(toolbar, text="−", width=3, command=lambda: self.set_zoom(self.zoom / 1.25)).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="+", width=3, command=lambda: self.set_zoom(self.zoom * 1.25)).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="OCR الصفحة", command=self.ocr_page).pack(side=tk.LEFT, padx=8)

        ttk.Label(toolbar, text="OCR langs:").pack(side=tk.LEFT, padx=(10, 2))
        lang_entry = ttk.Entry(toolbar, width=8, textvariable=self.ocr_lang, justify="center")
        lang_entry.pack(side=tk.LEFT)

        # canvas + scrollbars
        container = ttk.Frame(self)
        container.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(container, bg="#404040", highlightthickness=0)
        vbar = ttk.Scrollbar(container, orient=tk.VERTICAL, command=self.canvas.yview)
        hbar = ttk.Scrollbar(container, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=vbar.set, xscrollcommand=hbar.set)
        vbar.pack(side=tk.RIGHT, fill=tk.Y)
        hbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # selection text panel
        panel = ttk.Frame(self)
        panel.pack(side=tk.BOTTOM, fill=tk.X, padx=6, pady=4)
        ttk.Button(panel, text="نسخ Copy (⌘C)", command=self.copy_selection).pack(side=tk.LEFT, padx=2)
        self.status = ttk.Label(panel, text="افتح ملف PDF للبدء — Open a PDF to start")
        self.status.pack(side=tk.LEFT, padx=10)
        self.text_box = tk.Text(panel, height=4, wrap=tk.WORD, font=("Helvetica", 13))
        self.text_box.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)

    def _bind_keys(self):
        self.bind("<Command-o>", lambda e: self.open_file())
        self.bind("<Command-O>", lambda e: self.open_file())
        self.bind("<Command-c>", lambda e: self.copy_selection())
        self.bind("<Command-C>", lambda e: self.copy_selection())
        self.bind("<Left>", lambda e: self.goto_page(self.page_num - 1))
        self.bind("<Right>", lambda e: self.goto_page(self.page_num + 1))
        self.bind("<Prior>", lambda e: self.goto_page(self.page_num - 1))
        self.bind("<Next>", lambda e: self.goto_page(self.page_num + 1))

        self.canvas.bind("<Button-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        # macOS trackpad / wheel scrolling
        self.canvas.bind("<MouseWheel>", self.on_wheel)
        self.canvas.bind("<Shift-MouseWheel>", lambda e: self.canvas.xview_scroll(-1 * int(e.delta), "units"))

    # ---------- document ----------

    def open_file(self):
        path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf"), ("All files", "*")])
        if path:
            self.open_path(path)

    def open_path(self, path):
        try:
            doc = pymupdf.open(path)
        except Exception as exc:
            messagebox.showerror("خطأ", f"Cannot open file:\n{exc}")
            return
        if self.doc:
            self.doc.close()
        self.doc = doc
        self.path = path
        self.title(f"{os.path.basename(path)} — Arabic PDF Reader")
        self.page_label.config(text=f"/ {doc.page_count}")
        self.goto_page(0)

    def goto_page(self, num):
        if not self.doc:
            return
        num = max(0, min(self.doc.page_count - 1, num))
        self.page_num = num
        self._ocr_textpage = None
        self.page_var.set(str(num + 1))
        self.render()

    def set_zoom(self, zoom):
        self.zoom = max(0.3, min(6.0, zoom))
        self.render()

    def render(self):
        if not self.doc:
            return
        page = self.doc[self.page_num]
        pix = page.get_pixmap(matrix=pymupdf.Matrix(self.zoom, self.zoom), alpha=False)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        self.photo = img  # keep reference; ImageTk would be needed in real run
        self._image = img
        self._draw_page(img, pix.width, pix.height)

    def _draw_page(self, img, w, h):
        try:
            from PIL import ImageTk
            self.tk_img = ImageTk.PhotoImage(img)
        except Exception:
            return
        self.canvas.delete("all")
        self.canvas.configure(scrollregion=(0, 0, w, h))
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_img)

    # ---------- selection ----------

    def on_press(self, event):
        self.sel_start = (self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))

    def on_drag(self, event):
        if not self.sel_start:
            return
        x0, y0 = self.sel_start
        x1, y1 = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        if self.sel_rect:
            self.canvas.delete(self.sel_rect)
        self.sel_rect = self.canvas.create_rectangle(
            x0, y0, x1, y1, outline="#2f9bff", width=2, dash=(4, 3))

    def on_release(self, event):
        if not self.sel_start or not self.doc:
            return
        x0, y0 = self.sel_start
        x1, y1 = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        self.sel_start = None
        rect = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
        if rect[2] - rect[0] < 4 or rect[3] - rect[1] < 4:
            return
        self.extract_selection(rect)

    def extract_selection(self, rect):
        page = self.doc[self.page_num]
        clip = pymupdf.Rect(*[c / self.zoom for c in rect])

        text = page.get_text("text", clip=clip).strip()
        source = "text layer"
        if not text:
            text = self.ocr_clip(page, clip)
            source = "OCR"

        if not text:
            self.status.config(text="لا يوجد نص في التحديد — no text found in selection")
            return

        text = normalize_text(text).strip()
        self.text_box.delete("1.0", tk.END)
        self.text_box.insert("1.0", text)
        self.status.config(text=f"✓ {source} — {len(text)} chars (⌘C to copy)")

    def ocr_clip(self, page, clip):
        """OCR a scanned page (full-page pass, cached) and return the words
        inside the selection, rebuilt line by line in RTL order."""
        tessdata = find_tessdata()
        if not tessdata:
            messagebox.showwarning(
                "OCR",
                "هذه الصفحة ممسوحة ولا توجد بيانات OCR.\n\n"
                "Run once:\n"
                "  python3 download_tessdata.py\n\n"
                "or install via Homebrew:\n"
                "  brew install tesseract tesseract-lang")
            return ""
        try:
            if self._ocr_page_num != self.page_num or self._ocr_textpage is None:
                self.status.config(text="… جارٍ إجراء OCR للصفحة — OCR running, may take a few seconds")
                self.update_idletasks()
                self._ocr_textpage = page.get_textpage_ocr(
                    full=True, language=self.ocr_lang.get(), dpi=OCR_DPI)
                self._ocr_page_num = self.page_num
            words = page.get_text("words", textpage=self._ocr_textpage)
            return words_to_text(words, clip)
        except Exception as exc:
            messagebox.showerror("OCR", f"OCR failed:\n{exc}")
            return ""

    def ocr_page(self):
        if not self.doc:
            return
        page = self.doc[self.page_num]
        text = normalize_text(page.get_text().strip())
        source = "text layer"
        if not text:
            self.status.config(text="… جارٍ إجراء OCR للصفحة — running OCR")
            self.update_idletasks()
            text = normalize_text(self.ocr_clip(page, page.rect)).strip()
            source = "OCR"
        self.text_box.delete("1.0", tk.END)
        self.text_box.insert("1.0", text)
        self.status.config(text=f"✓ {source} — {len(text)} chars (⌘C to copy)")

    def copy_selection(self):
        text = self.text_box.get("1.0", tk.END).strip()
        if not text:
            self.status.config(text="لا يوجد نص محدد — nothing to copy")
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self.status.config(text="✓ تم النسخ — copied to clipboard")

    def on_wheel(self, event):
        if event.delta:
            self.canvas.yview_scroll(-1 * int(event.delta), "units")


if __name__ == "__main__":
    app = PDFReader()
    app.mainloop()
