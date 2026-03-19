"""ISO week and date range helpers for Swiss prospekt scraping."""
from datetime import date, timedelta


def get_iso_week(d: date | None = None) -> tuple[int, int]:
    """Returns (year, week) for the given date."""
    d = d or date.today()
    return d.isocalendar()[:2]


def get_week_monday(year: int, week: int) -> date:
    """Get the Monday of a given ISO week."""
    jan4 = date(year, 1, 4)
    start = jan4 - timedelta(days=jan4.weekday())
    return start + timedelta(weeks=week - 1)


def get_week_date_range(year: int, week: int) -> tuple[str, str]:
    """Returns (monday_str, saturday_str) in YYYY-MM-DD format."""
    monday = get_week_monday(year, week)
    saturday = monday + timedelta(days=5)
    return monday.isoformat(), saturday.isoformat()


def format_kw(week: int) -> str:
    """Zero-pad week number."""
    return str(week).zfill(2)


def get_current_kw() -> dict:
    """Get current calendar week info."""
    year, week = get_iso_week()
    monday, saturday = get_week_date_range(year, week)
    return {
        "year": year,
        "week": week,
        "kw_str": format_kw(week),
        "monday": monday,
        "saturday": saturday,
    }
