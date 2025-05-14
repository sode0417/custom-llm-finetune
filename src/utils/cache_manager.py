from typing import Dict, Any, Optional
from pathlib import Path
import json
import shutil
from datetime import datetime, timezone
import threading
import time

from src.utils.logger import logger

class CacheManager:
    """ファイルキャッシュを管理するクラス"""
    
    def __init__(
        self,
        cache_dir: Path,
        ttl_hours: int = 24,
        max_size_mb: int = 1024  # 1GB
    ):
        self.cache_dir = cache_dir
        self.ttl_hours = ttl_hours
        self.max_size_mb = max_size_mb
        self.manifest_path = cache_dir / "manifest.json"
        self.manifest: Dict[str, Any] = self._load_manifest()
        self.lock = threading.Lock()
        
        # キャッシュクリーンアップスレッドの開始
        self.cleanup_thread = threading.Thread(
            target=self._cleanup_worker,
            daemon=True
        )
        self.cleanup_thread.start()
    
    def _load_manifest(self) -> Dict[str, Any]:
        """マニフェストファイルをロード"""
        if self.manifest_path.exists():
            try:
                with open(self.manifest_path, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                logger.error("Manifest file is corrupted. Creating new one.")
                return self._create_new_manifest()
        return self._create_new_manifest()
    
    def _create_new_manifest(self) -> Dict[str, Any]:
        """新しいマニフェストを作成"""
        manifest = {
            'files': {},
            'last_cleanup': datetime.now(timezone.utc).isoformat(),
            'total_size': 0
        }
        self._save_manifest(manifest)
        return manifest
    
    def _save_manifest(self, manifest: Optional[Dict] = None) -> None:
        """マニフェストを保存"""
        with self.lock:
            manifest = manifest or self.manifest
            with open(self.manifest_path, 'w') as f:
                json.dump(manifest, f, indent=2)
    
    def has_valid_cache(self, file_id: str) -> bool:
        """キャッシュが有効かどうかを確認"""
        with self.lock:
            if file_id not in self.manifest['files']:
                return False
                
            cache_info = self.manifest['files'][file_id]
            cache_path = Path(cache_info['path'])
            
            if not cache_path.exists():
                return False
                
            # TTLチェック
            cache_time = datetime.fromisoformat(cache_info['timestamp'])
            age = datetime.now(timezone.utc) - cache_time
            return age.total_seconds() < self.ttl_hours * 3600
    
    def get_cache_path(self, file_id: str) -> Optional[Path]:
        """キャッシュファイルのパスを取得"""
        with self.lock:
            if not self.has_valid_cache(file_id):
                return None
            return Path(self.manifest['files'][file_id]['path'])
    
    def add_to_cache(
        self,
        file_id: str,
        file_path: Path,
        metadata: Optional[Dict] = None
    ) -> Path:
        """ファイルをキャッシュに追加"""
        with self.lock:
            # キャッシュディレクトリにコピー
            cache_path = self.cache_dir / file_path.name
            shutil.copy2(file_path, cache_path)
            
            # マニフェストを更新
            file_size = cache_path.stat().st_size
            self.manifest['files'][file_id] = {
                'path': str(cache_path),
                'size': file_size,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'metadata': metadata or {}
            }
            self.manifest['total_size'] = sum(
                f['size'] for f in self.manifest['files'].values()
            )
            
            self._save_manifest()
            
            # 容量制限チェック
            if self.manifest['total_size'] > self.max_size_mb * 1024 * 1024:
                self._cleanup_old_files()
                
            return cache_path
    
    def remove_from_cache(self, file_id: str) -> None:
        """ファイルをキャッシュから削除"""
        with self.lock:
            if file_id in self.manifest['files']:
                cache_info = self.manifest['files'][file_id]
                cache_path = Path(cache_info['path'])
                
                if cache_path.exists():
                    cache_path.unlink()
                
                del self.manifest['files'][file_id]
                self.manifest['total_size'] = sum(
                    f['size'] for f in self.manifest['files'].values()
                )
                self._save_manifest()
    
    def clear_cache(self) -> None:
        """キャッシュを完全にクリア"""
        with self.lock:
            # すべてのファイルを削除
            for cache_info in self.manifest['files'].values():
                cache_path = Path(cache_info['path'])
                if cache_path.exists():
                    cache_path.unlink()
            
            # マニフェストをリセット
            self.manifest = self._create_new_manifest()
            self._save_manifest()
    
    def _cleanup_old_files(self) -> None:
        """古いファイルを削除してキャッシュサイズを制限内に収める"""
        with self.lock:
            # ファイルを最終アクセス時刻でソート
            files = list(self.manifest['files'].items())
            files.sort(
                key=lambda x: datetime.fromisoformat(x[1]['timestamp'])
            )
            
            # 容量が制限を下回るまで古いファイルを削除
            while (self.manifest['total_size'] > self.max_size_mb * 1024 * 1024
                   and files):
                file_id, cache_info = files.pop(0)
                self.remove_from_cache(file_id)
    
    def _cleanup_worker(self) -> None:
        """定期的にキャッシュのクリーンアップを実行"""
        while True:
            try:
                # 無効なキャッシュを削除
                current_time = datetime.now(timezone.utc)
                with self.lock:
                    for file_id in list(self.manifest['files'].keys()):
                        if not self.has_valid_cache(file_id):
                            self.remove_from_cache(file_id)
                    
                    # 最後のクリーンアップから24時間経過していたら容量チェック
                    last_cleanup = datetime.fromisoformat(
                        self.manifest['last_cleanup']
                    )
                    if (current_time - last_cleanup).total_seconds() >= 86400:
                        self._cleanup_old_files()
                        self.manifest['last_cleanup'] = current_time.isoformat()
                        self._save_manifest()
                
            except Exception as e:
                logger.error(f"Cache cleanup error: {e}")
            
            # 1時間待機
            time.sleep(3600)