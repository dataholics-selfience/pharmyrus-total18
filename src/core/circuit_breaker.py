"""
Circuit Breaker Pattern for resilient API calls
Implements failure detection, fallback strategies, and intelligent recovery
"""
import asyncio
import logging
import time
from enum import Enum
from typing import Callable, Any, Optional
from datetime import datetime, timedelta
import random

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, rejecting calls
    HALF_OPEN = "half_open"  # Testing recovery


class CircuitBreakerError(Exception):
    """Raised when circuit is open"""
    pass


class CircuitBreaker:
    """
    Circuit breaker with:
    - Failure threshold tracking
    - Automatic state transitions
    - Exponential backoff
    - Jitter for thundering herd prevention
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout: float = 60.0,
        error_threshold_percentage: float = 60.0,
        name: str = "default"
    ):
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout = timeout
        self.error_threshold_percentage = error_threshold_percentage
        self.name = name
        
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._total_calls = 0
        self._total_failures = 0
        
    @property
    def state(self) -> CircuitState:
        """Get current circuit state"""
        return self._state
    
    def _should_attempt_reset(self) -> bool:
        """Check if we should try to reset from OPEN to HALF_OPEN"""
        if self._state != CircuitState.OPEN:
            return False
        
        if self._last_failure_time is None:
            return True
        
        return datetime.now() >= self._last_failure_time + timedelta(seconds=self.timeout)
    
    def _calculate_failure_rate(self) -> float:
        """Calculate failure percentage"""
        if self._total_calls == 0:
            return 0.0
        return (self._total_failures / self._total_calls) * 100
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection
        
        Args:
            func: Async function to execute
            *args, **kwargs: Function arguments
            
        Returns:
            Function result
            
        Raises:
            CircuitBreakerError: If circuit is open
        """
        # Check if we should attempt reset
        if self._should_attempt_reset():
            logger.info(f"🔄 [{self.name}] Attempting reset to HALF_OPEN")
            self._state = CircuitState.HALF_OPEN
            self._failure_count = 0
            self._success_count = 0
        
        # Reject if circuit is OPEN
        if self._state == CircuitState.OPEN:
            logger.warning(f"⚠️ [{self.name}] Circuit is OPEN, rejecting call")
            raise CircuitBreakerError(f"Circuit breaker '{self.name}' is OPEN")
        
        self._total_calls += 1
        
        try:
            # Execute the function
            result = await func(*args, **kwargs)
            
            # Record success
            self._on_success()
            return result
            
        except Exception as e:
            # Record failure
            self._on_failure()
            raise e
    
    def _on_success(self):
        """Handle successful call"""
        self._success_count += 1
        
        if self._state == CircuitState.HALF_OPEN:
            if self._success_count >= self.success_threshold:
                logger.info(f"✅ [{self.name}] Circuit CLOSED (recovery successful)")
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                self._success_count = 0
        
        # Reset failure count on success in CLOSED state
        if self._state == CircuitState.CLOSED:
            self._failure_count = 0
    
    def _on_failure(self):
        """Handle failed call"""
        self._failure_count += 1
        self._total_failures += 1
        self._last_failure_time = datetime.now()
        
        # In HALF_OPEN, any failure reopens circuit
        if self._state == CircuitState.HALF_OPEN:
            logger.warning(f"❌ [{self.name}] Circuit reopened (failure during recovery)")
            self._state = CircuitState.OPEN
            self._success_count = 0
            return
        
        # Check failure threshold
        failure_rate = self._calculate_failure_rate()
        
        if (self._failure_count >= self.failure_threshold or 
            failure_rate >= self.error_threshold_percentage):
            logger.error(
                f"🔴 [{self.name}] Circuit OPENED "
                f"(failures: {self._failure_count}/{self.failure_threshold}, "
                f"rate: {failure_rate:.1f}%)"
            )
            self._state = CircuitState.OPEN
    
    def reset(self):
        """Manually reset circuit breaker"""
        logger.info(f"🔄 [{self.name}] Manual reset")
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._total_calls = 0
        self._total_failures = 0
        self._last_failure_time = None


class RetryStrategy:
    """
    Exponential backoff with jitter for retry logic
    Based on AWS best practices
    """
    
    def __init__(
        self,
        max_attempts: int = 5,
        base_delay: float = 0.1,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
    
    def calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for given attempt number
        
        Formula: min(max_delay, base_delay * (exponential_base ^ attempt))
        With jitter: delay ± random(0, delay * 0.2)
        """
        delay = min(
            self.max_delay,
            self.base_delay * (self.exponential_base ** attempt)
        )
        
        if self.jitter:
            # Add ±20% random jitter
            jitter_amount = delay * 0.2
            delay += random.uniform(-jitter_amount, jitter_amount)
        
        return max(0, delay)
    
    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with retry logic
        
        Args:
            func: Async function to execute
            *args, **kwargs: Function arguments
            
        Returns:
            Function result
            
        Raises:
            Last exception if all retries exhausted
        """
        last_exception = None
        
        for attempt in range(self.max_attempts):
            try:
                result = await func(*args, **kwargs)
                
                if attempt > 0:
                    logger.info(f"✅ Retry successful on attempt {attempt + 1}")
                
                return result
                
            except Exception as e:
                last_exception = e
                
                if attempt < self.max_attempts - 1:
                    delay = self.calculate_delay(attempt)
                    logger.warning(
                        f"⚠️ Attempt {attempt + 1}/{self.max_attempts} failed: {str(e)[:100]} "
                        f"(retrying in {delay:.2f}s)"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"❌ All {self.max_attempts} attempts failed: {str(e)[:100]}"
                    )
        
        raise last_exception


class RateLimiter:
    """
    Multi-provider rate limiter with different strategies
    """
    
    def __init__(self, limits: dict):
        """
        Args:
            limits: Dict of provider -> {per_minute: int, per_hour: int, ...}
        """
        self.limits = limits
        self._counters = {}
        self._windows = {}
        
    async def acquire(self, provider: str) -> bool:
        """
        Acquire rate limit token for provider
        
        Returns:
            True if request allowed, False if rate limited
        """
        if provider not in self.limits:
            return True
        
        now = time.time()
        
        # Initialize if needed
        if provider not in self._counters:
            self._counters[provider] = {'minute': [], 'hour': []}
            self._windows[provider] = {'minute': now, 'hour': now}
        
        # Clean old requests
        self._clean_old_requests(provider, now)
        
        # Check limits
        limits = self.limits[provider]
        
        if 'per_minute' in limits:
            if len(self._counters[provider]['minute']) >= limits['per_minute']:
                return False
        
        if 'per_hour' in limits:
            if len(self._counters[provider]['hour']) >= limits['per_hour']:
                return False
        
        # Record request
        self._counters[provider]['minute'].append(now)
        self._counters[provider]['hour'].append(now)
        
        return True
    
    def _clean_old_requests(self, provider: str, now: float):
        """Remove requests outside time windows"""
        # Remove requests older than 1 minute
        self._counters[provider]['minute'] = [
            t for t in self._counters[provider]['minute']
            if now - t < 60
        ]
        
        # Remove requests older than 1 hour
        self._counters[provider]['hour'] = [
            t for t in self._counters[provider]['hour']
            if now - t < 3600
        ]
    
    async def wait_if_needed(self, provider: str):
        """Wait until rate limit allows request"""
        while not await self.acquire(provider):
            await asyncio.sleep(0.1)
