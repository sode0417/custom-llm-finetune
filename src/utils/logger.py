import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional

from config.settings import LOG_FILE, DEBUG

def setup_logger(
    name: str,
    log_file: Optional[Path] = None,
    level: Optional[int] = None
) -> logging.Logger:
    """
    ロガーをセットアップする
    
    Args:
        name: ロガーの名前
        log_file: ログファイルのパス（デフォルトはsettings.LOG_FILE）
        level: ログレベル（デフォルトはDEBUGがTrueの場合DEBUG、それ以外はINFO）
        
    Returns:
        設定済みのロガーインスタンス
    """
    logger = logging.getLogger(name)
    
    # すでにハンドラーが設定されている場合は追加しない
    if logger.handlers:
        return logger
    
    # ログレベルの設定
    if level is None:
        level = logging.DEBUG if DEBUG else logging.INFO
    logger.setLevel(level)
    
    # フォーマッターの作成
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # ファイルハンドラーの設定
    log_file = log_file or LOG_FILE
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    # 最大10MBのログファイルを5つまで保持
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)
    
    # コンソールハンドラーの設定
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)
    
    # ハンドラーの追加
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# デフォルトロガーの作成
logger = setup_logger('ollama_roocode')

# 外部ライブラリのログレベルを調整
logging.getLogger('googleapiclient').setLevel(logging.WARNING)
logging.getLogger('google_auth_oauthlib').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)