"""
화면 캡처 모듈 - 얼불춤 화면에서 KPS 영역을 캡처합니다.
"""

import mss
import numpy as np
from PIL import Image


class ScreenCapture:
    """게임 화면에서 KPS 표시 영역을 캡처하는 클래스."""

    def __init__(self, region: dict | None = None):
        """
        Args:
            region: 캡처할 화면 영역 {"left": x, "top": y, "width": w, "height": h}.
                    None이면 자동 감지를 시도합니다.
        """
        self.sct = mss.mss()
        self.region = region or self._default_region()

    def _default_region(self) -> dict:
        """기본 KPS 영역 (화면 오른쪽 상단)."""
        monitor = self.sct.monitors[1]
        return {
            "left": monitor["width"] - 300,
            "top": 10,
            "width": 280,
            "height": 60,
        }

    def set_region(self, left: int, top: int, width: int, height: int):
        """캡처 영역을 수동으로 설정합니다."""
        self.region = {
            "left": left,
            "top": top,
            "width": width,
            "height": height,
        }

    def capture(self) -> np.ndarray:
        """현재 설정된 영역을 캡처하여 numpy 배열로 반환합니다."""
        screenshot = self.sct.grab(self.region)
        img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
        return np.array(img)

    def capture_full_screen(self) -> np.ndarray:
        """전체 화면을 캡처합니다 (영역 설정용)."""
        monitor = self.sct.monitors[1]
        screenshot = self.sct.grab(monitor)
        img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
        return np.array(img)
