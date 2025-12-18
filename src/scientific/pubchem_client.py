#!/usr/bin/env python3
"""
PubChem Client - Comprehensive Molecule Data Extractor
Busca sinônimos, CAS, dev codes, estrutura molecular completa
"""
import httpx
import asyncio
from typing import Dict, List, Optional
from dataclasses import dataclass
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class MoleculeData:
    """Dados completos da molécula do PubChem"""
    name: str
    cid: Optional[int]
    synonyms: List[str]
    dev_codes: List[str]
    cas_number: Optional[str]
    molecular_formula: Optional[str]
    molecular_weight: Optional[float]
    iupac_name: Optional[str]
    smiles: Optional[str]
    inchi: Optional[str]
    inchi_key: Optional[str]
    # Propriedades farmacológicas
    hydrogen_bond_acceptors: Optional[int]
    hydrogen_bond_donors: Optional[int]
    rotatable_bonds: Optional[int]
    xlogp3: Optional[float]
    tpsa: Optional[float]
    complexity: Optional[float]
    heavy_atom_count: Optional[int]

class PubChemClient:
    """Cliente completo para PubChem REST API"""
    
    BASE_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
    
    def __init__(self):
        self.timeout = 30.0
        
    async def get_molecule_data(self, molecule_name: str) -> Optional[MoleculeData]:
        """Busca dados completos da molécula"""
        logger.info(f"🧪 Buscando dados PubChem: {molecule_name}")
        
        # 1. Buscar CID
        cid = await self._get_cid(molecule_name)
        if not cid:
            logger.warning(f"  ⚠️  CID não encontrado para {molecule_name}")
            return None
        
        logger.info(f"  ✓ CID: {cid}")
        
        # 2. Buscar sinônimos (inclui dev codes e CAS)
        synonyms_data = await self._get_synonyms(molecule_name)
        
        # 3. Buscar propriedades completas
        properties = await self._get_properties(cid)
        
        # 4. Processar dev codes e CAS
        dev_codes, cas_number = self._extract_dev_codes_and_cas(synonyms_data)
        
        logger.info(f"  ✓ Sinônimos: {len(synonyms_data)}")
        logger.info(f"  ✓ Dev codes: {len(dev_codes)}")
        logger.info(f"  ✓ CAS: {cas_number or 'N/A'}")
        
        return MoleculeData(
            name=molecule_name,
            cid=cid,
            synonyms=synonyms_data[:100],  # Top 100 sinônimos
            dev_codes=dev_codes,
            cas_number=cas_number,
            molecular_formula=properties.get("MolecularFormula"),
            molecular_weight=properties.get("MolecularWeight"),
            iupac_name=properties.get("IUPACName"),
            smiles=properties.get("CanonicalSMILES"),
            inchi=properties.get("InChI"),
            inchi_key=properties.get("InChIKey"),
            hydrogen_bond_acceptors=properties.get("HBondAcceptorCount"),
            hydrogen_bond_donors=properties.get("HBondDonorCount"),
            rotatable_bonds=properties.get("RotatableBondCount"),
            xlogp3=properties.get("XLogP"),
            tpsa=properties.get("TPSA"),
            complexity=properties.get("Complexity"),
            heavy_atom_count=properties.get("HeavyAtomCount")
        )
    
    async def _get_cid(self, molecule_name: str) -> Optional[int]:
        """Busca CID (Compound ID) do PubChem"""
        url = f"{self.BASE_URL}/compound/name/{molecule_name}/cids/JSON"
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    data = response.json()
                    cids = data.get("IdentifierList", {}).get("CID", [])
                    return cids[0] if cids else None
        except Exception as e:
            logger.error(f"  ❌ Erro ao buscar CID: {e}")
        
        return None
    
    async def _get_synonyms(self, molecule_name: str) -> List[str]:
        """Busca sinônimos (inclui dev codes, CAS, nomes comerciais)"""
        url = f"{self.BASE_URL}/compound/name/{molecule_name}/synonyms/JSON"
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    data = response.json()
                    synonyms = data.get("InformationList", {}).get("Information", [{}])[0].get("Synonym", [])
                    
                    # Filtra sinônimos válidos
                    valid_synonyms = []
                    for syn in synonyms:
                        if isinstance(syn, str) and len(syn) > 2 and len(syn) < 100:
                            # Remove hashes e códigos muito longos
                            if not syn.startswith("CHEMBL") and not syn.startswith("SCHEMBL"):
                                valid_synonyms.append(syn)
                    
                    return valid_synonyms
        except Exception as e:
            logger.error(f"  ❌ Erro ao buscar sinônimos: {e}")
        
        return []
    
    async def _get_properties(self, cid: int) -> Dict:
        """Busca propriedades completas da molécula"""
        url = f"{self.BASE_URL}/compound/cid/{cid}/property/MolecularFormula,MolecularWeight,CanonicalSMILES,InChI,InChIKey,IUPACName,XLogP,TPSA,Complexity,HBondDonorCount,HBondAcceptorCount,RotatableBondCount,HeavyAtomCount/JSON"
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    data = response.json()
                    props = data.get("PropertyTable", {}).get("Properties", [{}])[0]
                    return props
        except Exception as e:
            logger.error(f"  ❌ Erro ao buscar propriedades: {e}")
        
        return {}
    
    def _extract_dev_codes_and_cas(self, synonyms: List[str]) -> tuple[List[str], Optional[str]]:
        """Extrai dev codes (ex: ODM-201) e CAS number dos sinônimos"""
        import re
        
        dev_codes = []
        cas_number = None
        
        # Padrão para dev codes: 2-5 letras, hífen opcional, 3-7 dígitos, letra opcional
        dev_pattern = re.compile(r'^[A-Z]{2,5}-?\d{3,7}[A-Z]?$', re.IGNORECASE)
        
        # Padrão para CAS number: XX-XX-X ou XXX-XX-X ou XXXX-XX-X etc
        cas_pattern = re.compile(r'^\d{2,7}-\d{2}-\d$')
        
        for syn in synonyms:
            syn_clean = syn.strip()
            
            # Ignora códigos do PubChem
            if syn_clean.startswith(('CID', 'SID', 'AID')):
                continue
            
            # Busca CAS number
            if cas_pattern.match(syn_clean) and not cas_number:
                cas_number = syn_clean
            
            # Busca dev codes
            elif dev_pattern.match(syn_clean):
                if len(dev_codes) < 20:  # Limita a 20 dev codes
                    dev_codes.append(syn_clean)
        
        return dev_codes, cas_number
    
    async def get_patent_references(self, molecule_name: str) -> List[str]:
        """Busca referências de patentes no PubChem (cross-references)"""
        url = f"{self.BASE_URL}/compound/name/{molecule_name}/xrefs/PatentID/JSON"
        
        patent_ids = []
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    data = response.json()
                    info_list = data.get("InformationList", {}).get("Information", [])
                    
                    for info in info_list:
                        if "PatentID" in info:
                            patent_ids.extend(info["PatentID"])
                    
                    # Filtra apenas WO numbers
                    wo_numbers = [p for p in patent_ids if isinstance(p, str) and p.startswith("WO")]
                    
                    logger.info(f"  ✓ Patent XRefs: {len(wo_numbers)} WO numbers")
                    return wo_numbers
        except Exception as e:
            logger.error(f"  ❌ Erro ao buscar patent references: {e}")
        
        return []
    
    def generate_search_variations(self, molecule_data: MoleculeData) -> List[str]:
        """Gera variações de busca para patentes"""
        variations = []
        
        # Nome principal
        variations.append(molecule_data.name)
        
        # Dev codes (top 5)
        variations.extend(molecule_data.dev_codes[:5])
        
        # Sinônimos relevantes (top 10, excluindo IUPAC muito longo)
        for syn in molecule_data.synonyms[:20]:
            if len(syn) < 30 and syn not in variations:
                variations.append(syn)
                if len(variations) >= 15:
                    break
        
        # Variações com sufixos para sais, cristais, etc
        base_variations = [
            f"{molecule_data.name} hydrochloride",
            f"{molecule_data.name} tosylate",
            f"{molecule_data.name} crystal",
            f"{molecule_data.name} polymorph",
            f"{molecule_data.name} salt",
            f"{molecule_data.name} pharmaceutical composition",
            f"{molecule_data.name} synthesis",
            f"{molecule_data.name} preparation",
            f"{molecule_data.name} use",
            f"{molecule_data.name} treatment",
            f"{molecule_data.name} enantiomer"
        ]
        
        variations.extend(base_variations)
        
        return variations

# Teste
async def test_pubchem():
    """Teste com Darolutamide"""
    client = PubChemClient()
    
    data = await client.get_molecule_data("Darolutamide")
    
    if data:
        print(f"\n✅ DADOS PUBCHEM:")
        print(f"CID: {data.cid}")
        print(f"Fórmula: {data.molecular_formula}")
        print(f"Peso: {data.molecular_weight}")
        print(f"CAS: {data.cas_number}")
        print(f"Dev codes: {', '.join(data.dev_codes[:5])}")
        print(f"SMILES: {data.smiles[:50]}...")
        print(f"\nSinônimos (top 10):")
        for i, syn in enumerate(data.synonyms[:10], 1):
            print(f"  {i}. {syn}")
        
        # Gera variações
        variations = client.generate_search_variations(data)
        print(f"\n📋 Variações de busca ({len(variations)}):")
        for i, var in enumerate(variations[:15], 1):
            print(f"  {i}. {var}")
        
        # Busca patent references
        patents = await client.get_patent_references("Darolutamide")
        if patents:
            print(f"\n📄 Patent XRefs ({len(patents)}):")
            for p in patents[:10]:
                print(f"  • {p}")

if __name__ == "__main__":
    asyncio.run(test_pubchem())
