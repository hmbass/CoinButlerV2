# 🤖 CoinButler V2

업비트 API 기반 코인 자동매매 시스템

## 📋 목차

- [개요](#-개요)
- [주요 기능](#-주요-기능)
- [시스템 요구사항](#-시스템-요구사항)
- [설치 및 설정](#-설치-및-설정)
- [사용법](#-사용법)
- [설정 옵션](#-설정-옵션)
- [웹 대시보드](#-웹-대시보드)
- [파일 구조](#-파일-구조)
- [주의사항](#-주의사항)
- [문제해결](#-문제해결)

## 🎯 개요

CoinButler V2는 업비트 거래소에서 코인 자동매매를 수행하는 Python 기반 시스템입니다.  
거래량 급등을 감지하여 자동 매수하고, 설정된 손익률에 따라 자동 매도하는 기능을 제공합니다.

### 주요 특징

- ⚡ 실시간 거래량 급등 감지 및 자동 매수
- 🎯 목표 수익률/손절률 기반 자동 매도  
- 🤖 **Google Gemini AI** 연동으로 AI 기반 종목 선택 (무료!)
- 📊 실시간 웹 대시보드 제공
- 💬 스마트한 텔레그램 알림 (매수/매도 시에만)
- 🛡️ 리스크 관리 (일일 손실 한도, 최대 포지션 수 제한)
- 📈 거래 내역 및 수익률 분석
- 🚀 **백그라운드 실행 지원** (원클릭 시작/중지)

## ✨ 주요 기능

### 🔄 자동매매 기능
- **거래량 급등 감지**: 5분봉 기준 거래량이 설정 배수 이상 증가 시 매수 신호
- **자동 매수**: 거래량 급등 + AI 추천 조건 만족 시 자동 매수
- **자동 매도**: 목표 수익률 달성 시 익절, 손절률 도달 시 손절
- **포지션 관리**: 최대 보유 포지션 수 제한으로 리스크 분산

### 🤖 AI 기반 종목 선택
- **Google Gemini AI**: 무료 API를 통한 종목 분석 및 추천 (월 1,500회 무료)
- **기술적 분석**: 거래량, 가격 변동성, 시장 트렌드 종합 분석
- **신뢰도 기반 선택**: AI 추천 신뢰도가 설정값 이상일 때만 매수
- **비용 효율적**: OpenAI 대비 100% 무료로 AI 분석 가능

### 🛡️ 리스크 관리
- **일일 손실 한도**: 설정된 금액 이상 손실 시 자동 거래 중단
- **최대 포지션 수**: 동시 보유 가능한 코인 수 제한 (기본값: 3개, 대시보드에서 조정 가능)
- **손절/익절**: 개별 포지션별 손익률 모니터링 및 자동 처리
- **🆕 동적 설정 관리**: 대시보드에서 실시간으로 매수 최소 잔고 및 거래 설정 조정

### 📊 모니터링 & 알림
- **실시간 대시보드**: Streamlit 기반 웹 인터페이스
  - 📊 대시보드: 실시간 계정 현황 및 시장 정보
  - 💼 보유 종목: 현재 포지션 상세 정보 (수익률, 목표가, 손절가)
  - 📈 거래 내역: 모든 매수/매도 기록 및 통계
  - 🤖 AI 성과: AI 추천 성과 분석 및 백테스팅 결과
  - ⚙️ 설정: 실시간 봇 설정 변경 (매수 최소 잔고, 최대 포지션 수 등)
  - 🔄 실제 잔고: 실제 업비트 계좌와 동기화 상태 확인 및 수동 거래 감지
- **스마트 텔레그램 알림**: 중요한 매수/매도 시에만 알림 (스팸 방지)
- **백그라운드 실행**: PID 기반 안전한 백그라운드 프로세스 관리
- **거래 기록**: CSV 형태로 모든 거래 내역 저장
- **수익률 분석**: 일별/주별 수익률 및 승률 통계

## 💻 시스템 요구사항

### 운영체제
- Ubuntu 18.04+ (권장)
- Linux 기반 시스템
- macOS (개발/테스트용)

### Python 환경
- Python 3.8+
- pip 패키지 관리자

### 필수 계정
- 업비트 API 키 (KRW 거래 권한 필요)
- Google Gemini API 키 (무료, 선택사항 - AI 분석용)
- 텔레그램 봇 토큰 (알림용, 선택사항)

## 🚀 설치 및 설정

### 1. 프로젝트 클론 및 이동

```bash
cd /path/to/your/directory
# 프로젝트 파일들이 이미 존재한다고 가정
```

### 2. 실행 권한 부여

```bash
chmod +x start.sh stop.sh status.sh
```

### 3. 환경 변수 설정

```bash
cp env_example.txt .env
nano .env
```

`.env` 파일 설정 예시:

```env
# 업비트 API 키
UPBIT_ACCESS_KEY=your_upbit_access_key_here
UPBIT_SECRET_KEY=your_upbit_secret_key_here

# Google Gemini API 키 (선택사항 - AI 분석용)
GEMINI_API_KEY=your_gemini_api_key_here

# 텔레그램 봇 (선택사항)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
TELEGRAM_CHAT_ID=your_telegram_chat_id_here

# 거래 설정
INVESTMENT_AMOUNT=100000          # 매수 시 투자 금액 (원)
PROFIT_RATE=0.03                 # 목표 수익률 (3%)
LOSS_RATE=-0.02                  # 손절 수익률 (-2%)
DAILY_LOSS_LIMIT=-50000          # 하루 손실 한도 (-5만원)

# 거래량 급등 설정
VOLUME_SPIKE_THRESHOLD=2.0       # 거래량 급등 기준 (2배)
PRICE_CHANGE_THRESHOLD=0.05      # 가격 변동 임계값 (5%)

# 시스템 설정
MAX_POSITIONS=3                  # 최대 보유 포지션 수
CHECK_INTERVAL=60                # 체크 주기 (초)
MARKET_SCAN_INTERVAL=600         # 시장 스캔 주기 (초, 10분)
MAX_SCAN_MARKETS=20              # 최대 스캔할 종목 수

# API Rate Limiting
UPBIT_CALLS_PER_SECOND=8         # 업비트 API 초당 호출 제한

# 대시보드 설정
DASHBOARD_HOST=0.0.0.0
DASHBOARD_PORT=8501
```

### 4. 업비트 API 키 발급

1. [업비트 프로페셔널](https://upbit.com/service_center/open_api_guide) 접속
2. Open API 신청 및 승인 대기
3. API 키 발급 (특정 IP 허용, 원화 거래 권한 필요)

### 5. Google Gemini API 키 발급 (선택사항)

1. [Google AI Studio](https://aistudio.google.com) 접속
2. Google 계정으로 로그인
3. "Get API Key" 클릭하여 **무료 API 키** 발급
4. 월 1,500회 무료 할당량 제공 (비용 없음)

### 6. 텔레그램 봇 설정 (선택사항)

1. @BotFather에서 새 봇 생성
2. 봇 토큰 획득
3. 봇과 대화하여 Chat ID 획득

```bash
# Chat ID 확인 방법
curl "https://api.telegram.org/bot[YOUR_BOT_TOKEN]/getUpdates"
```

#### 🧪 텔레그램 알림 테스트
```bash
# 텔레그램 설정 및 연결 테스트
python test_telegram.py
```

**알림이 오지 않는 경우 확인사항:**
- ✅ `.env` 파일에 `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` 설정 완료
- ✅ 봇이 해당 채팅방에 추가되어 있음
- ✅ 봇과 최소 한 번 대화를 시작함
- ✅ `test_telegram.py`로 연결 테스트 성공

## 📖 사용법

### 🚀 기본 실행 (백그라운드)

```bash
# 전체 시스템 백그라운드 실행 (기본값)
./start.sh

# 전경에서 실행 (디버깅용)
./start.sh -f

# 봇만 실행
./start.sh --bot-only

# 대시보드만 실행
./start.sh -d

# 도움말 확인
./start.sh -h
```

### 📊 상태 확인 및 모니터링

```bash
# 상세 시스템 상태 확인
./status.sh

# 실시간 로그 확인
tail -f logs/coinbutler.log

# 에러 로그 확인
tail -f logs/coinbutler_error.log

# 빠른 상태 확인
./start.sh -s
```

### ⏹️ 시스템 중지

```bash
# 안전한 시스템 중지
./stop.sh
```

### Python 직접 실행

```bash
# 가상환경 활성화 후
source venv/bin/activate

# 전체 시스템
python main.py

# 봇만 실행
python main.py bot

# 대시보드만 실행
python main.py dashboard

# 상태 확인
python main.py status
```

## ⚙️ 설정 옵션

### 거래 설정

| 설정 | 설명 | 기본값 | 권장값 |
|-----|------|--------|--------|
| `INVESTMENT_AMOUNT` | 매수 시 투자 금액 (원) | 100,000 | 50,000~200,000 |
| `PROFIT_RATE` | 목표 수익률 | 0.03 (3%) | 0.02~0.05 |
| `LOSS_RATE` | 손절 수익률 | -0.02 (-2%) | -0.01~-0.03 |
| `DAILY_LOSS_LIMIT` | 하루 손실 한도 (원) | -50,000 | -30,000~-100,000 |

### 매매 조건

| 설정 | 설명 | 기본값 | 권장값 |
|-----|------|--------|--------|
| `VOLUME_SPIKE_THRESHOLD` | 거래량 급등 기준 (배수) | 2.0 | 1.5~3.0 |
| `PRICE_CHANGE_THRESHOLD` | 가격 변동 임계값 | 0.05 (5%) | 0.03~0.07 |
| `MAX_POSITIONS` | 최대 보유 포지션 수 | 3 | 2~5 |
| `CHECK_INTERVAL` | 체크 주기 (초) | 60 | 30~120 |

### API 및 성능 설정

| 설정 | 설명 | 기본값 | 권장값 |
|-----|------|--------|--------|
| `MARKET_SCAN_INTERVAL` | 시장 스캔 주기 (초) | 600 | 300~1200 |
| `MAX_SCAN_MARKETS` | 스캔할 최대 종목 수 | 20 | 10~30 |
| `UPBIT_CALLS_PER_SECOND` | 업비트 API 초당 호출 제한 | 8 | 5~9 |

## 🌐 웹 대시보드

### 접속 방법
- URL: `http://localhost:8501` (로컬 실행 시)
- URL: `http://서버IP:8501` (서버 실행 시)

### 주요 기능

#### 📊 실시간 현황
- 현재 KRW 잔고
- 일일 손익 현황
- 보유 포지션 수
- 거래 승률

#### 💼 포지션 관리
- 현재 보유 중인 모든 포지션 조회
- 실시간 손익 계산
- 포지션별 상세 정보

#### 📈 거래 내역
- 모든 매수/매도 기록
- 날짜별 필터링
- 거래 통계 및 분석

#### 🎛️ 봇 제어
- 봇 시작/중지/일시정지
- 실시간 상태 모니터링
- 설정 값 확인

## 📁 파일 구조

```
CoinButlerV2/
├── main.py                    # 메인 실행 파일
├── trade_bot.py              # 자동매매 봇 로직 (Gemini AI 적용)
├── trade_utils.py            # 업비트 API 유틸리티 (레이트 리미터 적용)
├── risk_manager.py           # 리스크 관리 모듈
├── notifier.py               # 스마트 텔레그램 알림 모듈
├── dashboard.py              # Streamlit 대시보드
├── requirements.txt          # Python 패키지 의존성 (google-generativeai 포함)
├── env_example.txt           # 환경변수 템플릿 (Gemini API 키 포함)
├── .env                      # 환경변수 설정 (생성 필요)
├── start.sh                  # 🚀 향상된 시작 스크립트 (백그라운드 기본)
├── stop.sh                   # 🛑 향상된 중지 스크립트
├── status.sh                 # 📊 상세 상태 확인 스크립트
├── server_install.sh         # 서버 설치 스크립트
├── deploy.sh                 # 배포 스크립트
├── README.md                 # 프로젝트 문서
├── coinbutler.pid            # PID 파일 (백그라운드 실행 시)
├── trade_history.csv         # 거래 기록 (자동 생성)
├── daily_pnl.json           # 일일 손익 기록 (자동 생성)
└── logs/                    # 📂 로그 디렉토리 (자동 생성)
    ├── coinbutler.log       # 메인 애플리케이션 로그
    └── coinbutler_error.log # 에러 전용 로그
```

## ⚠️ 주의사항

### 투자 위험성
- **가상화폐 투자는 고위험 투자입니다**
- **원금 손실 위험이 매우 높습니다**
- **충분히 이해한 후 소액으로 시작하세요**
- **투자 결과에 대한 책임은 사용자에게 있습니다**

### 기술적 주의사항
- API 키 보안에 각별히 주의하세요
- 서버 안정성 및 네트워크 상태를 점검하세요
- 정기적으로 시스템 상태를 모니터링하세요
- 로그를 정기적으로 확인하여 오류를 점검하세요

### 법적 주의사항
- 각국의 가상화폐 관련 법규를 준수하세요
- 세금 신고 의무를 확인하세요
- 자동매매 관련 규제를 확인하세요

## 🔧 문제해결

### 일반적인 문제

#### 1. API 키 오류
```
❌ 업비트 API 키가 설정되지 않았습니다.
```
**해결방법**: `.env` 파일에서 `UPBIT_ACCESS_KEY`, `UPBIT_SECRET_KEY` 확인

#### 2. 패키지 설치 오류
```
❌ No module named 'pyupbit'
```
**해결방법**: 가상환경 활성화 후 패키지 재설치
```bash
source venv/bin/activate
pip install -r requirements.txt
```

#### 3. 포트 충돌
```
❌ Port 8501 is already in use
```
**해결방법**: 포트 변경 또는 기존 프로세스 종료
```bash
# 포트 사용 프로세스 확인
lsof -i :8501

# .env에서 포트 변경
DASHBOARD_PORT=8502
```

#### 4. 봇이 매수하지 않음
**확인사항**:
- KRW 잔고 충분한지 확인
- 거래량 급등 기준이 적절한지 확인
- 최대 포지션 수 도달했는지 확인
- 일일 손실 한도 초과했는지 확인

#### 5. API 호출 제한 오류 (429 Error)
```
❌ 429 Client Error: Too Many Requests
```
**해결방법**:
- API 호출 주기가 자동으로 조절됨 (재시도 로직 적용)
- `MAX_SCAN_MARKETS` 값을 줄여서 스캔하는 종목 수 감소
- `MARKET_SCAN_INTERVAL` 값을 늘려서 스캔 주기 증가

#### 6. Google Gemini API 오류
```
❌ Gemini AI 초기화 실패
```
**해결방법**:
- [Google AI Studio](https://aistudio.google.com)에서 API 키 재발급
- `.env` 파일에서 `GEMINI_API_KEY` 확인
- API 키를 주석 처리하면 AI 분석 자동 비활성화
- AI 없이도 거래량 급등 기반 매매는 정상 작동

#### 7. 백그라운드 실행 문제
```
❌ 백그라운드에서 시작했지만 프로세스를 찾을 수 없음
```
**해결방법**:
```bash
# 상태 확인
./status.sh

# PID 파일 정리 후 재시작
rm -f coinbutler.pid
./start.sh

# 전경에서 실행하여 오류 확인
./start.sh -f
```

#### 8. 텔레그램 알림 오류
```
❌ 텔레그램 메시지 전송 실패
❌ 텔레그램 알림이 설정되지 않음
```
**해결방법**: 
```bash
# 1. 텔레그램 설정 테스트
python test_telegram.py

# 2. 환경변수 확인
echo "BOT_TOKEN: $TELEGRAM_BOT_TOKEN"
echo "CHAT_ID: $TELEGRAM_CHAT_ID"
```

**체크리스트**:
- ✅ `.env` 파일에 `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` 설정됨
- ✅ 봇이 해당 채팅방에 추가되어 있음  
- ✅ 봇과 최소 한 번은 대화를 시작함
- ✅ Chat ID가 정수형으로 올바르게 설정됨 (따옴표 없이)
- ✅ 인터넷 연결이 정상적임

### 📝 로그 확인

```bash
# 실시간 로그 모니터링
tail -f logs/coinbutler.log

# 에러 로그 확인
tail -f logs/coinbutler_error.log

# 특정 오류 검색
grep -i "error\|exception\|failed" logs/coinbutler.log

# 최근 거래 내역 확인
tail -10 trade_history.csv

# 상세 시스템 상태 확인
./status.sh
```

### 🔄 재시작 방법

```bash
# 안전한 재시작
./stop.sh
sleep 3
./start.sh

# 강제 재시작 (문제 발생 시)
./stop.sh
rm -f coinbutler.pid
./start.sh

# 디버깅용 전경 실행
./start.sh -f
```

## 📞 지원

### 로그 분석
시스템에 문제가 발생하면 다음 로그를 확인하세요:

1. `logs/coinbutler.log` - 메인 애플리케이션 로그
2. `logs/coinbutler_error.log` - 에러 전용 로그
3. `trade_history.csv` - 거래 내역
4. `daily_pnl.json` - 일일 손익 기록
5. `coinbutler.pid` - 현재 프로세스 ID

### 시스템 모니터링
정기적으로 다음을 확인하세요:

- `./status.sh`로 상세 시스템 상태 점검
- 대시보드(`http://localhost:8501`)에서 실시간 현황 모니터링  
- 일일 손익 및 누적 수익률 추적
- 백그라운드 프로세스 상태 모니터링

---

## 🎉 최신 업데이트 (V2.1)

### ✨ 새로운 기능들
- 🆓 **Google Gemini AI**: OpenAI 대신 무료 AI 분석 (월 1,500회)
- 📱 **스마트 알림**: 매수/매도 시에만 텔레그램 알림  
- 🚀 **백그라운드 실행**: 원클릭으로 백그라운드 시작/중지
- 🔧 **향상된 모니터링**: 상세한 시스템 상태 확인
- ⚡ **API 최적화**: 레이트 리미터로 429 오류 방지
- ⚙️ **동적 설정 관리**: 대시보드에서 실시간 거래 설정 변경
- 🔄 **실제 잔고 동기화**: 업비트 앱 수동 거래 자동 감지 및 동기화

### 💰 비용 절약
- **AI 분석 비용**: $5-20/월 → **무료**
- **알림 스팸**: 하루 50+ 알림 → **중요한 2-3개만**
- **서버 리소스**: 더 효율적인 API 사용

---

⚡ **CoinButler V2.1로 더욱 스마트한 코인 자동매매를 시작해보세요!**

*※ 투자에 따른 손실 위험을 충분히 이해하고 사용하시기 바랍니다.*
