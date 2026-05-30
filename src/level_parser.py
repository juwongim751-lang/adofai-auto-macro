"""
.adofai 레벨 파일 파서 - 레벨 파일을 읽어 타일 타이밍 정보를 추출합니다.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path


# pathData 문자 → 절대 각도 매핑
PATH_CHAR_TO_ANGLE: dict[str, float] = {
    "R": 0,
    "p": 15,
    "J": 30,
    "E": 45,
    "T": 60,
    "o": 75,
    "U": 90,
    "q": 105,
    "G": 120,
    "Q": 135,
    "H": 150,
    "W": 165,
    "L": 180,
    "x": 195,
    "N": 210,
    "Z": 225,
    "F": 240,
    "V": 255,
    "D": 270,
    "Y": 285,
    "B": 300,
    "C": 315,
    "M": 330,
    "A": 345,
    "!": 999,  # 미드스핀 (midspin)
}


@dataclass
class TileHit:
    """하나의 타일 입력 정보."""
    index: int
    time_ms: float  # 이 타일을 눌러야 하는 시간 (ms, 곡 시작부터)
    bpm: float
    angle: float  # 상대 각도
    is_midspin: bool = False
    auto: bool = False  # 게임이 자동으로 치는 구간(AutoPlayTiles) - 매크로는 누르지 않음
    hold_ms: float = 0.0  # >0이면 롱노트(Hold): 이 시간(ms)만큼 키를 누른 채 유지
    hold_covered: bool = False  # 롱노트 유지 중 지나가는 타일 - 따로 누르지 않음


@dataclass
class LevelData:
    """파싱된 레벨 데이터."""
    bpm: float = 120.0
    offset: float = 0.0  # ms
    tiles: list[TileHit] = field(default_factory=list)
    song: str = ""
    artist: str = ""
    author: str = ""


def _strip_control_chars(raw: str) -> str:
    """
    JSON 문자열 값 안에 들어있는 비허용 제어문자(0x00-0x1F)를 공백으로 치환합니다.
    문자열 밖의 정상 공백(\\n, \\r, \\t)은 그대로 둡니다.
    """
    out = []
    in_string = False
    escaped = False
    for ch in raw:
        if in_string:
            if escaped:
                escaped = False
                out.append(ch)
                continue
            if ch == "\\":
                escaped = True
                out.append(ch)
                continue
            if ch == '"':
                in_string = False
                out.append(ch)
                continue
            # 문자열 안의 제어문자는 공백으로 치환
            if ord(ch) < 0x20:
                out.append(" ")
                continue
            out.append(ch)
        else:
            if ch == '"':
                in_string = True
            out.append(ch)
    return "".join(out)


def _fix_adofai_json(raw: str) -> str:
    """
    .adofai 파일은 표준 JSON이 아닌 경우가 많습니다.
    - 마지막 쉼표(trailing comma) 제거
    - 문자열 안 제어문자 정리
    """
    # trailing comma 제거 (}, 또는 ], 앞의 쉼표)
    raw = re.sub(r',\s*([\]}])', r'\1', raw)
    # 문자열 내 제어문자 정리
    raw = _strip_control_chars(raw)
    return raw


def _parse_angles(data: dict) -> list[float]:
    """angleData 또는 pathData에서 절대 각도 리스트를 추출합니다."""
    if "angleData" in data:
        return [float(a) for a in data["angleData"]]

    if "pathData" in data:
        angles = []
        for char in data["pathData"]:
            if char in PATH_CHAR_TO_ANGLE:
                angles.append(PATH_CHAR_TO_ANGLE[char])
        return angles

    return []


def _get_relative_angle(this_angle: float, next_angle: float, twirled: bool) -> float:
    """
    두 타일 사이의 행성이 회전하는 상대 각도를 계산합니다.
    공식: angle = (180 + ThisTile - NextTile) % 360
    (직선 타일=180°, R→U 같은 90° 꺾임=90°. ADOFAI 실제 동작과 일치)
    """
    if next_angle == 999 or this_angle == 999:
        return 0  # 미드스핀

    angle = (180 + this_angle - next_angle) % 360
    if twirled:
        angle = 360 - angle
    if angle == 0:
        angle = 360
    return angle


def _angle_to_ms(angle: float, bpm: float) -> float:
    """
    상대 각도와 BPM으로 밀리초를 계산합니다.
    공식: ms = (1000 * angle) / (3 * bpm)
    """
    if bpm <= 0:
        return 0
    return (1000.0 * angle) / (3.0 * bpm)


def parse_level(filepath: str) -> LevelData:
    """
    .adofai 레벨 파일을 파싱하여 각 타일의 입력 타이밍을 계산합니다.

    Args:
        filepath: .adofai 파일 경로.

    Returns:
        LevelData 객체.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"레벨 파일을 찾을 수 없습니다: {filepath}")

    raw = path.read_text(encoding="utf-8-sig")
    fixed = _fix_adofai_json(raw)

    try:
        data = json.loads(fixed, strict=False)
    except json.JSONDecodeError as e:
        raise ValueError(f".adofai 파일 파싱 실패: {e}")

    settings = data.get("settings", {})

    level = LevelData(
        bpm=float(settings.get("bpm", 120)),
        offset=float(settings.get("offset", 0)),
        song=settings.get("song", ""),
        artist=settings.get("artist", ""),
        author=settings.get("author", ""),
    )

    angles = _parse_angles(data)
    if not angles:
        return level

    # 이벤트(actions)에서 BPM 변경 및 Twirl 이벤트 추출
    actions = data.get("actions", [])

    speed_changes: dict[int, dict] = {}
    twirl_floors: list[int] = []  # 순서 유지 (중복 허용 = 토글)
    pause_floors: dict[int, float] = {}  # floor -> 멈춤 길이(비트)
    autoplay_events: list[tuple[int, bool]] = []  # (floor, enabled)
    hold_floors: dict[int, int] = {}  # floor -> 유지할 타일 수(duration)

    for action in actions:
        floor = action.get("floor", 0)
        event_type = action.get("eventType", "")

        if event_type == "SetSpeed":
            speed_changes[floor] = action
        elif event_type == "Twirl":
            twirl_floors.append(floor)
        elif event_type == "Pause":
            # 멈춤: 해당 타일에서 duration 비트만큼 멈췄다가 다음 타일로 진행
            pause_floors[floor] = pause_floors.get(floor, 0.0) + float(action.get("duration", 0))
        elif event_type == "AutoPlayTiles":
            autoplay_events.append((floor, bool(action.get("enabled", True))))
        elif event_type == "Hold":
            # 롱노트: 이 타일부터 duration개 타일을 지나는 동안 키를 누른 채 유지
            dur = int(action.get("duration", 0))
            if dur > 0:
                hold_floors[floor] = hold_floors.get(floor, 0) + dur

    # AutoPlayTiles 구간 계산: enabled=True 타일부터 enabled=False 타일 전까지 자동 재생
    auto_floors: set[int] = set()
    autoplay_events.sort(key=lambda x: x[0])
    auto_on_from: int | None = None
    for floor, enabled in autoplay_events:
        if enabled and auto_on_from is None:
            auto_on_from = floor
        elif not enabled and auto_on_from is not None:
            for f in range(auto_on_from, floor):
                auto_floors.add(f)
            auto_on_from = None
    if auto_on_from is not None:
        # 끝까지 켜져 있으면 마지막 타일까지 자동
        for f in range(auto_on_from, len(angles) + 1):
            auto_floors.add(f)

    # 마지막 타일 복제 (ADOFAI는 angleData보다 타일이 1개 더 많음 / adofaipy 방식)
    padded = list(angles)
    if padded:
        last = padded[-1]
        if last != 999:
            padded.append(last)
        else:
            padded.append((padded[-2] + 180) % 360 if len(padded) >= 2 else 0)

    # --- Twirl 처리: 절대 각도를 직전 타일 각도 기준으로 반사 ---
    # (adofaipy 방식: absangles[twirl:] = (2*absangles[twirl-1] - angle) % 360)
    abs_angles = list(padded)
    for twirl in sorted(twirl_floors, reverse=True):
        if twirl < 1 or twirl >= len(abs_angles):
            continue
        axis = abs_angles[twirl - 1]
        for k in range(twirl, len(abs_angles)):
            if abs_angles[k] != 999:
                abs_angles[k] = (2 * axis - abs_angles[k]) % 360

    # --- 미드스핀 처리: 미드스핀 이후 모든 타일 각도에 180도 추가 ---
    midspins = [idx for idx, a in enumerate(abs_angles) if a == 999]
    for mid in sorted(midspins, reverse=True):
        for k in range(mid + 1, len(abs_angles)):
            if abs_angles[k] != 999:
                abs_angles[k] = (abs_angles[k] + 180) % 360

    # --- 상대 각도 계산 (twirl/midspin이 이미 abs_angles에 반영됨) ---
    def _rel_at(idx: int) -> float:
        if abs_angles[idx] == 999:
            return 0.0
        if idx == 0:
            prev = 0.0
        elif abs_angles[idx - 1] == 999:
            prev = abs_angles[idx - 2] if idx >= 2 else 0.0
        else:
            prev = abs_angles[idx - 1]
        return _get_relative_angle(prev, abs_angles[idx], False)

    # --- 타임라인 구성 ---
    current_bpm = level.bpm
    current_time_ms = level.offset

    # 첫 번째 타일 (floor 0): 시작 지점
    level.tiles.append(TileHit(
        index=0,
        time_ms=current_time_ms,
        bpm=current_bpm,
        angle=0,
        is_midspin=(padded[0] == 999) if padded else False,
        auto=(0 in auto_floors),
    ))

    # floor 0에 멈춤이 있으면 적용
    if 0 in pause_floors:
        current_time_ms += pause_floors[0] * (60000.0 / current_bpm) if current_bpm > 0 else 0

    for idx in range(1, len(abs_angles)):
        # BPM 변경 (해당 타일로 진입하는 회전부터 적용)
        if idx in speed_changes:
            speed_event = speed_changes[idx]
            speed_type = speed_event.get("speedType", "Bpm")
            if speed_type == "Bpm":
                current_bpm = float(speed_event.get("beatsPerMinute", current_bpm))
            elif speed_type == "Multiplier":
                multiplier = float(speed_event.get("bpmMultiplier", 1.0))
                current_bpm *= multiplier

        is_midspin = (padded[idx] == 999)
        rel_angle = _rel_at(idx)

        interval_ms = _angle_to_ms(rel_angle, current_bpm)
        current_time_ms += interval_ms

        level.tiles.append(TileHit(
            index=idx,
            time_ms=current_time_ms,
            bpm=current_bpm,
            angle=rel_angle,
            is_midspin=is_midspin,
            auto=(idx in auto_floors),
        ))

        # 멈춤(Pause): 이 타일에 도착한 뒤 duration 비트만큼 대기 → 이후 타일 전체가 밀림
        if idx in pause_floors and current_bpm > 0:
            current_time_ms += pause_floors[idx] * (60000.0 / current_bpm)

    # --- 롱노트(Hold) 처리 ---
    # floor에서 키를 누른 뒤 duration개 타일을 지날 때까지 유지하고 그 시점에 뗀다.
    # 사이의 타일(floor+1 ~ floor+duration)은 유지로 처리되므로 따로 누르지 않는다.
    last_idx = len(level.tiles) - 1
    for floor, dur in hold_floors.items():
        if floor < 0 or floor > last_idx:
            continue
        end = min(floor + dur, last_idx)
        level.tiles[floor].hold_ms = level.tiles[end].time_ms - level.tiles[floor].time_ms
        for c in range(floor + 1, end + 1):
            level.tiles[c].hold_covered = True

    return level


def print_level_info(level: LevelData):
    """레벨 정보를 출력합니다."""
    print(f"  곡: {level.song}")
    print(f"  아티스트: {level.artist}")
    print(f"  제작자: {level.author}")
    print(f"  BPM: {level.bpm}")
    print(f"  오프셋: {level.offset}ms")
    print(f"  총 타일 수: {len(level.tiles)}")

    if level.tiles:
        total_time = level.tiles[-1].time_ms
        minutes = int(total_time // 60000)
        seconds = (total_time % 60000) / 1000
        print(f"  총 길이: {minutes}분 {seconds:.1f}초")

        auto_count = sum(1 for t in level.tiles if getattr(t, "auto", False))
        if auto_count:
            print(f"  자동 재생 타일(매크로 입력 제외): {auto_count}개")
