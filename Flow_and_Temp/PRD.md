# PRD: Flow & Temperature 모니터링 시스템

## 1. 개요

극저온 냉각 시스템의 헬륨 유량(MFC 4채널)과 온도 컨트롤러 2채널을 실시간으로 수집·표시·기록하고, 장비 연결 이상 시 이메일로 경보를 발송하는 시스템이다.

---

## 2. 구성 요소

```
[MKS247C MFC × 4채널]               [DRC91C / Lakeshore330]
        ↓ (아날로그 제어)                     ↓ (GPIB IEEE 488.2)
[Arduino — RFM 시리얼 브릿지]        [DRC91Cdaemon.py / Lakeshore330.py]
        ↓ (Serial 9600 baud)                 ↓ (Flask/HTTP 서버, 기본 :5001)
[RFMdaemon.py — GUI + HTTP 서버]
   · MFC 채널 On/Off 제어
   · 유량 설정값 입력
   · 스케줄러 (주간 자동 제어)
   · HTTP 서버 (기본 :5000) → 유량값 노출
        ↓                                    ↓
        +-----------+  HTTP 폴링  +-----------+
                    ↓
          [FlowTempPlotter.py — Tkinter GUI]
                    ↓
          · 실시간 그래프 (matplotlib)
          · 시작 시 데이터 로그 복원
          · 1분 주기 데이터 로그 + 기능 로그
          · 이상 감지 → 이메일 알림 (CustomMail) + 메일 로그
```

> NI IEEE 488.2 드라이버(`pyvisa` 백엔드) 설치가 필요하다. (`READ.me` 참조)

---

## 3. 모듈 상세

### 3-1. `RFMdaemon.py` — MFC 제어 GUI + HTTP 서버

- MKS247C를 Arduino로 제어하는 흑색 배경 Canvas GUI 애플리케이션이다.
- 채널 수: 4 (Tip, Shield, Bypass, Pumping)
- 기능:
  - 채널별 On/Off 토글 버튼
  - 유량 설정값(0 ~ `pc_input_max`) 키보드 입력 후 Enter 적용
  - 채널 번호(1~4) 할당
  - RESET: 모든 채널을 초기 상태로 복귀
  - Mini 모드: 창 높이를 130 px로 축소
  - 스케줄러: 요일/시각 기반 자동 On·Off·Setpoint 설정
- HTTP 서버(`localhost:<localserver_port>/get_value`)를 별도 스레드로 실행하여 최신 유량값을 JSON으로 노출한다.
- config·기능 로그는 exe/스크립트 옆 (`common/paths.writable_path`). 기동·HTTP·스케줄 이상은 `flog_flowtemp/`에 기록한다.

**응답 JSON 스키마**

```json
{
  "Tip":     1.23,
  "Shield":  0.45,
  "Bypass":  0.67,
  "Pumping": 0.89,
  "timestamp": 1700000000.0
}
```

**설정 파일: `rfm_config.json`**

```json
{
  "arduino_port":    "COM3",
  "localserver_port": 5000,
  "pc_input_max":    99,
  "arduino_read_max": 4095
}
```

**Serial 프로토콜 (`RFMserial.py`)**

- 수신 포맷: `aaaabbbbccccdddd\n` (각 채널 4자리 정수, 16자 고정)
- 유량값 변환: `bit × pc_input_max / arduino_read_max / 10` (L/min)
- 송신 명령 (단일 ASCII 문자):

| 동작 | CH1 | CH2 | CH3 | CH4 |
|---|---|---|---|---|
| ON | `z` | `x` | `c` | `v` |
| OFF | `a` | `s` | `d` | `f` |
| Setpoint | `q` | `w` | `e` | `r` |
| RESET | `B` | — | — | — |

---

### 3-2. `DRC91Cdaemon.py` — DRC91C 온도 컨트롤러 데몬

- GPIB(`pyvisa`)로 DRC91C에 접속하여 센서 A/B 온도값을 읽는다.
- Flask HTTP 서버(`0.0.0.0:<port>/sensor_pair`)로 두 채널 온도를 JSON 노출한다.
- 값 포맷: `+XXX.XXK` (8자 문자열), 플로터가 `float(value[1:7])`로 파싱(단위: K).
- 장비 open 실패·서버 기동 등은 `flog_flowtemp/`에 기록한다.

**설정 파일: `drc91c_config.json`**

```json
{
  "device_address": "GPIB1::15::INSTR",
  "port": 5001
}
```

---

### 3-3. `Lakeshore330.py` — Lakeshore 330 온도계 데몬 (대체 옵션)

- DRC91C 대신 Lakeshore 330을 사용할 때 이 모듈로 교체한다.
- GPIB `SDAT?` (Head), `CDAT?` (Cold Tip) 명령으로 온도를 읽는다.
- 값 포맷: `XX.XXX K` (오버로드 시 `OL` → `00.000` 대체)
- 동일한 `/sensor_pair` 엔드포인트로 노출하므로 `FlowTempPlotter`와 인터페이스가 동일하다.
- 장비 open 실패·서버 기동 등은 `flog_flowtemp/`에 기록한다.

**설정 파일: `lakeshore330_config.json`**

```json
{
  "device_address": "GPIB1::30::INSTR",
  "port": 5001
}
```

---

### 3-4. `FlowTempPlotter.py` — GUI 플로터

- Tkinter 윈도우 + matplotlib TkAgg 백엔드를 사용한다.
- 별도 스레드(`fetch_loop`)가 1초마다 두 HTTP 서버를 폴링하여 `VariousTimeDeque`에 저장한다.
- GUI 메인 루프는 200 ms 주기로 `update_display`를 호출한다.
- 포트 설정은 `flowtempplotter_config.json`에서 관리한다 (exe/스크립트 옆).
- **시작 시 로그 복원**: `log_flowtemp/`의 1분 주기 로그를 읽어 RFM·DRC91C deque를 각 인터벌의 `N × T` 윈도우만큼 채운다.
- 운영 이벤트는 `common/FuncLogger`로 `flog_flowtemp/YYYY/MM/DD.txt`에 기록한다.
- Pressure와 달리 캘리브레이션 창·Local Max/Min·메일 실패 GUI 팝업은 없다 (의도적).

**표시 채널**

| 레이블 | 데이터 | 축 | 색상 |
|---|---|---|---|
| Tip | RFM Tip 유량 | 왼쪽 y (L/min) | green |
| Shield | RFM Shield 유량 | 왼쪽 y (L/min) | blue |
| Bypass | RFM Bypass 유량 | 왼쪽 y (L/min) | purple |
| Pumping | RFM Pumping 유량 | 왼쪽 y (L/min) | skyblue |
| Head | DRC91C/LS330 Head 온도 | 오른쪽 y (K) | red |
| Cold Tip | DRC91C/LS330 Cold Tip 온도 | 오른쪽 y (K) | orange |

**그래프 인터벌 선택**

`VariousTimeDeque`가 네 가지 해상도의 링 버퍼(각 100개)를 관리한다.

| 선택 | 버퍼 | x축 포맷 |
|---|---|---|
| 1 s | 초별 데이터 | `HH:MM:SS` |
| 1 min | 분별 데이터 | `HH:MM` |
| 10 min | 10분별 데이터 | `MM-DD HH:MM` |
| 1 hour | 시간별 데이터 | `MM-DD HH` |

**`flowtempplotter_config.json`**

```json
{
  "rfm_localserver_port": 5000,
  "drc91c_localserver_port": 5001
}
```

---

## 4. 스케줄러 (`RFMdaemon`)

- 주간 단위 스케줄을 등록하여 MFC 채널을 자동으로 On·Off·Setpoint로 제어한다.
- 판정 조건: 요일 + 시·분이 일치하고, 직전 실행 분과 다른 분일 때 1회 실행된다(중복 실행 방지).
- 스케줄 항목 구성: 요일, 시각(HH:MM), 채널명(Tip/Shield/Bypass/Pumping), 동작(On/Off/Setpoint), 설정값(Setpoint 시에만)

---

## 5. 이상 감지 및 알림

이메일 알림은 `CustomMail.send_mail()`을 통해 SMTP SSL로 발송된다. 설정은 `mail_config.json`에서 관리한다.

| 조건 | 체크 주기 | 알림 내용 |
|---|---|---|
| RFM HTTP 연결 끊김 (`Off`/`Connecting` 제외) | 10분 | "MKS247C is disconnected" |
| DRC91C HTTP 연결 끊김 (`Off`/`Connecting` 제외) | 10분 | "Temperature controller is disconnected" |

- 발송 결과(성공/실패·stage)는 `maillog_flowtemp.txt`에 기록된다.
- 메일 실패 시 GUI 팝업은 표시하지 않는다 (기능 로그·메일 로그만).

---

## 6. 로그 저장

### 데이터 로그

- 저장 주기: 1분마다 (`VariousTimeDeque`의 1분 버퍼 갱신 시점)
- 저장 경로: `log_flowtemp/YYYY/MM/DD.txt` (exe/스크립트 옆)
- 저장 형식:

```
2024-11-01 14:30:00: 1.23, 0.45, 0.67, 0.89, 12.34, 4.56
```

필드 순서: `Tip`, `Shield`, `Bypass`, `Pumping` (L/min), `Head`, `Cold Tip` (K)

### 기능 로그

- 경로: `flog_flowtemp/YYYY/MM/DD.txt`
- 소스 태그: `FlowTempPlotter`, `RFMdaemon`, `DRC91Cdaemon`, `Lakeshore330`
- 레벨: `INFO` / `CAUTION` / `ERROR` / `CRITICAL`

---

## 7. 빌드 및 배포

- PyInstaller로 단일 exe 빌드를 지원한다 (`FlowTempPlotter/makefile.bat`, `RFM/makefile.bat`, `DRC91C/makefile.bat`, `Lakeshore330/makefile.bat`).
- GUI Plotter는 `--noconsole`, 콘솔 데몬(DRC91C/Lakeshore)은 콘솔을 유지한다.
- `common/paths.bundle_path()` / `writable_path()`로 아이콘·config·로그 경로를 통일한다.
- `RFMserial.py`는 실제 시리얼(`RFMserial_Real`) / 시뮬레이션(`RFMserial_Sim`) 두 구현체를 `RFMserial` 래퍼로 전환한다. `SERIAL_ON = False`로 설정하면 시뮬 모드로 동작한다.

---

## 8. 파일 목록

```
Flow_and_Temp/
├── FlowTempPlotter/
│   ├── FlowTempPlotter.py       # GUI 메인 (+ 로그 복원)
│   ├── VariousTimeDeque.py      # 멀티 인터벌 링 버퍼 (+ load_historical)
│   ├── CustomDateLocator.py     # x축 눈금 위치 계산
│   ├── CustomMail.py            # SMTP 이메일 발송 + maillog_flowtemp.txt
│   └── makefile.bat
├── RFM/
│   ├── RFMdaemon.py             # MFC 제어 GUI + HTTP 서버
│   ├── RFMserial.py             # Arduino 시리얼 통신
│   ├── channel.py               # 채널 Enum 정의
│   ├── schedularwindow.py       # 스케줄러 GUI
│   ├── makefile.bat
│   └── RFM_arduino/             # Arduino 펌웨어 (MKS247C 제어)
├── DRC91C/
│   ├── DRC91Cdaemon.py          # GPIB → Flask HTTP:5001
│   └── makefile.bat
└── Lakeshore330/
    ├── Lakeshore330.py          # GPIB → HTTP:5001 (DRC91C 대체)
    └── makefile.bat
```

공통 모듈: `../../common/paths.py`, `../../common/FuncLogger.py`
