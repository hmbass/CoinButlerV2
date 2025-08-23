#!/bin/bash

# CoinButler V2 시작 스크립트
# 백그라운드 실행 기본 지원

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 로그 함수
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# 변수 설정
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PID_FILE="$SCRIPT_DIR/coinbutler.pid"
LOG_DIR="$SCRIPT_DIR/logs"
LOG_FILE="$LOG_DIR/coinbutler.log"
ERROR_LOG="$LOG_DIR/coinbutler_error.log"

# 도움말 출력
show_help() {
    echo "CoinButler V2 시작 스크립트"
    echo ""
    echo "사용법: $0 [옵션]"
    echo ""
    echo "옵션:"
    echo "  -b, --background    백그라운드에서 실행 (기본값)"
    echo "  -f, --foreground    전경에서 실행"
    echo "  -d, --dashboard     대시보드만 실행"
    echo "  --bot-only          봇만 실행"
    echo "  -s, --status        실행 상태 확인"
    echo "  -h, --help          도움말 표시"
    echo ""
    echo "예시:"
    echo "  $0                  # 백그라운드에서 전체 시스템 실행"
    echo "  $0 -f               # 전경에서 전체 시스템 실행"
    echo "  $0 -d               # 대시보드만 백그라운드 실행"
    echo "  $0 -s               # 현재 상태 확인"
}

# 상태 확인 함수
check_status() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            log_info "✅ CoinButler가 실행 중입니다 (PID: $PID)"
            
            # 포트 확인
            if command -v lsof >/dev/null 2>&1; then
                if lsof -i :8501 >/dev/null 2>&1; then
                    log_info "📊 대시보드 포트(8501): 활성"
                else
                    log_warn "📊 대시보드 포트(8501): 비활성"
                fi
            fi
            
            # 로그 파일 확인
            if [ -f "$LOG_FILE" ]; then
                RECENT_ACTIVITY=$(tail -1 "$LOG_FILE" 2>/dev/null || echo "로그 없음")
                log_info "📝 최근 활동: $RECENT_ACTIVITY"
            fi
            
            return 0
        else
            log_warn "⚠️  PID 파일이 있지만 프로세스가 실행 중이 아닙니다."
            rm -f "$PID_FILE"
            return 1
        fi
    else
        log_info "❌ CoinButler가 실행 중이 아닙니다."
        return 1
    fi
}

# 실행 중인지 확인
is_running() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            return 0
        else
            rm -f "$PID_FILE"
            return 1
        fi
    fi
    return 1
}

# 초기 설정
setup_environment() {
    log_step "환경 설정 중..."
    
    # Python 버전 체크
    if ! command -v python3 &> /dev/null; then
        log_error "Python3가 설치되지 않았습니다."
        exit 1
    fi
    
    # 로그 디렉토리 생성
    mkdir -p "$LOG_DIR"
    
    # 가상환경 확인 및 생성
    if [ ! -d "venv" ]; then
        log_step "Python 가상환경 생성 중..."
        python3 -m venv venv
    fi
    
    # 가상환경 활성화
    source venv/bin/activate
    
    # 의존성 패키지 설치 (조용히)
    log_step "필요한 패키지 확인 중..."
    pip install -q -r requirements.txt
    
    # .env 파일 확인
    if [ ! -f ".env" ]; then
        if [ -f "env_example.txt" ]; then
            log_warn ".env 파일이 없습니다. 템플릿을 복사합니다."
            cp env_example.txt .env
            log_error "API 키를 설정해주세요: nano .env"
            exit 1
        else
            log_error "env_example.txt 파일을 찾을 수 없습니다."
            exit 1
        fi
    fi
    
    log_info "환경 설정 완료"
}

# 백그라운드 실행
start_background() {
    local mode=${1:-"full"}
    
    if is_running; then
        log_warn "CoinButler가 이미 실행 중입니다."
        check_status
        return 0
    fi
    
    setup_environment
    
    log_step "백그라운드에서 CoinButler 시작 중..."
    
    # 가상환경 활성화
    source venv/bin/activate
    
    # 백그라운드에서 실행
    case $mode in
        "dashboard")
            nohup python3 main.py dashboard > "$LOG_FILE" 2> "$ERROR_LOG" &
            ;;
        "bot")
            nohup python3 main.py bot > "$LOG_FILE" 2> "$ERROR_LOG" &
            ;;
        *)
            nohup python3 main.py > "$LOG_FILE" 2> "$ERROR_LOG" &
            ;;
    esac
    
    local PID=$!
    echo $PID > "$PID_FILE"
    
    # 시작 확인 (3초 대기)
    sleep 3
    
    if ps -p "$PID" > /dev/null 2>&1; then
        log_info "✅ CoinButler가 성공적으로 시작되었습니다!"
        log_info "📄 PID: $PID"
        
        if [ "$mode" = "full" ] || [ "$mode" = "dashboard" ]; then
            # 외부 IP 가져오기 (시도)
            EXTERNAL_IP=$(curl -s -m 5 ifconfig.me 2>/dev/null || echo "localhost")
            log_info "📊 대시보드: http://$EXTERNAL_IP:8501"
        fi
        
        log_info "📝 로그: tail -f $LOG_FILE"
        log_info "🛑 중지: ./stop.sh"
        log_info "📊 상태: ./status.sh"
        
        return 0
    else
        log_error "CoinButler 시작에 실패했습니다."
        rm -f "$PID_FILE"
        
        if [ -f "$ERROR_LOG" ]; then
            log_error "오류 로그:"
            tail -10 "$ERROR_LOG"
        fi
        
        return 1
    fi
}

# 전경 실행
start_foreground() {
    local mode=${1:-"full"}
    
    if is_running; then
        log_warn "CoinButler가 이미 실행 중입니다."
        log_info "중지한 후 다시 실행하려면: ./stop.sh"
        return 1
    fi
    
    setup_environment
    
    log_step "전경에서 CoinButler 시작 중..."
    log_info "🛑 중지하려면 Ctrl+C를 누르세요"
    echo ""
    
    # 가상환경 활성화
    source venv/bin/activate
    
    # 전경에서 실행
    case $mode in
        "dashboard")
            python3 main.py dashboard
            ;;
        "bot")
            python3 main.py bot
            ;;
        *)
            python3 main.py
            ;;
    esac
}

# 메인 로직
main() {
    echo "🤖 CoinButler V2 자동매매 시스템"
    echo "================================"
    
    # 파라미터 파싱
    BACKGROUND=true
    MODE="full"
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            -b|--background)
                BACKGROUND=true
                shift
                ;;
            -f|--foreground)
                BACKGROUND=false
                shift
                ;;
            -d|--dashboard)
                MODE="dashboard"
                shift
                ;;
            --bot-only)
                MODE="bot"
                shift
                ;;
            -s|--status)
                check_status
                exit $?
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                log_error "알 수 없는 옵션: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    # 실행
    if [ "$BACKGROUND" = true ]; then
        start_background "$MODE"
    else
        start_foreground "$MODE"
    fi
}

# 스크립트 실행
main "$@"