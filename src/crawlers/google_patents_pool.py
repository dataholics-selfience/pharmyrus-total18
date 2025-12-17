"""
Google Patents Crawler Pool
Manages multiple browser instances for parallel processing
"""

import asyncio
import logging
from typing import Dict, Any, List
from .google_patents_playwright import GooglePatentsCrawler

logger = logging.getLogger(__name__)

class GooglePatentsCrawlerPool:
    """
    Pool of GooglePatentsCrawler instances for parallel processing
    """
    
    def __init__(self, pool_size: int = 2):
        """
        Initialize crawler pool
        
        Args:
            pool_size: Number of crawler instances in the pool
        """
        self.pool_size = pool_size
        self.crawlers: List[GooglePatentsCrawler] = []
        self._lock = asyncio.Lock()
        self._initialized = False
        
        logger.info(f"🏊 Creating Google Patents crawler pool (size={pool_size})")
    
    async def initialize(self):
        """Initialize all crawlers in the pool"""
        if self._initialized:
            logger.warning("Pool already initialized")
            return
        
        try:
            logger.info(f"🔧 Initializing {self.pool_size} crawlers...")
            
            for i in range(self.pool_size):
                crawler = GooglePatentsCrawler()
                await crawler.initialize()
                self.crawlers.append(crawler)
                logger.info(f"  ✅ Google Patents crawler {i+1}/{self.pool_size} ready")
            
            self._initialized = True
            logger.info(f"✅ Google Patents crawler pool initialized ({self.pool_size} instances)")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize crawler pool: {e}")
            # Cleanup any initialized crawlers
            await self.close_all()
            raise
    
    async def get_crawler(self) -> GooglePatentsCrawler:
        """
        Get an available crawler from the pool
        Simple round-robin selection
        """
        if not self._initialized:
            await self.initialize()
        
        if not self.crawlers:
            raise RuntimeError("No crawlers available in pool")
        
        # Simple round-robin: take first available
        async with self._lock:
            return self.crawlers[0] if self.crawlers else None
    
    async def fetch_patent_details(self, patent_id: str) -> Dict[str, Any]:
        """
        Fetch patent details using an available crawler from the pool
        
        Args:
            patent_id: Patent publication number
            
        Returns:
            Dictionary with patent data
        """
        crawler = await self.get_crawler()
        if not crawler:
            return {
                'patent_id': patent_id,
                'success': False,
                'error': 'No crawler available',
                'data': {},
                'family_members': []
            }
        
        try:
            result = await crawler.get_patent_details(patent_id)
            return result
        except Exception as e:
            logger.error(f"Error fetching patent {patent_id}: {e}")
            return {
                'patent_id': patent_id,
                'success': False,
                'error': str(e),
                'data': {},
                'family_members': []
            }
    
    async def close_all(self):
        """Close all crawlers in the pool"""
        logger.info("🔌 Closing crawler pool...")
        
        for i, crawler in enumerate(self.crawlers):
            try:
                await crawler.close()
                logger.info(f"  ✅ Crawler {i+1}/{self.pool_size} closed")
            except Exception as e:
                logger.error(f"  ⚠️  Error closing crawler {i+1}: {e}")
        
        self.crawlers.clear()
        self._initialized = False
        logger.info("✅ Crawler pool closed")
    
    def __len__(self):
        """Return number of crawlers in pool"""
        return len(self.crawlers)

# Global pool instance (initialized in __init__.py)
google_patents_pool: GooglePatentsCrawlerPool = None
