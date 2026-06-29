# PRD: Pressure & Level 모니터링 시스템

## 1. 개요

저온 실험 장비의 압력 및 액위(液位)를 실시간으로 수집·표시·기록하고, 임계값 초과 시 이메일로 경보를 발송하는 시스템이다.

---

## 2. 구성 요소

```
[압력/레벨 센서 × 4]
        ↓ (아날로그 전압)
[Arduino Mega — ArduinoADCReceiver.ino]
        ↓ (Serial 9600 baud, 500 ms 주기)
[ArduinoADCReceiver.py — HTTP 서버 :5003]
        ↓ (HTTP GET /Meas, 1 s 폴링)
[PressureLevelPlotter.py — Tkinter GUI]
        ↓
  · 실시간 그래프 (matplotlib)
  · 1분 주기 로그 파일 저장
  · 이상 감지 → 이메일 알림 (CustomMail)
```

---

## 3. 모듈 상세

### 3-1. `ArduinoADCReceiver.ino` (펌웨어)

| 항목 | 내용 |
|---|---|
| 측정 핀 | A0 (P_st), A8 (P_pl), A15 (V_pl), A1 (P_pur) |
| 샘플링 주기 | 1 ms 루프, 500회마다 Serial 전송 (≈ 500 ms) |
| 하드웨어 필터 | 1차 지수 저역통과 필터, β = 0.9875 (차단주파수 ≈ 2 Hz) |
| 전송 포맷 | `float,float,float,float\n` (쉼표 구분 CSV) |

### 3-2. `ArduinoADCReceiver.py` (수신 데몬)

- Serial 포트·HTTP 포트 등은 `arduinoadcreceiver_config.json`에서 읽는다. 파일이 없거나 잘못되면 기본값으로 자동 생성한다.
- 수신값에 소프트웨어 지수 필터(β = `exp(-2π × arduino_period / filter_cutoff_second)`)를 추가 적용한다.
- `localhost:<localserver_port>/Meas` HTTP GET 엔드포인트로 최신 측정값을 JSON 노출한다.

**변환 공식**

| 채널 | 물리량 | 변환식 |
|---|---|---|
| A0 | P_storage (psi) | `0.06104 × bit − 5.82056` |
| A8 | P_plant (psi) | `0.01865 × bit − 3.40120` |
| A15 | V_plant (L) | level = `0.06807 × bit − 0.81458` → 4차 다항식 변환 |
| A1 | P_purifier (psi) | `0.06104 × bit − 5.82056` |

**응답 JSON 스키마**

```json
{
  "P_st":  "6.123",
  "P_pl":  "1.456",
  "V_pl":  "72.300",
  "P_pur": "1.200",
  "timestamp": 1700000000.0
}
```

- `timestamp`가 현재 시각 기준 5초 초과 시 플로터는 해당 데이터를 무효 처리한다.

### 3-3. `PressureLevelPlotter.py` (GUI 플로터)

#### 캘리브레이션

- 채널별 2점 선형 매핑을 지원한다: `(orig1, calib1)`, `(orig2, calib2)` 두 점으로부터 `calibrated = slope × raw + offset`을 계산한다.
- `arduino_deque`에는 **항상 raw 값**만 저장하며, 캘리브레이션은 표시·플롯·로그 저장·이메일 임계값 비교 직전에만 적용한다.
- 설정은 `plotter_config.json`의 `"calibrations"` 키에 저장된다.

#### 설정 영속성 (`plotter_config.json`)

시작 시 `plotter_config.json`을 읽어 아래 세 가지 설정을 복원한다. 파일이 없거나 파싱에 실패하면 기본값으로 자동 복구한다.

| 키 | 내용 | 기본값 |
|---|---|---|
| `calibrations` | 채널별 2점 매핑 파라미터 | identity map (보정 없음) |
| `channel_order` | 우측 패널 표시 순서 | `[0, 1, 2, 3]` |
| `channel_visible` | 채널별 그래프 표시 여부 | `[true, true, true, true]` |

설정 변경 시점(Setting 창 닫기, Cal 창 Apply)에 즉시 파일에 기록한다.

> **마이그레이션**: 구버전 `calibration.json`이 존재하면 시작 시 자동으로 `plotter_config.json`으로 이전 후 삭제한다.

#### Auto Raise

상단 **"Auto Raise (30 min)"** 체크박스를 켜면 30분마다 창을 최상위로 강제로 올린다. 체크박스를 끄면 즉시 비활성화된다. `IS_TEST = True` 환경에서는 30초 간격으로 동작한다.



- Tkinter 윈도우 + matplotlib TkAgg 백엔드를 사용한다.
- 별도 스레드(`fetch_loop`)가 1초마다 HTTP 데이터를 수집하여 `VariousTimeDeque`에 저장한다.
- GUI 메인 루프는 200 ms 주기로 `update_display`를 호출한다.
- **시작 시 로그 복원**: `log_pressurelevel/`에 저장된 1분 주기 로그가 있으면, 각 인터벌 버퍼의 `N × T` 윈도우(예: 1 s → 100 s, 1 hour → 100 h) 안의 기록만 읽어 deque를 채운다. 로그에는 calibrated 값이 저장되므로, deque에 넣기 전 `reverse_calibration()`으로 raw로 되돌린다. 해당 구간에 로그가 없으면 버퍼는 비어 있거나 0으로 초기화된다.

**표시 채널**

| 레이블 | 데이터 | 축 | 색상 |
|---|---|---|---|
| Volume | V_plant | 왼쪽 y (L) | blue |
| P_plant | P_pl | 오른쪽 y (psi) | green |
| P_storage | P_st | 오른쪽 y (psi) | red |
| P_purifier | P_pur | 오른쪽 y (psi) | skyblue |

**그래프 인터벌 선택**

`VariousTimeDeque`가 네 가지 해상도의 링 버퍼(각 100개)를 관리한다.

| 선택 | 버퍼 | x축 포맷 |
|---|---|---|
| 1 s | 초별 데이터 | `HH:MM:SS` |
| 1 min | 분별 데이터 | `HH:MM` |
| 10 min | 10분별 데이터 | `MM-DD HH:MM` |
| 1 hour | 시간별 데이터 | `MM-DD HH:MM` |

**설정 창 (`PressureLevelSetting`)**

- 우측 패널의 채널 표시 순서를 위/아래 화살표로 재배치할 수 있다.
- 체크박스로 각 채널의 그래프 표시 여부를 독립적으로 제어한다.
- 각 채널 행 옆 **Cal** 버튼으로 해당 채널의 캘리브레이션 창(`CalibrationWindow`)을 열 수 있다. 같은 채널 창이 이미 열려 있으면 앞으로 가져온다.

---

### 3-4. `CalibrationWindow.py` (캘리브레이션 창)

Setting 창에서 채널별 **Cal** 버튼을 눌러 열 수 있는 논모달 `tk.Toplevel` 창이다.

| 구성 요소 | 내용 |
|---|---|
| 상단 레이블 | 현재 raw 값 실시간 표시 (200 ms 갱신) |
| 중단 2×2 매트릭스 | Point 1·2의 Original / Calibrated Entry 입력 |
| Apply 버튼 | 입력값 검증 후 `plotter_config.json`에 즉시 저장 |

- `orig1 == orig2`인 경우 에러 다이얼로그로 입력을 방지한다.
- 채널당 창이 1개만 열리며, 중복 클릭 시 기존 창을 앞으로 가져온다.

---

## 4. 이상 감지 및 알림

이메일 알림은 `CustomMail.send_mail()`을 통해 SMTP SSL로 발송된다. 설정은 `mail_config.json`에서 관리한다.

| 조건 | 체크 주기 | 알림 내용 |
|---|---|---|
| Arduino HTTP 연결 끊김 | 10분 | "Arduino is disconnected" |
| P_plant > 3.0 psi **또는** P_storage > 9.0 psi | 10분 | "Pressure is too high" |
| P_plant < 0.25 psi | 10분 | "Storage Pressure is too low" |

- 이메일 발송 실패 시 GUI에 논모달 경고 창(`show_email_alert`)을 표시한다.
- 발송 결과(성공/실패)는 `maillog.txt`에 기록된다.

---

## 5. 로그 저장

- 저장 주기: 1분마다 (`VariousTimeDeque`의 1분 버퍼 갱신 시점)
- 저장 경로: `log_pressurelevel/YYYY/MM/DD.txt`
- 저장 형식:

```
2024-11-01 14:30:00: 72.30 L, 1.46 psi, 6.12 psi, 1.20 psi
```

필드 순서: `V_plant`, `P_plant`, `P_storage`, `P_purifier`

---

## 6. 설정 파일

### `arduinoadcreceiver_config.json`

`ArduinoADCReceiver.py`와 같은 디렉터리(또는 exe 옆)에 위치한다. 첫 실행 시 자동 생성된다.

```json
{
  "arduino_port": "COM4",
  "localserver_port": 5003,
  "baud_rate": 9600,
  "serial_timeout": 1,
  "reconnect_delay": 1.0,
  "loop_sleep": 0.1,
  "buffer_flush_interval": 30,
  "filter_cutoff_second": 10,
  "arduino_period": 0.5
}
```

| 키 | 설명 | 기본값 |
|---|---|---|
| `arduino_port` | Arduino Serial 포트 | `"COM4"` |
| `localserver_port` | HTTP 서버 포트 | `5003` |
| `baud_rate` | Serial baud rate | `9600` |
| `serial_timeout` | Serial read timeout (초) | `1` |
| `reconnect_delay` | 연결 실패 후 재시도 대기 (초) | `1.0` |
| `loop_sleep` | 메인 루프 폴링 간격 (초) | `0.1` |
| `buffer_flush_interval` | Serial 버퍼 flush 주기 (초) | `30` |
| `filter_cutoff_second` | 소프트웨어 LPF cutoff (초) | `10` |
| `arduino_period` | Arduino 전송 주기 (초, 펌웨어 500 ms와 일치) | `0.5` |

> PC를 옮길 때는 `arduino_port`만 해당 환경의 COM 포트로 수정하면 된다.

### `mail_config.json`

```json
{
  "smtp_server": "smtp.example.com",
  "smtp_port": 465,
  "smtp_user": "sender@example.com",
  "smtp_password": "password",
  "sender_name": "Lab Monitor",
  "recipients": ["recipient@example.com"]
}
```

---

## 7. 빌드 및 배포

- PyInstaller로 단일 exe 빌드를 지원한다 (`makefile.bat`).
- `resource_path()`가 개발 환경과 PyInstaller `_MEIPASS` 환경 모두에서 리소스 경로를 올바르게 반환한다.
- 테스트 모드: `PressureLevelPlotter.py` 상단의 `IS_TEST = True`로 설정하면 사인파 기반 시뮬레이션 데이터를 사용한다.

---

## 8. 파일 목록

```
Pressure_and_Level/
├── ArduinoADCReceiver/
│   ├── ArduinoADCReceiver.ino          # Arduino 펌웨어
│   ├── ArduinoADCReceiver.py           # Serial → HTTP 브릿지
│   └── arduinoadcreceiver_config.json  # 실행 시 자동 생성 — Serial/HTTP 설정
└── PressureLevelPlotter/
    ├── PressureLevelPlotter.py  # GUI 메인
    ├── PressureLevelSetting.py  # 설정 창 (채널 순서·표시·Cal 버튼)
    ├── CalibrationWindow.py     # 채널별 캘리브레이션 창
    ├── VariousTimeDeque.py      # 멀티 인터벌 링 버퍼
    ├── CustomDateLocator.py     # x축 눈금 위치 계산
    ├── CustomMail.py            # SMTP 이메일 발송
    ├── plotter_config.json      # 실행 시 자동 생성 — 캘리브레이션·채널 설정
    └── makefile.bat             # PyInstaller 빌드 스크립트
```
