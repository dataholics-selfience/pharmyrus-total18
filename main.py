"""
Pharmyrus V5.0 - Patent Intelligence Platform
FastAPI application with ultra-resilient crawling
100% cloud-agnostic, n8n-independent
"""
import os
import logging
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.core.parallel_orchestrator_v2 import ParallelOrchestratorV2
from src.core.debug_logger import DebugLogger
from src.ai.ai_fallback import AIFallbackProcessor

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

orchestrator: Optional[ParallelOrchestratorV2] = None
debug_logger: Optional[DebugLogger] = None
ai_processor: Optional[AIFallbackProcessor] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global orchestrator, debug_logger, ai_processor
    logger.info("🚀 Starting Pharmyrus V5.0...")
    
    debug_logger = DebugLogger(
        use_firestore=os.getenv("USE_FIRESTORE", "false").lower() == "true",
        local_storage_path="./debug_logs",
        project_id=os.getenv("FIRESTORE_PROJECT_ID")
    )
    
    ai_processor = AIFallbackProcessor(max_budget_usd=0.10)
    
    orchestrator = ParallelOrchestratorV2(
        epo_consumer_key=os.getenv("EPO_CONSUMER_KEY"),
        epo_consumer_secret=os.getenv("EPO_CONSUMER_SECRET"),
        inpi_crawler_url=os.getenv("INPI_CRAWLER_URL", "https://crawler3-production.up.railway.app"),
        serpapi_key=os.getenv("SERPAPI_KEY"),
        ai_fallback_enabled=True
    )
    
    logger.info("✅ All systems ready!")
    yield
    logger.info("🛑 Shutting down...")
    if orchestrator:
        await orchestrator.__aexit__(None, None, None)

app = FastAPI(
    title="Pharmyrus V5.0",
    description="Patent Intelligence Platform - Ultra Resilient",
    version="5.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SearchRequest(BaseModel):
    molecule: str = Field(..., description="Molecule name")
    brand_name: Optional[str] = Field(None, description="Brand name")
    target_countries: Optional[List[str]] = Field(default=["BR"], description="Target countries")
    deep_search: bool = Field(False, description="Enable deep search")

class HealthResponse(BaseModel):
    status: str
    version: str
    services: dict

@app.get("/", tags=["Status"])
async def root():
    return {
        "service": "Pharmyrus V5.0",
        "version": "5.0.0",
        "status": "online",
        "features": [
            "Multi-source patent search",
            "Clinical trials data",
            "Ultra-resilient super crawler",
            "AI fallback processing",
            "Auto-healing system",
            "Cloud-agnostic",
            "n8n-independent"
        ]
    }

@app.get("/health", response_model=HealthResponse, tags=["Status"])
async def health_check():
    """
    Health check simplificado - retorna OK mesmo durante inicialização
    Railway precisa de resposta rápida
    """
    services = {
        "orchestrator": "ready" if orchestrator else "initializing",
        "debug_logger": "ready" if debug_logger else "initializing",
        "ai_processor": "ready" if ai_processor else "initializing"
    }
    # Railway healthcheck: retorna 200 sempre, status nos details
    return HealthResponse(
        status="healthy",
        version="5.0.0",
        services=services
    )

@app.get("/ready", tags=["Status"])
async def readiness_check():
    """
    Readiness check - retorna 200 apenas quando tudo está pronto
    """
    if not orchestrator or not debug_logger or not ai_processor:
        raise HTTPException(status_code=503, detail="Services still initializing")
    return {"status": "ready", "message": "All systems operational"}

@app.post("/api/v1/search", tags=["Search"])
async def comprehensive_search(request: SearchRequest, background_tasks: BackgroundTasks):
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")
    try:
        async with orchestrator:
            result = await orchestrator.comprehensive_search(
                molecule=request.molecule,
                brand_name=request.brand_name,
                target_countries=request.target_countries,
                deep_search=request.deep_search
            )
        return result.to_dict()
    except Exception as e:
        logger.error(f"Search failed: {str(e)}", exc_info=True)
        if debug_logger:
            background_tasks.add_task(
                debug_logger.log_error,
                url=f"/api/v1/search?molecule={request.molecule}",
                error=str(e),
                source="comprehensive_search",
                context={"request": request.dict()}
            )
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/patents/search", tags=["Patents"])
async def patents_only_search(request: SearchRequest):
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")
    try:
        async with orchestrator:
            result = await orchestrator.comprehensive_search(
                molecule=request.molecule,
                brand_name=request.brand_name,
                target_countries=request.target_countries,
                deep_search=request.deep_search
            )
        full_result = result.to_dict()
        return {
            "success": full_result["success"],
            "molecule": full_result["molecule"],
            "patents": full_result["patents"],
            "pubchem_data": full_result.get("pubchem_data"),
            "metadata": full_result["metadata"]
        }
    except Exception as e:
        logger.error(f"Patents search failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/research/clinical-trials", tags=["Research & Development"])
async def clinical_trials_search(request: SearchRequest):
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")
    try:
        async with orchestrator:
            result = await orchestrator.comprehensive_search(
                molecule=request.molecule,
                brand_name=request.brand_name,
                target_countries=request.target_countries,
                deep_search=request.deep_search
            )
        full_result = result.to_dict()
        return {
            "success": full_result["success"],
            "molecule": full_result["molecule"],
            "research_and_development": full_result["research_and_development"],
            "pubchem_data": full_result.get("pubchem_data"),
            "metadata": full_result["metadata"]
        }
    except Exception as e:
        logger.error(f"Clinical trials search failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/molecule/{molecule}/pubchem", tags=["Molecular Data"])
async def get_pubchem_data(molecule: str):
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")
    try:
        async with orchestrator:
            pubchem_data = await orchestrator._get_pubchem_data(molecule)
        if not pubchem_data:
            raise HTTPException(status_code=404, detail="Molecule not found in PubChem")
        return pubchem_data.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PubChem query failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/debug/failed-urls", tags=["Debug"])
async def get_failed_urls(source: Optional[str] = None, limit: int = 50):
    if not debug_logger:
        raise HTTPException(status_code=503, detail="Debug logger not initialized")
    try:
        failed = await debug_logger.list_failed_urls(source=source, limit=limit)
        return {"total": len(failed), "failed_urls": failed}
    except Exception as e:
        logger.error(f"Failed to get debug logs: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/stats", tags=["Status"])
async def get_stats():
    if not orchestrator or not orchestrator.super_crawler:
        raise HTTPException(status_code=503, detail="System not ready")
    stats = {
        "super_crawler": orchestrator.super_crawler.get_stats() if orchestrator.super_crawler else {},
        "version": "5.0.0",
        "features_enabled": {
            "wo_search": bool(orchestrator.wo_searcher),
            "clinical_trials": bool(orchestrator.ct_crawler),
            "ai_fallback": bool(orchestrator.ai_processor),
            "debug_logging": bool(debug_logger)
        }
    }
    return stats

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, workers=2, log_level="info")
