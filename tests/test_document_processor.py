import pytest
from unittest.mock import Mock, patch, call
from pathlib import Path
import json
from datetime import datetime, timezone
from queue import Queue

from src.core.document_processor import DocumentProcessor, ProcessingProgress
from src.utils.pdf_processor import TextChunk

@pytest.fixture
def mock_gdrive_client():
    """GoogleDriveClientのモック"""
    with patch('src.core.document_processor.GoogleDriveClient') as mock:
        client = Mock()
        mock.return_value = client
        yield client

@pytest.fixture
def mock_ollama_client():
    """OllamaClientのモック"""
    with patch('src.core.document_processor.OllamaClient') as mock:
        client = Mock()
        mock.return_value = client
        yield client

@pytest.fixture
def mock_pdf_processor():
    """PDFProcessorのモック"""
    with patch('src.core.document_processor.PDFProcessor') as mock:
        processor = Mock()
        mock.return_value = processor
        yield processor

@pytest.fixture
def document_processor(
    mock_gdrive_client,
    mock_ollama_client,
    mock_pdf_processor,
    tmp_path
):
    """テスト用のDocumentProcessor"""
    # 一時ディレクトリを設定
    with patch('src.core.document_processor.VECTOR_STORE_DIR', tmp_path):
        processor = DocumentProcessor()
        return processor

def create_test_chunks():
    """テスト用のチャンクを作成"""
    return [
        TextChunk(
            text="Test content 1",
            metadata={"page": 1}
        ),
        TextChunk(
            text="Test content 2",
            metadata={"page": 2}
        )
    ]

def test_processor_initialization(document_processor):
    """初期化のテスト"""
    assert document_processor.metadata['processed_files'] == {}
    assert document_processor.metadata['embedding_model'] is not None
    assert isinstance(document_processor.processing_queue, Queue)

def test_process_drive_folder(
    document_processor,
    mock_gdrive_client,
    mock_ollama_client,
    mock_pdf_processor
):
    """フォルダ処理の基本機能テスト"""
    # モックの設定
    test_files = [
        {'id': 'file1', 'name': 'test1.pdf'},
        {'id': 'file2', 'name': 'test2.pdf'}
    ]
    mock_gdrive_client.list_pdf_files.return_value = test_files
    mock_gdrive_client.download_file.return_value = Path("test.pdf")
    
    test_chunks = create_test_chunks()
    mock_pdf_processor.process_pdf.return_value = test_chunks
    
    test_embeddings = [[0.1, 0.2], [0.3, 0.4]]
    mock_ollama_client.get_embeddings.return_value = test_embeddings
    
    # フォルダを処理
    document_processor.process_drive_folder()
    
    # 各ファイルが処理されたことを確認
    assert mock_gdrive_client.download_file.call_count == 2
    assert mock_pdf_processor.process_pdf.call_count == 2
    assert mock_ollama_client.get_embeddings.call_count == 2
    
    # メタデータが更新されたことを確認
    assert len(document_processor.metadata['processed_files']) == 2

def test_progress_callback(document_processor, mock_gdrive_client):
    """進捗通知のテスト"""
    # コールバックのモック
    progress_callback = Mock()
    document_processor.progress_callback = progress_callback
    
    # テストファイルの設定
    test_files = [
        {'id': 'file1', 'name': 'test1.pdf'},
        {'id': 'file2', 'name': 'test2.pdf'}
    ]
    mock_gdrive_client.list_pdf_files.return_value = test_files
    
    # 処理を実行
    document_processor.process_drive_folder()
    
    # コールバックが適切に呼ばれたことを確認
    assert progress_callback.call_count > 0
    
    # 進捗状態の検証
    calls = progress_callback.call_args_list
    
    # 初期化時の呼び出し
    assert calls[0][0][0].total_files == 2
    assert calls[0][0][0].processed_files == 0
    assert calls[0][0][0].status == "initializing"
    
    # 完了時の呼び出し
    final_call = calls[-1][0][0]
    assert final_call.status in ["completed", "error"]

def test_watch_for_changes(document_processor):
    """変更監視機能のテスト"""
    # 監視機能付きで初期化
    processor = DocumentProcessor(watch_for_changes=True)
    assert processor.watcher is not None
    
    # 監視が開始されることを確認
    with processor:
        assert processor.watcher.running
    
    # 終了時に監視が停止することを確認
    assert not processor.watcher.running

def test_error_handling(document_processor, mock_gdrive_client):
    """エラーハンドリングのテスト"""
    # エラーを発生させる設定
    mock_gdrive_client.list_pdf_files.side_effect = Exception("Test error")
    
    # プログレスコールバックのモック
    progress_callback = Mock()
    document_processor.progress_callback = progress_callback
    
    # エラーが発生することを確認
    with pytest.raises(Exception):
        document_processor.process_drive_folder()
    
    # エラー状態が通知されることを確認
    last_progress = progress_callback.call_args[0][0]
    assert last_progress.status == "error"
    assert last_progress.error == "Test error"

def test_queue_processing(document_processor):
    """処理キューのテスト"""
    # キューにファイルを追加
    test_files = [
        {'id': 'file1', 'name': 'test1.pdf'},
        {'id': 'file2', 'name': 'test2.pdf'}
    ]
    
    for file in test_files:
        document_processor.processing_queue.put(file)
    
    # キュー処理を開始
    with patch.object(document_processor, 'process_drive_folder') as mock_process:
        document_processor._process_queue()
        
        # 各ファイルが処理されたことを確認
        assert mock_process.call_count == 2
        assert document_processor.processing_queue.empty()

def test_metadata_management(document_processor, tmp_path):
    """メタデータ管理のテスト"""
    # テストメタデータを作成
    test_metadata = {
        'processed_files': {
            'file1': {
                'file_name': 'test1.pdf',
                'chunk_count': 2,
                'processed_at': datetime.now(timezone.utc).isoformat()
            }
        },
        'last_update': datetime.now(timezone.utc).isoformat(),
        'embedding_model': 'test-model'
    }
    
    # メタデータを保存
    document_processor.metadata = test_metadata
    document_processor._save_metadata()
    
    # 新しいプロセッサーでメタデータを読み込み
    new_processor = DocumentProcessor()
    assert new_processor.metadata['processed_files']['file1']['file_name'] == 'test1.pdf'
    
    # ドキュメント情報の取得をテスト
    info = new_processor.get_document_info()
    assert info['total_documents'] == 1
    assert info['embedding_model'] == 'test-model'