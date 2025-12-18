"""
Integration Test - Pharmyrus V5.0
Testa fluxo completo: SuperCrawler -> WO Search -> ClinicalTrials -> Orchestrator
"""
import asyncio
import logging
import os
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_super_crawler():
    """Test 1: SuperCrawler multi-strategy"""
    logger.info("\n" + "="*70)
    logger.info("TEST 1: SuperCrawler Multi-Strategy")
    logger.info("="*70)
    
    from src.core.super_crawler import SuperCrawler
    
    async with SuperCrawler(max_retries=3, timeout=30) as crawler:
        # Test simple URL
        result = await crawler.crawl("https://httpbin.org/html")
        assert result.success, "SuperCrawler failed on simple URL"
        logger.info(f"✅ Simple URL: {result.strategy_used}")
        
        # Test with potential blocking
        result2 = await crawler.crawl("https://www.google.com")
        logger.info(f"✅ Google: success={result2.success}, strategy={result2.strategy_used}")
        
        # Stats
        stats = crawler.get_stats()
        logger.info(f"📊 Stats: {stats}")
    
    logger.info("✅ TEST 1 PASSED\n")


async def test_wo_search():
    """Test 2: WO Number Search"""
    logger.info("\n" + "="*70)
    logger.info("TEST 2: WO Number Search")
    logger.info("="*70)
    
    from src.core.super_crawler import SuperCrawler
    from src.crawlers.wo_search import WONumberSearcher
    
    async with SuperCrawler() as crawler:
        searcher = WONumberSearcher(super_crawler=crawler, serpapi_key=None)
        
        result = await searcher.search_wo_numbers(
            molecule="Darolutamide",
            dev_codes=["ODM-201"],
            cas_number=None,
            brand_name="Nubeqa"
        )
        
        logger.info(f"✅ Found {len(result.wo_numbers)} WO numbers")
        logger.info(f"📊 Sources: {result.sources}")
        
        for wo in list(result.wo_numbers)[:5]:
            logger.info(f"   - {wo}")
        
        await searcher.close()
    
    logger.info("✅ TEST 2 PASSED\n")


async def test_clinical_trials():
    """Test 3: ClinicalTrials.gov Crawler"""
    logger.info("\n" + "="*70)
    logger.info("TEST 3: ClinicalTrials.gov Crawler")
    logger.info("="*70)
    
    from src.core.super_crawler import SuperCrawler
    from src.crawlers.clinicaltrials_crawler import ClinicalTrialsGovCrawler
    
    async with SuperCrawler() as crawler:
        ct_crawler = ClinicalTrialsGovCrawler(super_crawler=crawler)
        
        trials = await ct_crawler.search_by_molecule("Aspirin", max_results=5)
        
        logger.info(f"✅ Found {len(trials)} trials")
        
        for trial in trials:
            logger.info(f"   - {trial.nct_id}: {trial.title[:60]}...")
            logger.info(f"     Phase: {trial.phase}, Status: {trial.status}")
        
        await ct_crawler.close()
    
    logger.info("✅ TEST 3 PASSED\n")


async def test_ai_fallback():
    """Test 4: AI Fallback Processor"""
    logger.info("\n" + "="*70)
    logger.info("TEST 4: AI Fallback Processor")
    logger.info("="*70)
    
    from src.ai.ai_fallback import AIFallbackProcessor
    
    ai = AIFallbackProcessor(max_budget_usd=0.05)
    
    # Test com HTML pequeno
    sample_html = """
    <html>
        <body>
            <div class="patent">WO2020123456</div>
            <div class="patent">WO2021654321</div>
        </body>
    </html>
    """
    
    result = await ai.process_html_for_patents(sample_html, "test_source")
    
    logger.info(f"✅ AI Result: success={result.success}")
    logger.info(f"   Provider: {result.provider_used}")
    logger.info(f"   Cost: ${result.cost:.4f}")
    logger.info(f"   Data: {result.data}")
    
    logger.info("✅ TEST 4 PASSED\n")


async def test_orchestrator_lite():
    """Test 5: Orchestrator V2 (lite version - sem APIs externas caras)"""
    logger.info("\n" + "="*70)
    logger.info("TEST 5: Orchestrator V2 (Lite)")
    logger.info("="*70)
    
    from src.core.parallel_orchestrator_v2 import ParallelOrchestratorV2
    
    async with ParallelOrchestratorV2(
        epo_consumer_key=os.getenv("EPO_CONSUMER_KEY"),
        epo_consumer_secret=os.getenv("EPO_CONSUMER_SECRET"),
        ai_fallback_enabled=False  # Disable para teste rápido
    ) as orchestrator:
        
        # Test apenas PubChem (barato)
        pubchem_data = await orchestrator._get_pubchem_data("Aspirin")
        
        assert pubchem_data is not None, "PubChem failed"
        logger.info(f"✅ PubChem: {pubchem_data.name}")
        logger.info(f"   CAS: {pubchem_data.cas_number}")
        logger.info(f"   Dev codes: {len(pubchem_data.dev_codes)}")
        logger.info(f"   Synonyms: {len(pubchem_data.synonyms)}")
    
    logger.info("✅ TEST 5 PASSED\n")


async def test_debug_logger():
    """Test 6: Debug Logger"""
    logger.info("\n" + "="*70)
    logger.info("TEST 6: Debug Logger")
    logger.info("="*70)
    
    from src.core.debug_logger import DebugLogger
    
    debug = DebugLogger(use_firestore=False, local_storage_path="./test_debug_logs")
    
    # Log HTML
    log_id = await debug.log_html(
        url="https://test.com",
        html="<html><body>Test HTML</body></html>",
        source="test",
        success=True,
        metadata={"test": True}
    )
    
    logger.info(f"✅ HTML logged: {log_id}")
    
    # Retrieve
    retrieved = await debug.get_html(log_id)
    assert retrieved is not None, "Failed to retrieve HTML"
    logger.info(f"✅ HTML retrieved: {len(retrieved)} chars")
    
    # Log error
    error_id = await debug.log_error(
        url="https://test.com",
        error="Test error",
        source="test",
        context={"reason": "testing"}
    )
    
    logger.info(f"✅ Error logged: {error_id}")
    
    # List failed
    failed = await debug.list_failed_urls(source="test", limit=10)
    logger.info(f"✅ Failed URLs: {len(failed)}")
    
    logger.info("✅ TEST 6 PASSED\n")


async def main():
    """Run all tests"""
    start = datetime.now()
    
    logger.info("\n" + "="*70)
    logger.info("🧪 PHARMYRUS V5.0 - INTEGRATION TESTS")
    logger.info("="*70 + "\n")
    
    tests = [
        ("SuperCrawler", test_super_crawler),
        ("WO Search", test_wo_search),
        ("ClinicalTrials", test_clinical_trials),
        ("AI Fallback", test_ai_fallback),
        ("Orchestrator Lite", test_orchestrator_lite),
        ("Debug Logger", test_debug_logger)
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            await test_func()
            passed += 1
        except Exception as e:
            logger.error(f"❌ {name} FAILED: {str(e)}", exc_info=True)
            failed += 1
    
    duration = (datetime.now() - start).total_seconds()
    
    logger.info("\n" + "="*70)
    logger.info("📊 TEST SUMMARY")
    logger.info("="*70)
    logger.info(f"✅ Passed: {passed}/{len(tests)}")
    logger.info(f"❌ Failed: {failed}/{len(tests)}")
    logger.info(f"⏱️  Duration: {duration:.2f}s")
    logger.info("="*70 + "\n")
    
    if failed == 0:
        logger.info("🎉 ALL TESTS PASSED!")
        return 0
    else:
        logger.error("💥 SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
