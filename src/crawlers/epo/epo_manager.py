#!/usr/bin/env python3
"""
EPO (European Patent Office) Manager
Token auth + Family resolution + Worldwide applications
"""
import httpx
import asyncio
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import logging
from datetime import datetime, timedelta
import base64

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class EPOToken:
    """EPO access token"""
    access_token: str
    expires_at: datetime
    
    def is_valid(self) -> bool:
        return datetime.now() < self.expires_at

@dataclass
class PatentFamily:
    """Família de patentes"""
    wo_number: str
    family_id: str = ""
    members: List[str] = field(default_factory=list)
    br_members: List[str] = field(default_factory=list)
    
class EPOManager:
    """Manager para EPO OPS API"""
    
    # Suas credentials
    CONSUMER_KEY = "G5wJypxeg0GXEJoMGP37tdK370aKxeMszGKAkD6QaR0yiR5X"
    CONSUMER_SECRET = "zg5AJ0EDzXdJey3GaFNM8ztMVxHKXRrAihXH93iS5ZAzKPAPMFLuVUfiEuAqpdbz"
    
    BASE_URL = "https://ops.epo.org/3.2"
    
    def __init__(self):
        self.session: Optional[httpx.AsyncClient] = None
        self.token: Optional[EPOToken] = None
    
    async def __aenter__(self):
        self.session = httpx.AsyncClient(timeout=90.0, follow_redirects=True)
        await self._ensure_token()
        return self
    
    async def __aexit__(self, *args):
        if self.session:
            await self.session.aclose()
    
    async def _ensure_token(self):
        """Garante token válido"""
        if self.token and self.token.is_valid():
            return
        
        logger.info("🔑 [EPO] Obtendo access token...")
        
        # Basic auth
        credentials = f"{self.CONSUMER_KEY}:{self.CONSUMER_SECRET}"
        basic_auth = base64.b64encode(credentials.encode()).decode()
        
        headers = {
            "Authorization": f"Basic {basic_auth}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        data = {"grant_type": "client_credentials"}
        
        try:
            response = await self.session.post(
                f"{self.BASE_URL}/auth/accesstoken",
                headers=headers,
                data=data
            )
            
            if response.status_code == 200:
                token_data = response.json()
                access_token = token_data.get("access_token")
                expires_in = token_data.get("expires_in", 1200)  # Default 20min
                
                self.token = EPOToken(
                    access_token=access_token,
                    expires_at=datetime.now() + timedelta(seconds=expires_in - 60)  # 1min buffer
                )
                
                logger.info(f"  ✅ Token válido por {expires_in//60}min")
            else:
                logger.error(f"  ❌ Token error: {response.status_code}")
        
        except Exception as e:
            logger.error(f"  ❌ Token exception: {e}")
    
    async def get_family_from_wo(self, wo_number: str) -> Optional[PatentFamily]:
        """Busca família de patentes de um WO number"""
        
        await self._ensure_token()
        
        if not self.token:
            logger.error("  ❌ Sem token EPO")
            return None
        
        logger.info(f"👨‍👩‍👧‍👦 [EPO Family] {wo_number}")
        
        try:
            # Search endpoint
            url = f"{self.BASE_URL}/rest-services/published-data/search"
            
            headers = {
                "Authorization": f"Bearer {self.token.access_token}",
                "Accept": "application/json"
            }
            
            params = {"q": wo_number}
            
            response = await self.session.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                return self._parse_family_response(wo_number, data)
            else:
                logger.warning(f"  ⚠️  EPO status: {response.status_code}")
        
        except Exception as e:
            logger.error(f"  ❌ EPO error: {e}")
        
        return None
    
    def _parse_family_response(self, wo_number: str, data: Dict) -> Optional[PatentFamily]:
        """Parse resposta EPO"""
        
        try:
            # Estrutura EPO pode variar
            search_results = data.get("ops:world-patent-data", {}).get("ops:biblio-search", {}).get("ops:search-result", {})
            
            publications = search_results.get("ops:publication-reference", [])
            if not isinstance(publications, list):
                publications = [publications] if publications else []
            
            all_members = []
            br_members = []
            
            for pub in publications:
                doc_id = pub.get("document-id", {})
                country = doc_id.get("country", {}).get("$", "")
                number = doc_id.get("doc-number", {}).get("$", "")
                
                if country and number:
                    full_id = f"{country}{number}"
                    all_members.append(full_id)
                    
                    if country == "BR":
                        br_members.append(full_id)
            
            logger.info(f"  ✅ {len(all_members)} members | {len(br_members)} BR")
            
            return PatentFamily(
                wo_number=wo_number,
                family_id="",  # EPO não retorna sempre
                members=all_members,
                br_members=br_members
            )
        
        except Exception as e:
            logger.debug(f"  Parse error: {e}")
            return None
    
    async def batch_resolve_families(self, wo_numbers: List[str]) -> List[PatentFamily]:
        """Resolve múltiplas famílias (sequencial com delay)"""
        
        logger.info(f"👨‍👩‍👧‍👦 [EPO Batch] {len(wo_numbers)} WO numbers")
        
        families = []
        
        for i, wo in enumerate(wo_numbers, 1):
            logger.info(f"  [{i}/{len(wo_numbers)}] {wo}")
            
            family = await self.get_family_from_wo(wo)
            if family:
                families.append(family)
            
            # Rate limiting (EPO é sensível)
            if i < len(wo_numbers):
                await asyncio.sleep(1)
        
        total_br = sum(len(f.br_members) for f in families)
        logger.info(f"  🎯 Total: {total_br} BR patents from {len(families)} families")
        
        return families


# Mock data
MOCK_EPO_FAMILIES = {
    "WO2011148135": PatentFamily(
        wo_number="WO2011148135",
        family_id="44795839",
        members=["WO2011148135A1", "US2013178472A1", "EP2621933A1", "BR112012008823B8"],
        br_members=["BR112012008823B8"]
    ),
    "WO2014108438": PatentFamily(
        wo_number="WO2014108438",
        family_id="50191635",
        members=["WO2014108438A1", "US9688669B2", "EP2941428A1", "BR112016007690A2"],
        br_members=["BR112016007690A2"]
    )
}

# Test
async def test_epo():
    """Teste com mock"""
    async with EPOManager() as epo:
        try:
            family = await epo.get_family_from_wo("WO2011148135")
        except:
            logger.info("  📦 Usando MOCK data")
            family = MOCK_EPO_FAMILIES["WO2011148135"]
        
        if family:
            print(f"\n✅ EPO FAMILY:")
            print(f"WO: {family.wo_number}")
            print(f"Members: {len(family.members)}")
            print(f"BR Members: {len(family.br_members)}")
            print(f"\nBR Patents:")
            for br in family.br_members:
                print(f"  • {br}")

if __name__ == "__main__":
    asyncio.run(test_epo())
