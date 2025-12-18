"""
WO Number Search - Native Implementation
Substitui 100% dependência de n8n
Busca números WO em múltiplas fontes
"""
import asyncio
import logging
import re
from typing import List, Set, Dict, Any, Optional
from dataclasses import dataclass
import urllib.parse

import httpx
from bs4 import BeautifulSoup

from ..core.super_crawler import SuperCrawler, CrawlStrategy

logger = logging.getLogger(__name__)


@dataclass
class WOSearchResult:
    """Resultado de busca de WO numbers"""
    wo_numbers: Set[str]
    sources: Dict[str, int]  # source -> count
    total_found: int
    search_time: float


class WONumberSearcher:
    """
    Busca WO numbers em múltiplas fontes
    
    Fontes:
    1. Google Patents (scraping)
    2. Espacenet (EPO)
    3. Lens.org (API)
    4. Google Search via SerpAPI
    5. Direct pattern search
    
    100% independente de n8n!
    """
    
    # Padrão WO: WO + ano (4 dígitos) + número (6 dígitos)
    WO_PATTERN = re.compile(r'WO\s?(\d{4})\s?/?(\d{6,7})', re.IGNORECASE)
    
    def __init__(
        self,
        super_crawler: Optional[SuperCrawler] = None,
        serpapi_key: Optional[str] = None
    ):
        self.crawler = super_crawler or SuperCrawler(
            max_retries=5,
            timeout=60
        )
        self.serpapi_key = serpapi_key
    
    async def search_wo_numbers(
        self,
        molecule: str,
        dev_codes: List[str] = None,
        cas_number: Optional[str] = None,
        brand_name: Optional[str] = None
    ) -> WOSearchResult:
        """
        Busca WO numbers para uma molécula
        
        Estratégia multi-fonte paralela:
        - Google Patents
        - Google Search
        - Espacenet
        - Direct queries with company names
        """
        import time
        start = time.time()
        
        logger.info(f"🔍 Buscando WO numbers para: {molecule}")
        
        wo_numbers: Set[str] = set()
        sources: Dict[str, int] = {}
        
        # Prepare search queries
        queries = self._build_search_queries(
            molecule, dev_codes, cas_number, brand_name
        )
        
        logger.info(f"   📋 {len(queries)} queries preparadas")
        
        # Executa buscas em paralelo
        tasks = [
            self._search_google_patents(queries),
            self._search_espacenet(molecule),
            self._search_google_general(queries)
        ]
        
        if self.serpapi_key:
            tasks.append(self._search_serpapi(queries))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Agrega resultados
        for result in results:
            if isinstance(result, Exception):
                logger.warning(f"   ⚠️ Search error: {result}")
                continue
            
            if isinstance(result, dict):
                for wo in result.get("wo_numbers", []):
                    wo_numbers.add(wo)
                
                source = result.get("source", "unknown")
                count = result.get("count", 0)
                if count > 0:
                    sources[source] = count
        
        elapsed = time.time() - start
        
        logger.info(f"   ✅ {len(wo_numbers)} WO numbers únicos encontrados em {elapsed:.1f}s")
        logger.info(f"   📊 Fontes: {sources}")
        
        return WOSearchResult(
            wo_numbers=wo_numbers,
            sources=sources,
            total_found=len(wo_numbers),
            search_time=elapsed
        )
    
    def _build_search_queries(
        self,
        molecule: str,
        dev_codes: List[str] = None,
        cas_number: Optional[str] = None,
        brand_name: Optional[str] = None
    ) -> List[str]:
        """Constrói queries inteligentes"""
        queries = []
        
        # Query base
        queries.append(f"{molecule} patent WO")
        
        # Com anos específicos (últimos 15 anos)
        years = [2011, 2012, 2015, 2016, 2018, 2019, 2020, 2021, 2022, 2023]
        for year in years:
            queries.append(f"{molecule} WO{year}")
        
        # Com companies conhecidas
        companies = [
            "Bayer", "Merck", "Pfizer", "Novartis", "Roche",
            "AstraZeneca", "Bristol Myers", "Orion", "Takeda"
        ]
        for company in companies[:3]:  # Top 3
            queries.append(f"{molecule} {company} patent WO")
        
        # Com dev codes
        if dev_codes:
            for code in dev_codes[:3]:  # Top 3 dev codes
                queries.append(f"{code} patent WO")
        
        # Com brand name
        if brand_name:
            queries.append(f"{brand_name} patent WO")
        
        # Com CAS
        if cas_number:
            queries.append(f"{cas_number} patent WO")
        
        return queries
    
    async def _search_google_patents(
        self,
        queries: List[str]
    ) -> Dict[str, Any]:
        """Busca em Google Patents"""
        wo_numbers = set()
        
        logger.info(f"   🔍 Google Patents: {len(queries)} queries")
        
        for query in queries[:10]:  # Limita para não sobrecarregar
            try:
                url = f"https://patents.google.com/?q={urllib.parse.quote(query)}"
                
                result = await self.crawler.crawl(url)
                
                if result.success and result.html:
                    # Extrai WO numbers do HTML
                    found = self._extract_wo_from_html(result.html)
                    wo_numbers.update(found)
                    
                    if found:
                        logger.info(f"      ✅ Query '{query[:30]}...': {len(found)} WOs")
                
                # Delay entre queries
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.warning(f"      ⚠️ Query failed: {e}")
                continue
        
        return {
            "source": "google_patents",
            "wo_numbers": list(wo_numbers),
            "count": len(wo_numbers)
        }
    
    async def _search_espacenet(self, molecule: str) -> Dict[str, Any]:
        """Busca em Espacenet (EPO)"""
        wo_numbers = set()
        
        logger.info(f"   🔍 Espacenet")
        
        try:
            # URL de busca Espacenet
            url = f"https://worldwide.espacenet.com/searchResults?submitted=true&locale=en_EP&DB=EPODOC&ST=singleline&query={urllib.parse.quote(molecule)}"
            
            result = await self.crawler.crawl(url)
            
            if result.success and result.html:
                found = self._extract_wo_from_html(result.html)
                wo_numbers.update(found)
                
                logger.info(f"      ✅ {len(found)} WOs")
        
        except Exception as e:
            logger.warning(f"      ⚠️ Failed: {e}")
        
        return {
            "source": "espacenet",
            "wo_numbers": list(wo_numbers),
            "count": len(wo_numbers)
        }
    
    async def _search_google_general(
        self,
        queries: List[str]
    ) -> Dict[str, Any]:
        """Busca WO numbers via Google Search regular"""
        wo_numbers = set()
        
        logger.info(f"   🔍 Google Search")
        
        for query in queries[:5]:  # Limita queries
            try:
                url = f"https://www.google.com/search?q={urllib.parse.quote(query + ' site:patents.google.com OR site:espacenet.com')}"
                
                result = await self.crawler.crawl(url)
                
                if result.success and result.html:
                    found = self._extract_wo_from_html(result.html)
                    wo_numbers.update(found)
                
                await asyncio.sleep(2)  # Rate limiting
                
            except Exception as e:
                logger.warning(f"      ⚠️ Query failed: {e}")
                continue
        
        return {
            "source": "google_search",
            "wo_numbers": list(wo_numbers),
            "count": len(wo_numbers)
        }
    
    async def _search_serpapi(
        self,
        queries: List[str]
    ) -> Dict[str, Any]:
        """Busca via SerpAPI (se disponível)"""
        if not self.serpapi_key:
            return {"source": "serpapi", "wo_numbers": [], "count": 0}
        
        wo_numbers = set()
        
        logger.info(f"   🔍 SerpAPI")
        
        for query in queries[:5]:  # Limita por quota
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(
                        "https://serpapi.com/search.json",
                        params={
                            "engine": "google_patents",
                            "q": query,
                            "api_key": self.serpapi_key,
                            "num": 20
                        }
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        # Extrai de resultados
                        for result in data.get("organic_results", []):
                            patent_id = result.get("patent_id", "")
                            if patent_id.startswith("WO"):
                                wo_numbers.add(patent_id)
                            
                            # Também busca no snippet/title
                            text = result.get("title", "") + " " + result.get("snippet", "")
                            found = self._extract_wo_from_text(text)
                            wo_numbers.update(found)
                
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.warning(f"      ⚠️ SerpAPI error: {e}")
                continue
        
        return {
            "source": "serpapi",
            "wo_numbers": list(wo_numbers),
            "count": len(wo_numbers)
        }
    
    def _extract_wo_from_html(self, html: str) -> Set[str]:
        """Extrai WO numbers de HTML"""
        wo_numbers = set()
        
        # Parse HTML
        soup = BeautifulSoup(html, "lxml")
        
        # Remove scripts e styles
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Pega texto
        text = soup.get_text()
        
        # Extrai WO numbers
        wo_numbers = self._extract_wo_from_text(text)
        
        return wo_numbers
    
    def _extract_wo_from_text(self, text: str) -> Set[str]:
        """Extrai WO numbers de texto"""
        wo_numbers = set()
        
        # Encontra matches
        matches = self.WO_PATTERN.findall(text)
        
        for year, number in matches:
            # Normaliza: WO + ano + número (sem espaços)
            wo = f"WO{year}{number}"
            
            # Valida
            if self._validate_wo_number(wo):
                wo_numbers.add(wo)
        
        return wo_numbers
    
    def _validate_wo_number(self, wo: str) -> bool:
        """Valida se WO number é válido"""
        # Formato: WO + 4 dígitos (ano) + 6-7 dígitos (número)
        if not wo.startswith("WO"):
            return False
        
        wo_clean = wo[2:]  # Remove "WO"
        
        # Deve ter 10-11 dígitos no total
        if not wo_clean.isdigit():
            return False
        
        if len(wo_clean) < 10 or len(wo_clean) > 11:
            return False
        
        # Ano deve ser razoável (1978-2025)
        year = int(wo_clean[:4])
        if year < 1978 or year > 2025:
            return False
        
        return True
    
    async def close(self):
        """Fecha recursos"""
        if self.crawler:
            await self.crawler.close()
