"""
얼불춤(A Dance of Fire and Ice) 자동 매크로
화면의 KPS 표시를 OCR로 읽어 자동으로 키를 입력합니다.

사용법:
    python main.py                  # 기본 설정으로 실행
    python main.py --config my.yaml # 사용자 설정 파일 사용
    python main.py --set-region     # 캡처 영역 직접 설정 모드
"""

import argparse
import sys
import time
import yaml
from pathlib import Path
from pynput import keyboard

from src.screen_capture import ScreenCapture
from src.kps_reader import KPSReader
from src.auto_player import AutoPlayer
from src.overlay import StatusOverlay


def load_config(path: str = "config.yaml") -> dict:
    """설정 파일을 로드합니다."""
    config_path = Path(path)
    if not config_path.exists():
        print(f"[!] 설정 파일을 찾을 수 없습니다: {path}")
        print("[*] 기본 설정으로 실행합니다.")
        return {}

    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def region_setup_mode(capture: ScreenCapture):
    """캡처 영역을 사용자가 직접 설정하는 모드."""
    print("=" * 50)
    print("  KPS 캡처 영역 설정 모드")
    print("=" * 50)
    print()
    print("얼불춤을 실행한 상태에서 KPS가 표시되는 영역의 좌표를 입력하세요.")
    print("화면 좌측 상단이 (0, 0)입니다.")
    print()

    try:
        left = int(input("  X 좌표 (left): "))
        top = int(input("  Y 좌표 (top): "))
        width = int(input("  너비 (width): "))
        height = int(input("  높이 (height): "))
    except (ValueError, EOFError):
        print("[!] 잘못된 입력입니다.")
        return

    capture.set_region(left, top, width, height)
    print(f"\n[*] 캡처 영역 설정됨: ({left}, {top}, {width}x{height})")

    # 테스트 캡처
    img = capture.capture()
    print(f"[*] 테스트 캡처 완료: {img.shape}")


class MacroController:
    """매크로 전체 흐름을 제어하는 메인 컨트롤러."""

    def __init__(self, config: dict):
        self.config = config
        self.running = False
        self.macro_active = False

        # 모듈 초기화
        capture_cfg = config.get("capture", {})
        macro_cfg = config.get("macro", {})
        ocr_cfg = config.get("ocr", {})
        hotkey_cfg = config.get("hotkeys", {})

        # 캡처 영역 설정
        region = capture_cfg.get("region", "auto")
        self.capture = ScreenCapture(region=None if region == "auto" else region)

        # OCR 리더
        tesseract_cmd = ocr_cfg.get("tesseract_cmd", "") or None
        self.reader = KPSReader(tesseract_cmd=tesseract_cmd)

        # 자동 플레이어
        self.player = AutoPlayer(
            key=macro_cfg.get("key", "space"),
            min_kps=macro_cfg.get("min_kps", 0.5),
            max_kps=macro_cfg.get("max_kps", 30.0),
        )

        # 오버레이
        overlay_cfg = config.get("overlay", {})
        self.overlay = StatusOverlay() if overlay_cfg.get("enabled", True) else None

        # 캡처 주기
        self.capture_interval = capture_cfg.get("interval", 0.05)

        # 핫키
        self.toggle_key = hotkey_cfg.get("toggle", "f6")
        self.quit_key = hotkey_cfg.get("quit", "f8")
        self.reset_key = hotkey_cfg.get("reset_region", "f7")

    def _on_key_press(self, key):
        """핫키 처리."""
        try:
            key_name = key.name if hasattr(key, "name") else str(key)
        except AttributeError:
            return

        if key_name == self.toggle_key:
            self._toggle_macro()
        elif key_name == self.quit_key:
            self._quit()
        elif key_name == self.reset_key:
            region_setup_mode(self.capture)

    def _toggle_macro(self):
        """매크로 시작/중지 토글."""
        if self.macro_active:
            self.macro_active = False
            self.player.stop()
            status = "[매크로 중지됨]"
        else:
            self.macro_active = True
            self.player.start()
            status = "[매크로 활성화]"

        print(f"\n{status}")
        if self.overlay:
            self.overlay.update(status)

    def _quit(self):
        """프로그램 종료."""
        print("\n[*] 프로그램을 종료합니다...")
        self.running = False
        self.player.stop()
        if self.overlay:
            self.overlay.stop()

    def run(self):
        """메인 루프."""
        print("=" * 50)
        print("  얼불춤 자동 매크로 (ADOFAI Auto Macro)")
        print("=" * 50)
        print()
        print(f"  [F6] 매크로 시작/중지  (현재 키: {self.toggle_key.upper()})")
        print(f"  [F7] 캡처 영역 재설정  (현재 키: {self.reset_key.upper()})")
        print(f"  [F8] 프로그램 종료      (현재 키: {self.quit_key.upper()})")
        print()
        print(f"  입력 키: {self.config.get('macro', {}).get('key', 'space')}")
        print(f"  캡처 주기: {self.capture_interval}초")
        print()
        print("[*] 대기 중... F6을 눌러 매크로를 시작하세요.")
        print()

        # 오버레이 시작
        if self.overlay:
            self.overlay.start()

        # 핫키 리스너 시작
        listener = keyboard.Listener(on_press=self._on_key_press)
        listener.start()

        self.running = True
        consecutive_failures = 0

        try:
            while self.running:
                if not self.macro_active:
                    time.sleep(0.1)
                    continue

                try:
                    # 화면 캡처
                    image = self.capture.capture()

                    # KPS 인식
                    kps = self.reader.read_kps(image)

                    if kps is not None:
                        consecutive_failures = 0
                        self.player.update_kps(kps)
                        status = f"KPS: {kps:.1f} | 활성"
                        print(f"\r  {status}    ", end="", flush=True)
                    else:
                        consecutive_failures += 1
                        if consecutive_failures > 20:
                            status = "KPS 인식 실패 - 영역 확인 필요"
                            print(f"\r  [!] {status}    ", end="", flush=True)

                    if self.overlay:
                        self.overlay.update(status)

                except Exception as e:
                    print(f"\n[!] 오류: {e}")

                time.sleep(self.capture_interval)

        except KeyboardInterrupt:
            pass
        finally:
            self._quit()
            listener.stop()
            print("[*] 종료 완료.")


def main():
    parser = argparse.ArgumentParser(
        description="얼불춤(ADOFAI) 자동 매크로 - KPS 기반 자동 키 입력"
    )
    parser.add_argument(
        "--config", "-c",
        default="config.yaml",
        help="설정 파일 경로 (기본: config.yaml)",
    )
    parser.add_argument(
        "--set-region",
        action="store_true",
        help="캡처 영역 설정 모드로 실행",
    )
    args = parser.parse_args()

    config = load_config(args.config)

    if args.set_region:
        capture = ScreenCapture()
        region_setup_mode(capture)
        return

    controller = MacroController(config)
    controller.run()


if __name__ == "__main__":
    main()
