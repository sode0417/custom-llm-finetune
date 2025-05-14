# インポートエラー修正計画

## 問題点
現在のプロジェクト構造では以下の問題が発生しています：
1. configパッケージが正しく認識されていない
2. モジュール間の相対インポートが機能していない
3. PYTHONPATHの設定が必要

## 修正方針

### 1. パッケージ構造の整理
- configディレクトリをパッケージとして認識させるため、`config/__init__.py`を追加
- プロジェクトルートにsetup.pyを追加してパッケージとしてインストール可能に

### 2. 必要なファイル
```
project_root/
├── setup.py
├── config/
│   ├── __init__.py
│   └── settings.py
└── src/
    └── ... (existing files)
```

### 3. インポートパスの修正
1. すべてのインポートを絶対パスベースに統一
2. configパッケージのインポートを修正
   ```python
   # Before
   from config.settings import SOME_SETTING
   
   # After
   from ollama_roocode.config.settings import SOME_SETTING
   ```

### 4. setup.pyの実装
- パッケージ名を`ollama_roocode`として定義
- 必要な依存関係を記述
- configパッケージを含めたパッケージ構造を定義

### 5. テスト環境の整備
- pytestのパス設定を修正
- テストケースのインポート文を更新

## 実装手順

1. setup.pyの作成
2. config/__init__.pyの作成
3. 各モジュールのインポート文の修正
4. パッケージのインストールとテスト

## 注意点
- 開発中は`pip install -e .`でパッケージをインストール
- テスト実行前にPYTHONPATHが正しく設定されていることを確認
- VSCodeの設定で作業ディレクトリを正しく認識させる

この修正により、モジュール間の依存関係が明確になり、インポートエラーが解消されることが期待されます。