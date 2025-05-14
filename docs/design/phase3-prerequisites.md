# Phase 3: 実装前準備

## 1. 追加ライブラリ

### ベクトルデータベース
```txt
chromadb>=0.4.0
hnswlib>=0.7.0
faiss-cpu>=1.7.4  # または faiss-gpu (CUDA対応)
```

### 非同期処理
```txt
aiohttp>=3.8.0
asyncio>=3.4.3
aiosqlite>=0.17.0
```

### 最適化・モニタリング
```txt
optuna>=3.0.0
prometheus-client>=0.16.0
opentelemetry-api>=1.15.0
```

## 2. 設定パラメータ

### config/settings.pyに追加
```python
# Vector Store Settings
VECTOR_STORE = {
    'engine': 'chroma',  # または 'faiss'
    'dimension': 384,    # BGE-Small-ENの出力次元
    'metric': 'cosine',
    'index_params': {
        'M': 64,        # グラフの次数
        'ef_construction': 200,
        'ef_search': 100
    }
}

# Search Settings
SEARCH = {
    'semantic_weight': 0.7,   # セマンティック検索の重み
    'top_k': 5,              # 検索結果数
    'min_similarity': 0.6    # 最小類似度
}

# Context Settings
CONTEXT = {
    'max_tokens': 2000,      # コンテキスト最大トークン数
    'chunk_overlap': 50,     # チャンク間オーバーラップ
    'min_chunk_length': 100  # 最小チャンク長
}

# Generation Settings
GENERATION = {
    'temperature': 0.7,
    'top_p': 0.9,
    'max_tokens': 500,
    'system_prompt': """与えられた情報に基づいて質問に回答してください。
情報に基づかない推測は避け、不確かな場合はその旨を明示してください。"""
}

# Performance Settings
PERFORMANCE = {
    'batch_size': 100,
    'cache_ttl': 3600,
    'max_concurrent': 10
}
```

## 3. 統合ポイント

### 1. DocumentProcessorとの統合
```python
class DocumentProcessor:
    # 既存のメソッドに追加
    async def process_embeddings(self, chunks: List[TextChunk]) -> None:
        """チャンクのembeddingを生成しベクトルストアに保存"""
        embeddings = await self.generate_embeddings(chunks)
        await self.vector_store.add_embeddings(
            embeddings=embeddings,
            texts=[c.text for c in chunks],
            metadata=[c.metadata for c in chunks]
        )
```

### 2. PDFProcessorとの統合
```python
class PDFProcessor:
    # チャンク分割の最適化
    def _split_text(self, text: str, metadata: Dict) -> List[TextChunk]:
        """コンテキスト管理を考慮したチャンク分割"""
        chunks = self._smart_split(
            text,
            max_tokens=CONTEXT['max_tokens'],
            overlap=CONTEXT['chunk_overlap'],
            min_length=CONTEXT['min_chunk_length']
        )
        return [TextChunk(text=c, metadata=metadata) for c in chunks]
```

### 3. OllamaClientとの統合
```python
class OllamaClient:
    # 生成パラメータの最適化
    async def generate_with_context(
        self,
        prompt: str,
        context: str,
        **kwargs
    ) -> str:
        """コンテキストを考慮した生成"""
        full_prompt = self._build_prompt(
            query=prompt,
            context=context,
            system_prompt=GENERATION['system_prompt']
        )
        return await self.generate(
            prompt=full_prompt,
            temperature=kwargs.get('temperature', GENERATION['temperature']),
            top_p=kwargs.get('top_p', GENERATION['top_p']),
            max_tokens=kwargs.get('max_tokens', GENERATION['max_tokens'])
        )
```

## 4. 事前確認事項

### 1. 性能要件
- メモリ: 最低8GB（推奨16GB）
- ストレージ: 最低50GB空き容量
- CPU: 4コア以上（推奨8コア）
- GPU: オプション（CUDA対応）

### 2. 依存関係の確認
```bash
# 互換性チェック
pip check

# 依存関係の更新
pip install --upgrade -r requirements.txt
```

### 3. 環境変更
- Python 3.10以上を推奨
- 非同期I/O対応
- CUDA環境（オプション）

## 5. 移行ステップ

1. 設定ファイルの更新
   - 新規パラメータの追加
   - 既存設定の最適化

2. 依存関係の更新
   - 新規パッケージのインストール
   - バージョン互換性の確認

3. データ移行準備
   - 既存データのバックアップ
   - 新フォーマットへの変換計画

4. モニタリング設定
   - メトリクス定義
   - アラート設定
   - ログ形式の標準化

## 6. リスク対策

### 1. パフォーマンス
- 段階的なデータ移行
- 負荷テストの実施
- スケーリング計画の準備

### 2. 互換性
- 下位互換性の維持
- フォールバックオプションの用意
- 段階的な機能追加

### 3. 安定性
- 自動バックアップの設定
- エラー検知の強化
- リカバリー手順の整備