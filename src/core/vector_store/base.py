from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import numpy as np

@dataclass
class SearchResult:
    """検索結果を表すデータクラス"""
    text: str
    metadata: Dict[str, Any]
    similarity: float
    id: Optional[str] = None

class VectorStore(ABC):
    """ベクトルストアの基本クラス"""
    
    @abstractmethod
    async def add_embeddings(
        self,
        embeddings: List[List[float]],
        texts: List[str],
        metadata: List[Dict[str, Any]]
    ) -> List[str]:
        """ベクトルデータを追加し、IDのリストを返す"""
        pass
    
    @abstractmethod
    async def search(
        self,
        query_vector: List[float],
        top_k: int = 5,
        filter_criteria: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """類似ベクトルを検索"""
        pass
    
    @abstractmethod
    async def delete(
        self,
        ids: Optional[List[str]] = None,
        filter_criteria: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """指定されたIDまたは条件に合うデータを削除し、削除されたIDを返す"""
        pass
    
    @abstractmethod
    async def get_by_id(
        self,
        ids: List[str]
    ) -> List[SearchResult]:
        """指定されたIDのデータを取得"""
        pass
    
    @abstractmethod
    async def clear(self) -> None:
        """全データを削除"""
        pass
    
    @abstractmethod
    async def get_stats(self) -> Dict[str, Any]:
        """ベクトルストアの統計情報を取得"""
        pass

class VectorStoreError(Exception):
    """ベクトルストア関連のエラー"""
    pass

class InvalidDimensionError(VectorStoreError):
    """ベクトルの次元が不正な場合のエラー"""
    pass

class StorageError(VectorStoreError):
    """ストレージ操作に関するエラー"""
    pass

def normalize_vector(vector: List[float]) -> List[float]:
    """ベクトルを正規化"""
    array = np.array(vector)
    norm = np.linalg.norm(array)
    if norm == 0:
        return vector
    return (array / norm).tolist()

def compute_similarity(
    vector1: List[float],
    vector2: List[float],
    metric: str = "cosine"
) -> float:
    """ベクトル間の類似度を計算"""
    v1 = np.array(vector1)
    v2 = np.array(vector2)
    
    if metric == "cosine":
        # コサイン類似度
        return float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))
    elif metric == "euclidean":
        # ユークリッド距離から類似度に変換
        distance = np.linalg.norm(v1 - v2)
        return float(1 / (1 + distance))
    elif metric == "dot":
        # 内積
        return float(np.dot(v1, v2))
    else:
        raise ValueError(f"Unsupported similarity metric: {metric}")

def validate_embeddings(
    embeddings: List[List[float]],
    expected_dim: Optional[int] = None
) -> None:
    """埋め込みベクトルのバリデーション"""
    if not embeddings:
        raise ValueError("Embeddings list is empty")
    
    # 次元数の確認
    dims = {len(emb) for emb in embeddings}
    if len(dims) > 1:
        raise InvalidDimensionError("Inconsistent embedding dimensions")
    
    dim = dims.pop()
    if expected_dim and dim != expected_dim:
        raise InvalidDimensionError(
            f"Expected dimension {expected_dim}, got {dim}"
        )
    
    # 値の範囲確認
    for emb in embeddings:
        if not all(isinstance(x, (int, float)) for x in emb):
            raise ValueError("Invalid embedding values")
        if any(abs(x) > 1e6 for x in emb):  # 異常に大きな値をチェック
            raise ValueError("Embedding values out of reasonable range")

def batch_data(
    data: List[Any],
    batch_size: int
) -> List[List[Any]]:
    """データをバッチに分割"""
    return [
        data[i:i + batch_size]
        for i in range(0, len(data), batch_size)
    ]