# 얼불춤 자동 매크로 (ADOFAI Auto Macro)

**A Dance of Fire and Ice** 게임의 `.adofai` 레벨 파일을 파싱하여, 각 타일의 정확한 타이밍에 맞춰 자동으로 키를 입력하는 매크로입니다.

---

## 동작 원리

1. `.adofai` 레벨 파일에서 **타일 각도(angleData/pathData)**, **BPM**, **SetSpeed**, **Twirl** 이벤트를 파싱
2. 각 타일의 상대 각도를 계산하여 정확한 입력 타이밍(ms)을 산출
3. 게임 내에서 계산된 타이밍에 맞춰 자동으로 키를 입력

### 타이밍 계산 공식
```
상대 각도 = (다음타일각도 - 현재타일각도 + 540) % 360
입력 간격(ms) = (1000 × 상대각도) / (3 × BPM)
```

## 기능

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

### 기본 실행

```bash
# .adofai 파일 경로를 인자로 전달
python main.py "C:\경로\레벨파일.adofai"
```

### 옵션

```bash
# 입력 키 변경 (기본: space)
python main.py level.adofai --key d

# 시작 딜레이 추가 (ms)
python main.py level.adofai --delay 200

# 카운트다운 변경 (기본: 3초)
python main.py level.adofai --countdown 5

# 레벨 정보만 출력
python main.py level.adofai --info

# 오버레이 비활성화
python main.py level.adofai --no-overlay
```

### 실행 순서

1. 얼불춤 게임을 실행합니다
2. 플레이할 레벨을 선택하고 시작 화면까지 진입합니다
3. 매크로를 실행합니다: `python main.py "레벨파일.adofai"`
4. 게임에서 레벨을 시작합니다
5. **F6**을 눌러 매크로를 시작합니다 (3초 카운트다운 후 자동 입력 시작)
6. **F6**을 다시 눌러 중지하거나, **F8**로 프로그램을 종료합니다

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
    ├── auto_player.py     # 타이밍 기반 자동 키 입력
    └── overlay.py         # 상태 오버레이
```

## 팁

- **딜레이 조정**: 게임 시작과 매크로 시작 사이에 타이밍이 맞지 않으면 `--delay` 옵션으로 조정하세요
- **카운트다운 활용**: 카운트다운 동안 게임에서 레벨을 시작하면 타이밍을 맞추기 쉽습니다
- **레벨 정보 확인**: `--info` 옵션으로 먼저 레벨의 BPM, 타일 수, 길이를 확인하세요

## 주의 사항

- 이 매크로는 **개인 연습 및 학습 목적**으로만 사용하세요.
- 온라인 랭킹이나 경쟁 환경에서의 사용은 권장하지 않습니다.

## 라이선스

MIT License
