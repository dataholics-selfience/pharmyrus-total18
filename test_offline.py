"""
Simple offline tests for core components
No network dependencies
"""
import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_imports():
    """Test all imports work"""
    logger.info("\n" + "="*70)
    logger.info("TEST 1: Module Imports")
    logger.info("="*70)
    
    try:
        from src.core.circuit_breaker import CircuitBreaker, RetryStrategy, RateLimiter
        logger.info("✅ Circuit breaker imports OK")
        
        from src.crawlers.epo.epo_client import EPOClient
        logger.info("✅ EPO client imports OK")
        
        from src.core.parallel_orchestrator import ParallelOrchestrator
        logger.info("✅ Parallel orchestrator imports OK")
        
        return True
    except Exception as e:
        logger.error(f"❌ Import failed: {str(e)}")
        return False


async def test_circuit_breaker():
    """Test circuit breaker logic"""
    logger.info("\n" + "="*70)
    logger.info("TEST 2: Circuit Breaker Logic")
    logger.info("="*70)
    
    from src.core.circuit_breaker import CircuitBreaker, RetryStrategy
    
    # Test successful call
    cb = CircuitBreaker(name="test", failure_threshold=3)
    
    async def success():
        return "OK"
    
    result = await cb.call(success)
    assert result == "OK"
    logger.info("✅ Successful calls work")
    
    # Test retry logic
    retry = RetryStrategy(max_attempts=3, base_delay=0.05)
    
    attempt = 0
    async def flaky():
        nonlocal attempt
        attempt += 1
        if attempt < 2:
            raise Exception("Transient")
        return "SUCCESS"
    
    result = await retry.execute(flaky)
    assert result == "SUCCESS"
    logger.info("✅ Retry strategy works")
    
    return True


async def test_rate_limiter():
    """Test rate limiter"""
    logger.info("\n" + "="*70)
    logger.info("TEST 3: Rate Limiter")
    logger.info("="*70)
    
    from src.core.circuit_breaker import RateLimiter
    
    limiter = RateLimiter({'test': {'per_minute': 10}})
    
    # Should allow first 10 requests
    for i in range(10):
        allowed = await limiter.acquire('test')
        assert allowed, f"Request {i+1} should be allowed"
    
    logger.info("✅ Rate limiter allows requests within limit")
    
    # 11th should be blocked
    allowed = await limiter.acquire('test')
    assert not allowed, "11th request should be blocked"
    
    logger.info("✅ Rate limiter blocks excess requests")
    
    return True


async def test_data_models():
    """Test data models"""
    logger.info("\n" + "="*70)
    logger.info("TEST 4: Data Models")
    logger.info("="*70)
    
    from src.core.parallel_orchestrator import SearchResult, MoleculeData
    
    # Test SearchResult
    result = SearchResult(
        publication_number="BR112013000001",
        country="BR",
        title="Test Patent",
        source="test"
    )
    assert result.publication_number == "BR112013000001"
    logger.info("✅ SearchResult model OK")
    
    # Test MoleculeData
    mol = MoleculeData(
        name="Aspirin",
        cas_number="50-78-2",
        dev_codes=["ASA-001"]
    )
    assert mol.name == "Aspirin"
    logger.info("✅ MoleculeData model OK")
    
    return True


async def main():
    """Run all tests"""
    logger.info("\n" + "="*70)
    logger.info("🧪 PHARMYRUS V5.0 - OFFLINE TESTS")
    logger.info("="*70 + "\n")
    
    results = []
    
    try:
        results.append(await test_imports())
        results.append(await test_circuit_breaker())
        results.append(await test_rate_limiter())
        results.append(await test_data_models())
        
        if all(results):
            logger.info("\n" + "="*70)
            logger.info("✅ ALL TESTS PASSED")
            logger.info("="*70 + "\n")
            logger.info("🚀 System ready for deployment!")
            logger.info("   • Core components: ✅")
            logger.info("   • Circuit breakers: ✅")
            logger.info("   • Rate limiters: ✅")
            logger.info("   • Data models: ✅")
            logger.info("="*70 + "\n")
        else:
            logger.error("❌ Some tests failed")
            
    except Exception as e:
        logger.error(f"❌ Test suite failed: {str(e)}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
