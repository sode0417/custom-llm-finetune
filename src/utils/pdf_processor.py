from typing import List, Dict, Any
from pathlib import Path
import PyPDF2
from dataclasses import dataclass
from datetime import datetime
import json
import re

from config.settings import CHUNK_SIZE, CHUNK_OVERLAP
from src.utils.logger import logger

@dataclass
class TextChunk:
    """テキストチャンクを表すデータクラス"""
    text: str
    metadata: Dict[str, Any]

class PDFProcessorError(Exception):
    """PDFプロセッサーの基本例外クラス"""
    pass

class PDFProcessor:
    """PDFファイルの処理とテキスト抽出を行うクラス"""
    
    def __init__(
        self,
        chunk_size: int = CHUNK_SIZE,
        chunk_overlap: int = CHUNK_OVERLAP
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    def process_pdf(self, pdf_path: Path) -> List[TextChunk]:
        """PDFファイルを処理してテキストチャンクのリストを返す"""
        if not pdf_path.exists():
            raise PDFProcessorError(f"PDF file not found: {pdf_path}")
            
        try:
            # PDFファイルを読み込み
            with open(pdf_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                
                # 基本的なメタデータを取得
                metadata = self._extract_metadata(reader, pdf_path)
                
                chunks = []
                total_text = 0
                for page_num, page in enumerate(reader.pages, 1):
                    page_text = page.extract_text()
                    if not page_text.strip():
                        continue
                        
                    # ページごとのメタデータを作成
                    page_metadata = {
                        **metadata,
                        'page_number': page_num,
                        'chunk_type': 'page'
                    }
                    
                    # テキストをチャンクに分割
                    page_chunks = self._split_text(
                        page_text,
                        page_metadata
                    )
                    chunks.extend(page_chunks)
                    total_text += len(page_text)
                
                logger.info(
                    f"Processed {pdf_path.name}: "
                    f"{len(chunks)} chunks created from {len(reader.pages)} pages "
                    f"(total {total_text:,} characters)"
                )
                return chunks
                
        except PyPDF2.PdfReadError as e:
            logger.error(f"Failed to read PDF {pdf_path}: {e}")
            raise PDFProcessorError(f"Invalid PDF file: {e}") from e
        except Exception as e:
            logger.error(f"Failed to process PDF {pdf_path}: {e}")
            raise PDFProcessorError(f"PDF processing failed: {e}") from e
    
    def _extract_metadata(
        self,
        reader: PyPDF2.PdfReader,
        pdf_path: Path
    ) -> Dict[str, Any]:
        """PDFのメタデータを抽出"""
        metadata = {
            'file_name': pdf_path.name,
            'file_path': str(pdf_path),
            'page_count': len(reader.pages),
            'processed_at': datetime.now().isoformat()
        }
        
        # PDFの情報を取得
        if reader.metadata:
            metadata.update({
                'title': reader.metadata.get('/Title', ''),
                'author': reader.metadata.get('/Author', ''),
                'creation_date': reader.metadata.get('/CreationDate', '')
            })
        
        return metadata
    
    def _split_text(
        self,
        text: str,
        metadata: Dict[str, Any]
    ) -> List[TextChunk]:
        """テキストをチャンクに分割"""
        chunks = []
        
        # テキストの前処理
        text = self._preprocess_text(text)
        
        # 段落で分割
        paragraphs = self._split_paragraphs(text)
        
        current_chunk = ""
        current_size = 0
        
        for para in paragraphs:
            para_size = len(para.split())
            
            # 現在のチャンクにパラグラフを追加できる場合
            if current_size + para_size <= self.chunk_size:
                if current_chunk:
                    current_chunk += "\n\n"
                current_chunk += para
                current_size += para_size
            
            # チャンクが最大サイズに達した場合
            else:
                if current_chunk:
                    chunk_metadata = {
                        **metadata,
                        'chunk_index': len(chunks),
                        'chunk_size': current_size
                    }
                    chunks.append(TextChunk(current_chunk, chunk_metadata))
                
                # 新しいチャンクを開始
                current_chunk = para
                current_size = para_size
        
        # 最後のチャンクを追加
        if current_chunk:
            chunk_metadata = {
                **metadata,
                'chunk_index': len(chunks),
                'chunk_size': current_size
            }
            chunks.append(TextChunk(current_chunk, chunk_metadata))
        
        return chunks
    
    def _preprocess_text(self, text: str) -> str:
        """テキストの前処理を行う"""
        # 余分な空白を削除
        text = re.sub(r'\s+', ' ', text)
        
        # 不要な制御文字を削除
        text = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f-\x9f]', '', text)
        
        # 全角スペースを半角に変換
        text = text.replace('　', ' ')
        
        # 前後の空白を削除
        return text.strip()
    
    def _split_paragraphs(self, text: str) -> List[str]:
        """テキストを段落に分割"""
        # 空行で区切られた段落を検出
        paragraphs = [p.strip() for p in text.split('\n\n')]
        
        # 空の段落を除外し、過度に短い段落を結合
        processed_paragraphs = []
        current_para = ""
        
        for p in paragraphs:
            if not p:
                continue
                
            if len(p.split()) < 5 and current_para:  # 単語数が5未満の短い段落は前の段落に結合
                current_para += " " + p
            else:
                if current_para:
                    processed_paragraphs.append(current_para)
                current_para = p
        
        if current_para:
            processed_paragraphs.append(current_para)
        
        return processed_paragraphs
    
    def save_chunks(
        self,
        chunks: List[TextChunk],
        output_dir: Path,
        base_name: str
    ) -> None:
        """チャンクをJSONファイルとして保存"""
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{base_name}_chunks.json"
        
        # チャンクをJSON形式に変換
        chunks_data = [
            {
                'text': chunk.text,
                'metadata': chunk.metadata
            }
            for chunk in chunks
        ]
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(chunks_data, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved {len(chunks)} chunks to {output_path}")
            
        except Exception as e:
            logger.error(f"Failed to save chunks to {output_path}: {e}")
            raise PDFProcessorError(f"Failed to save chunks: {e}") from e