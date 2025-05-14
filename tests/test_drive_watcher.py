import pytest
from unittest.mock import Mock, patch
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
import time

from src.utils.drive_watcher import DriveWatcher
from src.utils.cache_manager import CacheManager

@pytest.fixture
def mock_gdrive_client():
    """GoogleDriveClientのモック"""
    with patch('src.utils.drive_watcher.GoogleDriveClient') as mock:
        client = Mock()
        mock.return_value = client
        yield client

@pytest.fixture
def mock_cache_manager(tmp_path):
    """CacheManagerのモック"""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return CacheManager(cache_dir)

@pytest.fixture
def watcher(mock_gdrive_client, mock_cache_manager, tmp_path):
    """テスト用のDriveWatcher"""
    watcher = DriveWatcher(
        folder_id="test_folder",
        check_interval=1,  # テスト用に短い間隔
        cache_ttl=1
    )
    watcher.cache_manager = mock_cache_manager
    return watcher

def create_mock_file(file_id: str, name: str, modified_time: datetime):
    """モックファイルデータを作成"""
    return {
        'id': file_id,
        'name': name,
        'modifiedTime': modified_time.isoformat() + 'Z'
    }

def test_watcher_initialization(watcher, tmp_path):
    """初期化のテスト"""
    assert watcher.folder_id == "test_folder"
    assert watcher.check_interval == 1
    assert watcher.cache_ttl == 1
    assert not watcher.running
    assert isinstance(watcher.known_files, dict)

def test_load_save_state(watcher, tmp_path):
    """状態の保存と読み込みのテスト"""
    # 状態を設定
    test_time = datetime.now(timezone.utc)
    test_files = {
        'file1': {
            'name': 'test.pdf',
            'modifiedTime': test_time.isoformat(),
            'path': '/test/path'
        }
    }
    watcher.last_check = test_time
    watcher.known_files = test_files
    
    # 状態を保存
    watcher._save_state()
    
    # 新しいウォッチャーで読み込み
    new_watcher = DriveWatcher(folder_id="test_folder")
    new_watcher._load_state()
    
    assert new_watcher.last_check.isoformat() == test_time.isoformat()
    assert new_watcher.known_files == test_files

def test_check_updates_new_file(watcher, mock_gdrive_client):
    """新規ファイル検出のテスト"""
    # モックの設定
    current_time = datetime.now(timezone.utc)
    mock_file = create_mock_file(
        'file1',
        'test.pdf',
        current_time
    )
    mock_gdrive_client.list_pdf_files.return_value = [mock_file]
    
    # 更新チェック
    watcher._check_updates()
    
    # 新規ファイルが処理されたことを確認
    assert 'file1' in watcher.known_files
    assert mock_gdrive_client.download_file.called

def test_check_updates_modified_file(watcher, mock_gdrive_client):
    """ファイル更新の検出テスト"""
    # 既知のファイルを設定
    old_time = datetime.now(timezone.utc) - timedelta(hours=1)
    watcher.known_files = {
        'file1': {
            'name': 'test.pdf',
            'modifiedTime': old_time.isoformat() + 'Z',
            'path': '/test/path'
        }
    }
    
    # 更新されたファイルのモック
    new_time = datetime.now(timezone.utc)
    mock_file = create_mock_file(
        'file1',
        'test.pdf',
        new_time
    )
    mock_gdrive_client.list_pdf_files.return_value = [mock_file]
    
    # 更新チェック
    watcher._check_updates()
    
    # ファイルが更新されたことを確認
    assert watcher.known_files['file1']['modifiedTime'] == new_time.isoformat() + 'Z'
    assert mock_gdrive_client.download_file.called

def test_check_updates_deleted_file(watcher, mock_gdrive_client):
    """ファイル削除の検出テスト"""
    # 既知のファイルを設定
    watcher.known_files = {
        'file1': {
            'name': 'test.pdf',
            'modifiedTime': datetime.now(timezone.utc).isoformat() + 'Z',
            'path': '/test/path'
        }
    }
    
    # 空のファイルリストを返すようにモック設定
    mock_gdrive_client.list_pdf_files.return_value = []
    
    # 更新チェック
    watcher._check_updates()
    
    # ファイルが削除されたことを確認
    assert 'file1' not in watcher.known_files

def test_watch_loop(watcher, mock_gdrive_client):
    """監視ループのテスト"""
    # モックの設定
    mock_file = create_mock_file(
        'file1',
        'test.pdf',
        datetime.now(timezone.utc)
    )
    mock_gdrive_client.list_pdf_files.return_value = [mock_file]
    
    # 監視を開始
    watcher.start()
    
    # 数秒待機して更新が行われることを確認
    time.sleep(2)
    
    # 監視を停止
    watcher.stop()
    
    # 更新が行われたことを確認
    assert mock_gdrive_client.list_pdf_files.called
    assert 'file1' in watcher.known_files

def test_error_handling(watcher, mock_gdrive_client):
    """エラーハンドリングのテスト"""
    # エラーを発生させるようにモック設定
    mock_gdrive_client.list_pdf_files.side_effect = Exception("Test error")
    
    # 更新チェック
    watcher._check_updates()
    
    # エラーが適切に処理され、プロセスが継続することを確認
    assert watcher.last_check is None
    
    # エラー後も監視が継続できることを確認
    mock_gdrive_client.list_pdf_files.side_effect = None
    mock_file = create_mock_file(
        'file1',
        'test.pdf',
        datetime.now(timezone.utc)
    )
    mock_gdrive_client.list_pdf_files.return_value = [mock_file]
    
    watcher._check_updates()
    assert 'file1' in watcher.known_files

def test_get_cached_files(watcher):
    """キャッシュされたファイル一覧取得のテスト"""
    # テストデータを設定
    test_time = datetime.now(timezone.utc)
    watcher.known_files = {
        'file1': {
            'name': 'test1.pdf',
            'modifiedTime': test_time.isoformat(),
            'path': '/test/path1'
        },
        'file2': {
            'name': 'test2.pdf',
            'modifiedTime': test_time.isoformat(),
            'path': '/test/path2'
        }
    }
    
    # ファイル一覧を取得
    files = watcher.get_cached_files()
    
    # 結果を確認
    assert len(files) == 2
    assert files[0]['name'] in ['test1.pdf', 'test2.pdf']
    assert files[1]['name'] in ['test1.pdf', 'test2.pdf']
    assert files[0]['name'] != files[1]['name']