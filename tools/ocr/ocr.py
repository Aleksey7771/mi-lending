import os
import sys
import shutil
import pymupdf
import pytesseract
from PIL import Image


def _find_tesseract() -> str:
    if "TESSERACT_CMD" in os.environ:
        return os.environ["TESSERACT_CMD"]
    found = shutil.which("tesseract")
    if found:
        return found
    default = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    return default


def extract_pdf(path: str) -> str:
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")
    with pymupdf.open(path) as doc:
        pages = [page.get_text() for page in doc]
    text = "\n\n".join(pages).strip()
    if not text:
        print("[WARNING] PDF has no text layer. Try scanning the PDF as an image.", file=sys.stderr)
    return text


def extract_image(path: str) -> str:
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")
    pytesseract.pytesseract.tesseract_cmd = _find_tesseract()
    img = Image.open(path)
    try:
        text = pytesseract.image_to_string(img, lang="rus+eng").strip()
    except pytesseract.TesseractError as e:
        if "Failed loading language" in str(e):
            raise pytesseract.TesseractError(
                1,
                "Russian language pack missing. Rerun the Tesseract installer and tick 'Russian'. See tools/ocr/INSTALL.md"
            ) from e
        raise
    if not text:
        print("[WARNING] No text detected in image.", file=sys.stderr)
    return text


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}


def route_file(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return extract_pdf(path)
    elif ext in IMAGE_EXTENSIONS:
        return extract_image(path)
    else:
        raise ValueError(
            f"Unsupported format: {ext!r}. Supported: .pdf, {', '.join(sorted(IMAGE_EXTENSIONS))}"
        )


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

    if len(sys.argv) < 2:
        print("Usage: python ocr.py <file.pdf|file.png|...>", file=sys.stderr)
        sys.exit(1)

    if len(sys.argv) > 2:
        print("[ERROR] Path contains spaces — wrap it in quotes: python ocr.py \"my scan.pdf\"", file=sys.stderr)
        sys.exit(1)

    path = sys.argv[1]
    try:
        text = route_file(path)
    except FileNotFoundError as e:
        print(f"[ERROR] File not found: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)
    except pytesseract.TesseractNotFoundError:
        print("[ERROR] Tesseract not installed. See tools/ocr/INSTALL.md", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)

    if text:
        try:
            import pyperclip
            pyperclip.copy(text)
            print("✓ Copied to clipboard", file=sys.stderr)
        except Exception as e:
            print(f"[WARNING] Clipboard copy failed: {e}", file=sys.stderr)

    print(text)


if __name__ == "__main__":
    main()
