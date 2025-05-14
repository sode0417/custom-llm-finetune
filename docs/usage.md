# 使用方法

## 環境のセットアップ

1. 仮想環境の作成とパッケージのインストール:

```bash
# Linux/macOS:
./install_dev.sh

# Windows:
./install_dev.ps1
```

2. Google Drive APIの設定:
   - [Google Cloud Console](https://console.cloud.google.com/)で新しいプロジェクトを作成
   - Google Drive APIを有効化
   - OAuth 2.0クライアントIDを作成
   - credentials.jsonをダウンロードしてプロジェクトルートに配置

3. 環境変数の設定:
   - `.env`ファイルを作成または編集:
   ```env
   GOOGLE_DRIVE_FOLDER_ID=your_folder_id
   DEBUG=False
   ```

## ドキュメント処理の実行

### 基本的な使用方法

1. 特定のフォルダ内のPDFを処理:
```bash
python src/examples/process_documents.py --folder-id your_folder_id
```

2. 強制的に再処理:
```bash
python src/examples/process_documents.py --folder-id your_folder_id --force
```

3. 変更監視モード:
```bash
python src/examples/process_documents.py --watch
```

### オプション

- `--folder-id`: 処理対象のGoogle DriveフォルダID（デフォルト: 環境変数の値）
- `--watch`: フォルダの変更を監視し、新規・更新ファイルを自動処理
- `--force`: 既存の処理済みファイルも強制的に再処理

## 処理の流れ

1. Google Driveからのファイル取得:
   - 指定されたフォルダ内のPDFファイルを検索
   - 変更されたファイルのみ処理（--forceオプションがない場合）

2. PDFの処理:
   - テキスト抽出
   - チャンク分割
   - メタデータの付与

3. Embeddingの生成:
   - BGE-Small-ENモデルによるベクトル化
   - チャンク単位での処理

4. 結果の保存:
   - ベクトルストアへの保存
   - メタデータの更新

## キャッシュ管理

- ダウンロードしたPDFは`cache/pdf/`に保存
- キャッシュの有効期限: 24時間（デフォルト）
- 自動クリーンアップ機能あり

## エラー処理

1. ネットワークエラー:
   - 自動リトライ（最大3回）
   - エクスポネンシャルバックオフ

2. ファイルエラー:
   - スキップして次のファイルを処理
   - エラーログに記録

3. API制限:
   - レート制限に配慮
   - 適切な待機時間を挿入

## 進捗表示

- ファイル単位の進捗
- 全体の処理状況
- エラー情報の表示

## トラブルシューティング

1. 認証エラー:
   - credentials.jsonの配置を確認
   - token.jsonを削除して再認証

2. メモリエラー:
   - チャンクサイズを調整（config/settings.py）
   - 大きなファイルはバッチ処理を検討

3. API制限エラー:
   - 処理間隔を調整
   - バッチサイズを減少

## 監視モードについて

- 新規ファイルの自動検知
- 更新ファイルの再処理
- 削除ファイルの管理
- 定期的なキャッシュクリーンアップ

## パフォーマンス最適化

1. キャッシュ設定:
```python
# config/settings.pyで設定可能
CACHE_TTL_HOURS = 24  # キャッシュ有効期間
MAX_CACHE_SIZE_MB = 1024  # キャッシュサイズ上限
```

2. チャンク設定:
```python
# 必要に応じて調整
CHUNK_SIZE = 500  # チャンクサイズ
CHUNK_OVERLAP = 50  # オーバーラップ
```

3. バッチ処理:
   - 大量のファイルは--watchモードでの処理を推奨
   - 自動的にバッチ処理を行い、メモリ使用を最適化

## プログラムでの使用例

```python
from src.core.document_processor import DocumentProcessor

def progress_callback(progress):
    print(f"Processing: {progress.current_file} ({progress.processed_files}/{progress.total_files})")

# 処理の実行
with DocumentProcessor(progress_callback=progress_callback) as processor:
    processor.process_drive_folder("your_folder_id")
    
    # 処理結果の確認
    info = processor.get_document_info()
    print(f"Processed {info['total_documents']} documents")