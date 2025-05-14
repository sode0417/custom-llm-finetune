import pytest
from pathlib import Path
import json
import time
from datetime import datetime, timezone, timedelta

from src.utils.cache_manager import CacheManager

@pytest.fixture
def test_cache_dir(tmp_path):
    """テスト用のキャッシュディレクトリを提供"""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return cache_dir

@pytest.fixture
def cache_manager(test_cache_dir):
    """テスト用のキャッシュマネージャーを提供"""
    return CacheManager(test_cache_dir, ttl_hours=1)

def test_cache_manager_initialization(test_cache_dir):
    """初期化のテスト"""
    manager = CacheManager(test_cache_dir)
    assert manager.cache_dir == test_cache_dir
    assert manager.ttl_hours == 24  # デフォルト値
    assert manager.manifest_path.exists()
    
    with open(manager.manifest_path) as f:
        manifest = json.load(f)
        assert "files" in manifest
        assert "last_cleanup" in manifest
        assert "total_size" in manifest

def test_add_to_cache(cache_manager, tmp_path):
    """キャッシュへのファイル追加テスト"""
    # テストファイルを作成
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")
    
    # キャッシュに追加
    cache_path = cache_manager.add_to_cache(
        "test_id",
        test_file,
        {"test_meta": "value"}
    )
    
    # キャッシュされたファイルを確認
    assert cache_path.exists()
    assert cache_path.read_text() == "test content"
    
    # マニフェストを確認
    with open(cache_manager.manifest_path) as f:
        manifest = json.load(f)
        assert "test_id" in manifest["files"]
        assert manifest["files"]["test_id"]["metadata"]["test_meta"] == "value"

def test_has_valid_cache(cache_manager, tmp_path):
    """キャッシュの有効性チェックテスト"""
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")
    
    # 新しいファイルを追加
    cache_manager.add_to_cache("test_id", test_file)
    assert cache_manager.has_valid_cache("test_id")
    
    # 存在しないIDのテスト
    assert not cache_manager.has_valid_cache("nonexistent_id")
    
    # TTL切れのテスト
    manager = CacheManager(tmp_path / "cache2", ttl_hours=0)
    manager.add_to_cache("test_id", test_file)
    time.sleep(1)  # 1秒待機
    assert not manager.has_valid_cache("test_id")

def test_remove_from_cache(cache_manager, tmp_path):
    """キャッシュからの削除テスト"""
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")
    
    # ファイルを追加して削除
    cache_manager.add_to_cache("test_id", test_file)
    cache_manager.remove_from_cache("test_id")
    
    # 削除の確認
    assert not cache_manager.has_valid_cache("test_id")
    with open(cache_manager.manifest_path) as f:
        manifest = json.load(f)
        assert "test_id" not in manifest["files"]

def test_clear_cache(cache_manager, tmp_path):
    """キャッシュのクリアテスト"""
    # 複数のファイルを追加
    for i in range(3):
        test_file = tmp_path / f"test{i}.txt"
        test_file.write_text(f"content {i}")
        cache_manager.add_to_cache(f"id{i}", test_file)
    
    # キャッシュをクリア
    cache_manager.clear_cache()
    
    # クリア結果を確認
    with open(cache_manager.manifest_path) as f:
        manifest = json.load(f)
        assert len(manifest["files"]) == 0
        assert manifest["total_size"] == 0
    
    # キャッシュディレクトリ内のファイルを確認
    cache_files = list(cache_manager.cache_dir.glob("*.txt"))
    assert len(cache_files) == 0

def test_cache_size_limit(tmp_path):
    """キャッシュサイズ制限のテスト"""
    # 1MBの制限でキャッシュマネージャーを作成
    manager = CacheManager(tmp_path / "cache", ttl_hours=1, max_size_mb=1)
    
    # 約0.5MBのファイルを2つ作成
    for i in range(2):
        test_file = tmp_path / f"test{i}.txt"
        test_file.write_bytes(b"0" * 500_000)  # 約0.5MB
        manager.add_to_cache(f"id{i}", test_file)
    
    # 3つ目のファイルを追加（最も古いファイルが削除されるはず）
    test_file = tmp_path / "test2.txt"
    test_file.write_bytes(b"0" * 500_000)
    manager.add_to_cache("id2", test_file)
    
    # キャッシュサイズを確認
    with open(manager.manifest_path) as f:
        manifest = json.load(f)
        assert manifest["total_size"] < 1024 * 1024  # 1MB未満
        assert len(manifest["files"]) == 2  # 2つのファイルのみ

def test_concurrent_access(cache_manager, tmp_path):
    """並行アクセスのテスト"""
    import threading
    
    def add_file(id_num):
        test_file = tmp_path / f"test{id_num}.txt"
        test_file.write_text(f"content {id_num}")
        cache_manager.add_to_cache(f"id{id_num}", test_file)
    
    # 複数のスレッドでファイルを追加
    threads = [
        threading.Thread(target=add_file, args=(i,))
        for i in range(5)
    ]
    
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    # 結果を確認
    with open(cache_manager.manifest_path) as f:
        manifest = json.load(f)
        assert len(manifest["files"]) == 5