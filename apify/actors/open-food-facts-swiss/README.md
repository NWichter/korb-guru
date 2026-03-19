# Swiss Open Food Facts Importer

Apify Actor that imports Swiss product data from the [Open Food Facts](https://world.openfoodfacts.org/) API.

## What it does

- Fetches products tagged with `countries_tags_en=Switzerland` from the Open Food Facts v2 search API
- Filters for products with a German name and a completeness score above the configured threshold
- Maps allergen tags to simple names (e.g. `en:milk` -> `lactose`)
- Maps category tags to normalized categories (dairy, fruits, vegetables, meat, bakery, beverages, etc.)
- Extracts nutritional info (calories, protein, fat, carbs) from the `nutriments` field
- Rate-limits requests to 1 per second to respect the API fair-use policy

## Output

Each product is pushed to the default dataset with this structure:

```json
{
  "ean": "7610000123456",
  "name": "Migros Bio Vollmilch 1L",
  "brand": "Migros Bio",
  "price": null,
  "category": "dairy",
  "image_url": "https://images.openfoodfacts.org/...",
  "allergens": ["lactose"],
  "nutritional_info": {
    "calories": 64,
    "protein": 3.3,
    "fat": 3.5,
    "carbs": 4.8
  },
  "nutriscore": "A",
  "stores": ["Migros"],
  "source": "openfoodfacts",
  "region": "switzerland"
}
```

## Input

| Parameter       | Type | Default | Description                    |
| --------------- | ---- | ------- | ------------------------------ |
| maxProducts     | int  | 5000    | Maximum products to import     |
| categories      | list | []      | OFF category tags to filter by |
| minCompleteness | int  | 50      | Minimum completeness % (0-100) |
