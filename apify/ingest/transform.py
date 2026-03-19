"""Normalize product data from Apify Actor output into a common format."""
import logging
import re
import unicodedata

logger = logging.getLogger(__name__)

PRICE_MIN = 0.10
PRICE_MAX = 500.0

# Junk product names that should be filtered out during normalization
_JUNK_NAME_RE = re.compile(
    r"^("
    r"\d{1,3}\s*%"
    r"|ab\s|bis\s|gültig\s"
    r"|herkunft|gewicht|inhalt"
    r"|je\s|pro\s"
    r"|\d+\s*(?:g|kg|ml|l|cl|dl|stk|st)\b"
    r"|seite\s*\d"
    r"|www\."
    r"|montag|dienstag|mittwoch|donnerstag|freitag|samstag|sonntag"
    r"|aktion\s*$|angebot\s*$|rabatt\s*$|sparen\s*$|gratis\s*$|neu\s*$"
    r"|\d+\s*(?:tage|nächte)"
    r"|buchbar|reise|flug|hotel|kreuzfahrt|wellness"
    r"|termine:|voucher|gutschein"
    r"|farbe|grösse|sortiment"
    r"|preishighlight|preiserhebung|preisvergleich"
    r"|.*z\.\s*B\.\s*$"
    r"|(?:mo|di|mi|do|fr|sa|so)\s*[-–]\s*(?:mo|di|mi|do|fr|sa|so)"
    r"|leistung|eigene\s+erhebung"
    r")",
    re.IGNORECASE,
)

# Category headers that aren't real products
_CATEGORY_HEADERS = frozenset({
    "fleisch", "fisch", "gemüse", "obst", "früchte", "backwaren",
    "getränke", "molkerei", "käse", "wurst", "brot", "snacks",
    "süsswaren", "tiefkühl", "haushalt", "pflege", "beauty",
    "damen", "herren", "kinder", "baby", "sport", "garten",
    "qualität", "licht", "schweizer", "leistung", "farbe",
    "sortiment", "aktion", "angebot", "highlight",
    "woche", "favorit", "klassiker", "neuheit", "tipp", "top", "hit",
})


_NON_GROCERY_WORDS = frozenset({
    "reise", "hotel", "flug", "kreuzfahrt", "nächte", "tage",
    "kabine", "innenkabine", "dz", "ez", "economy", "class",
    "buchbar", "voucher", "gutschein", "termine",
    "damen", "herren", "kinder", "grösse",
    "velosattel", "velozubehör", "kulturtopf",
    "licht", "lampe", "led", "leuchte",
    "packung", "stück", "erhebung",
    "nordlicht", "wellness", "versprechen",
    "plüsch", "wecker", "geschirrtücher", "fitnessbereich",
})

# Price fragments embedded in product names (e.g. "Milch 1L CHF 2.50")
_PRICE_FRAGMENT_RE = re.compile(
    r"\s*(?:CHF|Fr\.?|SFr\.?)\s*\d+[.,]?\d*\s*$", re.IGNORECASE
)

# Promotional prefixes to strip
_PROMO_PREFIX_RE = re.compile(
    r"^(?:AKTION|NEU|TIPP|TOP|HIT)\s*:\s*", re.IGNORECASE
)

# OCR doubled-character pattern: each char appears twice (e.g. "RRÜÜEEEBBLLII")
_OCR_DOUBLED_RE = re.compile(r"(.)\1", re.IGNORECASE)

MAX_NAME_LENGTH = 100


def clean_product_name(name: str) -> str:
    """Normalize a product name: Unicode, whitespace, promo prefixes, price fragments, OCR fixes."""
    # Unicode NFKC normalization
    name = unicodedata.normalize("NFKC", name)

    # Strip and collapse whitespace
    name = " ".join(name.split())

    # Remove promotional prefixes
    name = _PROMO_PREFIX_RE.sub("", name).strip()

    # Remove trailing price fragments
    name = _PRICE_FRAGMENT_RE.sub("", name).strip()

    # Fix OCR doubled characters: if >60% of char-pairs are doubles, de-duplicate
    if len(name) >= 8:
        pairs_total = len(name) // 2
        doubled = len(_OCR_DOUBLED_RE.findall(name))
        if pairs_total > 0 and doubled / pairs_total > 0.6:
            # De-duplicate: take every other character
            name = "".join(name[i] for i in range(0, len(name), 2))

    # Cap length
    if len(name) > MAX_NAME_LENGTH:
        name = name[:MAX_NAME_LENGTH].rsplit(" ", 1)[0]

    return name.strip()


# Regex for concatenated text (camelCase / digit-letter transitions)
_CONCAT_PATTERN = re.compile(r"[a-zäöü][A-ZÄÖÜ]")
_DIGIT_ALPHA = re.compile(r"\d[a-zA-ZäöüÄÖÜ]")

# Non-grocery product keywords
_NON_GROCERY_PRODUCT_RE = re.compile(
    r"\b(?:cien|beauty|kosmetik|pinsel|manikure|pedikure|multigroomer|"
    r"personenwaage|schmucktablett|barttrimmer|bürste|bettwäsche|"
    r"mikrofaser|satin|gardine|vorhang|laptop|tablet|smartphone|"
    r"bluetooth|kopfhörer|plüsch|wecker|geschirrtücher)\b",
    re.IGNORECASE,
)


def _is_junk_name(name: str) -> bool:
    """Check if a product name is junk (metadata, category header, etc.)."""
    if not name or len(name) < 3:
        return True
    # Reject names that are >50% digits or special characters
    alpha_count = sum(1 for c in name if c.isalpha())
    if len(name) > 0 and alpha_count / len(name) < 0.5:
        return True
    # Reject names that are just currency/price strings
    if re.match(r"^[\d.,\s]+(?:CHF|Fr\.?|SFr\.?|%|.-)?$", name, re.IGNORECASE):
        return True
    # Reject placeholder/filler text from OCR
    if re.match(r"^[.\-_=*#/\\|+]+$", name):
        return True
    if _JUNK_NAME_RE.match(name):
        return True
    if name.lower().strip() in _CATEGORY_HEADERS:
        return True
    # Short all-caps words are likely category headers (but not valid product names)
    if name.isupper() and len(name.split()) <= 3 and len(name) < 20:
        return True
    # Fewer than 3 alphabetic characters
    if sum(1 for c in name if c.isalpha()) < 3:
        return True
    # Doubled characters (OCR artefact)
    if len(name) >= 10:
        pairs = sum(1 for i in range(0, len(name) - 1, 2) if name[i] == name[i + 1])
        total_pairs = len(name) // 2
        if total_pairs > 0 and pairs / total_pairs > 0.6:
            return True
    # Repeated words (OCR artefact: "SCHWEIZER SCHWEIZER 250 g")
    # Only flag if consecutive words repeat (not brand names like "Beyond Meat Beyond")
    words = name.split()
    consecutive_repeats = sum(
        1 for i in range(len(words) - 1)
        if words[i].lower() == words[i + 1].lower() and len(words[i]) > 2
    )
    if consecutive_repeats >= 1:
        return True
    # Non-grocery words (≥2 matches = skip)
    name_words = set(name.lower().split())
    if len(name_words & _NON_GROCERY_WORDS) >= 2:
        return True
    # Concatenated text (camelCase transitions indicate missing spaces)
    camel_count = len(_CONCAT_PATTERN.findall(name))
    digit_alpha_count = len(_DIGIT_ALPHA.findall(name))
    if camel_count + digit_alpha_count >= 2:
        return True
    # Names starting with bullet points + travel/promo content
    if name.startswith("•") or name.startswith("·"):
        return True
    # "auch in" type fragments
    if name.lower().startswith("auch in") or name.lower().startswith("oder "):
        return True
    # Color-only names
    if name.lower().strip() in {"schwarz", "weiss", "blau", "rot", "grün", "gelb", "braun", "rosa", "grau"}:
        return True
    # Non-grocery products
    if _NON_GROCERY_PRODUCT_RE.search(name):
        return True
    # Names containing "Wert:" or similar metadata/fragments
    lower = name.lower()
    if re.search(r"(?:\b(?:normalpreis|statt|preis)\b|wert:|erwartet\.)", lower):
        if len(name) < 20:  # Short fragments containing these words
            return True
    # Date patterns like "26.2.bis18." or "Nur von Do., 26.2."
    if re.search(r"\d{1,2}\.\d{1,2}\.(?:bis|ab)", name):
        return True
    if re.match(r"(?:Nur\s+von|Gültig|Ab|Bis)\b", name, re.IGNORECASE):
        return True
    # Broken text fragments (short with parentheses/symbols)
    if len(name) < 25 and re.search(r"[(){}]", name):
        return True
    # Names starting with lowercase (broken sentence fragments)
    if name[0].islower() and len(name.split()) >= 2:
        return True
    # Names with embedded period-number patterns (travel itineraries)
    if re.search(r"\d+\.\s*[-–]\s*\d+\.\s*Tag", name):
        return True
    # Names containing "Besichtigung", "Abflug", etc. (travel content)
    if re.search(r"(?:Besichtigung|Abflug|Badeaufenthalt|Kreuzfahrt|Tempel)", name, re.IGNORECASE):
        return True
    # Names with colons followed by concatenated words (PDF extraction artefacts)
    if ":" in name and len(name.split()) <= 2 and len(name) < 30:
        return True
    # Concatenated abbreviations like "6202.3.4sib." or "z.B.am6."
    if re.search(r"\d{3,}\.\d+\.\d+", name):
        return True
    if re.match(r"[a-z.]+\d", name) and len(name) < 15:
        return True
    # "ab2Stück" type concatenations
    if re.match(r"ab\d", name, re.IGNORECASE):
        return True
    # "z.B." starting names
    if name.lower().startswith("z.b."):
        return True
    # Long single words without spaces are concatenated text (>30 chars)
    # German compound words can be 25+ chars (Gelbflossenthunfischfilets)
    longest_word = max((len(w) for w in name.split()), default=0)
    if longest_word > 30:
        return True
    # "imDZ", "Gültigbis" — short concatenated words starting lowercase
    if re.match(r"[a-zäöü]+[A-ZÄÖÜ]", name) and len(name) < 20:
        return True
    return False


def normalize_items(items: list[dict], source: str) -> list[dict]:
    """Normalize items from Actor output into common product schema."""
    normalized = []

    for item in items:
        try:
            price = _extract_price(item)
            original_price = _extract_float(item.get("originalPrice") or item.get("regularPrice"))

            # Validate prices
            price = _validate_price(price)
            original_price = _validate_price(original_price)

            discount_pct = _extract_float(item.get("discount") or item.get("discountPercent") or item.get("discount_pct"))

            product = {
                "retailer": _detect_retailer(item, source),
                "name": item.get("name") or item.get("title") or item.get("productName", ""),
                "description": item.get("description") or item.get("desc", ""),
                "price": price,
                "original_price": original_price,
                "discount_pct": discount_pct,
                "category": item.get("category") or item.get("categoryName", ""),
                "image_url": item.get("image") or item.get("imageUrl") or item.get("img") or item.get("image_url", ""),
                "source": "apify",
            }

            # Calculate discount if we have both prices but no explicit discount
            if product["price"] and product["original_price"] and not product["discount_pct"]:
                if product["original_price"] > product["price"]:
                    product["discount_pct"] = round(
                        (1 - product["price"] / product["original_price"]) * 100, 1
                    )

            name = clean_product_name(product["name"])
            if _is_junk_name(name):
                continue
            product["name"] = name
            normalized.append(product)
        except Exception as e:
            logger.warning(f"Failed to normalize item: {e}")

    logger.info(f"Normalized {len(normalized)}/{len(items)} items from {source}")
    return normalized


def _detect_retailer(item: dict, source: str) -> str:
    if source in ("aldi", "lidl", "migros", "coop", "denner"):
        return source
    return (
        item.get("retailer")
        or item.get("store")
        or item.get("chain", "")
    ).lower() or source


def _extract_price(item: dict) -> float | None:
    for key in ("price", "currentPrice", "salePrice", "priceNum"):
        val = item.get(key)
        if val is not None:
            return _extract_float(val)
    return None


def _extract_float(val) -> float | None:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return round(float(val), 2)
    try:
        cleaned = str(val).replace("CHF", "").replace(",", ".").replace("Fr.", "").strip()
        return round(float(cleaned), 2)
    except (ValueError, TypeError):
        return None


def _validate_price(price: float | None) -> float | None:
    """Return price only if within valid range."""
    if price is None:
        return None
    if PRICE_MIN <= price <= PRICE_MAX:
        return price
    return None
