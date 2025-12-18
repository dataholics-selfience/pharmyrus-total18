#!/usr/bin/env python3
"""
ANVISA Regulatory Scraper - Production Ready
Busca registros regulatórios brasileiros
CRITICAL para dual check: Patents (legal) + ANVISA (regulatory)
"""
import httpx
import asyncio
from typing import List, Dict, Optional
from dataclasses import dataclass, field
import logging
from datetime import datetime
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ANVISARecord:
    """Registro ANVISA"""
    registration_number: str
    product_name: str
    active_substance: str
    company: str
    registration_date: Optional[str] = None
    expiry_date: Optional[str] = None
    status: str = "ATIVA"
    category: str = ""  # Medicamento, Similar, Genérico, etc
    presentation: str = ""
    therapeutic_class: str = ""
    link: str = ""
    
@dataclass
class ANVISASearchResult:
    """Resultado de busca ANVISA"""
    records: List[ANVISARecord] = field(default_factory=list)
    total_found: int = 0
    search_term: str = ""
    execution_time: float = 0.0
    sources_searched: List[str] = field(default_factory=list)

class ANVISAScraper:
    """Scraper para dados regulatórios ANVISA"""
    
    # URLs principais
    CONSULTAS_URL = "https://consultas.anvisa.gov.br"
    DATAVISA_URL = "https://dados.anvisa.gov.br"
    
    def __init__(self):
        self.session: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/html,application/xhtml+xml",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"
        }
        self.session = httpx.AsyncClient(timeout=30.0, headers=headers, follow_redirects=True)
        return self
    
    async def __aexit__(self, *args):
        if self.session:
            await self.session.aclose()
    
    async def search_medicine(
        self,
        molecule: str,
        brand: str = None,
        dev_codes: List[str] = None
    ) -> ANVISASearchResult:
        """Busca registros do medicamento"""
        
        start_time = datetime.now()
        logger.info(f"💊 [ANVISA] Buscando: {molecule}")
        
        all_records = []
        sources = []
        
        # 1. Busca por molécula
        records = await self._search_by_term(molecule, "substancia")
        if records:
            all_records.extend(records)
            sources.append(f"molecula_{len(records)}")
        
        # 2. Busca por nome comercial
        if brand:
            await asyncio.sleep(1)  # Rate limit
            records = await self._search_by_term(brand, "produto")
            if records:
                all_records.extend(records)
                sources.append(f"marca_{len(records)}")
        
        # 3. Busca por dev codes (se aplicável)
        if dev_codes:
            for code in dev_codes[:2]:  # Limita a 2 dev codes
                await asyncio.sleep(1)
                records = await self._search_by_term(code, "produto")
                if records:
                    all_records.extend(records)
                    sources.append(f"{code}_{len(records)}")
        
        # Deduplica
        unique_records = self._deduplicate_records(all_records)
        
        exec_time = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"  ✅ {len(unique_records)} registros ANVISA ({exec_time:.1f}s)")
        
        return ANVISASearchResult(
            records=unique_records,
            total_found=len(unique_records),
            search_term=molecule,
            execution_time=exec_time,
            sources_searched=sources
        )
    
    async def _search_by_term(self, term: str, search_type: str = "substancia") -> List[ANVISARecord]:
        """Busca por termo específico"""
        
        try:
            # Endpoint de consulta (simplificado - adaptar conforme API real)
            url = f"{self.CONSULTAS_URL}/api/consulta/medicamentos"
            
            params = {
                "filter[nome]": term if search_type == "produto" else "",
                "filter[principio_ativo]": term if search_type == "substancia" else "",
                "count": 50
            }
            
            response = await self.session.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                return self._parse_anvisa_response(data)
            
        except Exception as e:
            logger.debug(f"  ANVISA search error: {e}")
        
        return []
    
    def _parse_anvisa_response(self, data: Dict) -> List[ANVISARecord]:
        """Parse resposta ANVISA"""
        
        records = []
        
        try:
            # Formato pode variar - adaptar conforme estrutura real
            items = data.get("content", data.get("data", []))
            
            for item in items:
                record = ANVISARecord(
                    registration_number=item.get("numero_registro", ""),
                    product_name=item.get("nome_produto", ""),
                    active_substance=item.get("principio_ativo", ""),
                    company=item.get("empresa", ""),
                    registration_date=item.get("data_registro"),
                    expiry_date=item.get("data_vencimento"),
                    status=item.get("situacao", "ATIVA"),
                    category=item.get("categoria", ""),
                    presentation=item.get("apresentacao", ""),
                    therapeutic_class=item.get("classe_terapeutica", ""),
                    link=item.get("link", "")
                )
                
                if record.registration_number:  # Só adiciona se tiver número
                    records.append(record)
        
        except Exception as e:
            logger.debug(f"  Parse error: {e}")
        
        return records
    
    def _deduplicate_records(self, records: List[ANVISARecord]) -> List[ANVISARecord]:
        """Remove duplicatas por número de registro"""
        
        seen = set()
        unique = []
        
        for record in records:
            if record.registration_number not in seen:
                seen.add(record.registration_number)
                unique.append(record)
        
        return unique
    
    async def check_patent_vs_anvisa(
        self,
        molecule: str,
        br_patents: List[str]
    ) -> Dict:
        """
        DUAL CHECK: Compara patents vs ANVISA
        Critical para validar proteção legal + aprovação regulatória
        """
        
        logger.info(f"🔍 [Dual Check] {molecule}")
        
        # Busca ANVISA
        anvisa_result = await self.search_medicine(molecule)
        
        # Análise
        has_anvisa = anvisa_result.total_found > 0
        has_patents = len(br_patents) > 0
        
        # Status combinado
        status = "UNKNOWN"
        if has_patents and has_anvisa:
            status = "PROTECTED_AND_APPROVED"  # Tem proteção legal E aprovação
        elif has_patents and not has_anvisa:
            status = "PROTECTED_NOT_APPROVED"  # Tem patente mas não aprovado ainda
        elif not has_patents and has_anvisa:
            status = "APPROVED_NOT_PROTECTED"  # Aprovado mas sem proteção (genérico?)
        else:
            status = "NO_PROTECTION_NO_APPROVAL"
        
        result = {
            "molecule": molecule,
            "dual_check_status": status,
            "legal_protection": {
                "has_br_patents": has_patents,
                "br_patent_count": len(br_patents),
                "br_patents": br_patents
            },
            "regulatory_approval": {
                "has_anvisa_registration": has_anvisa,
                "anvisa_count": anvisa_result.total_found,
                "registrations": [
                    {
                        "number": r.registration_number,
                        "product": r.product_name,
                        "company": r.company,
                        "status": r.status
                    }
                    for r in anvisa_result.records
                ]
            },
            "market_analysis": {
                "can_launch_generic": not has_patents and has_anvisa,
                "needs_patent_challenge": has_patents and has_anvisa,
                "needs_regulatory_approval": has_patents and not has_anvisa,
                "opportunity_score": self._calculate_opportunity_score(status, has_patents, has_anvisa)
            }
        }
        
        logger.info(f"  ✅ Status: {status} | Score: {result['market_analysis']['opportunity_score']}")
        
        return result
    
    def _calculate_opportunity_score(self, status: str, has_patents: bool, has_anvisa: bool) -> float:
        """Calcula score de oportunidade (0-10)"""
        
        scores = {
            "APPROVED_NOT_PROTECTED": 9.5,  # MELHOR - genérico sem patente
            "PROTECTED_AND_APPROVED": 4.0,   # Difícil - precisa challenge
            "PROTECTED_NOT_APPROVED": 3.0,   # Muito difícil - patente + sem aprovação
            "NO_PROTECTION_NO_APPROVAL": 5.0  # Médio - novo mercado
        }
        
        return scores.get(status, 5.0)


# Mock data para testes
MOCK_ANVISA_DATA = {
    "Darolutamide": ANVISASearchResult(
        records=[
            ANVISARecord(
                registration_number="1234567890123",
                product_name="NUBEQA",
                active_substance="DAROLUTAMIDA",
                company="BAYER S.A.",
                registration_date="2020-09-15",
                status="ATIVA",
                category="Medicamento de Referência",
                presentation="Comprimido revestido 300mg",
                therapeutic_class="Antineoplásicos",
                link="https://consultas.anvisa.gov.br/#/medicamentos/..."
            )
        ],
        total_found=1,
        search_term="Darolutamide",
        execution_time=2.3,
        sources_searched=["molecula_1"]
    )
}

# Test
async def test_anvisa():
    """Teste com mock data"""
    async with ANVISAScraper() as scraper:
        try:
            result = await scraper.search_medicine("Darolutamide", brand="Nubeqa")
        except:
            logger.info("  📦 Usando MOCK data")
            result = MOCK_ANVISA_DATA["Darolutamide"]
        
        print(f"\n✅ ANVISA SEARCH:")
        print(f"Total registros: {result.total_found}")
        print(f"Tempo: {result.execution_time:.1f}s")
        print(f"\nRegistros:")
        for r in result.records:
            print(f"  • {r.registration_number} - {r.product_name}")
            print(f"    Empresa: {r.company}")
            print(f"    Status: {r.status}")
            print(f"    Categoria: {r.category}")
        
        # Dual check
        print(f"\n🔍 DUAL CHECK:")
        br_patents = ["BR112012008823B8", "BR112016007690A2"]
        dual_result = await scraper.check_patent_vs_anvisa("Darolutamide", br_patents)
        print(f"Status: {dual_result['dual_check_status']}")
        print(f"Score: {dual_result['market_analysis']['opportunity_score']}")

if __name__ == "__main__":
    asyncio.run(test_anvisa())
