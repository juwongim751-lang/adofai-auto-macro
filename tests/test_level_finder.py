"""레벨 탐색 보조 함수 검증 (레지스트리 바이너리 디코딩, 로그 경로 추출)."""

from src import level_finder
from src.level_finder import _decode_pref_bytes, ADOFAI_PATH_PATTERN


def test_decode_pref_bytes_utf8_with_null():
    raw = "C:\\Users\\user\\Downloads\\HELLO (BPM) 2026\\level.adofai".encode("utf-8") + b"\x00"
    assert _decode_pref_bytes(raw) == "C:\\Users\\user\\Downloads\\HELLO (BPM) 2026\\level.adofai"


def test_decode_pref_bytes_korean_path():
    raw = "C:\\맵\\레벨.adofai".encode("utf-8") + b"\x00\x00"
    assert _decode_pref_bytes(raw) == "C:\\맵\\레벨.adofai"


def test_decode_pref_bytes_no_null():
    raw = "D:/maps/song.adofai".encode("utf-8")
    assert _decode_pref_bytes(raw) == "D:/maps/song.adofai"


def test_decode_pref_bytes_non_bytes():
    assert _decode_pref_bytes("plain") == "plain"
    assert _decode_pref_bytes(123) == "123"


def test_path_pattern_windows():
    line = r'Loading level: C:\Program Files (x86)\Steam\workshop\977950\123\main.adofai done'
    m = ADOFAI_PATH_PATTERN.findall(line)
    assert m and m[0].endswith("main.adofai")


def test_path_pattern_unix():
    line = "load /home/user/maps/cool.adofai ok"
    m = ADOFAI_PATH_PATTERN.findall(line)
    assert m and m[0] == "/home/user/maps/cool.adofai"


def test_find_from_registry_non_windows(monkeypatch):
    # 비윈도우 환경에서는 항상 None
    monkeypatch.setattr(level_finder.sys, "platform", "linux")
    assert level_finder.find_level_from_registry() is None
