# korb.guru

**Smart grocery shopping. Better cooking.**

[![GenAI Zurich Hackathon 2026](https://img.shields.io/badge/GenAI_Zurich_Hackathon-2026-blue?style=for-the-badge)](https://genai-zurich.ch)

[Website](https://korb.guru) · [Web App](https://app.korb.guru) · [API Docs](https://api.korb.guru/docs)

---

## The Problem

Swiss households shop across 5 major grocery retailers -- Migros, Coop, Aldi Suisse, Denner, and Lidl. Each has different prices, weekly promotions, and store locations. There is no unified way to:

- Compare prices across retailers for the same product
- Plan meals based on what is actually on sale this week
- Build a shopping list that optimizes for budget and route
- Get recipe recommendations that improve with every interaction

korb.guru solves all of this.

---

## Our Solution

A grocery assistant that scrapes live prices from all 5 Swiss retailers, matches them against 102k+ products and 3.5k recipes, and learns user preferences through a swipe-based discovery interface. Every interaction feeds back into the vector space, making recommendations smarter over time.

**Key features:**

| Feature                    | Description                                                  |
| -------------------------- | ------------------------------------------------------------ |
| Hybrid product search      | Dense (semantic) + sparse (BM25) with Reciprocal Rank Fusion |
| Recipe discovery           | Tinder-style swiping with Qdrant Recommend + Discovery API   |
| Self-improving preferences | Evolving taste vectors updated on every swipe via EMA        |
| Price comparison           | Cross-retailer comparison for any ingredient                 |
| Meal planning              | Weekly planner with auto-generated grocery lists             |
| Route optimization         | Optimal shopping route across selected stores                |
| Household collaboration    | Shared lists, meal polls, budget tracking, chat              |
| Live weekly offers         | Scraped every Monday and Thursday from all 5 retailers       |
| Shopping agent             | Natural language queries → personalized recommendations      |

---

## Architecture

```
+------------------+     +------------------+     +--------------------+
|  Next.js         |     |  Apify Platform  |     |  Open Food Facts   |
|  Frontend        |     |  (5 Actors)      |     |  API               |
+--------+---------+     +--------+---------+     +--------+-----------+
         |                        |                         |
         | REST API               | Webhooks                | Batch import
         v                        v                         v
+--------+------------------------+-------------------------+-----------+
|                         FastAPI Backend (Python)                      |
|                                                                      |
|  Product Service  |  Recipe Service  |  Discovery Service            |
|  (hybrid search)  |  (recommend)     |  (context pairs)              |
+--------+---------+--------+---------+--------+------------+---------+
         |                  |                   |
         v                  v                   v
+--------+---------+  +----+------+  +---------+----------+
|   PostgreSQL     |  |  Qdrant   |  |  OpenRouter LLM    |
|   (Coolify)      |  |  Cloud    |  |  (shopping agent)  |
+------------------+  +-----------+  +--------------------+
```

---

## Tech Stack

| Layer        | Technology                                      | Purpose                                     |
| ------------ | ----------------------------------------------- | ------------------------------------------- |
| Frontend     | Next.js 16, TypeScript, Tailwind CSS            | Web application                             |
| Backend      | FastAPI, Python 3.11, SQLModel                  | REST API, 20 route modules                  |
| Database     | PostgreSQL 16 (Coolify)                         | Users, households, recipes, meal plans      |
| Vector DB    | Qdrant Cloud                                    | Hybrid search, recommendations, preferences |
| Embeddings   | paraphrase-multilingual-MiniLM-L12-v2 (384-dim) | Multilingual local inference via fastembed  |
| Scraping     | Apify (Crawlee, Playwright, Docling OCR)        | Live retail data from 5 Swiss chains        |
| LLM          | OpenRouter (via Apify proxy)                    | Shopping agent reasoning (Gemini 2.5 Flash) |
| Auth         | Open (no auth required)                         | Dev mode, all routes public                 |
| Landing Page | Astro + Tailwind                                | Marketing site                              |
| Analytics    | PostHog                                         | Server-side event tracking                  |
| Deployment   | Docker Compose on Coolify                       | All services orchestrated                   |

---

## Apify Integration

We built 4 custom Actors and use 1 platform Actor. The pipeline runs on a weekly schedule with webhook-driven ingestion.

| #   | Actor                             | Type     | Description                                                                                                                              |
| --- | --------------------------------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | `nwichter/swiss-grocery-scraper` | Custom   | Scrapes weekly offers from 5 Swiss retailers (Playwright, Docling OCR, BeautifulSoup, API parsing)                                       |
| 2   | `nwichter/shopping-agent`        | Custom   | Agentic shopping assistant: accepts natural language queries, orchestrates scraper + Qdrant + LLM to return personalized recommendations |
| 3   | `nwichter/open-food-facts-swiss` | Custom   | Imports 102k+ Swiss products from Open Food Facts API with allergen mapping, Nutri-Score, and nutritional data                           |
| 4   | `nwichter/recipe-collector`      | Custom   | Collects recipes from RSS feeds (Chefkoch, SRF), RecipeNLG dataset, and 50 curated Swiss classics                                        |
| 5   | `compass/crawler-google-places`   | Platform | Discovers store locations for all 5 retailers via Google Maps (102 stores in Zurich)                                                     |

**Per-retailer scraping strategy:**

| Retailer | Method                        | Data Source                |
| -------- | ----------------------------- | -------------------------- |
| Aldi     | PDF + Docling OCR             | Scene7 CDN weekly prospekt |
| Migros   | Playwright (headless)         | migros.ch/de/offers        |
| Coop     | ePaper JSON API + pdfplumber  | epaper.coopzeitung.ch      |
| Denner   | BeautifulSoup HTML            | denner.ch aktionen         |
| Lidl     | Leaflets API + PDF enrichment | endpoints.leaflets.schwarz |

**Webhook pipeline:**

```
Apify Schedule (Mon/Thu 06:00 UTC)
  --> swiss-grocery-scraper runs
    --> Dataset JSON output
      --> POST /ingest webhook
        --> FastAPI embeds + upserts to PostgreSQL + Qdrant
```

---

## Qdrant Integration

Qdrant is the intelligence layer, not just storage. Three collections power a self-improving system.

| Collection         | Vectors                                       | Purpose                                                                  |
| ------------------ | --------------------------------------------- | ------------------------------------------------------------------------ |
| `products`         | Dense (384-dim) + Sparse (BM25, IDF modifier) | Hybrid search across all retailers with RRF fusion                       |
| `recipes`          | Dense (384-dim)                               | Swipe-driven discovery via Recommend API with positive/negative examples |
| `user_preferences` | Dense (384-dim)                               | Evolving per-user taste vector, updated on every interaction             |

**Qdrant features used:**

| Feature                                      | Application                                                  |
| -------------------------------------------- | ------------------------------------------------------------ |
| Named vectors (dense + sparse)               | Single point stores both semantic and keyword vectors        |
| Reciprocal Rank Fusion                       | Merges dense and sparse prefetch results                     |
| Recommend API                                | Recipe suggestions from liked/disliked swipe history         |
| Discovery API + context pairs                | Progressively refined search regions from accumulated swipes |
| Payload filtering (KEYWORD, FLOAT, DATETIME) | Retailer, price, category, region, expiration filters        |
| Scalar quantization (INT8)                   | Reduced memory with oversampling + rescore                   |
| IDF modifier on sparse vectors               | Better BM25 relevance scoring                                |
| Multi-mode client                            | cloud / docker / local / memory deployment                   |
| query_batch_points                           | Batch hybrid search for ingredient lists (up to 20 queries)  |
| Preference-based re-ranking                  | Blends hybrid scores with user preference similarity         |
| Scroll API                                   | Batch operations and data export                             |

**Self-improving loop:** Every swipe updates the user's preference vector via exponential moving average. Early interactions have strong influence (cold-start bootstrap), later interactions make finer adjustments. After 5+ swipes, the Discovery API activates context pairs that define "near recipes like this, far from recipes like that." Three axes of improvement: user-driven (swipes → preferences), data-driven (weekly scraping expands product space), and interaction-driven (context pairs accumulate for precise search regions).

---

## Data

| Dataset                 | Count     | Source                                       |
| ----------------------- | --------- | -------------------------------------------- |
| Products (base catalog) | 102,000+  | Open Food Facts API (Swiss products)         |
| Weekly offers           | ~370/week | Live scraping from 5 retailers               |
| Recipes                 | 3,500+    | RecipeNLG, RSS feeds, curated Swiss classics |
| Store locations         | 102       | Google Maps (Zurich region)                  |

---

## Project Structure

```
korb-guru/
├── backend/              FastAPI backend + smartcart crawlers
│   ├── src/              API source (routes, services, models, qdrant)
│   ├── alembic/          Database migrations
│   ├── crawler/smartcart/ Standalone scrapers (aldi, coop, denner, lidl, migros)
│   └── Dockerfile
├── frontend/             Next.js web application
│   ├── src/app/          Pages (deals, recipes, lists, compare)
│   └── Dockerfile
├── website/              Astro landing page
│   ├── src/
│   └── Dockerfile
├── apify/                Apify Actors + orchestrator
│   └── actors/           4 custom Actors
├── db/                   PostgreSQL init + seed scripts
├── qdrant/               Qdrant seed scripts
├── docker-compose.yml    backend + frontend + website
├── .env.example
└── README.md
```

---

## Quick Start

```bash
# 1. Clone and configure
git clone https://github.com/NWichter/korb-guru.git
cd korb-guru
cp .env.example .env
# Edit .env with your DATABASE_URL, QDRANT_URL, QDRANT_API_KEY, APIFY_TOKEN

# 2. Start all services
docker compose up --build

# 3. Run migrations
docker compose exec backend uv run alembic upgrade head
```

**Live:**

- Website: [korb.guru](https://korb.guru)
- Web App: [app.korb.guru](https://app.korb.guru)
- API Docs: [api.korb.guru/docs](https://api.korb.guru/docs)

---

## License

[Business Source License 1.1](LICENSE) -- Transitions to AGPL-3.0-or-later four years after each release.
