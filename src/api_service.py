"""FastAPI service for Pharmyrus v4.0"""
import logging
import time
from fastapi import FastAPI, HTTPException, Path
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .models import (
    WODetailsResponse,
    PatentDetailsResponse,
    SearchRequest,
    SearchResponse,
    WorldwideApplication
)
from .crawlers import crawler_pool, google_patents_client, google_patents_pool, inpi_client
from . import utils, config

# Setup logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# Lifespan management
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    logger.info("🚀 Starting Pharmyrus v4.0...")
    logger.info(f"  Initializing {config.CRAWLER_POOL_SIZE} WIPO crawlers...")
    await crawler_pool.initialize()
    logger.info("  Initializing Google Patents crawlers...")
    await google_patents_pool.initialize()
    logger.info("  Initializing API clients...")
    await google_patents_client.initialize()
    await inpi_client.initialize()
    logger.info("✅ Pharmyrus v4.0 ready!")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down Pharmyrus v4.0...")
    await crawler_pool.close()
    await google_patents_pool.close()
    await google_patents_client.close()
    await inpi_client.close()
    logger.info("✅ Shutdown complete")

# ============================================================================
# FastAPI app
# ============================================================================

app = FastAPI(
    title="Pharmyrus v4.0",
    description="Patent Intelligence API for Pharmaceutical Patents",
    version="4.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Debug endpoints (for HTML/screenshot retrieval)
try:
    from .debug_endpoints import router as debug_router
    app.include_router(debug_router)
    logger.info("✅ Debug endpoints enabled at /debug/*")
except Exception as e:
    logger.warning(f"⚠️  Debug endpoints not loaded: {e}")

# ============================================================================
# ENDPOINT 1: WO Details (ALL countries)
# ============================================================================

@app.get("/api/v1/wo/{wo_number}", response_model=WODetailsResponse)
async def get_wo_details(
    wo_number: str = Path(..., description="WO number (e.g., WO2011051540)")
):
    """
    Get complete WO patent details including ALL worldwide applications
    
    This endpoint returns:
    - WO basic info (title, abstract, assignee, dates)
    - ALL worldwide applications (not just BR)
    - Grouped by year
    - Total countries count
    """
    start_time = time.time()
    
    logger.info(f"📋 REQUEST: GET /api/v1/wo/{wo_number}")
    
    # Normalize WO number
    clean_wo = utils.normalize_wo_number(wo_number)
    
    if not utils.is_valid_wo_number(clean_wo):
        raise HTTPException(status_code=400, detail=f"Invalid WO number format: {wo_number}")
    
    try:
        # Get crawler from pool
        crawler = crawler_pool.get_crawler()
        
        # Fetch WO details via WIPO Patentscope
        logger.info(f"  🔍 Fetching WIPO data for {clean_wo}...")
        wo_data = await crawler.get_wo_details(clean_wo)
        
        if not wo_data:
            raise HTTPException(status_code=404, detail=f"WO not found: {wo_number}")
        
        # Parse worldwide applications
        worldwide_apps = wo_data.get("worldwide_applications", {})
        
        # Convert to response format
        applications_by_year = {}
        all_countries = set()
        
        for year, apps in worldwide_apps.items():
            applications_by_year[year] = [
                WorldwideApplication(
                    country_code=app.get("country_code", ""),
                    application_number=app.get("application_number", ""),
                    filing_date=app.get("filing_date", ""),
                    publication_date=app.get("publication_date", ""),
                    status=app.get("status", "")
                )
                for app in apps
            ]
            
            # Count unique countries
            for app in apps:
                country = app.get("country_code", "")
                if country:
                    all_countries.add(country)
        
        duration = time.time() - start_time
        
        response = WODetailsResponse(
            wo_number=clean_wo,
            title=wo_data.get("title", ""),
            abstract=wo_data.get("abstract", ""),
            assignee=wo_data.get("assignee", ""),
            filing_date=wo_data.get("filing_date", ""),
            publication_date=wo_data.get("publication_date", ""),
            worldwide_applications=applications_by_year,
            total_applications=sum(len(apps) for apps in applications_by_year.values()),
            total_countries=len(all_countries),
            search_duration_seconds=round(duration, 2)
        )
        
        logger.info(f"  ✅ Found {response.total_applications} applications in {response.total_countries} countries")
        logger.info(f"  ⏱️  Duration: {utils.format_duration(duration)}")
        
        return response
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"  ❌ Error processing {wo_number}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

# ============================================================================
# ENDPOINT 2: Patent Details (single patent)
# ============================================================================

@app.get("/api/v1/patent/{patent_number}", response_model=PatentDetailsResponse)
async def get_patent_details(
    patent_number: str = Path(..., description="Patent number (e.g., BR112012008823B8, US9376391B2)")
):
    """
    Get complete details for a single patent
    
    This endpoint returns:
    - Full patent info (title, abstract, claims)
    - Dates (priority, filing, publication, grant)
    - Parties (assignee, inventors)
    - Legal status
    - Family information
    - Data from multiple sources (Google Patents + INPI if BR)
    
    Strategy:
    1. Try Google Patents Playwright (direct scraping, no rate limits)
    2. Fallback to SerpAPI if Playwright fails
    3. Enrich with INPI data if Brazilian patent
    """
    start_time = time.time()
    
    logger.info(f"📋 REQUEST: GET /api/v1/patent/{patent_number}")
    
    # Clean patent number
    clean_patent = utils.clean_patent_number(patent_number)
    country_code = utils.extract_country_code(clean_patent)
    
    logger.info(f"  🌍 Country: {country_code} ({utils.get_country_name(country_code)})")
    
    try:
        # Strategy 1: Try Google Patents Playwright (direct, no rate limits)
        logger.info(f"  🔍 Fetching Google Patents data (Playwright)...")
        gp_playwright_data = await google_patents_pool.fetch_patent(clean_patent)
        
        # Check if Playwright got meaningful data
        playwright_success = (
            gp_playwright_data.get('title') or 
            gp_playwright_data.get('abstract') or 
            gp_playwright_data.get('patent_family', {}).get('total_members', 0) > 0
        )
        
        if playwright_success:
            logger.info(f"  ✅ Playwright: Got data for {clean_patent}")
            gp_data = gp_playwright_data
            data_source = "playwright"
        else:
            # Strategy 2: Fallback to SerpAPI
            logger.warning(f"  ⚠️  Playwright failed, trying SerpAPI fallback...")
            gp_data = await google_patents_client.get_patent_details(clean_patent)
            data_source = "serpapi"
        
        # Initialize sources dict
        sources = {
            "google_patents": {
                "url": gp_data.get("url", f"https://patents.google.com/patent/{clean_patent}"),
                "pdf_url": gp_data.get("pdf_url", ""),
                "cpc_classifications": gp_data.get("classifications", {}).get("cpc", []) or gp_data.get("cpc_classifications", []),
                "ipc_classifications": gp_data.get("classifications", {}).get("ipc", []) or gp_data.get("ipc_classifications", []),
                "family_id": gp_data.get("family_id", ""),
                "family_size": gp_data.get("patent_family", {}).get("total_members", 0) or gp_data.get("family_size", 0),
                "data_source": data_source,
                "family_countries": gp_data.get("patent_family", {}).get("countries", [])
            }
        }
        
        # If BR patent, enrich with INPI data
        if country_code == "BR":
            logger.info(f"  🇧🇷 Fetching INPI data...")
            inpi_data = await inpi_client.get_patent_details(clean_patent)
            
            if inpi_data.get("found"):
                sources["inpi"] = {
                    "status": inpi_data.get("status", ""),
                    "process_number": inpi_data.get("process_number", ""),
                    "events": inpi_data.get("events", [])
                }
                logger.info(f"  ✅ INPI data enriched")
        
        duration = time.time() - start_time
        
        response = PatentDetailsResponse(
            publication_number=clean_patent,
            country_code=country_code,
            priority_date=gp_data.get("priority_date", ""),
            filing_date=gp_data.get("filing_date", ""),
            publication_date=gp_data.get("publication_date", ""),
            grant_date=gp_data.get("grant_date", ""),
            title=gp_data.get("title", ""),
            abstract=gp_data.get("abstract", ""),
            claims=gp_data.get("claims", ""),
            assignee=gp_data.get("assignee", ""),
            inventors=gp_data.get("inventors", []),
            legal_status=gp_data.get("legal_status", ""),
            legal_status_detail=gp_data.get("legal_status", ""),
            family_id=gp_data.get("family_id", ""),
            wo_number="",  # Could be extracted from family
            sources=sources,
            search_duration_seconds=round(duration, 2)
        )
        
        logger.info(f"  ✅ Patent details retrieved ({data_source})")
        logger.info(f"  ⏱️  Duration: {utils.format_duration(duration)}")
        
        return response
    
    except Exception as e:
        logger.error(f"  ❌ Error processing {patent_number}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

# ============================================================================
# ENDPOINT 3: Search (complete pipeline)
# ============================================================================

@app.post("/api/v1/search", response_model=SearchResponse)
async def search_molecule(request: SearchRequest):
    """
    Complete patent search pipeline for a molecule
    
    Pipeline:
    1. PubChem → dev codes, CAS, synonyms
    2. WO Discovery → find WO numbers
    3. For each WO → WIPO Crawler → worldwide applications
    4. For each application → Google Patents → full details
    5. For each BR → INPI → enrichment
    6. Consolidation → final JSON (target-buscas.json format)
    
    This is the most comprehensive endpoint.
    """
    logger.info(f"📋 REQUEST: POST /api/v1/search")
    logger.info(f"  Molecule: {request.molecule_name}")
    logger.info(f"  Max WOs: {request.max_wos}")
    logger.info(f"  Include INPI: {request.include_inpi}")
    
    try:
        # Import orchestrator
        from .orchestrator import search_orchestrator
        
        # Execute full pipeline
        response = await search_orchestrator.execute_search(request)
        
        logger.info(f"  ✅ Search complete: {response.executive_summary.total_patents} patents found")
        
        return response
    
    except Exception as e:
        logger.error(f"  ❌ Error in search pipeline: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

# ============================================================================
# Health check
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "4.0.0",
        "crawlers_ready": len(crawler_pool.crawlers),
        "crawler_pool_size": config.CRAWLER_POOL_SIZE,
        "serpapi_keys_available": len(config.SERPAPI_KEYS)
    }

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Pharmyrus v4.0",
        "description": "Patent Intelligence API",
        "endpoints": {
            "wo_details": "/api/v1/wo/{wo_number}",
            "patent_details": "/api/v1/patent/{patent_number}",
            "search": "/api/v1/search",
            "health": "/health",
            "docs": "/docs"
        }
    }
