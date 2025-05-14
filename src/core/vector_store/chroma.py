from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings
import asyncio
from pathlib import Path
import json
import time

from .base import (
    VectorStore,
    SearchResult,
    VectorStoreError,
    validate_embeddings,
    batch_data
)
from src.utils.logger import logger
from config.settings import VECTOR_STORE_DIR

class ChromaVectorStore(VectorStore):
    """ChromaDBを使用したベクトルストア実装"""
    
    def __init__(
        self,
        collection_name: str = "documents",
        dimension: int = 384,  # BGE-Small-ENの次元数
        persist_directory: Optional[Path] = None
    ):
        self.collection_name = collection_name
        self.dimension = dimension
        self.persist_directory = (
            persist_directory or
            VECTOR_STORE_DIR / "chroma"
        )
        
        # クライアントの初期化
        try:
            self.client = chromadb.Client(
                Settings(
                    persist_directory=str(self.persist_directory),
                    anonymized_telemetry=False
                )
            )
            
            # コレクションの取得または作成
            self.collection = self.client.get_or_create_collection(
                name=collection_name,
                metadata={"dimension": dimension}
            )
            
            logger.info(
                f"Initialized ChromaDB store: {collection_name} "
                f"(dimension: {dimension})"
            )
            
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            raise VectorStoreError(f"ChromaDB initialization failed: {e}") from e
    
    async def add_embeddings(
        self,
        embeddings: List[List[float]],
        texts: List[str],
        metadata: List[Dict[str, Any]]
    ) -> List[str]:
        """ベクトルデータを追加"""
        try:
            # 入力の検証
            if not (len(embeddings) == len(texts) == len(metadata)):
                raise ValueError("Inconsistent input lengths")
            
            validate_embeddings(embeddings, self.dimension)
            
            # IDの生成（タイムスタンプベース）
            base_id = str(int(time.time() * 1000))
            ids = [
                f"{base_id}_{i}"
                for i in range(len(embeddings))
            ]
            
            # バッチ処理（ChromaDBの推奨）
            batch_size = 100
            for batch_idx, batch_start in enumerate(range(0, len(ids), batch_size)):
                batch_end = batch_start + batch_size
                
                # バッチデータの準備
                batch_ids = ids[batch_start:batch_end]
                batch_embeddings = embeddings[batch_start:batch_end]
                batch_texts = texts[batch_start:batch_end]
                batch_metadata = metadata[batch_start:batch_end]
                
                # メタデータの正規化（ChromaDBの制約に合わせる）
                normalized_metadata = [
                    {
                        k: (
                            json.dumps(v)
                            if not isinstance(v, (str, int, float, bool))
                            else v
                        )
                        for k, v in m.items()
                    }
                    for m in batch_metadata
                ]
                
                # バッチの追加
                await asyncio.to_thread(
                    self.collection.add,
                    ids=batch_ids,
                    embeddings=batch_embeddings,
                    documents=batch_texts,
                    metadatas=normalized_metadata
                )
                
                logger.debug(
                    f"Added batch {batch_idx + 1} "
                    f"({len(batch_ids)} items)"
                )
            
            logger.info(
                f"Successfully added {len(ids)} items to ChromaDB"
            )
            return ids
            
        except Exception as e:
            logger.error(f"Failed to add embeddings: {e}")
            raise VectorStoreError(f"Failed to add embeddings: {e}") from e
    
    async def search(
        self,
        query_vector: List[float],
        top_k: int = 5,
        filter_criteria: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """類似ベクトルを検索"""
        try:
            # クエリベクトルの検証
            validate_embeddings([query_vector], self.dimension)
            
            # フィルタの構築
            where = None
            if filter_criteria:
                where = {
                    k: (
                        json.dumps(v)
                        if not isinstance(v, (str, int, float, bool))
                        else v
                    )
                    for k, v in filter_criteria.items()
                }
            
            # 検索の実行
            results = await asyncio.to_thread(
                self.collection.query,
                query_embeddings=[query_vector],
                n_results=top_k,
                where=where
            )
            
            # 結果の変換
            search_results = []
            for i in range(len(results['ids'][0])):
                # メタデータの復元
                metadata = results['metadatas'][0][i]
                for k, v in metadata.items():
                    try:
                        metadata[k] = json.loads(v)
                    except (json.JSONDecodeError, TypeError):
                        pass
                
                search_results.append(
                    SearchResult(
                        id=results['ids'][0][i],
                        text=results['documents'][0][i],
                        metadata=metadata,
                        similarity=float(results['distances'][0][i])
                    )
                )
            
            return search_results
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise VectorStoreError(f"Search failed: {e}") from e
    
    async def delete(
        self,
        ids: Optional[List[str]] = None,
        filter_criteria: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """データの削除"""
        try:
            if ids:
                # IDによる削除
                await asyncio.to_thread(
                    self.collection.delete,
                    ids=ids
                )
                deleted_ids = ids
            elif filter_criteria:
                # 条件による削除
                where = {
                    k: (
                        json.dumps(v)
                        if not isinstance(v, (str, int, float, bool))
                        else v
                    )
                    for k, v in filter_criteria.items()
                }
                # 削除前にIDを取得
                results = await asyncio.to_thread(
                    self.collection.get,
                    where=where
                )
                deleted_ids = results['ids']
                
                if deleted_ids:
                    await asyncio.to_thread(
                        self.collection.delete,
                        ids=deleted_ids
                    )
            else:
                raise ValueError("Either ids or filter_criteria must be provided")
            
            logger.info(f"Deleted {len(deleted_ids)} items from ChromaDB")
            return deleted_ids
            
        except Exception as e:
            logger.error(f"Deletion failed: {e}")
            raise VectorStoreError(f"Deletion failed: {e}") from e
    
    async def get_by_id(self, ids: List[str]) -> List[SearchResult]:
        """指定されたIDのデータを取得"""
        try:
            results = await asyncio.to_thread(
                self.collection.get,
                ids=ids
            )
            
            search_results = []
            for i in range(len(results['ids'])):
                # メタデータの復元
                metadata = results['metadatas'][i]
                for k, v in metadata.items():
                    try:
                        metadata[k] = json.loads(v)
                    except (json.JSONDecodeError, TypeError):
                        pass
                
                search_results.append(
                    SearchResult(
                        id=results['ids'][i],
                        text=results['documents'][i],
                        metadata=metadata,
                        similarity=1.0  # 完全一致
                    )
                )
            
            return search_results
            
        except Exception as e:
            logger.error(f"Get by ID failed: {e}")
            raise VectorStoreError(f"Get by ID failed: {e}") from e
    
    async def clear(self) -> None:
        """全データを削除"""
        try:
            await asyncio.to_thread(
                self.collection.delete,
                where={}
            )
            logger.info("Cleared all data from ChromaDB")
            
        except Exception as e:
            logger.error(f"Clear failed: {e}")
            raise VectorStoreError(f"Clear failed: {e}") from e
    
    async def get_stats(self) -> Dict[str, Any]:
        """統計情報を取得"""
        try:
            count = await asyncio.to_thread(
                self.collection.count
            )
            
            return {
                "total_items": count,
                "dimension": self.dimension,
                "collection_name": self.collection_name
            }
            
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            raise VectorStoreError(f"Failed to get stats: {e}") from e