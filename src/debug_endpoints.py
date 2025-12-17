"""Debug endpoints for HTML/Screenshot retrieval"""
import os
import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/debug", tags=["debug"])

DEBUG_DIR = "/tmp/playwright_debug"

@router.get("/files")
async def list_debug_files():
    """List all saved debug HTML and screenshot files"""
    try:
        if not os.path.exists(DEBUG_DIR):
            return {"files": [], "message": "No debug files yet"}
        
        files = []
        for filename in os.listdir(DEBUG_DIR):
            filepath = os.path.join(DEBUG_DIR, filename)
            size = os.path.getsize(filepath)
            files.append({
                "filename": filename,
                "size_bytes": size,
                "size_kb": round(size / 1024, 2),
                "url": f"/debug/download/{filename}"
            })
        
        return {
            "files": files,
            "total": len(files),
            "directory": DEBUG_DIR
        }
    except Exception as e:
        logger.error(f"Error listing debug files: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/html/{patent_id}")
async def get_debug_html(patent_id: str):
    """Get the most recent debug HTML for a patent ID"""
    try:
        if not os.path.exists(DEBUG_DIR):
            raise HTTPException(status_code=404, detail="No debug directory found")
        
        # Find most recent HTML file for this patent
        html_files = [f for f in os.listdir(DEBUG_DIR) 
                      if f.startswith(patent_id) and f.endswith('.html')]
        
        if not html_files:
            raise HTTPException(status_code=404, 
                              detail=f"No HTML file found for {patent_id}")
        
        # Get most recent (by filename timestamp)
        html_files.sort(reverse=True)
        latest_file = html_files[0]
        filepath = os.path.join(DEBUG_DIR, latest_file)
        
        with open(filepath, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # Return as HTML response with stats
        stats = {
            "filename": latest_file,
            "size_bytes": len(html_content),
            "contains_docdbFamily": "docdbFamily" in html_content,
            "contains_itemprop": "itemprop" in html_content,
            "patent_id": patent_id
        }
        
        # Return HTML with stats in comment
        return HTMLResponse(
            content=f"<!-- DEBUG STATS: {stats} -->\n{html_content}",
            headers={"X-Debug-Stats": str(stats)}
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"File not found: {patent_id}")
    except Exception as e:
        logger.error(f"Error retrieving HTML: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/download/{filename}")
async def download_debug_file(filename: str):
    """Download a specific debug file"""
    filepath = os.path.join(DEBUG_DIR, filename)
    
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")
    
    if not filepath.startswith(DEBUG_DIR):
        raise HTTPException(status_code=403, detail="Access denied")
    
    return FileResponse(
        filepath,
        media_type="text/html" if filename.endswith('.html') else "image/png",
        filename=filename
    )

@router.get("/latest")
async def get_latest_debug_files():
    """Get the most recent HTML and screenshot files"""
    try:
        if not os.path.exists(DEBUG_DIR):
            return {"message": "No debug files yet"}
        
        files = sorted(os.listdir(DEBUG_DIR), reverse=True)
        
        latest_html = next((f for f in files if f.endswith('.html')), None)
        latest_png = next((f for f in files if f.endswith('.png')), None)
        
        return {
            "latest_html": {
                "filename": latest_html,
                "url": f"/debug/download/{latest_html}" if latest_html else None
            } if latest_html else None,
            "latest_screenshot": {
                "filename": latest_png,
                "url": f"/debug/download/{latest_png}" if latest_png else None
            } if latest_png else None,
            "all_files_url": "/debug/files"
        }
    except Exception as e:
        logger.error(f"Error getting latest files: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/clean")
async def clean_debug_files():
    """Delete all debug files"""
    try:
        if not os.path.exists(DEBUG_DIR):
            return {"message": "Debug directory doesn't exist"}
        
        count = 0
        for filename in os.listdir(DEBUG_DIR):
            filepath = os.path.join(DEBUG_DIR, filename)
            os.remove(filepath)
            count += 1
        
        return {"deleted": count, "message": f"Deleted {count} debug files"}
    except Exception as e:
        logger.error(f"Error cleaning debug files: {e}")
        raise HTTPException(status_code=500, detail=str(e))
