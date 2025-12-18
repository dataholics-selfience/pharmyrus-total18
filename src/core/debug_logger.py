"""
Firestore Debug Logger
Armazena HTMLs, requests, responses para debug e auto-healing
Cloud-agnostic: funciona com Firestore ou JSON local
"""
import asyncio
import logging
import json
import os
from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path
import hashlib
import gzip

try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    FIRESTORE_AVAILABLE = True
except ImportError:
    FIRESTORE_AVAILABLE = False

logger = logging.getLogger(__name__)


class DebugLogger:
    """
    Sistema de debug resiliente
    
    Features:
    - Salva HTMLs brutos
    - Salva requests/responses
    - Salva erros com contexto
    - Firestore (produção) ou JSON local (dev)
    - Compressão automática
    - TTL automático
    """
    
    def __init__(
        self,
        use_firestore: bool = True,
        local_storage_path: str = "./debug_logs",
        project_id: Optional[str] = None
    ):
        self.use_firestore = use_firestore and FIRESTORE_AVAILABLE
        self.local_storage_path = Path(local_storage_path)
        self.db = None
        
        if self.use_firestore:
            try:
                if not firebase_admin._apps:
                    if project_id:
                        cred = credentials.ApplicationDefault()
                        firebase_admin.initialize_app(cred, {
                            'projectId': project_id
                        })
                    else:
                        # Tenta auto-detect
                        firebase_admin.initialize_app()
                
                self.db = firestore.client()
                logger.info("✅ Firestore conectado")
                
            except Exception as e:
                logger.warning(f"⚠️ Firestore falhou, usando local storage: {e}")
                self.use_firestore = False
        
        if not self.use_firestore:
            self.local_storage_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"✅ Local storage: {self.local_storage_path}")
    
    async def log_html(
        self,
        url: str,
        html: str,
        source: str,
        success: bool,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Salva HTML para debug
        
        Returns: ID do log
        """
        log_id = self._generate_log_id(url, source)
        
        # Comprime HTML
        html_compressed = gzip.compress(html.encode('utf-8'))
        html_size = len(html_compressed)
        
        doc = {
            "log_id": log_id,
            "url": url,
            "source": source,
            "success": success,
            "html_size_bytes": html_size,
            "html_compressed": html_compressed.hex(),  # Hex string para serialização
            "metadata": metadata or {},
            "timestamp": datetime.utcnow().isoformat(),
            "ttl_days": 30
        }
        
        if self.use_firestore:
            try:
                await asyncio.to_thread(
                    self.db.collection("debug_html_logs").document(log_id).set,
                    doc
                )
                logger.info(f"📝 Firestore: HTML salvo ({html_size} bytes) - {log_id}")
            except Exception as e:
                logger.warning(f"⚠️ Firestore write failed: {e}")
                await self._save_local(log_id, doc)
        else:
            await self._save_local(log_id, doc)
        
        return log_id
    
    async def log_error(
        self,
        url: str,
        error: str,
        source: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Salva erro com contexto"""
        log_id = self._generate_log_id(url, source)
        
        doc = {
            "log_id": log_id,
            "url": url,
            "source": source,
            "error": error,
            "context": context or {},
            "timestamp": datetime.utcnow().isoformat(),
            "ttl_days": 7
        }
        
        if self.use_firestore:
            try:
                await asyncio.to_thread(
                    self.db.collection("debug_error_logs").document(log_id).set,
                    doc
                )
                logger.info(f"📝 Firestore: Erro salvo - {log_id}")
            except Exception as e:
                logger.warning(f"⚠️ Firestore write failed: {e}")
                await self._save_local(log_id, doc, collection="errors")
        else:
            await self._save_local(log_id, doc, collection="errors")
        
        return log_id
    
    async def log_request_response(
        self,
        url: str,
        method: str,
        headers: Dict[str, str],
        status_code: int,
        response_time: float,
        source: str
    ) -> str:
        """Salva request/response para análise"""
        log_id = self._generate_log_id(url, source)
        
        doc = {
            "log_id": log_id,
            "url": url,
            "method": method,
            "headers": headers,
            "status_code": status_code,
            "response_time_seconds": response_time,
            "source": source,
            "timestamp": datetime.utcnow().isoformat(),
            "ttl_days": 7
        }
        
        if self.use_firestore:
            try:
                await asyncio.to_thread(
                    self.db.collection("debug_request_logs").document(log_id).set,
                    doc
                )
            except Exception as e:
                logger.warning(f"⚠️ Firestore write failed: {e}")
                await self._save_local(log_id, doc, collection="requests")
        else:
            await self._save_local(log_id, doc, collection="requests")
        
        return log_id
    
    async def get_html(self, log_id: str) -> Optional[str]:
        """Recupera HTML salvo"""
        if self.use_firestore:
            try:
                doc_ref = self.db.collection("debug_html_logs").document(log_id)
                doc = await asyncio.to_thread(doc_ref.get)
                
                if doc.exists:
                    data = doc.to_dict()
                    html_compressed_hex = data.get("html_compressed", "")
                    html_compressed = bytes.fromhex(html_compressed_hex)
                    html = gzip.decompress(html_compressed).decode('utf-8')
                    return html
            except Exception as e:
                logger.warning(f"⚠️ Firestore read failed: {e}")
        
        # Fallback local
        local_file = self.local_storage_path / "html" / f"{log_id}.json.gz"
        if local_file.exists():
            with gzip.open(local_file, 'rt') as f:
                data = json.load(f)
                html_compressed_hex = data.get("html_compressed", "")
                html_compressed = bytes.fromhex(html_compressed_hex)
                html = gzip.decompress(html_compressed).decode('utf-8')
                return html
        
        return None
    
    async def list_failed_urls(
        self,
        source: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Lista URLs que falharam para retry"""
        results = []
        
        if self.use_firestore:
            try:
                query = self.db.collection("debug_error_logs").limit(limit)
                if source:
                    query = query.where("source", "==", source)
                
                docs = await asyncio.to_thread(query.get)
                
                for doc in docs:
                    data = doc.to_dict()
                    results.append({
                        "log_id": data.get("log_id"),
                        "url": data.get("url"),
                        "error": data.get("error"),
                        "source": data.get("source"),
                        "timestamp": data.get("timestamp")
                    })
            except Exception as e:
                logger.warning(f"⚠️ Firestore query failed: {e}")
        
        # Fallback local
        error_dir = self.local_storage_path / "errors"
        if error_dir.exists():
            for file in sorted(error_dir.glob("*.json.gz"), reverse=True)[:limit]:
                try:
                    with gzip.open(file, 'rt') as f:
                        data = json.load(f)
                        if not source or data.get("source") == source:
                            results.append({
                                "log_id": data.get("log_id"),
                                "url": data.get("url"),
                                "error": data.get("error"),
                                "source": data.get("source"),
                                "timestamp": data.get("timestamp")
                            })
                except:
                    continue
        
        return results[:limit]
    
    def _generate_log_id(self, url: str, source: str) -> str:
        """Gera ID único para log"""
        content = f"{url}_{source}_{datetime.utcnow().isoformat()}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    async def _save_local(
        self,
        log_id: str,
        doc: Dict[str, Any],
        collection: str = "html"
    ):
        """Salva localmente como fallback"""
        try:
            collection_dir = self.local_storage_path / collection
            collection_dir.mkdir(parents=True, exist_ok=True)
            
            file_path = collection_dir / f"{log_id}.json.gz"
            
            with gzip.open(file_path, 'wt') as f:
                json.dump(doc, f, indent=2)
            
            logger.info(f"📁 Local: Salvo em {file_path}")
            
        except Exception as e:
            logger.error(f"❌ Local save failed: {e}")


class AutoHealingSystem:
    """
    Sistema de auto-healing para crawlers
    
    Usa IA para:
    1. Analisar HTMLs que falharam
    2. Gerar novo código de parser
    3. Testar e validar
    4. Deploy automático
    """
    
    def __init__(
        self,
        debug_logger: DebugLogger,
        ai_processor: Any  # AIFallbackProcessor
    ):
        self.debug_logger = debug_logger
        self.ai_processor = ai_processor
    
    async def analyze_and_heal(
        self,
        url: str,
        source: str
    ) -> Optional[str]:
        """
        Analisa falha e tenta corrigir
        
        Returns: Novo código de parser (se gerado)
        """
        logger.info(f"🔧 Auto-healing: {source} - {url}")
        
        # 1. Busca HTML que falhou
        failed_logs = await self.debug_logger.list_failed_urls(source=source, limit=1)
        
        if not failed_logs:
            logger.warning(f"   ⚠️ Sem logs de falha para {source}")
            return None
        
        log_id = failed_logs[0]["log_id"]
        html = await self.debug_logger.get_html(log_id)
        
        if not html:
            logger.warning(f"   ⚠️ HTML não encontrado para {log_id}")
            return None
        
        # 2. Usa IA para gerar novo parser
        prompt = f"""Analyze this HTML and generate a Python function to extract data.

URL: {url}
Source: {source}
HTML: {html[:10000]}

Generate a complete async function that:
1. Takes the HTML as input
2. Extracts all relevant data
3. Returns structured dict

Function signature:
async def parse_{source}(html: str) -> Dict[str, Any]:
    # Your code here
    pass

Return ONLY the Python code, no explanations.
"""
        
        from ..ai.ai_fallback import AIFallbackProcessor
        ai = AIFallbackProcessor()
        
        # Usa AI para gerar código
        result = await ai.process_with_grok_for_code(prompt)
        
        if result.success and result.data:
            new_code = result.data.get("code", "")
            
            if new_code:
                logger.info(f"   ✅ Novo parser gerado!")
                logger.info(f"   📝 Código:\n{new_code}")
                
                # 3. Testa novo parser
                is_valid = await self._test_parser(new_code, html)
                
                if is_valid:
                    logger.info(f"   ✅ Parser validado!")
                    return new_code
                else:
                    logger.warning(f"   ⚠️ Parser inválido")
        
        return None
    
    async def _test_parser(self, code: str, html: str) -> bool:
        """Testa se parser funciona"""
        try:
            # Executa código em namespace isolado
            namespace = {}
            exec(code, namespace)
            
            # Pega função gerada
            parser_func = None
            for name, obj in namespace.items():
                if callable(obj) and name.startswith("parse_"):
                    parser_func = obj
                    break
            
            if not parser_func:
                return False
            
            # Testa
            result = await parser_func(html)
            
            # Valida que retornou dict não vazio
            if isinstance(result, dict) and result:
                logger.info(f"   ✅ Parser retornou: {len(result)} campos")
                return True
            
        except Exception as e:
            logger.warning(f"   ⚠️ Parser test failed: {e}")
        
        return False
