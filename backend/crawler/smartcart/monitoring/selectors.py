"""Centralized registry of CSS selectors per retailer for health monitoring."""

SELECTOR_REGISTRY = {
    "denner": {
        "url": "https://www.denner.ch/de/aktionen-und-sortiment/aktuelle-aktionen",
        "method": "beautifulsoup",
        "selectors": {
            "product_cards": "[class*='product-card'], [class*='product-tile'], [class*='promotion-item']",
            "product_name": "[class*='product-name'], [class*='product-title'], h3, h4",
            "price": "[class*='price']",
        },
        "min_expected": 3,
    },
    "migros": {
        "url": "https://www.migros.ch/de/aktionen.html",
        "method": "playwright",
        "selectors": {
            "product_cards": '[class*="product-card"], [class*="ProductCard"], [class*="offer-card"], article[class*="product"]',
            "product_name": '[class*="product-name"], [class*="ProductName"], h2, h3, [class*="title"]',
            "price": '[class*="price"], [class*="Price"]',
        },
        "min_expected": 3,
    },
    "coop": {
        "url": "https://www.coop.ch/de/aktionen.html",
        "method": "playwright",
        "selectors": {
            "product_cards": '[class*="product"], [class*="Product"], [class*="offer"], article',
            "product_name": '[class*="product-name"], [class*="productName"], h3, h4, [class*="title"]',
            "price": '[class*="price"], [class*="Price"]',
        },
        "min_expected": 3,
    },
    "aldi": {
        "url": None,
        "method": "head_check",
        "min_expected": 1,
    },
    "lidl": {
        "url": "https://www.lidl.ch/c/de-CH/werbeprospekte-als-pdf/s10019683",
        "method": "playwright",
        "selectors": {
            "pdf_links": 'a[href*=".pdf"], [data-href*=".pdf"], [download]',
        },
        "min_expected": 1,
    },
}
