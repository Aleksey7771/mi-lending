import sys, os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools', 'ocr'))

from ocr import extract_pdf, extract_image, route_file


def test_extract_pdf_returns_text():
    result = extract_pdf("tests/ocr/fixtures/sample.pdf")
    assert "Hello OCR World" in result


def test_extract_pdf_missing_file():
    with pytest.raises(FileNotFoundError):
        extract_pdf("nonexistent.pdf")


TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
tesseract_available = os.path.exists(TESSERACT_PATH)


@pytest.mark.skipif(not tesseract_available, reason="Tesseract not installed")
def test_extract_image_returns_text():
    result = extract_image("tests/ocr/fixtures/sample.png")
    assert "Hello" in result


def test_extract_image_missing_file():
    with pytest.raises(FileNotFoundError):
        extract_image("nonexistent.png")


def test_route_file_pdf():
    result = route_file("tests/ocr/fixtures/sample.pdf")
    assert "Hello OCR World" in result


def test_route_file_unsupported():
    with pytest.raises(ValueError, match="Unsupported"):
        route_file("file.docx")
