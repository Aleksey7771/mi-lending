import os
from datetime import datetime

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
_jinja_env = Environment(loader=FileSystemLoader(_TEMPLATES_DIR))


def generate_kp_pdf(
    client_name: str,
    items: list[dict],
    settings: dict,
) -> bytes:
    # Strip price_vip from items — never goes into the PDF
    clean_items = [{k: v for k, v in item.items() if k != "price_vip"}
                   for item in items]

    template = _jinja_env.get_template("kp.html")
    html_str = template.render(
        date=datetime.now().strftime("%d.%m.%Y"),
        client_name=client_name,
        items=clean_items,
        company_name=settings.get("company_name", ""),
        manager_contact=settings.get("manager_contact", ""),
        delivery_zones=settings.get("delivery_zones", ""),
    )
    return HTML(string=html_str, base_url=_TEMPLATES_DIR).write_pdf()
