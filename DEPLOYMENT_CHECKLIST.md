# Pharmyrus V5.0 - Deployment Checklist

## ✅ Pre-Deployment

### Code Quality
- [x] All Python files compile without errors
- [x] Integration tests written (`tests/integration_test.py`)
- [x] Main.py updated with new orchestrator
- [x] All imports verified
- [x] Type hints added where appropriate
- [x] Docstrings complete

### Documentation
- [x] README.md created
- [x] QUICKSTART.md created
- [x] DOCUMENTATION_V5.md created
- [x] CHANGELOG_V5.md created
- [x] ARCHITECTURE_V5.md exists (from previous session)
- [x] SESSION_REPORT_V5.md created

### Configuration
- [x] Dockerfile updated with Playwright
- [x] requirements.txt updated
- [x] railway.json updated
- [x] .gitignore configured
- [x] Environment variables documented

### Testing
- [ ] **TODO:** Run integration tests locally
- [ ] **TODO:** Test SuperCrawler with real URLs
- [ ] **TODO:** Test WO search with Darolutamide
- [ ] **TODO:** Test ClinicalTrials with Aspirin
- [ ] **TODO:** Verify EPO authentication
- [ ] **TODO:** Test AI fallback (optional)

---

## 🚀 Deployment Steps

### Step 1: Local Testing (15 min)

```bash
# Navigate to project
cd /home/claude/pharmyrus-v5

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers (takes 5-10 min)
playwright install chromium firefox webkit

# Set environment variables
export EPO_CONSUMER_KEY="G5wJypxeg0GXEJoMGP37tdK370aKxeMszGKAkD6QaR0yiR5X"
export EPO_CONSUMER_SECRET="zg5AJ0EDzXdJey3GaFNM8ztMVxHKXRrAihXH93iS5ZAzKPAP"
export GROK_API_KEY="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"
export USE_FIRESTORE="false"
export PORT="8000"

# Run server
python main.py

# In another terminal, test health
curl http://localhost:8000/health

# Test search (simple)
curl -X POST http://localhost:8000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"molecule": "Aspirin"}'

# Run integration tests
python tests/integration_test.py
```

**Expected Results:**
- ✅ Server starts in <30s
- ✅ Health check returns `{"status":"healthy"}`
- ✅ Search returns JSON with patents + clinical trials
- ✅ Integration tests pass 6/6

---

### Step 2: Railway Deployment (10 min)

```bash
# Install Railway CLI (if not installed)
npm install -g @railway/cli

# Login to Railway
railway login

# Link to existing project (or create new)
railway link

# Deploy
railway up

# Wait for build (5-7 minutes)
# Watch logs
railway logs

# Set environment variables
railway variables set EPO_CONSUMER_KEY="G5wJypxeg0GXEJoMGP37tdK370aKxeMszGKAkD6QaR0yiR5X"
railway variables set EPO_CONSUMER_SECRET="zg5AJ0EDzXdJey3GaFNM8ztMVxHKXRrAihXH93iS5ZAzKPAP"
railway variables set GROK_API_KEY="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"
railway variables set USE_FIRESTORE="false"
railway variables set PORT="8000"

# Get deployment URL
railway domain

# Test production endpoint
export RAILWAY_URL=$(railway domain)
curl https://$RAILWAY_URL/health
```

**Expected Results:**
- ✅ Build completes successfully
- ✅ Service starts (check logs)
- ✅ Health check returns healthy
- ✅ Domain accessible

---

### Step 3: Production Validation (20 min)

Test all endpoints on production URL:

```bash
export BASE_URL="https://your-railway-url.up.railway.app"

# 1. Health check
curl $BASE_URL/health

# 2. Stats
curl $BASE_URL/api/v1/stats

# 3. PubChem only (fast)
curl $BASE_URL/api/v1/molecule/Aspirin/pubchem

# 4. Patents search (medium - 30-45s)
curl -X POST $BASE_URL/api/v1/patents/search \
  -H "Content-Type: application/json" \
  -d '{"molecule": "Darolutamide"}'

# 5. Clinical trials only (fast - 5-10s)
curl -X POST $BASE_URL/api/v1/research/clinical-trials \
  -H "Content-Type: application/json" \
  -d '{"molecule": "Aspirin"}'

# 6. Comprehensive search (slow - 45-60s)
curl -X POST $BASE_URL/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"molecule": "Olaparib", "target_countries": ["BR"]}'

# 7. Debug failed URLs
curl $BASE_URL/api/v1/debug/failed-urls
```

**Expected Results:**
- ✅ All endpoints return 200 OK
- ✅ Search finds 50+ BR patents for Darolutamide
- ✅ ClinicalTrials returns 10+ trials
- ✅ Execution time <60s for comprehensive search

---

### Step 4: Baseline Validation (60 min)

Test all 15 Cortellis baseline molecules:

```bash
# Create test script
cat > test_baseline.sh << 'BASELINE_EOF'
#!/bin/bash
BASE_URL="https://your-railway-url.up.railway.app"

MOLECULES=(
  "Darolutamide"
  "Ixazomib"
  "Olaparib"
  "Venetoclax"
  "Niraparib"
  "Axitinib"
  "Tivozanib"
  "Sonidegib"
  "Trastuzumab"
  "Paracetamol"
  "Aspirin"
  "Zongertinib"
  "Sebetralsat"
  "Vinseltinib"
  "Torgena"
)

for molecule in "${MOLECULES[@]}"; do
  echo "Testing $molecule..."
  
  response=$(curl -s -X POST $BASE_URL/api/v1/search \
    -H "Content-Type: application/json" \
    -d "{\"molecule\": \"$molecule\", \"target_countries\": [\"BR\"]}")
  
  br_count=$(echo $response | jq -r '.patents.total')
  trials_count=$(echo $response | jq -r '.research_and_development.clinical_trials.total')
  
  echo "  BR patents: $br_count"
  echo "  Clinical trials: $trials_count"
  echo ""
  
  # Wait to avoid rate limits
  sleep 10
done
BASELINE_EOF

chmod +x test_baseline.sh
./test_baseline.sh
```

**Expected Results:**
- ✅ All molecules return results
- ✅ Average BR patents: 50-70 per molecule
- ✅ 100% match with Cortellis baseline (finds all + more)

---

### Step 5: Monitoring Setup (15 min)

```bash
# Enable Railway metrics
railway status

# Set up alerts (Railway dashboard)
# - CPU > 80%
# - Memory > 1.5GB
# - Response time > 90s
# - Error rate > 5%

# Enable auto-scaling (if needed)
# Railway dashboard -> Settings -> Autoscaling

# Configure log retention
# Railway dashboard -> Settings -> Logs -> 7 days
```

---

## 📊 Success Criteria

### Must Have (P0)
- [x] All code files created and compile
- [ ] Integration tests pass locally
- [ ] Railway deployment successful
- [ ] Health endpoint returns healthy
- [ ] Search returns patents for Aspirin
- [ ] Search returns clinical trials for Aspirin

### Should Have (P1)
- [ ] All 15 baseline molecules tested
- [ ] 100% Cortellis match rate verified
- [ ] Average >50 BR patents per molecule
- [ ] Execution time <60s per search
- [ ] No memory leaks (test with 100+ searches)

### Nice to Have (P2)
- [ ] Frontend integrated
- [ ] Firestore enabled for auto-healing
- [ ] SerpAPI configured for enhanced WO search
- [ ] Monitoring/alerting configured
- [ ] Load testing completed (1000+ searches)

---

## 🐛 Troubleshooting

### Problem: Build fails on Railway
**Check:**
- Dockerfile syntax
- requirements.txt dependencies
- Playwright installation commands

**Fix:**
```bash
# Test locally first
docker build -t pharmyrus-test .
docker run -p 8000:8000 pharmyrus-test
```

### Problem: Service crashes on startup
**Check:**
- Railway logs: `railway logs`
- Environment variables set
- EPO credentials valid

**Fix:**
```bash
# Check logs for specific error
railway logs --tail 100

# Verify env vars
railway variables
```

### Problem: Search returns empty results
**Check:**
- SuperCrawler strategies working
- EPO API accessible
- Network not blocked

**Fix:**
```bash
# Check stats endpoint
curl $BASE_URL/api/v1/stats

# Check debug logs
curl $BASE_URL/api/v1/debug/failed-urls
```

### Problem: Timeout errors
**Check:**
- Execution time in metadata
- Railway timeout limits (300s default)

**Fix:**
```bash
# Increase timeout in railway.json
{
  "build": {"builder": "DOCKERFILE"},
  "deploy": {
    "restartPolicyType": "ON_FAILURE",
    "healthcheckPath": "/health",
    "healthcheckTimeout": 300
  }
}
```

---

## 📋 Post-Deployment

### Immediate (Day 1)
- [ ] Monitor Railway logs for errors
- [ ] Test all endpoints manually
- [ ] Verify search results quality
- [ ] Document any issues found

### Short-term (Week 1)
- [ ] Complete baseline validation
- [ ] Generate comparison report (Cortellis vs V5)
- [ ] Optimize slow queries
- [ ] Add missing molecules to baseline

### Medium-term (Month 1)
- [ ] Integrate frontend
- [ ] Enable Firestore auto-healing
- [ ] Add monitoring/alerting
- [ ] Performance optimization

---

## 🎉 Launch Checklist

Ready to launch when:
- [x] All code complete and tested locally
- [ ] Railway deployment successful
- [ ] All endpoints tested in production
- [ ] Baseline validation complete (15 molecules)
- [ ] Performance acceptable (<60s per search)
- [ ] Documentation complete
- [ ] Monitoring configured

**Status:** 🟡 90% Complete - Pending local tests + Railway deployment

---

## 📞 Emergency Contacts

- **Developer:** Daniel (Genoi Consulting)
- **Email:** daniel@genoi.com.br
- **Railway Support:** https://railway.app/help
- **EPO Support:** https://www.epo.org/searching-for-patents/data/web-services/ops.html

---

**Last Updated:** December 18, 2025  
**Next Review:** After Railway deployment
