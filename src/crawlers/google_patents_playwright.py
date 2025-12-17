"""
Google Patents Playwright Crawler
Version: v4.0.3 AI-POWERED
🧠 Enhanced with AI-powered extraction for maximum resilience!
"""

import logging
import asyncio
import os
from typing import Dict, Any, List, Optional
from playwright.async_api import Page, async_playwright, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)


class GooglePatentsPlaywrightCrawler:
    """Playwright-based crawler for Google Patents with stealth capabilities"""
    
    def __init__(self, headless: bool = True, timeout: int = 60000, max_retries: int = 3):
        self.headless = headless
        self.timeout = timeout
        self.max_retries = max_retries  # For compatibility with pool initialization
        self.playwright = None
        self.browser = None
        self.context = None
        
    async def __aenter__(self):
        """Async context manager entry"""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
    
    async def start(self):
        """Initialize Playwright and browser"""
        try:
            logger.info("🚀 Starting Playwright browser...")
            self.playwright = await async_playwright().start()
            
            # Launch browser with stealth options
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-setuid-sandbox'
                ]
            )
            
            # Create context with realistic user agent
            self.context = await self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            
            # Add stealth script to hide automation
            await self.context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)
            
            logger.info("✅ Browser started successfully")
        except Exception as e:
            logger.error(f"❌ Failed to start browser: {e}")
            raise
    
    async def close(self):
        """Close browser and Playwright"""
        try:
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            logger.info("✅ Browser closed")
        except Exception as e:
            logger.error(f"⚠️  Error closing browser: {e}")
    
    # ========================================
    # POOL COMPATIBILITY METHODS
    # ========================================
    
    async def initialize(self, playwright_instance=None):
        """
        Initialize crawler (pool compatibility method)
        
        Args:
            playwright_instance: Optional Playwright instance from pool
                                If provided, use it instead of creating new one
        """
        if playwright_instance:
            # Use shared Playwright instance from pool
            self.playwright = playwright_instance
            
            # Launch browser with stealth options
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-setuid-sandbox'
                ]
            )
            
            # Create context
            self.context = await self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            
            # Add stealth script
            await self.context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)
            
            logger.info("✅ Browser initialized (pool mode)")
        else:
            # Standalone mode - use start()
            await self.start()
    
    async def fetch_patent_details(self, patent_id: str) -> dict:
        """
        Fetch patent details (pool compatibility method)
        
        Args:
            patent_id: Patent publication number
        
        Returns:
            Dictionary with patent data (pool-compatible format)
        """
        result = await self.get_patent_details(patent_id)
        
        # Convert to pool-expected format
        return {
            'publication_number': patent_id,
            'success': result.get('success', False),
            'family_members': result.get('family_members', []),
            'data': result.get('data', {}),
            'error': result.get('error')
        }
    
    async def _extract_basic_info(self, page: Page) -> Dict[str, Any]:
        """Extract basic patent information"""
        data = {
            'title': '',
            'abstract': '',
            'inventors': [],
            'assignee': '',
            'filing_date': '',
            'publication_date': '',
            'classifications': {'cpc': [], 'ipc': []},
            'pdf_url': '',
            'legal_status': ''
        }
        
        # Title
        try:
            title_elem = await page.query_selector('h1, title, [itemprop="title"]')
            if title_elem:
                data['title'] = (await title_elem.inner_text()).strip()
        except Exception as e:
            logger.warning(f"    ⚠️  Could not extract title: {e}")
        
        # Abstract
        try:
            abstract_elem = await page.query_selector('[itemprop="abstract"], .abstract, #abstract')
            if abstract_elem:
                data['abstract'] = (await abstract_elem.inner_text()).strip()
        except Exception as e:
            logger.warning(f"    ⚠️  Could not extract abstract: {e}")
        
        # Inventors
        try:
            inventor_elems = await page.query_selector_all('[itemprop="inventor"]')
            for elem in inventor_elems:
                inventor = (await elem.inner_text()).strip()
                if inventor:
                    data['inventors'].append(inventor)
        except Exception as e:
            logger.warning(f"    ⚠️  Could not extract inventors: {e}")
        
        # Assignee
        try:
            assignee_elem = await page.query_selector('[itemprop="assignee"], .assignee')
            if assignee_elem:
                data['assignee'] = (await assignee_elem.inner_text()).strip()
        except Exception as e:
            logger.warning(f"    ⚠️  Could not extract assignee: {e}")
        
        # Dates
        try:
            date_elems = await page.query_selector_all('time[itemprop]')
            for elem in date_elems:
                itemprop = await elem.get_attribute('itemprop')
                date_text = await elem.get_attribute('datetime')
                if not date_text:
                    date_text = (await elem.inner_text()).strip()
                
                if 'filing' in itemprop.lower():
                    data['filing_date'] = date_text
                elif 'publication' in itemprop.lower():
                    data['publication_date'] = date_text
        except Exception as e:
            logger.warning(f"    ⚠️  Could not extract dates: {e}")
        
        # Classifications
        try:
            # CPC
            cpc_elems = await page.query_selector_all('span.cpc, [itemprop="cpc"]')
            for elem in cpc_elems[:10]:
                cpc = (await elem.inner_text()).strip()
                if cpc:
                    data['classifications']['cpc'].append(cpc)
            
            # IPC
            ipc_elems = await page.query_selector_all('span.ipc, [itemprop="ipc"]')
            for elem in ipc_elems[:10]:
                ipc = (await elem.inner_text()).strip()
                if cpc:
                    data['classifications']['ipc'].append(ipc)
        except Exception as e:
            logger.warning(f"    ⚠️  Could not extract classifications: {e}")
        
        # PDF URL
        try:
            pdf_elem = await page.query_selector('a[href*=".pdf"]')
            if pdf_elem:
                data['pdf_url'] = await pdf_elem.get_attribute('href')
                if data['pdf_url'] and not data['pdf_url'].startswith('http'):
                    data['pdf_url'] = 'https://patents.google.com' + data['pdf_url']
        except Exception as e:
            logger.warning(f"    ⚠️  Could not extract PDF URL: {e}")
        
        # Legal Status
        try:
            status_elem = await page.query_selector('[itemprop="status"], .legal-status')
            if status_elem:
                data['legal_status'] = (await status_elem.inner_text()).strip()
        except Exception as e:
            logger.warning(f"    ⚠️  Could not extract legal status: {e}")
        
        return data
    
    async def _extract_patent_family(self, page: Page) -> List[Dict[str, Any]]:
        """
        Extract patent family members using CORRECT selectors from actual HTML
        
        HOTFIX3.2: Based on real Google Patents HTML structure:
        - NO tab clicking needed (data is already in page)
        - Use tr[itemprop="docdbFamily"] selector
        - Extract span[itemprop="publicationNumber"] and td[itemprop="publicationDate"]
        """
        family_members = []
        
        try:
            logger.info("    🔍 Extracting patent family using CORRECT selectors...")
            
            # CORRECT SELECTOR: tr[itemprop="docdbFamily"]
            family_rows = await page.query_selector_all('tr[itemprop="docdbFamily"]')
            
            logger.info(f"    📊 Found {len(family_rows)} family members using tr[itemprop='docdbFamily']")
            
            if not family_rows:
                logger.warning("    ⚠️  No family members found with correct selector")
                
                # 🐛 DEBUG: Save HTML and screenshot for analysis
                try:
                    import os
                    import datetime
                    
                    # Create debug directory
                    debug_dir = "/tmp/playwright_debug"
                    os.makedirs(debug_dir, exist_ok=True)
                    
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    patent_id_clean = page.url.split('/')[-2] if '/' in page.url else 'unknown'
                    
                    # Save HTML
                    html_path = f"{debug_dir}/{patent_id_clean}_{timestamp}.html"
                    html_content = await page.content()
                    with open(html_path, 'w', encoding='utf-8') as f:
                        f.write(html_content)
                    logger.warning(f"    🐛 DEBUG: Saved HTML to {html_path}")
                    
                    # Save screenshot
                    screenshot_path = f"{debug_dir}/{patent_id_clean}_{timestamp}.png"
                    await page.screenshot(path=screenshot_path, full_page=True)
                    logger.warning(f"    🐛 DEBUG: Saved screenshot to {screenshot_path}")
                    
                    # Log some HTML stats
                    logger.warning(f"    🐛 DEBUG: HTML size: {len(html_content)} bytes")
                    logger.warning(f"    🐛 DEBUG: Contains 'docdbFamily': {('docdbFamily' in html_content)}")
                    logger.warning(f"    🐛 DEBUG: Contains 'itemprop': {('itemprop' in html_content)}")
                    
                    # SAVE LAST HTML PATH for debug endpoint
                    self._last_debug_html_path = html_path
                    self._last_debug_screenshot_path = screenshot_path
                    
                except Exception as debug_err:
                    logger.error(f"    ❌ Debug save failed: {debug_err}")
                
                return []
            
            for idx, row in enumerate(family_rows):
                try:
                    # Extract publication number from span[itemprop="publicationNumber"]
                    pub_num_elem = await row.query_selector('span[itemprop="publicationNumber"]')
                    if not pub_num_elem:
                        logger.debug(f"    ⏭️  Row {idx}: No publicationNumber span found")
                        continue
                    
                    publication_number = (await pub_num_elem.inner_text()).strip()
                    
                    if not publication_number or len(publication_number) < 3:
                        logger.debug(f"    ⏭️  Row {idx}: Invalid publication number: '{publication_number}'")
                        continue
                    
                    # Extract country code (first 2 characters)
                    country_code = publication_number[:2].upper()
                    
                    # Validate country code
                    if not country_code.isalpha() or len(country_code) != 2:
                        logger.debug(f"    ⚠️  Row {idx}: Invalid country code: '{country_code}' from '{publication_number}'")
                        country_code = 'XX'
                    
                    # Extract publication date from td[itemprop="publicationDate"]
                    pub_date_elem = await row.query_selector('td[itemprop="publicationDate"]')
                    publication_date = ''
                    if pub_date_elem:
                        publication_date = (await pub_date_elem.inner_text()).strip()
                    
                    # Extract link
                    link_elem = await row.query_selector('a[href*="/patent/"]')
                    link = ''
                    if link_elem:
                        href = await link_elem.get_attribute('href')
                        if href:
                            link = f"https://patents.google.com{href}" if not href.startswith('http') else href
                    
                    # Extract primary language (optional)
                    lang_elem = await row.query_selector('span[itemprop="primaryLanguage"]')
                    primary_language = ''
                    if lang_elem:
                        primary_language = (await lang_elem.inner_text()).strip()
                    
                    member = {
                        'publication_number': publication_number,
                        'country_code': country_code,
                        'publication_date': publication_date,
                        'primary_language': primary_language,
                        'link': link,
                        'title': ''  # Not typically in family table
                    }
                    
                    family_members.append(member)
                    logger.debug(f"    ✅ Row {idx}: {publication_number} ({country_code}) - {publication_date}")
                
                except Exception as e:
                    logger.warning(f"    ⚠️  Error parsing family row {idx}: {e}")
                    continue
            
            logger.info(f"    ✅ Successfully extracted {len(family_members)} family members")
            
            # Log country distribution
            if family_members:
                countries = {}
                for member in family_members:
                    cc = member['country_code']
                    countries[cc] = countries.get(cc, 0) + 1
                
                logger.info(f"    📍 Country distribution: {dict(sorted(countries.items()))}")
            
        except Exception as e:
            logger.error(f"    ❌ Fatal error in _extract_patent_family: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        return family_members
    
    def get_last_debug_html(self) -> dict:
        """
        Get last saved debug HTML and screenshot paths
        
        Returns:
            Dictionary with paths to debug files
        """
        return {
            'html_path': getattr(self, '_last_debug_html_path', None),
            'screenshot_path': getattr(self, '_last_debug_screenshot_path', None)
        }
    
    async def get_patent_details(self, patent_id: str) -> Dict[str, Any]:
        """
        Get complete patent details including family members
        🧠 NOW WITH AI-POWERED EXTRACTION!
        
        Args:
            patent_id: Patent publication number (e.g., 'BR112012008823B8')
        
        Returns:
            Dictionary with patent data and family members
        """
        result = {
            'patent_id': patent_id,
            'success': False,
            'data': {},
            'family_members': [],
            'error': None,
            'extraction_method': 'unknown'
        }
        
        try:
            logger.info(f"🔍 Fetching patent: {patent_id}")
            
            # Construct URL
            url = f"https://patents.google.com/patent/{patent_id}/en"
            logger.info(f"    📍 URL: {url}")
            
            # Create new page
            page = await self.context.new_page()
            
            try:
                # Navigate to patent page
                logger.info(f"    🌐 Navigating to patent page...")
                await page.goto(url, wait_until='domcontentloaded', timeout=self.timeout)
                
                # Wait for content to load
                logger.info(f"    ⏳ Waiting for page content...")
                await page.wait_for_timeout(3000)  # Initial 3 seconds
                
                # Try to wait for patent family section (may not exist on all pages)
                try:
                    await page.wait_for_selector('tr[itemprop="docdbFamily"], section#family', timeout=10000)
                    logger.info("    ✅ Patent family section detected")
                except:
                    logger.warning("    ⚠️  Patent family section not found after 10s wait")
                
                # Additional wait for JavaScript to complete
                await page.wait_for_timeout(2000)
                
                # Try clicking "Family" tab if it exists (some pages have tabs)
                try:
                    family_tab = await page.query_selector('a:has-text("Family"), button:has-text("Family")')
                    if family_tab:
                        logger.info("    🖱️  Clicking Family tab...")
                        await family_tab.click()
                        await page.wait_for_timeout(2000)
                        logger.info("    ✅ Family tab clicked")
                except Exception as tab_err:
                    logger.debug(f"    ℹ️  No Family tab to click (expected): {tab_err}")
                
                # Check if page loaded successfully
                title = await page.title()
                if 'error' in title.lower() or '404' in title:
                    raise Exception(f"Patent page not found: {title}")
                
                logger.info(f"    ✅ Page loaded: {title}")
                
                # 🧠 NEW: Try AI extraction first!
                ai_success = False
                try:
                    from src.extractors.ai_extractor import get_extractor
                    
                    # Get full HTML
                    html_content = await page.content()
                    logger.info(f"    🧠 Attempting AI extraction...")
                    
                    # Get AI extractor
                    api_key = os.environ.get('ANTHROPIC_API_KEY')
                    extractor = get_extractor(api_key)
                    
                    # Extract with AI
                    ai_data = extractor.extract(html_content, patent_id)
                    
                    if ai_data and ai_data.get('extraction_method') == 'ai':
                        logger.info(f"    ✅ AI extraction SUCCESS!")
                        
                        # Use AI-extracted data
                        result['data'] = {
                            'title': ai_data.get('title', ''),
                            'abstract': ai_data.get('abstract', ''),
                            'inventors': ai_data.get('inventors', []),
                            'assignee': ai_data.get('assignee', ''),
                            'filing_date': ai_data.get('filing_date', ''),
                            'publication_date': ai_data.get('publication_date', ''),
                            'classifications': ai_data.get('classifications', {'cpc': [], 'ipc': []}),
                            'pdf_url': '',
                            'legal_status': ''
                        }
                        
                        # Convert AI family members to expected format
                        family_members = []
                        for member in ai_data.get('family_members', []):
                            family_members.append({
                                'publication_number': member.get('publication_number', ''),
                                'title': member.get('title', ''),
                                'country': member.get('publication_number', '')[:2] if member.get('publication_number') else '',
                                'kind_code': '',
                                'publication_date': member.get('publication_date', ''),
                                'link': f"https://patents.google.com/patent/{member.get('publication_number', '')}/en"
                            })
                        
                        result['family_members'] = family_members
                        result['extraction_method'] = 'ai'
                        ai_success = True
                        
                        logger.info(f"    📊 AI found {len(family_members)} family members")
                    
                except ImportError:
                    logger.warning("    ⚠️  AI extractor not available (import failed)")
                except Exception as ai_err:
                    logger.warning(f"    ⚠️  AI extraction failed: {ai_err}")
                
                # Fallback to CSS extraction if AI failed
                if not ai_success:
                    logger.info(f"    📄 Using CSS fallback extraction...")
                    
                    # Extract basic info (old method)
                    basic_info = await self._extract_basic_info(page)
                    
                    # Extract patent family (old method)
                    logger.info(f"    👨‍👩‍👧‍👦 Extracting patent family...")
                    family_members = await self._extract_patent_family(page)
                    
                    result['data'] = basic_info
                    result['family_members'] = family_members
                    result['extraction_method'] = 'css_fallback'
                    
                    logger.info(f"    ✅ CSS extracted {len(family_members)} family members")
                
                result['success'] = True
                logger.info(f"    ✅ SUCCESS using {result['extraction_method']}")
                
            finally:
                await page.close()
        
        except Exception as e:
            logger.error(f"    ❌ Error fetching patent {patent_id}: {e}")
            result['error'] = str(e)
            import traceback
            logger.error(traceback.format_exc())
        
        return result
    
    async def get_worldwide_applications(self, wo_number: str) -> Dict[str, Any]:
        """
        Get worldwide applications (family members) for a WO patent
        
        Args:
            wo_number: WO patent number (e.g., 'WO2011051311A1')
        
        Returns:
            Dictionary with family members
        """
        logger.info(f"🌍 Getting worldwide applications for: {wo_number}")
        
        # Reuse get_patent_details
        result = await self.get_patent_details(wo_number)
        
        return {
            'wo_number': wo_number,
            'success': result['success'],
            'family_members': result['family_members'],
            'error': result.get('error')
        }


# ========================================
# HELPER FUNCTIONS
# ========================================

async def test_patent_family_extraction(patent_id: str = 'BR112012008823B8'):
    """Test patent family extraction with a known patent"""
    
    print(f"\n{'='*80}")
    print(f"🧪 TESTING PATENT FAMILY EXTRACTION - HOTFIX3.2")
    print(f"{'='*80}\n")
    
    async with GooglePatentsPlaywrightCrawler(headless=True) as crawler:
        result = await crawler.get_patent_details(patent_id)
        
        print(f"\n📊 RESULTS:")
        print(f"   Patent ID: {result['patent_id']}")
        print(f"   Success: {result['success']}")
        print(f"   Family Members: {len(result['family_members'])}")
        
        if result['family_members']:
            print(f"\n👨‍👩‍👧‍👦 FAMILY MEMBERS:")
            
            # Group by country
            by_country = {}
            for member in result['family_members']:
                cc = member['country_code']
                if cc not in by_country:
                    by_country[cc] = []
                by_country[cc].append(member['publication_number'])
            
            for country, patents in sorted(by_country.items()):
                print(f"\n   {country} ({len(patents)}):")
                for patent in patents[:5]:  # Show first 5
                    print(f"      • {patent}")
                if len(patents) > 5:
                    print(f"      ... and {len(patents) - 5} more")
        
        if result['error']:
            print(f"\n❌ ERROR: {result['error']}")
    
    print(f"\n{'='*80}\n")


# ========================================
# BACKWARD COMPATIBILITY ALIAS
# ========================================
# The pool system expects 'GooglePatentsCrawler' but we renamed to 'GooglePatentsPlaywrightCrawler'
GooglePatentsCrawler = GooglePatentsPlaywrightCrawler


if __name__ == "__main__":
    # Run test
    asyncio.run(test_patent_family_extraction())
