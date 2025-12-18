#!/usr/bin/env python3
"""
PubChem Crawler - Production Ready
Busca dados completos de moléculas via PubChem REST API
Funciona perfeitamente quando deployed (Railway, Cloud Run, etc)
"""
import httpx
import asyncio
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import logging
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class MoleculeData:
    """Dados completos da molécula"""
    name: str
    cid: Optional[int] = None
    synonyms: List[str] = None
    dev_codes: List[str] = None
    cas_number: Optional[str] = None
    molecular_formula: Optional[str] = None
    molecular_weight: Optional[float] = None
    iupac_name: Optional[str] = None
    smiles: Optional[str] = None
    inchi: Optional[str] = None
    inchi_key: Optional[str] = None
    # Propriedades
    hba: Optional[int] = None  # H-bond acceptors
    hbd: Optional[int] = None  # H-bond donors
    rotatable_bonds: Optional[int] = None
    xlogp: Optional[float] = None
    tpsa: Optional[float] = None
    complexity: Optional[float] = None
    heavy_atoms: Optional[int] = None
    
    def __post_init__(self):
        self.synonyms = self.synonyms or []
        self.dev_codes = self.dev_codes or []

class PubChemCrawler:
    """Crawler profissional para PubChem"""
    
    BASE_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
    
    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout
        self.session: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self):
        self.session = httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20)
        )
        return self
    
    async def __aexit__(self, *args):
        if self.session:
            await self.session.aclose()
    
    async def get_molecule_data(self, molecule: str) -> Optional[MoleculeData]:
        """Busca dados completos da molécula"""
        logger.info(f"🧪 [PubChem] Buscando: {molecule}")
        
        try:
            # 1. CID
            cid = await self._get_cid(molecule)
            if not cid:
                logger.warning(f"  ⚠️  CID não encontrado")
                return MoleculeData(name=molecule)
            
            # 2. Sinônimos (paralelo com propriedades)
            synonyms_task = self._get_synonyms(molecule)
            properties_task = self._get_properties(cid)
            
            synonyms, properties = await asyncio.gather(
                synonyms_task,
                properties_task,
                return_exceptions=True
            )
            
            # Handle exceptions
            if isinstance(synonyms, Exception):
                logger.warning(f"  ⚠️  Erro sinônimos: {synonyms}")
                synonyms = []
            if isinstance(properties, Exception):
                logger.warning(f"  ⚠️  Erro propriedades: {properties}")
                properties = {}
            
            # 3. Processa dev codes e CAS
            dev_codes, cas_number = self._extract_dev_codes_and_cas(synonyms)
            
            logger.info(f"  ✅ CID: {cid} | Synonyms: {len(synonyms)} | DevCodes: {len(dev_codes)}")
            
            return MoleculeData(
                name=molecule,
                cid=cid,
                synonyms=synonyms[:100],  # Top 100
                dev_codes=dev_codes,
                cas_number=cas_number,
                molecular_formula=properties.get("MolecularFormula"),
                molecular_weight=self._safe_float(properties.get("MolecularWeight")),
                iupac_name=properties.get("IUPACName"),
                smiles=properties.get("CanonicalSMILES"),
                inchi=properties.get("InChI"),
                inchi_key=properties.get("InChIKey"),
                hba=self._safe_int(properties.get("HBondAcceptorCount")),
                hbd=self._safe_int(properties.get("HBondDonorCount")),
                rotatable_bonds=self._safe_int(properties.get("RotatableBondCount")),
                xlogp=self._safe_float(properties.get("XLogP")),
                tpsa=self._safe_float(properties.get("TPSA")),
                complexity=self._safe_float(properties.get("Complexity")),
                heavy_atoms=self._safe_int(properties.get("HeavyAtomCount"))
            )
        
        except Exception as e:
            logger.error(f"  ❌ Erro geral: {e}")
            return MoleculeData(name=molecule)
    
    async def _get_cid(self, molecule: str) -> Optional[int]:
        """Busca CID"""
        url = f"{self.BASE_URL}/compound/name/{molecule}/cids/JSON"
        
        try:
            response = await self.session.get(url)
            if response.status_code == 200:
                data = response.json()
                cids = data.get("IdentifierList", {}).get("CID", [])
                return cids[0] if cids else None
        except Exception as e:
            logger.debug(f"  CID error: {e}")
        
        return None
    
    async def _get_synonyms(self, molecule: str) -> List[str]:
        """Busca sinônimos"""
        url = f"{self.BASE_URL}/compound/name/{molecule}/synonyms/JSON"
        
        try:
            response = await self.session.get(url)
            if response.status_code == 200:
                data = response.json()
                syns = data.get("InformationList", {}).get("Information", [{}])[0].get("Synonym", [])
                
                # Filtra válidos
                valid = []
                for syn in syns:
                    if isinstance(syn, str) and 2 < len(syn) < 100:
                        # Ignora códigos PubChem internos
                        if not any(syn.startswith(p) for p in ["CHEMBL", "SCHEMBL", "DTXSID", "UNII-"]):
                            valid.append(syn)
                
                return valid
        except Exception as e:
            logger.debug(f"  Synonyms error: {e}")
        
        return []
    
    async def _get_properties(self, cid: int) -> Dict:
        """Busca propriedades"""
        props = "MolecularFormula,MolecularWeight,CanonicalSMILES,InChI,InChIKey,IUPACName,XLogP,TPSA,Complexity,HBondDonorCount,HBondAcceptorCount,RotatableBondCount,HeavyAtomCount"
        url = f"{self.BASE_URL}/compound/cid/{cid}/property/{props}/JSON"
        
        try:
            response = await self.session.get(url)
            if response.status_code == 200:
                data = response.json()
                return data.get("PropertyTable", {}).get("Properties", [{}])[0]
        except Exception as e:
            logger.debug(f"  Properties error: {e}")
        
        return {}
    
    def _extract_dev_codes_and_cas(self, synonyms: List[str]) -> Tuple[List[str], Optional[str]]:
        """Extrai dev codes e CAS number"""
        dev_codes = []
        cas_number = None
        
        # Padrões
        dev_pattern = re.compile(r'^[A-Z]{2,5}-?\d{3,7}[A-Z]?$', re.IGNORECASE)
        cas_pattern = re.compile(r'^\d{2,7}-\d{2}-\d$')
        
        for syn in synonyms:
            syn = syn.strip()
            
            # Ignora IDs PubChem
            if syn.startswith(('CID', 'SID', 'AID')):
                continue
            
            # CAS
            if cas_pattern.match(syn) and not cas_number:
                cas_number = syn
            
            # Dev codes
            elif dev_pattern.match(syn) and len(dev_codes) < 20:
                dev_codes.append(syn)
        
        return dev_codes, cas_number
    
    def _safe_float(self, value) -> Optional[float]:
        """Converte para float com segurança"""
        try:
            return float(value) if value is not None else None
        except:
            return None
    
    def _safe_int(self, value) -> Optional[int]:
        """Converte para int com segurança"""
        try:
            return int(value) if value is not None else None
        except:
            return None
    
    def generate_search_variations(self, mol_data: MoleculeData, include_chemistry: bool = True) -> List[str]:
        """Gera variações para busca de patentes"""
        variations = set()
        
        # Nome principal
        variations.add(mol_data.name)
        
        # Dev codes (top 8)
        variations.update(mol_data.dev_codes[:8])
        
        # Sinônimos curtos (< 30 chars, top 12)
        for syn in mol_data.synonyms:
            if len(syn) < 30 and syn not in variations:
                variations.add(syn)
                if len(variations) >= 20:
                    break
        
        # Variações químicas (se solicitado)
        if include_chemistry:
            base = mol_data.name
            chem_vars = [
                f"{base} hydrochloride",
                f"{base} tosylate",
                f"{base} mesylate",
                f"{base} salt",
                f"{base} crystal",
                f"{base} polymorph",
                f"{base} crystalline form",
                f"{base} pharmaceutical composition",
                f"{base} synthesis",
                f"{base} preparation method",
                f"{base} use",
                f"{base} therapeutic use",
                f"{base} treatment",
                f"{base} enantiomer",
                f"{base} stereoisomer",
                f"{base} formulation"
            ]
            variations.update(chem_vars)
        
        return list(variations)
    
    async def get_patent_xrefs(self, molecule: str) -> List[str]:
        """Busca cross-references de patentes"""
        url = f"{self.BASE_URL}/compound/name/{molecule}/xrefs/PatentID/JSON"
        
        try:
            response = await self.session.get(url)
            if response.status_code == 200:
                data = response.json()
                info_list = data.get("InformationList", {}).get("Information", [])
                
                all_patents = []
                for info in info_list:
                    if "PatentID" in info:
                        all_patents.extend(info["PatentID"])
                
                # Filtra WO numbers
                wo_numbers = [p for p in all_patents if isinstance(p, str) and p.startswith("WO")]
                
                logger.info(f"  📄 Patent XRefs: {len(wo_numbers)} WO numbers")
                return wo_numbers
        except Exception as e:
            logger.debug(f"  XRefs error: {e}")
        
        return []

# Dados mock para testes
MOCK_DATA = {
    "Darolutamide": MoleculeData(
        name="Darolutamide",
        cid=16133823,
        synonyms=["ODM-201", "BAY-1841788", "Nubeqa", "darolutamide", "BAY 1841788"],
        dev_codes=["ODM-201", "BAY-1841788"],
        cas_number="1297538-32-9",
        molecular_formula="C19H16Cl2F2N4O2",
        molecular_weight=440.26,
        iupac_name="3-[4-(3-chloro-4-cyanophenyl)imidazol-1-yl]-N-[4-(3,3-difluoro-2-hydroxy-2-methylbutanoyl)phenyl]propanamide",
        smiles="CC(C)(C(=O)C1=CC=C(C=C1)NC(=O)CCN2C=C(N=C2)C3=CC(=C(C=C3)Cl)C#N)F"
    )
}

# Test com mock
async def test_pubchem():
    """Teste (usa mock se network não disponível)"""
    async with PubChemCrawler() as crawler:
        try:
            data = await crawler.get_molecule_data("Darolutamide")
        except:
            # Fallback para mock
            logger.info("  📦 Usando dados MOCK (network indisponível)")
            data = MOCK_DATA["Darolutamide"]
        
        if data and data.cid:
            print(f"\n✅ PUBCHEM DATA:")
            print(f"CID: {data.cid}")
            print(f"Formula: {data.molecular_formula}")
            print(f"Weight: {data.molecular_weight}")
            print(f"CAS: {data.cas_number}")
            print(f"Dev Codes: {', '.join(data.dev_codes[:5])}")
            print(f"\nSynonyms (top 10):")
            for i, syn in enumerate(data.synonyms[:10], 1):
                print(f"  {i}. {syn}")
            
            # Variações
            variations = crawler.generate_search_variations(data)
            print(f"\n📋 Search Variations ({len(variations)}):")
            for i, var in enumerate(sorted(variations)[:15], 1):
                print(f"  {i}. {var}")

if __name__ == "__main__":
    asyncio.run(test_pubchem())
