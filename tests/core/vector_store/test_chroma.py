import pytest
import asyncio
from typing import List, Dict
import numpy as np
from pathlib import Path

from src.core.vector_store.base import SearchResult, VectorStoreError
from src.core.vector_store.chroma import ChromaVectorStore

@pytest.fixture
async def vector_store(tmp_path):
    """テスト用のベクトルストア"""
    store = ChromaVectorStore(
        collection_name="test_collection",
        dimension=4,
        persist_directory=tmp_path / "chroma"
    )
    yield store
    # クリーンアップ
    await store.clear()

def create_test_embeddings(
    count: int,
    dim: int = 4
) -> List[List[float]]:
    """テスト用の埋め込みベクトルを生成"""
    return [
        list(np.random.rand(dim))
        for _ in range(count)
    ]

def create_test_metadata(count: int) -> List[Dict]:
    """テスト用のメタデータを生成"""
    return [
        {
            "index": i,
            "type": "test",
            "nested": {"value": i}
        }
        for i in range(count)
    ]

@pytest.mark.asyncio
async def test_add_and_retrieve(vector_store):
    """追加と取得のテスト"""
    # テストデータの準備
    embeddings = create_test_embeddings(3)
    texts = [f"Text {i}" for i in range(3)]
    metadata = create_test_metadata(3)
    
    # データの追加
    ids = await vector_store.add_embeddings(embeddings, texts, metadata)
    assert len(ids) == 3
    
    # IDによる取得
    results = await vector_store.get_by_id(ids)
    assert len(results) == 3
    
    for i, result in enumerate(results):
        assert result.text == f"Text {i}"
        assert result.metadata["index"] == i
        assert result.metadata["type"] == "test"
        assert result.metadata["nested"]["value"] == i

@pytest.mark.asyncio
async def test_search(vector_store):
    """検索機能のテスト"""
    # テストデータの準備
    embeddings = create_test_embeddings(10)
    texts = [f"Text {i}" for i in range(10)]
    metadata = create_test_metadata(10)
    
    # データの追加
    await vector_store.add_embeddings(embeddings, texts, metadata)
    
    # 検索の実行
    query_vector = embeddings[0]  # 最初のベクトルで検索
    results = await vector_store.search(
        query_vector=query_vector,
        top_k=3
    )
    
    assert len(results) == 3
    # 最も類似度の高い結果が最初のベクトルであることを確認
    assert results[0].text == "Text 0"
    assert results[0].similarity > 0.9  # ほぼ完全一致

@pytest.mark.asyncio
async def test_delete(vector_store):
    """削除機能のテスト"""
    # テストデータの追加
    embeddings = create_test_embeddings(5)
    texts = [f"Text {i}" for i in range(5)]
    metadata = create_test_metadata(5)
    
    ids = await vector_store.add_embeddings(embeddings, texts, metadata)
    
    # IDによる削除
    deleted_ids = await vector_store.delete(ids=[ids[0]])
    assert len(deleted_ids) == 1
    
    # 条件による削除
    deleted_ids = await vector_store.delete(
        filter_criteria={"type": "test"}
    )
    assert len(deleted_ids) == 4  # 残りすべて
    
    # 統計の確認
    stats = await vector_store.get_stats()
    assert stats["total_items"] == 0

@pytest.mark.asyncio
async def test_batch_processing(vector_store):
    """バッチ処理のテスト"""
    # 大量のテストデータ
    count = 150  # バッチサイズ(100)を超える数
    embeddings = create_test_embeddings(count)
    texts = [f"Text {i}" for i in range(count)]
    metadata = create_test_metadata(count)
    
    # バッチ処理での追加
    ids = await vector_store.add_embeddings(embeddings, texts, metadata)
    assert len(ids) == count
    
    # 統計の確認
    stats = await vector_store.get_stats()
    assert stats["total_items"] == count

@pytest.mark.asyncio
async def test_error_handling(vector_store):
    """エラーハンドリングのテスト"""
    # 不正な次元数
    with pytest.raises(VectorStoreError):
        wrong_dim_embeddings = create_test_embeddings(3, dim=5)  # 異なる次元数
        await vector_store.add_embeddings(
            wrong_dim_embeddings,
            ["Text 1", "Text 2", "Text 3"],
            create_test_metadata(3)
        )
    
    # 不整合な入力長
    with pytest.raises(ValueError):
        embeddings = create_test_embeddings(3)
        await vector_store.add_embeddings(
            embeddings,
            ["Text 1", "Text 2"],  # テキストが1つ少ない
            create_test_metadata(3)
        )

@pytest.mark.asyncio
async def test_concurrent_operations(vector_store):
    """並行処理のテスト"""
    # 同時に複数の操作を実行
    embeddings1 = create_test_embeddings(5)
    embeddings2 = create_test_embeddings(5)
    
    # 並行してデータを追加
    results = await asyncio.gather(
        vector_store.add_embeddings(
            embeddings1,
            [f"Text A{i}" for i in range(5)],
            create_test_metadata(5)
        ),
        vector_store.add_embeddings(
            embeddings2,
            [f"Text B{i}" for i in range(5)],
            create_test_metadata(5)
        )
    )
    
    assert len(results) == 2
    assert len(results[0]) == 5
    assert len(results[1]) == 5
    
    # 統計の確認
    stats = await vector_store.get_stats()
    assert stats["total_items"] == 10

@pytest.mark.asyncio
async def test_filter_search(vector_store):
    """フィルタ付き検索のテスト"""
    # 異なるタイプのデータを追加
    embeddings = create_test_embeddings(6)
    texts = [f"Text {i}" for i in range(6)]
    metadata = [
        {"type": "A", "value": i}
        for i in range(3)
    ] + [
        {"type": "B", "value": i}
        for i in range(3)
    ]
    
    await vector_store.add_embeddings(embeddings, texts, metadata)
    
    # タイプAのみを検索
    results = await vector_store.search(
        query_vector=embeddings[0],
        top_k=5,
        filter_criteria={"type": "A"}
    )
    
    assert len(results) == 3
    for result in results:
        assert result.metadata["type"] == "A"