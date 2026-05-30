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
    source: str  # 어디서 찾았는지 (registry / log / directory)


# .adofai settings 블록에서 곡명/아티스트/BPM을 가볍게 뽑는 패턴
_META_SONG = re.compile(r'"song"\s*:\s*"((?:[^"\\]|\\.)*)"')
_META_ARTIST = re.compile(r'"artist"\s*:\s*"((?:[^"\\]|\\.)*)"')
_META_AUTHOR = re.compile(r'"author"\s*:\s*"((?:[^"\\]|\\.)*)"')
_META_SONGFILE = re.compile(r'"songFilename"\s*:\s*"((?:[^"\\]|\\.)*)"')
_META_BPM = re.compile(r'"bpm"\s*:\s*([0-9.]+)')

# main.adofai / level.adofai 처럼 파일명만으론 구분이 안 되는 일반 이름들
_GENERIC_FILENAMES = {"main.adofai", "level.adofai", "song.adofai"}


def read_level_meta(path: Path, max_bytes: int = 1_048_576) -> dict:
    """
    .adofai 파일 앞부분(기본 1MB)만 읽어 곡명/아티스트/BPM을 가볍게 추출합니다.
    settings 블록은 angleData 뒤에 오므로 타일 수가 많으면 더 뒤에 있지만,
    1MB면 대부분의 맵을 커버하면서도 전체 파싱보다 훨씬 빠릅니다.
    """
    meta = {"song": "", "artist": "", "bpm": None}
    try:
        with open(path, "r", encoding="utf-8-sig", errors="ignore") as fh:
            head = fh.read(max_bytes)
    except OSError:
        return meta

    m = _META_SONG.search(head)
    if m:
        meta["song"] = m.group(1).strip()
    # song이 비어있으면 songFilename(예: "Hello.mp3")을 곡명 대용으로 쓴다.
    if not meta["song"]:
        m = _META_SONGFILE.search(head)
        if m:
            name = m.group(1).strip()
            name = re.sub(r"\.(mp3|ogg|wav|flac|m4a)$", "", name, flags=re.IGNORECASE)
            meta["song"] = name.strip()
    m = _META_ARTIST.search(head)
    if m:
        meta["artist"] = m.group(1).strip()
    if not meta["artist"]:
        m = _META_AUTHOR.search(head)
        if m:
            meta["artist"] = m.group(1).strip()
    m = _META_BPM.search(head)
    if m:
        try:
            meta["bpm"] = float(m.group(1))
        except ValueError:
            pass
    return meta


def level_display_name(level: "FoundLevel", meta: dict | None = None) -> str:
    """목록에 보여줄 사람친화된 맵 이름을 정합니다.

    우선순위: 곡명(메타) → 파일명이 일반명(main.adofai 등)이면 상위 폴더명 → 파일명(확장자 제외).
    메타가 비어 있더라도 항상 의미 있는 이름을 돌려준다.
    """
    if meta is None:
        meta = read_level_meta(level.path)
    song = (meta.get("song") or "").strip()
    if song:
        return song
    if level.path.name.lower() in _GENERIC_FILENAMES:
        parent = level.path.parent.name
        if parent:
            return parent
    return level.path.stem


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


def find_level_from_registry_folder() -> Path | None:
    """
    레지스트리 lastUsedFolder(마지막으로 사용한 폴더)에서 가장 최근에 수정된
    .adofai 파일을 찾습니다. lastOpenedLevel이 비어있을 때의 보조 수단입니다.
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
        folder = _read_pref_string(key, LAST_FOLDER_KEY_PREFIX)
    finally:
        winreg.CloseKey(key)

    if not folder:
        return None

    folder_path = Path(folder)
    if not folder_path.is_dir():
        return None

    levels = find_levels_in_dirs([folder_path], limit=1)
    return levels[0].path if levels else None


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


def _read_pref_int(key, name_prefix: str) -> int | None:
    """열린 레지스트리 키에서 name_prefix로 시작하는 DWORD 값을 정수로 읽습니다."""
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
        try:
            return int(data)
        except (TypeError, ValueError):
            return None
    return None


def get_game_framerate() -> int | None:
    """
    Windows 레지스트리에서 ADOFAI가 렌더링하는 프레임레이트(Hz)를 추정합니다.

    ADOFAI(Unity)는 프레임마다 입력을 한 번 폴링하므로, 한 프레임보다 짧은
    간격으로 들어온 키 입력은 묶여서 한 번만 인식됩니다. 따라서 매크로의
    최소 입력 간격을 이 프레임레이트에 맞추면 동타/삼각형/트월 같은 빠른
    구간에서 입력 누락을 줄일 수 있습니다.

    우선순위:
      1. targetFramerate (게임 설정의 목표 프레임레이트)
      2. Native RefreshRate Numerator/Denominator (모니터 주사율)
    실패하거나 비정상 값이면 None.
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
        target = _read_pref_int(key, "targetFramerate")
        if target and 20 <= target <= 1000:
            return target
        num = _read_pref_int(key, "Screenmanager Native RefreshRate Numerator")
        den = _read_pref_int(key, "Screenmanager Native RefreshRate Denominator")
        if num and den:
            rate = round(num / den)
            if 20 <= rate <= 1000:
                return rate
    finally:
        winreg.CloseKey(key)

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

    # 2순위: 레지스트리 lastUsedFolder의 최근 맵 (lastOpenedLevel이 비었을 때)
    from_reg_folder = find_level_from_registry_folder()
    if from_reg_folder:
        return from_reg_folder

    # 3순위: Player.log
    from_log = find_level_from_log()
    if from_log:
        return from_log

    # 4순위: 디렉토리에서 가장 최근 파일
    dirs = get_default_level_dirs()
    if extra_dirs:
        dirs.extend(Path(d) for d in extra_dirs if Path(d).exists())

    levels = find_levels_in_dirs(dirs)
    if levels:
        return levels[0].path

    return None


def gather_candidate_levels(extra_dirs: list[str] | None = None) -> list[FoundLevel]:
    """
    탐색 가능한 레벨 후보를 우선순위 순으로 모아 중복 없이 반환합니다.
    (레지스트리 → 레지스트리 폴더 → Player.log → 디렉토리 스캔)
    """
    dirs = get_default_level_dirs()
    if extra_dirs:
        dirs.extend(Path(d) for d in extra_dirs if Path(d).exists())

    levels = find_levels_in_dirs(dirs)

    def _prepend(path: Path | None, source: str):
        nonlocal levels
        if not path or not path.exists():
            return
        levels = [lv for lv in levels if lv.path.resolve() != path.resolve()]
        try:
            mtime = path.stat().st_mtime
        except OSError:
            mtime = 0
        levels.insert(0, FoundLevel(path=path, mtime=mtime, source=source))

    # 아래에서 위 순서로 prepend → 최종적으로 레지스트리가 맨 위
    _prepend(find_level_from_log(), "log (현재 로드됨)")
    _prepend(find_level_from_registry_folder(), "registry folder (최근 폴더)")
    _prepend(find_level_from_registry(), "registry (마지막으로 연 맵)")
    return levels


def _format_level_line(idx: int, level: FoundLevel) -> list[str]:
    """목록 한 항목을 곡명/BPM 등 메타와 함께 여러 줄 문자열로 만듭니다."""
    marker = " *" if level.source.startswith(("registry", "log")) else "  "
    meta = read_level_meta(level.path)
    title = level_display_name(level, meta)
    bits = []
    if meta.get("artist"):
        bits.append(f"by {meta['artist']}")
    if meta.get("bpm") is not None:
        bits.append(f"BPM {meta['bpm']:g}")
    bits.append(level.path.name)  # 파일명도 같이 (구분용)
    meta_str = "  ·  ".join(bits)
    return [
        f"  {marker}[{idx:>2}] {title}",
        f"        {meta_str}",
        f"        ({level.source}) {level.path.parent}",
    ]


def list_levels(extra_dirs: list[str] | None = None) -> list[FoundLevel]:
    """탐색된 레벨 목록을 곡명/BPM과 함께 출력합니다 (선택 없이 보기 전용)."""
    levels = gather_candidate_levels(extra_dirs)
    if not levels:
        print("[!] .adofai 파일을 찾을 수 없습니다.")
        print("    --dir 옵션으로 레벨 폴더를 직접 지정해보세요.")
        return []

    print("\n  탐색된 레벨 목록:")
    print("  " + "-" * 60)
    for i, level in enumerate(levels):
        for line in _format_level_line(i + 1, level):
            print(line)
    print("  " + "-" * 60)
    print("  * = 현재 게임에서 로드된 것으로 추정되는 레벨")
    return levels


def select_level_interactive(extra_dirs: list[str] | None = None) -> Path | None:
    """
    탐색된 레벨 목록을 보여주고 사용자가 선택하게 합니다.

    Returns:
        선택된 .adofai 파일 경로, 취소 시 None.
    """
    levels = list_levels(extra_dirs)
    if not levels:
        return None

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
