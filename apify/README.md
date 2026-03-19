# Apify Integration

korb.guru uses Apify as its web data infrastructure. We built **4 custom Actors** and use **1 platform Actor** to collect live grocery data from 5 Swiss retailers.

**Apify Profile:** [apify.com/nwichter](https://apify.com/nwichter)

---

## Custom Actors (Built by us)

### 1. swiss-grocery-scraper

**Apify Store:** [nwichter/swiss-grocery-scraper](https://apify.com/nwichter/swiss-grocery-scraper)
**Source:** `actors/swiss-grocery-scraper/`

Scrapes weekly offers from all 5 major Swiss grocery retailers. Each retailer has a completely different website structure, so the Actor implements 5 distinct scraping strategies:

| Retailer | Method                        | Data Source                | How it works                                                                                                                            |
| -------- | ----------------------------- | -------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| Aldi     | PDF + Docling OCR             | Scene7 CDN weekly prospekt | Downloads the weekly PDF prospekt, extracts product blocks using Docling OCR with article-number anchoring, normalizes prices and names |
| Migros   | Playwright (headless)         | migros.ch/de/offers        | Renders the JavaScript-heavy offers page with Playwright, extracts product cards from the DOM                                           |
| Coop     | ePaper JSON API + pdfplumber  | epaper.coopzeitung.ch      | Fetches the ePaper JSON index, downloads individual pages, extracts products using pdfplumber layout analysis                           |
| Denner   | BeautifulSoup HTML            | denner.ch/aktionen         | Parses the static HTML promotions page with BeautifulSoup, extracts product data from structured markup                                 |
| Lidl     | Leaflets API + PDF enrichment | endpoints.leaflets.schwarz | Calls the Schwarz Group leaflets API for structured data, enriches with PDF extraction for missing fields                               |

**Output per product:**

```json
{
  "name": "Bio Vollmilch 1L",
  "price": 1.85,
  "original_price": 2.3,
  "discount_pct": 20,
  "category": "dairy",
  "retailer": "lidl",
  "valid_from": "2026-03-18",
  "valid_to": "2026-03-24",
  "image_url": "https://..."
}
```

**Technologies:** Crawlee, Playwright, Docling OCR, BeautifulSoup, pdfplumber, httpx.

---

### 2. shopping-agent

**Apify Store:** [nwichter/shopping-agent](https://apify.com/nwichter/shopping-agent)
**Source:** `actors/shopping-agent/`

An AI-powered shopping assistant that accepts natural language queries and returns personalized product recommendations. This Actor demonstrates the **AI Agents** path of the Apify Challenge.

**How it works:**

1. User sends a natural language query (e.g., "Find the cheapest pasta" or "What cheese is on sale?")
2. Query is embedded locally using fastembed (`paraphrase-multilingual-MiniLM-L12-v2`, 384-dim)
3. Qdrant hybrid search combines dense (semantic) + sparse (BM25) vectors with Reciprocal Rank Fusion
4. OpenRouter LLM (via Apify proxy) reasons about the search results and generates a natural language response
5. Returns ranked products with prices, savings estimates, and retailer comparison

**Technologies:** fastembed, Qdrant client, OpenRouter API (via Apify proxy), MD5-based deterministic sparse vectors (2^20 buckets).

**Prompts:** `actors/shopping-agent/prompts/shopping-recommendations.md`

---

### 3. open-food-facts-swiss

**Apify Store:** [nwichter/open-food-facts-swiss](https://apify.com/nwichter/open-food-facts-swiss)
**Source:** `actors/open-food-facts-swiss/`

Imports the complete Swiss product catalog from the Open Food Facts API — **102,000+ products** with full nutritional data. This provides the base product catalog that weekly scraping builds on top of.

**Data extracted per product:**

- Name, barcode, brands
- Categories (hierarchical)
- Nutri-Score grade (A-E)
- Allergens (gluten, lactose, nuts, etc.)
- Full nutritional values (energy, fat, protein, carbs, sugar, salt, fiber)
- Product images

**Input:** Country filter (default: Switzerland), optional category filter, batch size.

---

### 4. recipe-collector

**Apify Store:** [nwichter/recipe-collector](https://apify.com/nwichter/recipe-collector)
**Source:** `actors/recipe-collector/`

Collects recipes from multiple sources and outputs structured recipe data ready for vector embedding. Currently ingests **3,500+ recipes**.

**Sources:**

- **RSS feeds:** Chefkoch.de (Germany's largest recipe site), SRF (Swiss public broadcaster cooking section)
- **RecipeNLG dataset:** Academic dataset with structured recipes
- **Curated classics:** 50 hand-picked Swiss recipes (Rösti, Fondue, Zürcher Geschnetzeltes, etc.)

**Output per recipe:**

```json
{
  "name": "Zürcher Geschnetzeltes",
  "ingredients": ["veal", "cream", "mushrooms", "white wine"],
  "instructions": "...",
  "time_minutes": 35,
  "servings": 4,
  "type": "main",
  "source": "curated-swiss"
}
```

---

## Platform Actor (Apify Store)

### 5. compass/crawler-google-places

**Apify Store:** [compass/crawler-google-places](https://apify.com/compass/crawler-google-places)

We use this existing platform Actor to discover store locations for all 5 retailers in the Zurich region. **102 stores** ingested with coordinates, opening hours, ratings, and addresses.

**Input:** Search queries like "Migros Zürich", "Coop Zürich", etc. with geographic bounds.

---

## Setting Up Scheduled Runs

To keep product data fresh, configure Apify Schedules for automatic weekly scraping:

### Step 1: Go to Apify Schedules

Navigate to [console.apify.com/schedules](https://console.apify.com/schedules) and click "Create new schedule".

### Step 2: Configure the scraper schedule

| Setting         | Value                                                           |
| --------------- | --------------------------------------------------------------- |
| Name            | `korb-guru-weekly-scrape`                                       |
| Cron expression | `0 6 * * 1,4` (Mon + Thu at 06:00 UTC)                          |
| Timezone        | `Europe/Zurich`                                                 |
| Actor           | `nwichter/swiss-grocery-scraper`                                |
| Input           | `{ "retailers": ["aldi", "migros", "coop", "denner", "lidl"] }` |

### Step 3: Configure the webhook

After the Actor finishes, it should POST the results to your backend:

1. In the Actor run settings, add a **webhook**:
   - Event type: `ACTOR.RUN.SUCCEEDED`
   - URL: `https://api.korb.guru/ingest`
   - Headers: `{ "Authorization": "Bearer YOUR_INGEST_API_KEY" }`

2. The backend automatically embeds products and upserts to PostgreSQL + Qdrant.

### Step 4: Optional — schedule Open Food Facts refresh

| Setting         | Value                                        |
| --------------- | -------------------------------------------- |
| Name            | `korb-guru-off-monthly`                      |
| Cron expression | `0 2 1 * *` (1st of each month at 02:00 UTC) |
| Actor           | `nwichter/open-food-facts-swiss`             |

### Step 5: Optional — schedule recipe refresh

| Setting         | Value                             |
| --------------- | --------------------------------- |
| Name            | `korb-guru-recipes-weekly`        |
| Cron expression | `0 3 * * 0` (Sunday at 03:00 UTC) |
| Actor           | `nwichter/recipe-collector`       |

---

## Data Pipeline

```
Apify Schedule (Mon/Thu 06:00 UTC)
  → swiss-grocery-scraper runs
    → Dataset JSON output (~370 products/week)
      → Webhook POST /ingest
        → FastAPI embeds with fastembed (384-dim)
          → Upserts to PostgreSQL + Qdrant (hybrid vectors)
```

---

## Orchestrator (Local/CI)

For manual runs or CI pipelines, use the orchestrator script:

```bash
# Run all retailers
python orchestrator.py

# Single retailer
python orchestrator.py --chain=aldi

# With automatic Qdrant ingestion
python orchestrator.py --ingest

# Preview what would run
python orchestrator.py --dry-run
```

**Config:** `config.py` — Actor IDs, tokens, retailer list.

---

## OpenRouter LLM Integration

The shopping-agent Actor uses OpenRouter via Apify's proxy for LLM reasoning:

- **Primary:** `https://openrouter.apify.actor/api/v1/chat/completions` (auth via `APIFY_TOKEN`)
- **Fallback:** Direct OpenRouter API (auth via `OPENROUTER_API_KEY`)
- **Default model:** `google/gemini-2.5-flash`

The backend `LLMService` (`backend/src/services/llm_service.py`) uses the same dual-provider pattern for product categorization, description enrichment, and ingredient extraction.

---

## Challenge Coverage

| Apify Challenge Path     | How We Cover It                                                                                      |
| ------------------------ | ---------------------------------------------------------------------------------------------------- |
| **AI Agents**            | Shopping Agent Actor: NL query → Qdrant hybrid search → LLM reasoning → personalized recommendations |
| **RAG Applications**     | 102k+ products + 3.5k recipes in Qdrant as retrieval layer, preference-based re-ranking              |
| **Build an Apify Actor** | 4 custom Actors published on Apify Store, each reusable and serverless                               |
