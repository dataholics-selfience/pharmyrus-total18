"""
Pharmyrus Crawlers Package
Initializes browser pools for patent data extraction
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Global instances (will be initialized on app startup)
google_patents_pool: Optional['GooglePatentsCrawlerPool'] = None
google_patents_client: Optional['GooglePatentsCrawler'] = None

def init_crawlers():
    """
    Initialize crawler pools
    Called during FastAPI startup
    """
    global google_patents_pool, google_patents_client
    
    try:
        logger.info("🔧 Initializing Google Patents crawler pool...")
        
        from .google_patents_pool import GooglePatentsCrawlerPool
        from .google_patents_playwright import GooglePatentsCrawler
        
        # Initialize pool with 2 crawlers
        google_patents_pool = GooglePatentsCrawlerPool(pool_size=2)
        
        # Initialize single client for simple requests
        google_patents_client = GooglePatentsCrawler()
        
        logger.info("✅ Crawler pools initialized successfully")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize crawlers: {e}")
        raise

async def shutdown_crawlers():
    """
    Cleanup crawler resources
    Called during FastAPI shutdown
    """
    global google_patents_pool, google_patents_client
    
    try:
        if google_patents_pool:
            await google_patents_pool.close_all()
            logger.info("✅ Google Patents pool closed")
        
        if google_patents_client:
            await google_patents_client.close()
            logger.info("✅ Google Patents client closed")
            
    except Exception as e:
        logger.error(f"⚠️  Error during crawler shutdown: {e}")

__all__ = [
    'google_patents_pool',
    'google_patents_client',
    'init_crawlers',
    'shutdown_crawlers'
]
