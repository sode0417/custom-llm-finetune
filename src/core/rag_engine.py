from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import json
import asyncio
from datetime import datetime

from src.core.search_engine import SearchEngine, SearchQuery, RankedResult
from src.clients.ollama_client import OllamaClient
from src.utils.logger import logger
from config.settings import (
    OLLAMA_MODELS,
    SEARCH,
    GENERATION
)

@dataclass
class GenerationResult:
    """生成結果を表すデータクラス"""
    text: str
    sources: List[Dict[str, Any]]
    confidence: float
    metadata: Dict[str, Any]

class ContextManager:
    """コンテキスト管理を行うクラス"""
    
    def __init__(self, max_tokens: int = 2000):
        self.max_tokens = max_tokens
    
    def build_context(
        self,
        results: List[RankedResult],
        query: str
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """検索結果からコンテキストを構築"""
        context_parts = []
        sources = []
        total_tokens = 0
        
        # スコアでソート済みの結果から追加
        for result in results:
            # 簡易的なトークン数の見積もり
            estimated_tokens = len(result.text.split())
            
            if total_tokens + estimated_tokens <= self.max_tokens:
                context_parts.append(
                    f"Source: {result.metadata.get('source', 'Unknown')}\n"
                    f"Content: {result.text}\n"
                    f"Relevance: {result.final_score:.2f}\n"
                )
                total_tokens += estimated_tokens
                
                sources.append({
                    'text': result.text,
                    'metadata': result.metadata,
                    'relevance': result.final_score
                })
            else:
                break
        
        context = "\n---\n".join(context_parts)
        return context, sources

class RAGEngine:
    """RAG（Retrieval-Augmented Generation）エンジン"""
    
    def __init__(
        self,
        search_engine: Optional[SearchEngine] = None,
        ollama_client: Optional[OllamaClient] = None
    ):
        self.search_engine = search_engine or SearchEngine()
        self.ollama_client = ollama_client or OllamaClient()
        self.context_manager = ContextManager()
    
    def _build_prompt(
        self,
        query: str,
        context: str,
        metadata: Optional[Dict] = None
    ) -> str:
        """プロンプトを構築"""
        system_prompt = GENERATION['system_prompt']
        
        if metadata:
            # メタデータに基づいてシステムプロンプトをカスタマイズ
            if metadata.get('format'):
                system_prompt += f"\n出力フォーマット: {metadata['format']}"
            if metadata.get('style'):
                system_prompt += f"\n回答スタイル: {metadata['style']}"
        
        return f"""System: {system_prompt}

Context:
{context}

Question: {query}

Answer:"""
    
    def _estimate_confidence(
        self,
        response: str,
        sources: List[Dict],
        query: str
    ) -> float:
        """回答の信頼度を推定"""
        try:
            # 基本スコアは検索結果の関連性スコアの平均
            base_score = (
                sum(s['relevance'] for s in sources) / len(sources)
                if sources else 0.0
            )
            
            # 回答の長さによる調整
            length_score = min(len(response.split()) / 100, 1.0)
            
            # ソースの数による調整
            source_score = min(len(sources) / 5, 1.0)
            
            # 重み付けして組み合わせ
            confidence = (
                base_score * 0.5 +
                length_score * 0.3 +
                source_score * 0.2
            )
            
            return min(max(confidence, 0.0), 1.0)
            
        except Exception as e:
            logger.warning(f"Confidence estimation failed: {e}")
            return 0.5  # デフォルト値
    
    async def process_query(
        self,
        query: str,
        metadata: Optional[Dict] = None
    ) -> GenerationResult:
        """クエリを処理して回答を生成"""
        try:
            # 検索クエリの構築
            search_query = SearchQuery(
                text=query,
                filters=metadata.get('filters') if metadata else None,
                semantic_weight=metadata.get(
                    'semantic_weight',
                    SEARCH['semantic_weight']
                )
            )
            
            # 関連文書の検索
            search_results = await self.search_engine.search(search_query)
            
            if not search_results:
                return GenerationResult(
                    text="申し訳ありません。関連する情報が見つかりませんでした。",
                    sources=[],
                    confidence=0.0,
                    metadata={'error': 'no_results'}
                )
            
            # コンテキストの構築
            context, sources = self.context_manager.build_context(
                search_results,
                query
            )
            
            # プロンプトの構築
            prompt = self._build_prompt(query, context, metadata)
            
            # 回答の生成
            response = await self.ollama_client.generate(
                prompt=prompt,
                model_name=metadata.get(
                    'model',
                    OLLAMA_MODELS['general']
                ),
                temperature=metadata.get(
                    'temperature',
                    GENERATION['temperature']
                )
            )
            
            # 信頼度の推定
            confidence = self._estimate_confidence(response, sources, query)
            
            # 結果の構築
            result = GenerationResult(
                text=response,
                sources=sources,
                confidence=confidence,
                metadata={
                    'query': query,
                    'timestamp': datetime.now().isoformat(),
                    'model': OLLAMA_MODELS['general'],
                    'context_length': len(context.split())
                }
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Query processing failed: {e}")
            raise
    
    async def update_index(self, documents: List[str]) -> None:
        """検索インデックスを更新"""
        await self.search_engine.update_index(documents)
    
    def get_stats(self) -> Dict[str, Any]:
        """システムの統計情報を取得"""
        return {
            'search_engine': self.search_engine.get_stats(),
            'models': {
                'embedding': OLLAMA_MODELS['embedding'],
                'general': OLLAMA_MODELS['general']
            },
            'settings': {
                'search': SEARCH,
                'generation': GENERATION
            }
        }