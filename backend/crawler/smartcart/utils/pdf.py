"""PDF text extraction and product parsing for grocery prospekts using Docling."""
import logging
import re
from pathlib import Path

from crawler.smartcart.models.product import ScrapedProduct

logger = logging.getLogger(__name__)

# Price patterns: "2.95", "CHF 2.95", "2,95", "CHF\n2.95"
PRICE_RE = re.compile(r"(?:CHF\s*)?(\d{1,3}[.,]\d{2})")
# Discount patterns: "-20%", "20% Rabatt"
DISCOUNT_RE = re.compile(r"[-–]?\s*(\d{1,2})\s*%")

PRICE_MIN = 0.10
PRICE_MAX = 500.0


def extract_products_from_pdf(
    pdf_path: str | Path,
    retailer: str,
    valid_from: str | None = None,
    valid_to: str | None = None,
) -> list[ScrapedProduct]:
    """Extract products from a grocery prospekt PDF using Docling."""
    try:
        from docling.document_converter import DocumentConverter
    except ImportError:
        logger.warning("Docling not installed, falling back to pdfplumber")
        return _extract_with_pdfplumber(pdf_path, retailer, valid_from, valid_to)

    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        logger.warning(f"PDF not found: {pdf_path}")
        return []

    products: list[ScrapedProduct] = []
    seen_names: set[str] = set()

    try:
        converter = DocumentConverter()
        result = converter.convert(str(pdf_path))
        md = result.document.export_to_markdown()

        for line in md.split("\n"):
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("|") or len(line) < 3:
                continue

            price_match = PRICE_RE.search(line)
            if not price_match:
                continue

            price = float(price_match.group(1).replace(",", "."))
            if not (PRICE_MIN <= price <= PRICE_MAX):
                continue

            name = line[:price_match.start()].strip()
            name = re.sub(r"\s+", " ", name)
            name = re.sub(r"[*_#|>]+", "", name).strip()

            if not name or len(name) < 3:
                continue

            name_lower = name.lower()
            if name_lower in seen_names:
                continue
            seen_names.add(name_lower)

            discount = None
            discount_match = DISCOUNT_RE.search(line)
            if discount_match:
                discount = float(discount_match.group(1))

            from datetime import date as dt_date
            products.append(ScrapedProduct(
                retailer=retailer,
                name=name,
                price=price,
                discount_pct=discount,
                valid_from=dt_date.fromisoformat(valid_from) if valid_from else None,
                valid_to=dt_date.fromisoformat(valid_to) if valid_to else None,
            ))

    except Exception as e:
        logger.error(f"Docling failed for {pdf_path}: {e}")
        # Fallback to pdfplumber
        return _extract_with_pdfplumber(pdf_path, retailer, valid_from, valid_to)

    logger.info(f"Docling extracted {len(products)} products from {pdf_path.name}")
    return products


def _extract_with_pdfplumber(
    pdf_path: str | Path,
    retailer: str,
    valid_from: str | None = None,
    valid_to: str | None = None,
) -> list[ScrapedProduct]:
    """Fallback: Extract products using pdfplumber if Docling is unavailable."""
    try:
        import pdfplumber
    except ImportError:
        logger.warning("Neither Docling nor pdfplumber installed")
        return []

    pdf_path = Path(pdf_path)
    products: list[ScrapedProduct] = []
    seen_names: set[str] = set()

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if not text:
                    continue
                for line in text.split("\n"):
                    line = line.strip()
                    price_match = PRICE_RE.search(line)
                    if not price_match:
                        continue

                    price = float(price_match.group(1).replace(",", "."))
                    if not (PRICE_MIN <= price <= PRICE_MAX):
                        continue

                    name = re.sub(r"\s+", " ", line[:price_match.start()].strip())
                    if not name or len(name) < 3 or name.lower() in seen_names:
                        continue
                    seen_names.add(name.lower())

                    from datetime import date as dt_date
                    products.append(ScrapedProduct(
                        retailer=retailer,
                        name=name,
                        price=price,
                        valid_from=dt_date.fromisoformat(valid_from) if valid_from else None,
                        valid_to=dt_date.fromisoformat(valid_to) if valid_to else None,
                    ))
    except Exception as e:
        logger.error(f"pdfplumber failed for {pdf_path}: {e}")

    logger.info(f"pdfplumber extracted {len(products)} products from {pdf_path.name}")
    return products
