import os
import sys
import pymupdf


def extract_pdf(path: str) -> str:
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")
    doc = pymupdf.open(path)
    pages = [page.get_text() for page in doc]
    text = "\n\n".join(pages).strip()
    if not text:
        print("[WARNING] PDF has no text layer. Try scanning the PDF as an image.", file=sys.stderr)
    return text
