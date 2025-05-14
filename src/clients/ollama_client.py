import requests
import json
from typing import Dict, Any, Optional, List
import time
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

from config.settings import OLLAMA_HOST, OLLAMA_MODELS
from src.utils.logger import logger

class OllamaClientError(Exception):
    """Ollamaクライアントの基本例外クラス"""
    pass

class OllamaConnectionError(OllamaClientError):
    """接続エラー"""
    pass

class OllamaModelError(OllamaClientError):
    """モデル関連のエラー"""
    pass

class OllamaClient:
    """Ollamaサーバーとの通信を管理するクライアント"""
    
    def __init__(self, host: str = OLLAMA_HOST):
        self.host = host.rstrip('/')
        self.models: Dict[str, bool] = {}  # モデルの利用可能状態を追跡
        self._check_server_connection()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(requests.exceptions.RequestException),
        reraise=True
    )
    def _check_server_connection(self) -> None:
        """Ollamaサーバーの接続を確認"""
        try:
            response = requests.get(
                f"{self.host}/api/tags",
                timeout=10
            )
            response.raise_for_status()
            available_models = [model["name"] for model in response.json()["models"]]
            logger.info(f"Available models: {available_models}")
            
            # 必要なモデルの存在確認
            for purpose, model in OLLAMA_MODELS.items():
                self.models[model] = model in available_models
                if not self.models[model]:
                    logger.warning(f"Model {model} for {purpose} is not available")
                    
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to connect to Ollama server: {e}")
            raise OllamaConnectionError("Ollama server is not accessible") from e
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(requests.exceptions.RequestException),
        reraise=True
    )
    def ensure_model_available(self, model_name: str) -> None:
        """モデルが利用可能か確認し、必要に応じてダウンロード"""
        if model_name not in self.models or not self.models[model_name]:
            try:
                logger.info(f"Pulling model: {model_name}")
                response = requests.post(
                    f"{self.host}/api/pull",
                    json={"name": model_name},
                    timeout=600  # モデルのダウンロードは時間がかかる可能性がある
                )
                response.raise_for_status()
                self.models[model_name] = True
                logger.info(f"Successfully pulled model: {model_name}")
            except requests.exceptions.RequestException as e:
                logger.error(f"Failed to pull model {model_name}: {e}")
                raise OllamaModelError(f"Failed to pull model: {model_name}") from e
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(requests.exceptions.RequestException),
        reraise=True
    )
    def generate(
        self,
        prompt: str,
        model_name: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        """テキスト生成リクエストを送信"""
        self.ensure_model_available(model_name)
        
        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": False
        }
        
        if system_prompt:
            payload["system"] = system_prompt
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens:
            payload["max_tokens"] = max_tokens
            
        try:
            response = requests.post(
                f"{self.host}/api/generate",
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            return response.json()["response"]
        except requests.exceptions.RequestException as e:
            logger.error(f"Generation failed: {e}")
            raise OllamaClientError("Failed to generate response") from e
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(requests.exceptions.RequestException),
        reraise=True
    )
    def get_embeddings(
        self,
        texts: List[str],
        model_name: str = OLLAMA_MODELS["embedding"]
    ) -> List[List[float]]:
        """テキストのembeddingを取得"""
        self.ensure_model_available(model_name)
        
        embeddings = []
        for text in texts:
            try:
                response = requests.post(
                    f"{self.host}/api/embeddings",
                    json={"model": model_name, "prompt": text},
                    timeout=10
                )
                response.raise_for_status()
                embeddings.append(response.json()["embedding"])
                
                # レート制限を考慮して短い待機を入れる
                time.sleep(0.1)
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Embedding generation failed: {e}")
                raise OllamaClientError("Failed to generate embeddings") from e
                
        return embeddings