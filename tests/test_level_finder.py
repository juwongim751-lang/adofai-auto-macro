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


def test_find_from_registry_folder_non_windows(monkeypatch):
    monkeypatch.setattr(level_finder.sys, "platform", "linux")
    assert level_finder.find_level_from_registry_folder() is None


def test_get_game_framerate_non_windows(monkeypatch):
    monkeypatch.setattr(level_finder.sys, "platform", "linux")
    assert level_finder.get_game_framerate() is None


def _write_level(path, song="My Song", artist="Artist X", bpm=150):
    # angleData를 길게 넣어 settings가 앞부분 16KB 밖에 오도록(읽기 범위 검증) 해도 됨
    angles = ", ".join(["0"] * 50)
    path.write_text(
        '{\n"angleData": [' + angles + '],\n'
        '"settings": {"song": "' + song + '", "artist": "' + artist + '", "bpm": ' + str(bpm) + '},\n'
        '"actions": []\n}',
        encoding="utf-8",
    )
    return path


def test_read_level_meta_extracts_song_artist_bpm(tmp_path):
    f = _write_level(tmp_path / "a.adofai", song="Hello", artist="Camellia", bpm=222.5)
    meta = level_finder.read_level_meta(f)
    assert meta["song"] == "Hello"
    assert meta["artist"] == "Camellia"
    assert meta["bpm"] == 222.5


def test_read_level_meta_missing_file(tmp_path):
    meta = level_finder.read_level_meta(tmp_path / "nope.adofai")
    assert meta == {"song": "", "artist": "", "bpm": None}


def test_gather_candidate_levels_from_dir(tmp_path, monkeypatch):
    # 레지스트리/로그는 비활성화하고 디렉토리 스캔만 검증
    monkeypatch.setattr(level_finder, "find_level_from_registry", lambda: None)
    monkeypatch.setattr(level_finder, "find_level_from_registry_folder", lambda: None)
    monkeypatch.setattr(level_finder, "find_level_from_log", lambda: None)
    monkeypatch.setattr(level_finder, "get_default_level_dirs", lambda: [])
    _write_level(tmp_path / "one.adofai")
    levels = level_finder.gather_candidate_levels([str(tmp_path)])
    assert len(levels) == 1
    assert levels[0].path.name == "one.adofai"


def test_list_levels_prints_meta(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(level_finder, "find_level_from_registry", lambda: None)
    monkeypatch.setattr(level_finder, "find_level_from_registry_folder", lambda: None)
    monkeypatch.setattr(level_finder, "find_level_from_log", lambda: None)
    monkeypatch.setattr(level_finder, "get_default_level_dirs", lambda: [])
    _write_level(tmp_path / "song.adofai", song="TestSong", bpm=180)
    level_finder.list_levels([str(tmp_path)])
    out = capsys.readouterr().out
    assert "song.adofai" in out
    assert "TestSong" in out
    assert "BPM 180" in out


def test_display_name_uses_song_when_present(tmp_path):
    f = _write_level(tmp_path / "main.adofai", song="Cool Song")
    lv = level_finder.FoundLevel(path=f, mtime=0, source="directory")
    assert level_finder.level_display_name(lv) == "Cool Song"


def test_display_name_falls_back_to_folder_for_generic_filename(tmp_path):
    # song 메타가 비어 있고 파일명이 일반명(main.adofai)이면 폴더명을 쓴다
    folder = tmp_path / "HELLO (BPM) 2026"
    folder.mkdir()
    f = _write_level(folder / "main.adofai", song="", artist="")
    lv = level_finder.FoundLevel(path=f, mtime=0, source="directory")
    assert level_finder.level_display_name(lv) == "HELLO (BPM) 2026"


def test_display_name_falls_back_to_filename_stem(tmp_path):
    # 일반명이 아닌 파일명이면 곡명이 없을 때 파일명(확장자 제외)을 쓴다
    f = _write_level(tmp_path / "My Cool Map.adofai", song="")
    lv = level_finder.FoundLevel(path=f, mtime=0, source="directory")
    assert level_finder.level_display_name(lv) == "My Cool Map"


def test_read_level_meta_songfilename_fallback(tmp_path):
    # song이 비어 있으면 songFilename에서 확장자를 떼고 곡명으로 쓴다
    path = tmp_path / "x.adofai"
    path.write_text(
        '{\n"angleData": [0, 0],\n'
        '"settings": {"song": "", "songFilename": "Hello (BPM).mp3", "bpm": 200},\n'
        '"actions": []\n}',
        encoding="utf-8",
    )
    meta = level_finder.read_level_meta(path)
    assert meta["song"] == "Hello (BPM)"
