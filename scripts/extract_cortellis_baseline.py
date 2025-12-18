#!/usr/bin/env python3
"""
Cortellis Baseline Extractor
Lê todos os Excel do Cortellis e cria baseline para comparação
"""
import json
import pandas as pd
from pathlib import Path
from typing import Dict, List
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CortellisBaselineExtractor:
    """Extrai baseline do Cortellis de múltiplos Excel"""
    
    def __init__(self, excel_dir: str = "/mnt/project"):
        self.excel_dir = Path(excel_dir)
        self.baseline = {}
        
    def extract_from_excel(self, excel_path: Path) -> Dict:
        """Extrai dados de um Excel do Cortellis"""
        molecule_name = excel_path.stem.replace("_", " ").replace("  validando", "")
        logger.info(f"📊 Processando: {molecule_name}")
        
        try:
            # Tenta ler todas as sheets possíveis
            excel_file = pd.ExcelFile(excel_path)
            
            result = {
                "molecule": molecule_name,
                "br_patents": [],
                "total_patents": 0,
                "jurisdictions": set(),
                "sheets_found": excel_file.sheet_names
            }
            
            # Procura sheet com dados de patentes
            for sheet_name in excel_file.sheet_names:
                try:
                    df = pd.read_excel(excel_path, sheet_name=sheet_name)
                    
                    # Procura colunas relevantes
                    columns_lower = [str(col).lower() for col in df.columns]
                    
                    # Identifica colunas de patente
                    patent_col = None
                    jurisdiction_col = None
                    status_col = None
                    
                    for i, col in enumerate(columns_lower):
                        if any(x in col for x in ['patent', 'publication', 'number', 'patente']):
                            patent_col = df.columns[i]
                        if any(x in col for x in ['jurisdiction', 'country', 'país', 'pais']):
                            jurisdiction_col = df.columns[i]
                        if any(x in col for x in ['status', 'legal']):
                            status_col = df.columns[i]
                    
                    if patent_col:
                        logger.info(f"  ✓ Sheet '{sheet_name}': {len(df)} rows")
                        
                        for _, row in df.iterrows():
                            patent_num = str(row.get(patent_col, "")).strip()
                            
                            if patent_num and patent_num not in ['nan', 'None', '']:
                                # Checa se é BR
                                is_br = False
                                if patent_num.upper().startswith('BR'):
                                    is_br = True
                                elif jurisdiction_col and 'BR' in str(row.get(jurisdiction_col, '')).upper():
                                    is_br = True
                                
                                patent_info = {
                                    "number": patent_num,
                                    "jurisdiction": str(row.get(jurisdiction_col, "")).strip() if jurisdiction_col else "Unknown",
                                    "status": str(row.get(status_col, "")).strip() if status_col else "Unknown",
                                    "is_br": is_br,
                                    "sheet": sheet_name
                                }
                                
                                if is_br:
                                    result["br_patents"].append(patent_info)
                                
                                result["total_patents"] += 1
                                
                                if jurisdiction_col:
                                    juris = str(row.get(jurisdiction_col, "")).strip()
                                    if juris and juris != 'nan':
                                        result["jurisdictions"].add(juris)
                
                except Exception as e:
                    logger.warning(f"  ⚠️  Erro ao ler sheet '{sheet_name}': {e}")
                    continue
            
            result["jurisdictions"] = list(result["jurisdictions"])
            logger.info(f"  ✅ {len(result['br_patents'])} BRs | {result['total_patents']} total")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Erro ao processar {excel_path}: {e}")
            return None
    
    def extract_all(self) -> Dict:
        """Extrai de todos os Excel"""
        logger.info("🔍 Buscando arquivos Excel do Cortellis...")
        
        excel_files = list(self.excel_dir.glob("*.xlsx"))
        logger.info(f"📁 Encontrados {len(excel_files)} arquivos")
        
        for excel_file in sorted(excel_files):
            result = self.extract_from_excel(excel_file)
            if result:
                self.baseline[result["molecule"]] = result
        
        # Estatísticas gerais
        total_molecules = len(self.baseline)
        total_br = sum(len(m["br_patents"]) for m in self.baseline.values())
        total_patents = sum(m["total_patents"] for m in self.baseline.values())
        
        summary = {
            "total_molecules": total_molecules,
            "total_br_patents": total_br,
            "total_patents": total_patents,
            "molecules": self.baseline
        }
        
        logger.info(f"\n📊 RESUMO CORTELLIS BASELINE:")
        logger.info(f"   Moléculas: {total_molecules}")
        logger.info(f"   Patentes BR: {total_br}")
        logger.info(f"   Patentes totais: {total_patents}")
        
        return summary
    
    def save_baseline(self, output_path: str = "/home/claude/pharmyrus-v5/data/cortellis_baseline.json"):
        """Salva baseline em JSON"""
        summary = self.extract_all()
        
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        logger.info(f"\n💾 Baseline salvo em: {output_file}")
        logger.info(f"   Tamanho: {output_file.stat().st_size / 1024:.1f} KB")
        
        return summary

if __name__ == "__main__":
    extractor = CortellisBaselineExtractor()
    baseline = extractor.save_baseline()
    
    # Mostra detalhes de Darolutamide (molécula de teste)
    if "Darulomatide  validando" in baseline["molecules"]:
        daro = baseline["molecules"]["Darulomatide  validando"]
        print(f"\n🎯 DAROLUTAMIDE (baseline de teste):")
        print(f"   BRs encontradas: {len(daro['br_patents'])}")
        print(f"   Patentes totais: {daro['total_patents']}")
        print(f"   BRs:")
        for br in daro["br_patents"]:
            print(f"     - {br['number']} ({br['status']})")
