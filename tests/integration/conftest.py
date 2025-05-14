import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

@pytest.fixture
def temp_dir():
    """一時ディレクトリを提供"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)

@pytest.fixture
def mock_gdrive_client():
    """GoogleDriveClientのモック"""
    with patch('src.clients.gdrive_client.GoogleDriveClient') as mock:
        client = Mock()
        client.list_pdf_files = AsyncMock()
        client.download_file = AsyncMock()
        mock.return_value = client
        yield client

@pytest.fixture
def mock_ollama_client():
    """OllamaClientのモック"""
    with patch('src.clients.ollama_client.OllamaClient') as mock:
        client = Mock()
        client.get_embeddings = AsyncMock()
        client.generate = AsyncMock()
        mock.return_value = client
        yield client

@pytest.fixture
def test_data_dir() -> Path:
    """テストデータディレクトリ"""
    return Path(__file__).parent / "data"

@pytest.fixture
def sample_pdf(test_data_dir) -> Path:
    """サンプルPDFファイルのパス"""
    return test_data_dir / "sample.pdf"

@pytest.fixture
def sample_metadata() -> dict:
    """テスト用のメタデータ"""
    return {
        "source": "sample.pdf",
        "title": "Sample Document",
        "pages": 1,
        "created_at": "2025-05-15T00:00:00Z"
    }

@pytest.fixture
def test_cache_dir(temp_dir) -> Path:
    """テスト用のキャッシュディレクトリ"""
    cache_dir = temp_dir / "cache"
    cache_dir.mkdir()
    return cache_dir

@pytest.fixture
def test_vector_store_dir(temp_dir) -> Path:
    """テスト用のベクトルストアディレクトリ"""
    store_dir = temp_dir / "vector_store"
    store_dir.mkdir()
    return store_dir

@pytest.fixture(autouse=True)
def mock_settings(temp_dir, monkeypatch):
    """設定値をテスト用に上書き"""
    monkeypatch.setattr(
        'src.config.settings.PDF_CACHE_DIR',
        temp_dir / "cache"
    )
    monkeypatch.setattr(
        'src.config.settings.VECTOR_STORE_DIR',
        temp_dir / "vector_store"
    )
    monkeypatch.setattr(
        'src.config.settings.LOG_DIR',
        temp_dir / "logs"
    )

@pytest.fixture
async def setup_test_environment(
    temp_dir,
    mock_gdrive_client,
    mock_ollama_client,
    sample_pdf,
    sample_metadata
):
    """テスト環境のセットアップ"""
    # 必要なディレクトリを作成
    (temp_dir / "cache").mkdir(exist_ok=True)
    (temp_dir / "vector_store").mkdir(exist_ok=True)
    (temp_dir / "logs").mkdir(exist_ok=True)
    
    # モックの設定
    mock_gdrive_client.list_pdf_files.return_value = [{
        'id': 'test1',
        'name': 'sample.pdf',
        'modifiedTime': '2025-05-15T00:00:00Z'
    }]
    mock_gdrive_client.download_file.return_value = sample_pdf
    
    mock_ollama_client.get_embeddings.return_value = [
        [0.1, 0.2, 0.3] for _ in range(5)
    ]
    mock_ollama_client.generate.return_value = "Test response"
    
    yield {
        'temp_dir': temp_dir,
        'gdrive_client': mock_gdrive_client,
        'ollama_client': mock_ollama_client,
        'sample_pdf': sample_pdf,
        'metadata': sample_metadata
    }
    
    # クリーンアップ
    for path in temp_dir.glob("**/*"):
        if path.is_file():
            path.unlink()
        elif path.is_dir():
            path.rmdir()