import sys, os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools', 'ocr'))

from ocr import extract_pdf


def test_extract_pdf_returns_text():
    result = extract_pdf("tests/ocr/fixtures/sample.pdf")
    assert "Hello OCR World" in result


def test_extract_pdf_missing_file():
    with pytest.raises(FileNotFoundError):
        extract_pdf("nonexistent.pdf")
