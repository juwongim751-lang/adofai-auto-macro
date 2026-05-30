"""테스트용 합성 .adofai 파일 생성 도우미."""

import json
from pathlib import Path


def make_adofai(
    tmp_path: Path,
    angle_data: list,
    actions: list | None = None,
    bpm: float = 120.0,
    offset: float = 0.0,
    name: str = "level.adofai",
) -> str:
    """주어진 angleData/actions로 최소 .adofai 파일을 만들어 경로를 반환합니다."""
    level = {
        "angleData": list(angle_data),
        "settings": {
            "version": 15,
            "artist": "",
            "song": "",
            "author": "",
            "bpm": bpm,
            "offset": offset,
        },
        "actions": actions or [],
        "decorations": [],
    }
    path = tmp_path / name
    path.write_text(json.dumps(level), encoding="utf-8")
    return str(path)
