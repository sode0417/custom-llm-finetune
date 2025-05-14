import {
    LanguageClient,
    LanguageClientOptions,
    ServerOptions,
    TransportKind
} from 'vscode-languageclient/node';
import * as vscode from 'vscode';
import { join } from 'path';
import {
    ServerRequestParams,
    ServerResponse,
    SearchResult,
    DocumentationResult
} from '../types/progress';

export class RooCodeLanguageClient {
    private client: LanguageClient;
    private readonly clientOptions: LanguageClientOptions;
    private readonly serverOptions: ServerOptions;

    constructor(context: vscode.ExtensionContext) {
        // サーバーオプションの設定
        this.serverOptions = {
            command: vscode.workspace.getConfiguration('roocode').get('pythonPath') || 'python',
            args: [join(context.extensionPath, 'server', 'server.py')],
            transport: TransportKind.stdio
        };

        // クライアントオプションの設定
        this.clientOptions = {
            documentSelector: [
                { scheme: 'file', language: 'python' },
                { scheme: 'file', language: 'typescript' },
                { scheme: 'file', language: 'javascript' }
            ],
            synchronize: {
                fileEvents: vscode.workspace.createFileSystemWatcher('**/*.{py,ts,js}')
            },
            outputChannelName: 'RooCode Language Server'
        };

        // Language Clientの初期化
        this.client = new LanguageClient(
            'roocode',
            'RooCode Language Server',
            this.serverOptions,
            this.clientOptions
        );
    }

    /**
     * クライアントを起動
     */
    public async start(): Promise<void> {
        try {
            await this.client.start();
            console.log('RooCode Language Client started');
        } catch (error) {
            console.error('Failed to start RooCode Language Client:', error);
            throw error;
        }
    }

    /**
     * クライアントを停止
     */
    public async stop(): Promise<void> {
        if (this.client) {
            await this.client.stop();
        }
    }

    /**
     * ドキュメント検索リクエストを送信
     */
    public async searchDocumentation(params: ServerRequestParams): Promise<ServerResponse<SearchResult[]>> {
        try {
            return await this.client.sendRequest('roocode/search', params);
        } catch (error) {
            console.error('Search request failed:', error);
            throw error;
        }
    }

    /**
     * ドキュメント生成リクエストを送信
     */
    public async generateDocumentation(params: ServerRequestParams): Promise<ServerResponse<DocumentationResult>> {
        try {
            return await this.client.sendRequest('roocode/generate', params);
        } catch (error) {
            console.error('Generate request failed:', error);
            throw error;
        }
    }

    /**
     * シンボル情報のリクエストを送信
     */
    public async getSymbolInfo(symbol: string, context: vscode.TextDocument): Promise<ServerResponse<any>> {
        try {
            return await this.client.sendRequest('roocode/symbolInfo', {
                symbol,
                filePath: context.uri.fsPath,
                language: context.languageId
            });
        } catch (error) {
            console.error('Symbol info request failed:', error);
            throw error;
        }
    }

    /**
     * サーバーの状態を確認
     */
    public get isRunning(): boolean {
        return this.client !== undefined && this.client.isRunning();
    }

    /**
     * エラーハンドラーを設定
     */
    public setErrorHandler(handler: (error: Error) => void): void {
        this.client.onDidFailWithError(handler);
    }

    /**
     * 通知ハンドラーを設定
     */
    public setNotificationHandler(type: string, handler: (params: any) => void): void {
        this.client.onNotification(type, handler);
    }

    /**
     * カスタムリクエストを送信
     */
    public async sendCustomRequest<T>(method: string, params: any): Promise<ServerResponse<T>> {
        try {
            return await this.client.sendRequest(method, params);
        } catch (error) {
            console.error(`Custom request '${method}' failed:`, error);
            throw error;
        }
    }
}