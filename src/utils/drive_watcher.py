from typing import Dict, Any, Optional, List, Set
from pathlib import Path
import threading
import time
from datetime import datetime, timezone
import json

from src.clients.gdrive_client import GoogleDriveClient
from src.utils.cache_manager import CacheManager
from src.utils.logger import logger
from config.settings import (
    GOOGLE_DRIVE_FOLDER_ID,
    PDF_CACHE_DIR
)

class DriveWatcher:
    """Google Driveフォルダの変更を監視するクラス"""
    
    def __init__(
        self,
        folder_id: str = GOOGLE_DRIVE_FOLDER_ID,
        check_interval: int = 300,  # 5分
        cache_ttl: int = 24  # 24時間
    ):
        self.folder_id = folder_id
        self.check_interval = check_interval
        self.cache_ttl = cache_ttl
        
        self.gdrive_client = GoogleDriveClient()
        self.cache_manager = CacheManager(
            PDF_CACHE_DIR,
            ttl_hours=cache_ttl
        )
        
        self.last_check: Optional[datetime] = None
        self.known_files: Dict[str, Dict[str, Any]] = {}
        self.running = False
        self.lock = threading.Lock()
        
        # 状態ファイルの読み込み
        self.state_file = PDF_CACHE_DIR / "watcher_state.json"
        self._load_state()
    
    def _load_state(self) -> None:
        """監視状態を読み込む"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    self.last_check = datetime.fromisoformat(
                        state.get('last_check', '')
                    )
                    self.known_files = state.get('known_files', {})
            except Exception as e:
                logger.error(f"Failed to load watcher state: {e}")
                self.last_check = None
                self.known_files = {}
    
    def _save_state(self) -> None:
        """監視状態を保存"""
        with self.lock:
            state = {
                'last_check': self.last_check.isoformat() if self.last_check else None,
                'known_files': self.known_files
            }
            try:
                with open(self.state_file, 'w') as f:
                    json.dump(state, f, indent=2)
            except Exception as e:
                logger.error(f"Failed to save watcher state: {e}")
    
    def _check_updates(self) -> None:
        """フォルダ内のファイル変更を確認"""
        try:
            # フォルダ内のPDFファイル一覧を取得
            current_files = self.gdrive_client.list_pdf_files(self.folder_id)
            current_time = datetime.now(timezone.utc)
            
            # ファイルの変更を確認
            with self.lock:
                # 新規・更新ファイルの確認
                for file in current_files:
                    file_id = file['id']
                    modified_time = datetime.fromisoformat(
                        file['modifiedTime'].rstrip('Z')
                    ).replace(tzinfo=timezone.utc)
                    
                    if file_id not in self.known_files:
                        # 新規ファイル
                        logger.info(f"New file detected: {file['name']}")
                        self._process_file(file)
                        
                    elif modified_time > datetime.fromisoformat(
                        self.known_files[file_id]['modifiedTime']
                    ):
                        # 更新されたファイル
                        logger.info(f"File updated: {file['name']}")
                        self._process_file(file)
                
                # 削除されたファイルの確認
                current_ids = {f['id'] for f in current_files}
                for file_id in list(self.known_files.keys()):
                    if file_id not in current_ids:
                        logger.info(
                            f"File removed: {self.known_files[file_id]['name']}"
                        )
                        self.cache_manager.remove_from_cache(file_id)
                        del self.known_files[file_id]
                
                self.last_check = current_time
                self._save_state()
                
        except Exception as e:
            logger.error(f"Failed to check updates: {e}")
    
    def _process_file(self, file: Dict[str, Any]) -> None:
        """ファイルを処理"""
        file_id = file['id']
        file_name = file['name']
        
        try:
            # ファイルをダウンロード
            cache_path = self.gdrive_client.download_file(file_id, file_name)
            
            # 処理が成功したらknown_filesを更新
            self.known_files[file_id] = {
                'name': file_name,
                'modifiedTime': file['modifiedTime'],
                'path': str(cache_path)
            }
            
        except Exception as e:
            logger.error(f"Failed to process file {file_name}: {e}")
    
    def start(self) -> None:
        """監視を開始"""
        if self.running:
            return
            
        self.running = True
        threading.Thread(target=self._watch_loop, daemon=True).start()
        logger.info(
            f"Started watching Google Drive folder: {self.folder_id}"
        )
    
    def stop(self) -> None:
        """監視を停止"""
        self.running = False
        self._save_state()
        logger.info("Stopped Google Drive watcher")
    
    def _watch_loop(self) -> None:
        """監視ループ"""
        while self.running:
            self._check_updates()
            time.sleep(self.check_interval)
    
    def get_cached_files(self) -> List[Dict[str, Any]]:
        """キャッシュされているファイルの一覧を取得"""
        with self.lock:
            return [
                {
                    'id': file_id,
                    'name': info['name'],
                    'path': info['path'],
                    'modified': info['modifiedTime']
                }
                for file_id, info in self.known_files.items()
            ]
    
    def get_file_info(self, file_id: str) -> Optional[Dict[str, Any]]:
        """特定のファイルの情報を取得"""
        with self.lock:
            return self.known_files.get(file_id)