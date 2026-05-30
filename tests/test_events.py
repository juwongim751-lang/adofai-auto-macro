"""SetSpeed / Pause / AutoPlayTiles 이벤트 처리와 타이밍 계산 검증."""

from src.level_parser import parse_level, _angle_to_ms, _get_relative_angle
from tests.helpers import make_adofai


def test_basic_timing_straight(tmp_path):
    # 직선 타일(180°) @ 120BPM = 500ms 간격
    f = make_adofai(tmp_path, [0, 0, 0, 0], bpm=120, offset=0)
    lv = parse_level(f)
    times = [t.time_ms for t in lv.tiles]
    for i in range(1, len(times)):
        assert abs((times[i] - times[i - 1]) - 500.0) < 1e-6


def test_offset_applied(tmp_path):
    f = make_adofai(tmp_path, [0, 0], bpm=120, offset=947)
    lv = parse_level(f)
    assert abs(lv.tiles[0].time_ms - 947.0) < 1e-6


def test_setspeed_bpm(tmp_path):
    f = make_adofai(
        tmp_path,
        [0, 0, 0, 0],
        bpm=120,
        actions=[{"floor": 2, "eventType": "SetSpeed", "speedType": "Bpm",
                  "beatsPerMinute": 240}],
    )
    lv = parse_level(f)
    d1 = lv.tiles[1].time_ms - lv.tiles[0].time_ms  # 120BPM -> 500ms
    d2 = lv.tiles[2].time_ms - lv.tiles[1].time_ms  # 240BPM -> 250ms
    assert abs(d1 - 500) < 1e-6
    assert abs(d2 - 250) < 1e-6


def test_setspeed_multiplier_is_cumulative(tmp_path):
    # ×0.125 후 ×2 = 누적 ×0.25 → 120 → 30BPM
    f = make_adofai(
        tmp_path,
        [0, 0, 0, 0, 0],
        bpm=120,
        actions=[
            {"floor": 1, "eventType": "SetSpeed", "speedType": "Multiplier",
             "bpmMultiplier": 0.125},
            {"floor": 2, "eventType": "SetSpeed", "speedType": "Multiplier",
             "bpmMultiplier": 2},
        ],
    )
    lv = parse_level(f)
    assert abs(lv.tiles[1].bpm - 15.0) < 1e-6   # 120 * 0.125
    assert abs(lv.tiles[2].bpm - 30.0) < 1e-6   # 15 * 2


def test_pause_adds_time(tmp_path):
    # floor 1에 2비트 멈춤 @120BPM = 1000ms 추가 → 이후 타일 전부 밀림
    base = parse_level(make_adofai(tmp_path, [0, 0, 0, 0], bpm=120, name="a.adofai"))
    paused = parse_level(make_adofai(
        tmp_path, [0, 0, 0, 0], bpm=120, name="b.adofai",
        actions=[{"floor": 1, "eventType": "Pause", "duration": 2}],
    ))
    # 멈춤 타일(1)까지는 동일, 그 다음 타일(2)부터 1000ms 밀림
    assert abs(base.tiles[1].time_ms - paused.tiles[1].time_ms) < 1e-6
    shift = paused.tiles[2].time_ms - base.tiles[2].time_ms
    assert abs(shift - 1000.0) < 1e-6


def test_autoplay_flags_range(tmp_path):
    f = make_adofai(
        tmp_path,
        [0] * 10,
        actions=[
            {"floor": 3, "eventType": "AutoPlayTiles", "enabled": True},
            {"floor": 7, "eventType": "AutoPlayTiles", "enabled": False},
        ],
    )
    lv = parse_level(f)
    autos = {t.index for t in lv.tiles if t.auto}
    assert autos == {3, 4, 5, 6}


def test_autoplay_open_until_end(tmp_path):
    f = make_adofai(
        tmp_path,
        [0] * 6,
        actions=[{"floor": 4, "eventType": "AutoPlayTiles", "enabled": True}],
    )
    lv = parse_level(f)
    autos = {t.index for t in lv.tiles if t.auto}
    assert 4 in autos and 5 in autos
    assert 0 not in autos and 3 not in autos


def test_angle_formula_known_values():
    # 직선(R->R): 180°, R->U(0->90): 90°, U->R(90->0): 270°
    assert _get_relative_angle(0, 0, False) == 180
    assert _get_relative_angle(0, 90, False) == 90
    assert _get_relative_angle(90, 0, False) == 270


def test_angle_to_ms_formula():
    # ms = 1000*angle/(3*bpm); 180°@120 = 500ms
    assert abs(_angle_to_ms(180, 120) - 500.0) < 1e-9
    assert abs(_angle_to_ms(90, 120) - 250.0) < 1e-9
    assert _angle_to_ms(180, 0) == 0
