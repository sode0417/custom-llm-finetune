import * as vscode from 'vscode';

export interface Progress {
    report(value: { message?: string; increment?: number }): void;
}

export interface SearchResult {
    text: string;
    source: string;
    relevance: number;
    metadata?: {
        [key: string]: any;
    };
}

export interface DocumentationResult {
    content: string;
    format: string;
    metadata?: {
        [key: string]: any;
    };
}

export interface ServerRequestParams {
    query?: string;
    code?: string;
    language?: string;
    options?: {
        [key: string]: any;
    };
}

export interface ServerResponse<T> {
    success: boolean;
    data?: T;
    error?: string;
}

export interface ExtensionState {
    initialized: boolean;
    serverRunning: boolean;
    lastQuery?: string;
    lastResults?: SearchResult[];
}