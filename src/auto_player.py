"""
자동 플레이어 모듈 - .adofai 레벨 파일의 타이밍 정보에 따라 자동으로 키를 입력합니다.
"""

import time
import threading
from pynput.keyboard import Controller, Key

from src.level_parser import LevelData, TileHit


class AutoPlayer:
    """.adofai 레벨의 타일 타이밍에 맞춰 자동으로 키를 입력하는 클래스."""

    SPECIAL_KEYS = {
        "space": Key.space,
    }

    def __init__(self, keys="space"):
        """
        Args:
            keys: 입력할 키. 단일 문자열("space") 또는 여러 키 목록
                  (["w", "f", "o", "j"]). 여러 개면 타일마다 번갈아 눌러
                  같은 키 연타를 피한다 (게임의 채터 블로커 회피).
        """
        self.keyboard = Controller()
        self.keys = self._normalize_keys(keys)
        self._key_idx = 0

        self._running = False
        self._thread: threading.Thread | None = None
        self._level: LevelData | None = None
        self._current_tile: int = 0
        self._start_time: float = 0.0
        self._progress_callback = None

    def load_level(self, level: LevelData):
        """레벨 데이터를 로드합니다."""
        self._level = level
        self._current_tile = 0

    def set_progress_callback(self, callback):
        """진행 상황 콜백을 설정합니다. callback(tile_index, total_tiles, time_ms)"""
        self._progress_callback = callback

    def _normalize_keys(self, keys) -> list:
        """키 설정을 pynput이 쓸 수 있는 리스트로 변환합니다."""
        if isinstance(keys, str):
            keys = [keys]
        normalized = []
        for k in keys:
            k = str(k).strip().lower()
            if not k:
                continue
            normalized.append(self.SPECIAL_KEYS.get(k, k))
        return normalized or [Key.space]

    def _press_key(self):
        """다음 키를 한 번 누릅니다 (여러 키면 순환)."""
        key = self.keys[self._key_idx % len(self.keys)]
        self._key_idx += 1
        self.keyboard.press(key)
        self.keyboard.release(key)

    def _wait_precise(self, target_time: float):
        """정밀한 타이밍으로 대기합니다 (busy-wait)."""
        while self._running:
            remaining = target_time - time.perf_counter()
            if remaining <= 0:
                break
            if remaining > 0.005:
                time.sleep(0.001)

    def _play_loop(self):
        """레벨 타이밍에 맞춰 키를 입력하는 메인 루프."""
        if not self._level or not self._level.tiles:
            return

        tiles = self._level.tiles

        # 첫 타일의 시간을 기준으로 시작 시간 계산
        first_tile_time_ms = tiles[0].time_ms
        self._start_time = time.perf_counter() - (first_tile_time_ms / 1000.0)

        for i, tile in enumerate(tiles):
            if not self._running:
                break

            self._current_tile = i

            # 미드스핀 타일은 건너뛰지 않고 입력
            # floor 0 (시작 타일)은 건너뜀
            if i == 0:
                continue

            # 목표 시간까지 대기
            target_perf = self._start_time + (tile.time_ms / 1000.0)
            self._wait_precise(target_perf)

            if not self._running:
                break

            # 게임이 자동으로 치는 구간(AutoPlayTiles)은 누르지 않음
            if getattr(tile, "auto", False):
                continue

            # 키 입력
            self._press_key()

            # 진행 상황 콜백
            if self._progress_callback:
                elapsed_ms = (time.perf_counter() - self._start_time) * 1000
                self._progress_callback(i, len(tiles), elapsed_ms)

        # 레벨 완료
        self._running = False

    def start(self):
        """자동 플레이를 시작합니다."""
        if self._running:
            return
        if not self._level:
            return

        self._running = True
        self._current_tile = 0
        self._key_idx = 0
        self._thread = threading.Thread(target=self._play_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """자동 플레이를 중지합니다."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def current_tile(self) -> int:
        return self._current_tile

    @property
    def total_tiles(self) -> int:
        if self._level:
            return len(self._level.tiles)
        return 0
