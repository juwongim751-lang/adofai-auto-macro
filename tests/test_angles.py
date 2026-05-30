"""
각도/트월/미드스핀 상대각 계산이 권위 라이브러리(adofaipy)와 일치하는지 검증.

adofaipy가 설치돼 있으면 무작위 합성 맵으로 교차검증하고,
없으면 해당 테스트는 자동으로 건너뜁니다.
"""

import random

import pytest

from src.level_parser import parse_level
from tests.helpers import make_adofai

adofaipy = pytest.importorskip("adofaipy")
from adofaipy import LevelDict  # noqa: E402


def _angles_match(filepath: str):
    """파서의 상대각 리스트와 adofaipy getAnglesRelative(padmidspins=True)를 비교."""
    ld = LevelDict(filepath)
    ref = ld.getAnglesRelative(padmidspins=True)
    lv = parse_level(filepath)
    mine = [t.angle for t in lv.tiles]
    assert len(ref) == len(mine), f"타일 수 불일치: ref={len(ref)} mine={len(mine)}"
    # idx 0은 시작 타일이라 설계상 다름 → 1부터 비교
    for i in range(1, len(ref)):
        assert abs(ref[i] - mine[i]) < 0.01, (
            f"idx {i}: ref={ref[i]} mine={mine[i]}"
        )


def test_straight_tiles(tmp_path):
    f = make_adofai(tmp_path, [0, 0, 0, 0, 0])
    _angles_match(f)


def test_right_angles(tmp_path):
    f = make_adofai(tmp_path, [0, 90, 180, 90, 0, 270, 0])
    _angles_match(f)


def test_single_twirl(tmp_path):
    f = make_adofai(
        tmp_path,
        [0, 90, 180, 90, 0],
        actions=[{"floor": 2, "eventType": "Twirl"}],
    )
    _angles_match(f)


def test_multiple_twirls(tmp_path):
    f = make_adofai(
        tmp_path,
        [0, 90, 0, 90, 180, 270, 0, 90],
        actions=[
            {"floor": 2, "eventType": "Twirl"},
            {"floor": 5, "eventType": "Twirl"},
        ],
    )
    _angles_match(f)


def test_midspin(tmp_path):
    # 999 = 미드스핀
    f = make_adofai(tmp_path, [0, 0, 999, 0, 90, 0])
    _angles_match(f)


def test_twirl_and_midspin(tmp_path):
    f = make_adofai(
        tmp_path,
        [0, 90, 999, 180, 90, 0, 270],
        actions=[{"floor": 3, "eventType": "Twirl"}],
    )
    _angles_match(f)


@pytest.mark.parametrize("seed", range(20))
def test_random_levels_match_adofaipy(tmp_path, seed):
    """무작위 각도 + 무작위 트월/미드스핀 맵 20종을 adofaipy와 교차검증."""
    rng = random.Random(seed)
    n = rng.randint(5, 40)
    choices = [0, 15, 30, 45, 60, 90, 120, 135, 150, 180, 210, 225, 270, 300, 315, 999]
    angles = [0] + [rng.choice(choices) for _ in range(n)]
    # 미드스핀이 연속되지 않도록 보정 (게임 규칙상 흔치 않음)
    for i in range(1, len(angles)):
        if angles[i] == 999 and angles[i - 1] == 999:
            angles[i] = 0
    actions = []
    for floor in range(1, len(angles)):
        if angles[floor] != 999 and rng.random() < 0.2:
            actions.append({"floor": floor, "eventType": "Twirl"})
    f = make_adofai(tmp_path, angles, actions=actions, name=f"r{seed}.adofai")
    _angles_match(f)
