#!/bin/bash

# プロジェクトディレクトリに移動
cd "$(dirname "$0")/.."

# 既存のnode_modulesを削除
rm -rf node_modules
rm -f package-lock.json

# 必要なパッケージをインストール
npm install -D @types/vscode@^1.60.0
npm install -D @types/node@^20.2.5
npm install -D vscode-languageclient@^8.1.0
npm install -D vscode-languageserver@^8.1.0
npm install -D vscode-languageserver-protocol@^3.17.3
npm install -D vscode-languageserver-types@^3.17.3
npm install -D typescript@^5.1.3
npm install -D @typescript-eslint/parser@^5.59.8
npm install -D @typescript-eslint/eslint-plugin@^5.59.8
npm install -D eslint@^8.41.0

# TypeScriptの設定ファイルが存在しない場合は作成
if [ ! -f tsconfig.json ]; then
    cp scripts/tsconfig.template.json tsconfig.json
fi

# ビルドディレクトリの作成
mkdir -p out

# TypeScriptのコンパイル
npx tsc

echo "Installation completed successfully!"