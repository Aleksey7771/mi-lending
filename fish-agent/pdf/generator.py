"""
PDF generator: WeasyPrint + Jinja2 templates.
Generates preis.pdf and kp.pdf files.
"""
import hashlib
import logging
import os
from datetime import datetime
from decimal import Decimal

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

logger = logging.getLogger(__name__)

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "generated_pdfs")

_jinja_env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))


def _logo_path() -> tuple[bool, str]:
    for name in ("logo.png", "logo.jpg", "logo.jpeg"):
        path = os.path.join(ASSETS_DIR, name)
        if os.path.exists(path):
            return True, f"file://{os.path.abspath(path)}"
    return False, ""


def render_preis(
    products_by_category: dict[str, list[dict]],
    company_name: str,
    phone: str,
    telegram: str,
    conditions: str,
    email: str = "",
) -> bytes:
    """Render full price list PDF. Returns PDF bytes."""
    logo_exists, logo_path = _logo_path()
    template = _jinja_env.get_template("preis.html")
    html_str = template.render(
        date=datetime.now().strftime("%d.%m.%Y"),
        company_name=company_name,
        products_by_category=products_by_category,
        unit="кг",
        phone=phone,
        telegram=telegram,
        email=email,
        conditions=conditions,
        logo_exists=logo_exists,
        logo_path=logo_path,
    )
    return HTML(string=html_str, base_url=ASSETS_DIR).write_pdf()


def render_kp(
    client_name: str,
    client_city: str,
    items: list[dict],
    discount_pct: float,
    min_order: float | None,
    company_name: str,
    phone: str,
    telegram: str,
    conditions: str,
    email: str = "",
) -> bytes:
    """Render commercial proposal PDF. Returns PDF bytes."""
    logo_exists, logo_path = _logo_path()
    template = _jinja_env.get_template("kp.html")
    html_str = template.render(
        date=datetime.now().strftime("%d.%m.%Y"),
        company_name=company_name,
        client_name=client_name,
        client_city=client_city,
        items=items,
        discount_pct=discount_pct,
        min_order=min_order,
        phone=phone,
        telegram=telegram,
        email=email,
        conditions=conditions,
        logo_exists=logo_exists,
        logo_path=logo_path,
    )
    return HTML(string=html_str, base_url=ASSETS_DIR).write_pdf()


def save_pdf(content: bytes, filename: str) -> str:
    """Save PDF bytes to generated_pdfs/ and return absolute path."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "wb") as f:
        f.write(content)
    return path


def pdf_checksum(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
