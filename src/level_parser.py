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


@dataclass
class LevelData:
    """파싱된 레벨 데이터."""
    bpm: float = 120.0
    offset: float = 0.0  # ms
    tiles: list[TileHit] = field(default_factory=list)
    song: str = ""
    artist: str = ""
    author: str = ""


def _fix_adofai_json(raw: str) -> str:
    """
    .adofai 파일은 표준 JSON이 아닌 경우가 많습니다.
    - 마지막 쉼표(trailing comma) 제거
    - 주석 제거
    """
    # 주석 제거
    raw = re.sub(r'//.*', '', raw)
    # trailing comma 제거 (}, 또는 ], 앞의 쉼표)
    raw = re.sub(r',\s*([\]}])', r'\1', raw)
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
    두 타일 사이의 상대 각도를 계산합니다.
    공식: angle = (NextTile - ThisTile + 540) % 360
    """
    if next_angle == 999 or this_angle == 999:
        return 0  # 미드스핀

    angle = (next_angle - this_angle + 540) % 360
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
        data = json.loads(fixed)
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

    # 타일별 BPM 변경 이벤트
    speed_changes: dict[int, dict] = {}
    twirl_tiles: set[int] = set()

    for action in actions:
        floor = action.get("floor", 0)
        event_type = action.get("eventType", "")

        if event_type == "SetSpeed":
            speed_changes[floor] = action
        elif event_type == "Twirl":
            twirl_tiles.add(floor)

    # 타이밍 계산
    current_bpm = level.bpm
    current_time_ms = level.offset
    twirled = False

    # 첫 번째 타일 (floor 0)
    level.tiles.append(TileHit(
        index=0,
        time_ms=current_time_ms,
        bpm=current_bpm,
        angle=0,
    ))

    for i in range(len(angles)):
        tile_floor = i + 1  # floor index (1-based for actual tiles)

        # Twirl 확인 (현재 타일에 Twirl 이벤트가 있으면 방향 반전)
        if tile_floor in twirl_tiles:
            twirled = not twirled

        # BPM 변경 확인 (현재 타일에 SetSpeed가 있으면 BPM 업데이트)
        if tile_floor in speed_changes:
            speed_event = speed_changes[tile_floor]
            speed_type = speed_event.get("speedType", "Bpm")

            if speed_type == "Bpm":
                current_bpm = float(speed_event.get("beatsPerMinute", current_bpm))
            elif speed_type == "Multiplier":
                multiplier = float(speed_event.get("bpmMultiplier", 1.0))
                current_bpm *= multiplier

        # 상대 각도 계산
        if i < len(angles):
            this_angle = angles[i]
            is_midspin = (this_angle == 999)

            if i == 0:
                # 첫 번째 타일의 이전 각도는 기본적으로 0 (R 방향)
                prev_angle = 0
            else:
                prev_angle = angles[i - 1]
                if prev_angle == 999:
                    # 미드스핀의 경우 그 이전 타일의 각도를 사용
                    for j in range(i - 2, -1, -1):
                        if angles[j] != 999:
                            prev_angle = angles[j]
                            break

            if is_midspin:
                rel_angle = 0
            else:
                rel_angle = _get_relative_angle(prev_angle, this_angle, twirled)

            # 시간 계산
            interval_ms = _angle_to_ms(rel_angle, current_bpm)
            current_time_ms += interval_ms

            level.tiles.append(TileHit(
                index=tile_floor,
                time_ms=current_time_ms,
                bpm=current_bpm,
                angle=rel_angle,
                is_midspin=is_midspin,
            ))

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
