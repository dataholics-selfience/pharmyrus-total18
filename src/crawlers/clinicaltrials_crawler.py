"""
ClinicalTrials.gov Crawler
Busca dados de P&D (trials clínicos) de medicamentos
"""
import asyncio
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import urllib.parse

import httpx
from bs4 import BeautifulSoup

from .super_crawler import SuperCrawler, CrawlStrategy

logger = logging.getLogger(__name__)


@dataclass
class ClinicalTrial:
    """Dados de trial clínico"""
    nct_id: str
    title: str
    status: str
    phase: str
    conditions: List[str]
    interventions: List[str]
    sponsor: str
    start_date: Optional[str] = None
    completion_date: Optional[str] = None
    enrollment: Optional[int] = None
    locations: List[str] = field(default_factory=list)
    url: str = ""
    
    # Metadados
    last_update: Optional[str] = None
    results_available: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário"""
        return {
            "nct_id": self.nct_id,
            "title": self.title,
            "status": self.status,
            "phase": self.phase,
            "conditions": self.conditions,
            "interventions": self.interventions,
            "sponsor": self.sponsor,
            "start_date": self.start_date,
            "completion_date": self.completion_date,
            "enrollment": self.enrollment,
            "locations": self.locations,
            "url": self.url,
            "last_update": self.last_update,
            "results_available": self.results_available
        }


class ClinicalTrialsGovCrawler:
    """
    Crawler para ClinicalTrials.gov
    
    Características:
    - API oficial (primário)
    - Scraping (fallback)
    - SuperCrawler resiliente
    - Parse múltiplos formatos
    """
    
    BASE_API_URL = "https://clinicaltrials.gov/api/v2/studies"
    BASE_WEB_URL = "https://clinicaltrials.gov"
    
    def __init__(self, super_crawler: Optional[SuperCrawler] = None):
        self.crawler = super_crawler or SuperCrawler(
            max_retries=5,
            timeout=60
        )
    
    async def search_by_molecule(
        self,
        molecule: str,
        max_results: int = 100
    ) -> List[ClinicalTrial]:
        """
        Busca trials por nome da molécula
        
        Estratégia:
        1. Tenta API oficial
        2. Se falhar, scraping do site
        """
        logger.info(f"🔬 ClinicalTrials.gov: buscando '{molecule}'")
        
        # Tenta API primeiro
        try:
            trials = await self._search_via_api(molecule, max_results)
            if trials:
                logger.info(f"   ✅ API: {len(trials)} trials encontrados")
                return trials
        except Exception as e:
            logger.warning(f"   ⚠️ API falhou: {str(e)}")
        
        # Fallback para scraping
        try:
            trials = await self._search_via_scraping(molecule, max_results)
            logger.info(f"   ✅ Scraping: {len(trials)} trials encontrados")
            return trials
        except Exception as e:
            logger.error(f"   ❌ Scraping falhou: {str(e)}")
            return []
    
    async def _search_via_api(
        self,
        molecule: str,
        max_results: int
    ) -> List[ClinicalTrial]:
        """Busca via API oficial v2"""
        trials = []
        page_size = min(100, max_results)
        
        params = {
            "query.term": molecule,
            "pageSize": page_size,
            "format": "json"
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                self.BASE_API_URL,
                params=params
            )
            
            if response.status_code != 200:
                raise Exception(f"API returned {response.status_code}")
            
            data = response.json()
            
            # Parse estudos
            studies = data.get("studies", [])
            
            for study in studies[:max_results]:
                try:
                    trial = self._parse_api_study(study)
                    if trial:
                        trials.append(trial)
                except Exception as e:
                    logger.warning(f"   ⚠️ Erro parseando estudo: {e}")
                    continue
        
        return trials
    
    def _parse_api_study(self, study: Dict) -> Optional[ClinicalTrial]:
        """Parse estudo da API v2"""
        try:
            protocol = study.get("protocolSection", {})
            id_module = protocol.get("identificationModule", {})
            status_module = protocol.get("statusModule", {})
            design_module = protocol.get("designModule", {})
            arms_module = protocol.get("armsInterventionsModule", {})
            conditions_module = protocol.get("conditionsModule", {})
            sponsor_module = protocol.get("sponsorCollaboratorsModule", {})
            
            nct_id = id_module.get("nctId", "")
            if not nct_id:
                return None
            
            # Fase
            phases = design_module.get("phases", [])
            phase = phases[0] if phases else "Unknown"
            
            # Intervenções
            interventions = []
            for intervention in arms_module.get("interventions", []):
                name = intervention.get("name", "")
                if name:
                    interventions.append(name)
            
            # Condições
            conditions = conditions_module.get("conditions", [])
            
            # Sponsor
            lead_sponsor = sponsor_module.get("leadSponsor", {})
            sponsor = lead_sponsor.get("name", "Unknown")
            
            # Enrollment
            enrollment_info = design_module.get("enrollmentInfo", {})
            enrollment = enrollment_info.get("count")
            
            # Localizações
            locations = []
            locations_module = protocol.get("contactsLocationsModule", {})
            for loc in locations_module.get("locations", [])[:10]:
                city = loc.get("city", "")
                country = loc.get("country", "")
                if city and country:
                    locations.append(f"{city}, {country}")
            
            trial = ClinicalTrial(
                nct_id=nct_id,
                title=id_module.get("officialTitle") or id_module.get("briefTitle", ""),
                status=status_module.get("overallStatus", "Unknown"),
                phase=phase,
                conditions=conditions,
                interventions=interventions,
                sponsor=sponsor,
                start_date=status_module.get("startDateStruct", {}).get("date"),
                completion_date=status_module.get("completionDateStruct", {}).get("date"),
                enrollment=enrollment,
                locations=locations,
                url=f"{self.BASE_WEB_URL}/study/{nct_id}",
                last_update=status_module.get("lastUpdateSubmitDate"),
                results_available=bool(study.get("resultsSection"))
            )
            
            return trial
            
        except Exception as e:
            logger.warning(f"   ⚠️ Parse error: {e}")
            return None
    
    async def _search_via_scraping(
        self,
        molecule: str,
        max_results: int
    ) -> List[ClinicalTrial]:
        """Busca via scraping do site (fallback)"""
        trials = []
        
        # URL de busca
        search_url = f"{self.BASE_WEB_URL}/search"
        params = {
            "term": molecule,
            "page": 1
        }
        
        # Monta URL
        url = f"{search_url}?{urllib.parse.urlencode(params)}"
        
        # Crawl com SuperCrawler
        result = await self.crawler.crawl(url)
        
        if not result.success or not result.html:
            raise Exception("Failed to fetch search results")
        
        # Parse HTML
        soup = self.crawler.parse_html(result.html)
        
        # Encontra links de estudos
        study_links = []
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if "/study/" in href and "NCT" in href:
                nct_id = href.split("/study/")[1].split("?")[0]
                if nct_id not in study_links:
                    study_links.append(nct_id)
        
        logger.info(f"   📋 Encontrados {len(study_links)} estudos para parsear")
        
        # Limita resultados
        study_links = study_links[:max_results]
        
        # Parse cada estudo
        for nct_id in study_links:
            try:
                trial = await self._scrape_study_page(nct_id)
                if trial:
                    trials.append(trial)
            except Exception as e:
                logger.warning(f"   ⚠️ Erro parseando {nct_id}: {e}")
                continue
        
        return trials
    
    async def _scrape_study_page(self, nct_id: str) -> Optional[ClinicalTrial]:
        """Scrape página individual de estudo"""
        url = f"{self.BASE_WEB_URL}/study/{nct_id}"
        
        result = await self.crawler.crawl(url)
        
        if not result.success or not result.html:
            return None
        
        soup = self.crawler.parse_html(result.html)
        
        # Extrai dados (estrutura simplificada)
        try:
            # Título
            title_elem = soup.find("h1", class_="ct-title")
            title = title_elem.text.strip() if title_elem else "Unknown"
            
            # Status e fase (parse das tabelas)
            status = "Unknown"
            phase = "Unknown"
            
            # Condições
            conditions = []
            conditions_section = soup.find("div", {"id": "conditions"})
            if conditions_section:
                for item in conditions_section.find_all("li"):
                    conditions.append(item.text.strip())
            
            # Intervenções
            interventions = []
            interventions_section = soup.find("div", {"id": "interventions"})
            if interventions_section:
                for item in interventions_section.find_all("li"):
                    interventions.append(item.text.strip())
            
            # Sponsor
            sponsor = "Unknown"
            sponsor_elem = soup.find("div", {"id": "sponsor"})
            if sponsor_elem:
                sponsor = sponsor_elem.text.strip()
            
            trial = ClinicalTrial(
                nct_id=nct_id,
                title=title,
                status=status,
                phase=phase,
                conditions=conditions,
                interventions=interventions,
                sponsor=sponsor,
                url=url
            )
            
            return trial
            
        except Exception as e:
            logger.warning(f"   ⚠️ Parse error for {nct_id}: {e}")
            return None
    
    async def get_trial_details(self, nct_id: str) -> Optional[ClinicalTrial]:
        """Busca detalhes de trial específico"""
        url = f"{self.BASE_API_URL}/{nct_id}"
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params={"format": "json"})
                
                if response.status_code == 200:
                    data = response.json()
                    study = data.get("studies", [{}])[0]
                    return self._parse_api_study(study)
        except:
            pass
        
        # Fallback para scraping
        return await self._scrape_study_page(nct_id)
    
    async def close(self):
        """Fecha recursos"""
        if self.crawler:
            await self.crawler.close()
