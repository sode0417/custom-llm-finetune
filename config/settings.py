import os
from pathlib import Path
from typing import Dict
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = BASE_DIR / "src"
CACHE_DIR = BASE_DIR / "cache"
DOCS_DIR = BASE_DIR / "docs"

# Create required directories
CACHE_DIR.mkdir(exist_ok=True)
DOCS_DIR.mkdir(exist_ok=True)

# PDF processing settings
PDF_CACHE_DIR = CACHE_DIR / "pdf"
PDF_CACHE_DIR.mkdir(exist_ok=True)
CHUNK_SIZE = 500  # チャンクサイズ（トークン数）
CHUNK_OVERLAP = 50  # チャンク間のオーバーラップ（トークン数）

# Vector store settings
VECTOR_STORE_DIR = CACHE_DIR / "vector_store"
VECTOR_STORE_DIR.mkdir(exist_ok=True)

# Logging settings
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "app.log"

# Google Drive settings
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
GOOGLE_TOKEN_FILE = os.getenv("GOOGLE_TOKEN_FILE", "token.json")
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")

# Ollama settings
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODELS: Dict[str, str] = {
    "general": os.getenv(
        "OLLAMA_GENERAL_MODEL",
        "mistralai/Mistral-7B-Instruct-v0.1"
    ),
    "code": os.getenv(
        "OLLAMA_CODE_MODEL",
        "codellama:7b-code"
    ),
    "embedding": os.getenv(
        "OLLAMA_EMBEDDING_MODEL",
        "znbang/bge:small-en-v1.5-f32"
    )
}

# Debug mode
DEBUG = os.getenv("DEBUG", "False").lower() == "true"

# Default environment variables for .env file
DEFAULT_ENV_VARS = """# Google Drive Settings
GOOGLE_CREDENTIALS_FILE=credentials.json
GOOGLE_TOKEN_FILE=token.json
GOOGLE_DRIVE_FOLDER_ID=your_folder_id_here

# Ollama Settings
OLLAMA_HOST=http://localhost:11434
OLLAMA_GENERAL_MODEL=mistralai/Mistral-7B-Instruct-v0.1
OLLAMA_CODE_MODEL=codellama:7b-code
OLLAMA_EMBEDDING_MODEL=znbang/bge:small-en-v1.5-f32

# Debug Mode
DEBUG=False
"""

# Create default .env file if it doesn't exist
env_file = BASE_DIR / ".env"
if not env_file.exists():
    env_file.write_text(DEFAULT_ENV_VARS)

# Validate required settings
if not GOOGLE_DRIVE_FOLDER_ID and not DEBUG:
    raise ValueError(
        "GOOGLE_DRIVE_FOLDER_ID is required. "
        "Please set it in your .env file."
    )