import * as vscode from 'vscode';
import { ExtensionContext, window, commands, workspace } from 'vscode';
import { LanguageClient, LanguageClientOptions, ServerOptions, TransportKind } from 'vscode-languageclient/node';
import { join } from 'path';

let client: LanguageClient;

export async function activate(context: ExtensionContext) {
    console.log('RooCode extension is now active');

    try {
        // Language Serverの設定
        const serverOptions: ServerOptions = {
            command: workspace.getConfiguration('roocode').get('pythonPath') || 'python',
            args: [join(__dirname, '..', 'server', 'server.py')],
            transport: TransportKind.stdio
        };

        // クライアントの設定
        const clientOptions: LanguageClientOptions = {
            documentSelector: [
                { scheme: 'file', language: 'python' },
                { scheme: 'file', language: 'typescript' },
                { scheme: 'file', language: 'javascript' }
            ],
            synchronize: {
                fileEvents: workspace.createFileSystemWatcher('**/*.{py,ts,js}')
            }
        };

        // Language Clientの作成と起動
        client = new LanguageClient(
            'roocode',
            'RooCode Language Server',
            serverOptions,
            clientOptions
        );

        await client.start();
        
        // ステータスバーの設定
        const statusBarItem = window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
        statusBarItem.text = "$(search) RooCode";
        statusBarItem.tooltip = "Click to search documentation";
        statusBarItem.command = 'roocode.searchDocs';
        statusBarItem.show();
        context.subscriptions.push(statusBarItem);

        // コマンドの登録
        context.subscriptions.push(
            commands.registerCommand('roocode.searchDocs', async () => {
                try {
                    const editor = window.activeTextEditor;
                    if (!editor) {
                        window.showWarningMessage('No active editor');
                        return;
                    }

                    const selection = editor.selection;
                    const text = editor.document.getText(selection);
                    
                    // プログレス表示
                    await window.withProgress({
                        location: vscode.ProgressLocation.Notification,
                        title: "Searching documentation...",
                        cancellable: false
                    }, async (progress) => {
                        try {
                            const response = await client.sendRequest('roocode/search', {
                                query: text || await window.showInputBox({
                                    prompt: 'Enter search query'
                                })
                            });

                            // 結果の表示
                            if (response) {
                                const panel = window.createWebviewPanel(
                                    'roocodeResults',
                                    'RooCode Search Results',
                                    vscode.ViewColumn.Beside,
                                    { enableScripts: true }
                                );
                                panel.webview.html = formatSearchResults(response);
                            }
                        } catch (error) {
                            window.showErrorMessage(`Search failed: ${error}`);
                        }
                    });
                } catch (error) {
                    window.showErrorMessage(`Command execution failed: ${error}`);
                }
            }),

            commands.registerCommand('roocode.generateDocs', async () => {
                try {
                    const editor = window.activeTextEditor;
                    if (!editor) {
                        window.showWarningMessage('No active editor');
                        return;
                    }

                    const text = editor.document.getText(editor.selection);
                    if (!text) {
                        window.showWarningMessage('No text selected');
                        return;
                    }

                    // ドキュメント生成
                    const response = await client.sendRequest('roocode/generate', {
                        code: text,
                        language: editor.document.languageId
                    });

                    if (response) {
                        // 生成されたドキュメントの挿入
                        await editor.edit(editBuilder => {
                            editBuilder.insert(editor.selection.start, response);
                        });
                    }
                } catch (error) {
                    window.showErrorMessage(`Documentation generation failed: ${error}`);
                }
            })
        );

    } catch (error) {
        window.showErrorMessage(`Failed to activate RooCode: ${error}`);
        throw error;
    }
}

export function deactivate(): Thenable<void> | undefined {
    if (!client) {
        return undefined;
    }
    return client.stop();
}

function formatSearchResults(results: any): string {
    return `
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body { font-family: var(--vscode-editor-font-family); }
                .result { margin: 1em 0; padding: 1em; background: var(--vscode-editor-background); }
                .source { color: var(--vscode-textLink-foreground); }
                .relevance { color: var(--vscode-textPreformat-foreground); }
            </style>
        </head>
        <body>
            <h2>Search Results</h2>
            ${results.map((result: any) => `
                <div class="result">
                    <div class="content">${result.text}</div>
                    <div class="source">Source: ${result.source}</div>
                    <div class="relevance">Relevance: ${result.relevance.toFixed(2)}</div>
                </div>
            `).join('')}
        </body>
        </html>
    `;
}