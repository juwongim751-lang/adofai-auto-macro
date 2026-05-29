# 🔥 얼불춤 자동 매크로 (ADOFAI Auto Macro)

**A Dance of Fire and Ice** 게임 화면의 KPS(Keys Per Second) 표시를 OCR로 인식하여, 해당 속도에 맞춰 자동으로 키를 입력하는 매크로입니다.

---

## 기능

- **KPS 자동 인식**: 화면 오른쪽 상단의 KPS 표시를 실시간 OCR로 읽어냄
- **자동 키 입력**: 인식된 KPS에 맞춰 정밀한 타이밍으로 키를 자동 입력
- **상태 오버레이**: 현재 매크로 상태를 화면에 오버레이로 표시
- **핫키 제어**: F6(시작/중지), F7(영역 재설정), F8(종료)
- **설정 파일**: YAML 기반 설정으로 모든 옵션을 커스터마이즈 가능

## 요구 사항

- Python 3.10 이상
- Tesseract OCR 설치 필요

### Tesseract 설치

**Windows:**
```bash
# Chocolatey
choco install tesseract

# 또는 공식 설치 파일 다운로드:
# https://github.com/UB-Mannheim/tesseract/wiki
```

**macOS:**
```bash
brew install tesseract
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get install tesseract-ocr
```

## 설치

```bash
# 레포지토리 클론
git clone https://github.com/juwongim751-lang/adofai-auto-macro.git
cd adofai-auto-macro

# 가상 환경 생성 (권장)
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt
```

## 사용법

### 기본 실행

```bash
python main.py
```

### 캡처 영역 설정

KPS가 정확히 인식되지 않으면, 캡처 영역을 수동으로 설정하세요:

```bash
python main.py --set-region
```

### 사용자 설정 파일 사용

```bash
python main.py --config my_config.yaml
```

## 핫키

| 키 | 기능 |
|---|---|
| **F6** | 매크로 시작/중지 토글 |
| **F7** | 캡처 영역 재설정 |
| **F8** | 프로그램 종료 |

핫키는 `config.yaml`에서 변경 가능합니다.

## 설정 (config.yaml)

```yaml
# 캡처 설정
capture:
  region: auto          # 자동 감지 또는 수동 좌표 설정
  interval: 0.05        # 캡처 주기 (초)

# 매크로 설정
macro:
  key: space            # 입력 키 (space, d, f, j, k)
  min_kps: 0.5          # 최소 KPS 임계값
  max_kps: 30.0         # 최대 KPS 제한

# 핫키 설정
hotkeys:
  toggle: f6            # 매크로 토글
  quit: f8              # 종료
  reset_region: f7      # 영역 재설정
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
    ├── screen_capture.py  # 화면 캡처 모듈
    ├── kps_reader.py      # KPS OCR 인식 모듈
    ├── auto_player.py     # 자동 키 입력 모듈
    └── overlay.py         # 상태 오버레이 모듈
```

## 주의 사항

- 이 매크로는 **개인 연습 및 학습 목적**으로만 사용하세요.
- 온라인 랭킹이나 경쟁 환경에서의 사용은 권장하지 않습니다.
- KPS 인식 정확도는 게임 설정(해상도, 폰트 크기 등)에 따라 달라질 수 있습니다.
- Tesseract OCR이 시스템에 설치되어 있어야 합니다.

## 라이선스

MIT License
