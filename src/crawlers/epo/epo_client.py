"""
EPO Open Patent Services (OPS) API Client
Implements OAuth2 authentication, token refresh, and patent family extraction
"""
import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import aiohttp
from dataclasses import dataclass
import xml.etree.ElementTree as ET

from ...core.circuit_breaker import CircuitBreaker, RetryStrategy, RateLimiter

logger = logging.getLogger(__name__)


@dataclass
class EPOToken:
    """EPO OAuth2 token"""
    access_token: str
    expires_at: datetime
    token_type: str = "Bearer"
    
    def is_expired(self) -> bool:
        """Check if token is expired (with 2-minute buffer)"""
        return datetime.now() >= self.expires_at - timedelta(minutes=2)


class EPOClient:
    """
    EPO OPS API Client with:
    - OAuth2 token management
    - Automatic token refresh
    - Circuit breaker protection
    - Rate limiting
    - Patent family extraction
    """
    
    BASE_URL = "https://ops.epo.org/3.2"
    AUTH_URL = "https://ops.epo.org/3.2/auth/accesstoken"
    
    def __init__(
        self,
        consumer_key: str,
        consumer_secret: str,
        rate_limit_per_minute: int = 50
    ):
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        
        self._token: Optional[EPOToken] = None
        self._session: Optional[aiohttp.ClientSession] = None
        
        # Circuit breaker for API calls
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            timeout=30.0,
            name="EPO"
        )
        
        # Retry strategy
        self.retry_strategy = RetryStrategy(
            max_attempts=3,
            base_delay=1.0,
            max_delay=10.0
        )
        
        # Rate limiter (50 requests/minute)
        self.rate_limiter = RateLimiter({
            'epo': {'per_minute': rate_limit_per_minute}
        })
    
    async def __aenter__(self):
        """Async context manager entry"""
        self._session = aiohttp.ClientSession()
        await self._ensure_token()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self._session:
            await self._session.close()
    
    async def _get_token(self) -> EPOToken:
        """
        Get OAuth2 access token
        
        EPO tokens expire after 20 minutes
        """
        logger.info("🔑 [EPO] Requesting OAuth2 token")
        
        auth = aiohttp.BasicAuth(self.consumer_key, self.consumer_secret)
        
        data = {'grant_type': 'client_credentials'}
        
        async with self._session.post(
            self.AUTH_URL,
            auth=auth,
            data=data,
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        ) as response:
            response.raise_for_status()
            result = await response.json()
            
            # EPO tokens last 20 minutes
            expires_at = datetime.now() + timedelta(seconds=result.get('expires_in', 1200))
            
            token = EPOToken(
                access_token=result['access_token'],
                expires_at=expires_at
            )
            
            logger.info(f"✅ [EPO] Token acquired (expires: {expires_at.strftime('%H:%M:%S')})")
            
            return token
    
    async def _ensure_token(self):
        """Ensure we have a valid token, refresh if needed"""
        if self._token is None or self._token.is_expired():
            self._token = await self._get_token()
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        headers: Optional[Dict] = None
    ) -> Any:
        """
        Make authenticated request to EPO API
        
        Args:
            method: HTTP method
            endpoint: API endpoint (relative to BASE_URL)
            params: Query parameters
            headers: Additional headers
            
        Returns:
            Response data (JSON or text)
        """
        await self._ensure_token()
        await self.rate_limiter.wait_if_needed('epo')
        
        url = f"{self.BASE_URL}/{endpoint}"
        
        request_headers = {
            'Authorization': f'Bearer {self._token.access_token}',
            'Accept': 'application/json'
        }
        
        if headers:
            request_headers.update(headers)
        
        async def _request():
            async with self._session.request(
                method,
                url,
                params=params,
                headers=request_headers,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                
                # Check traffic light system (X-Throttling-Control header)
                throttle = response.headers.get('X-Throttling-Control', 'green')
                if throttle in ['yellow', 'red']:
                    logger.warning(f"⚠️ [EPO] Traffic light: {throttle}")
                    if throttle == 'red':
                        await asyncio.sleep(5)  # Back off
                
                response.raise_for_status()
                
                # Try JSON first, fall back to text
                content_type = response.headers.get('Content-Type', '')
                if 'json' in content_type:
                    return await response.json()
                else:
                    return await response.text()
        
        # Execute with circuit breaker and retry
        return await self.circuit_breaker.call(
            self.retry_strategy.execute,
            _request
        )
    
    async def get_patent_family(
        self,
        publication_number: str,
        format: str = "docdb"
    ) -> Dict[str, Any]:
        """
        Get patent family for a publication number
        
        Args:
            publication_number: Patent number (e.g., "WO2011156378")
            format: Number format ("docdb", "epodoc", or "original")
            
        Returns:
            Patent family data
        """
        logger.info(f"👨‍👩‍👧‍👦 [EPO] Fetching family for {publication_number}")
        
        endpoint = f"rest-services/family/publication/{format}/{publication_number}"
        
        try:
            result = await self._make_request('GET', endpoint)
            return result
        except Exception as e:
            logger.error(f"❌ [EPO] Family fetch failed: {str(e)}")
            return {}
    
    async def get_worldwide_applications(
        self,
        publication_number: str
    ) -> List[Dict[str, str]]:
        """
        Get worldwide (national phase) applications from WO number
        
        Args:
            publication_number: WO number (e.g., "WO2011156378")
            
        Returns:
            List of national applications with country codes and numbers
        """
        logger.info(f"🌍 [EPO] Fetching worldwide apps for {publication_number}")
        
        family = await self.get_patent_family(publication_number)
        
        applications = []
        
        try:
            # Parse family data
            if 'ops:world-patent-data' in family:
                family_data = family['ops:world-patent-data']
                
                # Navigate to family members
                if 'ops:patent-family' in family_data:
                    patent_family = family_data['ops:patent-family']
                    
                    # Get family members
                    members = patent_family.get('ops:family-member', [])
                    
                    # Ensure it's a list
                    if not isinstance(members, list):
                        members = [members]
                    
                    for member in members:
                        # Extract publication reference
                        pub_ref = member.get('publication-reference', {})
                        doc_id = pub_ref.get('document-id', {})
                        
                        if isinstance(doc_id, list):
                            doc_id = doc_id[0]  # Take first format
                        
                        country = doc_id.get('country', {}).get('$', '')
                        number = doc_id.get('doc-number', {}).get('$', '')
                        kind = doc_id.get('kind', {}).get('$', '')
                        date = doc_id.get('date', {}).get('$', '')
                        
                        if country and number:
                            applications.append({
                                'country': country,
                                'number': number,
                                'kind': kind,
                                'date': date,
                                'publication_number': f"{country}{number}"
                            })
            
            logger.info(f"✅ [EPO] Found {len(applications)} family members")
            
            return applications
            
        except Exception as e:
            logger.error(f"❌ [EPO] Error parsing family data: {str(e)}")
            return []
    
    async def get_br_patents_from_wo(
        self,
        wo_number: str
    ) -> List[Dict[str, str]]:
        """
        Extract Brazilian (BR) patents from WO number
        
        Args:
            wo_number: WO number (e.g., "WO2011156378")
            
        Returns:
            List of BR patents with numbers and details
        """
        logger.info(f"🇧🇷 [EPO] Extracting BR patents from {wo_number}")
        
        worldwide = await self.get_worldwide_applications(wo_number)
        
        br_patents = [
            app for app in worldwide
            if app['country'] == 'BR'
        ]
        
        logger.info(f"✅ [EPO] Found {len(br_patents)} BR patents")
        
        return br_patents
    
    async def batch_get_br_patents(
        self,
        wo_numbers: List[str],
        max_concurrent: int = 5
    ) -> Dict[str, List[Dict[str, str]]]:
        """
        Get BR patents for multiple WO numbers in parallel
        
        Args:
            wo_numbers: List of WO numbers
            max_concurrent: Maximum concurrent requests
            
        Returns:
            Dict mapping WO number -> list of BR patents
        """
        logger.info(f"⚡ [EPO] Batch fetching {len(wo_numbers)} WO numbers ({max_concurrent} concurrent)")
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def _fetch_one(wo: str) -> tuple:
            async with semaphore:
                try:
                    br_patents = await self.get_br_patents_from_wo(wo)
                    return (wo, br_patents)
                except Exception as e:
                    logger.error(f"❌ Error fetching {wo}: {str(e)}")
                    return (wo, [])
        
        tasks = [_fetch_one(wo) for wo in wo_numbers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Build result dict
        result_dict = {}
        for item in results:
            if isinstance(item, Exception):
                continue
            wo, patents = item
            result_dict[wo] = patents
        
        total_br = sum(len(patents) for patents in result_dict.values())
        logger.info(f"✅ [EPO] Batch complete: {total_br} total BR patents")
        
        return result_dict
