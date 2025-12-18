#!/usr/bin/env python3
"""
Pharmyrus v5 - Service Orchestrator
Orquestra chamadas para endpoints existentes (INPI crawler, n8n webhooks, EPO via n8n)
"""
import httpx
import asyncio
from typing import Dict, List, Optional
from dataclasses import dataclass
import logging
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ServiceEndpoints:
    """Endpoints de serviços externos"""
    inpi_crawler: str = "https://crawler3-production.up.railway.app/api/data/inpi/patents"
    n8n_base: str = "https://n8n.railway.app"  # Ajustar para URL real
    # Webhooks n8n (criar se não existir)
    n8n_pubchem: Optional[str] = None
    n8n_google_patents: Optional[str] = None
    n8n_epo_search: Optional[str] = None

class ServiceOrchestrator:
    """Orquestra chamadas para serviços existentes"""
    
    def __init__(self, endpoints: ServiceEndpoints = None):
        self.endpoints = endpoints or ServiceEndpoints()
        self.timeout = 120.0  # 2 minutos para chamadas longas
        
    async def search_inpi(self, medicine: str) -> Dict:
        """Chama INPI crawler (JÁ FUNCIONA na Railway)"""
        logger.info(f"🔍 [INPI] Buscando: {medicine}")
        
        url = f"{self.endpoints.inpi_crawler}?medicine={medicine}"
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Parse resposta do INPI crawler
                    patents = data.get("data", [])
                    logger.info(f"  ✅ INPI: {len(patents)} patentes")
                    
                    return {
                        "success": True,
                        "source": "inpi_crawler",
                        "count": len(patents),
                        "patents": patents
                    }
                else:
                    logger.warning(f"  ⚠️  INPI status: {response.status_code}")
                    return {"success": False, "error": f"HTTP {response.status_code}"}
        
        except Exception as e:
            logger.error(f"  ❌ Erro INPI: {e}")
            return {"success": False, "error": str(e)}
    
    async def search_inpi_variations(self, molecule: str, variations: List[str]) -> List[Dict]:
        """Busca INPI com múltiplas variações"""
        logger.info(f"🔄 [INPI Multi] Buscando {len(variations)} variações")
        
        all_patents = []
        sources_used = {}
        
        # Busca nome principal
        result = await self.search_inpi(molecule)
        if result.get("success"):
            all_patents.extend(result.get("patents", []))
            sources_used["main"] = len(result.get("patents", []))
        
        # Aguarda 1s entre requests
        await asyncio.sleep(1)
        
        # Busca top 5 variações
        for i, variation in enumerate(variations[:5], 1):
            if variation != molecule:  # Evita duplicata
                result = await self.search_inpi(variation)
                if result.get("success") and result.get("count", 0) > 0:
                    new_patents = result.get("patents", [])
                    all_patents.extend(new_patents)
                    sources_used[f"var_{i}"] = len(new_patents)
                
                await asyncio.sleep(1)
        
        # Deduplica por processNumber
        unique_patents = {}
        for patent in all_patents:
            proc_num = patent.get("processNumber") or patent.get("title")
            if proc_num and proc_num not in unique_patents:
                unique_patents[proc_num] = patent
        
        logger.info(f"  ✅ Total: {len(all_patents)} bruto, {len(unique_patents)} únicos")
        logger.info(f"  📊 Fontes: {sources_used}")
        
        return list(unique_patents.values())
    
    async def call_n8n_webhook(self, webhook_name: str, payload: Dict) -> Dict:
        """Chama webhook n8n genérico"""
        logger.info(f"📡 [n8n] Chamando webhook: {webhook_name}")
        
        # URLs dos webhooks (AJUSTAR COM URLs REAIS)
        webhook_urls = {
            "pubchem": f"{self.endpoints.n8n_base}/webhook/pubchem-search",
            "google_patents": f"{self.endpoints.n8n_base}/webhook/google-patents-search",
            "epo_search": f"{self.endpoints.n8n_base}/webhook/epo-search",
            "patent_details": f"{self.endpoints.n8n_base}/webhook/patent-details"
        }
        
        url = webhook_urls.get(webhook_name)
        if not url:
            return {"success": False, "error": f"Webhook {webhook_name} não configurado"}
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"  ✅ Webhook OK")
                    return {"success": True, "data": data}
                else:
                    logger.warning(f"  ⚠️  Webhook status: {response.status_code}")
                    return {"success": False, "error": f"HTTP {response.status_code}"}
        
        except Exception as e:
            logger.error(f"  ❌ Erro webhook: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_pubchem_data(self, molecule: str) -> Dict:
        """Busca dados PubChem via n8n webhook"""
        return await self.call_n8n_webhook("pubchem", {"molecule": molecule})
    
    async def search_google_patents_wo(self, molecule: str, year_range: List[int] = None) -> Dict:
        """Busca WO numbers via n8n webhook"""
        payload = {
            "molecule": molecule,
            "year_range": year_range or list(range(2010, 2026))
        }
        return await self.call_n8n_webhook("google_patents", payload)
    
    async def search_epo_family(self, wo_number: str) -> Dict:
        """Busca família de patentes via n8n/EPO"""
        return await self.call_n8n_webhook("epo_search", {"wo_number": wo_number})
    
    async def get_patent_details(self, patent_id: str) -> Dict:
        """Busca detalhes de patente via n8n"""
        return await self.call_n8n_webhook("patent_details", {"patent_id": patent_id})
    
    async def comprehensive_search(self, molecule: str) -> Dict:
        """Busca abrangente usando todos os serviços"""
        logger.info(f"\n{'='*60}")
        logger.info(f"🎯 BUSCA ABRANGENTE: {molecule}")
        logger.info(f"{'='*60}\n")
        
        results = {
            "molecule": molecule,
            "sources": {},
            "br_patents": [],
            "wo_numbers": [],
            "errors": []
        }
        
        # 1. INPI (direto - sabemos que funciona)
        logger.info("📍 Fase 1: Busca INPI")
        inpi_result = await self.search_inpi(molecule)
        if inpi_result.get("success"):
            results["sources"]["inpi"] = inpi_result.get("count", 0)
            results["br_patents"].extend(inpi_result.get("patents", []))
        else:
            results["errors"].append(f"INPI: {inpi_result.get('error')}")
        
        # 2. PubChem via n8n (se webhook existir)
        if self.endpoints.n8n_pubchem:
            logger.info("\n📍 Fase 2: PubChem (via n8n)")
            pubchem_result = await self.get_pubchem_data(molecule)
            if pubchem_result.get("success"):
                results["sources"]["pubchem"] = "OK"
                # Extrai variações para buscar no INPI
                data = pubchem_result.get("data", {})
                variations = data.get("synonyms", [])[:10]
                
                if variations:
                    logger.info(f"\n📍 Fase 2.1: INPI com variações PubChem")
                    varied_patents = await self.search_inpi_variations(molecule, variations)
                    results["sources"]["inpi_variations"] = len(varied_patents)
                    results["br_patents"].extend(varied_patents)
        
        # 3. Google Patents WO search via n8n
        if self.endpoints.n8n_google_patents:
            logger.info("\n📍 Fase 3: Google Patents WO search")
            gp_result = await self.search_google_patents_wo(molecule)
            if gp_result.get("success"):
                wo_numbers = gp_result.get("data", {}).get("wo_numbers", [])
                results["wo_numbers"] = wo_numbers
                results["sources"]["google_patents"] = len(wo_numbers)
        
        # Deduplica patentes BR
        unique_br = {}
        for patent in results["br_patents"]:
            key = patent.get("processNumber") or patent.get("title") or str(patent)
            if key not in unique_br:
                unique_br[key] = patent
        
        results["br_patents"] = list(unique_br.values())
        
        logger.info(f"\n{'='*60}")
        logger.info(f"✅ RESULTADO FINAL")
        logger.info(f"{'='*60}")
        logger.info(f"BRs encontradas: {len(results['br_patents'])}")
        logger.info(f"WOs encontrados: {len(results['wo_numbers'])}")
        logger.info(f"Fontes: {list(results['sources'].keys())}")
        if results["errors"]:
            logger.info(f"Erros: {len(results['errors'])}")
        logger.info(f"{'='*60}\n")
        
        return results

# Teste
async def test_orchestrator():
    """Teste com endpoint INPI real"""
    orchestrator = ServiceOrchestrator()
    
    # Teste 1: INPI direto
    print("\n" + "="*60)
    print("TESTE 1: INPI Crawler (endpoint real)")
    print("="*60)
    
    result = await orchestrator.search_inpi("Darolutamide")
    print(json.dumps(result, indent=2))
    
    # Teste 2: Busca abrangente (só INPI por enquanto)
    print("\n" + "="*60)
    print("TESTE 2: Busca Abrangente")
    print("="*60)
    
    comprehensive = await orchestrator.comprehensive_search("Darolutamide")
    print(f"\nBRs: {len(comprehensive['br_patents'])}")
    print(f"Fontes: {comprehensive['sources']}")

if __name__ == "__main__":
    asyncio.run(test_orchestrator())
