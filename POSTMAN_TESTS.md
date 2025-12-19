# 🧪 Pharmyrus V5.0 - Postman Test Collection

## 📋 Variáveis de Ambiente

Configure estas variáveis no Postman (Environment):

```
BASE_URL = https://your-app.up.railway.app
# OU para local:
BASE_URL = http://localhost:8000
```

---

## 🔍 COLLECTION DE TESTES

### 1. Health Check ⚡ (1 segundo)

**Request:**
```http
GET {{BASE_URL}}/health
```

**Resposta Esperada:**
```json
{
  "status": "healthy",
  "timestamp": "2025-12-18T18:00:00.000000",
  "version": "5.0.0",
  "services": {
    "orchestrator": "initialized",
    "debug_logger": "ready",
    "ai_fallback": "ready"
  }
}
```

**Status:** `200 OK`

---

### 2. System Stats 📊 (1 segundo)

**Request:**
```http
GET {{BASE_URL}}/api/v1/stats
```

**Resposta Esperada:**
```json
{
  "uptime_seconds": 3600,
  "total_searches": 150,
  "cache_hits": 45,
  "cache_misses": 105,
  "success_rate": 0.95,
  "average_response_time_ms": 35000,
  "services_status": {
    "orchestrator": "healthy",
    "debug_logger": "healthy",
    "ai_fallback": "healthy"
  }
}
```

**Status:** `200 OK`

---

### 3. PubChem Data 🧪 (2-3 segundos)

**Request:**
```http
GET {{BASE_URL}}/api/v1/molecule/Aspirin/pubchem
```

**Resposta Esperada:**
```json
{
  "success": true,
  "molecule": "Aspirin",
  "data": {
    "cid": 2244,
    "iupac_name": "2-acetoxybenzoic acid",
    "molecular_formula": "C9H8O4",
    "molecular_weight": 180.16,
    "canonical_smiles": "CC(=O)OC1=CC=CC=C1C(=O)O",
    "synonyms": ["Aspirin", "Acetylsalicylic acid", "ASA"],
    "dev_codes": ["ASA", "AAS"],
    "cas_number": "50-78-2"
  }
}
```

**Status:** `200 OK`

---

### 4. Busca Completa - Aspirin 🔍 (30-45 segundos)

**Request:**
```http
POST {{BASE_URL}}/api/v1/search
Content-Type: application/json

{
  "molecule": "Aspirin",
  "brand_name": "Aspirina",
  "target_countries": ["BR"],
  "deep_search": false
}
```

**Resposta Esperada:**
```json
{
  "success": true,
  "molecule": "Aspirin",
  "brand_name": "Aspirina",
  "execution_time_seconds": 38.5,
  "patents": {
    "total": 85,
    "by_country": {
      "BR": 85
    },
    "by_source": {
      "google_patents": 35,
      "epo": 40,
      "inpi_crawler": 10
    },
    "quality_score": 78.5,
    "results": [
      {
        "publication_number": "BR112015001234A2",
        "title": "Pharmaceutical composition comprising acetylsalicylic acid",
        "abstract": "The invention relates to...",
        "assignee": "Bayer AG",
        "filing_date": "2013-06-15",
        "publication_date": "2015-02-20",
        "patent_type": "COMPOSITION",
        "quality_score": 85.0,
        "relevance_score": 90.0,
        "source": "google_patents",
        "link": "https://patents.google.com/patent/BR112015001234A2"
      }
    ]
  },
  "research_and_development": {
    "clinical_trials": {
      "total": 245,
      "by_phase": {
        "Phase 1": 50,
        "Phase 2": 80,
        "Phase 3": 90,
        "Phase 4": 25
      },
      "by_status": {
        "Recruiting": 30,
        "Active": 50,
        "Completed": 150,
        "Terminated": 15
      },
      "results": [
        {
          "nct_id": "NCT01234567",
          "title": "Safety and Efficacy of Aspirin in Cardiovascular Prevention",
          "status": "Completed",
          "phase": "Phase 3",
          "start_date": "2015-01-01",
          "completion_date": "2018-12-31",
          "sponsor": "Bayer",
          "conditions": ["Cardiovascular Disease"],
          "interventions": ["Aspirin 100mg daily"],
          "locations": ["Brazil", "USA"],
          "link": "https://clinicaltrials.gov/study/NCT01234567"
        }
      ]
    }
  },
  "metadata": {
    "search_id": "search_20251218_180000_aspirin",
    "timestamp": "2025-12-18T18:00:00",
    "sources_queried": ["pubchem", "google_patents", "epo", "inpi", "clinicaltrials"],
    "sources_success": 5,
    "sources_failed": 0
  }
}
```

**Status:** `200 OK`

---

### 5. Apenas Patentes - Darolutamide 📄 (40-50 segundos)

**Request:**
```http
POST {{BASE_URL}}/api/v1/patents/search
Content-Type: application/json

{
  "molecule": "Darolutamide",
  "brand_name": "Nubeqa",
  "target_countries": ["BR"],
  "deep_search": true
}
```

**Resposta Esperada:**
```json
{
  "success": true,
  "molecule": "Darolutamide",
  "brand_name": "Nubeqa",
  "execution_time_seconds": 45.2,
  "patents": {
    "total": 55,
    "by_country": {
      "BR": 55
    },
    "by_source": {
      "google_patents": 20,
      "epo": 25,
      "inpi_crawler": 10
    },
    "by_patent_type": {
      "COMPOSITION": 15,
      "FORMULATION": 10,
      "CRYSTALLINE": 8,
      "PROCESS": 12,
      "MEDICAL_USE": 10
    },
    "quality_score": 85.5,
    "results": [...]
  }
}
```

**Status:** `200 OK`

---

### 6. Apenas Clinical Trials - Olaparib 🧬 (5-8 segundos)

**Request:**
```http
POST {{BASE_URL}}/api/v1/research/clinical-trials
Content-Type: application/json

{
  "molecule": "Olaparib",
  "brand_name": "Lynparza"
}
```

**Resposta Esperada:**
```json
{
  "success": true,
  "molecule": "Olaparib",
  "brand_name": "Lynparza",
  "execution_time_seconds": 6.8,
  "research_and_development": {
    "clinical_trials": {
      "total": 320,
      "by_phase": {
        "Early Phase 1": 10,
        "Phase 1": 45,
        "Phase 2": 120,
        "Phase 3": 130,
        "Phase 4": 15
      },
      "by_status": {
        "Recruiting": 50,
        "Active": 80,
        "Completed": 180,
        "Terminated": 10
      },
      "results": [...]
    }
  }
}
```

**Status:** `200 OK`

---

### 7. Debug - Failed URLs 🐛 (Instantâneo)

**Request:**
```http
GET {{BASE_URL}}/api/v1/debug/failed-urls?limit=10
```

**Resposta Esperada:**
```json
{
  "total_failed": 25,
  "failed_urls": [
    {
      "url": "https://example.com/patent/BR123",
      "error": "Connection timeout",
      "timestamp": "2025-12-18T17:30:00",
      "attempts": 3,
      "last_strategy": "HTTPX_STEALTH"
    }
  ]
}
```

**Status:** `200 OK`

---

## 🧪 TESTES PROGRESSIVOS (Recomendado)

### Nível 1: Básico (5 minutos)
1. ✅ Health Check
2. ✅ System Stats
3. ✅ PubChem - Aspirin

### Nível 2: Intermediário (15 minutos)
4. ✅ Busca Completa - Aspirin (simples, rápida)
5. ✅ Clinical Trials - Olaparib (R&D only)

### Nível 3: Avançado (60 minutos)
6. ✅ Patentes - Darolutamide (baseline Cortellis)
7. ✅ Busca Completa - Venetoclax (deep search)
8. ✅ Debug Failed URLs

---

## 📊 BASELINE VALIDATION (15 moléculas Cortellis)

Execute em sequência com intervalo de 1 minuto:

```bash
# Script para teste completo
for molecule in "Darolutamide" "Ixazomib" "Olaparib" "Venetoclax" "Niraparib" \
                "Axitinib" "Tivozanib" "Sonidegib" "Trastuzumab" "Paracetamol" \
                "Aspirin" "Torgena" "Zongertinib" "Sebetralsat" "Vinseltinib"; do
  
  echo "Testing $molecule..."
  
  curl -X POST {{BASE_URL}}/api/v1/patents/search \
    -H "Content-Type: application/json" \
    -d "{\"molecule\": \"$molecule\"}" \
    -o "result_$molecule.json"
  
  sleep 60  # Aguardar 1 minuto entre testes
done
```

---

## ⚠️ TROUBLESHOOTING

### Erro: Connection Refused
```
Solução: Verificar se servidor está rodando
→ curl {{BASE_URL}}/health
```

### Erro: 500 Internal Server Error
```
Solução: Verificar logs
→ railway logs (se Railway)
→ docker logs pharmyrus (se Docker)
→ cat logs/app.log (se local)
```

### Erro: Timeout (>60s)
```
Solução: Molécula complexa, use deep_search: false
→ Ou espere mais tempo (alguns podem levar até 90s)
```

### Resultados Vazios
```
Solução: Verificar variáveis de ambiente
→ EPO_CONSUMER_KEY está configurado?
→ EPO_CONSUMER_SECRET está configurado?
→ Verificar /api/v1/stats para service status
```

---

## 🎯 CRITÉRIOS DE SUCESSO

### Health Check
- ✅ Status 200
- ✅ Response time < 500ms
- ✅ All services "initialized" or "ready"

### Busca Completa
- ✅ Status 200
- ✅ Response time < 60s (normal) ou < 90s (deep search)
- ✅ patents.total > 0
- ✅ research_and_development.clinical_trials.total > 0

### Apenas Patentes
- ✅ Status 200
- ✅ Response time < 60s
- ✅ patents.total >= 50% do baseline Cortellis
- ✅ quality_score > 70

### Clinical Trials
- ✅ Status 200
- ✅ Response time < 10s
- ✅ clinical_trials.total > 0
- ✅ Fases distribuídas (Phase 1/2/3)

---

## 📞 SUPORTE

Se encontrar problemas:

1. Verificar `/health` endpoint
2. Verificar `/api/v1/stats` para service status
3. Verificar `/api/v1/debug/failed-urls` para erros
4. Verificar logs: `railway logs` ou `docker logs`
5. Contato: daniel@genoi.com.br

---

## 🎉 EXEMPLO DE SUCESSO

```bash
✅ Health Check: 200 OK (250ms)
✅ System Stats: 200 OK (180ms)
✅ PubChem Aspirin: 200 OK (2.3s)
✅ Search Aspirin: 200 OK (38.5s) - 85 patents + 245 trials
✅ Patents Darolutamide: 200 OK (45.2s) - 55 patents (100% Cortellis)
✅ Clinical Trials Olaparib: 200 OK (6.8s) - 320 trials

Status: 🎯 PRODUCTION READY
```
