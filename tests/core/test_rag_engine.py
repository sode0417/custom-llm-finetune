import pytest
from unittest.mock import Mock, patch, AsyncMock
from typing import List, Dict
import json

from src.core.rag_engine import (
    RAGEngine,
    ContextManager,
    GenerationResult,
    RankedResult
)

@pytest.fixture
def mock_search_engine():
    """SearchEngineのモック"""
    with patch('src.core.rag_engine.SearchEngine') as mock:
        engine = Mock()
        engine.search = AsyncMock()
        mock.return_value = engine
        yield engine

@pytest.fixture
def mock_ollama_client():
    """OllamaClientのモック"""
    with patch('src.core.rag_engine.OllamaClient') as mock:
        client = Mock()
        client.generate = AsyncMock()
        mock.return_value = client
        yield client

@pytest.fixture
def rag_engine(mock_search_engine, mock_ollama_client):
    """テスト用のRAGエンジン"""
    return RAGEngine(
        search_engine=mock_search_engine,
        ollama_client=mock_ollama_client
    )

def create_test_results() -> List[RankedResult]:
    """テスト用の検索結果を生成"""
    return [
        RankedResult(
            text="First test document content",
            metadata={"source": "doc1.pdf", "page": 1},
            semantic_score=0.9,
            keyword_score=0.8,
            final_score=0.85,
            id="1"
        ),
        RankedResult(
            text="Second test document content",
            metadata={"source": "doc2.pdf", "page": 2},
            semantic_score=0.8,
            keyword_score=0.7,
            final_score=0.75,
            id="2"
        )
    ]

@pytest.mark.asyncio
async def test_context_building():
    """コンテキスト構築のテスト"""
    context_manager = ContextManager(max_tokens=100)
    results = create_test_results()
    
    context, sources = context_manager.build_context(
        results,
        "test query"
    )
    
    # コンテキストの検証
    assert "First test document" in context
    assert "Second test document" in context
    assert len(sources) == 2
    assert sources[0]['metadata']['source'] == "doc1.pdf"

@pytest.mark.asyncio
async def test_query_processing(rag_engine, mock_search_engine, mock_ollama_client):
    """クエリ処理のテスト"""
    # モックの設定
    mock_search_engine.search.return_value = create_test_results()
    mock_ollama_client.generate.return_value = "Test response"
    
    # クエリの実行
    result = await rag_engine.process_query(
        "test query",
        metadata={"temperature": 0.7}
    )
    
    # 結果の検証
    assert isinstance(result, GenerationResult)
    assert result.text == "Test response"
    assert len(result.sources) > 0
    assert 0 <= result.confidence <= 1
    assert "query" in result.metadata

@pytest.mark.asyncio
async def test_empty_results_handling(rag_engine, mock_search_engine):
    """空の検索結果の処理テスト"""
    # 空の検索結果を返すように設定
    mock_search_engine.search.return_value = []
    
    result = await rag_engine.process_query("test query")
    
    assert "申し訳ありません" in result.text
    assert result.confidence == 0.0
    assert result.metadata['error'] == 'no_results'

@pytest.mark.asyncio
async def test_confidence_estimation(rag_engine):
    """信頼度推定のテスト"""
    # テストケース
    test_cases = [
        {
            'response': "Short answer",
            'sources': [{'relevance': 0.9}, {'relevance': 0.8}],
            'expected_range': (0.5, 0.9)
        },
        {
            'response': "A much longer and more detailed answer " * 10,
            'sources': [{'relevance': 0.7}, {'relevance': 0.6}, {'relevance': 0.5}],
            'expected_range': (0.6, 0.8)
        }
    ]
    
    for case in test_cases:
        confidence = rag_engine._estimate_confidence(
            case['response'],
            case['sources'],
            "test query"
        )
        
        assert case['expected_range'][0] <= confidence <= case['expected_range'][1]

@pytest.mark.asyncio
async def test_prompt_building(rag_engine):
    """プロンプト構築のテスト"""
    query = "test query"
    context = "test context"
    metadata = {
        "format": "JSON",
        "style": "technical"
    }
    
    prompt = rag_engine._build_prompt(query, context, metadata)
    
    assert query in prompt
    assert context in prompt
    assert "JSON" in prompt
    assert "technical" in prompt

@pytest.mark.asyncio
async def test_error_handling(rag_engine, mock_search_engine):
    """エラーハンドリングのテスト"""
    # 検索エラーをシミュレート
    mock_search_engine.search.side_effect = Exception("Search failed")
    
    with pytest.raises(Exception):
        await rag_engine.process_query("test query")

@pytest.mark.asyncio
async def test_index_update(rag_engine, mock_search_engine):
    """インデックス更新のテスト"""
    mock_search_engine.update_index = AsyncMock()
    
    documents = ["doc1", "doc2", "doc3"]
    await rag_engine.update_index(documents)
    
    mock_search_engine.update_index.assert_called_once_with(documents)

@pytest.mark.asyncio
async def test_metadata_handling(rag_engine, mock_search_engine, mock_ollama_client):
    """メタデータ処理のテスト"""
    # モックの設定
    mock_search_engine.search.return_value = create_test_results()
    mock_ollama_client.generate.return_value = "Test response"
    
    # カスタムメタデータでクエリを実行
    metadata = {
        "temperature": 0.5,
        "filters": {"source": "doc1.pdf"},
        "model": "test-model"
    }
    
    result = await rag_engine.process_query("test query", metadata)
    
    # メタデータの検証
    assert result.metadata['model'] == "test-model"
    assert isinstance(result.metadata['timestamp'], str)
    assert result.metadata['query'] == "test query"

def test_stats(rag_engine, mock_search_engine):
    """統計情報取得のテスト"""
    mock_search_engine.get_stats.return_value = {
        "total_documents": 10,
        "index_size": 1000
    }
    
    stats = rag_engine.get_stats()
    
    assert "search_engine" in stats
    assert "models" in stats
    assert "settings" in stats
    assert stats['search_engine']['total_documents'] == 10