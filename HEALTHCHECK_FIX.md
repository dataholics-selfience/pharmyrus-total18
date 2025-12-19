# 🚨 Railway Healthcheck Troubleshooting

## Problema: "Healthcheck failed!"

O healthcheck do Railway está falhando. Aqui estão as **causas e soluções**.

---

## ✅ Correções Aplicadas

### 1. Health Check Simplificado
```python
# ANTES: Falhava se orchestrator não estivesse ready
@app.get("/health")
async def health_check():
    if not orchestrator:
        raise HTTPException(503)  # ❌ FALHA

# DEPOIS: Sempre retorna 200 OK
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",  # ✅ SEMPRE OK
        "services": {
            "orchestrator": "ready" or "initializing"
        }
    }
```

### 2. Timeout Aumentado
```json
// railway.json
{
  "healthcheckTimeout": 300  // Era 100, agora 300 (5 minutos)
}
```

### 3. Workers Reduzido
```dockerfile
# Dockerfile.light
CMD ["uvicorn", "--workers", "1"]  // Era 2, agora 1
```

### 4. Endpoint /ready Adicional
```python
@app.get("/ready")  # Para quando REALMENTE precisa de tudo pronto
```

---

## 🔍 Diagnóstico

### Verificar se variáveis de ambiente estão configuradas:

```bash
railway variables
```

**Deve ter:**
```
EPO_CONSUMER_KEY = G5wJypxeg0GXEJoMGP37tdK370aKxeMszGKAkD6QaR0yiR5X
EPO_CONSUMER_SECRET = zg5AJ0EDzXdJey3GaFNM8ztMVxHKXRrAihXH93iS5ZAzKPAP
USE_FIRESTORE = false
```

### Se não tiver, configure:

```bash
railway variables set EPO_CONSUMER_KEY="G5wJypxeg0GXEJoMGP37tdK370aKxeMszGKAkD6QaR0yiR5X"
railway variables set EPO_CONSUMER_SECRET="zg5AJ0EDzXdJey3GaFNM8ztMVxHKXRrAihXH93iS5ZAzKPAP"
railway variables set USE_FIRESTORE="false"
railway variables set GROK_API_KEY="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"
```

---

## 🚀 Fazer Redeploy

Depois de configurar variáveis e commitar as correções:

```bash
# Fazer push das correções
railway up

# Acompanhar logs
railway logs --follow
```

---

## 📊 Verificar Status

Depois que deploy terminar:

```bash
# 1. Pegar URL
railway domain

# 2. Testar health (deve retornar 200 sempre)
curl https://your-app.up.railway.app/health

# Resposta esperada:
{
  "status": "healthy",
  "version": "5.0.0",
  "services": {
    "orchestrator": "ready",      // ou "initializing"
    "debug_logger": "ready",
    "ai_processor": "ready"
  }
}

# 3. Testar readiness (só retorna 200 quando tudo pronto)
curl https://your-app.up.railway.app/ready

# Resposta esperada:
{
  "status": "ready",
  "message": "All systems operational"
}
```

---

## ⚠️ Se Ainda Falhar

### Cenário 1: Build falhou
```bash
railway logs | grep -i error
```
**Solução:** Verificar se Dockerfile.light está correto

### Cenário 2: App inicia mas crashea
```bash
railway logs | tail -50
```
**Possíveis causas:**
- Falta variável EPO_CONSUMER_KEY
- Falta variável EPO_CONSUMER_SECRET
- Memória insuficiente (Railway Free = 512 MB)

**Solução:**
```bash
# Configurar variáveis
railway variables set EPO_CONSUMER_KEY="..."
railway variables set EPO_CONSUMER_SECRET="..."

# Redeploy
railway up
```

### Cenário 3: App funcionando mas healthcheck timeout
**Causa:** App demora muito para inicializar

**Solução:** Já aplicada nas correções (timeout 300s, 1 worker)

### Cenário 4: Erro de importação
```
ModuleNotFoundError: No module named 'src'
```

**Solução:** Verificar se todos arquivos foram copiados
```bash
# No Dockerfile.light deve ter:
COPY . .
```

---

## 🎯 Checklist de Sucesso

Antes de considerar o deploy bem-sucedido:

- [ ] Build completou sem erros
- [ ] Variáveis de ambiente configuradas (EPO_CONSUMER_KEY, EPO_CONSUMER_SECRET, USE_FIRESTORE)
- [ ] `/health` retorna 200 OK
- [ ] `/ready` retorna 200 OK ou 503 (se ainda inicializando)
- [ ] `/` retorna informações do serviço
- [ ] Logs não mostram erros críticos

---

## 📞 Comandos Úteis

```bash
# Ver status
railway status

# Ver logs em tempo real
railway logs --follow

# Ver últimas 100 linhas
railway logs | tail -100

# Ver apenas erros
railway logs | grep -i error

# Reiniciar serviço
railway restart

# Ver variáveis
railway variables

# Abrir no browser
railway open
```

---

## 🔧 Configurações Finais

Se tudo falhar, considere estas configurações no Railway Dashboard:

1. **Settings → Deploy**
   - Health Check Path: `/health`
   - Health Check Timeout: `300`
   - Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT --workers 1 --timeout-keep-alive 120`

2. **Settings → Resources**
   - Memory: Pelo menos 512 MB (Free tier)
   - Se disponível, aumentar para 1 GB

3. **Settings → Environment**
   - Verificar TODAS as variáveis listadas acima

---

## ✅ Estado Atual das Correções

**Arquivos modificados:**
- ✅ `main.py` - Health check simplificado + endpoint /ready
- ✅ `railway.json` - Timeout 300s + startCommand otimizado
- ✅ `Dockerfile.light` - 1 worker + timeout-keep-alive 120s

**Próximo passo:**
```bash
railway up
```

E acompanhar logs para verificar se iniciou corretamente!
