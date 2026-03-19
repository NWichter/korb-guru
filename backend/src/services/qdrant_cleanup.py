"""Qdrant cleanup service — detect and remove junk products, re-embed cleaned names."""

import logging
import re
import unicodedata

from qdrant_client import models

from ..qdrant.client import get_qdrant_client
from .embedding_service import embed_text

logger = logging.getLogger(__name__)

COLLECTION = "products"
SCROLL_BATCH = 100

# Patterns that indicate junk payload names
_JUNK_PATTERNS = [
    re.compile(r"^[\d.,\s%]+$"),  # only digits/punctuation
    re.compile(r"^[.\-_=*#/\\|+]+$"),  # filler characters
    re.compile(r"^\d{1,3}\s*%", re.IGNORECASE),  # percentage labels
    re.compile(r"^(?:ab\s|bis\s|gültig\s)", re.IGNORECASE),  # date/range fragments
    re.compile(r"^(?:herkunft|gewicht|inhalt)\b", re.IGNORECASE),  # metadata labels
    re.compile(r"^(?:seite\s*\d|www\.)", re.IGNORECASE),  # page refs / URLs
    re.compile(
        r"^(?:montag|dienstag|mittwoch|donnerstag|freitag|samstag|sonntag)\b",
        re.IGNORECASE,
    ),
    re.compile(r"^(?:AKTION|NEU|TIPP|TOP|HIT)\s*$", re.IGNORECASE),  # bare promos
]

_PROMO_PREFIX_RE = re.compile(r"^(?:AKTION|NEU|TIPP|TOP|HIT)\s*:\s*", re.IGNORECASE)
_PRICE_FRAGMENT_RE = re.compile(
    r"\s*(?:CHF|Fr\.?|SFr\.?)\s*\d+[.,]?\d*\s*$", re.IGNORECASE
)


def _is_junk(name: str | None) -> bool:
    """Check if a product name is junk and should be deleted."""
    if not name or len(name.strip()) < 3:
        return True
    name = name.strip()
    # >50% non-alpha characters
    alpha_count = sum(1 for c in name if c.isalpha())
    if len(name) > 0 and alpha_count / len(name) < 0.5:
        return True
    # Fewer than 3 alphabetic characters
    if alpha_count < 3:
        return True
    for pat in _JUNK_PATTERNS:
        if pat.match(name):
            return True
    return False


def _clean_name(name: str) -> str:
    """Clean a product name (same logic as crawler transform)."""
    name = unicodedata.normalize("NFKC", name)
    name = " ".join(name.split())
    name = _PROMO_PREFIX_RE.sub("", name).strip()
    name = _PRICE_FRAGMENT_RE.sub("", name).strip()
    if len(name) > 100:
        name = name[:100].rsplit(" ", 1)[0]
    return name.strip()


def _needs_cleaning(name: str) -> bool:
    """Check if a name would change after cleaning."""
    return _clean_name(name) != name


def run_cleanup() -> dict:
    """Scan all products, delete junk, re-embed cleaned names.

    Returns a report dict with deleted_count, cleaned_count, remaining_count.
    """
    client = get_qdrant_client()

    delete_ids: list[str] = []
    clean_updates: list[tuple[str, str]] = []  # (point_id, cleaned_name)

    offset = None
    while True:
        results, next_offset = client.scroll(
            collection_name=COLLECTION,
            limit=SCROLL_BATCH,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        if not results:
            break

        for point in results:
            name = (point.payload or {}).get("name")
            if _is_junk(name):
                delete_ids.append(point.id)
            elif name and _needs_cleaning(name):
                cleaned = _clean_name(name)
                if _is_junk(cleaned):
                    delete_ids.append(point.id)
                else:
                    clean_updates.append((point.id, cleaned))

        if next_offset is None:
            break
        offset = next_offset

    # Delete junk points
    if delete_ids:
        client.delete(
            collection_name=COLLECTION,
            points_selector=models.PointIdsList(points=delete_ids),
        )
        logger.info("Deleted %d junk products", len(delete_ids))

    # Re-embed cleaned products
    cleaned_count = 0
    for point_id, cleaned_name in clean_updates:
        try:
            dense_vector = embed_text(cleaned_name)
            client.set_payload(
                collection_name=COLLECTION,
                payload={"name": cleaned_name},
                points=[point_id],
            )
            client.update_vectors(
                collection_name=COLLECTION,
                points=[
                    models.PointVectors(
                        id=point_id,
                        vector={"dense": dense_vector},
                    )
                ],
            )
            cleaned_count += 1
        except Exception as e:
            logger.warning("Failed to re-embed product %s: %s", point_id, e)

    # Count remaining
    collection_info = client.get_collection(COLLECTION)
    remaining = collection_info.points_count

    report = {
        "deleted_count": len(delete_ids),
        "cleaned_count": cleaned_count,
        "remaining_count": remaining,
    }
    logger.info("Cleanup report: %s", report)
    return report
