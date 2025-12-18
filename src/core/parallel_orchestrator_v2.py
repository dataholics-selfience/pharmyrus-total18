"""
Parallel Orchestrator V2 - Ultra Resiliente
Integra todos os crawlers + AI fallback
Separa patents vs R&D
100% independente de n8n
"""
import asyncio
import logging
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field, asdict
from datetime import datetime
import time

import httpx

from .super_crawler import SuperCrawler
from ..crawlers.epo.epo_client import EPOClient
from ..crawlers.wo_search import WONumberSearcher
from ..crawlers.clinicaltrials_crawler import ClinicalTrialsGovCrawler, ClinicalTrial
from ..ai.ai_fallback import AIFallbackProcessor

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Resultado de busca de patente"""
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
    quality_score: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MoleculeData:
    """Dados moleculares do PubChem"""
    name: str
    cas_number: Optional[str] = None
    dev_codes: List[str] = field(default_factory=list)
    synonyms: List[str] = field(default_factory=list)
    molecular_formula: Optional[str] = None
    molecular_weight: Optional[float] = None
    smiles: Optional[str] = None
    inchikey: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ComprehensiveSearchResult:
    """Resultado completo separando patents vs R&D"""
    success: bool
    molecule: str
    patents: List[SearchResult] = field(default_factory=list)
    patent_summary: Dict[str, Any] = field(default_factory=dict)
    research_and_development: List[Dict[str, Any]] = field(default_factory=list)
    rd_summary: Dict[str, Any] = field(default_factory=dict)
    pubchem_data: Optional[MoleculeData] = None
    execution_time_seconds: float = 0.0
    sources_used: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "molecule": self.molecule,
            "patents": {
                "total": len(self.patents),
                "by_country": self.patent_summary.get("by_country", {}),
                "by_source": self.patent_summary.get("by_source", {}),
                "results": [p.to_dict() for p in self.patents]
            },
            "research_and_development": {
                "clinical_trials": {
                    "total": len(self.research_and_development),
                    "by_phase": self.rd_summary.get("by_phase", {}),
                    "by_status": self.rd_summary.get("by_status", {}),
                    "results": self.research_and_development
                }
            },
            "pubchem_data": self.pubchem_data.to_dict() if self.pubchem_data else None,
            "metadata": {
                "execution_time_seconds": self.execution_time_seconds,
                "sources_used": self.sources_used,
                "errors": self.errors if self.errors else []
            }
        }


class ParallelOrchestratorV2:
    def __init__(
        self,
        epo_consumer_key: Optional[str] = None,
        epo_consumer_secret: Optional[str] = None,
        inpi_crawler_url: str = "https://crawler3-production.up.railway.app",
        serpapi_key: Optional[str] = None,
        ai_fallback_enabled: bool = True
    ):
        self.epo_consumer_key = epo_consumer_key
        self.epo_consumer_secret = epo_consumer_secret
        self.inpi_crawler_url = inpi_crawler_url
        self.serpapi_key = serpapi_key
        self.ai_fallback_enabled = ai_fallback_enabled
        self.super_crawler: Optional[SuperCrawler] = None
        self.wo_searcher: Optional[WONumberSearcher] = None
        self.ct_crawler: Optional[ClinicalTrialsGovCrawler] = None
        self.ai_processor: Optional[AIFallbackProcessor] = None
    
    async def __aenter__(self):
        self.super_crawler = SuperCrawler(max_retries=5, timeout=90, use_cache=True)
        self.wo_searcher = WONumberSearcher(super_crawler=self.super_crawler, serpapi_key=self.serpapi_key)
        self.ct_crawler = ClinicalTrialsGovCrawler(super_crawler=self.super_crawler)
        if self.ai_fallback_enabled:
            self.ai_processor = AIFallbackProcessor(max_budget_usd=0.10)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.super_crawler:
            await self.super_crawler.close()
        if self.ct_crawler:
            await self.ct_crawler.close()
        if self.wo_searcher:
            await self.wo_searcher.close()
    
    async def comprehensive_search(
        self,
        molecule: str,
        brand_name: Optional[str] = None,
        target_countries: List[str] = None,
        deep_search: bool = False
    ) -> ComprehensiveSearchResult:
        start_time = time.time()
        logger.info(f"\n{'='*70}")
        logger.info(f"🚀 COMPREHENSIVE SEARCH: {molecule}")
        logger.info(f"{'='*70}")
        
        result = ComprehensiveSearchResult(success=False, molecule=molecule)
        
        try:
            logger.info("\n📊 FASE 1: PubChem Molecular Data")
            pubchem_data = await self._get_pubchem_data(molecule)
            result.pubchem_data = pubchem_data
            
            if pubchem_data:
                logger.info(f"   ✅ CAS: {pubchem_data.cas_number}")
                logger.info(f"   ✅ Dev codes: {len(pubchem_data.dev_codes)}")
            
            logger.info("\n🔄 FASE 2: Parallel Multi-Source Search")
            tasks = [
                self._search_wo_numbers(molecule, pubchem_data.dev_codes if pubchem_data else [], pubchem_data.cas_number if pubchem_data else None, brand_name),
                self._search_inpi(molecule, pubchem_data.dev_codes if pubchem_data else []),
                self._search_clinical_trials(molecule)
            ]
            
            search_results = await asyncio.gather(*tasks, return_exceptions=True)
            wo_numbers, patents, trials = set(), [], []
            
            for idx, search_result in enumerate(search_results):
                if isinstance(search_result, Exception):
                    logger.warning(f"   ⚠️ Task {idx+1} failed: {search_result}")
                    result.errors.append(f"Task {idx+1}: {str(search_result)}")
                    continue
                
                if idx == 0:
                    wo_numbers = search_result
                    logger.info(f"   ✅ WO numbers: {len(wo_numbers)}")
                elif idx == 1:
                    patents.extend(search_result)
                    logger.info(f"   ✅ INPI: {len(search_result)} patents")
                elif idx == 2:
                    trials = search_result
                    logger.info(f"   ✅ ClinicalTrials: {len(trials)} trials")
            
            if wo_numbers:
                logger.info(f"\n📈 FASE 3: EPO Expansion ({len(wo_numbers)} WO numbers)")
                epo_patents = await self._expand_wo_to_br(list(wo_numbers))
                patents.extend(epo_patents)
                logger.info(f"   ✅ EPO: {len(epo_patents)} BR patents")
            
            logger.info("\n🔍 FASE 4: Deduplication & Quality Scoring")
            patents_unique = self._deduplicate_patents(patents)
            logger.info(f"   ✅ Unique patents: {len(patents_unique)}")
            
            for patent in patents_unique:
                patent.quality_score = self._calculate_quality_score(patent)
            
            patents_unique.sort(key=lambda p: p.quality_score, reverse=True)
            
            logger.info("\n📊 FASE 5: Categorization")
            result.patents = patents_unique
            result.patent_summary = self._generate_patent_summary(patents_unique)
            result.research_and_development = [t.to_dict() for t in trials]
            result.rd_summary = self._generate_rd_summary(trials)
            
            sources = set()
            for p in patents_unique:
                sources.add(p.source)
            if trials:
                sources.add("clinicaltrials_gov")
            result.sources_used = list(sources)
            result.success = True
            
        except Exception as e:
            logger.error(f"\n❌ Comprehensive search failed: {str(e)}", exc_info=True)
            result.errors.append(f"Fatal: {str(e)}")
        
        result.execution_time_seconds = time.time() - start_time
        logger.info(f"\n{'='*70}")
        logger.info(f"✅ SEARCH COMPLETE: {result.execution_time_seconds:.2f}s")
        logger.info(f"   Patents: {len(result.patents)}")
        logger.info(f"   Trials: {len(result.research_and_development)}")
        logger.info(f"{'='*70}\n")
        
        return result
    
    async def _get_pubchem_data(self, molecule: str) -> Optional[MoleculeData]:
        try:
            url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{molecule}/synonyms/JSON"
            result = await self.super_crawler.crawl(url)
            
            if not result.success:
                return None
            
            import json, re
            data = json.loads(result.html)
            info = data.get("InformationList", {}).get("Information", [{}])[0]
            synonyms = info.get("Synonym", [])
            
            dev_codes, cas_number = [], None
            dev_pattern = re.compile(r'^[A-Z]{2,5}-?\d{3,7}[A-Z]?$', re.IGNORECASE)
            cas_pattern = re.compile(r'^\d{2,7}-\d{2}-\d$')
            
            for syn in synonyms:
                if dev_pattern.match(syn):
                    dev_codes.append(syn)
                if cas_pattern.match(syn) and not cas_number:
                    cas_number = syn
            
            return MoleculeData(name=molecule, cas_number=cas_number, dev_codes=dev_codes[:20], synonyms=synonyms[:50])
            
        except Exception as e:
            logger.warning(f"PubChem failed: {e}")
            return None
    
    async def _search_wo_numbers(self, molecule: str, dev_codes: List[str], cas_number: Optional[str], brand_name: Optional[str]) -> Set[str]:
        try:
            result = await self.wo_searcher.search_wo_numbers(molecule, dev_codes, cas_number, brand_name)
            return result.wo_numbers
        except Exception as e:
            logger.warning(f"WO search failed: {e}")
            return set()
    
    async def _search_inpi(self, molecule: str, dev_codes: List[str]) -> List[SearchResult]:
        patents = []
        try:
            terms = [molecule] + dev_codes[:5]
            for term in terms:
                url = f"{self.inpi_crawler_url}/api/data/inpi/patents?medicine={term}"
                result = await self.super_crawler.crawl(url)
                
                if result.success and result.html:
                    import json
                    data = json.loads(result.html)
                    for item in data.get("data", []):
                        patent = SearchResult(
                            publication_number=item.get("title", "").replace(" ", "-"),
                            country="BR",
                            title=item.get("applicant", ""),
                            abstract=item.get("fullText", "")[:500],
                            filing_date=item.get("depositDate", ""),
                            source="inpi_crawler",
                            link=f"https://busca.inpi.gov.br/pePI/servlet/PatenteServletController?Action=detail&CodPedido={item.get('title', '')}"
                        )
                        patents.append(patent)
        except Exception as e:
            logger.warning(f"INPI search failed: {e}")
        return patents
    
    async def _search_clinical_trials(self, molecule: str) -> List[ClinicalTrial]:
        try:
            trials = await self.ct_crawler.search_by_molecule(molecule, max_results=50)
            return trials
        except Exception as e:
            logger.warning(f"ClinicalTrials search failed: {e}")
            return []
    
    async def _expand_wo_to_br(self, wo_numbers: List[str]) -> List[SearchResult]:
        patents = []
        try:
            async with EPOClient(consumer_key=self.epo_consumer_key, consumer_secret=self.epo_consumer_secret) as epo:
                br_patents = await epo.batch_get_br_patents(wo_numbers[:30])
                for br in br_patents:
                    patent = SearchResult(
                        publication_number=br.get("publication_number", ""),
                        country="BR",
                        source=f"epo_{br.get('wo_number', '')}",
                        link=f"https://worldwide.espacenet.com/patent/search?q={br.get('publication_number', '')}"
                    )
                    patents.append(patent)
        except Exception as e:
            logger.warning(f"EPO expansion failed: {e}")
        return patents
    
    def _deduplicate_patents(self, patents: List[SearchResult]) -> List[SearchResult]:
        seen = {}
        for patent in patents:
            num = patent.publication_number.upper().replace("-", "").replace(" ", "").replace("/", "")
            if num not in seen:
                seen[num] = patent
            else:
                existing = seen[num]
                if len(patent.title) > len(existing.title):
                    seen[num] = patent
        return list(seen.values())
    
    def _calculate_quality_score(self, patent: SearchResult) -> float:
        score = 0.0
        if patent.publication_number: score += 20
        if patent.country: score += 20
        if patent.title: score += 15
        if patent.abstract: score += 10
        if patent.applicant: score += 10
        if patent.filing_date: score += 10
        if patent.inventors: score += 5
        if patent.classifications: score += 5
        if patent.publication_date: score += 5
        return min(score, 100.0)
    
    def _generate_patent_summary(self, patents: List[SearchResult]) -> Dict[str, Any]:
        by_country, by_source = {}, {}
        for p in patents:
            by_country[p.country] = by_country.get(p.country, 0) + 1
            by_source[p.source] = by_source.get(p.source, 0) + 1
        return {"by_country": by_country, "by_source": by_source}
    
    def _generate_rd_summary(self, trials: List[ClinicalTrial]) -> Dict[str, Any]:
        by_phase, by_status = {}, {}
        for t in trials:
            by_phase[t.phase] = by_phase.get(t.phase, 0) + 1
            by_status[t.status] = by_status.get(t.status, 0) + 1
        return {"by_phase": by_phase, "by_status": by_status}
