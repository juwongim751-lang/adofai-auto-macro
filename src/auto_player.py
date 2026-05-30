"""
자동 플레이어 모듈 - .adofai 레벨 파일의 타이밍 정보에 따라 자동으로 키를 입력합니다.
"""

import sys
import time
import threading

from src.level_parser import LevelData, TileHit

# pynput은 실제 키 입력 시에만 필요하므로 지연 임포트한다.
# (파싱/테스트는 X 디스플레이 없는 환경에서도 동작해야 한다.)

# 특수키 이름 → pynput Key 속성 이름
SPECIAL_KEY_NAMES = {
    "space": "space",
    "enter": "enter",
    "tab": "tab",
    "shift": "shift",
    "ctrl": "ctrl",
    "alt": "alt",
    "esc": "esc",
    "up": "up",
    "down": "down",
    "left": "left",
    "right": "right",
}


class AutoPlayer:
    """.adofai 레벨의 타일 타이밍에 맞춰 자동으로 키를 입력하는 클래스."""

    def __init__(self, keys="space", min_gap_ms: float = 16.0, offset_ms: float = 0.0,
                 tap_hold_ms: float = 24.0):
        """
        Args:
            keys: 입력할 키. 단일 문자열("space") 또는 여러 키 목록
                  (["w", "f", "o", "j"]). 여러 개면 타일마다 번갈아 눌러
                  같은 키 연타를 피한다 (게임의 채터 블로커 회피).
            min_gap_ms: 연속 입력 사이의 최소 간격(ms). 같은 시각에 몰린
                  타일(동타)을 같은 렌더 프레임에 같이 누르면 게임이 한 번만
                  인식하므로, 최소 이 간격만큼 벌려 각 입력이 별도 프레임에
                  들어가게 한다 (기본 16ms ≈ 60fps 한 프레임).
        """
        self.keyboard = None  # 첫 입력 시 지연 생성
        self.keys = self._normalize_keys(keys)
        self._key_idx = 0

        self._running = False
        self._thread: threading.Thread | None = None
        self._level: LevelData | None = None
        self._current_tile: int = 0
        self._start_time: float = 0.0
        self._progress_callback = None
        self._held_key = None  # 롱노트로 누른 채 유지 중인 키
        self._held_release_perf: float | None = None  # 떼야 하는 perf 시각
        self._start_index: int = 0  # 이 타일부터 재생 (구간 연습용)
        self._min_press_gap_s: float = max(0.0, min_gap_ms) / 1000.0
        self._last_press_perf: float = float("-inf")  # 마지막 입력 시각(동타 분산용)
        self._offset_s: float = offset_ms / 1000.0  # 전역 타이밍 보정(+늦게/-일찍)
        # 각 입력을 즉시 떼지 않고 잠깐 눌러 유지했다가 떼서 인식률을 높인다.
        # 타이밍이 밀리지 않도록 비동기로(대기 루프에서) 떼며, 다른 키들과
        # 잠깐 동시에 눌려도 ADOFAI는 각 키의 누름 순간만 한 번씩 인식한다.
        self._tap_hold_s: float = max(0.0, tap_hold_ms) / 1000.0
        self._pending_releases: list = []  # [(key, 떼야_할_perf_시각)]

    def set_start_index(self, idx: int):
        """재생을 시작할 타일 인덱스를 설정합니다 (구간 연습용)."""
        self._start_index = max(0, int(idx))

    def load_level(self, level: LevelData):
        """레벨 데이터를 로드합니다."""
        self._level = level
        self._current_tile = 0

    def set_progress_callback(self, callback):
        """진행 상황 콜백을 설정합니다. callback(tile_index, total_tiles, time_ms)"""
        self._progress_callback = callback

    def _normalize_keys(self, keys) -> list:
        """키 설정을 정규화된 문자열 리스트로 변환합니다 (빈 값 제거, 소문자)."""
        if isinstance(keys, str):
            keys = [keys]
        normalized = []
        for k in keys:
            k = str(k).strip().lower()
            if not k:
                continue
            normalized.append(k)
        return normalized or ["space"]

    def _get_keyboard(self):
        """pynput Controller를 지연 생성합니다."""
        if self.keyboard is None:
            from pynput.keyboard import Controller
            self.keyboard = Controller()
        return self.keyboard

    @staticmethod
    def _resolve_key(name):
        """키 이름을 pynput이 받는 값으로 변환 (일반 문자는 그대로)."""
        if name in SPECIAL_KEY_NAMES:
            from pynput.keyboard import Key
            return getattr(Key, SPECIAL_KEY_NAMES[name])
        return name

    def _next_key(self):
        """다음 키를 순환해서 반환합니다 (resolve된 값)."""
        name = self.keys[self._key_idx % len(self.keys)]
        self._key_idx += 1
        return self._resolve_key(name)

    def _press_key(self):
        """다음 키를 누릅니다 (여러 키면 순환). 즉시 떼지 않고 짧게 유지 후 비동기로 뗌."""
        key = self._next_key()
        kb = self._get_keyboard()
        self._release_key_now(key)  # 같은 키가 아직 눌린 상태면 깔끔한 누름 엣지를 위해 먼저 뗌
        kb.press(key)
        if self._tap_hold_s > 0:
            self._pending_releases.append((key, time.perf_counter() + self._tap_hold_s))
        else:
            kb.release(key)

    def _press_hold(self):
        """다음 키를 누른 채로 유지합니다 (떼지 않음). 유지 중인 키를 반환."""
        key = self._next_key()
        kb = self._get_keyboard()
        self._release_key_now(key)
        kb.press(key)
        return key

    def _release_key_now(self, key):
        """대기 중인 짧은-유지 입력 중 해당 키가 있으면 지금 바로 뗍니다."""
        if not self._pending_releases:
            return
        remaining = []
        released = False
        for k, t in self._pending_releases:
            if k == key and not released:
                self._get_keyboard().release(k)
                released = True
            else:
                remaining.append((k, t))
        self._pending_releases = remaining

    def _flush_releases(self, now: float):
        """유지 시간이 지난 입력들을 뗍니다 (대기 루프에서 주기적으로 호출)."""
        if not self._pending_releases:
            return
        remaining = []
        for k, t in self._pending_releases:
            if t <= now:
                self._get_keyboard().release(k)
            else:
                remaining.append((k, t))
        self._pending_releases = remaining

    def _release_all_pending(self):
        """대기 중인 모든 짧은-유지 입력을 즉시 뗍니다."""
        for k, _t in self._pending_releases:
            self._get_keyboard().release(k)
        self._pending_releases = []

    def _release_hold(self):
        """유지 중인 롱노트 키를 뗍니다."""
        if self._held_key is not None:
            self._get_keyboard().release(self._held_key)
            self._held_key = None
            self._held_release_perf = None

    def _begin_high_res_timer(self):
        """Windows의 기본 타이머 해상도(~15.6ms)를 1ms로 올려 sleep 정밀도를 높인다.

        이게 없으면 time.sleep(1ms)가 실제로 최대 ~15ms까지 자버려 입력이
        전체적으로 조금씩 늦고(살짝 느림) 타일을 간헐적으로 놓치게 된다.
        """
        self._winmm = None
        if not sys.platform.startswith("win"):
            return
        try:
            import ctypes
            winmm = ctypes.WinDLL("winmm")
            winmm.timeBeginPeriod(1)
            self._winmm = winmm
        except Exception:
            self._winmm = None

    def _end_high_res_timer(self):
        """올렸던 타이머 해상도를 다시 내린다 (시스템 전원 절약)."""
        if getattr(self, "_winmm", None) is not None:
            try:
                self._winmm.timeEndPeriod(1)
            except Exception:
                pass
            self._winmm = None

    def _wait_precise(self, target_time: float):
        """정밀한 타이밍으로 대기합니다 (busy-wait). 대기 중 짧은-유지 입력도 제때 뗌."""
        while self._running:
            now = time.perf_counter()
            if self._pending_releases:
                self._flush_releases(now)
            remaining = target_time - now
            if remaining <= 0:
                break
            if remaining > 0.002:
                time.sleep(0.001)

    def _play_loop(self):
        """레벨 타이밍에 맞춰 키를 입력하는 메인 루프."""
        if not self._level or not self._level.tiles:
            return

        tiles = self._level.tiles

        # 재생 시작 타일 (구간 연습 시 중간부터). 그 타일의 시간을 기준점으로.
        start_i = min(max(0, self._start_index), len(tiles) - 1)
        first_tile_time_ms = tiles[start_i].time_ms
        self._start_time = time.perf_counter() - (first_tile_time_ms / 1000.0)

        for i, tile in enumerate(tiles):
            if not self._running:
                break

            self._current_tile = i

            # 시작 타일 이전(그리고 floor 0 시작 타일)은 건너뜀
            if i <= start_i:
                continue

            # 목표 시간까지 대기 (offset으로 전체를 앞/뒤로 보정)
            target_perf = self._start_time + (tile.time_ms / 1000.0) + self._offset_s
            self._wait_precise(target_perf)

            if not self._running:
                break

            # 유지 중인 롱노트가 떼야 할 시각을 지났으면 뗀다
            if self._held_release_perf is not None and time.perf_counter() >= self._held_release_perf:
                self._release_hold()

            # 게임이 자동으로 치는 구간(AutoPlayTiles)은 누르지 않음
            if getattr(tile, "auto", False):
                continue

            # 롱노트 유지 중 지나가는 타일은 따로 누르지 않음
            if getattr(tile, "hold_covered", False):
                continue

            # 동타(같은 시각에 몰린 타일) 분산: 직전 입력과 최소 간격을 둬서
            # 두 입력이 같은 렌더 프레임에 들어가 한 번만 인식되는 것을 방지한다.
            if self._min_press_gap_s > 0:
                min_perf = self._last_press_perf + self._min_press_gap_s
                if min_perf > time.perf_counter():
                    self._wait_precise(min_perf)
                    if not self._running:
                        break

            # 키 입력
            hold_ms = getattr(tile, "hold_ms", 0.0)
            if hold_ms and hold_ms > 0:
                # 진행 중인 홀드가 있으면 먼저 떼고 새로 누른다
                self._release_hold()
                self._held_key = self._press_hold()
                self._held_release_perf = self._start_time + ((tile.time_ms + hold_ms) / 1000.0)
            else:
                self._press_key()

            self._last_press_perf = time.perf_counter()

            # 진행 상황 콜백
            if self._progress_callback:
                elapsed_ms = (time.perf_counter() - self._start_time) * 1000
                self._progress_callback(i, len(tiles), elapsed_ms)

        # 남은 홀드 키/짧은-유지 입력 정리
        self._release_hold()
        self._release_all_pending()

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
        self._last_press_perf = float("-inf")
        self._pending_releases = []
        self._begin_high_res_timer()
        self._thread = threading.Thread(target=self._play_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """자동 플레이를 중지합니다."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        self._end_high_res_timer()

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
