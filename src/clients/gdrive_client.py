from typing import List, Dict, Optional, Any
from pathlib import Path
from datetime import datetime, timezone
import json
import io
import time
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.auth.exceptions import RefreshError

from src.utils.cache_manager import CacheManager
from src.utils.drive_watcher import DriveWatcher
from src.utils.logger import logger
from config.settings import (
    GOOGLE_CREDENTIALS_FILE,
    GOOGLE_TOKEN_FILE,
    PDF_CACHE_DIR,
    GOOGLE_DRIVE_FOLDER_ID
)

class GoogleDriveError(Exception):
    """Google Drive関連の基本例外クラス"""
    pass

class AuthenticationError(GoogleDriveError):
    """認証関連のエラー"""
    pass

class FileOperationError(GoogleDriveError):
    """ファイル操作関連のエラー"""
    pass

class GoogleDriveClient:
    """Google Drive APIとの連携を管理するクライアント"""
    
    # APIで必要なスコープを定義
    SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
    
    def __init__(
        self,
        credentials_file: str = GOOGLE_CREDENTIALS_FILE,
        token_file: str = GOOGLE_TOKEN_FILE,
        cache_ttl_hours: int = 24
    ):
        self.credentials_file = credentials_file
        self.token_file = token_file
        
        # 認証情報の取得
        self.creds = self._get_credentials()
        self.service = build('drive', 'v3', credentials=self.creds)
        
        # キャッシュマネージャーの初期化
        self.cache_manager = CacheManager(
            PDF_CACHE_DIR,
            ttl_hours=cache_ttl_hours
        )
        
        # ファイル監視の初期化（必要に応じて）
        self.watcher: Optional[DriveWatcher] = None
    
    def _get_credentials(self) -> Credentials:
        """認証情報を取得または更新"""
        creds = None
        token_path = Path(self.token_file)
        
        try:
            # 既存のトークンをロード
            if token_path.exists():
                creds = Credentials.from_authorized_user_file(
                    str(token_path),
                    self.SCOPES
                )
        except Exception as e:
            logger.warning(f"Failed to load existing token: {e}")
            creds = None
        
        # 有効な認証情報がない場合は新規取得
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except RefreshError as e:
                    logger.error(f"Failed to refresh token: {e}")
                    creds = None
                except Exception as e:
                    logger.error(f"Unexpected error during token refresh: {e}")
                    creds = None
            
            if not creds:
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_file,
                        self.SCOPES
                    )
                    creds = flow.run_local_server(port=0)
                except Exception as e:
                    logger.error(f"Failed to get new credentials: {e}")
                    raise AuthenticationError(
                        "Failed to authenticate with Google Drive"
                    ) from e
            
            # トークンを保存
            token_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                with open(token_path, 'w') as token:
                    token.write(creds.to_json())
            except Exception as e:
                logger.error(f"Failed to save token: {e}")
        
        return creds
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(
            (ConnectionError, TimeoutError)
        )
    )
    def list_pdf_files(
        self,
        folder_id: Optional[str] = None,
        recursive: bool = False
    ) -> List[Dict[str, Any]]:
        """指定フォルダ内のPDFファイル一覧を取得"""
        folder_id = folder_id or GOOGLE_DRIVE_FOLDER_ID
        if not folder_id:
            raise ValueError("Folder ID is required")
            
        try:
            # クエリの構築
            query = f"'{folder_id}' in parents and mimeType='application/pdf'"
            if recursive:
                query = (
                    f"('{folder_id}' in parents or "
                    f"'{folder_id}' in ancestors) and "
                    "mimeType='application/pdf'"
                )
            
            # ファイル一覧を取得
            files = []
            page_token = None
            while True:
                results = self.service.files().list(
                    q=query,
                    spaces='drive',
                    fields='nextPageToken, files(id, name, modifiedTime, size)',
                    pageToken=page_token
                ).execute()
                
                files.extend(results.get('files', []))
                page_token = results.get('nextPageToken')
                if not page_token:
                    break
            
            logger.info(f"Found {len(files)} PDF files in folder {folder_id}")
            return files
            
        except Exception as e:
            logger.error(f"Failed to list PDF files: {e}")
            raise FileOperationError(f"Failed to list files: {str(e)}") from e
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(
            (ConnectionError, TimeoutError)
        )
    )
    def download_file(self, file_id: str, file_name: str) -> Path:
        """ファイルをダウンロードしてキャッシュに保存"""
        # キャッシュをチェック
        if self.cache_manager.has_valid_cache(file_id):
            cache_path = self.cache_manager.get_cache_path(file_id)
            logger.info(f"Using cached file: {file_name}")
            return cache_path
        
        try:
            # ファイルをダウンロード
            request = self.service.files().get_media(fileId=file_id)
            file_handle = io.BytesIO()
            downloader = MediaIoBaseDownload(file_handle, request)
            
            done = False
            while not done:
                _, done = downloader.next_chunk()
            
            # 一時ファイルに保存
            temp_path = PDF_CACHE_DIR / f"temp_{file_name}"
            with open(temp_path, 'wb') as f:
                f.write(file_handle.getvalue())
            
            # キャッシュに追加
            cache_path = self.cache_manager.add_to_cache(
                file_id,
                temp_path,
                {'name': file_name}
            )
            
            # 一時ファイルを削除
            temp_path.unlink()
            
            logger.info(f"Downloaded and cached file: {file_name}")
            return cache_path
            
        except Exception as e:
            logger.error(f"Failed to download file {file_name}: {e}")
            raise FileOperationError(
                f"Failed to download file: {str(e)}"
            ) from e
    
    def start_watching(
        self,
        folder_id: Optional[str] = None,
        check_interval: int = 300
    ) -> None:
        """フォルダの監視を開始"""
        if not self.watcher:
            self.watcher = DriveWatcher(
                folder_id or GOOGLE_DRIVE_FOLDER_ID,
                check_interval=check_interval,
                cache_ttl=self.cache_manager.ttl_hours
            )
        self.watcher.start()
    
    def stop_watching(self) -> None:
        """フォルダの監視を停止"""
        if self.watcher:
            self.watcher.stop()
    
    def clear_cache(self) -> None:
        """キャッシュをクリア"""
        self.cache_manager.clear_cache()
        logger.info("Cache cleared successfully")
    
    def get_cached_files(self) -> List[Dict[str, Any]]:
        """キャッシュされているファイルの一覧を取得"""
        if self.watcher:
            return self.watcher.get_cached_files()
        return []
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop_watching()