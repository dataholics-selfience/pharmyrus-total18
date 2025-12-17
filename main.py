"""
Pharmyrus v4.0 - Patent Intelligence Platform
Main entry point for FastAPI application
"""

import uvicorn
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("🚀 Starting Pharmyrus v4.0...")
    
    uvicorn.run(
        "src.api_service:app",
        host="0.0.0.0",
        port=8080,
        log_level="info",
        access_log=True
    )
