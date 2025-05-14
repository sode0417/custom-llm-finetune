from typing import List, Dict, Any, Optional, TypeVar
from dataclasses import dataclass
import asyncio
from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np

from src.core.vector_store.base import SearchResult
from src.core.vector_store.chroma import ChromaVectorStore
from src.clients.ollama_client import OllamaClient
from src.utils.logger import logger
from config.settings import (
    VECTOR_STORE_DIR,
    OLLAMA_MODELS,
    SEARCH
)

T = TypeVar('T')

@dataclass
class SearchQuery:
    """検索クエリを表すデータクラス"""
    text: str
    filters: Optional[Dict[str, Any]] = None
    top_k: int = SEARCH['top_k']
    semantic_weight: float = SEARCH['semantic_weight']

@dataclass
class RankedResult:
    """ランク付けされた検索結果"""
    text: str
    metadata: Dict[str, Any]
    semantic_score: float
    keyword_score: float
    final_score: float
    id: Optional[str] = None

class SearchEngine:
    """RAG検索エンジンの実装"""
    
    def __init__(
        self,
        vector_store: Optional[ChromaVectorStore] = None,
        ollama_client: Optional[OllamaClient] = None
    ):
        self.vector_store = vector_store or ChromaVectorStore()
        self.ollama_client = ollama_client or OllamaClient()
        self.tfidf = TfidfVectorizer(
            lowercase=True,
            ngram_range=(1, 2),
            max_features=10000
        )
        self.tfidf_matrix = None
        self.documents = []
    
    async def update_index(self, documents: List[str]) -> None:
        """検索インデックスを更新"""
        try:
            self.documents = documents
            self.tfidf_matrix = self.tfidf.fit_transform(documents)
            logger.info(
                f"Updated search index with {len(documents)} documents"
            )
        except Exception as e:
            logger.error(f"Failed to update search index: {e}")
            raise
    
    def _compute_keyword_scores(
        self,
        query: str,
        top_k: int
    ) -> List[tuple[int, float]]:
        """キーワードベースの類似度を計算"""
        if not self.tfidf_matrix:
            return []
            
        try:
            # クエリのベクトル化
            query_vector = self.tfidf.transform([query])
            
            # コサイン類似度の計算
            scores = (
                self.tfidf_matrix @ query_vector.T
            ).toarray().flatten()
            
            # 上位k件のインデックスとスコアを取得
            top_indices = np.argsort(scores)[-top_k:][::-1]
            return [
                (idx, float(scores[idx]))
                for idx in top_indices
                if scores[idx] > 0
            ]
            
        except Exception as e:
            logger.error(f"Keyword scoring failed: {e}")
            return []
    
    async def _compute_semantic_similarity(
        self,
        query: str,
        filter_criteria: Optional[Dict] = None,
        top_k: int = SEARCH['top_k']
    ) -> List[SearchResult]:
        """セマンティック検索を実行"""
        try:
            # クエリのembeddingを生成
            query_embedding = await self.ollama_client.get_embeddings(
                [query],
                OLLAMA_MODELS['embedding']
            )
            
            # ベクトル検索を実行
            results = await self.vector_store.search(
                query_vector=query_embedding[0],
                filter_criteria=filter_criteria,
                top_k=top_k
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []
    
    def _combine_scores(
        self,
        semantic_results: List[SearchResult],
        keyword_scores: List[tuple[int, float]],
        semantic_weight: float
    ) -> List[RankedResult]:
        """セマンティックスコアとキーワードスコアを組み合わせ"""
        combined_results = {}
        
        # セマンティック検索結果のスコアを正規化
        if semantic_results:
            max_semantic = max(r.similarity for r in semantic_results)
            min_semantic = min(r.similarity for r in semantic_results)
            semantic_range = max_semantic - min_semantic or 1
        
        # キーワードスコアを正規化
        if keyword_scores:
            max_keyword = max(score for _, score in keyword_scores)
            min_keyword = min(score for _, score in keyword_scores)
            keyword_range = max_keyword - min_keyword or 1
        
        # セマンティック検索結果を処理
        for result in semantic_results:
            normalized_semantic = (
                (result.similarity - min_semantic) / semantic_range
                if semantic_results else 0
            )
            combined_results[result.text] = RankedResult(
                text=result.text,
                metadata=result.metadata,
                semantic_score=normalized_semantic,
                keyword_score=0,
                final_score=normalized_semantic * semantic_weight,
                id=result.id
            )
        
        # キーワード検索結果を統合
        for idx, score in keyword_scores:
            text = self.documents[idx]
            normalized_keyword = (score - min_keyword) / keyword_range
            
            if text in combined_results:
                result = combined_results[text]
                result.keyword_score = normalized_keyword
                result.final_score += (
                    normalized_keyword * (1 - semantic_weight)
                )
            else:
                combined_results[text] = RankedResult(
                    text=text,
                    metadata={},
                    semantic_score=0,
                    keyword_score=normalized_keyword,
                    final_score=normalized_keyword * (1 - semantic_weight)
                )
        
        # スコアで降順ソート
        return sorted(
            combined_results.values(),
            key=lambda x: x.final_score,
            reverse=True
        )
    
    async def search(
        self,
        query: SearchQuery
    ) -> List[RankedResult]:
        """ハイブリッド検索を実行"""
        try:
            # セマンティック検索とキーワード検索を並行実行
            semantic_results, keyword_scores = await asyncio.gather(
                self._compute_semantic_similarity(
                    query.text,
                    query.filters,
                    query.top_k
                ),
                asyncio.to_thread(
                    self._compute_keyword_scores,
                    query.text,
                    query.top_k
                )
            )
            
            # スコアを組み合わせてランク付け
            results = self._combine_scores(
                semantic_results,
                keyword_scores,
                query.semantic_weight
            )
            
            # 上位k件を返す
            return results[:query.top_k]
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise
    
    def optimize_results(
        self,
        results: List[RankedResult],
        max_tokens: int
    ) -> List[RankedResult]:
        """検索結果を最適化"""
        if not results:
            return []
            
        optimized = []
        total_tokens = 0
        
        for result in results:
            # 簡易的なトークン数の見積もり
            estimated_tokens = len(result.text.split())
            
            if total_tokens + estimated_tokens <= max_tokens:
                optimized.append(result)
                total_tokens += estimated_tokens
            else:
                break
        
        return optimized