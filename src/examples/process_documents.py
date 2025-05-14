#!/usr/bin/env python3
"""
Google DriveのPDFファイルを処理するデモスクリプト
"""

import sys
import time
from pathlib import Path
from typing import Optional
import argparse
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskID

from src.core.document_processor import DocumentProcessor, ProcessingProgress
from src.utils.logger import logger
from config.settings import GOOGLE_DRIVE_FOLDER_ID

console = Console()

class DocumentProcessingUI:
    """ドキュメント処理のUI管理クラス"""
    
    def __init__(self):
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console
        )
        self.total_task: Optional[TaskID] = None
        self.current_task: Optional[TaskID] = None
    
    def progress_callback(self, progress: ProcessingProgress) -> None:
        """進捗状況を表示"""
        if progress.status == "initializing":
            self.total_task = self.progress.add_task(
                f"Processing {progress.total_files} files...",
                total=progress.total_files
            )
            self.current_task = self.progress.add_task(
                "Initializing...",
                total=None
            )
            
        elif progress.status == "processing":
            self.progress.update(
                self.total_task,
                completed=progress.processed_files
            )
            self.progress.update(
                self.current_task,
                description=f"Processing: {progress.current_file}"
            )
            
        elif progress.status == "completed":
            self.progress.update(
                self.total_task,
                completed=progress.total_files
            )
            self.progress.update(
                self.current_task,
                description="Processing completed!"
            )
            
        elif progress.status == "error":
            self.progress.update(
                self.current_task,
                description=f"Error: {progress.error}"
            )

def main():
    parser = argparse.ArgumentParser(
        description="Process PDF files from Google Drive"
    )
    parser.add_argument(
        "--folder-id",
        default=GOOGLE_DRIVE_FOLDER_ID,
        help="Google Drive folder ID"
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Watch for changes"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force update existing documents"
    )
    
    args = parser.parse_args()
    
    try:
        ui = DocumentProcessingUI()
        
        with ui.progress:
            processor = DocumentProcessor(
                watch_for_changes=args.watch,
                progress_callback=ui.progress_callback
            )
            
            with processor:
                # 初期処理
                processor.process_drive_folder(
                    args.folder_id,
                    force_update=args.force
                )
                
                # 変更監視が有効な場合は継続実行
                if args.watch:
                    console.print("\nWatching for changes... Press Ctrl+C to stop")
                    try:
                        while True:
                            time.sleep(1)
                    except KeyboardInterrupt:
                        console.print("\nStopping...")
        
        # 処理結果の表示
        info = processor.get_document_info()
        console.print("\n[bold green]Processing Summary:[/bold green]")
        console.print(f"Total Documents: {info['total_documents']}")
        console.print(f"Last Update: {info['last_update']}")
        console.print(f"Embedding Model: {info['embedding_model']}")
        
    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {str(e)}")
        logger.error(f"Processing failed: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())