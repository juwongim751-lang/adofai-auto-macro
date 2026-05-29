"""
KPS 인식 모듈 - OCR을 이용하여 화면에서 KPS 수치를 읽어냅니다.
"""

import re
import cv2
import numpy as np
import pytesseract


class KPSReader:
    """화면 캡처에서 KPS 수치를 OCR로 인식하는 클래스."""

    def __init__(self, tesseract_cmd: str | None = None):
        """
        Args:
            tesseract_cmd: tesseract 실행 파일 경로 (None이면 기본 경로 사용).
        """
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    def preprocess(self, image: np.ndarray) -> np.ndarray:
        """OCR 정확도를 높이기 위해 이미지를 전처리합니다."""
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

        # 밝은 텍스트를 위한 반전
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # 어두운 배경에 밝은 텍스트인 경우 반전
        if np.mean(thresh) > 127:
            thresh = cv2.bitwise_not(thresh)

        # 노이즈 제거
        kernel = np.ones((2, 2), np.uint8)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)

        # 확대 (OCR 정확도 향상)
        thresh = cv2.resize(thresh, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)

        return thresh

    def read_kps(self, image: np.ndarray) -> float | None:
        """
        이미지에서 KPS 수치를 읽어냅니다.

        Args:
            image: 캡처된 KPS 영역 이미지 (numpy 배열).

        Returns:
            인식된 KPS 값 (float), 인식 실패 시 None.
        """
        processed = self.preprocess(image)

        config = "--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789.KPSkps"
        text = pytesseract.image_to_string(processed, config=config).strip()

        return self._parse_kps(text)

    def _parse_kps(self, text: str) -> float | None:
        """OCR 텍스트에서 KPS 숫자를 추출합니다."""
        # "KPS: 12.5" 또는 "12.5 KPS" 또는 "12.5" 패턴 매칭
        patterns = [
            r"[Kk][Pp][Ss]\s*[:\s]\s*(\d+\.?\d*)",
            r"(\d+\.?\d*)\s*[Kk][Pp][Ss]",
            r"(\d+\.?\d*)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    value = float(match.group(1))
                    if 0 < value < 100:  # 합리적인 KPS 범위
                        return value
                except ValueError:
                    continue

        return None
