"""AutoPlayer 키 순환 및 자동재생 타일 건너뛰기 검증.

pynput/X 디스플레이 없이도 돌도록 가짜 keyboard를 주입한다.
일반 문자 키는 pynput을 전혀 부르지 않으므로 헤드리스 CI에서도 통과한다.
"""

import pytest

from src.auto_player import AutoPlayer
from src.level_parser import LevelData, TileHit


class _Recorder:
    """pynput Controller 대체: 누름/뗌을 순서대로 기록."""
    def __init__(self):
        self.pressed = []
        self.released = []
        self.log = []  # ("press"|"release", key) 순서 기록

    def press(self, key):
        self.pressed.append(key)
        self.log.append(("press", key))

    def release(self, key):
        self.released.append(key)
        self.log.append(("release", key))


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


def test_play_loop_simultaneous_tiles_all_pressed():
    """동타(같은 시각 타일)도 전부 입력되어야 한다 (한 번만 인식되는 문제 방지)."""
    lvl = LevelData(bpm=120, offset=0)
    # 타일 1,2,3이 모두 같은 시각(0ms)에 몰린 '동타' 구간
    lvl.tiles = [
        TileHit(index=0, time_ms=0, bpm=120, angle=0),
        TileHit(index=1, time_ms=0, bpm=120, angle=180),
        TileHit(index=2, time_ms=0, bpm=120, angle=180),
        TileHit(index=3, time_ms=0, bpm=120, angle=180),
    ]
    ap = AutoPlayer(keys=["a", "b", "c", "d"], min_gap_ms=5.0)
    rec = _Recorder()
    ap.keyboard = rec
    ap.load_level(lvl)
    ap._running = True
    ap._play_loop()
    # 세 동타 타일 모두 서로 다른 키로 입력됨 (하나도 누락 안 됨)
    assert rec.pressed == ["a", "b", "c"]


def test_min_gap_spaces_out_presses():
    """min_gap 설정 시 연속 입력이 최소 간격만큼 떨어져 발생한다 (실시간 측정)."""
    import time as _time

    lvl = LevelData(bpm=120, offset=0)
    lvl.tiles = [
        TileHit(index=0, time_ms=0, bpm=120, angle=0),
        TileHit(index=1, time_ms=0, bpm=120, angle=180),
        TileHit(index=2, time_ms=0, bpm=120, angle=180),
    ]
    ap = AutoPlayer(keys=["a", "b"], min_gap_ms=20.0)
    press_times = []
    rec = _Recorder()
    orig_press = ap._press_key

    def spy():
        press_times.append(_time.perf_counter())
        orig_press()

    ap.keyboard = rec
    ap._press_key = spy
    ap.load_level(lvl)
    ap._running = True
    ap._play_loop()
    assert len(press_times) == 2
    # 두 입력은 최소 20ms(0.02s) 이상 벌어져야 한다 (약간의 오차 허용)
    assert press_times[1] - press_times[0] >= 0.018


def test_play_loop_start_index_skips_earlier_tiles():
    """--start-tile: 지정 인덱스 이전 타일은 누르지 않는다."""
    lvl = LevelData(bpm=120, offset=0)
    lvl.tiles = [
        TileHit(index=0, time_ms=0, bpm=120, angle=0),
        TileHit(index=1, time_ms=0, bpm=120, angle=180),
        TileHit(index=2, time_ms=0, bpm=120, angle=180),
        TileHit(index=3, time_ms=0, bpm=120, angle=180),
    ]
    ap = AutoPlayer(keys=["a", "b", "c", "d"])
    rec = _Recorder()
    ap.keyboard = rec
    ap.set_start_index(2)
    ap.load_level(lvl)
    ap._running = True
    ap._play_loop()
    # 타일 0,1,2는 건너뛰고 타일 3만 입력 (키 순환은 처음부터)
    assert rec.pressed == ["a"]


def test_play_loop_hold_press_and_release():
    """롱노트(hold) 타일은 누른 채 유지하고, 유지 중 타일은 안 누르고, 끝에 뗀다."""
    lvl = LevelData(bpm=120, offset=0)
    lvl.tiles = [
        TileHit(index=0, time_ms=0, bpm=120, angle=0),
        TileHit(index=1, time_ms=0, bpm=120, angle=180),                       # 일반
        TileHit(index=2, time_ms=0, bpm=120, angle=180, hold_ms=0.0001),       # 홀드 시작
        TileHit(index=3, time_ms=0, bpm=120, angle=180, hold_covered=True),    # 유지 중
        TileHit(index=4, time_ms=0, bpm=120, angle=180),                       # 일반
    ]
    ap = AutoPlayer(keys=["a", "b", "c", "d"])
    rec = _Recorder()
    ap.keyboard = rec
    ap.load_level(lvl)
    ap._running = True
    ap._play_loop()
    # 일반(a) → 홀드(b, 유지) → 유지타일 스킵 → 일반(c)
    assert rec.pressed == ["a", "b", "c"]
    # 홀드 키 b는 c가 눌리기 전에 떼져야 한다
    assert ("release", "b") in rec.log
    assert rec.log.index(("release", "b")) < rec.log.index(("press", "c"))
    # 끝나면 유지 중인 키가 없어야 한다
    assert ap._held_key is None
