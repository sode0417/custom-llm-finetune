import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import json
import datetime
from google.oauth2.credentials import Credentials

from src.clients.gdrive_client import GoogleDriveClient

@pytest.fixture
def mock_credentials():
    """認証情報のモック"""
    creds = Mock(spec=Credentials)
    creds.valid = True
    creds.expired = False
    return creds

@pytest.fixture
def mock_drive_service():
    """Drive APIサービスのモック"""
    service = MagicMock()
    return service

@pytest.fixture
def mock_client(mock_credentials, mock_drive_service, pdf_cache_dir):
    """GoogleDriveClientのモック"""
    with patch('src.clients.gdrive_client.build') as mock_build:
        mock_build.return_value = mock_drive_service
        
        client = GoogleDriveClient()
        client.creds = mock_credentials
        client.service = mock_drive_service
        client.cache_dir = pdf_cache_dir
        
        return client

def test_credentials_refresh(temp_dir, monkeypatch):
    """認証情報の更新テスト"""
    # 環境変数のパスを一時ディレクトリに変更
    monkeypatch.setattr(
        'src.clients.gdrive_client.GOOGLE_TOKEN_FILE',
        str(temp_dir / 'token.json')
    )
    monkeypatch.setattr(
        'src.clients.gdrive_client.GOOGLE_CREDENTIALS_FILE',
        str(temp_dir / 'credentials.json')
    )
    
    with patch('src.clients.gdrive_client.Credentials') as mock_creds:
        # 期限切れの認証情報をシミュレート
        instance = Mock()
        instance.valid = False
        instance.expired = True
        instance.refresh_token = True
        mock_creds.from_authorized_user_file.return_value = instance
        
        client = GoogleDriveClient()
        
        # refresh()が呼ばれたことを確認
        assert instance.refresh.called

def test_list_pdf_files(mock_client):
    """PDFファイル一覧取得のテスト"""
    # APIレスポンスのモック
    mock_response = {
        'files': [
            {
                'id': 'file1',
                'name': 'test1.pdf',
                'modifiedTime': '2025-05-14T12:00:00Z'
            },
            {
                'id': 'file2',
                'name': 'test2.pdf',
                'modifiedTime': '2025-05-14T13:00:00Z'
            }
        ]
    }
    
    # files().list()の呼び出しをモック
    mock_client.service.files.return_value.list.return_value.execute\
        .return_value = mock_response
    
    files = mock_client.list_pdf_files('test_folder')
    
    assert len(files) == 2
    assert files[0]['name'] == 'test1.pdf'
    assert files[1]['name'] == 'test2.pdf'

def test_download_file(mock_client, pdf_cache_dir):
    """ファイルダウンロードのテスト"""
    file_id = 'test_file_id'
    file_name = 'test.pdf'
    
    # ファイルダウンロードのモック
    mock_request = Mock()
    mock_client.service.files.return_value.get_media.return_value = mock_request
    
    # MediaIoBaseDownloadのモック
    with patch('src.clients.gdrive_client.MediaIoBaseDownload') as mock_downloader:
        mock_downloader.return_value.next_chunk.return_value = (None, True)
        
        # ファイルをダウンロード
        result = mock_client.download_file(file_id, file_name)
        
        assert result == pdf_cache_dir / file_name
        assert result.exists()

def test_cache_management(mock_client, pdf_cache_dir):
    """キャッシュ管理のテスト"""
    # キャッシュマニフェストを作成
    cache_data = {
        'test_file_id': {
            'path': str(pdf_cache_dir / 'test.pdf'),
            'timestamp': datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat()
        }
    }
    mock_client.cache_manifest = cache_data
    
    # キャッシュの有効性チェック
    assert mock_client._is_cache_valid('test_file_id', max_age_hours=1)
    
    # 古いタイムスタンプでテスト
    old_time = datetime.datetime.now(datetime.timezone.utc) - \
               datetime.timedelta(hours=2)
    cache_data['test_file_id']['timestamp'] = old_time.isoformat()
    assert not mock_client._is_cache_valid('test_file_id', max_age_hours=1)

def test_clear_cache(mock_client, pdf_cache_dir):
    """キャッシュクリアのテスト"""
    # テストファイルを作成
    test_file = pdf_cache_dir / 'test.pdf'
    test_file.write_text('test content')
    
    mock_client.cache_manifest = {
        'test_file_id': {
            'path': str(test_file),
            'timestamp': datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat()
        }
    }
    
    # キャッシュをクリア
    mock_client.clear_cache()
    
    assert not test_file.exists()
    assert len(mock_client.cache_manifest) == 0

def test_error_handling(mock_client):
    """エラーハンドリングのテスト"""
    # APIエラーをシミュレート
    mock_client.service.files.return_value.list.return_value.execute\
        .side_effect = Exception('API Error')
    
    with pytest.raises(Exception):
        mock_client.list_pdf_files('test_folder')