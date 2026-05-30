"""AutoPlayer 키 순환 및 자동재생 타일 건너뛰기 검증.

pynput/X 디스플레이 없이도 돌도록 가짜 keyboard를 주입한다.
일반 문자 키는 pynput을 전혀 부르지 않으므로 헤드리스 CI에서도 통과한다.
"""

import pytest

from src.auto_player import AutoPlayer
from src.level_parser import LevelData, TileHit


class _Recorder:
    """pynput Controller 대체: 눌린 키만 기록."""
    def __init__(self):
        self.pressed = []

    def press(self, key):
        self.pressed.append(key)

    def release(self, key):
        pass


def test_single_key():
    ap = AutoPlayer(keys="a")
    rec = _Recorder()
    ap.keyboard = rec
    for _ in range(3):
        ap._press_key()
    assert rec.pressed == ["a", "a", "a"]


def test_qwertyuiop_cycle():
    keys = ["q", "w", "e", "r", "t", "y", "u", "i", "o", "p"]
    ap = AutoPlayer(keys=keys)
    rec = _Recorder()
    ap.keyboard = rec
    for _ in range(12):
        ap._press_key()
    assert rec.pressed[:10] == keys
    assert rec.pressed[10:] == ["q", "w"]


def test_normalize_filters_blanks():
    ap = AutoPlayer(keys=["q", " ", "w", ""])
    assert ap.keys == ["q", "w"]


def test_normalize_lowercases():
    ap = AutoPlayer(keys=["Q", "W", "E"])
    assert ap.keys == ["q", "w", "e"]


def test_empty_keys_fallback_to_space():
    ap = AutoPlayer(keys=[])
    assert ap.keys == ["space"]


def test_special_key_resolves_to_pynput():
    try:
        from pynput.keyboard import Key
    except ImportError:
        pytest.skip("pynput backend unavailable (no display)")
    assert AutoPlayer._resolve_key("space") == Key.space
    assert AutoPlayer._resolve_key("a") == "a"


def test_play_loop_skips_auto_tiles():
    """auto=True 타일은 키를 누르지 않고, 일반 타일만 누른다."""
    lvl = LevelData(bpm=120, offset=0)
    lvl.tiles = [
        TileHit(index=0, time_ms=0, bpm=120, angle=0),
        TileHit(index=1, time_ms=1, bpm=120, angle=180),
        TileHit(index=2, time_ms=2, bpm=120, angle=180, auto=True),
        TileHit(index=3, time_ms=3, bpm=120, angle=180),
    ]
    ap = AutoPlayer(keys=["a", "b", "c", "d"])
    rec = _Recorder()
    ap.keyboard = rec
    ap.load_level(lvl)
    ap._running = True
    ap._play_loop()
    # 타일 0(시작) 건너뜀, 타일 2(auto) 건너뜀 → 타일 1,3만 입력
    assert rec.pressed == ["a", "b"]
