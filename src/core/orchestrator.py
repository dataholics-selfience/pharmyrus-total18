#!/usr/bin/env python3
"""
Pharmyrus v5.0 Main Orchestrator
Coordena: PubChem → WO Search → EPO Families → INPI → ANVISA → Aggregation
"""
import asyncio
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict
import logging
from datetime import datetime
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from crawlers.pubchem_crawler import PubChemCrawler, MoleculeData
from crawlers.google_patents.wo_searcher_v2 import GooglePatentsWOSearcher, WOSearchResult
from crawlers.epo.epo_manager import EPOManager, PatentFamily
from crawlers.inpi.inpi_crawler import INPICrawler, INPISearchResult
from regulatory.anvisa_scraper import ANVISAScraper, ANVISASearchResult

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class PharmyrusResult:
    """Resultado completo Pharmyrus v5"""
    # Metadata
    molecule: str
    brand: str = ""
    search_timestamp: str = ""
    execution_time: float = 0.0
    complete: bool = True
    
    # Molecule data
    pubchem_data: Optional[Dict] = None
    
    # Patent data
    wo_numbers: List[str] = field(default_factory=list)
    patent_families: List[Dict] = field(default_factory=list)
    
    # Brazilian patents
    br_patents_inpi: List[Dict] = field(default_factory=list)
    br_patents_from_families: List[str] = field(default_factory=list)
    total_br_patents: int = 0
    
    # Regulatory
    anvisa_registrations: List[Dict] = field(default_factory=list)
    
    # Analysis
    dual_check: Optional[Dict] = None
    quality_score: float = 0.0
    cortellis_comparison: Optional[Dict] = None

class PharmyrusOrchestrator:
    """Orchestrator principal do Pharmyrus v5"""
    
    def __init__(self):
        self.pubchem = None
        self.wo_searcher = None
        self.epo = None
        self.inpi = None
        self.anvisa = None
    
    async def __aenter__(self):
        """Initialize all crawlers"""
        logger.info("🚀 Initializing Pharmyrus v5 Orchestrator...")
        
        self.pubchem = await PubChemCrawler().__aenter__()
        self.wo_searcher = await GooglePatentsWOSearcher().__aenter__()
        self.epo = await EPOManager().__aenter__()
        self.inpi = await INPICrawler().__aenter__()
        self.anvisa = await ANVISAScraper().__aenter__()
        
        return self
    
    async def __aexit__(self, *args):
        """Cleanup all crawlers"""
        if self.pubchem:
            await self.pubchem.__aexit__(*args)
        if self.wo_searcher:
            await self.wo_searcher.__aexit__(*args)
        if self.epo:
            await self.epo.__aexit__(*args)
        if self.inpi:
            await self.inpi.__aexit__(*args)
        if self.anvisa:
            await self.anvisa.__aexit__(*args)
    
    async def search_comprehensive(
        self,
        molecule: str,
        brand: str = "",
        deep_search: bool = False,
        timeout_minutes: int = 5
    ) -> PharmyrusResult:
        """
        Busca compreensiva - Fluxo completo v5.0
        
        FASE 1: PubChem (sinônimos, CAS, dev codes)
        FASE 2: WO Search (múltiplas fontes)
        FASE 3: EPO Families (worldwide applications)
        FASE 4: INPI (patentes BR diretas)
        FASE 5: ANVISA (registros regulatórios)
        FASE 6: Aggregation + Quality Score
        """
        
        start_time = datetime.now()
        logger.info(f"\n{'='*80}")
        logger.info(f"🧬 PHARMYRUS v5.0 - COMPREHENSIVE SEARCH")
        logger.info(f"Molecule: {molecule}")
        logger.info(f"Brand: {brand or 'N/A'}")
        logger.info(f"Deep Search: {deep_search}")
        logger.info(f"{'='*80}\n")
        
        result = PharmyrusResult(
            molecule=molecule,
            brand=brand,
            search_timestamp=datetime.now().isoformat()
        )
        
        try:
            # FASE 1: PubChem
            logger.info("📊 FASE 1: PubChem Data")
            mol_data = await self._phase1_pubchem(molecule)
            if mol_data:
                result.pubchem_data = asdict(mol_data)
            
            # FASE 2: WO Search
            logger.info("\n🔍 FASE 2: WO Number Search")
            wo_result = await self._phase2_wo_search(mol_data, deep_search)
            result.wo_numbers = wo_result.wo_numbers if wo_result else []
            
            # FASE 3: EPO Families (paralelo com INPI para otimizar tempo)
            logger.info(f"\n👨‍👩‍👧‍👦 FASE 3: EPO Family Resolution")
            logger.info(f"🇧🇷 FASE 4: INPI Direct Search")
            
            epo_task = self._phase3_epo_families(result.wo_numbers)
            inpi_task = self._phase4_inpi_search(mol_data)
            
            families, inpi_result = await asyncio.gather(epo_task, inpi_task)
            
            # Processa famílias
            if families:
                result.patent_families = [asdict(f) for f in families]
                result.br_patents_from_families = self._extract_br_from_families(families)
            
            # Processa INPI
            if inpi_result:
                result.br_patents_inpi = [
                    {
                        "number": p.publication_number,
                        "applicant": p.applicant,
                        "filing_date": p.filing_date,
                        "link": p.link
                    }
                    for p in inpi_result.patents
                ]
            
            # FASE 5: ANVISA
            logger.info("\n💊 FASE 5: ANVISA Regulatory Check")
            anvisa_result = await self._phase5_anvisa(molecule, brand)
            if anvisa_result:
                result.anvisa_registrations = [
                    {
                        "number": r.registration_number,
                        "product": r.product_name,
                        "company": r.company,
                        "status": r.status
                    }
                    for r in anvisa_result.records
                ]
            
            # FASE 6: Aggregation
            logger.info("\n📊 FASE 6: Aggregation & Analysis")
            result = await self._phase6_aggregation(result)
            
            # Calculate execution time
            exec_time = (datetime.now() - start_time).total_seconds()
            result.execution_time = exec_time
            result.complete = True
            
            logger.info(f"\n{'='*80}")
            logger.info(f"✅ SEARCH COMPLETE")
            logger.info(f"Total BR Patents: {result.total_br_patents}")
            logger.info(f"Quality Score: {result.quality_score:.2f}/100")
            logger.info(f"Execution Time: {exec_time:.1f}s")
            logger.info(f"{'='*80}\n")
        
        except Exception as e:
            logger.error(f"❌ Orchestrator error: {e}")
            result.complete = False
        
        return result
    
    async def _phase1_pubchem(self, molecule: str) -> Optional[MoleculeData]:
        """FASE 1: PubChem data"""
        try:
            return await self.pubchem.get_molecule_data(molecule)
        except Exception as e:
            logger.error(f"  PubChem error: {e}")
            return None
    
    async def _phase2_wo_search(self, mol_data: Optional[MoleculeData], deep: bool) -> Optional[WOSearchResult]:
        """FASE 2: WO number search"""
        if not mol_data:
            return None
        
        try:
            max_queries = 25 if deep else 15
            return await self.wo_searcher.search_wo_numbers(
                molecule=mol_data.name,
                dev_codes=mol_data.dev_codes,
                cas=mol_data.cas_number,
                max_queries=max_queries
            )
        except Exception as e:
            logger.error(f"  WO search error: {e}")
            return None
    
    async def _phase3_epo_families(self, wo_numbers: List[str]) -> List[PatentFamily]:
        """FASE 3: EPO family resolution"""
        if not wo_numbers:
            return []
        
        try:
            # Limita a 20 WOs para não exceder timeout
            limited_wos = wo_numbers[:20]
            return await self.epo.batch_resolve_families(limited_wos)
        except Exception as e:
            logger.error(f"  EPO error: {e}")
            return []
    
    async def _phase4_inpi_search(self, mol_data: Optional[MoleculeData]) -> Optional[INPISearchResult]:
        """FASE 4: INPI direct search"""
        if not mol_data:
            return None
        
        try:
            # Gera variações com PubChem
            variations = self.pubchem.generate_search_variations(mol_data, include_chemistry=True)
            return await self.inpi.search_variations(mol_data.name, variations, max_variations=15)
        except Exception as e:
            logger.error(f"  INPI error: {e}")
            return None
    
    async def _phase5_anvisa(self, molecule: str, brand: str) -> Optional[ANVISASearchResult]:
        """FASE 5: ANVISA regulatory"""
        try:
            return await self.anvisa.search_medicine(molecule, brand)
        except Exception as e:
            logger.error(f"  ANVISA error: {e}")
            return None
    
    async def _phase6_aggregation(self, result: PharmyrusResult) -> PharmyrusResult:
        """FASE 6: Aggregation and analysis"""
        
        # Deduplica BRs
        all_br = set()
        all_br.update(result.br_patents_from_families)
        all_br.update(p["number"] for p in result.br_patents_inpi)
        
        result.total_br_patents = len(all_br)
        
        # Dual check (Patent + ANVISA)
        has_anvisa = len(result.anvisa_registrations) > 0
        has_patents = result.total_br_patents > 0
        
        result.dual_check = {
            "has_patents": has_patents,
            "has_anvisa": has_anvisa,
            "status": self._dual_check_status(has_patents, has_anvisa)
        }
        
        # Quality score (algoritmo simplificado)
        result.quality_score = self._calculate_quality_score(result)
        
        return result
    
    def _extract_br_from_families(self, families: List[PatentFamily]) -> List[str]:
        """Extrai todos os BR numbers das famílias"""
        all_br = set()
        for family in families:
            all_br.update(family.br_members)
        return list(all_br)
    
    def _dual_check_status(self, has_patents: bool, has_anvisa: bool) -> str:
        """Status do dual check"""
        if has_patents and has_anvisa:
            return "PROTECTED_AND_APPROVED"
        elif has_patents:
            return "PROTECTED_NOT_APPROVED"
        elif has_anvisa:
            return "APPROVED_NOT_PROTECTED"
        else:
            return "NO_PROTECTION_NO_APPROVAL"
    
    def _calculate_quality_score(self, result: PharmyrusResult) -> float:
        """
        Quality Score Algorithm (0-100)
        Baseado em ARCHITECTURE_V5.md
        """
        score = 0.0
        
        # PubChem data (20 pontos)
        if result.pubchem_data:
            score += 10
            if result.pubchem_data.get("dev_codes"):
                score += 5
            if result.pubchem_data.get("cas_number"):
                score += 5
        
        # WO numbers (25 pontos)
        wo_count = len(result.wo_numbers)
        score += min(wo_count * 2.5, 25)
        
        # BR patents (35 pontos)
        br_count = result.total_br_patents
        score += min(br_count * 4.4, 35)
        
        # ANVISA (10 pontos)
        if result.anvisa_registrations:
            score += 10
        
        # Patent families (10 pontos)
        if result.patent_families:
            score += min(len(result.patent_families) * 2, 10)
        
        return min(score, 100.0)

# Test orchestrator
async def test_orchestrator():
    """Teste completo do orchestrator"""
    async with PharmyrusOrchestrator() as orch:
        result = await orch.search_comprehensive(
            molecule="Darolutamide",
            brand="Nubeqa",
            deep_search=False
        )
        
        print(f"\n{'='*80}")
        print(f"PHARMYRUS v5.0 RESULT")
        print(f"{'='*80}")
        print(f"Molecule: {result.molecule}")
        print(f"Execution Time: {result.execution_time:.1f}s")
        print(f"Complete: {result.complete}")
        print(f"\nWO Numbers: {len(result.wo_numbers)}")
        print(f"Patent Families: {len(result.patent_families)}")
        print(f"BR Patents (total): {result.total_br_patents}")
        print(f"  - From families: {len(result.br_patents_from_families)}")
        print(f"  - From INPI: {len(result.br_patents_inpi)}")
        print(f"ANVISA Registrations: {len(result.anvisa_registrations)}")
        print(f"\nDual Check: {result.dual_check['status']}")
        print(f"Quality Score: {result.quality_score:.2f}/100")
        print(f"{'='*80}\n")

if __name__ == "__main__":
    asyncio.run(test_orchestrator())
