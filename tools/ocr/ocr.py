import os
import sys
import pymupdf
import pytesseract
from PIL import Image

TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def extract_pdf(path: str) -> str:
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")
    doc = pymupdf.open(path)
    pages = [page.get_text() for page in doc]
    text = "\n\n".join(pages).strip()
    if not text:
        print("[WARNING] PDF has no text layer. Try scanning the PDF as an image.", file=sys.stderr)
    return text


def extract_image(path: str) -> str:
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")
    try:
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
        img = Image.open(path)
        text = pytesseract.image_to_string(img, lang="rus+eng").strip()
    except pytesseract.TesseractNotFoundError:
        print("[ERROR] Tesseract not installed. See tools/ocr/INSTALL.md", file=sys.stderr)
        sys.exit(1)
    if not text:
        print("[WARNING] No text detected in image.", file=sys.stderr)
    return text
