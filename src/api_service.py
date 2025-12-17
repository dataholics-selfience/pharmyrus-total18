"""
FastAPI Application Service - ALL IN ONE (no external models.py)
🧠 NOW WITH AI-POWERED EXTRACTION!
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from contextlib import asynccontextmanager
from pydantic import BaseModel, Field
import os
from pathlib import Path

# AI Extractor import
try:
    from src.extractors.ai_extractor import get_extractor
    AI_EXTRACTION_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  AI extraction not available: {e}")
    AI_EXTRACTION_AVAILABLE = False

logger = logging.getLogger(__name__)

# ============================================================================
# PYDANTIC MODELS (INLINE - NO SEPARATE FILE)
# ============================================================================

class PatentRequest(BaseModel):
    """Request model for patent search"""
    patent_id: str = Field(..., description="Patent publication number")


class PatentFamilyMember(BaseModel):
    """Model for a patent family member"""
    publication_number: str
    title: str = ""
    country: str = ""
    kind_code: str = ""
    publication_date: str = ""
    link: str = ""


class PatentDetailsResponse(BaseModel):
    """Response model for patent details"""
    patent_id: str
    success: bool
    data: Dict[str, Any] = {}
    family_members: List[PatentFamilyMember] = []
    br_patents_found: int = 0
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class HealthResponse(BaseModel):
    """Health check response"""
    status: str = "healthy"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: str = "4.0.3-AI-POWERED"


class DebugFileInfo(BaseModel):
    """Debug file information"""
    filename: str
    size: int
    created: str
    url: str


# ============================================================================
# DEBUG CONFIGURATION
# ============================================================================

DEBUG_DIR = Path("/tmp/playwright_debug")
DEBUG_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def remove_javascript_from_html(html_content: str) -> str:
    """
    Remove all JavaScript from HTML to prevent redirects and dynamic behavior
    This allows safe viewing of captured HTML without executing scripts
    """
    import re
    
    # Remove <script> tags and their content
    # Matches: <script>...</script> and <script src="..."></script>
    html_content = re.sub(
        r'<script[^>]*>.*?</script>',
        '',
        html_content,
        flags=re.DOTALL | re.IGNORECASE
    )
    
    # Remove inline event handlers (onclick, onload, etc)
    html_content = re.sub(
        r'\s+on\w+\s*=\s*["\'][^"\']*["\']',
        '',
        html_content,
        flags=re.IGNORECASE
    )
    
    # Remove javascript: URLs
    html_content = re.sub(
        r'href\s*=\s*["\']javascript:[^"\']*["\']',
        'href="#"',
        html_content,
        flags=re.IGNORECASE
    )
    
    # Add notice banner at the top
    notice = """
    <div style="background: #ff6b6b; color: white; padding: 10px; text-align: center; position: sticky; top: 0; z-index: 9999;">
        ⚠️ <strong>DEBUG MODE:</strong> JavaScript disabled to prevent redirects | 
        This is the captured HTML from Google Patents | 
        <a href="/debug/download/{filename}" style="color: white; text-decoration: underline;">Download Original</a>
    </div>
    """
    
    # Insert notice after <body> tag
    html_content = re.sub(
        r'(<body[^>]*>)',
        r'\1' + notice,
        html_content,
        flags=re.IGNORECASE
    )
    
    return html_content


# ============================================================================
# GLOBAL CRAWLER POOL
# ============================================================================

google_patents_pool = None


# ============================================================================
# APPLICATION LIFECYCLE
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management"""
    global google_patents_pool
    
    logger.info("🚀 Starting Pharmyrus v4.0.3-AI-POWERED (Ultra Simple)...")
    
    try:
        from .crawlers.google_patents_pool import GooglePatentsCrawlerPool
        
        google_patents_pool = GooglePatentsCrawlerPool(pool_size=2)
        await google_patents_pool.initialize()
        
        logger.info("✅ Crawler pool initialized")
        logger.info("✅ API ready")
        
    except Exception as e:
        logger.error(f"❌ Init error: {e}")
        raise
    
    yield
    
    logger.info("🔌 Shutting down...")
    if google_patents_pool:
        await google_patents_pool.close_all()


# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI(
    title="Pharmyrus v4.0.3-AI-POWERED",
    description="Patent Intelligence - Ultra Simple Version",
    version="4.0.3-AI-POWERED",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# MAIN ENDPOINTS
# ============================================================================

@app.get("/", tags=["Root"])
async def root():
    """Root endpoint"""
    return {
        "service": "Pharmyrus v4.0.3-AI-POWERED",
        "status": "operational",
        "note": "Ultra Simple - All models inline",
        "endpoints": {
            "health": "/health",
            "patent": "POST /api/v1/patent/{patent_id}",
            "debug": "/debug/html/{patent_id}"
        }
    }


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Health check"""
    return HealthResponse(status="healthy", version="4.0.3-AI-POWERED")


@app.post("/api/v1/patent/{patent_id}", response_model=PatentDetailsResponse, tags=["Patents"])
async def get_patent_details(patent_id: str):
    """Get patent details and family"""
    global google_patents_pool
    
    if not google_patents_pool:
        raise HTTPException(503, "Crawler pool not ready")
    
    logger.info(f"🔍 Fetching: {patent_id}")
    
    try:
        result = await google_patents_pool.fetch_patent_details(patent_id)
        
        br_patents = [
            m for m in result.get('family_members', [])
            if m.get('publication_number', '').upper().startswith('BR')
        ]
        
        family_members = [
            PatentFamilyMember(**m)
            for m in result.get('family_members', [])
        ]
        
        logger.info(f"✅ Found {len(br_patents)} BR patents")
        
        return PatentDetailsResponse(
            patent_id=patent_id,
            success=result.get('success', False),
            data=result.get('data', {}),
            family_members=family_members,
            br_patents_found=len(br_patents),
            error=result.get('error')
        )
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        raise HTTPException(500, f"Error: {str(e)}")


# ============================================================================
# DEBUG ENDPOINTS
# ============================================================================

@app.get("/debug/files", tags=["Debug"])
async def list_debug_files():
    """List all captured HTML files"""
    try:
        files = []
        for f in DEBUG_DIR.glob("*.html"):
            stat = f.stat()
            files.append(DebugFileInfo(
                filename=f.name,
                size=stat.st_size,
                created=datetime.fromtimestamp(stat.st_ctime).isoformat(),
                url=f"/debug/download/{f.name}"
            ))
        
        return {
            "count": len(files),
            "files": sorted(files, key=lambda x: x.created, reverse=True)
        }
    except Exception as e:
        raise HTTPException(500, f"Error listing files: {str(e)}")


@app.get("/debug/html/{patent_id}", response_class=HTMLResponse, tags=["Debug"])
async def view_debug_html(patent_id: str):
    """View captured HTML in browser (with JavaScript removed to prevent redirects)"""
    try:
        files = list(DEBUG_DIR.glob(f"{patent_id}_*.html"))
        
        if not files:
            return HTMLResponse(
                f"<h1>No HTML captured for {patent_id}</h1>"
                f"<p>Make a POST request first to trigger capture</p>",
                status_code=404
            )
        
        latest = max(files, key=lambda f: f.stat().st_mtime)
        content = latest.read_text(encoding='utf-8')
        
        # ✅ REMOVE JAVASCRIPT to prevent redirects
        clean_content = remove_javascript_from_html(content)
        clean_content = clean_content.replace("{filename}", latest.name)
        
        logger.info(f"📄 Serving {patent_id} HTML without JavaScript (size: {len(clean_content)} bytes)")
        
        return HTMLResponse(content=clean_content)
        
    except Exception as e:
        raise HTTPException(500, f"Error: {str(e)}")


@app.get("/debug/download/{filename}", tags=["Debug"])
async def download_debug_file(filename: str):
    """Download debug HTML file"""
    file_path = DEBUG_DIR / filename
    
    if not file_path.exists():
        raise HTTPException(404, "File not found")
    
    return FileResponse(
        path=str(file_path),
        media_type="text/html",
        filename=filename
    )


@app.get("/debug/latest", response_class=HTMLResponse, tags=["Debug"])
async def view_latest_debug():
    """View most recent captured HTML (with JavaScript removed)"""
    try:
        files = list(DEBUG_DIR.glob("*.html"))
        
        if not files:
            return HTMLResponse(
                "<h1>No HTML files captured yet</h1>",
                status_code=404
            )
        
        latest = max(files, key=lambda f: f.stat().st_mtime)
        content = latest.read_text(encoding='utf-8')
        
        # ✅ REMOVE JAVASCRIPT to prevent redirects
        clean_content = remove_javascript_from_html(content)
        clean_content = clean_content.replace("{filename}", latest.name)
        
        logger.info(f"📄 Serving latest HTML without JavaScript: {latest.name}")
        
        return HTMLResponse(content=clean_content)
        
    except Exception as e:
        raise HTTPException(500, f"Error: {str(e)}")


@app.delete("/debug/clean", tags=["Debug"])
async def clean_debug_files():
    """Delete all debug HTML files"""
    try:
        files = list(DEBUG_DIR.glob("*.html"))
        deleted = 0
        
        for f in files:
            f.unlink()
            deleted += 1
        
        return {"deleted": deleted, "message": f"Removed {deleted} files"}
        
    except Exception as e:
        raise HTTPException(500, f"Error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
