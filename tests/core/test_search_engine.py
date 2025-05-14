import pytest
from unittest.mock import Mock, patch
import numpy as np
from typing import List

from src.core.search_engine import (
    SearchEngine,
    SearchQuery,
    RankedResult
)
from src.core.vector_store.base import SearchResult

@pytest.fixture
def mock_vector_store():
    """ベクトルストアのモック"""
    with patch('src.core.vector_store.chroma.ChromaVectorStore') as mock:
        store = Mock()
        mock.return_value = store
        yield store

@pytest.fixture
def mock_ollama_client():
    """OllamaClientのモック"""
    with patch('src.core.search_engine.OllamaClient') as mock:
        client = Mock()
        mock.return_value = client
        yield client

@pytest.fixture
def search_engine(mock_vector_store, mock_ollama_client):
    """テスト用の検索エンジン"""
    return SearchEngine(
        vector_store=mock_vector_store,
        ollama_client=mock_ollama_client
    )

def create_test_documents() -> List[str]:
    """テスト用のドキュメントを生成"""
    return [
        "The quick brown fox jumps over the lazy dog",
        "A quick brown dog sleeps under the tree",
        "The lazy fox watches the sleeping dog",
        "A document about different topics entirely",
        "Another unrelated document for testing"
    ]

def create_test_search_results() -> List[SearchResult]:
    """テスト用の検索結果を生成"""
    return [
        SearchResult(
            text="The quick brown fox jumps over the lazy dog",
            metadata={"source": "doc1"},
            similarity=0.9,
            id="1"
        ),
        SearchResult(
            text="A quick brown dog sleeps under the tree",
            metadata={"source": "doc2"},
            similarity=0.8,
            id="2"
        ),
        SearchResult(
            text="The lazy fox watches the sleeping dog",
            metadata={"source": "doc3"},
            similarity=0.7,
            id="3"
        )
    ]

@pytest.mark.asyncio
async def test_search_basic(search_engine, mock_vector_store, mock_ollama_client):
    """基本的な検索機能のテスト"""
    # テストデータの準備
    documents = create_test_documents()
    await search_engine.update_index(documents)
    
    # モックの設定
    mock_ollama_client.get_embeddings.return_value = [[0.1, 0.2, 0.3]]
    mock_vector_store.search.return_value = create_test_search_results()
    
    # 検索実行
    query = SearchQuery(
        text="quick brown fox",
        semantic_weight=0.7
    )
    results = await search_engine.search(query)
    
    # 結果の検証
    assert len(results) > 0
    assert isinstance(results[0], RankedResult)
    assert "fox" in results[0].text.lower()
    assert results[0].semantic_score >= 0
    assert results[0].keyword_score >= 0

@pytest.mark.asyncio
async def test_hybrid_scoring(search_engine):
    """ハイブリッドスコアリングのテスト"""
    # インデックスの更新
    documents = create_test_documents()
    await search_engine.update_index(documents)
    
    # セマンティック検索結果
    semantic_results = create_test_search_results()
    
    # キーワードスコア
    keyword_scores = [(0, 0.9), (1, 0.8), (2, 0.7)]
    
    # スコアの組み合わせ
    results = search_engine._combine_scores(
        semantic_results,
        keyword_scores,
        semantic_weight=0.7
    )
    
    # スコアの検証
    assert len(results) > 0
    for result in results:
        assert 0 <= result.semantic_score <= 1
        assert 0 <= result.keyword_score <= 1
        assert 0 <= result.final_score <= 1

@pytest.mark.asyncio
async def test_result_optimization(search_engine):
    """結果の最適化テスト"""
    results = [
        RankedResult(
            text="Short text",
            metadata={},
            semantic_score=0.9,
            keyword_score=0.8,
            final_score=0.85
        ),
        RankedResult(
            text="A much longer text that should take up more tokens in the context",
            metadata={},
            semantic_score=0.8,
            keyword_score=0.7,
            final_score=0.75
        )
    ]
    
    # トークン制限付きで最適化
    optimized = search_engine.optimize_results(results, max_tokens=10)
    assert len(optimized) == 1
    assert optimized[0].text == "Short text"

@pytest.mark.asyncio
async def test_filter_search(search_engine, mock_vector_store):
    """フィルタ付き検索のテスト"""
    # テストデータの準備
    documents = create_test_documents()
    await search_engine.update_index(documents)
    
    # フィルタ条件付きの検索
    query = SearchQuery(
        text="test query",
        filters={"source": "doc1"}
    )
    
    mock_vector_store.search.return_value = [
        SearchResult(
            text="Test document",
            metadata={"source": "doc1"},
            similarity=0.8,
            id="1"
        )
    ]
    
    results = await search_engine.search(query)
    
    # 結果の検証
    assert len(results) > 0
    assert results[0].metadata["source"] == "doc1"

@pytest.mark.asyncio
async def test_empty_results(search_engine, mock_vector_store):
    """空の結果セットのテスト"""
    # インデックスの更新
    documents = create_test_documents()
    await search_engine.update_index(documents)
    
    # 該当なしの検索結果を返すように設定
    mock_vector_store.search.return_value = []
    
    query = SearchQuery(text="nonexistent content")
    results = await search_engine.search(query)
    
    assert len(results) == 0

@pytest.mark.asyncio
async def test_error_handling(search_engine, mock_vector_store):
    """エラーハンドリングのテスト"""
    # エラーを発生させる
    mock_vector_store.search.side_effect = Exception("Test error")
    
    query = SearchQuery(text="test query")
    
    with pytest.raises(Exception):
        await search_engine.search(query)

@pytest.mark.asyncio
async def test_score_normalization(search_engine):
    """スコア正規化のテスト"""
    # 極端なスコアを持つ結果
    semantic_results = [
        SearchResult(
            text="Text 1",
            metadata={},
            similarity=1.0,
            id="1"
        ),
        SearchResult(
            text="Text 2",
            metadata={},
            similarity=0.0,
            id="2"
        )
    ]
    
    keyword_scores = [(0, 1.0), (1, 0.0)]
    
    results = search_engine._combine_scores(
        semantic_results,
        keyword_scores,
        semantic_weight=0.5
    )
    
    # 正規化されたスコアの検証
    assert len(results) == 2
    assert results[0].final_score == 1.0
    assert results[1].final_score == 0.0