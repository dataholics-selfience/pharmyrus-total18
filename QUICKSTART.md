# Pharmyrus V5.0 - Quick Start Guide

## 🚀 5-Minute Setup

### Step 1: Clone & Install
```bash
git clone <repo>
cd pharmyrus-v5
pip install -r requirements.txt
playwright install chromium  # Only chromium for quick start
```

### Step 2: Configure
```bash
# Create .env file
cat > .env << EOF
EPO_CONSUMER_KEY=G5wJypxeg0GXEJoMGP37tdK370aKxeMszGKAkD6QaR0yiR5X
EPO_CONSUMER_SECRET=zg5AJ0EDzXdJey3GaFNM8ztMVxHKXRrAihXH93iS5ZAzKPAP
SERPAPI_KEY=optional
GROK_API_KEY=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
USE_FIRESTORE=false
PORT=8000
EOF
```

### Step 3: Run
```bash
python main.py
```

Server starts at `http://localhost:8000`

---

## 📡 First API Call

### cURL Example
```bash
curl -X POST http://localhost:8000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{
    "molecule": "Aspirin",
    "brand_name": "Bayer Aspirin",
    "target_countries": ["BR"],
    "deep_search": false
  }'
```

### Python Example
```python
import requests

response = requests.post(
    "http://localhost:8000/api/v1/search",
    json={
        "molecule": "Darolutamide",
        "brand_name": "Nubeqa",
        "target_countries": ["BR"],
        "deep_search": False
    }
)

data = response.json()
print(f"✅ Found {data['patents']['total']} patents")
print(f"✅ Found {data['research_and_development']['clinical_trials']['total']} trials")
```

### JavaScript Example
```javascript
const response = await fetch('http://localhost:8000/api/v1/search', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    molecule: 'Olaparib',
    brand_name: 'Lynparza',
    target_countries: ['BR'],
    deep_search: false
  })
});

const data = await response.json();
console.log(`✅ Patents: ${data.patents.total}`);
console.log(`✅ Trials: ${data.research_and_development.clinical_trials.total}`);
```

---

## 🎯 Common Use Cases

### Use Case 1: Patent Search Only
```bash
curl -X POST http://localhost:8000/api/v1/patents/search \
  -H "Content-Type: application/json" \
  -d '{"molecule": "Venetoclax"}'
```

**Response:**
```json
{
  "success": true,
  "molecule": "Venetoclax",
  "patents": {
    "total": 89,
    "by_country": {"BR": 45, "US": 25, "EP": 19},
    "results": [...]
  }
}
```

### Use Case 2: Clinical Trials Only
```bash
curl -X POST http://localhost:8000/api/v1/research/clinical-trials \
  -H "Content-Type: application/json" \
  -d '{"molecule": "Niraparib"}'
```

**Response:**
```json
{
  "success": true,
  "molecule": "Niraparib",
  "research_and_development": {
    "clinical_trials": {
      "total": 34,
      "by_phase": {"Phase 3": 12, "Phase 2": 18, "Phase 1": 4},
      "by_status": {"Recruiting": 8, "Completed": 22, "Active": 4},
      "results": [...]
    }
  }
}
```

### Use Case 3: Molecular Data Only
```bash
curl http://localhost:8000/api/v1/molecule/Ixazomib/pubchem
```

**Response:**
```json
{
  "name": "Ixazomib",
  "cas_number": "1201902-80-8",
  "dev_codes": ["MLN-9708", "MLN2238"],
  "synonyms": ["Ixazomib citrate", "Ninlaro", ...],
  "molecular_formula": "C14H19BCl2N2O4",
  "molecular_weight": 361.0
}
```

---

## 🧪 Testing

### Run All Tests
```bash
python tests/integration_test.py
```

### Test Individual Components

**SuperCrawler:**
```python
from src.core.super_crawler import SuperCrawler

async with SuperCrawler() as crawler:
    result = await crawler.crawl("https://httpbin.org/html")
    print(result.success, result.strategy_used)
```

**WO Search:**
```python
from src.crawlers.wo_search import WONumberSearcher

searcher = WONumberSearcher(super_crawler=crawler)
result = await searcher.search_wo_numbers("Aspirin", [], None, None)
print(f"Found {len(result.wo_numbers)} WO numbers")
```

**Clinical Trials:**
```python
from src.crawlers.clinicaltrials_crawler import ClinicalTrialsGovCrawler

ct = ClinicalTrialsGovCrawler(super_crawler=crawler)
trials = await ct.search_by_molecule("Aspirin", max_results=10)
print(f"Found {len(trials)} trials")
```

---

## 🐳 Docker Quick Start

### Build & Run
```bash
# Build
docker build -t pharmyrus-v5 .

# Run
docker run -d \
  --name pharmyrus \
  -p 8000:8000 \
  -e EPO_CONSUMER_KEY=xxx \
  -e EPO_CONSUMER_SECRET=xxx \
  pharmyrus-v5

# Check logs
docker logs pharmyrus

# Test
curl http://localhost:8000/health
```

### Stop & Clean
```bash
docker stop pharmyrus
docker rm pharmyrus
```

---

## 🚂 Railway Quick Deploy

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Initialize project
railway init

# Deploy
railway up

# Set secrets
railway variables set EPO_CONSUMER_KEY=xxx
railway variables set EPO_CONSUMER_SECRET=xxx

# Get URL
railway domain
```

Your app is now live! 🎉

---

## 📊 Monitoring

### Health Check
```bash
# Should return {"status":"healthy"}
curl http://localhost:8000/health
```

### System Stats
```bash
# Shows SuperCrawler statistics
curl http://localhost:8000/api/v1/stats
```

### Debug Failed URLs
```bash
# Shows URLs that failed crawling
curl http://localhost:8000/api/v1/debug/failed-urls
```

---

## 🔍 Troubleshooting

### Problem: "Orchestrator not initialized"
**Solution:** Wait 10-15s after startup for initialization to complete.

### Problem: "EPO authentication failed"
**Solution:** Check `EPO_CONSUMER_KEY` and `EPO_CONSUMER_SECRET` are correct.

### Problem: "Crawler blocked (403)"
**Solution:** System auto-retries with different strategies. Check logs for final status.

### Problem: "Timeout errors"
**Solution:** Increase timeouts in `.env`:
```bash
CRAWLER_TIMEOUT=90
REQUEST_TIMEOUT=120
```

### Problem: "No patents found"
**Solution:** 
1. Check molecule name spelling
2. Try with dev codes or CAS number
3. Enable `deep_search: true` for broader results

### Problem: "High memory usage"
**Solution:** Reduce parallel workers:
```bash
# In main.py, change:
uvicorn.run("main:app", workers=1)  # Instead of 2
```

---

## 📚 Example Molecules

Good molecules for testing (known to have many patents):

| Molecule | Dev Code | CAS | Expected BR Patents |
|----------|----------|-----|---------------------|
| Darolutamide | ODM-201 | 1297538-32-9 | 55+ |
| Olaparib | AZD-2281 | 763113-22-0 | 78+ |
| Venetoclax | ABT-199 | 1257044-40-8 | 65+ |
| Ixazomib | MLN-9708 | 1201902-80-8 | 45+ |
| Niraparib | MK-4827 | 1038915-60-4 | 52+ |

---

## 🎓 Learning Resources

1. **API Documentation:** `DOCUMENTATION_V5.md`
2. **Architecture:** `ARCHITECTURE_V5.md`
3. **Source Code:** Heavily commented for learning
4. **Integration Tests:** `tests/integration_test.py`

---

## 🆘 Getting Help

1. Check logs: `docker logs pharmyrus` or console output
2. Review `DOCUMENTATION_V5.md` for detailed info
3. Run integration tests to isolate issues
4. Check debug logs: `./debug_logs/`
5. Contact support: daniel@genoi.com.br

---

## 🎯 Next Steps

After successful setup:

1. ✅ Test with known molecules (Darolutamide, Olaparib)
2. ✅ Compare results with Cortellis baseline
3. ✅ Integrate with frontend dashboard
4. ✅ Set up monitoring/alerting
5. ✅ Enable Firestore for auto-healing
6. ✅ Configure CI/CD pipeline

---

## 🔐 Security Best Practices

1. **Never commit .env files**
```bash
echo ".env" >> .gitignore
```

2. **Use secrets management in production**
- Railway: Use Railway's secret management
- GCP: Use Secret Manager
- AWS: Use AWS Secrets Manager

3. **Rotate API keys regularly**
- EPO keys: Quarterly
- AI keys: Monthly

4. **Enable rate limiting in production**
```python
# Add to main.py
from slowapi import Limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
```

---

## 📈 Performance Tips

1. **Use deep_search=false for faster results**
2. **Cache PubChem results** (implemented in SuperCrawler)
3. **Use SerpAPI for better WO search** (optional, costs money)
4. **Run on machines with good internet** (crawler benefits from bandwidth)
5. **Use Redis for distributed caching** (future enhancement)

---

Happy searching! 🚀
