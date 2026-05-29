"""
자동 플레이어 모듈 - KPS에 맞춰 자동으로 키를 입력합니다.
"""

import time
import threading
from pynput.keyboard import Controller, Key


class AutoPlayer:
    """KPS 값에 따라 자동으로 키를 입력하는 클래스."""

    # 얼불춤 기본 조작키
    KEY_MAP = {
        "space": Key.space,
        "d": "d",
        "f": "f",
        "j": "j",
        "k": "k",
    }

    def __init__(self, key: str = "space", min_kps: float = 0.5, max_kps: float = 30.0):
        """
        Args:
            key: 입력할 키 (기본: space).
            min_kps: 최소 KPS 임계값. 이 아래면 입력하지 않음.
            max_kps: 최대 KPS 제한.
        """
        self.keyboard = Controller()
        self.key = self.KEY_MAP.get(key, key)
        self.min_kps = min_kps
        self.max_kps = max_kps

        self._running = False
        self._thread: threading.Thread | None = None
        self._current_kps: float = 0.0
        self._lock = threading.Lock()

    def update_kps(self, kps: float):
        """현재 KPS 값을 업데이트합니다."""
        with self._lock:
            self._current_kps = min(kps, self.max_kps)

    def _get_kps(self) -> float:
        with self._lock:
            return self._current_kps

    def _press_key(self):
        """키를 한 번 누릅니다."""
        self.keyboard.press(self.key)
        self.keyboard.release(self.key)

    def _play_loop(self):
        """KPS에 맞춰 키를 입력하는 메인 루프."""
        while self._running:
            kps = self._get_kps()

            if kps < self.min_kps:
                time.sleep(0.01)
                continue

            interval = 1.0 / kps
            self._press_key()

            # 정밀한 타이밍을 위한 busy-wait
            target = time.perf_counter() + interval
            while time.perf_counter() < target and self._running:
                remaining = target - time.perf_counter()
                if remaining > 0.002:
                    time.sleep(0.001)

    def start(self):
        """자동 플레이를 시작합니다."""
        if self._running:
            return

        self._running = True
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
