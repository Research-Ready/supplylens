# UC4 — Software Potentially Needed

> Pipeline: Supply Chain Visualization / Knopenkoning
> Last updated: 2026-09-28

## What this pipeline does

Given a product SKU or company name, the pipeline traverses its full supply chain backwards: who supplies this, who supplies the supplier, where do raw materials come from. Browserless scrapes JS-rendered supplier websites. Unstructured and Tika extract content from PDFs and procurement documents. LLM infers missing links. Everything gets stored in Neo4j as a directed graph. LangGraph orchestrates the multi-step enrichment agent. Superset and Metabase render SQL dashboards. n8n schedules periodic refreshes. Qdrant enables semantic search over supplier documents.

---

## Current services (confirmed in use)

| Service | Container | IP:Port | Role |
|---------|-----------|---------|------|
| Neo4j | CT114 | 10.0.1.114:7687 | Supply chain graph (primary store) |
| LangGraph | CT119 | 10.0.1.119:8000 | Multi-step enrichment agent |
| Browserless (prod) | CT400 | 10.0.5.100:3500 | JS-rendered page scraping |
| Browserless (acc) | CT306 | 10.0.3.106:3500 | Fallback scraper |
| Unstructured | CT117 | 10.0.1.117:8000 | HTML/PDF text extraction |
| Tika | CT115 | 10.0.1.115:9998 | Binary doc parsing (XLS, DOC) |
| Qdrant | CT102 | 10.0.1.102:6333 | Supplier doc vector search |
| LiteLLM | CT205 | 10.0.2.205:4000 | LLM: infer supply chain links |
| PostgreSQL | CT100 | 10.0.1.100:5432 | Structured entity table (knopenkonings DB) |
| Superset | CT206 | 10.0.2.206:8088 | SQL dashboards |
| Metabase | CT202 | 10.0.2.202:3000 | Alternative dashboards |
| n8n | CT104 | 10.0.1.104:5678 | Scheduled refresh pipeline |
| Langfuse | CT112 | 10.0.1.112:3000 | LLM call tracing |
| MongoDB | CT121 | 10.0.1.121:27017 | Raw scraped data store |
| Kotaemon | CT120 | 10.0.1.120:8501 | RAG chat over supplier PDFs |
| Graphiti | CT124 | 10.0.1.124:8000 | Temporal knowledge graph memory |

---

## Likely additions (stack services not yet wired in)

| Service | Container | Reason |
|---------|-----------|--------|
| CrewAI | CT308 | Multi-agent deep research on specific suppliers — runs in parallel with LangGraph |
| Docling | CT107 | Better PDF extraction than Tika for annual reports with complex layouts |
| SearXNG | CT105 | Agent web search for discovering suppliers not yet in the graph |
| Perplexica | CT133 | AI-powered supplier search with LLM-ranked results |
| Crawl4AI | CT134 | Recursive crawling of supplier websites (multiple pages, not just homepage) |
| Elasticsearch | CT204 | Full-text search over raw scraped supplier content alongside Qdrant vector search |
| Weaviate | CT137 | Hybrid BM25+vector search over supplier documents |
| Airflow | CT207 | More robust scheduling than n8n for complex multi-step refresh DAGs |
| BookStack | CT201 | Document supply chain methodology, data dictionaries, schema decisions |
| OpenCTI | CT403 | Geopolitical risk intelligence — flag suppliers in conflict zones or sanctioned territories |
| TheHive | CT402 | Track supply chain disruption incidents (port closures, sanctions, natural disasters) |
| OpenBB | CT408 | Financial data terminal — supplier financial health, public company risk scores |
| Storm | CT406 | Deep research agents for autonomous supplier investigation |
| Skyvern | CT407 | AI-driven browser automation for sites with CAPTCHAs Browserless can't handle |
| Deerflow | CT404 | Research pipeline alternative to manual LangGraph research steps |

---

## Speculative additions (external APIs / tooling)

| Service | Why it fits UC4 |
|---------|----------------|
| **GLEIF API** (free) | Legal Entity Identifier data — standardized company IDs with ownership structure. Links subsidiaries to parents. |
| **OpenCorporates API** (free tier) | Company registry data from 130+ countries — disambiguate supplier names, find registered addresses. |
| **Trade Map (ITC/UN Comtrade)** (free) | Bilateral trade flow data — who exports steel from Germany to Netherlands. Evidence for supply chain links. |
| **Import Yeti / ImportGenius** | US bill of lading records — actual documented shipments between supplier pairs. |
| **EDGAR (SEC)** (free) | US public company 10-K filings name top suppliers by revenue. High-signal for Tier 1. |
| **Dun & Bradstreet / Creditsafe** | Commercial supplier risk scores, financial health, payment track record. |
| **Panjiva (S&P Global)** | Customs records database — documented shipments worldwide (commercial). |
| **Diffbot API** | Structured data extraction from supplier websites — better than Unstructured for schema-mapped data. |
| **ScraperAPI / Zyte** | Managed scraping proxy with rotating IPs, CAPTCHA solving — handles sites Browserless can't. |
| **Google Maps API** | Geocode supplier addresses → plot on world map in Superset; distance/logistics risk. |
| **UN LOCODE** (free) | Standard port/city codes — normalize location data across suppliers. |
| **Clearbit / Apollo.io** | Enrich company data (size, industry, tech stack) from domain name. |
| **SerpAPI** | Google News search for supplier disruptions, recalls, financial news. |
| **OpenStreetMap / Nominatim** (free) | Free geocoding alternative to Google Maps. |
| **NeoDash** (already in stack) | Neo4j native dashboard builder — render the supply chain graph visually without Superset. CT130 10.0.1.130. |
| **Sigma.js / vis-network** | Client-side JS graph visualization — embed in BookStack or generate as HTML artifact. |

---

## Priority recommendations

1. **Wire in NeoDash (CT130)** — it is already deployed and renders Neo4j graph data natively. Faster path to a visual supply chain map than Superset + JDBC connector.
2. **Add GLEIF + OpenCorporates APIs** to the LangGraph agent's tool set — free, high-signal company identity data that fills gaps LLM inference gets wrong.
3. **Add Crawl4AI (CT134)** for multi-page supplier site crawls — the current Browserless single-page scrape misses linked pages (supplier lists, annual report PDFs).
4. **Add OpenCTI (CT403)** geopolitical risk feed — automatic `GEOPOLITICAL_RISK` flagging based on sanctions lists and conflict zone data.
5. **Add Skyvern (CT407)** as a CAPTCHA-handling fallback when Browserless fails on protected supplier sites.
