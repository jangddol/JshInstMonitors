# PRD: JshInstMonitors

## 1. 프로젝트 개요

**JshInstMonitors**는 극저온 물리 실험실의 계측 장비를 PC에서 실시간으로 모니터링하기 위한 Python GUI 애플리케이션 모음이다. 각 서브시스템은 독립된 프로세스로 동작하며, 로컬 HTTP 서버를 통해 데이터를 교환한다.

---

## 2. 서브시스템 목록

| 서브시스템 | 측정 대상 | 상세 PRD |
|---|---|---|
| Pressure & Level | 저장소/플랜트/정화기 압력, 플랜트 액위(부피) | [Pressure_and_Level/PRD.md](Pressure_and_Level/PRD.md) |
| Flow & Temperature | MFC 4채널 유량, 온도 컨트롤러 2채널 온도 | [Flow_and_Temp/PRD.md](Flow_and_Temp/PRD.md) |
| Current Monitor | 전류 1채널 | (별도 PRD 없음 — 경량 모니터) |

---

## 3. 전체 아키텍처

각 서브시스템은 동일한 3계층 구조를 따른다.

```
[실험 장비]
    ↓  Serial(Arduino) 또는 GPIB(IEEE 488.2)
[수집 데몬 / 수신 프로세스]
    ↓  localhost HTTP (1초 폴링)
[Plotter GUI]
    ↓
  · Tkinter + matplotlib 실시간 그래프
  · 멀티 인터벌 링 버퍼 (1s / 1min / 10min / 1hour)
  · 데이터 로그 (1분 주기)
  · 기능 로그 (INFO / CAUTION / ERROR / CRITICAL)
  · SMTP 이메일 경보 + 메일 로그
```

---

## 4. 공통 컴포넌트

| 컴포넌트 | 위치 | 역할 |
|---|---|---|
| `paths.py` | `common/` | `app_dir` / `writable_path` / `bundle_path` — 쓰기 파일은 exe(또는 엔트리 스크립트) 옆, 아이콘 등은 번들 경로 |
| `FuncLogger.py` | `common/` | 일별 기능 로그 (`flog_<subsystem>/YYYY/MM/DD.txt`) |
| `VariousTimeDeque` | 각 Plotter 디렉터리 | 4가지 시간 해상도 링 버퍼 (+ `load_historical`로 로그 복원) |
| `CustomDateLocator` | 각 Plotter 디렉터리 | 인터벌별 x축 눈금 위치 계산 |
| `CustomMail` | 각 Plotter 디렉터리 | SMTP SSL 이메일 발송 + 구조화 메일 로그 |
| `log_viewer/LogViewer.py` | 루트 | 저장된 데이터 로그 파일 탐색 및 열람 |

> 배포 시 소스도 함께 배포하므로, Plotter별 `VariousTimeDeque` / `CustomMail` 등은 의도적으로 복제본을 유지한다. 공유 로직만 `common/`에 둔다.

---

## 5. 로그 종류

모든 쓰기 경로는 **실행 파일(또는 개발 시 엔트리 스크립트)과 같은 디렉터리**를 기준으로 한다.

| 종류 | 경로 | 내용 |
|---|---|---|
| 데이터 로그 | `log_pressurelevel/`, `log_flowtemp/`, `log_current/` | 1분 주기 측정값 (레거시 디렉터리명 유지) |
| 기능 로그 | `flog_pressurelevel/`, `flog_flowtemp/` | 기동·연결·경보·예외 등 운영 이벤트 |
| 메일 로그 | `maillog_pressurelevel.txt`, `maillog_flowtemp.txt` | 메일 성공/실패와 실패 stage |

### 기능 로그 포맷

```text
[2026-07-09 13:37:00] [INFO] [PressureLevelPlotter] PressureLevelPlotter started
[2026-07-09 13:37:10] [ERROR] [ArduinoADCReceiver] Failed to open serial port: ...
```

레벨: `INFO` / `CAUTION` / `ERROR` / `CRITICAL`

### 메일 로그 포맷

```text
[2026-07-09 13:37:00] [SUCCESS] stage=smtp_send subject="..." recipients=2 smtp=host:465 user=...
[2026-07-09 13:37:01] [FAIL] stage=config_load detail=Configuration file not found: ...
```

`stage`: `config_load` | `recipient_validate` | `message_build` | `smtp_connect` | `smtp_login` | `smtp_send`

---

## 6. 공통 설정

### 이메일 알림 (`mail_config.json`)

각 Plotter 실행 파일과 같은 디렉터리에 위치해야 한다.

```json
{
  "smtp_server":   "smtp.example.com",
  "smtp_port":     465,
  "smtp_user":     "sender@example.com",
  "smtp_password": "password",
  "sender_name":   "Lab Monitor",
  "recipients":    ["recipient@example.com"]
}
```

---

## 7. 사전 설치 요구사항

| 항목 | 비고 |
|---|---|
| Python 3.x | tkinter, matplotlib, requests, pyserial 등 |
| NI IEEE 488.2 드라이버 | GPIB 장비(DRC91C, Lakeshore330) 사용 시 필수 |
| pyvisa | GPIB 통신 Python 래퍼 |
| Flask | DRC91C 데몬 HTTP 서버 |
| tkinterdnd2 | LogViewer 드래그 앤 드롭 |

---

## 8. 디렉터리 구조

```
JshInstMonitors/
├── PRD.md
├── common/
│   ├── paths.py
│   └── FuncLogger.py
├── Pressure_and_Level/
│   ├── PRD.md
│   ├── ArduinoADCReceiver/
│   └── PressureLevelPlotter/
├── Flow_and_Temp/
│   ├── PRD.md
│   ├── FlowTempPlotter/
│   ├── RFM/
│   ├── DRC91C/
│   └── Lakeshore330/
├── Current_Monitor/
│   ├── CurrentPlotter/
│   └── CurrentReceiver/
├── log_viewer/
├── log_pressurelevel/            # 자동 생성 (데이터 로그)
├── log_flowtemp/                 # 자동 생성
├── log_current/                  # 자동 생성
├── flog_pressurelevel/           # 자동 생성 (기능 로그)
└── flog_flowtemp/                # 자동 생성
```
