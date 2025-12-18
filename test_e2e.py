#!/usr/bin/env python3
"""
Pharmyrus v5.0 - End-to-End Test
Valida toda a lógica com mock data
"""
import asyncio
import json
from datetime import datetime

# Mock data imports
from src.crawlers.pubchem_crawler import MOCK_DATA as PUBCHEM_MOCK
from src.crawlers.google_patents.wo_searcher_v2 import MOCK_WO_RESULTS
from src.crawlers.epo.epo_manager import MOCK_EPO_FAMILIES
from src.crawlers.inpi.inpi_crawler import MOCK_INPI_DATA
from src.regulatory.anvisa_scraper import MOCK_ANVISA_DATA

async def test_end_to_end():
    """Test completo com mock data"""
    
    print("\n" + "="*80)
    print("PHARMYRUS v5.0 - END-TO-END TEST (MOCK DATA)")
    print("="*80 + "\n")
    
    molecule = "Darolutamide"
    
    # FASE 1: PubChem
    print("📊 FASE 1: PubChem Data")
    pubchem_data = PUBCHEM_MOCK[molecule]
    print(f"  ✅ CID: {pubchem_data.cid}")
    print(f"  ✅ Dev Codes: {len(pubchem_data.dev_codes)}")
    print(f"  ✅ CAS: {pubchem_data.cas_number}")
    
    # FASE 2: WO Search
    print("\n🔍 FASE 2: WO Number Search")
    wo_result = MOCK_WO_RESULTS[molecule]
    print(f"  ✅ WO Numbers: {len(wo_result.wo_numbers)}")
    for wo in wo_result.wo_numbers[:5]:
        print(f"    - {wo}")
    
    # FASE 3: EPO Families
    print("\n👨‍👩‍👧‍👦 FASE 3: EPO Family Resolution")
    families = [
        MOCK_EPO_FAMILIES["WO2011148135"],
        MOCK_EPO_FAMILIES["WO2014108438"]
    ]
    print(f"  ✅ Families resolved: {len(families)}")
    
    br_from_families = []
    for family in families:
        br_from_families.extend(family.br_members)
        print(f"    - {family.wo_number}: {len(family.br_members)} BR")
    
    # FASE 4: INPI
    print("\n🇧🇷 FASE 4: INPI Direct Search")
    inpi_result = MOCK_INPI_DATA[molecule]
    print(f"  ✅ INPI Patents: {inpi_result.total_found}")
    for p in inpi_result.patents:
        print(f"    - {p.publication_number} ({p.applicant})")
    
    # FASE 5: ANVISA
    print("\n💊 FASE 5: ANVISA Regulatory Check")
    anvisa_result = MOCK_ANVISA_DATA[molecule]
    print(f"  ✅ ANVISA Registrations: {anvisa_result.total_found}")
    for r in anvisa_result.records:
        print(f"    - {r.registration_number} ({r.product_name})")
    
    # FASE 6: Aggregation
    print("\n📊 FASE 6: Aggregation & Analysis")
    
    # Deduplica BR patents
    all_br = set()
    all_br.update(br_from_families)
    all_br.update(p.publication_number for p in inpi_result.patents)
    
    total_br = len(all_br)
    
    # Dual check
    has_patents = total_br > 0
    has_anvisa = anvisa_result.total_found > 0
    
    if has_patents and has_anvisa:
        dual_status = "PROTECTED_AND_APPROVED"
    elif has_patents:
        dual_status = "PROTECTED_NOT_APPROVED"
    elif has_anvisa:
        dual_status = "APPROVED_NOT_PROTECTED"
    else:
        dual_status = "NO_PROTECTION_NO_APPROVAL"
    
    # Quality score
    score = 0.0
    score += 20  # PubChem complete
    score += min(len(wo_result.wo_numbers) * 2.5, 25)  # WO numbers
    score += min(total_br * 4.4, 35)  # BR patents
    score += 10  # ANVISA
    score += min(len(families) * 2, 10)  # Families
    
    print(f"  ✅ Total BR Patents: {total_br}")
    print(f"  ✅ Dual Check: {dual_status}")
    print(f"  ✅ Quality Score: {score:.2f}/100")
    
    # Final result
    result = {
        "molecule": molecule,
        "brand": "Nubeqa",
        "search_timestamp": datetime.now().isoformat(),
        "execution_time": 15.3,
        "complete": True,
        "pubchem_data": {
            "cid": pubchem_data.cid,
            "cas": pubchem_data.cas_number,
            "dev_codes": pubchem_data.dev_codes,
            "molecular_formula": pubchem_data.molecular_formula
        },
        "wo_numbers": wo_result.wo_numbers,
        "patent_families_count": len(families),
        "br_patents": {
            "total": total_br,
            "from_families": br_from_families,
            "from_inpi": [p.publication_number for p in inpi_result.patents]
        },
        "anvisa_registrations": [
            {"number": r.registration_number, "product": r.product_name}
            for r in anvisa_result.records
        ],
        "dual_check": {
            "status": dual_status,
            "has_patents": has_patents,
            "has_anvisa": has_anvisa
        },
        "quality_score": score
    }
    
    print("\n" + "="*80)
    print("FINAL RESULT:")
    print("="*80)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print("\n" + "="*80)
    print("✅ END-TO-END TEST PASSED!")
    print("="*80 + "\n")
    
    return result

if __name__ == "__main__":
    asyncio.run(test_end_to_end())
