import pytest
import numpy as np
from unittest.mock import Mock, patch
from pathlib import Path
import json

from src.core.rag_engine import RAGEngine
from config.settings import VECTOR_STORE_DIR

@pytest.fixture
def mock_ollama_client():
    """OllamaClientのモック"""
    with patch('src.core.rag_engine.OllamaClient') as mock:
        client = Mock()
        mock.return_value = client
        yield client

@pytest.fixture
def sample_vector_store(vector_store_dir):
    """サンプルのベクトルストアデータを作成"""
    # メタデータの作成
    metadata = {
        'processed_files': {
            'test_file_1': {
                'file_name': 'test1.pdf',
                'chunk_count': 2,
                'processed_at': '2025-05-14T12:00:00',
                'embedding_model': 'test-embedding-model'
            }
        },
        'last_update': '2025-05-14T12:00:00'
    }
    
    # ベクトルストアディレクトリの作成
    doc_dir = vector_store_dir / 'test_file_1'
    doc_dir.mkdir(parents=True)
    
    # メタデータの保存
    with open(vector_store_dir / 'metadata.json', 'w') as f:
        json.dump(metadata, f)
    
    # Embeddingの保存
    embeddings = [
        [0.1, 0.2, 0.3],
        [0.4, 0.5, 0.6]
    ]
    with open(doc_dir / 'embeddings.json', 'w') as f:
        json.dump(embeddings, f)
    
    # チャンクの保存
    chunks = [
        {
            'text': 'Test chunk 1',
            'metadata': {
                'file_name': 'test1.pdf',
                'page_number': 1
            }
        },
        {
            'text': 'Test chunk 2',
            'metadata': {
                'file_name': 'test1.pdf',
                'page_number': 1
            }
        }
    ]
    with open(doc_dir / 'chunks.json', 'w') as f:
        json.dump(chunks, f)
    
    return vector_store_dir

@pytest.mark.parametrize("query_embedding,expected_indices", [
    ([0.1, 0.2, 0.3], [0, 1]),  # 最初のベクトルに近い
    ([0.4, 0.5, 0.6], [1, 0])   # 2番目のベクトルに近い
])
def test_compute_similarity(query_embedding, expected_indices):
    """類似度計算のテスト"""
    engine = RAGEngine()
    stored_embeddings = [
        [0.1, 0.2, 0.3],
        [0.4, 0.5, 0.6]
    ]
    
    similarities = engine._compute_similarity(query_embedding, stored_embeddings)
    assert len(similarities) == len(stored_embeddings)
    
    # 類似度の順序を確認
    sorted_indices = np.argsort(similarities)[::-1]
    assert list(sorted_indices) == expected_indices

def test_search(mock_ollama_client, sample_vector_store, monkeypatch):
    """検索機能のテスト"""
    # ベクトルストアのパスを一時ディレクトリに変更
    monkeypatch.setattr('src.core.rag_engine.VECTOR_STORE_DIR', sample_vector_store)
    
    # Embeddingの生成をモック
    mock_ollama_client.get_embeddings.return_value = [[0.1, 0.2, 0.3]]
    
    engine = RAGEngine(top_k=2)
    results = engine.search("test query")
    
    assert len(results) > 0
    assert 'text' in results[0]
    assert 'metadata' in results[0]
    assert 'similarity' in results[0]

def test_search_with_filter(mock_ollama_client, sample_vector_store, monkeypatch):
    """フィルタ付き検索のテスト"""
    monkeypatch.setattr('src.core.rag_engine.VECTOR_STORE_DIR', sample_vector_store)
    mock_ollama_client.get_embeddings.return_value = [[0.1, 0.2, 0.3]]
    
    engine = RAGEngine()
    results = engine.search(
        "test query",
        filter_criteria={'file_name': 'test1.pdf'}
    )
    
    assert all(r['metadata']['file_name'] == 'test1.pdf' for r in results)

def test_generate_response(mock_ollama_client, sample_vector_store, monkeypatch):
    """回答生成のテスト"""
    monkeypatch.setattr('src.core.rag_engine.VECTOR_STORE_DIR', sample_vector_store)
    
    # Embedding生成と回答生成をモック
    mock_ollama_client.get_embeddings.return_value = [[0.1, 0.2, 0.3]]
    mock_ollama_client.generate.return_value = "Test response"
    
    engine = RAGEngine()
    response, chunks = engine.generate_response("test query")
    
    assert response == "Test response"
    assert len(chunks) > 0
    assert mock_ollama_client.generate.called

def test_no_results_handling(mock_ollama_client, vector_store_dir, monkeypatch):
    """検索結果が無い場合のテスト"""
    monkeypatch.setattr('src.core.rag_engine.VECTOR_STORE_DIR', vector_store_dir)
    
    # 空のベクトルストアを作成
    vector_store_dir.mkdir(parents=True, exist_ok=True)
    with open(vector_store_dir / 'metadata.json', 'w') as f:
        json.dump({'processed_files': {}}, f)
    
    engine = RAGEngine()
    response, chunks = engine.generate_response("test query")
    
    assert "申し訳ありません" in response
    assert len(chunks) == 0

def test_get_stats(sample_vector_store, monkeypatch):
    """統計情報取得のテスト"""
    monkeypatch.setattr('src.core.rag_engine.VECTOR_STORE_DIR', sample_vector_store)
    
    engine = RAGEngine()
    stats = engine.get_stats()
    
    assert 'total_chunks' in stats
    assert 'total_documents' in stats
    assert 'embedding_model' in stats
    assert 'last_update' in stats