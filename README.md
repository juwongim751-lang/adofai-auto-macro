# 얼불춤 자동 매크로 (ADOFAI Auto Macro)

**A Dance of Fire and Ice** 게임의 `.adofai` 레벨 파일을 파싱하여, 각 타일의 정확한 타이밍에 맞춰 자동으로 키를 입력하는 매크로입니다.

---

## 동작 원리

1. **현재 플레이 중인 맵을 자동으로 탐색** (파일 경로를 직접 입력할 필요 없음)
2. `.adofai` 레벨 파일에서 **타일 각도(angleData/pathData)**, **BPM**, **SetSpeed**, **Twirl** 이벤트를 파싱
3. 각 타일의 상대 각도를 계산하여 정확한 입력 타이밍(ms)을 산출
4. 게임 내에서 계산된 타이밍에 맞춰 자동으로 키를 입력

### 맵 자동 탐색 방식

파일을 직접 지정하지 않으면 다음 순서로 현재 맵을 찾습니다:

1. **ADOFAI Player.log 분석** — 게임이 마지막으로 로드한 `.adofai` 경로를 추출
2. **레벨 폴더 스캔** — Steam 워크샵 / 커스텀 레벨 폴더에서 가장 최근에 수정된 `.adofai` 파일
3. **목록 선택** — `--select` 옵션으로 탐색된 맵 목록에서 직접 선택

### 타이밍 계산 공식
```
상대 각도 = (다음타일각도 - 현재타일각도 + 540) % 360
입력 간격(ms) = (1000 × 상대각도) / (3 × BPM)
```

## 기능

- **맵 자동 탐색**: 현재 플레이 중인 맵을 Player.log/폴더 스캔으로 자동 감지
- **.adofai 파일 파싱**: angleData, pathData 모두 지원
- **BPM 변경 지원**: SetSpeed 이벤트(Bpm / Multiplier) 자동 반영
- **Twirl 지원**: 회전 방향 반전 자동 처리
- **미드스핀 지원**: 미드스핀 타일 자동 처리
- **정밀 타이밍**: busy-wait 기반 고정밀 키 입력
- **카운트다운**: 시작 전 카운트다운으로 게임과 동기화
- **상태 오버레이**: 현재 진행 상황을 화면에 표시
- **핫키 제어**: F6(시작/중지), F8(종료)

## 요구 사항

- Python 3.10 이상
- Windows (게임이 Windows에서 실행되므로)

## 설치

```bash
# 레포지토리 클론
git clone https://github.com/juwongim751-lang/adofai-auto-macro.git
cd adofai-auto-macro

# 가상 환경 생성 (권장)
python -m venv .venv
.venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt
```

## 사용법

### 기본 실행 (맵 자동 탐색)

```bash
# 현재 플레이 중인 맵을 자동으로 찾아서 실행 (파일 경로 입력 불필요)
python main.py

# 탐색된 맵 목록에서 직접 선택
python main.py --select

# 자동 탐색이 안 될 때 검색할 폴더를 추가 지정
python main.py --dir "C:\내커스텀레벨폴더"
```

### 파일 직접 지정

```bash
# .adofai 파일 경로를 인자로 전달
python main.py "C:\경로\레벨파일.adofai"
```

### 옵션

```bash
# 입력 키 변경 (기본: space)
python main.py --key d

# 시작 딜레이 추가 (ms)
python main.py --delay 200

# 카운트다운 변경 (기본: 3초)
python main.py --countdown 5

# 레벨 정보만 출력
python main.py --info

# 오버레이 비활성화
python main.py --no-overlay
```

### 실행 순서

1. 얼불춤 게임을 실행합니다
2. 플레이할 레벨을 한 번 선택/로드합니다 (Player.log에 기록됨)
3. 매크로를 실행합니다: `python main.py` (자동으로 해당 맵을 찾습니다)
4. 게임에서 레벨을 시작합니다
5. **F6**을 눌러 매크로를 시작합니다 (3초 카운트다운 후 자동 입력 시작)
6. **F6**을 다시 눌러 중지하거나, **F8**로 프로그램을 종료합니다

> 자동 탐색이 잘못된 맵을 고른다면 `python main.py --select`로 목록에서 직접 고르거나, 파일 경로를 직접 지정하세요.

## 핫키

| 키 | 기능 |
|---|---|
| **F6** | 매크로 시작/중지 토글 |
| **F8** | 프로그램 종료 |

## 레벨 파일 위치

얼불춤의 `.adofai` 레벨 파일은 보통 다음 경로에 있습니다:

```
C:\Program Files (x86)\Steam\steamapps\common\A Dance of Fire and Ice\
```

또는 커스텀 레벨의 경우:
```
C:\Users\{사용자}\AppData\LocalLow\7th Beat Games\A Dance of Fire and Ice\CustomLevels\
```

## 프로젝트 구조

```
adofai-auto-macro/
├── main.py              # 메인 실행 스크립트
├── config.yaml          # 설정 파일
├── requirements.txt     # Python 의존성
├── README.md
└── src/
    ├── __init__.py
    ├── level_parser.py    # .adofai 파일 파서 (타이밍 계산)
    ├── level_finder.py    # 현재 플레이 중인 맵 자동 탐색
    ├── auto_player.py     # 타이밍 기반 자동 키 입력
    └── overlay.py         # 상태 오버레이
```

## 팁

- **딜레이 조정**: 게임 시작과 매크로 시작 사이에 타이밍이 맞지 않으면 `--delay` 옵션으로 조정하세요
- **카운트다운 활용**: 카운트다운 동안 게임에서 레벨을 시작하면 타이밍을 맞추기 쉽습니다
- **레벨 정보 확인**: `--info` 옵션으로 먼저 레벨의 BPM, 타일 수, 길이를 확인하세요
- **자동 탐색 정확도**: 게임에서 맵을 한 번 로드하면 Player.log에 기록되어 자동 탐색 정확도가 올라갑니다

## 주의 사항

- 이 매크로는 **개인 연습 및 학습 목적**으로만 사용하세요.
- 온라인 랭킹이나 경쟁 환경에서의 사용은 권장하지 않습니다.

## 라이선스

MIT License
