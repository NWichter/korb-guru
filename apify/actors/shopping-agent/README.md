# Korb Shopping Agent

AI shopping agent that orchestrates grocery search, Qdrant retrieval, and LLM-powered recommendations for Swiss grocery shopping.

## Input Parameters

| Parameter             | Type     | Required | Default                                        | Description                                                                        |
| --------------------- | -------- | -------- | ---------------------------------------------- | ---------------------------------------------------------------------------------- |
| `query`               | string   | Yes      | —                                              | Natural language shopping query (e.g., "Zutaten für Pasta Carbonara unter CHF 15") |
| `budget`              | number   | No       | `50.0`                                         | Maximum budget in CHF                                                              |
| `preferred_retailers` | string[] | No       | `["migros", "coop", "aldi", "denner", "lidl"]` | Preferred retailers                                                                |
| `region`              | string   | No       | `"zurich"`                                     | Swiss region (`zurich`, `bern`, `basel`)                                           |
| `qdrant_url`          | string   | No       | —                                              | Qdrant Cloud cluster URL                                                           |
| `qdrant_api_key`      | string   | No       | —                                              | Qdrant Cloud API key (secret)                                                      |
| `openrouter_api_key`  | string   | No       | —                                              | OpenRouter API key for LLM access (secret)                                         |
| `scrape_fresh`        | boolean  | No       | `false`                                        | Run swiss-grocery-scraper for fresh data before searching                          |
| `find_stores`         | boolean  | No       | `false`                                        | Use Google Maps to find nearby stores                                              |

## Output

Shopping recommendations with:

- Matched products with prices and stores
- Total cost and savings estimates
- LLM-generated reasoning and explanations
- Alternative store suggestions

## Example Input

```json
{
  "query": "Zutaten für Pasta Carbonara unter CHF 15",
  "budget": 15.0,
  "preferred_retailers": ["migros", "coop"],
  "region": "zurich",
  "qdrant_url": "https://xxx.qdrant.io",
  "qdrant_api_key": "...",
  "openrouter_api_key": "...",
  "scrape_fresh": false,
  "find_stores": true
}
```

## Tech Stack

- **Apify SDK** — Actor runtime and orchestration
- **Qdrant** — Vector/hybrid search over product data
- **OpenRouter** — LLM access for query parsing and recommendation reasoning
- **Google Maps** — Nearby store lookup via Apify platform actor
