"""
Parallel Patent Search Orchestrator
Coordinates multiple data sources with maximum parallelization
"""
import asyncio
import logging
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, field
from datetime import datetime
import aiohttp

from ..crawlers.epo.epo_client import EPOClient
from .circuit_breaker import CircuitBreaker, RetryStrategy

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Patent search result"""
    publication_number: str
    country: str
    title: str = ""
    abstract: str = ""
    applicant: str = ""
    inventors: List[str] = field(default_factory=list)
    filing_date: str = ""
    publication_date: str = ""
    classifications: List[str] = field(default_factory=list)
    source: str = ""
    link: str = ""
    raw_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MoleculeData:
    """Molecular data from PubChem"""
    name: str
    cas_number: Optional[str] = None
    dev_codes: List[str] = field(default_factory=list)
    synonyms: List[str] = field(default_factory=list)
    molecular_formula: Optional[str] = None
    molecular_weight: Optional[float] = None
    smiles: Optional[str] = None
    inchikey: Optional[str] = None


class ParallelOrchestrator:
    """
    Orchestrates parallel patent searches across multiple sources
    
    Implements:
    - Concurrent multi-source searches
    - WO number extraction and expansion
    - BR patent filtering and enrichment
    - Deduplication and quality scoring
    """
    
    def __init__(
        self,
        epo_key: str,
        epo_secret: str,
        inpi_crawler_url: str = "https://crawler3-production.up.railway.app",
        n8n_base_url: Optional[str] = None
    ):
        self.epo_key = epo_key
        self.epo_secret = epo_secret
        self.inpi_crawler_url = inpi_crawler_url
        self.n8n_base_url = n8n_base_url
        
        # Will be initialized in context manager
        self._epo_client: Optional[EPOClient] = None
        self._session: Optional[aiohttp.ClientSession] = None
        
        # Circuit breakers for each service
        self.cb_inpi = CircuitBreaker(name="INPI", timeout=60.0)
        self.cb_pubchem = CircuitBreaker(name="PubChem", timeout=30.0)
        self.cb_google = CircuitBreaker(name="Google", timeout=30.0)
        
        # Retry strategy
        self.retry = RetryStrategy(max_attempts=3, base_delay=0.5)
    
    async def __aenter__(self):
        """Initialize async resources"""
        self._session = aiohttp.ClientSession()
        self._epo_client = EPOClient(self.epo_key, self.epo_secret)
        await self._epo_client.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Cleanup async resources"""
        if self._epo_client:
            await self._epo_client.__aexit__(exc_type, exc_val, exc_tb)
        if self._session:
            await self._session.close()
    
    async def get_pubchem_data(self, molecule: str) -> Optional[MoleculeData]:
        """
        Get molecular data from PubChem
        
        Args:
            molecule: Molecule name
            
        Returns:
            MoleculeData or None if not found
        """
        logger.info(f"🧪 [PubChem] Searching: {molecule}")
        
        try:
            url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{molecule}/synonyms/JSON"
            
            async def _fetch():
                async with self._session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 404:
                        logger.warning(f"⚠️ [PubChem] Molecule not found: {molecule}")
                        return None
                    
                    response.raise_for_status()
                    data = await response.json()
                    return data
            
            data = await self.cb_pubchem.call(self.retry.execute, _fetch)
            
            if not data or 'InformationList' not in data:
                return None
            
            # Extract data
            info = data['InformationList']['Information'][0]
            synonyms = info.get('Synonym', [])
            
            # Extract CAS number
            cas = None
            for syn in synonyms:
                if isinstance(syn, str) and '-' in syn:
                    parts = syn.split('-')
                    if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit() and parts[2].isdigit():
                        cas = syn
                        break
            
            # Extract dev codes (pattern: XX-12345 or XXX12345)
            dev_codes = []
            for syn in synonyms[:100]:  # Limit to first 100
                if isinstance(syn, str) and 3 <= len(syn) <= 20:
                    # Patterns like: AB-1234, ABC-123, XY12345
                    if (('-' in syn and syn[0].isalpha()) or 
                        (syn[:2].isalpha() and syn[2:].replace('-', '').isdigit())):
                        if 'CID' not in syn:
                            dev_codes.append(syn)
            
            mol_data = MoleculeData(
                name=molecule,
                cas_number=cas,
                dev_codes=dev_codes[:10],  # Top 10
                synonyms=synonyms[:50]  # Top 50
            )
            
            logger.info(f"✅ [PubChem] Found: CAS={cas}, {len(dev_codes)} dev codes")
            
            return mol_data
            
        except Exception as e:
            logger.error(f"❌ [PubChem] Error: {str(e)}")
            return None
    
    async def search_inpi(
        self,
        medicine: str,
        variations: Optional[List[str]] = None
    ) -> List[SearchResult]:
        """
        Search INPI crawler (existing Railway endpoint)
        
        Args:
            medicine: Medicine/molecule name
            variations: Additional search terms
            
        Returns:
            List of BR patents
        """
        logger.info(f"🇧🇷 [INPI] Searching: {medicine}")
        
        search_terms = [medicine]
        if variations:
            search_terms.extend(variations)
        
        all_results = []
        seen_numbers = set()
        
        for term in search_terms:
            try:
                url = f"{self.inpi_crawler_url}/api/data/inpi/patents"
                params = {'medicine': term}
                
                async def _fetch():
                    async with self._session.get(
                        url,
                        params=params,
                        timeout=aiohttp.ClientTimeout(total=90)
                    ) as response:
                        response.raise_for_status()
                        return await response.json()
                
                data = await self.cb_inpi.call(self.retry.execute, _fetch)
                
                if data and 'data' in data and isinstance(data['data'], list):
                    for item in data['data']:
                        pub_num = item.get('title', '').replace(' ', '-')
                        
                        # Deduplicate
                        if pub_num in seen_numbers:
                            continue
                        seen_numbers.add(pub_num)
                        
                        result = SearchResult(
                            publication_number=pub_num,
                            country='BR',
                            title=item.get('applicant', ''),
                            abstract=item.get('fullText', '')[:500],
                            filing_date=item.get('depositDate', ''),
                            source='inpi_crawler',
                            link=f"https://busca.inpi.gov.br/pePI/servlet/PatenteServletController?Action=detail&CodPedido={pub_num}",
                            raw_data=item
                        )
                        all_results.append(result)
                
                logger.info(f"  ✓ Term '{term}': {len(data.get('data', []))} results")
                
            except Exception as e:
                logger.error(f"  ✗ Term '{term}' failed: {str(e)}")
                continue
        
        logger.info(f"✅ [INPI] Total unique: {len(all_results)}")
        
        return all_results
    
    async def search_wo_numbers(
        self,
        molecule: str,
        dev_codes: List[str]
    ) -> List[str]:
        """
        Search for WO numbers using multiple strategies
        
        Args:
            molecule: Molecule name
            dev_codes: Development codes
            
        Returns:
            List of WO numbers
        """
        logger.info(f"🔍 [WO Search] Finding WO numbers for: {molecule}")
        
        # Build search queries
        queries = []
        
        # Molecule + year range
        for year in [2018, 2019, 2020, 2021, 2022, 2023, 2024]:
            queries.append(f"{molecule} patent WO{year}")
        
        # Dev codes
        for code in dev_codes[:5]:  # Top 5 dev codes
            queries.append(f"{code} patent WO")
        
        # Common pharma companies (adjust based on target)
        companies = ["Bayer", "Pfizer", "Novartis", "Roche", "Merck"]
        for company in companies[:3]:
            queries.append(f"{molecule} {company} patent WO")
        
        logger.info(f"  📋 Built {len(queries)} search queries")
        
        # Extract WO numbers from query results
        # This would ideally use n8n webhook or SerpAPI
        # For now, returning empty list (placeholder for n8n integration)
        
        wo_numbers = []
        
        logger.info(f"  ⚠️ WO search requires n8n integration (placeholder)")
        
        return wo_numbers
    
    async def expand_wo_to_br(
        self,
        wo_numbers: List[str]
    ) -> List[SearchResult]:
        """
        Expand WO numbers to BR patents using EPO
        
        Args:
            wo_numbers: List of WO numbers
            
        Returns:
            List of BR patent search results
        """
        if not wo_numbers:
            return []
        
        logger.info(f"🌍 [EPO] Expanding {len(wo_numbers)} WO numbers to BR")
        
        # Batch fetch with EPO
        wo_to_br = await self._epo_client.batch_get_br_patents(
            wo_numbers,
            max_concurrent=5
        )
        
        results = []
        
        for wo, br_patents in wo_to_br.items():
            for br in br_patents:
                result = SearchResult(
                    publication_number=br['publication_number'],
                    country='BR',
                    filing_date=br.get('date', ''),
                    source=f'epo_wo_{wo}',
                    link=f"https://worldwide.espacenet.com/patent/search?q=pn%3D{br['publication_number']}",
                    raw_data={'wo_origin': wo, 'epo_data': br}
                )
                results.append(result)
        
        logger.info(f"✅ [EPO] Expanded to {len(results)} BR patents")
        
        return results
    
    async def comprehensive_search(
        self,
        molecule: str,
        brand_name: Optional[str] = None,
        target_countries: List[str] = None
    ) -> Dict[str, Any]:
        """
        Comprehensive parallel patent search
        
        Args:
            molecule: Molecule name
            brand_name: Brand name (optional)
            target_countries: Target countries (default: ['BR'])
            
        Returns:
            Complete search results with BR patents and metadata
        """
        if target_countries is None:
            target_countries = ['BR']
        
        logger.info(f"\n{'='*70}")
        logger.info(f"🎯 COMPREHENSIVE SEARCH: {molecule}")
        logger.info(f"{'='*70}\n")
        
        start_time = datetime.now()
        
        # Phase 1: Get molecular data (PubChem)
        logger.info("📍 Phase 1: Molecular Data")
        pubchem_data = await self.get_pubchem_data(molecule)
        
        # Build search variations
        variations = []
        if pubchem_data:
            variations.extend(pubchem_data.dev_codes[:10])
            if pubchem_data.cas_number:
                variations.append(pubchem_data.cas_number)
        
        if brand_name:
            variations.append(brand_name)
        
        logger.info(f"  ✓ Search variations: {len(variations)}")
        
        # Phase 2: Parallel searches
        logger.info("\n📍 Phase 2: Parallel Source Search")
        
        tasks = []
        
        # INPI direct search
        if 'BR' in target_countries:
            tasks.append(
                self.search_inpi(molecule, variations)
            )
        
        # WO number search (placeholder - needs n8n)
        # tasks.append(
        #     self.search_wo_numbers(molecule, pubchem_data.dev_codes if pubchem_data else [])
        # )
        
        # Execute all searches in parallel
        results_list = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Collect results
        all_patents = []
        for result in results_list:
            if isinstance(result, Exception):
                logger.error(f"  ✗ Task failed: {str(result)}")
                continue
            if isinstance(result, list):
                all_patents.extend(result)
        
        # Phase 3: Deduplication
        logger.info("\n📍 Phase 3: Deduplication")
        unique_patents = self._deduplicate_patents(all_patents)
        
        # Phase 4: Quality scoring
        logger.info("\n📍 Phase 4: Quality Scoring")
        scored_patents = self._score_patents(unique_patents)
        
        # Calculate elapsed time
        elapsed = (datetime.now() - start_time).total_seconds()
        
        # Build result
        result = {
            'molecule': molecule,
            'brand_name': brand_name,
            'pubchem_data': pubchem_data.__dict__ if pubchem_data else None,
            'summary': {
                'total_patents': len(scored_patents),
                'br_patents': len([p for p in scored_patents if p.country == 'BR']),
                'sources': list(set(p.source for p in scored_patents)),
                'elapsed_seconds': round(elapsed, 2)
            },
            'patents': [self._patent_to_dict(p) for p in scored_patents]
        }
        
        logger.info(f"\n{'='*70}")
        logger.info(f"✅ SEARCH COMPLETE")
        logger.info(f"  • Total: {result['summary']['total_patents']} patents")
        logger.info(f"  • BR: {result['summary']['br_patents']} patents")
        logger.info(f"  • Time: {elapsed:.2f}s")
        logger.info(f"{'='*70}\n")
        
        return result
    
    def _deduplicate_patents(self, patents: List[SearchResult]) -> List[SearchResult]:
        """
        Deduplicate patents by publication number
        
        Prefers results with more complete data
        """
        seen = {}
        
        for patent in patents:
            # Normalize number
            num = patent.publication_number.upper().replace(' ', '').replace('-', '')
            
            if num not in seen:
                seen[num] = patent
            else:
                # Keep the one with more data
                existing = seen[num]
                if len(patent.title) > len(existing.title):
                    seen[num] = patent
        
        logger.info(f"  ✓ {len(patents)} → {len(seen)} unique")
        
        return list(seen.values())
    
    def _score_patents(self, patents: List[SearchResult]) -> List[SearchResult]:
        """
        Calculate quality score for each patent
        
        Based on completeness of data
        """
        for patent in patents:
            score = 0.0
            
            # Required fields
            if patent.publication_number: score += 20
            if patent.country: score += 20
            
            # Important fields
            if patent.title: score += 15
            if patent.abstract: score += 10
            if patent.applicant: score += 10
            if patent.filing_date: score += 10
            
            # Additional fields
            if patent.inventors: score += 5
            if patent.classifications: score += 5
            if patent.publication_date: score += 5
            
            patent.raw_data['quality_score'] = score
        
        # Sort by score (highest first)
        patents.sort(key=lambda p: p.raw_data.get('quality_score', 0), reverse=True)
        
        return patents
    
    def _patent_to_dict(self, patent: SearchResult) -> Dict[str, Any]:
        """Convert SearchResult to dict"""
        return {
            'publication_number': patent.publication_number,
            'country': patent.country,
            'title': patent.title,
            'abstract': patent.abstract,
            'applicant': patent.applicant,
            'inventors': patent.inventors,
            'filing_date': patent.filing_date,
            'publication_date': patent.publication_date,
            'classifications': patent.classifications,
            'source': patent.source,
            'link': patent.link,
            'quality_score': patent.raw_data.get('quality_score', 0)
        }
