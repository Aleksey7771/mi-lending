from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal


@dataclass
class PriceRecord:
    raw_name: str
    price_rub: Decimal
    source: str
    source_url: str = ""
    supplier_name: str | None = None
    unit: str = "кг"
    recorded_at: datetime = field(default_factory=datetime.utcnow)
    product_id: int | None = None
    supplier_id: int | None = None


class BaseParser(ABC):
    source: str = ""
    url: str = ""

    @abstractmethod
    async def fetch_raw(self) -> str:
        """Fetch raw HTML or data from the source."""

    @abstractmethod
    def parse_raw(self, raw: str) -> list[PriceRecord]:
        """Parse raw data into PriceRecord list."""

    async def parse(self) -> list[PriceRecord]:
        raw = await self.fetch_raw()
        return self.parse_raw(raw)
