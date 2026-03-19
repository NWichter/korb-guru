# Recipe Collector

Collects recipes from open sources and formats them for korb.guru's meal planning system.

## Data Sources

- **RSS Feeds** — Parses recipe feeds from chefkoch.de, allrecipes.com, and SRF A Point
- **RecipeNLG** — Filters German/Swiss recipes from the open RecipeNLG dataset (CC-BY-NC-SA)
- **Curated Swiss Classics** — 50 built-in Swiss classic recipes as fallback (Rösti, Fondue, Zürcher Geschnetzeltes, etc.)

## Output

Each recipe is pushed to the default dataset:

| Field          | Type     | Description                                 |
| -------------- | -------- | ------------------------------------------- |
| `title`        | string   | Recipe title                                |
| `description`  | string   | Short description                           |
| `ingredients`  | array    | List of `{name, quantity, unit}` objects    |
| `instructions` | string   | Cooking instructions                        |
| `time_minutes` | int/null | Estimated cooking time in minutes           |
| `servings`     | int      | Number of servings                          |
| `type`         | string   | Category: protein, veggie, carb, or dessert |
| `tags`         | array    | Tags (e.g. swiss, gluten-free, vegetarian)  |
| `source`       | string   | Data source: recipenlg, rss, or curated     |
| `source_url`   | string   | Original URL (if available)                 |

## Input

| Field        | Default              | Description                                     |
| ------------ | -------------------- | ----------------------------------------------- |
| `sources`    | ["recipenlg", "rss"] | Sources to collect from                         |
| `maxRecipes` | 100                  | Max recipes to collect (1-10000)                |
| `categories` | []                   | Filter by type (protein, veggie, carb, dessert) |
| `language`   | "de"                 | Preferred language (de, en, fr)                 |

## Example Input

```json
{
  "sources": ["rss"],
  "maxRecipes": 50,
  "language": "de"
}
```

## Technology

- Python 3.11, Apify SDK v3
- feedparser for RSS parsing
- httpx for HTTP requests
- Rate limited: max 1 request/second for RSS feeds
