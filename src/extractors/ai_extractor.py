"""
🤖 AI-Powered Patent Data Extractor - GROK EDITION
Uses xAI Grok for intelligent extraction with CSS fallback
Enhanced resilience with Grok's superior reasoning capabilities
"""

import os
import json
import re
import logging
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Try to import xAI SDK
try:
    from xai_sdk import Client as GrokClient
    from xai_sdk.chat import user, system
    GROK_AVAILABLE = True
except ImportError:
    GROK_AVAILABLE = False
    logger.warning("⚠️  xAI SDK not available - will use CSS fallback only")


class AIPatentExtractor:
    """Extract patent data using Grok AI with CSS fallback"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize extractor with Grok API key
        
        Args:
            api_key: xAI API key (or set XAI_API_KEY env var)
        """
        self.client = None
        
        if GROK_AVAILABLE:
            # Get API key from parameter or environment
            key = api_key or os.getenv('XAI_API_KEY')
            
            if key:
                try:
                    self.client = GrokClient(api_key=key)
                    logger.info("✅ Grok AI extractor initialized")
                except Exception as e:
                    logger.warning(f"⚠️  Failed to initialize Grok: {e}")
            else:
                logger.warning("⚠️  No XAI_API_KEY found - using CSS fallback only")
        else:
            logger.warning("⚠️  xai-sdk not installed - using CSS fallback only")
    
    def extract(self, html_content: str, patent_id: str) -> Dict[str, Any]:
        """
        Extract patent data using AI-first approach with CSS fallback
        
        Args:
            html_content: Raw HTML from Google Patents
            patent_id: Patent number (e.g., BR112012008823B8)
            
        Returns:
            Structured patent data with extraction_method field
        """
        result = {
            'patent_id': patent_id,
            'title': '',
            'abstract': '',
            'inventors': [],
            'assignee': '',
            'filing_date': '',
            'publication_date': '',
            'family_members': [],
            'classifications': {'cpc': [], 'ipc': []},
            'extraction_method': 'unknown'
        }
        
        # Try AI extraction first
        if self.client:
            try:
                logger.info(f"🤖 Attempting Grok AI extraction for {patent_id}")
                ai_result = self._extract_with_grok(html_content, patent_id)
                
                if ai_result and ai_result.get('title'):
                    result.update(ai_result)
                    result['extraction_method'] = 'grok_ai'
                    logger.info(f"✅ Grok AI extraction successful for {patent_id}")
                    return result
                else:
                    logger.warning(f"⚠️  Grok returned empty data, trying CSS fallback")
            
            except Exception as e:
                logger.warning(f"⚠️  Grok extraction failed: {e}, trying CSS fallback")
        
        # Fallback to CSS extraction
        try:
            logger.info(f"🔧 Using CSS fallback extraction for {patent_id}")
            css_result = self._extract_with_css(html_content, patent_id)
            result.update(css_result)
            result['extraction_method'] = 'css_fallback'
            logger.info(f"✅ CSS extraction successful for {patent_id}")
        except Exception as e:
            logger.error(f"❌ CSS extraction also failed: {e}")
            result['extraction_method'] = 'failed'
        
        return result
    
    def _extract_with_grok(self, html_content: str, patent_id: str) -> Dict[str, Any]:
        """
        Use Grok AI to extract patent data from HTML
        
        Args:
            html_content: Full HTML content
            patent_id: Patent ID for logging
            
        Returns:
            Extracted patent data
        """
        # Truncate HTML to fit in context (~15KB for Grok)
        truncated_html = self._truncate_html_for_ai(html_content)
        
        # Build prompt for Grok
        prompt = f"""Extract patent data from the following Google Patents HTML and return ONLY a JSON object (no markdown, no backticks, no explanation).

Patent ID: {patent_id}

Required fields:
- title: Patent title in English (string)
- abstract: Full abstract in English only, not Portuguese (string)
- inventors: ALL inventor names as array of strings (e.g., ["Name1", "Name2", ...])
- assignee: Company or organization name (string)
- filing_date: Filing date in YYYY-MM-DD format (string)
- publication_date: Publication date in YYYY-MM-DD format (string)
- family_members: Array of related BR patents with patent_number, title, country (array of objects)

Important:
1. Extract ALL inventors, not just the first few
2. Abstract should be in English only (ignore Portuguese translations)
3. For family_members, prioritize BR patents and include up to 20
4. Return ONLY the JSON, no markdown formatting

HTML excerpt:
{truncated_html}

Return ONLY raw JSON:"""

        # Create chat and get response from Grok
        chat = self.client.chat.create(model="grok-3")
        chat.append(system("You are a patent data extraction specialist. Extract structured data from HTML and return ONLY valid JSON, no markdown."))
        chat.append(user(prompt))
        
        # Sample response
        response = chat.sample()
        
        # Parse JSON from response
        return self._parse_grok_response(response.content)
    
    def _parse_grok_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse Grok's response into structured data
        
        Args:
            response_text: Raw response from Grok
            
        Returns:
            Parsed JSON data
        """
        # Remove markdown code blocks if present
        cleaned = response_text.strip()
        
        # Remove ```json and ``` if present
        if cleaned.startswith('```'):
            lines = cleaned.split('\n')
            if lines[0].startswith('```'):
                lines = lines[1:]
            if lines[-1].strip() == '```':
                lines = lines[:-1]
            cleaned = '\n'.join(lines)
        
        # Parse JSON
        try:
            data = json.loads(cleaned)
            
            # Ensure all required fields exist
            result = {
                'title': data.get('title', ''),
                'abstract': data.get('abstract', ''),
                'inventors': data.get('inventors', []),
                'assignee': data.get('assignee', ''),
                'filing_date': data.get('filing_date', ''),
                'publication_date': data.get('publication_date', ''),
                'family_members': data.get('family_members', []),
                'classifications': data.get('classifications', {'cpc': [], 'ipc': []})
            }
            
            return result
        
        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse Grok JSON response: {e}")
            logger.debug(f"Response was: {response_text[:500]}")
            return {}
    
    def _truncate_html_for_ai(self, html_content: str, max_size: int = 15000) -> str:
        """
        Truncate HTML to fit in AI context window
        
        Keeps most important sections:
        - <head> (meta tags with inventor, assignee info)
        - <section id="abstract">
        - <h3 id="similarDocuments"> (family members)
        
        Args:
            html_content: Full HTML
            max_size: Maximum characters to keep
            
        Returns:
            Truncated HTML with key sections
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        
        parts = []
        
        # 1. Meta tags (inventors, assignee, etc.)
        head = soup.find('head')
        if head:
            meta_tags = head.find_all('meta', attrs={'name': True})
            meta_html = ''.join(str(tag) for tag in meta_tags[:50])
            parts.append(f"<head>{meta_html}</head>")
        
        # 2. Title
        title = soup.find('title')
        if title:
            parts.append(str(title))
        
        # 3. Abstract section
        abstract_section = soup.find('section', id='abstract')
        if abstract_section:
            parts.append(str(abstract_section)[:3000])
        
        # 4. Similar documents (family members)
        similar_section = soup.find('h3', id='similarDocuments')
        if similar_section:
            # Get the table after the h3
            table = similar_section.find_next('table')
            if table:
                parts.append(f"<h3 id='similarDocuments'>Similar Documents</h3>{str(table)[:5000]}")
        
        # 5. Timeline (for dates)
        timeline = soup.find('div', class_='timeline')
        if timeline:
            parts.append(str(timeline)[:1000])
        
        # Join and truncate
        combined = '\n'.join(parts)
        
        if len(combined) > max_size:
            combined = combined[:max_size] + "...[truncated]"
        
        return combined
    
    def _extract_with_css(self, html_content: str, patent_id: str) -> Dict[str, Any]:
        """
        Fallback extraction using CSS selectors and BeautifulSoup
        
        Args:
            html_content: Full HTML content
            patent_id: Patent ID
            
        Returns:
            Extracted patent data
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        
        result = {}
        
        # Title (from <title> tag, remove patent number prefix)
        title_tag = soup.find('title')
        if title_tag:
            title_text = title_tag.get_text(strip=True)
            # Remove "BR... - " prefix
            title_text = re.sub(r'^[A-Z]{2}\d+[A-Z]?\d*\s*-\s*', '', title_text)
            result['title'] = title_text
        
        # Abstract (from <abstract> tag, English portion)
        abstract_tag = soup.find('abstract')
        if abstract_tag:
            # Try to get English text (usually comes first)
            text = abstract_tag.get_text(separator=' ', strip=True)
            # Take first 500 chars as abstract (usually English)
            result['abstract'] = text[:500]
        
        # Inventors (from meta tags)
        inventors = []
        inventor_metas = soup.find_all('meta', attrs={'name': 'DC.contributor', 'scheme': 'inventor'})
        for meta in inventor_metas:
            name = meta.get('content', '').strip()
            if name:
                inventors.append(name)
        result['inventors'] = inventors
        
        # Assignee (from meta tag)
        assignee_meta = soup.find('meta', attrs={'name': 'DC.contributor', 'scheme': 'assignee'})
        if assignee_meta:
            result['assignee'] = assignee_meta.get('content', '').strip()
        
        # Dates (from timeline divs)
        dates = {}
        timeline_divs = soup.find_all('div', attrs={'date': True})
        for div in timeline_divs:
            date_val = div.get('date', '')
            label = div.get_text(strip=True).lower()
            
            if 'filing' in label or 'application' in label:
                dates['filing_date'] = date_val
            elif 'publication' in label or 'granted' in label:
                dates['publication_date'] = date_val
        
        result['filing_date'] = dates.get('filing_date', '')
        result['publication_date'] = dates.get('publication_date', '')
        
        # Family members (from similarDocuments table)
        family_members = []
        similar_h3 = soup.find('h3', id='similarDocuments')
        if similar_h3:
            table = similar_h3.find_next('table')
            if table:
                rows = table.find_all('tr')[1:]  # Skip header
                
                for row in rows[:20]:  # Limit to 20
                    cells = row.find_all('td')
                    if len(cells) >= 2:
                        pub_num = cells[0].get_text(strip=True)
                        title = cells[1].get_text(strip=True)
                        
                        # Only include BR patents
                        if pub_num.startswith('BR'):
                            family_members.append({
                                'patent_number': pub_num,
                                'title': title,
                                'country': 'BR'
                            })
        
        result['family_members'] = family_members
        result['classifications'] = {'cpc': [], 'ipc': []}
        
        return result


# Singleton instance
_extractor_instance = None

def get_extractor(api_key: Optional[str] = None) -> AIPatentExtractor:
    """
    Get singleton AI extractor instance
    
    Args:
        api_key: Optional xAI API key
        
    Returns:
        AIPatentExtractor instance
    """
    global _extractor_instance
    
    if _extractor_instance is None:
        _extractor_instance = AIPatentExtractor(api_key=api_key)
    
    return _extractor_instance
