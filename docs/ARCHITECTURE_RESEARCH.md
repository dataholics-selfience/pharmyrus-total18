# Patent Intelligence System - Best Practices Research

## 🔬 Industry Leaders Analysis

### 1. **Cortellis (Clarivate)**
**Architecture:**
- Multi-source aggregation (USPTO, EPO, WIPO, JPO, CNIPA, INPI)
- Family grouping algorithm (INPADOC family ID)
- Citation network analysis
- Legal status tracking (active/expired/abandoned)
- Assignee normalization (company name variants)

**Key Features:**
- 115M+ patent records
- 55M+ patent families
- Real-time legal status updates
- Prior art search with semantic analysis
- Freedom-to-operate (FTO) assessment
- Competitive intelligence dashboards

**Technical Stack (inferred):**
- Distributed crawlers (Java/Scala)
- Graph database (Neo4j-like) for citations
- ElasticSearch for full-text search
- ML models for classification (CPC/IPC prediction)
- API rate limiting and caching

---

### 2. **Lens.org (Cambia)**
**Architecture:**
- Open patent data aggregation
- ScholarlyWorks integration (academic papers ↔ patents)
- BLAST-like sequence search for biotech patents
- Citation network visualization

**Key Features:**
- 135M+ patent records (free access)
- Family clustering
- Citation analysis
- Sequence search (DNA/protein)
- Export to CSV/JSON/RIS

**Technical Insights:**
- Python-based crawlers
- PostgreSQL + MongoDB hybrid
- Redis caching layer
- Celery task queue for async processing
- Docker containerization

---

### 3. **PatentSight (LexisNexis)**
**Architecture:**
- Patent value scoring (Patent Asset Index)
- Technology lifecycle analysis
- Competitive landscape mapping
- Forward/backward citations

**Unique Features:**
- Competitive Impact (CI) score
- Technology Relevance score
- Market Coverage analysis
- White space identification

---

### 4. **Google Patents**
**Architecture:**
- Massive parallel crawling (Googlebot for patents)
- Machine translation (70+ languages)
- Prior art finder (semantic search)
- Worldwide applications tracking

**Technical Stack:**
- Bigtable for storage
- Spanner for metadata
- TensorFlow for ML (classification, OCR)
- gRPC APIs
- CDN for PDF delivery

---

## 🏗️ Best Practices for Pharmyrus v5

### **Core Architecture Principles**

#### 1. **Crawler Design**
```
┌─────────────────────────────────────────┐
│  Crawler Pool (Async + Parallel)       │
│  ├── INPI (Puppeteer/Playwright)       │
│  ├── Google Patents (Playwright)        │
│  ├── EPO (OPS API + Selenium fallback) │
│  ├── WIPO (Selenium + AI parser)        │
│  └── PubChem (REST API)                 │
└─────────────────────────────────────────┘
        ↓ (async tasks)
┌─────────────────────────────────────────┐
│  Task Queue (Celery/Redis)              │
│  - Rate limiting per source             │
│  - Retry with exponential backoff       │
│  - Deduplication at task level          │
└─────────────────────────────────────────┘
        ↓ (parsed data)
┌─────────────────────────────────────────┐
│  Data Pipeline                          │
│  ├── Raw extraction                     │
│  ├── Normalization (dates, names)       │
│  ├── Deduplication (fuzzy matching)     │
│  ├── Family grouping                    │
│  └── Quality scoring                    │
└─────────────────────────────────────────┘
        ↓ (enriched data)
┌─────────────────────────────────────────┐
│  Storage Layer                          │
│  ├── PostgreSQL (metadata, relations)   │
│  ├── MongoDB (full documents)           │
│  └── Redis (caching, sessions)          │
└─────────────────────────────────────────┘
```

#### 2. **Data Quality Scoring Algorithm**
```python
quality_score = (
    legal_status_known * 10 +
    abstract_present * 15 +
    inventors_complete * 10 +
    citations_present * 10 +
    ipc_cpc_present * 15 +
    family_complete * 20 +
    brazil_specific * 20 +
    priority_data_complete * 10
) / 110 * 100  # Normalize to 0-100
```

#### 3. **Family Grouping Strategy**
- **INPADOC Family ID** (EPO standard)
- **Simple Family** (same priority)
- **Extended Family** (common inventors + similar claims)
- **Technology Family** (IPC/CPC clustering)

**Algorithm:**
```python
1. Group by priority date + priority number
2. Merge families with shared members (>50% overlap)
3. Add citations as family links
4. Cluster by TF-IDF similarity of claims/abstract
```

#### 4. **Patent Number Normalization**
```python
# Handles all formats:
BR112012008823B8 → BR112012008823-B8
WO2011080351 → WO2011/080351
EP2555778A1 → EP2555778-A1
US20130131134 → US-20130131134-A1

# Deduplication key:
normalize_key = f"{country_code}-{doc_number}"
```

#### 5. **Rate Limiting Best Practices**
```python
rate_limits = {
    "google_patents": (100, "hour"),    # 100 req/hour
    "epo_ops": (4000, "week"),          # 4000 req/week
    "inpi": (60, "minute"),             # 60 req/minute (polite)
    "pubchem": (5, "second"),           # 5 req/second
    "serpapi": (100, "month", "per_key") # 100/month/key (9 keys = 900)
}

# Implement with Token Bucket algorithm
```

#### 6. **Error Handling & Resilience**
```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type((Timeout, ConnectionError))
)
async def crawl_with_retry(url):
    # Crawler logic
    pass

# Circuit breaker pattern for failing sources
if error_rate > 50% in last_100_requests:
    circuit_open = True
    wait_before_retry = 300  # 5 minutes
```

#### 7. **Caching Strategy**
```python
cache_rules = {
    "pubchem_synonyms": "24h",          # Rarely changes
    "epo_token": "1h",                  # Token expires
    "google_patents_wo": "7d",          # WO numbers stable
    "inpi_patent_details": "24h",       # Daily updates
    "cortellis_baseline": "30d"         # Monthly refresh
}
```

#### 8. **AI/ML Enhancements**
```python
# Use Grok for:
1. Field detection (dynamic forms)
2. PDF text extraction (when OCR needed)
3. Classification (patent type prediction)
4. Entity extraction (inventors, assignees)
5. Prior art relevance scoring

# Use embeddings for:
1. Semantic search (find similar patents)
2. Family clustering (when no formal link)
3. Technology trend analysis
```

#### 9. **Monitoring & Observability**
```python
metrics = {
    "crawler_success_rate": gauge,
    "patents_per_minute": counter,
    "api_latency": histogram,
    "cache_hit_ratio": gauge,
    "quality_score_avg": gauge,
    "cortellis_match_rate": gauge
}

# Log everything
logger.info({
    "event": "patent_found",
    "source": "inpi",
    "molecule": "darolutamide",
    "patent_id": "BR112012008823",
    "quality_score": 78.5,
    "processing_time_ms": 1234
})
```

#### 10. **API Design (FastAPI)**
```python
# Endpoints
POST /api/v1/search
  - molecule_name
  - synonyms (optional)
  - target_countries (default: ["BR"])
  - deep_search (bool)
  - include_regulatory (bool)

GET /api/v1/molecule/{name}
  - Cached comprehensive report

GET /api/v1/compare/{name}/cortellis
  - Comparison with baseline

WS /api/v1/search/stream
  - Real-time results streaming

# Response format (streaming)
{
  "event": "phase_start",
  "phase": "pubchem_lookup",
  "timestamp": "2025-12-18T..."
}
{
  "event": "patents_found",
  "source": "inpi",
  "count": 12,
  "patents": [...]
}
{
  "event": "phase_complete",
  "phase": "all",
  "summary": {...}
}
```

---

## 🚀 Implementation Priorities

### **MVP (2-3 hours)**
1. ✅ Cortellis baseline extractor
2. 🔄 INPI crawler integration (Playwright Python)
3. 🔄 PubChem client (with fallback to cached data)
4. 🔄 Basic orchestrator (sequential)
5. 🔄 JSON output formatter

### **v5.0 Production (1 day)**
1. Google Patents WO searcher (Playwright)
2. EPO OPS client (token management)
3. Family grouping algorithm
4. Quality scoring engine
5. FastAPI endpoints
6. Caching layer (Redis)
7. Async task queue

### **v5.1 Advanced (2-3 days)**
1. ANVISA scraper
2. FDA/EMA/DrugBank
3. Citation network analysis
4. Grok AI field detection
5. WebSocket streaming
6. Monitoring dashboard
7. Docker deployment

---

## 📊 Performance Targets

- **Search time:** <5min (default), <15min (deep)
- **BR patent recall:** >85% vs Cortellis
- **Quality score:** >70 average
- **API uptime:** >99.5%
- **Cache hit rate:** >60%
- **Cost:** <$100/month

---

## 🔐 Security & Compliance

- INPI credentials encryption (Fernet)
- Rate limiting per user/API key
- GDPR compliance (no PII storage)
- Audit logs (all searches)
- IP allowlist for production API
