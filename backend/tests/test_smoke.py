"""Smoke test for API scaffold."""


def test_import_app():
    """App module can be imported."""
    from src.main import app  # noqa: F401

    assert app is not None
