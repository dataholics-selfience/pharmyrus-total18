"""
Pharmyrus V5.0 - API Usage Examples
Demonstra como usar a API em produção
"""
import httpx
import asyncio
import json


# Configuração
BASE_URL = "http://localhost:8000"  # Alterar para URL do Railway em produção
# BASE_URL = "https://pharmyrus-v5-production.up.railway.app"


async def example_1_health_check():
    """Exemplo 1: Health Check"""
    print("\n" + "="*70)
    print("EXEMPLO 1: Health Check")
    print("="*70)
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/health")
        data = response.json()
        
        print(f"Status: {data['status']}")
        print(f"Version: {data['version']}")
        print(f"Services:")
        for service, status in data['services'].items():
            print(f"  • {service}: {status}")


async def example_2_comprehensive_search():
    """Exemplo 2: Busca Completa de Patentes"""
    print("\n" + "="*70)
    print("EXEMPLO 2: Busca Completa - Darolutamide")
    print("="*70)
    
    search_request = {
        "molecule": "Darolutamide",
        "brand_name": "Nubeqa",
        "target_countries": ["BR"],
        "deep_search": False,
        "timeout_minutes": 5
    }
    
    async with httpx.AsyncClient(timeout=300.0) as client:
        response = await client.post(
            f"{BASE_URL}/api/v1/search",
            json=search_request
        )
        data = response.json()
        
        if data['success']:
            print(f"\n✅ Busca concluída com sucesso!")
            print(f"Molécula: {data['molecule']}")
            print(f"Tempo de execução: {data['execution_time_seconds']:.2f}s")
            print(f"\nResumo:")
            print(f"  • Total de patentes: {data['summary']['total_patents']}")
            print(f"  • Patentes BR: {data['summary']['br_patents']}")
            print(f"  • Fontes consultadas: {', '.join(data['summary']['sources'])}")
            
            if data['summary']['br_patents'] > 0:
                print(f"\n🇧🇷 Primeiras 3 patentes BR:")
                for i, patent in enumerate(data['patents'][:3], 1):
                    print(f"\n  {i}. {patent['publication_number']}")
                    print(f"     Título: {patent['title'][:60]}...")
                    print(f"     Fonte: {patent['source']}")
                    print(f"     Quality Score: {patent['quality_score']}")
        else:
            print(f"❌ Erro: {data}")


async def example_3_pubchem_data():
    """Exemplo 3: Dados Moleculares do PubChem"""
    print("\n" + "="*70)
    print("EXEMPLO 3: Dados PubChem - Aspirin")
    print("="*70)
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/api/v1/molecule/Aspirin/pubchem")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n✅ Dados encontrados!")
            print(f"Molécula: {data['molecule']}")
            print(f"CAS Number: {data['cas_number']}")
            print(f"Development Codes: {', '.join(data['dev_codes'][:5])}")
            print(f"Sinônimos (primeiros 5): {', '.join(data['synonyms'][:5])}")
        else:
            print(f"❌ Molécula não encontrada (status: {response.status_code})")


async def example_4_inpi_search():
    """Exemplo 4: Busca Direta INPI"""
    print("\n" + "="*70)
    print("EXEMPLO 4: Busca INPI Direta")
    print("="*70)
    
    params = {
        "medicine": "Darolutamide",
        "variations": "ODM-201,BAY-1841788"
    }
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.get(
            f"{BASE_URL}/api/v1/inpi/search",
            params=params
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n✅ Busca INPI concluída!")
            print(f"Medicamento: {data['medicine']}")
            print(f"Variações buscadas: {data['variations']}")
            print(f"Total de resultados: {data['total_results']}")
            
            if data['total_results'] > 0:
                print(f"\nPrimeiro resultado:")
                first = data['results'][0]
                print(f"  • Número: {first['publication_number']}")
                print(f"  • Título: {first['title'][:60]}...")
        else:
            print(f"❌ Erro: {response.status_code}")


async def example_5_epo_family():
    """Exemplo 5: Família de Patentes EPO"""
    print("\n" + "="*70)
    print("EXEMPLO 5: Família de Patentes EPO")
    print("="*70)
    
    wo_number = "WO2011156378"
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(f"{BASE_URL}/api/v1/epo/family/{wo_number}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n✅ Família EPO encontrada!")
            print(f"WO Number: {data['wo_number']}")
            print(f"Patentes BR encontradas: {data['br_patents_count']}")
            
            if data['br_patents_count'] > 0:
                print(f"\nPatentes BR:")
                for br in data['br_patents']:
                    print(f"  • {br['publication_number']}")
        else:
            print(f"❌ Erro: {response.status_code}")


async def example_6_batch_search():
    """Exemplo 6: Busca em Lote"""
    print("\n" + "="*70)
    print("EXEMPLO 6: Busca em Lote (Múltiplas Moléculas)")
    print("="*70)
    
    molecules = ["Aspirin", "Paracetamol", "Ibuprofen"]
    
    async with httpx.AsyncClient(timeout=300.0) as client:
        tasks = []
        for molecule in molecules:
            request = {
                "molecule": molecule,
                "target_countries": ["BR"],
                "deep_search": False,
                "timeout_minutes": 5
            }
            tasks.append(
                client.post(f"{BASE_URL}/api/v1/search", json=request)
            )
        
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        print(f"\n✅ Busca em lote concluída!")
        for molecule, response in zip(molecules, responses):
            if isinstance(response, Exception):
                print(f"  ❌ {molecule}: Erro - {str(response)}")
            else:
                data = response.json()
                if data['success']:
                    print(f"  ✅ {molecule}: {data['summary']['br_patents']} patentes BR")
                else:
                    print(f"  ❌ {molecule}: Falhou")


async def main():
    """Executar todos os exemplos"""
    print("\n" + "="*70)
    print("🔬 PHARMYRUS V5.0 - EXEMPLOS DE USO DA API")
    print("="*70)
    print(f"\nBase URL: {BASE_URL}")
    
    try:
        # Exemplo 1: Health Check
        await example_1_health_check()
        
        # Exemplo 2: Busca completa
        # await example_2_comprehensive_search()
        
        # Exemplo 3: PubChem
        # await example_3_pubchem_data()
        
        # Exemplo 4: INPI
        # await example_4_inpi_search()
        
        # Exemplo 5: EPO Family
        # await example_5_epo_family()
        
        # Exemplo 6: Batch search
        # await example_6_batch_search()
        
        print("\n" + "="*70)
        print("✅ Exemplos executados com sucesso!")
        print("="*70 + "\n")
        
        print("💡 Dica: Descomente os outros exemplos em main() para testar")
        print("   todas as funcionalidades da API!")
        
    except httpx.ConnectError:
        print("\n" + "="*70)
        print("❌ ERRO: Não foi possível conectar ao servidor")
        print("="*70)
        print("\nCertifique-se de que:")
        print("  1. O servidor está rodando")
        print("  2. A URL está correta")
        print("  3. A porta está acessível")
        print("\nPara iniciar o servidor:")
        print("  python main.py")
        print("\nOu altere BASE_URL para o endpoint Railway")
        
    except Exception as e:
        print(f"\n❌ Erro: {str(e)}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
