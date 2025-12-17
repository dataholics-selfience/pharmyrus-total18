# 🔬 Pharmyrus v4.0 - Patent Intelligence Platform

Sistema de inteligência de patentes farmacêuticas com foco em patentes brasileiras (BR).

## 🚀 Features

- ✅ Extração de famílias de patentes do Google Patents via Playwright
- ✅ Debug endpoints para captura de HTML em tempo real
- ✅ Pool de browsers para processamento paralelo
- ✅ API REST com FastAPI

## 📦 Deployment

### Railway

```bash
# 1. Clone o repositório
git clone <repo-url>

# 2. Push para Railway
railway up

# 3. Configure variáveis (se necessário)
railway variables set PORT=8080
```

### Docker Local

```bash
# Build
docker build -t pharmyrus .

# Run
docker run -p 8080:8080 pharmyrus
```

## 🔍 Debug Endpoints

Quando o crawler não encontra patentes BR, HTML e screenshot são salvos automaticamente.

### Listar arquivos debug
```
GET /debug/files
```

### Ver HTML no navegador
```
GET /debug/html/{patent_id}
```

### Download de arquivo específico
```
GET /debug/download/{filename}
```

### Último arquivo salvo
```
GET /debug/latest
```

### Limpar arquivos debug
```
DELETE /debug/clean
```

## 🧪 Testing

```bash
# Buscar patente (vai falhar mas salvar HTML para debug)
POST /api/v1/patent/BR112012008823B8

# Acessar HTML capturado
GET /debug/html/BR112012008823B8
```

## 📊 Architecture

```
pharmyrus-v4.0/
├── main.py                          # Entry point
├── Dockerfile                       # Container config
├── requirements.txt                 # Python dependencies
├── railway.json                     # Railway config
└── src/
    ├── api_service.py              # FastAPI app
    ├── debug_endpoints.py          # Debug HTTP endpoints
    └── crawlers/
        ├── __init__.py             # Pool initialization
        ├── google_patents_playwright.py  # Browser automation
        └── google_patents_pool.py  # Crawler pool manager
```

## 🛠️ Stack

- **Python 3.11**
- **FastAPI** - Web framework
- **Playwright** - Browser automation
- **Chromium** - Headless browser
- **Railway** - Cloud deployment

## 📝 License

Proprietary - Pharmyrus Intelligence Platform
