#!/bin/bash

# Python仮想環境の作成
python -m venv venv

# 仮想環境の有効化
source venv/bin/activate

# 依存関係のインストール（開発用パッケージを含む）
pip install -e ".[dev]"

# テストの実行
pytest

echo "開発環境のセットアップが完了しました。"
echo "仮想環境を有効化するには次のコマンドを実行してください："
echo "source venv/bin/activate  # Linux/macOS"
echo "venv\\Scripts\\activate   # Windows"