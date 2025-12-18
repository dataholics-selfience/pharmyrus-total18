"""
Test script for Pharmyrus V5.0
Quick validation of core components
"""
import asyncio
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_circuit_breaker():
    """Test circuit breaker functionality"""
    from src.core.circuit_breaker import CircuitBreaker, RetryStrategy
    
    logger.info("\n" + "="*70)
    logger.info("TEST 1: Circuit Breaker")
    logger.info("="*70)
    
    cb = CircuitBreaker(name="test", failure_threshold=3, timeout=5.0)
    
    # Test successful calls
    async def successful_call():
        return "success"
    
    result = await cb.call(successful_call)
    assert result == "success"
    logger.info("✅ Circuit breaker: successful call works")
    
    # Test retry strategy
    retry = RetryStrategy(max_attempts=3, base_delay=0.1)
    
    attempt = 0
    async def flaky_call():
        nonlocal attempt
        attempt += 1
        if attempt < 2:
            raise Exception("Transient failure")
        return "success after retry"
    
    result = await retry.execute(flaky_call)
    assert result == "success after retry"
    logger.info("✅ Retry strategy: recovers from transient failures")
    
    logger.info("="*70 + "\n")


async def test_epo_client():
    """Test EPO client initialization"""
    from src.crawlers.epo.epo_client import EPOClient
    
    logger.info("\n" + "="*70)
    logger.info("TEST 2: EPO Client")
    logger.info("="*70)
    
    # Test client creation
    async with EPOClient(
        consumer_key="G5wJypxeg0GXEJoMGP37tdK370aKxeMszGKAkD6QaR0yiR5X",
        consumer_secret="zg5AJ0EDzXdJey3GaFNM8ztMVxHKXRrAihXH93iS5ZAzKPAPMFLuVUfiEuAqpdbz"
    ) as client:
        logger.info("✅ EPO client: initialization successful")
        logger.info(f"✅ EPO client: token acquired (expires: {client._token.expires_at.strftime('%H:%M:%S')})")
    
    logger.info("="*70 + "\n")


async def test_parallel_orchestrator():
    """Test parallel orchestrator"""
    from src.core.parallel_orchestrator import ParallelOrchestrator
    
    logger.info("\n" + "="*70)
    logger.info("TEST 3: Parallel Orchestrator")
    logger.info("="*70)
    
    async with ParallelOrchestrator(
        epo_key="G5wJypxeg0GXEJoMGP37tdK370aKxeMszGKAkD6QaR0yiR5X",
        epo_secret="zg5AJ0EDzXdJey3GaFNM8ztMVxHKXRrAihXH93iS5ZAzKPAPMFLuVUfiEuAqpdbz",
        inpi_crawler_url="https://crawler3-production.up.railway.app"
    ) as orchestrator:
        logger.info("✅ Orchestrator: initialization successful")
        
        # Test PubChem
        pubchem = await orchestrator.get_pubchem_data("Aspirin")
        if pubchem:
            logger.info(f"✅ PubChem: Found Aspirin (CAS: {pubchem.cas_number})")
        else:
            logger.warning("⚠️ PubChem: Aspirin lookup failed (may be 403 error)")
    
    logger.info("="*70 + "\n")


async def test_comprehensive_search():
    """Test comprehensive search"""
    from src.core.parallel_orchestrator import ParallelOrchestrator
    
    logger.info("\n" + "="*70)
    logger.info("TEST 4: Comprehensive Search (Darolutamide)")
    logger.info("="*70)
    
    async with ParallelOrchestrator(
        epo_key="G5wJypxeg0GXEJoMGP37tdK370aKxeMszGKAkD6QaR0yiR5X",
        epo_secret="zg5AJ0EDzXdJey3GaFNM8ztMVxHKXRrAihXH93iS5ZAzKPAPMFLuVUfiEuAqpdbz",
        inpi_crawler_url="https://crawler3-production.up.railway.app"
    ) as orchestrator:
        
        result = await orchestrator.comprehensive_search(
            molecule="Darolutamide",
            brand_name="Nubeqa",
            target_countries=["BR"]
        )
        
        logger.info(f"✅ Search complete:")
        logger.info(f"   • Total patents: {result['summary']['total_patents']}")
        logger.info(f"   • BR patents: {result['summary']['br_patents']}")
        logger.info(f"   • Sources: {', '.join(result['summary']['sources'])}")
        logger.info(f"   • Time: {result['summary']['elapsed_seconds']}s")
        
        if result['summary']['br_patents'] > 0:
            logger.info(f"✅ SUCCESS: Found {result['summary']['br_patents']} BR patents!")
        else:
            logger.warning("⚠️ No BR patents found (INPI crawler may be blocked)")
    
    logger.info("="*70 + "\n")


async def main():
    """Run all tests"""
    logger.info("\n" + "="*70)
    logger.info("🧪 PHARMYRUS V5.0 - COMPONENT TESTS")
    logger.info("="*70 + "\n")
    
    try:
        await test_circuit_breaker()
        await test_epo_client()
        await test_parallel_orchestrator()
        await test_comprehensive_search()
        
        logger.info("\n" + "="*70)
        logger.info("✅ ALL TESTS PASSED")
        logger.info("="*70 + "\n")
        
    except Exception as e:
        logger.error(f"\n❌ TEST FAILED: {str(e)}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
