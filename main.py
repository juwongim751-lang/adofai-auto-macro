"""
얼불춤(A Dance of Fire and Ice) 자동 매크로
.adofai 레벨 파일을 파싱하여 타일 타이밍에 맞춰 자동으로 키를 입력합니다.

사용법:
    python main.py                           # 현재 플레이 중인 맵 자동 탐색
    python main.py --select                  # 탐색된 맵 목록에서 선택
    python main.py level.adofai              # 레벨 파일 직접 지정
    python main.py --key d                   # 입력 키를 d로 변경
    python main.py --delay 200               # 시작 딜레이 200ms 추가
    python main.py --info                    # 레벨 정보만 출력
"""

import argparse
import sys
import time
import threading
from pathlib import Path
from pynput import keyboard

from src.level_parser import parse_level, print_level_info, LevelData
from src.auto_player import AutoPlayer
from src.level_finder import find_current_level, select_level_interactive

try:
    from src.overlay import StatusOverlay
except ImportError:
    # tkinter 미설치 환경에서는 오버레이 없이 동작
    StatusOverlay = None


class MacroController:
    """매크로 전체 흐름을 제어하는 메인 컨트롤러."""

    def __init__(
        self,
        level: LevelData,
        key: str = "space",
        start_delay: float = 0.0,
        countdown: int = 3,
        show_overlay: bool = True,
        toggle_key: str = "f6",
        quit_key: str = "f8",
    ):
        self.level = level
        self.start_delay = start_delay
        self.countdown = countdown
        self.toggle_key = toggle_key
        self.quit_key = quit_key

        self.player = AutoPlayer(key=key)
        self.player.load_level(level)
        self.player.set_progress_callback(self._on_progress)

        self.overlay = StatusOverlay() if (show_overlay and StatusOverlay) else None
        self.running = True
        self.macro_started = False

    def _on_progress(self, tile_index: int, total_tiles: int, time_ms: float):
        """타일 진행 콜백."""
        pct = (tile_index / total_tiles) * 100
        status = f"타일 {tile_index}/{total_tiles} ({pct:.0f}%)"
        print(f"\r  {status}    ", end="", flush=True)
        if self.overlay:
            self.overlay.update(status)

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

    def _toggle_macro(self):
        """매크로 시작/중지 토글."""
        if self.player.is_running:
            self.player.stop()
            self.macro_started = False
            status = "[매크로 중지됨]"
            print(f"\n{status}")
            if self.overlay:
                self.overlay.update(status)
        else:
            self._start_with_countdown()

    def _start_with_countdown(self):
        """카운트다운 후 매크로를 시작합니다."""
        def _countdown_and_start():
            for i in range(self.countdown, 0, -1):
                if not self.running:
                    return
                status = f"[{i}초 후 시작...]"
                print(f"\r  {status}    ", end="", flush=True)
                if self.overlay:
                    self.overlay.update(status)
                time.sleep(1)

            if self.start_delay > 0:
                status = f"[딜레이 {self.start_delay}ms...]"
                print(f"\r  {status}    ", end="", flush=True)
                if self.overlay:
                    self.overlay.update(status)
                time.sleep(self.start_delay / 1000.0)

            if self.running:
                self.macro_started = True
                self.player.load_level(self.level)  # 처음부터 다시 시작
                self.player.start()
                status = "[매크로 실행 중]"
                print(f"\n{status}")
                if self.overlay:
                    self.overlay.update(status)

        t = threading.Thread(target=_countdown_and_start, daemon=True)
        t.start()

    def _quit(self):
        """프로그램 종료."""
        print("\n[*] 프로그램을 종료합니다...")
        self.running = False
        self.player.stop()
        if self.overlay:
            self.overlay.stop()

    def run(self):
        """메인 루프."""
        print()
        print("=" * 55)
        print("  얼불춤 자동 매크로 (ADOFAI Auto Macro)")
        print("  .adofai 파일 기반 자동 플레이")
        print("=" * 55)
        print()

        print_level_info(self.level)
        print()
        print(f"  [{self.toggle_key.upper()}] 매크로 시작/중지")
        print(f"  [{self.quit_key.upper()}] 프로그램 종료")
        print()
        print("[*] 게임에서 레벨을 시작한 뒤 F6을 눌러 매크로를 시작하세요.")
        print(f"[*] 카운트다운: {self.countdown}초 / 시작 딜레이: {self.start_delay}ms")
        print()

        if self.overlay:
            self.overlay.start()

        listener = keyboard.Listener(on_press=self._on_key_press)
        listener.start()

        try:
            while self.running:
                if self.macro_started and not self.player.is_running:
                    self.macro_started = False
                    status = "[레벨 완료!]"
                    print(f"\n\n{status}")
                    if self.overlay:
                        self.overlay.update(status)
                time.sleep(0.1)
        except KeyboardInterrupt:
            pass
        finally:
            self._quit()
            listener.stop()
            print("[*] 종료 완료.")


def main():
    parser = argparse.ArgumentParser(
        description="얼불춤(ADOFAI) 자동 매크로 - .adofai 파일 기반 자동 플레이"
    )
    parser.add_argument(
        "level_file",
        nargs="?",
        default=None,
        help=".adofai 레벨 파일 경로 (생략 시 현재 플레이 중인 맵 자동 탐색)",
    )
    parser.add_argument(
        "--select", "-s",
        action="store_true",
        help="탐색된 맵 목록에서 직접 선택",
    )
    parser.add_argument(
        "--dir",
        action="append",
        default=[],
        help="추가로 검색할 레벨 폴더 경로 (여러 번 지정 가능)",
    )
    parser.add_argument(
        "--key", "-k",
        default="space",
        choices=["space", "d", "f", "j", "k"],
        help="입력할 키 (기본: space)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0,
        help="시작 딜레이 (ms, 기본: 0)",
    )
    parser.add_argument(
        "--countdown",
        type=int,
        default=3,
        help="시작 카운트다운 초 (기본: 3)",
    )
    parser.add_argument(
        "--no-overlay",
        action="store_true",
        help="상태 오버레이 비활성화",
    )
    parser.add_argument(
        "--info",
        action="store_true",
        help="레벨 정보만 출력하고 종료",
    )
    parser.add_argument(
        "--toggle-key",
        default="f6",
        help="매크로 시작/중지 핫키 (기본: f6)",
    )
    parser.add_argument(
        "--quit-key",
        default="f8",
        help="프로그램 종료 핫키 (기본: f8)",
    )

    args = parser.parse_args()

    # 레벨 파일 결정: 직접 지정 > 목록 선택 > 자동 탐색
    level_path = args.level_file

    if level_path is None:
        if args.select:
            print("[*] 레벨 탐색 중...")
            selected = select_level_interactive(args.dir)
            if selected is None:
                print("[!] 레벨을 선택하지 않았습니다. 종료합니다.")
                sys.exit(1)
            level_path = str(selected)
        else:
            print("[*] 현재 플레이 중인 맵 자동 탐색 중...")
            found = find_current_level(args.dir)
            if found is None:
                print("[!] 자동으로 맵을 찾지 못했습니다.")
                print("    --select 옵션으로 목록에서 선택하거나, 파일 경로를 직접 지정하세요.")
                sys.exit(1)
            level_path = str(found)
            print(f"[*] 자동 탐색된 맵: {found.name}")

    # 레벨 파일 파싱
    print(f"[*] 레벨 파일 로딩: {level_path}")
    try:
        level = parse_level(level_path)
    except (FileNotFoundError, ValueError) as e:
        print(f"[!] 오류: {e}")
        sys.exit(1)

    if not level.tiles:
        print("[!] 타일이 없는 레벨입니다.")
        sys.exit(1)

    # 정보 출력 모드
    if args.info:
        print()
        print_level_info(level)
        print()
        print("  첫 10개 타일 타이밍:")
        for tile in level.tiles[:11]:
            ms_str = f"{tile.time_ms:>10.1f}ms"
            angle_str = f"{tile.angle:>6.1f}°"
            bpm_str = f"BPM={tile.bpm:.1f}"
            mid = " [미드스핀]" if tile.is_midspin else ""
            print(f"    타일 {tile.index:>4}: {ms_str}  {angle_str}  {bpm_str}{mid}")
        return

    print(f"[*] {len(level.tiles)}개 타일 로드 완료")

    controller = MacroController(
        level=level,
        key=args.key,
        start_delay=args.delay,
        countdown=args.countdown,
        show_overlay=not args.no_overlay,
        toggle_key=args.toggle_key,
        quit_key=args.quit_key,
    )
    controller.run()


if __name__ == "__main__":
    main()
