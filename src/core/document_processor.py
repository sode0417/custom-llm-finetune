from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
import json
from datetime import datetime
import threading
from queue import Queue
from dataclasses import dataclass

from config.settings import (
    VECTOR_STORE_DIR,
    OLLAMA_MODELS,
    PDF_CACHE_DIR,
    GOOGLE_DRIVE_FOLDER_ID
)
from src.clients.gdrive_client import GoogleDriveClient
from src.clients.ollama_client import OllamaClient
from src.utils.pdf_processor import PDFProcessor, TextChunk
from src.utils.drive_watcher import DriveWatcher
from src.utils.logger import logger

@dataclass
class ProcessingProgress:
    """処理の進捗状況を表すデータクラス"""
    total_files: int
    processed_files: int
    current_file: Optional[str]
    status: str
    error: Optional[str] = None

class DocumentProcessor:
    """ドキュメント処理の全体的な流れを管理するクラス"""
    
    def __init__(
        self,
        watch_for_changes: bool = False,
        progress_callback: Optional[Callable[[ProcessingProgress], None]] = None
    ):
        self.gdrive_client = GoogleDriveClient()
        self.ollama_client = OllamaClient()
        self.pdf_processor = PDFProcessor()
        self.watcher = None if not watch_for_changes else DriveWatcher()
        self.progress_callback = progress_callback
        
        # 処理キューの初期化
        self.processing_queue = Queue()
        self.processing_thread = None
        self.is_processing = False
        
        # ベクトルストアのメタデータを保持するファイル
        self.metadata_file = VECTOR_STORE_DIR / 'metadata.json'
        self.metadata = self._load_metadata()
        
        # 変更監視を有効化
        if watch_for_changes:
            self._start_watching()
    
    def _load_metadata(self) -> Dict:
        """ベクトルストアのメタデータをロード"""
        if self.metadata_file.exists():
            with open(self.metadata_file, 'r') as f:
                return json.load(f)
        return {
            'processed_files': {},
            'last_update': None,
            'embedding_model': OLLAMA_MODELS['embedding']
        }
    
    def _save_metadata(self) -> None:
        """メタデータを保存"""
        with open(self.metadata_file, 'w') as f:
            json.dump(self.metadata, f, indent=2)
    
    def _start_watching(self) -> None:
        """ファイルの変更監視を開始"""
        if self.watcher:
            self.watcher.start()
            self._handle_watcher_updates()
    
    def _handle_watcher_updates(self) -> None:
        """ウォッチャーからの更新を処理"""
        def process_updates():
            while True:
                if not self.watcher or not self.watcher.running:
                    break
                    
                for file_info in self.watcher.get_cached_files():
                    if file_info['id'] not in self.metadata['processed_files']:
                        self.processing_queue.put(file_info)
                
                if not self.is_processing:
                    self._process_queue()
                    
                time.sleep(60)  # 1分待機
        
        threading.Thread(target=process_updates, daemon=True).start()
    
    def process_drive_folder(
        self,
        folder_id: Optional[str] = None,
        force_update: bool = False
    ) -> None:
        """Google Driveフォルダ内のPDFを処理"""
        try:
            # フォルダ内のPDFファイル一覧を取得
            pdf_files = self.gdrive_client.list_pdf_files(folder_id)
            
            # 進捗状況の初期化
            progress = ProcessingProgress(
                total_files=len(pdf_files),
                processed_files=0,
                current_file=None,
                status="initializing"
            )
            self._update_progress(progress)
            
            for pdf_file in pdf_files:
                progress.current_file = pdf_file['name']
                progress.status = "processing"
                self._update_progress(progress)
                
                file_id = pdf_file['id']
                file_name = pdf_file['name']
                
                # 処理済みで更新が不要な場合はスキップ
                if (
                    not force_update and
                    file_id in self.metadata['processed_files']
                ):
                    logger.info(f"Skipping already processed file: {file_name}")
                    progress.processed_files += 1
                    self._update_progress(progress)
                    continue
                
                try:
                    # PDFファイルをダウンロード
                    pdf_path = self.gdrive_client.download_file(file_id, file_name)
                    
                    # PDFを処理してチャンクに分割
                    chunks = self.pdf_processor.process_pdf(pdf_path)
                    
                    # Embeddingを生成
                    embeddings = self._generate_embeddings(chunks)
                    
                    # 結果を保存
                    self._save_results(file_id, file_name, chunks, embeddings)
                    
                    progress.processed_files += 1
                    self._update_progress(progress)
                    
                except Exception as e:
                    logger.error(f"Failed to process file {file_name}: {e}")
                    progress.error = str(e)
                    self._update_progress(progress)
                    continue
            
            progress.status = "completed"
            self._update_progress(progress)
            logger.info("Folder processing completed successfully")
            
        except Exception as e:
            logger.error(f"Failed to process drive folder: {e}")
            if progress:
                progress.status = "error"
                progress.error = str(e)
                self._update_progress(progress)
            raise
    
    def _process_queue(self) -> None:
        """処理キューの内容を処理"""
        if self.is_processing:
            return
            
        self.is_processing = True
        try:
            while not self.processing_queue.empty():
                file_info = self.processing_queue.get()
                self.process_drive_folder(
                    file_info['id'],
                    force_update=True
                )
                self.processing_queue.task_done()
        finally:
            self.is_processing = False
    
    def _generate_embeddings(self, chunks: List[TextChunk]) -> List[List[float]]:
        """テキストチャンクのEmbeddingを生成"""
        texts = [chunk.text for chunk in chunks]
        try:
            embeddings = self.ollama_client.get_embeddings(
                texts,
                OLLAMA_MODELS['embedding']
            )
            logger.info(f"Generated embeddings for {len(texts)} chunks")
            return embeddings
            
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            raise
    
    def _save_results(
        self,
        file_id: str,
        file_name: str,
        chunks: List[TextChunk],
        embeddings: List[List[float]]
    ) -> None:
        """処理結果を保存"""
        # 結果を保存するディレクトリ
        result_dir = VECTOR_STORE_DIR / file_id
        result_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # チャンクを保存
            chunks_file = result_dir / 'chunks.json'
            chunks_data = [
                {
                    'text': chunk.text,
                    'metadata': chunk.metadata
                }
                for chunk in chunks
            ]
            with open(chunks_file, 'w', encoding='utf-8') as f:
                json.dump(chunks_data, f, ensure_ascii=False, indent=2)
            
            # Embeddingを保存
            embeddings_file = result_dir / 'embeddings.json'
            with open(embeddings_file, 'w') as f:
                json.dump(embeddings, f)
            
            # メタデータを更新
            self.metadata['processed_files'][file_id] = {
                'file_name': file_name,
                'chunk_count': len(chunks),
                'processed_at': datetime.now().isoformat(),
                'embedding_model': OLLAMA_MODELS['embedding']
            }
            self.metadata['last_update'] = datetime.now().isoformat()
            self._save_metadata()
            
            logger.info(f"Saved processing results for {file_name}")
            
        except Exception as e:
            logger.error(f"Failed to save results for {file_name}: {e}")
            raise
    
    def _update_progress(self, progress: ProcessingProgress) -> None:
        """進捗状況を更新"""
        if self.progress_callback:
            try:
                self.progress_callback(progress)
            except Exception as e:
                logger.error(f"Progress callback error: {e}")
    
    def get_document_info(self) -> Dict[str, Any]:
        """処理済みドキュメントの情報を取得"""
        return {
            'total_documents': len(self.metadata['processed_files']),
            'last_update': self.metadata['last_update'],
            'embedding_model': self.metadata['embedding_model'],
            'documents': self.metadata['processed_files']
        }
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.watcher:
            self.watcher.stop()