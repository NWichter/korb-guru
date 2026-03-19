"""
Product extraction from grocery prospekt PDFs.

Strategy: pdfplumber first (fast text extraction), Docling OCR fallback (slow).
Grocery flyer PDFs from Scene7/Lidl typically have embedded text layers,
so pdfplumber is usually sufficient and runs in seconds vs minutes for Docling.
"""
import asyncio
import logging
import os
import re
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

PRICE_RE = re.compile(r"(?:CHF\s*)?(\d{1,3}[.,]\d{2})")
DISCOUNT_RE = re.compile(r"[-–]?\s*(\d{1,2})\s*%")
PRICE_MIN = 0.10
PRICE_MAX = 500.0


# Labels/metadata that appear on flyer pages but are not product names
_JUNK_PATTERNS = re.compile(
    r"^("
    r"\d{1,3}\s*%"          # "24%", "50%"
    r"|ab\s"                # "ab 19.3."
    r"|bis\s"               # "bis 25.3."
    r"|gültig\s"            # "gültig ab..."
    r"|herkunft"            # "Herkunft: ..."
    r"|gewicht"             # "Gewicht: ..."
    r"|inhalt"              # "Inhalt: ..."
    r"|je\s"                # "je Stück"
    r"|pro\s"               # "pro 100g"
    r"|\d+\s*(?:g|kg|ml|l|cl|dl|stk|st)\b"  # "100 g", "500 ml"
    r"|\d+\s*(?:g|kg|ml|l)\s*="  # "100 g ="
    r"|seite\s*\d"          # "Seite 1"
    r"|www\."               # URLs
    r"|(?:lidl|aldi|coop|migros|denner)\s*$"  # retailer name alone
    r"|montag|dienstag|mittwoch|donnerstag|freitag|samstag|sonntag"
    r"|aktion|angebot|rabatt|sparen|gratis|neu\s*$"
    # Non-grocery content (travel, fashion, household, etc.)
    r"|(?:tage|nächte),?\s*(?:dz|ez|innenkabine)"  # travel offers
    r"|\d+\s*(?:tage|nächte)"  # "14 Tage", "2 Nächte"
    r"|buchbar|reise|flug|hotel|kreuzfahrt|wellness"
    r"|termine:|voucher|gutschein"
    r"|(?:damen|herren|kinder)\s*$"  # clothing category headers
    r"|farbe|grösse|sortiment"  # product attribute labels
    r"|preishighlight|highlight|trendige?"
    r"|auch\s+in\b"          # "auch in Schwarz"
    r"|schwarz|weiss|blau|rot|grün\s*$"  # colour-only names
    r"|(?:mo|di|mi|do|fr|sa|so)\s*[-–]\s*(?:mo|di|mi|do|fr|sa|so)"
    r"|leistung|eigene\s+erhebung"
    r"|im\s+\d+cm"           # "Im 14cmKulturtopf"
    r"|kulturtopf|velosattel|velozubehör"
    r"|z\.\s*B\.\s*$"        # "z. B." alone
    r"|.*z\.\s*B\.\s*$"      # anything ending with "z. B."
    r"|preiserhebung|preisvergleich"
    r"|oder\s+gültig"        # "ODER Gültig vom..."
    r"|legend\s|blue\s*box"  # non-food product names
    r"|pro\s+packung"        # "pro Packung" metadata
    r"|.*frühstück.*z\.\s*B" # travel breakfast offers
    r")",
    re.IGNORECASE,
)

# Non-grocery words — if a name contains too many of these, skip it
_NON_GROCERY_WORDS = frozenset({
    "reise", "hotel", "flug", "kreuzfahrt", "nächte", "tage",
    "kabine", "innenkabine", "dz", "ez", "economy", "class",
    "buchbar", "voucher", "gutschein", "termine",
    "damen", "herren", "kinder", "grösse",
    "velosattel", "velozubehör", "kulturtopf",
    "licht", "lampe", "led", "leuchte",
    "packung", "stück", "erhebung",
})

# Single uppercase words that are category headers, not products
_CATEGORY_HEADERS = frozenset({
    "fleisch", "fisch", "gemüse", "obst", "früchte", "backwaren",
    "getränke", "molkerei", "käse", "wurst", "brot", "snacks",
    "süsswaren", "tiefkühl", "haushalt", "pflege", "beauty",
    "damen", "herren", "kinder", "baby", "sport", "garten",
    "qualität", "licht", "schweizer", "leistung", "farbe",
    "sortiment", "aktion", "angebot", "highlight", "woche",
    "favorit", "klassiker", "neuheit", "tipp", "top", "hit",
})


def _fix_doubled_chars(text: str) -> str:
    """Fix pdfplumber doubled-character artefact from overlapping text layers.

    Example: "FFrrhhlliinnggssggeeffüühhllee" → "Frühlingsgefühle"
    Detects if most consecutive character pairs are duplicates and deduplicates.
    """
    if len(text) < 6:
        return text

    # Check if this looks like doubled text (>60% of char pairs are duplicates)
    pairs_doubled = sum(
        1 for i in range(0, len(text) - 1, 2)
        if text[i] == text[i + 1]
    )
    total_pairs = len(text) // 2
    if total_pairs > 0 and pairs_doubled / total_pairs > 0.6:
        # Take every other character
        return text[::2]
    return text


def _clean_concatenated_text(text: str) -> str:
    """Fix concatenated words from PDF extraction missing spaces.

    Example: "2ScheibenToaster,7Bräunungsstufen," → likely junk, skip
    Example: "AmAbendAbflugmitEmiratesnachDubai." → travel junk
    """
    # Count transitions from lowercase to uppercase (camelCase = missing spaces)
    transitions = sum(
        1 for i in range(1, len(text))
        if text[i - 1].islower() and text[i].isupper()
    )
    # Also count digit-to-letter transitions (e.g. "2Scheiben")
    digit_transitions = sum(
        1 for i in range(1, len(text))
        if text[i - 1].isdigit() and text[i].isalpha()
    )
    total_transitions = transitions + digit_transitions
    # If many transitions, it's concatenated garbage
    if total_transitions >= 3:
        return ""  # Signal to skip
    return text


def _parse_products_from_text(text: str, retailer: str) -> list[dict]:
    """Parse products with prices from extracted text (pdfplumber or Docling)."""
    products = []
    seen: set[str] = set()

    for line in text.split("\n"):
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("|") or len(line) < 5:
            continue

        # Fix doubled characters from overlapping PDF text layers
        line = _fix_doubled_chars(line)

        price_match = PRICE_RE.search(line)
        if not price_match:
            continue

        price = float(price_match.group(1).replace(",", "."))
        if not (PRICE_MIN <= price <= PRICE_MAX):
            continue

        name = line[:price_match.start()].strip()
        name = re.sub(r"\s+", " ", name)
        name = re.sub(r"[*_#|>-]+", "", name).strip()

        # Fix concatenated words (missing spaces in PDF)
        cleaned = _clean_concatenated_text(name)
        if not cleaned:
            continue
        name = cleaned

        # Filter out junk names
        if not name or len(name) < 3 or name.lower() in seen:
            continue
        if _JUNK_PATTERNS.match(name):
            continue
        # Skip names that are mostly numbers/punctuation
        alpha_chars = sum(1 for c in name if c.isalpha())
        if alpha_chars < 3:
            continue
        # Skip non-grocery items (travel, fashion, etc.)
        name_words = set(name.lower().split())
        if len(name_words & _NON_GROCERY_WORDS) >= 2:
            continue
        # Skip single all-caps words that are category headers
        if name.isupper() and len(name.split()) <= 2:
            continue
        # Skip known category header words (case-insensitive)
        if name.lower().strip() in _CATEGORY_HEADERS:
            continue
        # Skip names with repeated words (OCR artefact: "SCHWEIZER SCHWEIZER")
        words = name.split()
        if len(words) >= 2 and len(set(w.lower() for w in words)) < len(words) * 0.5:
            continue

        seen.add(name.lower())

        discount = None
        discount_match = DISCOUNT_RE.search(line)
        if discount_match:
            discount = float(discount_match.group(1))

        products.append({
            "retailer": retailer,
            "name": name,
            "price": price,
            "discount_pct": discount,
            "category": "offer",
        })

    return products


# Article number patterns per retailer
_ALDI_ARTICLE_RE = re.compile(r"^\d{5,6}$")
_LIDL_ARTICLE_RE = re.compile(r"^\d{7}$")

# Metadata words to skip when building product names from block extraction
_BLOCK_SKIP_WORDS = frozenset({
    "herkunft", "siehe", "umverpackung", "pro", "weitere", "sorten",
    "diverse", "konkurrenz", "aldi", "lidl", "preis", "sparen", "aktion",
    "deal", "garantie", "donnerstag", "montag", "dienstag", "mittwoch",
    "freitag", "samstag", "sonntag", "gratis", "erhältlich", "rauchen",
    "auf", "seite", "solange", "vorrat", "bis", "tödlich", "basierend",
    "eigene", "erhebung", "mitbewerber", "günstiger", "unser", "tipp",
    "modell", "modelle", "farbe", "farben", "material", "highlight",
    "duopack", "multipack", "sparpack", "vorteilspack",
    "mit", "plus", "lidl", "abtropfgewicht", "einzelpreis",
    "kundenbewertungen", "sortiment", "stand",
})

# Page header patterns to filter from product names
_PAGE_HEADER_RE = re.compile(
    r"(?:WOCHENENDE|WEEKENDDEALS|OSTERDEALS|SUPERDEAL|AKTIONEN|"
    r"TIEFPREISGARANTIE|GESCHENK|IDEEN|ENTDECKE|UNSERE|ATTRAKTIVEN|"
    r"OSTER|DEALS|WWEEKK|BRANCHENCHAMPION|PREIS-HIGHLIGHT|"
    r"AB\s+(?:MO|DI|MI|DO|FR|SA|SO)|GÜLTIG|lohnt\s+sich|"
    r"Lidl\s+hat|günstigsten|Sieger|Einkauf|Warenkorb|"
    r"Siegerpodest|Bio-Preis)",
    re.IGNORECASE,
)


def _extract_blocks(file_path: str, retailer: str) -> list[dict]:
    """Extract products from flyer PDFs using article-number anchoring.

    Grocery flyers (Aldi, Lidl) use visual grid layouts where product name
    and price are on different lines. Each product block has an article
    number at the bottom. We find these anchors, then look upward in
    the same column for the product name, price and discount.
    """
    try:
        import pdfplumber
    except ImportError:
        return []

    # Retailer-specific settings
    if retailer == "aldi":
        article_re = _ALDI_ARTICLE_RE
        x_tolerance = 100
        y_range = 250
        max_name_parts = 3
    elif retailer == "lidl":
        article_re = _LIDL_ARTICLE_RE
        x_tolerance = 120   # Lidl blocks ~200px wide, 2-col on 515px page
        y_range = 200
        max_name_parts = 3
    else:
        return []

    products: list[dict] = []
    seen: set[str] = set()

    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                words = page.extract_words(
                    keep_blank_chars=True, x_tolerance=3, y_tolerance=3
                )
                if not words:
                    continue

                anchors = [
                    w for w in words if article_re.match(w["text"].strip())
                ]

                # Sort anchors by position for ceiling computation
                anchor_positions = [
                    (a["x0"], a["top"]) for a in anchors
                ]

                for anchor in anchors:
                    ax, ay = anchor["x0"], anchor["top"]

                    # Find the nearest anchor ABOVE in the same column
                    # to limit the search zone (prevents merging blocks)
                    ceiling = ay - y_range
                    for ox, oy in anchor_positions:
                        if abs(ox - ax) < x_tolerance and oy < ay - 10:
                            # Another anchor above in same column
                            ceiling = max(ceiling, oy + 10)

                    # Collect words in a vertical strip above the anchor
                    nearby = sorted(
                        [
                            w
                            for w in words
                            if abs(w["x0"] - ax) < x_tolerance
                            and ceiling < w["top"] < ay + 20
                            and w["text"].strip()
                        ],
                        key=lambda w: w["top"],
                    )
                    if not nearby:
                        continue

                    name_parts: list[str] = []
                    prices: list[float] = []
                    discount: float | None = None

                    for w in nearby:
                        txt = w["text"].strip()

                        # Fix doubled characters (OCR artefact)
                        txt = _fix_doubled_chars(txt)

                        # Price (standalone like "13.99")
                        if re.match(r"^\d{1,3}[.,]\d{2}$", txt):
                            p = float(txt.replace(",", "."))
                            if PRICE_MIN <= p <= PRICE_MAX:
                                prices.append(p)
                            continue

                        # Discount
                        dm = re.match(r"-(\d{1,2})%", txt)
                        if dm:
                            discount = float(dm.group(1))
                            continue

                        # Weight / quantity (skip, not part of name)
                        if re.match(
                            r"^(?:\d+\s*(?:x\s*\d+\s*)?(?:g|kg|ml|l|cl|dl|stk|liter|stück)\b)",
                            txt,
                            re.IGNORECASE,
                        ):
                            continue

                        # Per-unit price like "100 g = 1.54"
                        if re.match(r"\d+\s*(?:g|kg|ml|l)\s*=", txt):
                            continue

                        # Skip article numbers
                        if article_re.match(txt):
                            continue
                        # Also skip the other retailer's article pattern
                        if _ALDI_ARTICLE_RE.match(txt) or _LIDL_ARTICLE_RE.match(txt):
                            continue

                        # Per-unit prices with /
                        if "/" in txt and re.search(r"\d", txt):
                            continue

                        # Skip metadata words (whole-word matching to avoid false positives)
                        txt_lower = txt.lower()
                        txt_words = set(re.findall(r"\w+", txt_lower))
                        if txt_words & _BLOCK_SKIP_WORDS:
                            continue

                        # Skip page headers
                        if _PAGE_HEADER_RE.search(txt):
                            continue

                        # Skip date patterns
                        if re.match(r"(?:Ab\s+)?(?:Do|Mo|Di|Mi|Fr|Sa|So)\.", txt, re.IGNORECASE):
                            continue
                        if re.search(r"\d{1,2}\.\d{1,2}\.", txt):
                            continue

                        # Skip "Herkunft: ..." lines
                        if txt_lower.startswith("herkunft"):
                            continue

                        # Product name part: must have ≥3 alpha chars
                        alpha_count = sum(1 for c in txt if c.isalpha())
                        if alpha_count >= 3 and len(txt) >= 3:
                            # Join hyphenated fragments (Lachs- + spitzen)
                            if name_parts and name_parts[-1].endswith("-"):
                                name_parts[-1] = name_parts[-1][:-1] + txt
                            else:
                                name_parts.append(txt)

                    if not name_parts:
                        continue

                    name = " ".join(name_parts[:max_name_parts]).strip()
                    name = re.sub(r"[•·]", "", name).strip()
                    name = re.sub(r"\s+", " ", name)

                    # Skip if too short or already seen
                    if len(name) < 4 or name.lower() in seen:
                        continue

                    # Skip names that are all caps and look like headers
                    if name.isupper() and len(name.split()) <= 2 and len(name) < 20:
                        if name.lower() in _CATEGORY_HEADERS:
                            continue

                    # Clean trailing hyphens and fragments
                    name = re.sub(r"\s*-\s*$", "", name).strip()
                    # Remove "t: Schweiz" type trailing metadata
                    name = re.sub(r"\s+t:\s+\w+$", "", name).strip()
                    if len(name) < 4:
                        continue

                    # Skip garbled text (high non-ASCII/non-letter ratio)
                    alpha_ratio = sum(1 for c in name if c.isalpha()) / max(len(name), 1)
                    if alpha_ratio < 0.5:
                        continue

                    # Skip names starting with lowercase (broken fragments)
                    if name[0].islower() and not name[0].isdigit():
                        continue

                    # Skip non-grocery content (plant care, fashion, etc.)
                    name_lower = name.lower()
                    if any(w in name_lower for w in (
                        "sonnig", "halbschattig", "drinnen", "draussen",
                        "wasserkammer", "regelmässig", "integriert",
                    )):
                        continue

                    if not prices:
                        continue

                    sale_price = min(prices)
                    orig_price = (
                        max(prices) if len(prices) > 1 else None
                    )
                    if orig_price and sale_price and orig_price <= sale_price:
                        orig_price = None

                    if not discount and sale_price and orig_price:
                        discount = round(
                            (1 - sale_price / orig_price) * 100, 0
                        )

                    seen.add(name.lower())
                    products.append(
                        {
                            "retailer": retailer,
                            "name": name,
                            "price": sale_price,
                            "original_price": orig_price,
                            "discount_pct": discount,
                            "category": "offer",
                        }
                    )
    except Exception as e:
        logger.warning(f"Block extraction failed for {retailer}: {e}")

    return products


def _extract_with_pdfplumber(file_path: str) -> str:
    """Extract text from PDF using pdfplumber (fast, works on embedded text)."""
    try:
        import pdfplumber
    except ImportError:
        return ""

    text_parts = []
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
    except Exception as e:
        logger.warning(f"pdfplumber failed: {e}")

    return "\n".join(text_parts)


def _extract_with_docling(file_path: str) -> str:
    """Extract text from PDF/image using Docling OCR (slow, for scanned docs)."""
    try:
        from docling.document_converter import DocumentConverter
    except ImportError:
        logger.warning("Docling not available")
        return ""

    try:
        converter = DocumentConverter()
        result = converter.convert(file_path)
        return result.document.export_to_markdown()
    except Exception as e:
        logger.error(f"Docling extraction failed: {e}")
        return ""


def extract_products_from_file(
    file_path: str | Path, retailer: str, *, skip_ocr: bool = False
) -> list[dict]:
    """Extract products from a PDF file.

    Strategy: try pdfplumber first (fast text extraction for PDFs with
    embedded text). If pdfplumber finds fewer than 3 products and skip_ocr
    is False, fall back to Docling OCR (slow but handles scanned/image PDFs).
    """
    file_path = str(file_path)

    # Aldi/Lidl: use article-number-anchored block extraction (grid layout)
    if retailer in ("aldi", "lidl"):
        block_products = _extract_blocks(file_path, retailer)
        if len(block_products) >= 3:
            logger.info(
                f"Block extractor ({retailer}): {len(block_products)} products "
                f"from {Path(file_path).name}"
            )
            return block_products

    # Step 1: Try pdfplumber (fast — seconds)
    text = _extract_with_pdfplumber(file_path)
    products = _parse_products_from_text(text, retailer)

    if len(products) >= 3 or skip_ocr:
        logger.info(
            f"pdfplumber: {len(products)} products from {Path(file_path).name}"
        )
        return products

    # Step 2: Fallback to Docling OCR (slow — minutes on CPU)
    logger.info(
        f"pdfplumber found only {len(products)} products, trying Docling OCR..."
    )
    md = _extract_with_docling(file_path)
    if md:
        docling_products = _parse_products_from_text(md, retailer)
        if len(docling_products) > len(products):
            logger.info(
                f"Docling: {len(docling_products)} products from "
                f"{Path(file_path).name}"
            )
            return docling_products

    logger.info(
        f"PDF extraction: {len(products)} products from {Path(file_path).name}"
    )
    return products


async def _extract_in_thread(
    data: bytes, retailer: str, suffix: str, *, skip_ocr: bool = False
) -> list[dict]:
    """Write data to temp file, run extraction in a thread, then clean up."""
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    try:
        tmp.write(data)
        tmp.flush()
        tmp.close()
        return await asyncio.to_thread(
            extract_products_from_file, tmp.name, retailer, skip_ocr=skip_ocr
        )
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


async def extract_products_from_pdf_bytes(
    pdf_bytes: bytes,
    retailer: str,
    filename: str = "prospekt.pdf",
    *,
    skip_ocr: bool = False,
) -> list[dict]:
    """Extract products from PDF bytes (downloaded via HTTP)."""
    suffix = Path(filename).suffix or ".pdf"
    return await _extract_in_thread(pdf_bytes, retailer, suffix, skip_ocr=skip_ocr)


async def extract_products_from_image_bytes(
    image_bytes: bytes, retailer: str, filename: str = "page.jpg"
) -> list[dict]:
    """Extract products from a flyer page image using Docling OCR."""
    suffix = Path(filename).suffix or ".jpg"
    return await _extract_in_thread(image_bytes, retailer, suffix)
