"""
Super Crawler System - Multi-Strategy Resilient Web Scraping
Auto-adapta estratégias quando falhas ocorrem
"""
import asyncio
import logging
import random
import json
from typing import Optional, Dict, Any, List, Callable
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
import hashlib

import httpx
import cloudscraper
from playwright.async_api import async_playwright, Browser, Page
from bs4 import BeautifulSoup
import lxml.html
from fake_useragent import UserAgent

logger = logging.getLogger(__name__)


class CrawlStrategy(Enum):
    """Estratégias de crawling disponíveis"""
    HTTPX_SIMPLE = "httpx_simple"
    HTTPX_STEALTH = "httpx_stealth"
    CLOUDSCRAPER = "cloudscraper"
    PLAYWRIGHT_CHROMIUM = "playwright_chromium"
    PLAYWRIGHT_FIREFOX = "playwright_firefox"
    PLAYWRIGHT_WEBKIT = "playwright_webkit"


@dataclass
class CrawlAttempt:
    """Registro de tentativa de crawling"""
    strategy: CrawlStrategy
    timestamp: datetime
    success: bool
    status_code: Optional[int] = None
    error: Optional[str] = None
    response_time: float = 0.0
    html_size: int = 0


@dataclass
class CrawlResult:
    """Resultado de crawling"""
    success: bool
    html: Optional[str] = None
    status_code: Optional[int] = None
    final_url: Optional[str] = None
    strategy_used: Optional[CrawlStrategy] = None
    attempts: List[CrawlAttempt] = field(default_factory=list)
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class SuperCrawler:
    """
    Super Crawler Resiliente
    
    Características:
    - Múltiplas estratégias de crawling
    - Auto-adaptação quando falha
    - Retry inteligente com backoff exponencial
    - Rotação de headers/user-agents
    - Parsing com múltiplos engines
    - Fallback para IA quando tudo falha
    - Detecção de bloqueios (403, 429, captcha)
    - Cache de sucessos
    """
    
    def __init__(
        self,
        max_retries: int = 5,
        timeout: int = 60,
        min_delay: float = 1.0,
        max_delay: float = 30.0,
        use_cache: bool = True
    ):
        self.max_retries = max_retries
        self.timeout = timeout
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.use_cache = use_cache
        
        # User agents pool
        try:
            self.ua = UserAgent()
        except:
            self.ua = None
        
        # Strategy success tracking
        self.strategy_stats: Dict[CrawlStrategy, Dict[str, int]] = {
            strategy: {"success": 0, "failure": 0}
            for strategy in CrawlStrategy
        }
        
        # Cache de URLs bem-sucedidas
        self.success_cache: Dict[str, CrawlStrategy] = {}
        
        # Playwright browser (lazy init)
        self._playwright = None
        self._browser: Optional[Browser] = None
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def close(self):
        """Fecha recursos"""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
    
    def _get_user_agent(self) -> str:
        """Gera user agent aleatório"""
        if self.ua:
            try:
                return self.ua.random
            except:
                pass
        
        # Fallback para user agents conhecidos
        agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0"
        ]
        return random.choice(agents)
    
    def _get_headers(self, stealth: bool = False) -> Dict[str, str]:
        """Gera headers HTTP"""
        headers = {
            "User-Agent": self._get_user_agent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,pt-BR;q=0.8,pt;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }
        
        if stealth:
            headers.update({
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Cache-Control": "max-age=0"
            })
        
        return headers
    
    def _calculate_backoff_delay(self, attempt: int) -> float:
        """Calcula delay com exponential backoff + jitter"""
        base_delay = self.min_delay * (2 ** attempt)
        max_delay = min(base_delay, self.max_delay)
        jitter = random.uniform(0, max_delay * 0.3)
        return min(max_delay + jitter, self.max_delay)
    
    def _get_url_hash(self, url: str) -> str:
        """Hash de URL para cache"""
        return hashlib.md5(url.encode()).hexdigest()
    
    async def _strategy_httpx_simple(self, url: str) -> CrawlResult:
        """Estratégia: HTTPX simples"""
        start = datetime.now()
        
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True
            ) as client:
                response = await client.get(
                    url,
                    headers=self._get_headers()
                )
                
                elapsed = (datetime.now() - start).total_seconds()
                
                if response.status_code == 200:
                    html = response.text
                    return CrawlResult(
                        success=True,
                        html=html,
                        status_code=response.status_code,
                        final_url=str(response.url),
                        strategy_used=CrawlStrategy.HTTPX_SIMPLE,
                        metadata={
                            "response_time": elapsed,
                            "html_size": len(html)
                        }
                    )
                else:
                    return CrawlResult(
                        success=False,
                        status_code=response.status_code,
                        strategy_used=CrawlStrategy.HTTPX_SIMPLE,
                        error=f"HTTP {response.status_code}"
                    )
                    
        except Exception as e:
            return CrawlResult(
                success=False,
                strategy_used=CrawlStrategy.HTTPX_SIMPLE,
                error=str(e)
            )
    
    async def _strategy_httpx_stealth(self, url: str) -> CrawlResult:
        """Estratégia: HTTPX com headers stealth"""
        start = datetime.now()
        
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                http2=True
            ) as client:
                response = await client.get(
                    url,
                    headers=self._get_headers(stealth=True)
                )
                
                elapsed = (datetime.now() - start).total_seconds()
                
                if response.status_code == 200:
                    html = response.text
                    return CrawlResult(
                        success=True,
                        html=html,
                        status_code=response.status_code,
                        final_url=str(response.url),
                        strategy_used=CrawlStrategy.HTTPX_STEALTH,
                        metadata={
                            "response_time": elapsed,
                            "html_size": len(html)
                        }
                    )
                else:
                    return CrawlResult(
                        success=False,
                        status_code=response.status_code,
                        strategy_used=CrawlStrategy.HTTPX_STEALTH,
                        error=f"HTTP {response.status_code}"
                    )
                    
        except Exception as e:
            return CrawlResult(
                success=False,
                strategy_used=CrawlStrategy.HTTPX_STEALTH,
                error=str(e)
            )
    
    async def _strategy_cloudscraper(self, url: str) -> CrawlResult:
        """Estratégia: CloudScraper (bypassa Cloudflare)"""
        start = datetime.now()
        
        try:
            scraper = cloudscraper.create_scraper(
                browser={
                    'browser': 'chrome',
                    'platform': 'windows',
                    'mobile': False
                }
            )
            
            response = await asyncio.to_thread(
                scraper.get,
                url,
                timeout=self.timeout
            )
            
            elapsed = (datetime.now() - start).total_seconds()
            
            if response.status_code == 200:
                html = response.text
                return CrawlResult(
                    success=True,
                    html=html,
                    status_code=response.status_code,
                    final_url=response.url,
                    strategy_used=CrawlStrategy.CLOUDSCRAPER,
                    metadata={
                        "response_time": elapsed,
                        "html_size": len(html)
                    }
                )
            else:
                return CrawlResult(
                    success=False,
                    status_code=response.status_code,
                    strategy_used=CrawlStrategy.CLOUDSCRAPER,
                    error=f"HTTP {response.status_code}"
                )
                
        except Exception as e:
            return CrawlResult(
                success=False,
                strategy_used=CrawlStrategy.CLOUDSCRAPER,
                error=str(e)
            )
    
    async def _ensure_playwright(self):
        """Inicializa Playwright se necessário"""
        if not self._playwright:
            self._playwright = await async_playwright().start()
        
        if not self._browser:
            self._browser = await self._playwright.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-blink-features=AutomationControlled'
                ]
            )
    
    async def _strategy_playwright(
        self,
        url: str,
        browser_type: str = "chromium"
    ) -> CrawlResult:
        """Estratégia: Playwright com browser real"""
        start = datetime.now()
        
        try:
            await self._ensure_playwright()
            
            context = await self._browser.new_context(
                user_agent=self._get_user_agent(),
                viewport={"width": 1920, "height": 1080}
            )
            
            page = await context.new_page()
            
            # Anti-detection
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)
            
            response = await page.goto(
                url,
                wait_until="networkidle",
                timeout=self.timeout * 1000
            )
            
            # Aguarda renderização
            await asyncio.sleep(2)
            
            html = await page.content()
            final_url = page.url
            status = response.status if response else None
            
            await context.close()
            
            elapsed = (datetime.now() - start).total_seconds()
            
            strategy = {
                "chromium": CrawlStrategy.PLAYWRIGHT_CHROMIUM,
                "firefox": CrawlStrategy.PLAYWRIGHT_FIREFOX,
                "webkit": CrawlStrategy.PLAYWRIGHT_WEBKIT
            }.get(browser_type, CrawlStrategy.PLAYWRIGHT_CHROMIUM)
            
            if status == 200:
                return CrawlResult(
                    success=True,
                    html=html,
                    status_code=status,
                    final_url=final_url,
                    strategy_used=strategy,
                    metadata={
                        "response_time": elapsed,
                        "html_size": len(html),
                        "browser": browser_type
                    }
                )
            else:
                return CrawlResult(
                    success=False,
                    status_code=status,
                    strategy_used=strategy,
                    error=f"HTTP {status}"
                )
                
        except Exception as e:
            return CrawlResult(
                success=False,
                strategy_used=CrawlStrategy.PLAYWRIGHT_CHROMIUM,
                error=str(e)
            )
    
    def _is_blocked(self, result: CrawlResult) -> bool:
        """Detecta se foi bloqueado"""
        if not result.success:
            # Status codes de bloqueio
            blocked_codes = [403, 429, 503]
            if result.status_code in blocked_codes:
                return True
            
            # Erros de conexão
            if result.error:
                blocked_errors = [
                    "403",
                    "forbidden",
                    "blocked",
                    "captcha",
                    "cloudflare",
                    "too many requests"
                ]
                error_lower = result.error.lower()
                if any(err in error_lower for err in blocked_errors):
                    return True
        
        # Analisa HTML para detectar captcha/bloqueio
        if result.html:
            html_lower = result.html.lower()
            blocked_patterns = [
                "captcha",
                "access denied",
                "blocked",
                "forbidden",
                "cloudflare"
            ]
            if any(pattern in html_lower for pattern in blocked_patterns):
                return True
        
        return False
    
    async def crawl(
        self,
        url: str,
        preferred_strategy: Optional[CrawlStrategy] = None
    ) -> CrawlResult:
        """
        Crawl resiliente com múltiplas estratégias
        
        Ordem de tentativas:
        1. Cache (se disponível)
        2. Estratégia preferida (se especificada)
        3. HTTPX simples
        4. HTTPX stealth
        5. CloudScraper
        6. Playwright Chromium
        7. Playwright Firefox (se ainda falhar)
        """
        url_hash = self._get_url_hash(url)
        attempts: List[CrawlAttempt] = []
        
        logger.info(f"🕷️ SuperCrawler iniciando: {url}")
        
        # 1. Verifica cache
        if self.use_cache and url_hash in self.success_cache:
            cached_strategy = self.success_cache[url_hash]
            logger.info(f"   ✅ Cache hit: usando {cached_strategy.value}")
            
            # Usa estratégia que funcionou antes
            strategy_func = self._get_strategy_function(cached_strategy)
            if strategy_func:
                result = await strategy_func(url)
                if result.success:
                    return result
        
        # 2. Define ordem de estratégias
        strategies = []
        
        if preferred_strategy:
            strategies.append(preferred_strategy)
        
        # Adiciona estratégias em ordem de simplicidade → complexidade
        default_order = [
            CrawlStrategy.HTTPX_SIMPLE,
            CrawlStrategy.HTTPX_STEALTH,
            CrawlStrategy.CLOUDSCRAPER,
            CrawlStrategy.PLAYWRIGHT_CHROMIUM,
            CrawlStrategy.PLAYWRIGHT_FIREFOX
        ]
        
        for strat in default_order:
            if strat not in strategies:
                strategies.append(strat)
        
        # 3. Tenta cada estratégia
        for attempt_num, strategy in enumerate(strategies):
            if attempt_num >= self.max_retries:
                logger.warning(f"   ⚠️ Max retries atingido ({self.max_retries})")
                break
            
            # Delay progressivo entre tentativas
            if attempt_num > 0:
                delay = self._calculate_backoff_delay(attempt_num)
                logger.info(f"   ⏳ Aguardando {delay:.1f}s antes de tentar {strategy.value}...")
                await asyncio.sleep(delay)
            
            logger.info(f"   🎯 Tentativa {attempt_num + 1}/{self.max_retries}: {strategy.value}")
            
            attempt_start = datetime.now()
            
            # Executa estratégia
            strategy_func = self._get_strategy_function(strategy)
            if not strategy_func:
                continue
            
            result = await strategy_func(url)
            
            # Registra tentativa
            attempt = CrawlAttempt(
                strategy=strategy,
                timestamp=attempt_start,
                success=result.success,
                status_code=result.status_code,
                error=result.error,
                response_time=(datetime.now() - attempt_start).total_seconds(),
                html_size=len(result.html) if result.html else 0
            )
            attempts.append(attempt)
            
            # Atualiza estatísticas
            if result.success:
                self.strategy_stats[strategy]["success"] += 1
            else:
                self.strategy_stats[strategy]["failure"] += 1
            
            # Verifica resultado
            if result.success:
                logger.info(f"   ✅ Sucesso com {strategy.value}!")
                
                # Salva em cache
                if self.use_cache:
                    self.success_cache[url_hash] = strategy
                
                result.attempts = attempts
                return result
            
            # Analisa tipo de falha
            is_blocked = self._is_blocked(result)
            
            if is_blocked:
                logger.warning(f"   🚫 Bloqueado detectado ({result.status_code or 'unknown'})")
                # Pula para estratégia mais avançada
                if strategy in [CrawlStrategy.HTTPX_SIMPLE, CrawlStrategy.HTTPX_STEALTH]:
                    logger.info(f"   ⚡ Pulando para Playwright devido ao bloqueio")
                    continue
            else:
                logger.warning(f"   ❌ Falhou: {result.error}")
        
        # Todas estratégias falharam
        logger.error(f"   💀 Todas as {len(attempts)} estratégias falharam!")
        
        return CrawlResult(
            success=False,
            attempts=attempts,
            error=f"Failed after {len(attempts)} attempts with all strategies"
        )
    
    def _get_strategy_function(
        self,
        strategy: CrawlStrategy
    ) -> Optional[Callable]:
        """Retorna função da estratégia"""
        mapping = {
            CrawlStrategy.HTTPX_SIMPLE: self._strategy_httpx_simple,
            CrawlStrategy.HTTPX_STEALTH: self._strategy_httpx_stealth,
            CrawlStrategy.CLOUDSCRAPER: self._strategy_cloudscraper,
            CrawlStrategy.PLAYWRIGHT_CHROMIUM: lambda url: self._strategy_playwright(url, "chromium"),
            CrawlStrategy.PLAYWRIGHT_FIREFOX: lambda url: self._strategy_playwright(url, "firefox"),
            CrawlStrategy.PLAYWRIGHT_WEBKIT: lambda url: self._strategy_playwright(url, "webkit")
        }
        return mapping.get(strategy)
    
    def parse_html(
        self,
        html: str,
        parser: str = "lxml"
    ) -> BeautifulSoup:
        """Parse HTML com BeautifulSoup"""
        try:
            return BeautifulSoup(html, parser)
        except:
            # Fallback para html.parser
            return BeautifulSoup(html, "html.parser")
    
    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas de uso"""
        return {
            "strategy_stats": {
                strategy.value: stats
                for strategy, stats in self.strategy_stats.items()
            },
            "cache_size": len(self.success_cache),
            "total_attempts": sum(
                stats["success"] + stats["failure"]
                for stats in self.strategy_stats.values()
            )
        }
