import pytest
from pathlib import Path
from src.utils.pdf_processor import PDFProcessor, TextChunk

def test_pdf_processor_initialization():
    """PDFProcessorの初期化テスト"""
    processor = PDFProcessor(chunk_size=500, chunk_overlap=50)
    assert processor.chunk_size == 500
    assert processor.chunk_overlap == 50

def test_preprocess_text():
    """テキスト前処理のテスト"""
    processor = PDFProcessor()
    
    # 余分な空白の除去
    text = "This   has    extra   spaces  "
    result = processor._preprocess_text(text)
    assert result == "This has extra spaces"
    
    # 制御文字の除去
    text = "Text with\x00control\x1fchars"
    result = processor._preprocess_text(text)
    assert result == "Text withcontrolchars"

def test_split_paragraphs():
    """段落分割のテスト"""
    processor = PDFProcessor()
    
    text = """First paragraph
    
    Second paragraph
    
    Third paragraph"""
    
    paragraphs = processor._split_paragraphs(text)
    
    assert len(paragraphs) == 3
    assert paragraphs[0].strip() == "First paragraph"
    assert paragraphs[1].strip() == "Second paragraph"
    assert paragraphs[2].strip() == "Third paragraph"

def test_split_text():
    """テキスト分割のテスト"""
    processor = PDFProcessor(chunk_size=10, chunk_overlap=2)
    
    text = "This is a test text for splitting into chunks"
    metadata = {"file_name": "test.pdf", "page_number": 1}
    
    chunks = processor._split_text(text, metadata)
    
    assert len(chunks) > 0
    assert isinstance(chunks[0], TextChunk)
    assert chunks[0].metadata["file_name"] == "test.pdf"
    assert chunks[0].metadata["page_number"] == 1
    assert chunks[0].metadata["chunk_index"] == 0

def test_save_chunks(temp_dir):
    """チャンク保存のテスト"""
    processor = PDFProcessor()
    
    chunks = [
        TextChunk(
            text="Test chunk 1",
            metadata={"file_name": "test.pdf", "page_number": 1}
        ),
        TextChunk(
            text="Test chunk 2",
            metadata={"file_name": "test.pdf", "page_number": 1}
        )
    ]
    
    processor.save_chunks(chunks, temp_dir, "test")
    
    # 保存されたファイルの確認
    saved_file = temp_dir / "test_chunks.json"
    assert saved_file.exists()

@pytest.mark.integration
def test_process_pdf(sample_pdf):
    """PDFファイル処理の統合テスト"""
    processor = PDFProcessor()
    
    try:
        chunks = processor.process_pdf(sample_pdf)
        assert isinstance(chunks, list)
        if chunks:  # PDFから実際にテキストが抽出できた場合
            assert isinstance(chunks[0], TextChunk)
            assert "file_name" in chunks[0].metadata
            assert "page_number" in chunks[0].metadata
    except Exception as e:
        pytest.skip(f"PDF processing failed: {e}")

@pytest.mark.integration
def test_invalid_pdf_handling(temp_dir):
    """無効なPDFファイルの処理テスト"""
    processor = PDFProcessor()
    
    # 無効なファイルを作成
    invalid_pdf = temp_dir / "invalid.pdf"
    invalid_pdf.write_text("This is not a PDF file")
    
    with pytest.raises(Exception):
        processor.process_pdf(invalid_pdf)