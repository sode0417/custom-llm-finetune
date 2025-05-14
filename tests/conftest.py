import pytest
from pathlib import Path
import shutil
import tempfile

@pytest.fixture
def temp_dir():
    """一時ディレクトリを提供するフィクスチャ"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)

@pytest.fixture
def sample_pdf(temp_dir):
    """サンプルPDFファイルを提供するフィクスチャ"""
    pdf_content = b"%PDF-1.4\n..."  # 最小限のPDFコンテンツ
    pdf_path = temp_dir / "sample.pdf"
    with open(pdf_path, "wb") as f:
        f.write(pdf_content)
    return pdf_path

@pytest.fixture
def vector_store_dir(temp_dir):
    """一時的なベクトルストアディレクトリを提供するフィクスチャ"""
    vector_dir = temp_dir / "vector_store"
    vector_dir.mkdir()
    return vector_dir

@pytest.fixture
def pdf_cache_dir(temp_dir):
    """一時的なPDFキャッシュディレクトリを提供するフィクスチャ"""
    cache_dir = temp_dir / "pdf_cache"
    cache_dir.mkdir()
    return cache_dir