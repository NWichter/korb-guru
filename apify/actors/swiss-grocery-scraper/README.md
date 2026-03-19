# Swiss Grocery Scraper

Scrapes weekly offers and promotions from the five major Swiss grocery retailers:

- **Aldi Suisse** — PDF flyer extraction via Docling
- **Migros** — Issuu Wochenflyer OCR + aktionen HTML page
- **Coop** — aktionen HTML page via Playwright
- **Denner** — aktionen HTML + Issuu Wochenprospekt
- **Lidl Schweiz** — PDF flyer discovery + extraction

## Output

Each scraped product is pushed to the default dataset with these fields:

| Field          | Type   | Description                                      |
| -------------- | ------ | ------------------------------------------------ |
| `retailer`     | string | Retailer name (aldi, migros, coop, denner, lidl) |
| `name`         | string | Product name                                     |
| `price`        | number | Price in CHF                                     |
| `discount_pct` | number | Discount percentage (if available)               |
| `image_url`    | string | URL to product image (if available)              |
| `category`     | string | Product category                                 |
| `region`       | string | Swiss region                                     |

## Input

| Field           | Default  | Description                                      |
| --------------- | -------- | ------------------------------------------------ |
| `retailers`     | all five | Array of retailer names to scrape                |
| `region`        | zurich   | Swiss region (zurich, bern, basel)               |
| `maxItems`      | 200      | Max items per retailer (1-1000)                  |
| `webhookUrl`    | —        | Optional webhook URL for completion notification |
| `webhookApiKey` | —        | Optional API key for webhook auth header         |

## Example Input

```json
{
  "retailers": ["migros", "coop"],
  "region": "zurich",
  "maxItems": 50
}
```

## How It Works

1. Scrapes all requested retailers in parallel
2. Uses Crawlee (Playwright/BeautifulSoup) for HTML pages
3. Uses Docling for PDF/image OCR extraction
4. Pushes structured product data to the dataset
5. Stores a run summary in the key-value store
6. Optionally sends a webhook notification on completion

## Technology

- Python 3.12, Apify SDK v3, Crawlee v1.5
- Docling for document/PDF/image extraction
- Playwright for JavaScript-rendered pages
- BeautifulSoup for static HTML pages
