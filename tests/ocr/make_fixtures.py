"""Run once to generate test fixtures."""
import os, sys

fixtures = os.path.join(os.path.dirname(__file__), "fixtures")
os.makedirs(fixtures, exist_ok=True)

# PDF fixture
import fitz
doc = fitz.open()
page = doc.new_page()
page.insert_text((50, 50), "Hello OCR World")
doc.save(os.path.join(fixtures, "sample.pdf"))
print("Created sample.pdf")

# Image fixture
from PIL import Image, ImageDraw
img = Image.new("RGB", (300, 100), color="white")
draw = ImageDraw.Draw(img)
draw.text((10, 30), "Hello OCR World", fill="black")
img.save(os.path.join(fixtures, "sample.png"))
print("Created sample.png")
