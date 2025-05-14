# VSCode拡張機能開発環境セットアップ

## 1. 必要条件

### 1.1 開発環境
- Node.js v18.0.0以上
- Python 3.10以上
- VSCode 1.60.0以上
- Git

### 1.2 必要なVSCode拡張機能
- ESLint
- Prettier
- TypeScript and JavaScript Language Features
- Python
- Visual Studio Code Extension Testing

### 1.3 推奨スペック
- CPU: 4コア以上
- メモリ: 8GB以上
- ディスク: 20GB以上の空き容量

## 2. 開発環境セットアップ

### 2.1 プロジェクトの初期化
```bash
# プロジェクトディレクトリの作成
mkdir roocode-vscode
cd roocode-vscode

# TypeScriptプロジェクトの初期化
npm init -y
npm install -D typescript @types/vscode @types/node

# TypeScript設定
cat > tsconfig.json << EOF
{
    "compilerOptions": {
        "module": "commonjs",
        "target": "ES2020",
        "outDir": "out",
        "lib": ["ES2020"],
        "sourceMap": true,
        "rootDir": "src",
        "strict": true
    },
    "exclude": ["node_modules", ".vscode-test"]
}
EOF
```

### 2.2 VSCode拡張機能の構成
```bash
# 必要なパッケージのインストール
npm install -D @vscode/test-electron vscode-test
npm install -D webpack webpack-cli ts-loader

# package.jsonの設定
cat > package.json << EOF
{
    "name": "roocode",
    "displayName": "RooCode",
    "description": "Intelligent code documentation and search",
    "version": "0.1.0",
    "engines": {
        "vscode": "^1.60.0"
    },
    "categories": [
        "Programming Languages",
        "Other"
    ],
    "activationEvents": [
        "onLanguage:python",
        "onLanguage:typescript",
        "onLanguage:javascript"
    ],
    "main": "./out/extension.js",
    "contributes": {
        "commands": [
            {
                "command": "roocode.generateDocs",
                "title": "RooCode: Generate Documentation"
            },
            {
                "command": "roocode.searchSymbol",
                "title": "RooCode: Search Symbol"
            }
        ],
        "configuration": {
            "title": "RooCode",
            "properties": {
                "roocode.pythonPath": {
                    "type": "string",
                    "default": "python",
                    "description": "Path to Python interpreter"
                }
            }
        }
    },
    "scripts": {
        "vscode:prepublish": "npm run compile",
        "compile": "tsc -p ./",
        "watch": "tsc -watch -p ./",
        "test": "node ./out/test/runTest.js"
    }
}
EOF
```

### 2.3 プロジェクト構造のセットアップ
```bash
# ディレクトリ構造の作成
mkdir -p src/{core,providers,utils} test/{suite,fixtures}

# 基本ファイルの作成
touch src/extension.ts
touch src/core/languageServer.ts
touch src/providers/symbolProvider.ts
touch src/providers/documentProvider.ts
touch src/utils/config.ts
```

## 3. デバッグ環境の構成

### 3.1 VSCodeデバッグ設定
```json
// .vscode/launch.json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Extension",
            "type": "extensionHost",
            "request": "launch",
            "args": [
                "--extensionDevelopmentPath=${workspaceFolder}"
            ],
            "outFiles": [
                "${workspaceFolder}/out/**/*.js"
            ],
            "preLaunchTask": "npm: watch"
        },
        {
            "name": "Extension Tests",
            "type": "extensionHost",
            "request": "launch",
            "args": [
                "--extensionDevelopmentPath=${workspaceFolder}",
                "--extensionTestsPath=${workspaceFolder}/out/test/suite/index"
            ],
            "outFiles": [
                "${workspaceFolder}/out/test/**/*.js"
            ],
            "preLaunchTask": "npm: watch"
        }
    ]
}
```

### 3.2 タスク設定
```json
// .vscode/tasks.json
{
    "version": "2.0.0",
    "tasks": [
        {
            "type": "npm",
            "script": "watch",
            "problemMatcher": "$tsc-watch",
            "isBackground": true,
            "presentation": {
                "reveal": "never"
            },
            "group": {
                "kind": "build",
                "isDefault": true
            }
        }
    ]
}
```

## 4. 開発環境の初期化

### 4.1 Python環境のセットアップ
```bash
# 仮想環境の作成
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
.venv\Scripts\activate     # Windows

# 依存パッケージのインストール
pip install -r requirements.txt
```

### 4.2 Language Serverのセットアップ
```bash
# Language Server依存パッケージのインストール
npm install -D vscode-languageclient
npm install -D vscode-languageserver
npm install -D vscode-languageserver-types
```

## 5. テスト環境のセットアップ

### 5.1 テストフレームワークの設定
```bash
# テスト用パッケージのインストール
npm install -D mocha @types/mocha
npm install -D chai @types/chai
npm install -D sinon @types/sinon

# テストスクリプトの作成
cat > src/test/suite/index.ts << EOF
import * as path from 'path';
import * as Mocha from 'mocha';
import * as glob from 'glob';

export function run(): Promise<void> {
    const mocha = new Mocha({
        ui: 'tdd',
        color: true
    });
    
    const testsRoot = path.resolve(__dirname, '..');
    
    return new Promise((c, e) => {
        glob('**/**.test.js', { cwd: testsRoot }, (err, files) => {
            if (err) {
                return e(err);
            }
            
            files.forEach(f => mocha.addFile(path.resolve(testsRoot, f)));
            
            try {
                mocha.run(failures => {
                    if (failures > 0) {
                        e(new Error(`${failures} tests failed.`));
                    } else {
                        c();
                    }
                });
            } catch (err) {
                e(err);
            }
        });
    });
}
EOF
```

## 6. エラー対処とトラブルシューティング

### 6.1 一般的な問題
1. TypeScriptコンパイルエラー
   ```bash
   # tsconfig.jsonの確認
   tsc --noEmit
   
   # 依存関係の再インストール
   rm -rf node_modules
   npm install
   ```

2. デバッグ起動エラー
   ```bash
   # VSCode拡張ホストの再起動
   Ctrl+Shift+P → Developer: Reload Window
   ```

### 6.2 Language Server問題
1. 接続エラー
   ```bash
   # ポートの確認
   netstat -ano | findstr "8000"  # Windows
   lsof -i :8000                  # Linux/macOS
   ```

2. Python環境の問題
   ```bash
   # Pythonパスの確認
   which python
   python --version
   
   # 仮想環境の再作成
   rm -rf .venv
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

## 7. 開発ワークフロー

### 7.1 コーディング規約
```json
// .eslintrc.json
{
    "root": true,
    "parser": "@typescript-eslint/parser",
    "parserOptions": {
        "ecmaVersion": 2020,
        "sourceType": "module"
    },
    "plugins": [
        "@typescript-eslint"
    ],
    "extends": [
        "eslint:recommended",
        "plugin:@typescript-eslint/recommended"
    ]
}
```

### 7.2 コミット前の確認事項
```bash
# リントチェック
npm run lint

# テストの実行
npm test

# TypeScriptのビルド確認
npm run compile
```

## 8. パッケージング

### 8.1 拡張機能のパッケージング
```bash
# vsce のインストール
npm install -g vsce

# パッケージの作成
vsce package

# マーケットプレイスへの公開
vsce publish
```

### 8.2 配布用設定
```json
// package.json に追加
{
    "publisher": "your-publisher-name",
    "repository": {
        "type": "git",
        "url": "https://github.com/username/roocode-vscode.git"
    },
    "bugs": {
        "url": "https://github.com/username/roocode-vscode/issues"
    }
}