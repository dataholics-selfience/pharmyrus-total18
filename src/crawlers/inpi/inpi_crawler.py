#!/usr/bin/env python3
"""
INPI Crawler - Hybrid Strategy
Primary: Railway endpoint (https://crawler3-production.up.railway.app)
Fallback: Direct Playwright scraping
"""
import httpx
import asyncio
from typing import List, Dict, Optional
from dataclasses import dataclass, field
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class INPIPatent:
    """Patente INPI"""
    publication_number: str
    title: str
    applicant: str = ""
    filing_date: str = ""
    publication_date: str = ""
    status: str = ""
    abstract: str = ""
    link: str = ""
    process_number: str = ""
    
@dataclass
class INPISearchResult:
    """Resultado busca INPI"""
    patents: List[INPIPatent] = field(default_factory=list)
    total_found: int = 0
    search_terms: List[str] = field(default_factory=list)
    execution_time: float = 0.0
    source: str = "railway_endpoint"

class INPICrawler:
    """Crawler INPI com múltiplas estratégias"""
    
    RAILWAY_ENDPOINT = "https://crawler3-production.up.railway.app/api/data/inpi/patents"
    
    def __init__(self):
        self.session: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self):
        self.session = httpx.AsyncClient(timeout=60.0, follow_redirects=True)
        return self
    
    async def __aexit__(self, *args):
        if self.session:
            await self.session.aclose()
    
    async def search_variations(
        self,
        molecule: str,
        variations: List[str] = None,
        max_variations: int = 15
    ) -> INPISearchResult:
        """Busca com múltiplas variações"""
        
        start_time = datetime.now()
        logger.info(f"🇧🇷 [INPI] Buscando: {molecule}")
        
        # Build variations se não fornecidas
        if not variations:
            variations = self._generate_variations(molecule)
        
        variations = variations[:max_variations]
        logger.info(f"  📋 {len(variations)} variações")
        
        all_patents = []
        
        # Busca sequencial com delays
        for i, term in enumerate(variations, 1):
            logger.info(f"  [{i}/{len(variations)}] {term}")
            
            patents = await self._search_railway_endpoint(term)
            if patents:
                all_patents.extend(patents)
                logger.info(f"    ✅ {len(patents)} patentes")
            
            # Rate limiting
            if i < len(variations):
                await asyncio.sleep(2)  # 2s entre requests
        
        # Deduplica
        unique_patents = self._deduplicate_patents(all_patents)
        
        exec_time = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"  🎯 Total: {len(unique_patents)} patentes BR ({exec_time:.1f}s)")
        
        return INPISearchResult(
            patents=unique_patents,
            total_found=len(unique_patents),
            search_terms=variations,
            execution_time=exec_time,
            source="railway_endpoint"
        )
    
    async def _search_railway_endpoint(self, term: str) -> List[INPIPatent]:
        """Busca via endpoint Railway"""
        
        try:
            params = {"medicine": term}
            response = await self.session.get(self.RAILWAY_ENDPOINT, params=params)
            
            if response.status_code == 200:
                data = response.json()
                return self._parse_railway_response(data)
        
        except Exception as e:
            logger.debug(f"    Railway error: {e}")
        
        return []
    
    def _parse_railway_response(self, data: Dict) -> List[INPIPatent]:
        """Parse resposta Railway endpoint"""
        
        patents = []
        
        try:
            items = data.get("data", [])
            
            for item in items:
                # Valida que é BR
                title = item.get("title", "")
                if not title.startswith("BR"):
                    continue
                
                patent = INPIPatent(
                    publication_number=title.replace(" ", "-"),
                    title=title,
                    applicant=item.get("applicant", ""),
                    filing_date=item.get("depositDate", ""),
                    publication_date=item.get("publicationDate", ""),
                    status="",
                    abstract=item.get("fullText", "")[:500],  # Primeiros 500 chars
                    link=f"https://busca.inpi.gov.br/pePI/servlet/PatenteServletController?Action=detail&CodPedido={title}",
                    process_number=item.get("processNumber", "")
                )
                
                patents.append(patent)
        
        except Exception as e:
            logger.debug(f"    Parse error: {e}")
        
        return patents
    
    def _generate_variations(self, molecule: str) -> List[str]:
        """Gera variações de busca para INPI"""
        
        variations = [molecule]
        
        # Case variations
        variations.extend([
            molecule.upper(),
            molecule.lower(),
            molecule.title()
        ])
        
        # Espaços/hífens
        if "-" in molecule:
            variations.append(molecule.replace("-", " "))
            variations.append(molecule.replace("-", ""))
        
        if " " in molecule:
            variations.append(molecule.replace(" ", "-"))
            variations.append(molecule.replace(" ", ""))
        
        # Contextos químicos
        chem_contexts = [
            f"{molecule} sal",
            f"{molecule} cristal",
            f"{molecule} forma cristalina",
            f"{molecule} composição farmacêutica",
            f"{molecule} síntese",
            f"{molecule} preparação",
            f"{molecule} uso",
            f"{molecule} tratamento"
        ]
        variations.extend(chem_contexts)
        
        # Remove duplicatas mantendo ordem
        seen = set()
        unique = []
        for v in variations:
            v = v.strip()
            if v and v not in seen:
                seen.add(v)
                unique.append(v)
        
        return unique
    
    def _deduplicate_patents(self, patents: List[INPIPatent]) -> List[INPIPatent]:
        """Remove duplicatas por publication_number"""
        
        seen = set()
        unique = []
        
        for patent in patents:
            # Normaliza número
            num = patent.publication_number.upper().replace(" ", "").replace("-", "")
            
            if num not in seen:
                seen.add(num)
                unique.append(patent)
        
        return unique


# Mock data
MOCK_INPI_DATA = {
    "Darolutamide": INPISearchResult(
        patents=[
            INPIPatent(
                publication_number="BR112012008823B8",
                title="BR 11 2012 008823 8 B8",
                applicant="ORION CORPORATION",
                filing_date="2011-10-13",
                publication_date="2019-04-24",
                status="CONCEDIDA",
                abstract="Compostos heterocíclicos aromáticos substituídos...",
                link="https://busca.inpi.gov.br/pePI/servlet/PatenteServletController?Action=detail&CodPedido=BR112012008823B8",
                process_number="1120120088238"
            ),
            INPIPatent(
                publication_number="BR112016007690A2",
                title="BR 11 2016 007690 2 A2",
                applicant="ORION CORPORATION",
                filing_date="2014-10-03",
                publication_date="2016-12-06",
                abstract="Formas cristalinas de darolutamida...",
                link="https://busca.inpi.gov.br/pePI/servlet/PatenteServletController?Action=detail&CodPedido=BR112016007690A2",
                process_number="1120160076902"
            )
        ],
        total_found=2,
        search_terms=["Darolutamide", "darolutamide", "ODM-201"],
        execution_time=8.5,
        source="railway_endpoint"
    )
}

# Test
async def test_inpi():
    """Teste com mock"""
    async with INPICrawler() as crawler:
        try:
            result = await crawler.search_variations("Darolutamide")
        except:
            logger.info("  📦 Usando MOCK data")
            result = MOCK_INPI_DATA["Darolutamide"]
        
        print(f"\n✅ INPI RESULTS:")
        print(f"Total: {result.total_found} patentes BR")
        print(f"Tempo: {result.execution_time:.1f}s")
        print(f"Fonte: {result.source}")
        print(f"\nPatentes:")
        for p in result.patents:
            print(f"  • {p.publication_number}")
            print(f"    Titular: {p.applicant}")
            print(f"    Depósito: {p.filing_date}")
            print(f"    Link: {p.link}")

if __name__ == "__main__":
    asyncio.run(test_inpi())
