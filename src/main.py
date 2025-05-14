import argparse
import sys
from pathlib import Path
from typing import Optional
import json

from config.settings import (
    GOOGLE_DRIVE_FOLDER_ID,
    DEBUG
)
from src.core.document_processor import DocumentProcessor
from src.core.rag_engine import RAGEngine
from src.utils.logger import logger

def process_documents(
    folder_id: Optional[str] = None,
    force_update: bool = False
) -> None:
    """ドキュメントの処理を実行"""
    processor = DocumentProcessor()
    try:
        processor.process_drive_folder(folder_id, force_update)
        logger.info("Document processing completed successfully")
        
        # 処理結果の表示
        info = processor.get_document_info()
        print("\nProcessing Summary:")
        print(f"Total Documents: {info['total_documents']}")
        print(f"Last Update: {info['last_update']}")
        
    except Exception as e:
        logger.error(f"Document processing failed: {e}")
        sys.exit(1)

def query_documents(
    query: str,
    file_filter: Optional[str] = None
) -> None:
    """ドキュメントに対して質問"""
    rag = RAGEngine()
    try:
        # フィルタ条件の構築
        filter_criteria = (
            {'file_name': file_filter} if file_filter else None
        )
        
        # 回答を生成
        response, chunks = rag.generate_response(query, filter_criteria)
        
        print("\nAnswer:")
        print("=" * 80)
        print(response)
        print("=" * 80)
        
        if chunks:
            print("\nReferences:")
            for i, chunk in enumerate(chunks, 1):
                metadata = chunk['metadata']
                print(f"\n{i}. From: {metadata['file_name']}, "
                      f"Page: {metadata.get('page_number', 'N/A')}")
                print(f"Similarity: {chunk['similarity']:.3f}")
        
    except Exception as e:
        logger.error(f"Query failed: {e}")
        sys.exit(1)

def show_stats() -> None:
    """システムの統計情報を表示"""
    try:
        rag = RAGEngine()
        stats = rag.get_stats()
        
        print("\nSystem Statistics:")
        print("=" * 80)
        print(f"Total Documents: {stats['total_documents']}")
        print(f"Total Chunks: {stats['total_chunks']}")
        print(f"Embedding Model: {stats['embedding_model']}")
        print(f"Generation Model: {stats['generation_model']}")
        print(f"Last Update: {stats['last_update']}")
        print("=" * 80)
        
    except Exception as e:
        logger.error(f"Failed to get statistics: {e}")
        sys.exit(1)

def main() -> None:
    """メイン処理"""
    parser = argparse.ArgumentParser(
        description="Ollama + RooCode Document QA System"
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # processコマンド
    process_parser = subparsers.add_parser(
        'process',
        help='Process documents from Google Drive'
    )
    process_parser.add_argument(
        '--folder-id',
        default=GOOGLE_DRIVE_FOLDER_ID,
        help='Google Drive folder ID'
    )
    process_parser.add_argument(
        '--force',
        action='store_true',
        help='Force update existing documents'
    )
    
    # queryコマンド
    query_parser = subparsers.add_parser(
        'query',
        help='Query processed documents'
    )
    query_parser.add_argument(
        'question',
        help='Question to ask'
    )
    query_parser.add_argument(
        '--file',
        help='Filter by specific file name'
    )
    
    # statsコマンド
    subparsers.add_parser(
        'stats',
        help='Show system statistics'
    )
    
    args = parser.parse_args()
    
    if args.command == 'process':
        process_documents(args.folder_id, args.force)
    elif args.command == 'query':
        query_documents(args.question, args.file)
    elif args.command == 'stats':
        show_stats()
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        if DEBUG:
            raise
        sys.exit(1)