"""
AI Fallback System
Usa IA (Grok, Claude, etc) para processar HTML quando crawlers falham
Sistema econômico com verificação de custos
"""
import asyncio
import logging
import os
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum
import json

import httpx

logger = logging.getLogger(__name__)


class AIProvider(Enum):
    """Provedores de IA disponíveis"""
    GROK_FREE = "grok_free"
    GROK_PAID = "grok_paid"
    CLAUDE = "claude"
    OPENAI = "openai"


@dataclass
class AIProcessingCost:
    """Custo estimado de processamento IA"""
    provider: AIProvider
    tokens_estimated: int
    cost_usd: float
    is_affordable: bool
    max_budget_usd: float = 0.10  # $0.10 por operação


@dataclass
class AIResult:
    """Resultado de processamento com IA"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    provider_used: Optional[AIProvider] = None
    cost: Optional[AIProcessingCost] = None
    error: Optional[str] = None


class AIFallbackProcessor:
    """
    Processa HTML/dados com IA quando crawlers falham
    
    Características:
    - Usa Grok Free preferncialmente (gratuito)
    - Fallback para outros providers
    - Verificação econômica antes de processar
    - Prompts otimizados para extração de dados
    - Cache de resultados
    """
    
    # API keys via env vars
    GROK_API_KEY = os.getenv("GROK_API_KEY", "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")
    CLAUDE_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    
    # Custos por 1M tokens (USD)
    COSTS = {
        AIProvider.GROK_FREE: 0.0,  # Grátis!
        AIProvider.GROK_PAID: 0.50,
        AIProvider.CLAUDE: 3.00,
        AIProvider.OPENAI: 2.50
    }
    
    def __init__(self, max_budget_usd: float = 0.10):
        self.max_budget_usd = max_budget_usd
    
    async def process_html_for_patents(
        self,
        html: str,
        url: str,
        extraction_goal: str = "patent_data"
    ) -> AIResult:
        """
        Processa HTML para extrair dados de patentes
        
        Args:
            html: HTML bruto
            url: URL de origem
            extraction_goal: Objetivo (patent_data, wo_numbers, trial_data)
        """
        logger.info(f"🤖 AI Fallback: processando HTML de {url}")
        
        # Verifica viabilidade econômica
        cost = self._estimate_cost(html, AIProvider.GROK_FREE)
        
        if not cost.is_affordable and extraction_goal != "critical":
            logger.warning(f"   ⚠️ Custo estimado ${cost.cost_usd:.4f} excede budget ${self.max_budget_usd}")
            return AIResult(
                success=False,
                error=f"Cost ${cost.cost_usd:.4f} exceeds budget ${self.max_budget_usd}"
            )
        
        # Tenta Grok Free primeiro
        if self.GROK_API_KEY:
            result = await self._process_with_grok(html, url, extraction_goal)
            if result.success:
                return result
        
        # Fallback para outros providers (se configurados e dentro do budget)
        if self.CLAUDE_API_KEY:
            result = await self._process_with_claude(html, url, extraction_goal)
            if result.success:
                return result
        
        if self.OPENAI_API_KEY:
            result = await self._process_with_openai(html, url, extraction_goal)
            if result.success:
                return result
        
        return AIResult(
            success=False,
            error="No AI provider available or all failed"
        )
    
    def _estimate_cost(
        self,
        html: str,
        provider: AIProvider
    ) -> AIProcessingCost:
        """Estima custo de processamento"""
        # Estima tokens (aproximado: 1 token ≈ 4 chars)
        tokens = len(html) // 4 + 500  # +500 para prompt/resposta
        
        # Custo por milhão de tokens
        cost_per_million = self.COSTS.get(provider, 0.0)
        cost_usd = (tokens / 1_000_000) * cost_per_million
        
        is_affordable = cost_usd <= self.max_budget_usd
        
        return AIProcessingCost(
            provider=provider,
            tokens_estimated=tokens,
            cost_usd=cost_usd,
            is_affordable=is_affordable,
            max_budget_usd=self.max_budget_usd
        )
    
    async def _process_with_grok(
        self,
        html: str,
        url: str,
        goal: str
    ) -> AIResult:
        """Processa com Grok (xAI)"""
        logger.info(f"   🤖 Tentando Grok...")
        
        try:
            # Trunca HTML se muito grande (max 100k chars)
            html_truncated = html[:100000] if len(html) > 100000 else html
            
            prompt = self._build_extraction_prompt(html_truncated, url, goal)
            
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    "https://api.x.ai/v1/chat/completions",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.GROK_API_KEY}"
                    },
                    json={
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are a data extraction expert. Extract structured data from HTML and return ONLY valid JSON."
                            },
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ],
                        "model": "grok-beta",
                        "temperature": 0.1
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    content = data["choices"][0]["message"]["content"]
                    
                    # Parse JSON da resposta
                    try:
                        # Remove markdown se presente
                        content_clean = content.strip()
                        if content_clean.startswith("```json"):
                            content_clean = content_clean[7:]
                        if content_clean.startswith("```"):
                            content_clean = content_clean[3:]
                        if content_clean.endswith("```"):
                            content_clean = content_clean[:-3]
                        
                        extracted = json.loads(content_clean.strip())
                        
                        logger.info(f"   ✅ Grok: dados extraídos com sucesso")
                        
                        return AIResult(
                            success=True,
                            data=extracted,
                            provider_used=AIProvider.GROK_FREE,
                            cost=self._estimate_cost(html_truncated, AIProvider.GROK_FREE)
                        )
                        
                    except json.JSONDecodeError as e:
                        logger.warning(f"   ⚠️ Grok: JSON inválido - {e}")
                        return AIResult(success=False, error=f"Invalid JSON: {e}")
                else:
                    logger.warning(f"   ⚠️ Grok: HTTP {response.status_code}")
                    return AIResult(success=False, error=f"HTTP {response.status_code}")
                    
        except Exception as e:
            logger.warning(f"   ❌ Grok falhou: {str(e)}")
            return AIResult(success=False, error=str(e))
    
    async def _process_with_claude(
        self,
        html: str,
        url: str,
        goal: str
    ) -> AIResult:
        """Processa com Claude (Anthropic)"""
        logger.info(f"   🤖 Tentando Claude...")
        
        try:
            html_truncated = html[:100000]
            prompt = self._build_extraction_prompt(html_truncated, url, goal)
            
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "Content-Type": "application/json",
                        "x-api-key": self.CLAUDE_API_KEY,
                        "anthropic-version": "2023-06-01"
                    },
                    json={
                        "model": "claude-3-haiku-20240307",
                        "max_tokens": 4096,
                        "messages": [
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ]
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    content = data["content"][0]["text"]
                    
                    # Parse JSON
                    extracted = json.loads(content.strip())
                    
                    logger.info(f"   ✅ Claude: dados extraídos")
                    
                    return AIResult(
                        success=True,
                        data=extracted,
                        provider_used=AIProvider.CLAUDE,
                        cost=self._estimate_cost(html_truncated, AIProvider.CLAUDE)
                    )
                else:
                    return AIResult(success=False, error=f"HTTP {response.status_code}")
                    
        except Exception as e:
            logger.warning(f"   ❌ Claude falhou: {str(e)}")
            return AIResult(success=False, error=str(e))
    
    async def _process_with_openai(
        self,
        html: str,
        url: str,
        goal: str
    ) -> AIResult:
        """Processa com OpenAI"""
        logger.info(f"   🤖 Tentando OpenAI...")
        
        try:
            html_truncated = html[:100000]
            prompt = self._build_extraction_prompt(html_truncated, url, goal)
            
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.OPENAI_API_KEY}"
                    },
                    json={
                        "model": "gpt-4o-mini",
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are a data extraction expert. Extract structured data and return ONLY valid JSON."
                            },
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ],
                        "temperature": 0.1
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    content = data["choices"][0]["message"]["content"]
                    
                    extracted = json.loads(content.strip())
                    
                    logger.info(f"   ✅ OpenAI: dados extraídos")
                    
                    return AIResult(
                        success=True,
                        data=extracted,
                        provider_used=AIProvider.OPENAI,
                        cost=self._estimate_cost(html_truncated, AIProvider.OPENAI)
                    )
                else:
                    return AIResult(success=False, error=f"HTTP {response.status_code}")
                    
        except Exception as e:
            logger.warning(f"   ❌ OpenAI falhou: {str(e)}")
            return AIResult(success=False, error=str(e))
    
    def _build_extraction_prompt(
        self,
        html: str,
        url: str,
        goal: str
    ) -> str:
        """Constrói prompt otimizado para extração"""
        
        if goal == "wo_numbers":
            return f"""Extract all WO patent numbers from this HTML.

URL: {url}

HTML:
{html}

Return ONLY a JSON object with this structure:
{{
  "wo_numbers": ["WO2011156378", "WO2016123456", ...],
  "total_found": 2
}}

WO numbers follow pattern: WO + 4 digits (year) + 6-7 digits (number).
Examples: WO2011156378, WO2016001234, WO2023000001
"""
        
        elif goal == "patent_data":
            return f"""Extract patent information from this HTML.

URL: {url}

HTML:
{html}

Return ONLY a JSON object with this structure:
{{
  "patents": [
    {{
      "publication_number": "BR112013011458",
      "title": "Patent title",
      "abstract": "Abstract text...",
      "applicant": "Company name",
      "inventors": ["Name 1", "Name 2"],
      "filing_date": "2011-11-17",
      "publication_date": "2013-11-05",
      "status": "Active/Expired",
      "classifications": ["A61K", "C07D"]
    }}
  ],
  "total_found": 1
}}

Extract as much information as available. If a field is missing, use null.
"""
        
        elif goal == "trial_data":
            return f"""Extract clinical trial information from this HTML.

URL: {url}

HTML:
{html}

Return ONLY a JSON object with this structure:
{{
  "trials": [
    {{
      "nct_id": "NCT01234567",
      "title": "Trial title",
      "status": "Recruiting/Completed/etc",
      "phase": "Phase 1/2/3/4",
      "conditions": ["Disease 1", "Disease 2"],
      "interventions": ["Drug name", "Placebo"],
      "sponsor": "Company/Institution",
      "start_date": "2020-01-01",
      "completion_date": "2023-12-31"
    }}
  ],
  "total_found": 1
}}

Extract all available information.
"""
        
        else:
            return f"""Extract relevant data from this HTML.

URL: {url}
Goal: {goal}

HTML:
{html}

Return a JSON object with extracted data.
"""
