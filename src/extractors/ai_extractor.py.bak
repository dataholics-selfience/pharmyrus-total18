"""
🧠 AI-Powered Patent Data Extractor
Uses LLM to extract patent data from HTML for maximum resilience
Falls back to CSS selectors if LLM fails
"""
import json
import re
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup
import anthropic


class AIPatentExtractor:
    """Extract patent data using AI with CSS fallback"""
    
    def __init__(self, anthropic_api_key: Optional[str] = None):
        self.client = None
        if anthropic_api_key:
            try:
                self.client = anthropic.Anthropic(api_key=anthropic_api_key)
            except Exception as e:
                print(f"⚠️  AI extractor disabled: {e}")
    
    def extract(self, html_content: str, patent_id: str) -> Dict[str, Any]:
        """
        Extract patent data using AI-first approach with CSS fallback
        
        Args:
            html_content: Raw HTML from Google Patents
            patent_id: Patent number (e.g., BR112012008823B8)
            
        Returns:
            Structured patent data
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
                ai_data = self._extract_with_ai(html_content, patent_id)
                if ai_data and ai_data.get('title'):
                    result.update(ai_data)
                    result['extraction_method'] = 'ai'
                    print(f"✅ AI extraction successful for {patent_id}")
                    return result
            except Exception as e:
                print(f"⚠️  AI extraction failed: {e}, falling back to CSS")
        
        # Fallback to CSS selectors
        try:
            css_data = self._extract_with_css(html_content, patent_id)
            result.update(css_data)
            result['extraction_method'] = 'css_fallback'
            print(f"✅ CSS extraction successful for {patent_id}")
        except Exception as e:
            print(f"❌ CSS extraction failed: {e}")
            result['extraction_method'] = 'failed'
        
        return result
    
    def _extract_with_ai(self, html_content: str, patent_id: str) -> Dict[str, Any]:
        """Extract data using Claude API"""
        
        # Truncate HTML to fit in context (keep important sections)
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extract key sections
        meta_tags = str(soup.find('head')) if soup.find('head') else ''
        abstract_section = str(soup.find('section', id='abstract')) if soup.find('section', id='abstract') else ''
        similar_docs = str(soup.find('h3', id='similarDocuments')) if soup.find('h3', id='similarDocuments') else ''
        
        # Get inventors section
        inventors_section = ''
        dt_tags = soup.find_all('dt', class_='style-scope patent-result')
        for dt in dt_tags:
            if 'Inventor' in dt.get_text():
                next_dd = dt.find_next('dd')
                if next_dd:
                    inventors_section = str(dt) + str(next_dd)
                    break
        
        # Combine relevant sections
        relevant_html = f"{meta_tags}\n{abstract_section}\n{inventors_section}\n{similar_docs[:5000]}"
        
        prompt = f"""Extract patent information from this Google Patents HTML fragment.

Patent ID: {patent_id}

HTML:
{relevant_html[:15000]}

Extract and return ONLY a JSON object with this exact structure (no markdown, no explanations):

{{
  "title": "patent title",
  "abstract": "patent abstract text (in English if available)",
  "inventors": ["inventor1", "inventor2"],
  "assignee": "company name",
  "filing_date": "YYYY-MM-DD",
  "publication_date": "YYYY-MM-DD",
  "family_members": [
    {{"publication_number": "BR...", "title": "...", "publication_date": "..."}}
  ]
}}

Rules:
1. Extract ALL inventors you find
2. For family_members, extract patents from "Similar Documents" section, prioritizing BR patents
3. Use English text when available
4. Return empty strings/arrays if data not found
5. Dates in ISO format (YYYY-MM-DD)
"""
        
        message = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        response_text = message.content[0].text.strip()
        
        # Remove markdown code blocks if present
        response_text = re.sub(r'```json\s*|\s*```', '', response_text)
        
        # Parse JSON
        data = json.loads(response_text)
        
        return data
    
    def _extract_with_css(self, html_content: str, patent_id: str) -> Dict[str, Any]:
        """Fallback extraction using CSS selectors"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        data = {
            'title': '',
            'abstract': '',
            'inventors': [],
            'assignee': '',
            'filing_date': '',
            'publication_date': '',
            'family_members': []
        }
        
        # Extract title
        title_tag = soup.find('title')
        if title_tag:
            title_text = title_tag.get_text()
            # Remove patent number prefix
            data['title'] = re.sub(r'^[A-Z]{2}\d+[A-Z]\d+\s*-\s*', '', title_text).strip()
        
        # Extract abstract
        abstract_tag = soup.find('abstract')
        if abstract_tag:
            # Get English text (after Portuguese)
            text = abstract_tag.get_text()
            # Try to get just English part after Portuguese
            parts = text.split('compounds which modulate', 1)
            if len(parts) > 1:
                data['abstract'] = ('compounds which modulate' + parts[1]).strip()[:500]
            else:
                data['abstract'] = text.strip()[:500]
        
        # Extract inventors from meta tags
        inventor_metas = soup.find_all('meta', {'name': 'DC.contributor', 'scheme': 'inventor'})
        data['inventors'] = [tag.get('content', '') for tag in inventor_metas if tag.get('content')]
        
        # Extract assignee from meta tag
        assignee_meta = soup.find('meta', {'name': 'DC.contributor', 'scheme': 'assignee'})
        if assignee_meta:
            data['assignee'] = assignee_meta.get('content', '')
        
        # Extract dates from timeline
        date_divs = soup.find_all('div', {'date': ''})
        for div in date_divs:
            date_text = div.get_text().strip()
            if date_text and re.match(r'\d{4}-\d{2}-\d{2}', date_text):
                # First date is usually filing date
                if not data['filing_date']:
                    data['filing_date'] = date_text
                # Last date could be publication date
                data['publication_date'] = date_text
        
        # Extract family members (BR patents from Similar Documents)
        similar_section = soup.find('h3', id='similarDocuments')
        if similar_section:
            table = similar_section.find_next('div', class_='tbody')
            if table:
                rows = table.find_all('div', class_='tr')
                for row in rows[:20]:  # Limit to 20 patents
                    pub_num_span = row.find('span', class_='td')
                    if pub_num_span:
                        pub_num = pub_num_span.get_text().strip()
                        # Only BR patents
                        if pub_num.startswith('BR'):
                            title_span = row.find_all('span', class_='td')
                            date_span = None
                            title_text = ''
                            
                            if len(title_span) >= 3:
                                date_span = title_span[1]
                                title_text = title_span[2].get_text().strip()
                            
                            data['family_members'].append({
                                'publication_number': pub_num,
                                'title': title_text[:200],
                                'publication_date': date_span.get_text().strip() if date_span else ''
                            })
        
        return data


# Singleton instance
_extractor = None


def get_extractor(api_key: Optional[str] = None) -> AIPatentExtractor:
    """Get or create singleton extractor instance"""
    global _extractor
    if _extractor is None:
        _extractor = AIPatentExtractor(anthropic_api_key=api_key)
    return _extractor
