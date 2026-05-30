# 얼불춤 자동 매크로 (ADOFAI Auto Macro)

**A Dance of Fire and Ice** 게임의 `.adofai` 레벨 파일을 파싱하여, 각 타일의 정확한 타이밍에 맞춰 자동으로 키를 입력하는 매크로입니다.

---

## 동작 원리

1. **현재 플레이 중인 맵을 자동으로 탐색** (파일 경로를 직접 입력할 필요 없음)
2. `.adofai` 레벨 파일에서 **타일 각도(angleData/pathData)**, **BPM**, **SetSpeed**, **Twirl**, **Pause**, **AutoPlayTiles**, **Hold(롱노트)** 이벤트를 파싱
3. 각 타일의 상대 각도를 계산하여 정확한 입력 타이밍(ms)을 산출
4. 게임 내에서 계산된 타이밍에 맞춰 자동으로 키를 입력

### 맵 자동 탐색 방식

파일을 직접 지정하지 않으면 다음 순서로 현재 맵을 찾습니다:

1. **Windows 레지스트리(`lastOpenedLevel`)** — 게임이 마지막으로 연 맵 경로. **가장 정확** (Unity PlayerPrefs에 저장됨)
2. **Windows 레지스트리(`lastUsedFolder`)** — 마지막으로 사용한 폴더 안에서 가장 최근에 수정된 `.adofai` (워크샵 맵 등 `lastOpenedLevel`이 비었을 때의 보조 수단)
3. **ADOFAI Player.log 분석** — 로그에 `.adofai` 경로가 남아 있으면 추출 (※ 버전에 따라 안 남을 수 있음)
4. **레벨 폴더 스캔** — Steam 워크샵 / 커스텀 레벨 폴더에서 가장 최근에 수정된 `.adofai` 파일
5. **목록 선택** — `--select`(직접 선택) / `--list`(목록만 보기) 옵션으로 탐색된 맵을 곡명·BPM과 함께 확인

> 게임에서 평소 하던 맵을 **한 번 연 직후** 매크로를 실행하면 레지스트리 값으로 정확히 그 맵을 찾습니다. 스팀 워크샵 맵을 게임 내 목록에서 바로 플레이하는 경우 레지스트리가 갱신되지 않을 수 있으니, 이때는 `--select`로 고르세요.

### 타이밍 계산 공식
```
상대 각도 = (180 + 현재타일각도 - 다음타일각도) % 360
입력 간격(ms) = (1000 × 상대각도) / (3 × BPM)
```
이 상대각 계산은 권위 있는 ADOFAI 파싱 라이브러리 [`adofaipy`](https://pypi.org/project/adofaipy/)와 **실제 맵 14,720타일 전부에서 100% 일치**함을 자동 테스트로 검증했습니다.

### 지원하는 이벤트

| 이벤트 | 지원 | 설명 |
|---|---|---|
| `angleData` / `pathData` | ✅ | 타일 각도 (구/신 포맷 모두) |
| `SetSpeed` (Bpm) | ✅ | BPM 직접 변경 |
| `SetSpeed` (Multiplier) | ✅ | BPM 배율 변경 (누적 적용) |
| `Twirl` | ✅ | 회전 방향 반전 (절대각 반사 방식) |
| 미드스핀(999) | ✅ | 미드스핀 타일 |
| `Pause` | ✅ | 멈춤 구간 → 이후 타일 타이밍 전체 보정 |
| `AutoPlayTiles` | ✅ | 게임이 자동으로 치는 구간은 매크로가 입력하지 않음 |
| `Hold` | ✅ | 롱노트: 시작 타일에서 키를 누른 채 duration 타일만큼 유지 후 자동 해제 (유지 구간 타일은 입력 제외) |
| `RepeatEvents` | N/A | 장식(MoveDecorations) 반복만 하므로 게임플레이 타이밍에 영향 없음 |

## 기능

- **맵 자동 탐색**: 현재 플레이 중인 맵을 레지스트리 → Player.log → 폴더 스캔 순으로 자동 감지
- **.adofai 파일 파싱**: angleData, pathData 모두 지원
- **BPM 변경 지원**: SetSpeed 이벤트(Bpm / Multiplier) 자동 반영
- **Twirl / 미드스핀 지원**: 회전 반전·미드스핀 타일 자동 처리
- **Pause / AutoPlayTiles / Hold 지원**: 멈춤 구간 타이밍 보정, 자동 재생 구간 입력 제외, 롱노트 누름 유지/자동 해제
- **다중 키 순환 입력**: 기본 `QWERTYUIOP` 10키를 번갈아 눌러 게임의 채터 블로커 회피
- **동타·삼각형·트월 등 빠른 구간 보정(`--min-gap`)**: ADOFAI는 한 프레임에 입력을 한 번만 인식하므로, 같은 프레임에 두 입력이 몰리면 하나가 씹힙니다. 입력 사이에 최소 간격을 둬 각 입력이 별도 프레임에 들어가게 합니다. **미지정 시 게임/모니터 주사율을 자동 감지**해 한 프레임 길이로 자동 설정(예: 144Hz→약 8ms, 감지 실패 시 16ms)
- **드라이런(`--dry-run`)**: 키 입력 없이 타일별 타이밍 표만 출력해 안전하게 검증
- **구간 연습(`--start-tile N`)**: 특정 타일 번호부터 재생 시작
- **맵 목록 보기(`--list`)**: 탐색된 맵을 곡명·BPM과 함께 한눈에 확인
- **정밀 타이밍**: busy-wait 기반 고정밀 키 입력
- **카운트다운 / 상태 오버레이 / 핫키 제어**: F6(시작/중지), F8(종료)

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

# 탐색된 맵 목록(곡명·BPM)만 출력하고 종료
python main.py --list

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
# 입력 키 변경 (기본: q,w,e,r,t,y,u,i,o,p — 타일마다 순환)
python main.py --key d
python main.py --key d,f,j,k     # 쉼표로 여러 키를 주면 번갈아 누름
python main.py --key space       # 한 키만 쓰려면 단일 키 지정

# 시작 딜레이 추가 (ms)
python main.py --delay 200

# 빠른 구간 입력 보정 간격 직접 지정 (ms). 미지정 시 주사율 자동 감지
python main.py --min-gap 8         # 144Hz 모니터면 수동으로 ~8ms 권장
python main.py --min-gap 0         # 보정 끄기(동타/삼각형이 한 번만 인식될 수 있음)

# 카운트다운 변경 (기본: 3초)
python main.py --countdown 5

# 레벨 정보만 출력
python main.py --info

# 키 입력 없이 타일별 타이밍 표만 출력 (안전 검증)
python main.py --dry-run
python main.py --dry-run --start-tile 500   # 500번 타일부터 표시

# 특정 타일 번호부터 재생 시작 (구간 연습)
python main.py --start-tile 500

# 오버레이 비활성화
python main.py --no-overlay
```

### 실행 순서

1. 얼불춤 게임을 실행합니다
2. 플레이할 레벨을 한 번 선택/로드합니다 (레지스트리 `lastOpenedLevel`에 기록됨)
3. 매크로를 실행합니다: `python main.py` (자동으로 해당 맵을 찾습니다)
4. 게임에서 레벨을 시작합니다
5. **F6**을 눌러 매크로를 시작합니다 (3초 카운트다운 후 자동 입력 시작)
6. **F6**을 다시 눌러 중지하거나, **F8**로 프로그램을 종료합니다

> 자동 탐색이 잘못된 맵을 고른다면 `python main.py --select`로 목록에서 직접 고르거나, 파일 경로를 직접 지정하세요.

## 키보드 채터 블로커(KeyboardChatterBlocker) 주의

얼불춤은 같은 키가 너무 빠르게 연타되면 "채터링"으로 간주해 입력을 **무시**합니다 (로그의 `[KeyboardChatterBlocker] Blocked Async Key`). 그래서 이 매크로는 기본적으로 `QWERTYUIOP` 10개 키를 **번갈아** 눌러 동일 키 연타를 피합니다. 빠른 구간에서 입력이 씹히면 `--key`로 더 많은 키로 분산하거나 게임 설정에서 채터 블로커를 끄세요.

> 참고: **Camellia - Hello (BPM)** 같은 초고속 쇼케이스 맵은 BPM이 4000~100000까지 치솟아 초당 1000타 이상이 필요합니다. 사람도 매크로도 칠 수 없는 "보는 용도" 맵이니, 동작 확인은 평범한 BPM의 일반 맵으로 하세요.

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

## 개발 / 테스트

파서·이벤트·키 입력 로직을 검증하는 pytest 스위트가 있습니다 (X 디스플레이·게임 없이 실행 가능):

```bash
pip install -r requirements-dev.txt   # pytest + adofaipy 포함
pytest
```

각도 계산은 `adofaipy`와 무작위 합성 맵으로 교차검증되며, Pause/AutoPlayTiles/SetSpeed/Hold 타이밍과 키 순환·자동타일/홀드 건너뛰기·구간 시작(`--start-tile`)·맵 메타 추출(`--list`)도 테스트합니다 (총 58개 테스트).

## 프로젝트 구조

```
adofai-auto-macro/
├── main.py              # 메인 실행 스크립트
├── config.yaml          # 설정 파일
├── requirements.txt     # Python 의존성
├── README.md
├── src/
│   ├── __init__.py
│   ├── level_parser.py    # .adofai 파일 파서 (타이밍 계산)
│   ├── level_finder.py    # 현재 플레이 중인 맵 자동 탐색
│   ├── auto_player.py     # 타이밍 기반 자동 키 입력
│   └── overlay.py         # 상태 오버레이
├── tests/                 # pytest 테스트 스위트
└── requirements-dev.txt   # 개발/테스트 의존성
```

## 팁

- **딜레이 조정**: 게임 시작과 매크로 시작 사이에 타이밍이 맞지 않으면 `--delay` 옵션으로 조정하세요
- **카운트다운 활용**: 카운트다운 동안 게임에서 레벨을 시작하면 타이밍을 맞추기 쉽습니다
- **레벨 정보 확인**: `--info` 옵션으로 먼저 레벨의 BPM, 타일 수, 길이를 확인하세요
- **자동 탐색 정확도**: 게임에서 맵을 한 번 연 직후 실행하면 레지스트리(`lastOpenedLevel`)에서 정확히 그 맵을 찾습니다

## 주의 사항

- 이 매크로는 **개인 연습 및 학습 목적**으로만 사용하세요.
- 온라인 랭킹이나 경쟁 환경에서의 사용은 권장하지 않습니다.

## 라이선스

MIT License
