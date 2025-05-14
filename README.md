# Ollama + RooCode 独自データ統合システム

## 概要

このプロジェクトは、OllamaとRooCodeを組み合わせて独自のPDFデータを処理し、質問応答を行うシステムを実装します。

主な機能：
- Google DriveからのPDFファイル取得と処理
- テキスト抽出とチャンク分割
- Embeddingベースの検索
- RAGを用いた回答生成

## 必要要件

- Python 3.10以上
- VS Code（RooCode拡張機能）
- Ollama
- Google Drive API資格情報

## セットアップ

1. 環境構築

```bash
# 仮想環境の作成
python -m venv venv

# 仮想環境の有効化
# Windows:
.\venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 依存パッケージのインストール
pip install -r src/requirements.txt
```

2. Ollamaの設定

```bash
# Ollamaのインストール（公式サイトから）

# サーバーの起動
ollama serve

# 必要なモデルの取得
ollama pull mistralai/Mistral-7B-Instruct-v0.1
ollama pull codellama-7b
ollama pull znbang/bge:small-en-v1.5-f32
```

3. Google Drive APIの設定

- Google Cloud Consoleでプロジェクトを作成
- Google Drive APIを有効化
- 認証情報（OAuth 2.0クライアントID）を作成
- credentials.jsonをダウンロードし、プロジェクトルートに配置

4. 環境変数の設定

`.env`ファイルを作成：

```env
GOOGLE_DRIVE_FOLDER_ID=your_folder_id
DEBUG=False
```

## 使用方法

### 1. ドキュメントの処理

```bash
# 指定フォルダ内のPDFを処理
python src/main.py process --folder-id your_folder_id

# 強制更新オプション付き
python src/main.py process --folder-id your_folder_id --force
```

### 2. 質問応答

```bash
# 質問の実行
python src/main.py query "あなたの質問をここに入力"

# 特定のファイルに限定して質問
python src/main.py query "質問" --file "specific_file.pdf"
```

### 3. システム情報の確認

```bash
python src/main.py stats
```

## プロジェクト構造

```
.
├── config/             # 設定ファイル
├── src/               # ソースコード
│   ├── clients/       # 外部サービスクライアント
│   ├── core/          # コア機能
│   ├── utils/         # ユーティリティ
│   └── main.py        # メインスクリプト
├── tests/             # テストコード
├── cache/             # キャッシュデータ（自動生成）
└── docs/              # ドキュメント
```

## 開発ガイドライン

### テストの実行

```bash
# すべてのテストを実行
pytest

# カバレッジレポート付き
pytest --cov=src tests/
```

### コードフォーマット

```bash
# コードフォーマット
black src/ tests/

# 型チェック
mypy src/
```

## トラブルシューティング

1. Ollamaの接続エラー
   - Ollamaサーバーが起動していることを確認
   - `ollama list`でモデルが正しくインストールされているか確認

2. Google Drive API認証エラー
   - credentials.jsonの配置を確認
   - スコープの設定を確認
   - token.jsonが正しく生成されているか確認

3. メモリ不足エラー
   - チャンクサイズの調整（config/settings.py）
   - より軽量なモデルの使用を検討

## ライセンス

MITライセンス

## 参考文献

- Ollama公式ドキュメント
- RooCode公式ドキュメント
- Google Drive API公式ドキュメント
- LangChainドキュメント
