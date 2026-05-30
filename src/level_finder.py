"""
레벨 자동 탐색 모듈 - 현재 플레이 중인 .adofai 맵을 자동으로 찾습니다.

탐색 전략 (우선순위 순):
  1. Windows 레지스트리(Unity PlayerPrefs)의 lastOpenedLevel = 마지막으로 연 맵 (가장 정확)
  2. ADOFAI Player.log에서 최근 로드된 .adofai 경로 추출
  3. 알려진 커스텀 레벨 디렉토리에서 가장 최근에 수정된 .adofai 파일
  4. 사용자가 직접 목록에서 선택
"""

import os
import re
import sys
from pathlib import Path
from dataclasses import dataclass


# Steam 워크샵 ADOFAI App ID
ADOFAI_APP_ID = "977950"

# Unity PlayerPrefs 레지스트리 경로 (Windows)
ADOFAI_REG_PATH = r"Software\7th Beat Games\A Dance of Fire and Ice"
# Unity는 PlayerPrefs 키 이름 뒤에 _h<해시>를 붙여 저장하므로 접두사로 매칭한다.
LAST_LEVEL_KEY_PREFIX = "lastOpenedLevel"
LAST_FOLDER_KEY_PREFIX = "lastUsedFolder"

# Player.log 라인에서 .adofai 경로를 찾기 위한 패턴
ADOFAI_PATH_PATTERN = re.compile(r'([A-Za-z]:[\\/].*?\.adofai|/.*?\.adofai)', re.IGNORECASE)


@dataclass
class FoundLevel:
    """탐색된 레벨 파일 정보."""
    path: Path
    mtime: float
    source: str  # 어디서 찾았는지 (log / directory)


def find_level_from_registry() -> Path | None:
    """
    Windows 레지스트리의 Unity PlayerPrefs에서 마지막으로 연 레벨 경로를 읽습니다.
    HKCU\\Software\\7th Beat Games\\A Dance of Fire and Ice 의
    lastOpenedLevel_h<해시> 값(UTF-8 바이너리)을 디코딩합니다.
    """
    if not sys.platform.startswith("win"):
        return None

    try:
        import winreg
    except ImportError:
        return None

    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, ADOFAI_REG_PATH)
    except OSError:
        return None

    try:
        value = _read_pref_string(key, LAST_LEVEL_KEY_PREFIX)
    finally:
        winreg.CloseKey(key)

    if not value:
        return None

    candidate = Path(value)
    if candidate.exists() and candidate.suffix.lower() == ".adofai":
        return candidate
    return None


def _decode_pref_bytes(data) -> str:
    """
    Unity PlayerPrefs 레지스트리 값(REG_BINARY: UTF-8 문자열 + 끝에 null)을
    문자열로 디코딩합니다. bytes가 아니면 str로 변환합니다.
    """
    if isinstance(data, (bytes, bytearray)):
        return bytes(data).split(b"\x00", 1)[0].decode("utf-8", errors="ignore").strip()
    return str(data).strip()


def _read_pref_string(key, name_prefix: str) -> str | None:
    """열린 레지스트리 키에서 name_prefix로 시작하는 값을 찾아 UTF-8 문자열로 디코딩합니다."""
    import winreg

    i = 0
    while True:
        try:
            name, data, _vtype = winreg.EnumValue(key, i)
        except OSError:
            break
        i += 1
        if not name.startswith(name_prefix):
            continue
        return _decode_pref_bytes(data)
    return None


def get_player_log_paths() -> list[Path]:
    """플랫폼별 ADOFAI Player.log 가능 경로 목록을 반환합니다."""
    home = Path.home()
    candidates = []

    if sys.platform.startswith("win"):
        # Windows: AppData/LocalLow/7th Beat Games/A Dance of Fire and Ice/Player.log
        localappdata_low = home / "AppData" / "LocalLow" / "7th Beat Games" / "A Dance of Fire and Ice"
        candidates.append(localappdata_low / "Player.log")
        candidates.append(localappdata_low / "output_log.txt")
    elif sys.platform == "darwin":
        # macOS
        candidates.append(home / "Library" / "Logs" / "7th Beat Games" / "A Dance of Fire and Ice" / "Player.log")
        candidates.append(home / "Library" / "Logs" / "Unity" / "Player.log")
    else:
        # Linux
        candidates.append(home / ".config" / "unity3d" / "7th Beat Games" / "A Dance of Fire and Ice" / "Player.log")

    return [c for c in candidates if c.exists()]


def find_level_from_log() -> Path | None:
    """
    Player.log를 읽어 가장 최근에 로드된 .adofai 파일 경로를 추출합니다.
    로그를 뒤에서부터 읽어 마지막으로 등장한 유효한 경로를 반환합니다.
    """
    log_paths = get_player_log_paths()

    for log_path in log_paths:
        try:
            content = log_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        # 뒤에서부터 검색 (가장 최근 로드)
        matches = ADOFAI_PATH_PATTERN.findall(content)
        for match in reversed(matches):
            candidate = Path(match.strip().strip('"').strip("'"))
            if candidate.exists() and candidate.suffix.lower() == ".adofai":
                return candidate

    return None


def get_default_level_dirs() -> list[Path]:
    """플랫폼별 커스텀 레벨 디렉토리 후보 목록을 반환합니다."""
    home = Path.home()
    dirs: list[Path] = []

    if sys.platform.startswith("win"):
        # Steam 워크샵 경로
        program_files_x86 = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
        dirs.append(program_files_x86 / "Steam" / "steamapps" / "workshop" / "content" / ADOFAI_APP_ID)
        dirs.append(program_files_x86 / "Steam" / "steamapps" / "common" / "A Dance of Fire and Ice")
        # 일반 커스텀 레벨 폴더
        dirs.append(home / "A Dance of Fire and Ice" / "CustomSongs")
        dirs.append(home / "A Dance of Fire and Ice" / "CustomLevels")
        dirs.append(home / "Documents" / "A Dance of Fire and Ice")
        dirs.append(home / "Downloads")
    else:
        # Linux / macOS Steam 경로
        dirs.append(home / ".steam" / "steam" / "steamapps" / "workshop" / "content" / ADOFAI_APP_ID)
        dirs.append(home / ".local" / "share" / "Steam" / "steamapps" / "workshop" / "content" / ADOFAI_APP_ID)
        dirs.append(home / "A Dance of Fire and Ice" / "CustomSongs")
        dirs.append(home / "Downloads")

    return [d for d in dirs if d.exists()]


def find_levels_in_dirs(dirs: list[Path], limit: int = 30) -> list[FoundLevel]:
    """
    주어진 디렉토리들에서 모든 .adofai 파일을 찾아 수정 시간 내림차순으로 반환합니다.
    """
    found: list[FoundLevel] = []
    seen: set[Path] = set()

    for directory in dirs:
        try:
            for path in directory.rglob("*.adofai"):
                resolved = path.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                try:
                    mtime = path.stat().st_mtime
                except OSError:
                    continue
                found.append(FoundLevel(path=path, mtime=mtime, source="directory"))
        except (OSError, PermissionError):
            continue

    found.sort(key=lambda f: f.mtime, reverse=True)
    return found[:limit]


def find_current_level(extra_dirs: list[str] | None = None) -> Path | None:
    """
    현재 플레이 중인 레벨을 자동으로 찾습니다.

    Returns:
        찾은 .adofai 파일 경로, 없으면 None.
    """
    # 1순위: 레지스트리(마지막으로 연 맵) - 가장 정확
    from_reg = find_level_from_registry()
    if from_reg:
        return from_reg

    # 2순위: Player.log
    from_log = find_level_from_log()
    if from_log:
        return from_log

    # 3순위: 디렉토리에서 가장 최근 파일
    dirs = get_default_level_dirs()
    if extra_dirs:
        dirs.extend(Path(d) for d in extra_dirs if Path(d).exists())

    levels = find_levels_in_dirs(dirs)
    if levels:
        return levels[0].path

    return None


def select_level_interactive(extra_dirs: list[str] | None = None) -> Path | None:
    """
    탐색된 레벨 목록을 보여주고 사용자가 선택하게 합니다.

    Returns:
        선택된 .adofai 파일 경로, 취소 시 None.
    """
    dirs = get_default_level_dirs()
    if extra_dirs:
        dirs.extend(Path(d) for d in extra_dirs if Path(d).exists())

    levels = find_levels_in_dirs(dirs)

    # Player.log 결과를 맨 위에 추가
    from_log = find_level_from_log()
    if from_log:
        levels.insert(0, FoundLevel(
            path=from_log,
            mtime=from_log.stat().st_mtime if from_log.exists() else 0,
            source="log (현재 로드됨)",
        ))

    # 레지스트리 결과를 가장 위에 추가 (가장 정확)
    from_reg = find_level_from_registry()
    if from_reg:
        # 중복 제거
        levels = [lv for lv in levels if lv.path.resolve() != from_reg.resolve()]
        levels.insert(0, FoundLevel(
            path=from_reg,
            mtime=from_reg.stat().st_mtime if from_reg.exists() else 0,
            source="registry (마지막으로 연 맵)",
        ))

    if not levels:
        print("[!] .adofai 파일을 찾을 수 없습니다.")
        print("    --dir 옵션으로 레벨 폴더를 직접 지정해보세요.")
        return None

    print("\n  탐색된 레벨 목록:")
    print("  " + "-" * 60)
    for i, level in enumerate(levels):
        marker = " *" if level.source.startswith("log") else "  "
        print(f"  {marker}[{i + 1:>2}] {level.path.name}")
        print(f"        ({level.source}) {level.path.parent}")
    print("  " + "-" * 60)
    print("  * = 현재 게임에서 로드된 것으로 추정되는 레벨")

    try:
        choice = input("\n  선택할 번호 (Enter = 1번): ").strip()
    except (EOFError, KeyboardInterrupt):
        return None

    if not choice:
        return levels[0].path

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(levels):
            return levels[idx].path
    except ValueError:
        pass

    print("[!] 잘못된 선택입니다.")
    return None
