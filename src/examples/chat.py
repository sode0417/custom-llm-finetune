#!/usr/bin/env python3
"""
RAGシステムを使用した対話型チャットデモ
"""

import sys
import asyncio
import argparse
from pathlib import Path
from typing import Optional, Dict, Any
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from src.core.rag_engine import RAGEngine
from src.utils.logger import logger
from config.settings import OLLAMA_MODELS

console = Console()

def format_sources(sources: list[Dict[str, Any]]) -> str:
    """ソース情報をフォーマット"""
    if not sources:
        return "No sources found"
        
    table = Table(show_header=True, header_style="bold")
    table.add_column("Source")
    table.add_column("Page")
    table.add_column("Relevance")
    
    for source in sources:
        metadata = source['metadata']
        table.add_row(
            metadata.get('source', 'Unknown'),
            str(metadata.get('page', 'N/A')),
            f"{source.get('relevance', 0):.2f}"
        )
    
    return table

def display_response(
    response: str,
    sources: list[Dict[str, Any]],
    confidence: float
):
    """応答を表示"""
    # 回答を表示
    console.print("\n[bold green]Answer:[/bold green]")
    console.print(Panel(Markdown(response)))
    
    # 信頼度を表示
    color = "green" if confidence > 0.8 else "yellow" if confidence > 0.5 else "red"
    console.print(
        f"\n[bold]Confidence:[/bold] [{color}]{confidence:.2f}[/{color}]"
    )
    
    # ソース情報を表示
    console.print("\n[bold]Sources:[/bold]")
    console.print(format_sources(sources))

async def chat_loop(
    rag_engine: RAGEngine,
    temperature: float = 0.7,
    model: Optional[str] = None
):
    """対話ループ"""
    console.print(
        Panel.fit(
            "[bold]RAG Chat Demo[/bold]\n"
            "Type your questions and press Enter. "
            "Type 'exit' to quit.",
            border_style="blue"
        )
    )
    
    while True:
        try:
            # 質問の入力
            query = Prompt.ask("\n[bold blue]Question")
            
            if query.lower() in ['exit', 'quit']:
                break
            
            with console.status("[bold yellow]Thinking..."):
                # 回答を生成
                result = await rag_engine.process_query(
                    query,
                    metadata={
                        'temperature': temperature,
                        'model': model or OLLAMA_MODELS['general']
                    }
                )
            
            # 結果を表示
            display_response(
                result.text,
                result.sources,
                result.confidence
            )
            
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted by user[/yellow]")
            break
            
        except Exception as e:
            console.print(f"\n[bold red]Error:[/bold red] {str(e)}")
            logger.error(f"Chat error: {e}")

def main():
    parser = argparse.ArgumentParser(
        description="Interactive RAG Chat Demo"
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.7,
        help="Temperature for response generation"
    )
    parser.add_argument(
        "--model",
        help="Model name to use for generation"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug output"
    )
    
    args = parser.parse_args()
    
    try:
        # RAGエンジンの初期化
        rag_engine = RAGEngine()
        
        # メインループを実行
        asyncio.run(
            chat_loop(
                rag_engine,
                temperature=args.temperature,
                model=args.model
            )
        )
        
    except Exception as e:
        console.print(f"\n[bold red]Fatal error:[/bold red] {str(e)}")
        if args.debug:
            console.print_exception()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())