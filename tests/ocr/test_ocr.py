import sys, os, shutil
import pytest
from unittest.mock import patch, MagicMock

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools', 'ocr'))

from ocr import extract_pdf, extract_image, route_file


# --- extract_pdf ---

def test_extract_pdf_returns_text():
    result = extract_pdf(os.path.join(FIXTURES, "sample.pdf"))
    assert "Hello OCR World" in result


def test_extract_pdf_missing_file():
    with pytest.raises(FileNotFoundError):
        extract_pdf("nonexistent.pdf")


def test_extract_pdf_empty_warns(capsys):
    """A PDF with no text layer prints a warning and returns empty string."""
    import pymupdf
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        tmp = f.name
    try:
        doc = pymupdf.open()
        doc.new_page()  # blank page, no text
        doc.save(tmp)
        result = extract_pdf(tmp)
        captured = capsys.readouterr()
        assert result == ""
        assert "no text layer" in captured.err
    finally:
        os.unlink(tmp)


# --- extract_image ---

tesseract_available = bool(shutil.which("tesseract") or os.path.exists(r"C:\Program Files\Tesseract-OCR\tesseract.exe"))


@pytest.mark.skipif(not tesseract_available, reason="Tesseract not installed")
def test_extract_image_returns_text():
    result = extract_image(os.path.join(FIXTURES, "sample.png"))
    assert "Hello" in result


def test_extract_image_missing_file():
    with pytest.raises(FileNotFoundError):
        extract_image("nonexistent.png")


def test_extract_image_raises_not_exits(tmp_path, monkeypatch):
    """extract_image should raise TesseractNotFoundError, not call sys.exit."""
    import pytesseract
    from PIL import Image as PILImage
    img = PILImage.new("RGB", (100, 50), color="white")
    img_path = str(tmp_path / "blank.png")
    img.save(img_path)
    monkeypatch.setattr(pytesseract.pytesseract, "tesseract_cmd", "/nonexistent/tesseract")
    with pytest.raises(pytesseract.TesseractNotFoundError):
        extract_image(img_path)


# --- route_file ---

def test_route_file_pdf():
    result = route_file(os.path.join(FIXTURES, "sample.pdf"))
    assert "Hello OCR World" in result


def test_route_file_unsupported():
    with pytest.raises(ValueError, match="Unsupported"):
        route_file("file.docx")


# --- main() ---

def test_main_unsupported_format_exits_cleanly(capsys):
    """main() should print an error and exit 1 on ValueError, no traceback."""
    from ocr import main
    with patch("sys.argv", ["ocr.py", "file.docx"]):
        with pytest.raises(SystemExit) as exc_info:
            main()
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "Unsupported" in captured.err
    assert "Traceback" not in captured.err


def test_main_missing_file_exits_cleanly(capsys):
    """main() should print an error and exit 1 on FileNotFoundError, no traceback."""
    from ocr import main
    with patch("sys.argv", ["ocr.py", "nonexistent.pdf"]):
        with pytest.raises(SystemExit) as exc_info:
            main()
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "not found" in captured.err.lower()


def test_main_spaces_in_argv(capsys):
    """main() with multiple argv args should print a clear 'use quotes' message."""
    from ocr import main
    with patch("sys.argv", ["ocr.py", "my", "scan.pdf"]):
        with pytest.raises(SystemExit) as exc_info:
            main()
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "quote" in captured.err.lower()


def test_main_empty_text_skips_clipboard(capsys):
    """When extracted text is empty, clipboard copy should be skipped."""
    from ocr import main
    with patch("sys.argv", ["ocr.py", os.path.join(FIXTURES, "sample.pdf")]):
        with patch("ocr.route_file", return_value=""), \
             patch("pyperclip.copy") as mock_copy:
            main()
    mock_copy.assert_not_called()
