# 🧠 Pharmyrus v4.0.3-AI-POWERED

## 🎉 What's New in v4.0.3

### AI-Powered Extraction
- **Claude Sonnet 4 Integration**: Uses Anthropic's Claude API to intelligently extract patent data
- **Resilient to HTML Changes**: AI can understand patent data even when CSS selectors change
- **Automatic Fallback**: If AI extraction fails, automatically falls back to CSS selectors
- **Superior Data Quality**: AI extracts complete inventor lists, accurate abstracts, and family members

### How It Works
1. **AI-First Approach**: Tries Claude API extraction first
2. **Smart HTML Selection**: Sends only relevant HTML sections to reduce token usage
3. **Structured Output**: AI returns clean JSON with all patent fields
4. **CSS Fallback**: If AI fails (no API key, errors, etc.), uses traditional CSS selectors

## 🚀 Quick Start

### Environment Variables
```bash
# Required for AI extraction (optional - falls back to CSS if not set)
export ANTHROPIC_API_KEY="sk-ant-..."

# Railway deployment
railway variables set ANTHROPIC_API_KEY=sk-ant-...
```

### Deploy to Railway
```bash
cd /path/to/project
railway up
```

### Local Testing
```bash
# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Run server
python main.py
```

## 📊 API Endpoints

### Get Patent Details
```bash
POST /api/v1/patent/{patent_id}

# Example
curl -X POST https://your-app.up.railway.app/api/v1/patent/BR112012008823B8
```

### Health Check
```bash
GET /health

# Returns version 4.0.3-AI-POWERED
```

### Debug Endpoints
```bash
# View captured HTML (JS-free for safe viewing)
GET /debug/html/{patent_id}

# Download original HTML
GET /debug/download/{filename}

# List all captured files
GET /debug/files
```

## 🧠 AI Extraction Details

### What Gets Extracted
- ✅ **Title**: Full patent title in English
- ✅ **Abstract**: Complete abstract text
- ✅ **Inventors**: ALL inventors (not just first few)
- ✅ **Assignee**: Company/organization name
- ✅ **Dates**: Filing date and publication date
- ✅ **Family Members**: Related patents (prioritizing BR patents)

### Fallback Behavior
If AI extraction fails, the system automatically uses:
- CSS selectors for basic data
- Meta tags for inventors/assignees
- BeautifulSoup parsing for family members

### Cost Optimization
- Only sends relevant HTML sections (~15KB instead of 700KB)
- Uses Claude Sonnet 4 (fastest, most cost-effective)
- Caches results to avoid duplicate API calls

## 📈 Performance

### v4.0.3 vs v4.0.2
| Feature | v4.0.2 (CSS Only) | v4.0.3 (AI-Powered) |
|---------|-------------------|---------------------|
| **Inventor Extraction** | Often incomplete | ✅ Complete list |
| **Abstract Quality** | Mixed PT/EN | ✅ Clean English |
| **Family Members** | Hit or miss | ✅ Reliable |
| **Resilience** | Breaks on HTML changes | ✅ Adapts automatically |
| **Speed** | ~5-8 seconds | ~6-10 seconds |

## 🔧 Configuration

### Requirements
```
fastapi==0.104.1
uvicorn[standard]==0.24.0
playwright==1.40.0
beautifulsoup4==4.12.2
pydantic==2.5.0
anthropic==0.39.0  # New!
```

### Dockerfile
Already configured - no changes needed. Just set `ANTHROPIC_API_KEY` environment variable.

## 🎯 Testing AI Extraction

```python
import requests

# Test with known patent
response = requests.post(
    "https://your-app.up.railway.app/api/v1/patent/BR112012008823B8"
)

data = response.json()

# Check extraction method
print(f"Method: {data['data'].get('extraction_method')}")  
# Expected: 'ai' (if API key set) or 'css_fallback'

# Verify complete data
print(f"Inventors: {len(data['data']['inventors'])}")  
# Expected: 9 inventors for this patent

print(f"Family members: {data['br_patents_found']}")
# Expected: Multiple BR patents
```

## 🐛 Troubleshooting

### AI Extraction Not Working
1. Check API key is set: `echo $ANTHROPIC_API_KEY`
2. Verify key format: Should start with `sk-ant-`
3. Check logs for error messages
4. System automatically falls back to CSS if AI fails

### Still Getting Incomplete Data
- Check if `extraction_method` is 'ai' or 'css_fallback' in response
- If 'css_fallback', AI extraction failed - check API key
- If 'ai', but data still incomplete, open GitHub issue

## 📝 Changelog

### v4.0.3-AI-POWERED (2024-12-17)
- ✨ Added AI-powered extraction using Claude Sonnet 4
- ✨ Intelligent HTML parsing with automatic fallback
- ✨ Complete inventor and family member extraction
- ✨ Resilient to Google Patents HTML structure changes
- 📦 Added `anthropic==0.39.0` dependency
- 📦 Added `beautifulsoup4==4.12.2` for CSS fallback

### v4.0.2-NO-JS-REDIRECT (2024-12-17)
- 🐛 Fixed JavaScript redirect blocking HTML viewing
- 🐛 Removed all `<script>` tags from debug HTML endpoints

### v4.0.1-ULTRA-SIMPLE (2024-12-17)
- 🐛 Fixed ModuleNotFoundError by inlining all models

## 💡 Best Practices

1. **Always set ANTHROPIC_API_KEY** for best results
2. **Monitor extraction_method** in responses to verify AI usage
3. **Use debug endpoints** to verify HTML capture quality
4. **Set reasonable timeouts** (60s default is good)

## 🤝 Contributing

Found a patent that doesn't extract correctly? Open an issue with:
- Patent ID
- Expected data
- Actual data received
- Value of `extraction_method` field

## 📄 License

MIT License - Use freely in your projects!

---

**Made with 🧠 AI + ❤️ by Daniel for Pharmyrus Patent Intelligence**
