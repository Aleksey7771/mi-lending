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


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}


def route_file(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return extract_pdf(path)
    elif ext in IMAGE_EXTENSIONS:
        return extract_image(path)
    else:
        raise ValueError(f"Unsupported format: {ext!r}. Supported: .pdf, {', '.join(sorted(IMAGE_EXTENSIONS))}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python ocr.py <file.pdf|file.png|...>", file=sys.stderr)
        sys.exit(1)
    path = sys.argv[1]
    text = route_file(path)
    print(text)
    try:
        import pyperclip
        pyperclip.copy(text)
        print("\n✓ Copied to clipboard", file=sys.stderr)
    except Exception:
        pass


if __name__ == "__main__":
    main()
