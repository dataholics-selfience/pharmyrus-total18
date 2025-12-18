#!/usr/bin/env python3
"""
Ninja Crawler Base - Multi-Strategy Web Scraping
Alterna automaticamente entre: HTTPX → Playwright → Selenium
Headers rotativos, User-Agents fake, Stealth mode
"""
import httpx
import asyncio
from typing import Optional, Dict, List, Callable
from dataclasses import dataclass
from enum import Enum
import logging
import random
from fake_useragent import UserAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CrawlStrategy(Enum):
    """Estratégias de crawling disponíveis"""
    HTTPX_SIMPLE = "httpx_simple"
    HTTPX_ROTATING = "httpx_rotating"
    PLAYWRIGHT_HEADLESS = "playwright_headless"
    PLAYWRIGHT_STEALTH = "playwright_stealth"
    SELENIUM_HEADLESS = "selenium_headless"

@dataclass
class CrawlResult:
    """Resultado de uma tentativa de crawl"""
    success: bool
    data: Optional[Dict]
    strategy_used: CrawlStrategy
    attempts: int
    error: Optional[str] = None

class NinjaCrawler:
    """Base class para crawling ninja com múltiplas estratégias"""
    
    def __init__(self):
        self.ua = UserAgent()
        self.strategies = [
            CrawlStrategy.HTTPX_ROTATING,
            CrawlStrategy.PLAYWRIGHT_HEADLESS,
            CrawlStrategy.PLAYWRIGHT_STEALTH,
            CrawlStrategy.SELENIUM_HEADLESS
        ]
        
    def get_random_headers(self, device: str = "random") -> Dict[str, str]:
        """Gera headers aleatórios para diferentes dispositivos"""
        
        devices = {
            "mac": {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Upgrade-Insecure-Requests": "1"
            },
            "windows": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1"
            },
            "iphone": {
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br"
            },
            "android": {
                "User-Agent": "Mozilla/5.0 (Linux; Android 13; SM-S901B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate"
            }
        }
        
        if device == "random":
            device = random.choice(list(devices.keys()))
        
        return devices.get(device, devices["mac"])
    
    async def fetch_with_httpx(self, url: str, rotating: bool = True) -> Optional[Dict]:
        """Fetch com HTTPX e headers rotativos"""
        headers = self.get_random_headers() if rotating else {"User-Agent": self.ua.random}
        
        try:
            async with httpx.AsyncClient(
                timeout=30.0,
                headers=headers,
                follow_redirects=True,
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
            ) as client:
                response = await client.get(url)
                
                if response.status_code == 200:
                    # Tenta JSON primeiro, depois text
                    try:
                        return response.json()
                    except:
                        return {"text": response.text, "status_code": 200}
                else:
                    logger.warning(f"  ⚠️  HTTPX status: {response.status_code}")
                    return None
        
        except Exception as e:
            logger.warning(f"  ⚠️  HTTPX error: {e}")
            return None
    
    async def fetch_with_playwright(self, url: str, stealth: bool = False) -> Optional[Dict]:
        """Fetch com Playwright (headless browser)"""
        try:
            from playwright.async_api import async_playwright
            if stealth:
                from playwright_stealth import stealth_async
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                
                # Cria contexto com headers customizados
                headers = self.get_random_headers()
                context = await browser.new_context(
                    user_agent=headers["User-Agent"],
                    viewport={"width": 1920, "height": 1080},
                    locale="en-US"
                )
                
                page = await context.new_page()
                
                # Aplica stealth se solicitado
                if stealth:
                    await stealth_async(page)
                
                await page.goto(url, wait_until="networkidle", timeout=30000)
                
                # Aguarda JavaScript carregar
                await asyncio.sleep(2)
                
                # Pega conteúdo
                content = await page.content()
                
                await browser.close()
                
                return {"text": content, "status_code": 200}
        
        except Exception as e:
            logger.warning(f"  ⚠️  Playwright error: {e}")
            return None
    
    async def fetch_with_selenium(self, url: str) -> Optional[Dict]:
        """Fetch com Selenium (fallback final)"""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            
            # Configura Chrome headless
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            
            # User-Agent aleatório
            headers = self.get_random_headers()
            chrome_options.add_argument(f"user-agent={headers['User-Agent']}")
            
            driver = webdriver.Chrome(options=chrome_options)
            driver.get(url)
            
            # Aguarda página carregar
            await asyncio.sleep(3)
            
            # Pega HTML
            html = driver.page_source
            
            driver.quit()
            
            return {"text": html, "status_code": 200}
        
        except Exception as e:
            logger.warning(f"  ⚠️  Selenium error: {e}")
            return None
    
    async def ninja_fetch(self, url: str, max_attempts: int = 3) -> CrawlResult:
        """Fetch ninja com fallback automático entre estratégias"""
        
        logger.info(f"🥷 Ninja fetch: {url[:60]}...")
        
        for attempt in range(max_attempts):
            for strategy in self.strategies:
                logger.info(f"  Tentativa {attempt + 1}/{max_attempts} - {strategy.value}")
                
                data = None
                
                if strategy == CrawlStrategy.HTTPX_SIMPLE:
                    data = await self.fetch_with_httpx(url, rotating=False)
                
                elif strategy == CrawlStrategy.HTTPX_ROTATING:
                    data = await self.fetch_with_httpx(url, rotating=True)
                
                elif strategy == CrawlStrategy.PLAYWRIGHT_HEADLESS:
                    data = await self.fetch_with_playwright(url, stealth=False)
                
                elif strategy == CrawlStrategy.PLAYWRIGHT_STEALTH:
                    data = await self.fetch_with_playwright(url, stealth=True)
                
                elif strategy == CrawlStrategy.SELENIUM_HEADLESS:
                    data = await self.fetch_with_selenium(url)
                
                if data:
                    logger.info(f"  ✅ Sucesso com {strategy.value}")
                    return CrawlResult(
                        success=True,
                        data=data,
                        strategy_used=strategy,
                        attempts=attempt + 1
                    )
                
                # Rate limiting entre tentativas
                await asyncio.sleep(1)
        
        logger.error(f"  ❌ Todas as estratégias falharam após {max_attempts} tentativas")
        return CrawlResult(
            success=False,
            data=None,
            strategy_used=CrawlStrategy.HTTPX_SIMPLE,
            attempts=max_attempts,
            error="All strategies failed"
        )

# Teste
async def test_ninja():
    """Testa ninja crawler com PubChem"""
    ninja = NinjaCrawler()
    
    # Teste 1: PubChem CID
    url = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/Darolutamide/cids/JSON"
    
    result = await ninja.ninja_fetch(url)
    
    print(f"\n{'='*60}")
    print(f"TESTE NINJA CRAWLER")
    print(f"{'='*60}")
    print(f"Sucesso: {result.success}")
    print(f"Estratégia: {result.strategy_used.value}")
    print(f"Tentativas: {result.attempts}")
    if result.success:
        print(f"Data keys: {list(result.data.keys())}")
        if "text" in result.data:
            print(f"HTML length: {len(result.data['text'])} chars")
    print(f"{'='*60}")

if __name__ == "__main__":
    asyncio.run(test_ninja())
