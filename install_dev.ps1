# Windows用のインストールスクリプト

# Python仮想環境の作成
python -m venv venv

# 仮想環境の有効化
.\venv\Scripts\Activate.ps1

# 依存関係のインストール（開発用パッケージを含む）
pip install -e ".[dev]"

# テストの実行
pytest

Write-Host "`n開発環境のセットアップが完了しました。" -ForegroundColor Green
Write-Host "仮想環境を有効化するには次のコマンドを実行してください："
Write-Host ".\venv\Scripts\Activate.ps1" -ForegroundColor Yellow