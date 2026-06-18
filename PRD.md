# PRD: JshInstMonitors

## 1. 프로젝트 개요

**JshInstMonitors**는 극저온 물리 실험실의 계측 장비를 PC에서 실시간으로 모니터링하기 위한 Python GUI 애플리케이션 모음이다. 각 서브시스템은 독립된 프로세스로 동작하며, 로컬 HTTP 서버를 통해 데이터를 교환한다.

---

## 2. 서브시스템 목록

| 서브시스템 | 측정 대상 | 상세 PRD |
|---|---|---|
| Pressure & Level | 저장소/플랜트/정화기 압력, 플랜트 액위(부피) | [Pressure_and_Level/PRD.md](Pressure_and_Level/PRD.md) |
| Flow & Temperature | MFC 4채널 유량, 온도 컨트롤러 2채널 온도 | [Flow_and_Temp/PRD.md](Flow_and_Temp/PRD.md) |

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
  · 분 단위 로그 파일 저장
  · SMTP 이메일 경보
```

---

## 4. 공통 컴포넌트

| 컴포넌트 | 위치 | 역할 |
|---|---|---|
| `VariousTimeDeque` | 각 Plotter 디렉터리 | 4가지 시간 해상도 링 버퍼 |
| `CustomDateLocator` | 각 Plotter 디렉터리 | 인터벌별 x축 눈금 위치 계산 |
| `CustomMail` | 각 Plotter 디렉터리 | SMTP SSL 이메일 발송 |
| `log_viewer/LogViewer.py` | 루트 | 저장된 로그 파일 탐색 및 열람 |

---

## 5. 공통 설정

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

이메일 발송 결과는 동일 디렉터리의 `maillog.txt`에 기록된다.

---

## 6. 사전 설치 요구사항

| 항목 | 비고 |
|---|---|
| Python 3.x | tkinter, matplotlib, requests, pyserial 등 |
| NI IEEE 488.2 드라이버 | GPIB 장비(DRC91C, Lakeshore330) 사용 시 필수 |
| pyvisa | GPIB 통신 Python 래퍼 |
| Flask | DRC91C 데몬 HTTP 서버 |

---

## 7. 디렉터리 구조

```
JshInstMonitors/
├── PRD.md                        ← 현재 문서
├── Pressure_and_Level/
│   ├── PRD.md                    ← Pressure & Level 상세 PRD
│   ├── ArduinoADCReceiver/
│   └── PressureLevelPlotter/
├── Flow_and_Temp/
│   ├── PRD.md                    ← Flow & Temperature 상세 PRD
│   ├── FlowTempPlotter/
│   ├── RFM/
│   ├── DRC91C/
│   └── Lakeshore330/
├── Current_Monitor/              # (별도 PRD 없음)
│   ├── CurrentPlotter/
│   └── CurrentReceiver/
├── log_pressurelevel/            # 자동 생성 로그 디렉터리
├── log_viewer/
└── READ.me
```
