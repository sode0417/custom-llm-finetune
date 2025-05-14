import pytest
import asyncio
from pathlib import Path
import time
from typing import List, Dict
import json

from src.core.document_processor import DocumentProcessor
from src.core.rag_engine import RAGEngine
from src.utils.pdf_processor import TextChunk
from src.utils.drive_watcher import DriveWatcher

# テスト用のPDFファイルパス
SAMPLE_PDF = Path(__file__).parent / "data" / "sample.pdf"

@pytest.fixture
def sample_chunks() -> List[TextChunk]:
    """テスト用のチャンク"""
    return [
        TextChunk(
            text="This is a test document about AI technology.",
            metadata={
                "source": "test1.pdf",
                "page": 1
            }
        ),
        TextChunk(
            text="Machine learning is transforming various industries.",
            metadata={
                "source": "test1.pdf",
                "page": 1
            }
        ),
        TextChunk(
            text="Neural networks are inspired by biological brains.",
            metadata={
                "source": "test2.pdf",
                "page": 1
            }
        )
    ]

@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_pipeline(tmp_path, mock_gdrive_client, mock_ollama_client):
    """完全なパイプラインのテスト"""
    # セットアップ
    processor = DocumentProcessor()
    rag_engine = RAGEngine()
    
    # PDFファイルの処理をシミュレート
    mock_gdrive_client.list_pdf_files.return_value = [
        {'id': 'test1', 'name': 'test1.pdf'}
    ]
    mock_gdrive_client.download_file.return_value = SAMPLE_PDF
    
    mock_ollama_client.get_embeddings.return_value = [
        [0.1, 0.2, 0.3] for _ in range(3)
    ]
    mock_ollama_client.generate.return_value = "Test response"
    
    # 文書の処理
    await processor.process_drive_folder()
    
    # 質問応答のテスト
    result = await rag_engine.process_query(
        "What is AI technology?"
    )
    
    assert result.text == "Test response"
    assert len(result.sources) > 0
    assert result.confidence > 0

@pytest.mark.integration
@pytest.mark.asyncio
async def test_cache_and_watch(tmp_path, mock_gdrive_client):
    """キャッシュと変更監視のテスト"""
    # セットアップ
    watcher = DriveWatcher(check_interval=1)
    
    # ファイルの追加をシミュレート
    mock_gdrive_client.list_pdf_files.return_value = [
        {'id': 'test1', 'name': 'test1.pdf', 'modifiedTime': '2025-05-15T00:00:00Z'}
    ]
    
    # 監視を開始
    watcher.start()
    
    # 変更を待機
    await asyncio.sleep(2)
    
    # ファイルの更新をシミュレート
    mock_gdrive_client.list_pdf_files.return_value = [
        {'id': 'test1', 'name': 'test1.pdf', 'modifiedTime': '2025-05-15T00:01:00Z'}
    ]
    
    await asyncio.sleep(2)
    
    # 監視を停止
    watcher.stop()
    
    # キャッシュの状態を確認
    cached_files = watcher.get_cached_files()
    assert len(cached_files) == 1
    assert cached_files[0]['id'] == 'test1'

@pytest.mark.integration
@pytest.mark.asyncio
async def test_error_recovery(mock_gdrive_client, mock_ollama_client):
    """エラーからの回復テスト"""
    processor = DocumentProcessor()
    
    # 最初の試行でエラーを発生させる
    mock_gdrive_client.list_pdf_files.side_effect = [
        Exception("API Error"),
        [{'id': 'test1', 'name': 'test1.pdf'}]
    ]
    
    # エラーが発生しても処理が継続することを確認
    await processor.process_drive_folder()
    
    # 2回目の呼び出しが成功することを確認
    info = processor.get_document_info()
    assert 'test1.pdf' in str(info)

@pytest.mark.integration
@pytest.mark.asyncio
async def test_concurrent_processing(
    mock_gdrive_client,
    mock_ollama_client,
    sample_chunks
):
    """並行処理のテスト"""
    processor = DocumentProcessor()
    rag_engine = RAGEngine()
    
    # 複数のファイルを同時に処理
    mock_gdrive_client.list_pdf_files.return_value = [
        {'id': f'test{i}', 'name': f'test{i}.pdf'}
        for i in range(3)
    ]
    
    # Embeddingの生成をシミュレート
    mock_ollama_client.get_embeddings.return_value = [
        [0.1, 0.2, 0.3] for _ in range(len(sample_chunks))
    ]
    
    # 並行してクエリを処理
    queries = ["What is AI?", "Explain ML", "Define neural networks"]
    tasks = [
        rag_engine.process_query(query)
        for query in queries
    ]
    
    results = await asyncio.gather(*tasks)
    assert len(results) == len(queries)

@pytest.mark.integration
@pytest.mark.benchmark
async def test_performance(mock_gdrive_client, mock_ollama_client, sample_chunks):
    """パフォーマンステスト"""
    processor = DocumentProcessor()
    rag_engine = RAGEngine()
    
    # 大量のファイルを処理
    file_count = 10
    mock_gdrive_client.list_pdf_files.return_value = [
        {'id': f'test{i}', 'name': f'test{i}.pdf'}
        for i in range(file_count)
    ]
    
    # 処理時間を計測
    start_time = time.time()
    await processor.process_drive_folder()
    processing_time = time.time() - start_time
    
    # クエリのレイテンシを計測
    query_times = []
    for _ in range(5):
        start_time = time.time()
        await rag_engine.process_query("test query")
        query_times.append(time.time() - start_time)
    
    avg_query_time = sum(query_times) / len(query_times)
    
    # 結果をログに記録
    logger.info(
        f"Performance metrics:\n"
        f"Processing time: {processing_time:.2f}s\n"
        f"Average query time: {avg_query_time:.2f}s"
    )

@pytest.mark.integration
async def test_context_relevance(mock_ollama_client, sample_chunks):
    """コンテキストの関連性テスト"""
    rag_engine = RAGEngine()
    
    # Embeddingの生成をシミュレート
    mock_ollama_client.get_embeddings.return_value = [
        [0.1, 0.2, 0.3] for _ in range(len(sample_chunks))
    ]
    
    # 関連性の高いクエリと低いクエリをテスト
    relevant_query = "What is artificial intelligence?"
    irrelevant_query = "What is the weather like today?"
    
    relevant_result = await rag_engine.process_query(relevant_query)
    irrelevant_result = await rag_engine.process_query(irrelevant_query)
    
    # 関連性スコアを比較
    assert relevant_result.confidence > irrelevant_result.confidence