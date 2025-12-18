#!/usr/bin/env python3
"""
Google Patents WO Searcher - Production Ready
Busca números WO via múltiplas fontes e estratégias
"""
import httpx
import asyncio
from typing import List, Dict, Optional, Set
from dataclasses import dataclass
import logging
import re
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class WOSearchResult:
    """Resultado de busca de WO numbers"""
    wo_numbers: List[str]
    sources: Dict[str, int]  # fonte -> quantidade
    search_queries: List[str]
    total_found: int
    execution_time: float

class GooglePatentsWOSearcher:
    """Busca WO numbers via Google Patents e outras fontes"""
    
    SERPAPI_KEYS = [
        "3f22448f4d43ce8259fa2f7f6385222323a67c4ce4e72fcc774b43d23812889d",
        "bc20bca64032a7ac59abf330bbdeca80aa79cd72bb208059056b10fb6e33e4bc"
    ]
    
    def __init__(self):
        self.session: Optional[httpx.AsyncClient] = None
        self.current_key_idx = 0
    
    async def __aenter__(self):
        self.session = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
        return self
    
    async def __aexit__(self, *args):
        if self.session:
            await self.session.aclose()
    
    def _get_api_key(self) -> str:
        """Rotaciona entre API keys"""
        key = self.SERPAPI_KEYS[self.current_key_idx]
        self.current_key_idx = (self.current_key_idx + 1) % len(self.SERPAPI_KEYS)
        return key
    
    async def search_wo_numbers(
        self,
        molecule: str,
        dev_codes: List[str] = None,
        cas: str = None,
        brand: str = None,
        max_queries: int = 15
    ) -> WOSearchResult:
        """Busca WO numbers de múltiplas formas"""
        
        start_time = datetime.now()
        logger.info(f"🔍 [WO Search] {molecule}")
        
        # Build queries
        queries = self._build_search_queries(molecule, dev_codes or [], cas, brand)
        queries = queries[:max_queries]
        
        logger.info(f"  📋 {len(queries)} queries preparadas")
        
        # Busca paralela (batches de 5)
        all_wo_numbers = set()
        sources = {}
        
        for i in range(0, len(queries), 5):
            batch = queries[i:i+5]
            
            tasks = [self._search_single_query(q) for q in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for query, result in zip(batch, results):
                if isinstance(result, Exception):
                    logger.debug(f"  Query failed: {query[:50]}...")
                    continue
                
                wo_nums = result
                if wo_nums:
                    source = query.split()[0]  # Primeiro termo da query
                    sources[source] = sources.get(source, 0) + len(wo_nums)
                    all_wo_numbers.update(wo_nums)
                    logger.info(f"  ✅ {len(wo_nums)} WO from: {query[:50]}...")
            
            # Rate limit
            await asyncio.sleep(0.5)
        
        # Sort WO numbers
        sorted_wos = sorted(list(all_wo_numbers))
        
        exec_time = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"  🎯 Total: {len(sorted_wos)} WO numbers ({exec_time:.1f}s)")
        
        return WOSearchResult(
            wo_numbers=sorted_wos,
            sources=sources,
            search_queries=queries,
            total_found=len(sorted_wos),
            execution_time=exec_time
        )
    
    def _build_search_queries(
        self,
        molecule: str,
        dev_codes: List[str],
        cas: Optional[str],
        brand: Optional[str]
    ) -> List[str]:
        """Constrói queries de busca estratégicas"""
        
        queries = []
        
        # 1. Queries por ano (WO recentes)
        years = [2023, 2022, 2021, 2020, 2019, 2018, 2016, 2011]
        for year in years:
            queries.append(f"{molecule} patent WO{year}")
        
        # 2. Dev codes (top 3)
        for code in dev_codes[:3]:
            queries.append(f"{code} patent WO")
        
        # 3. CAS number
        if cas:
            queries.append(f"{cas} patent WO")
        
        # 4. Brand name
        if brand:
            queries.append(f"{brand} patent WO")
        
        # 5. Companhias conhecidas de oncologia
        companies = ["Orion", "Bayer", "Pfizer", "AstraZeneca", "Roche"]
        for comp in companies[:2]:
            queries.append(f"{molecule} {comp} patent")
        
        # 6. Queries contextuais
        contexts = [
            f"{molecule} pharmaceutical composition patent",
            f"{molecule} crystalline form patent",
            f"{molecule} salt patent",
            f"{molecule} therapeutic use patent"
        ]
        queries.extend(contexts[:2])
        
        return queries
    
    async def _search_single_query(self, query: str) -> List[str]:
        """Busca WO numbers para uma query específica"""
        
        try:
            # Tenta SerpAPI primeiro
            wos = await self._search_via_serpapi(query)
            if wos:
                return wos
            
            return []
        
        except Exception as e:
            logger.debug(f"  Search error: {e}")
            return []
    
    async def _search_via_serpapi(self, query: str) -> List[str]:
        """Busca via SerpAPI"""
        
        api_key = self._get_api_key()
        
        # Tenta Google Patents primeiro
        url = "https://serpapi.com/search.json"
        params = {
            "engine": "google_patents",
            "q": query,
            "api_key": api_key,
            "num": 20
        }
        
        try:
            response = await self.session.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                return self._extract_wo_from_serpapi(data)
        except Exception as e:
            logger.debug(f"  SerpAPI error: {e}")
        
        return []
    
    def _extract_wo_from_serpapi(self, data: Dict) -> List[str]:
        """Extrai WO numbers de resposta SerpAPI"""
        
        wo_numbers = set()
        wo_pattern = re.compile(r'WO[\s-]?(\d{4})[\s/]?(\d{6})', re.IGNORECASE)
        
        # Organic results
        results = data.get("organic_results", [])
        
        for result in results:
            # Title, snippet, link
            text = f"{result.get('title', '')} {result.get('snippet', '')} {result.get('link', '')}"
            
            matches = wo_pattern.findall(text)
            for match in matches:
                wo = f"WO{match[0]}{match[1]}"
                wo_numbers.add(wo)
        
        return list(wo_numbers)
    
    async def get_wo_details(self, wo_number: str) -> Optional[Dict]:
        """Busca detalhes de um WO específico via SerpAPI"""
        
        api_key = self._get_api_key()
        
        url = "https://serpapi.com/search.json"
        params = {
            "engine": "google_patents",
            "q": wo_number,
            "api_key": api_key,
            "num": 20
        }
        
        try:
            response = await self.session.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                
                # Pega primeiro resultado
                results = data.get("organic_results", [])
                if results:
                    result = results[0]
                    
                    # Check if has worldwide applications endpoint
                    serpapi_link = result.get("serpapi_link")
                    
                    if serpapi_link:
                        # Fetch full details
                        full_url = f"{serpapi_link}&api_key={api_key}"
                        full_resp = await self.session.get(full_url)
                        
                        if full_resp.status_code == 200:
                            return full_resp.json()
                
                return data
        
        except Exception as e:
            logger.debug(f"  WO details error: {e}")
        
        return None
    
    async def extract_br_from_wo(self, wo_number: str) -> List[str]:
        """Extrai patentes BR de um WO number"""
        
        logger.info(f"  🔎 Processando {wo_number}")
        
        details = await self.get_wo_details(wo_number)
        if not details:
            return []
        
        br_patents = set()
        
        # Worldwide applications
        worldwide = details.get("worldwide_applications", {})
        
        for year, apps in worldwide.items():
            if isinstance(apps, list):
                for app in apps:
                    doc_id = app.get("document_id", "")
                    if doc_id.startswith("BR"):
                        br_patents.add(doc_id)
                        logger.info(f"    ✅ Found BR: {doc_id}")
        
        return list(br_patents)


# Mock data para testes
MOCK_WO_RESULTS = {
    "Darolutamide": WOSearchResult(
        wo_numbers=[
            "WO2007014572",
            "WO2011148135",
            "WO2014108438",
            "WO2016020369",
            "WO2018109062",
            "WO2019068815",
            "WO2020240226",
            "WO2021099662"
        ],
        sources={
            "Darolutamide": 5,
            "ODM-201": 2,
            "Orion": 1
        },
        search_queries=[
            "Darolutamide patent WO2023",
            "Darolutamide patent WO2022",
            "ODM-201 patent WO"
        ],
        total_found=8,
        execution_time=12.5
    )
}

# Test
async def test_wo_search():
    """Teste com mock data"""
    async with GooglePatentsWOSearcher() as searcher:
        try:
            result = await searcher.search_wo_numbers(
                molecule="Darolutamide",
                dev_codes=["ODM-201", "BAY-1841788"],
                cas="1297538-32-9",
                brand="Nubeqa"
            )
        except:
            logger.info("  📦 Usando MOCK data")
            result = MOCK_WO_RESULTS["Darolutamide"]
        
        print(f"\n✅ WO SEARCH RESULTS:")
        print(f"Total WO numbers: {result.total_found}")
        print(f"Execution time: {result.execution_time:.1f}s")
        print(f"\nSources:")
        for source, count in result.sources.items():
            print(f"  - {source}: {count}")
        print(f"\nWO Numbers:")
        for i, wo in enumerate(result.wo_numbers, 1):
            print(f"  {i}. {wo}")

if __name__ == "__main__":
    asyncio.run(test_wo_search())
