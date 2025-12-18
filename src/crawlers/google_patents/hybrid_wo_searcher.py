#!/usr/bin/env python3
"""
Hybrid WO Number Searcher
Múltiplas estratégias: Direct scraping + AI parsing + SerpAPI fallback
"""
import re
import httpx
import asyncio
from typing import List, Set, Dict, Optional
from dataclasses import dataclass
import logging
from bs4 import BeautifulSoup
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class WOSearchResult:
    """Resultado de busca de WO numbers"""
    wo_numbers: List[str]
    total_found: int
    sources: Dict[str, int]
    queries_used: List[str]
    method_used: str

class HybridWOSearcher:
    """Busca WO numbers com múltiplas estratégias"""
    
    def __init__(self, grok_api_key: Optional[str] = None):
        self.wo_pattern = re.compile(r'WO\s*(\d{4})\s*/?\s*(\d{6})', re.IGNORECASE)
        self.grok_api_key = grok_api_key or "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"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
    
    async def search_google_patents_direct(self, molecule: str, year_range: List[int] = None) -> Set[str]:
        """Scraping direto do Google Patents"""
        if year_range is None:
            year_range = list(range(2010, 2026))
        
        wo_numbers = set()
        logger.info(f"🔍 [DIRECT] Buscando WO numbers para '{molecule}'")
        
        async with httpx.AsyncClient(timeout=30.0, headers=self.headers, follow_redirects=True) as client:
            for year in year_range:
                query = f"{molecule} WO{year}"
                url = f"https://patents.google.com/?q={query.replace(' ', '+')}&num=20"
                
                try:
                    response = await client.get(url)
                    if response.status_code == 200:
                        html = response.text
                        
                        # Método 1: Regex direto no HTML
                        matches = self.wo_pattern.findall(html)
                        for year_match, number in matches:
                            wo_num = f"WO{year_match}{number}"
                            wo_numbers.add(wo_num)
                        
                        # Método 2: Parse com BeautifulSoup
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        # Busca em links que contêm WO
                        for link in soup.find_all('a', href=True):
                            href = link.get('href', '')
                            if '/patent/WO' in href:
                                match = re.search(r'/patent/(WO\d{4}\d{6})', href)
                                if match:
                                    wo_numbers.add(match.group(1))
                        
                        # Busca em texto de resultados
                        for text_element in soup.find_all(['h3', 'h4', 'span', 'div']):
                            text = text_element.get_text()
                            if 'WO' in text:
                                matches = self.wo_pattern.findall(text)
                                for year_match, number in matches:
                                    wo_num = f"WO{year_match}{number}"
                                    wo_numbers.add(wo_num)
                        
                        if len(wo_numbers) > 0:
                            logger.info(f"  WO{year}: {len(wo_numbers)} found")
                    
                    await asyncio.sleep(1)  # Rate limiting
                    
                except Exception as e:
                    logger.warning(f"  ⚠️  Erro em WO{year}: {e}")
                    continue
        
        return wo_numbers
    
    async def search_pubchem_links(self, molecule: str) -> Set[str]:
        """Busca WO numbers nas referências do PubChem"""
        wo_numbers = set()
        logger.info(f"🧪 [PUBCHEM] Buscando referências")
        
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{molecule}/xrefs/PatentID/JSON"
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    data = response.json()
                    
                    # Extrai patent IDs
                    if "InformationList" in data:
                        for info in data["InformationList"]["Information"]:
                            if "PatentID" in info:
                                for patent_id in info["PatentID"]:
                                    if isinstance(patent_id, str) and patent_id.startswith("WO"):
                                        wo_numbers.add(patent_id)
                    
                    logger.info(f"  PubChem: {len(wo_numbers)} WO numbers")
        
        except Exception as e:
            logger.warning(f"  ⚠️  PubChem error: {e}")
        
        return wo_numbers
    
    async def search_with_grok_ai(self, molecule: str, html_content: str) -> Set[str]:
        """Usa Grok AI para extrair WO numbers de HTML complexo"""
        wo_numbers = set()
        
        if not html_content or len(html_content) < 100:
            return wo_numbers
        
        logger.info(f"🤖 [GROK AI] Analisando HTML ({len(html_content)} chars)")
        
        # Trunca HTML para não exceder limite da API
        html_snippet = html_content[:8000]  # Primeiros 8KB
        
        prompt = f"""Analise este HTML de resultados do Google Patents e extraia TODOS os números WO de patentes.

HTML:
{html_snippet}

TAREFA:
1. Encontre todos os números no formato WO seguido de ano (4 dígitos) e número (6 dígitos)
2. Exemplos válidos: WO2011080351, WO2015/018867, WO 2020 123456
3. Retorne APENAS uma lista JSON de strings, exemplo: ["WO2011080351", "WO2015018867"]

Responda SOMENTE com o JSON, sem texto adicional."""

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    "https://api.x.ai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.grok_api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "grok-beta",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.1
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    content = result["choices"][0]["message"]["content"]
                    
                    # Parse JSON response
                    try:
                        # Remove markdown code blocks se presentes
                        content = content.replace("```json", "").replace("```", "").strip()
                        wo_list = json.loads(content)
                        
                        if isinstance(wo_list, list):
                            wo_numbers.update(wo_list)
                            logger.info(f"  Grok AI: {len(wo_list)} WO numbers extraídos")
                    except:
                        # Fallback: regex no conteúdo
                        matches = self.wo_pattern.findall(content)
                        for year, number in matches:
                            wo_numbers.add(f"WO{year}{number}")
        
        except Exception as e:
            logger.warning(f"  ⚠️  Grok AI error: {e}")
        
        return wo_numbers
    
    async def search_comprehensive(
        self, 
        molecule: str, 
        synonyms: List[str] = None,
        year_range: List[int] = None,
        use_ai: bool = True
    ) -> WOSearchResult:
        """Busca abrangente híbrida"""
        
        logger.info(f"\n{'='*60}")
        logger.info(f"🎯 BUSCA HÍBRIDA DE WO NUMBERS: {molecule}")
        logger.info(f"{'='*60}\n")
        
        sources = {}
        all_wo_numbers = set()
        queries_used = []
        methods_used = []
        
        # 1. Scraping direto Google Patents
        direct_wos = await self.search_google_patents_direct(molecule, year_range)
        sources["google_patents_direct"] = len(direct_wos)
        all_wo_numbers.update(direct_wos)
        methods_used.append("direct_scraping")
        
        # 2. PubChem cross-references
        pubchem_wos = await self.search_pubchem_links(molecule)
        sources["pubchem_xrefs"] = len(pubchem_wos - all_wo_numbers)
        all_wo_numbers.update(pubchem_wos)
        methods_used.append("pubchem_api")
        
        # 3. Sinônimos (primeiros 3)
        if synonyms:
            for synonym in synonyms[:3]:
                syn_wos = await self.search_google_patents_direct(synonym, year_range[:3] if year_range else None)
                new_count = len(syn_wos - all_wo_numbers)
                if new_count > 0:
                    sources[f"synonym_{synonym[:10]}"] = new_count
                    all_wo_numbers.update(syn_wos)
        
        # 4. AI parsing (se ativado e encontrou poucos resultados)
        if use_ai and len(all_wo_numbers) < 5:
            logger.info(f"🤖 Poucos resultados ({len(all_wo_numbers)}), usando AI parsing...")
            
            # Pega HTML de uma busca para AI analisar
            url = f"https://patents.google.com/?q={molecule.replace(' ', '+')}"
            try:
                async with httpx.AsyncClient(timeout=30.0, headers=self.headers) as client:
                    response = await client.get(url)
                    if response.status_code == 200:
                        ai_wos = await self.search_with_grok_ai(molecule, response.text)
                        sources["grok_ai"] = len(ai_wos - all_wo_numbers)
                        all_wo_numbers.update(ai_wos)
                        methods_used.append("grok_ai")
            except:
                pass
        
        # Ordena e formata WO numbers
        sorted_wos = sorted(list(all_wo_numbers))
        
        logger.info(f"\n{'='*60}")
        logger.info(f"✅ RESULTADO: {len(sorted_wos)} WO numbers encontrados")
        logger.info(f"{'='*60}")
        logger.info(f"Fontes:")
        for source, count in sources.items():
            logger.info(f"  - {source}: {count}")
        logger.info(f"\nMétodos: {', '.join(methods_used)}")
        logger.info(f"\nWO Numbers encontrados:")
        for wo in sorted_wos[:15]:
            logger.info(f"  • {wo}")
        if len(sorted_wos) > 15:
            logger.info(f"  ... e mais {len(sorted_wos) - 15}")
        logger.info(f"{'='*60}\n")
        
        return WOSearchResult(
            wo_numbers=sorted_wos,
            total_found=len(sorted_wos),
            sources=sources,
            queries_used=queries_used,
            method_used=", ".join(methods_used)
        )

# Teste
async def test_hybrid():
    """Teste com Darolutamide"""
    searcher = HybridWOSearcher()
    
    result = await searcher.search_comprehensive(
        molecule="Darolutamide",
        synonyms=["ODM-201", "BAY-1841788"],
        year_range=[2010, 2011, 2012, 2013, 2014, 2015],
        use_ai=True
    )
    
    print(f"\n✅ TESTE CONCLUÍDO")
    print(f"Total: {result.total_found} WO numbers")
    print(f"Método: {result.method_used}")

if __name__ == "__main__":
    asyncio.run(test_hybrid())
