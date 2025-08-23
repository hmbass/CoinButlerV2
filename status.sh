#!/bin/bash

# CoinButler V2 상태 확인 스크립트

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
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

log_status() {
    echo -e "${BLUE}[STATUS]${NC} $1"
}

log_data() {
    echo -e "${CYAN}$1${NC}"
}

# 변수 설정
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PID_FILE="$SCRIPT_DIR/coinbutler.pid"
LOG_DIR="$SCRIPT_DIR/logs"
LOG_FILE="$LOG_DIR/coinbutler.log"
ERROR_LOG="$LOG_DIR/coinbutler_error.log"

echo "🔍 CoinButler V2 시스템 상태 확인"
echo "=================================="
echo "📅 확인 시간: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# 메인 프로세스 상태 확인
log_status "메인 프로세스 상태"
echo "-------------------"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    echo "📄 PID 파일: 존재 (PID: $PID)"
    
    if ps -p "$PID" > /dev/null 2>&1; then
        log_info "✅ CoinButler 실행 중"
        
        # 프로세스 세부 정보
        PROCESS_INFO=$(ps -p "$PID" -o pid,ppid,pcpu,pmem,etime,cmd --no-headers 2>/dev/null || echo "정보 없음")
        echo "   📊 세부 정보: $PROCESS_INFO"
        
        # CPU, 메모리 사용률 추출
        if [ "$PROCESS_INFO" != "정보 없음" ]; then
            CPU_USAGE=$(echo "$PROCESS_INFO" | awk '{print $3}')
            MEM_USAGE=$(echo "$PROCESS_INFO" | awk '{print $4}')
            RUNTIME=$(echo "$PROCESS_INFO" | awk '{print $5}')
            
            log_data "   💻 CPU 사용률: ${CPU_USAGE}%"
            log_data "   🧠 메모리 사용률: ${MEM_USAGE}%"
            log_data "   ⏰ 실행 시간: ${RUNTIME}"
        fi
        
    else
        log_error "❌ 메인 프로세스 중지됨 (PID 파일 존재하지만 프로세스 없음)"
        echo "   ⚠️  PID 파일을 정리하시겠습니까? (y/N)"
        read -r response
        if [[ "$response" =~ ^[Yy]$ ]]; then
            rm -f "$PID_FILE"
            log_info "🧹 PID 파일이 삭제되었습니다."
        fi
    fi
else
    log_error "❌ PID 파일 없음"
    echo "   ℹ️  백그라운드로 실행되지 않았거나 정상 종료됨"
fi

echo ""

# 관련 프로세스 검색
log_status "관련 프로세스 검색"
echo "-------------------"

MAIN_PROCESSES=$(pgrep -f "python.*main.py" 2>/dev/null || true)
STREAMLIT_PROCESSES=$(pgrep -f "streamlit.*dashboard" 2>/dev/null || true)

if [ ! -z "$MAIN_PROCESSES" ]; then
    log_info "✅ Python 메인 프로세스 발견:"
    ps -p $MAIN_PROCESSES -o pid,ppid,pcpu,pmem,etime,cmd --no-headers | \
    while read line; do
        echo "   📊 $line"
    done
else
    log_error "❌ Python 메인 프로세스 없음"
fi

if [ ! -z "$STREAMLIT_PROCESSES" ]; then
    log_info "✅ Streamlit 대시보드 프로세스 발견:"
    ps -p $STREAMLIT_PROCESSES -o pid,ppid,pcpu,pmem,etime,cmd --no-headers | \
    while read line; do
        echo "   📊 $line"
    done
else
    log_warn "❌ Streamlit 대시보드 프로세스 없음"
fi

echo ""

# 네트워크 포트 상태
log_status "네트워크 포트 상태"
echo "-------------------"

DASHBOARD_PORT=8501
if command -v lsof >/dev/null 2>&1; then
    PORT_INFO=$(lsof -i :$DASHBOARD_PORT 2>/dev/null || true)
    if [ ! -z "$PORT_INFO" ]; then
        log_info "✅ 포트 $DASHBOARD_PORT 사용 중"
        echo "$PORT_INFO" | head -5
        
        # 외부 접근 URL
        EXTERNAL_IP=$(curl -s -m 3 ifconfig.me 2>/dev/null || echo "localhost")
        log_data "🌐 대시보드 URL: http://$EXTERNAL_IP:$DASHBOARD_PORT"
    else
        log_error "❌ 포트 $DASHBOARD_PORT 사용 중이 아님"
    fi
elif command -v netstat >/dev/null 2>&1; then
    PORT_INFO=$(netstat -tuln | grep ":$DASHBOARD_PORT " || true)
    if [ ! -z "$PORT_INFO" ]; then
        log_info "✅ 포트 $DASHBOARD_PORT 사용 중"
        echo "   $PORT_INFO"
    else
        log_error "❌ 포트 $DASHBOARD_PORT 사용 중이 아님"
    fi
else
    log_warn "❓ 포트 확인 도구 없음 (lsof 또는 netstat 필요)"
fi

echo ""

# 로그 파일 상태
log_status "로그 파일 상태"
echo "---------------"

check_log_file() {
    local file_path=$1
    local file_name=$2
    
    if [ -f "$file_path" ]; then
        local size=$(stat -f%z "$file_path" 2>/dev/null || stat -c%s "$file_path" 2>/dev/null)
        local modified=$(stat -f%Sm "$file_path" 2>/dev/null || stat -c%y "$file_path" 2>/dev/null | cut -d' ' -f1-2)
        
        log_info "✅ $file_name 존재"
        log_data "   📏 크기: $(numfmt --to=iec $size 2>/dev/null || echo "$size bytes")"
        log_data "   🕐 최종 수정: $modified"
        
        # 최근 로그 에러 확인
        if [[ "$file_name" == *"로그"* ]]; then
            local recent_errors=$(tail -100 "$file_path" 2>/dev/null | grep -i "error\|exception\|failed\|traceback" | wc -l || echo "0")
            if [ "$recent_errors" -gt 0 ]; then
                log_warn "   ⚠️  최근 100줄에서 오류 $recent_errors개 발견"
                echo "   📝 확인: tail -20 $file_path | grep -i error"
            else
                log_info "   ✅ 최근 로그에서 오류 없음"
            fi
            
            # 최근 활동 확인
            local last_line=$(tail -1 "$file_path" 2>/dev/null || echo "내용 없음")
            if [ ${#last_line} -gt 100 ]; then
                last_line="${last_line:0:100}..."
            fi
            log_data "   📄 최근 활동: $last_line"
        fi
    else
        log_error "❌ $file_name 없음"
    fi
}

check_log_file "$LOG_FILE" "메인 로그"
check_log_file "$ERROR_LOG" "에러 로그"

# 거래 관련 파일들
if [ -f "trade_history.csv" ]; then
    TRADE_COUNT=$(tail -n +2 trade_history.csv 2>/dev/null | wc -l || echo "0")
    log_info "✅ 거래 기록 파일 존재"
    log_data "   📊 총 거래 기록: ${TRADE_COUNT}개"
else
    log_warn "❌ 거래 기록 파일 없음"
fi

if [ -f "daily_pnl.json" ]; then
    log_info "✅ 일일 손익 파일 존재"
else
    log_warn "❌ 일일 손익 파일 없음"
fi

echo ""

# 시스템 리소스
log_status "시스템 리소스"
echo "-------------"

# CPU 사용률
if command -v top >/dev/null 2>&1; then
    CPU_OVERALL=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1 2>/dev/null || echo "N/A")
    log_data "💻 전체 CPU 사용률: ${CPU_OVERALL}%"
fi

# 메모리 사용률
if command -v free >/dev/null 2>&1; then
    MEMORY_USAGE=$(free | grep Mem | awk '{printf("%.1f%%"), $3/$2 * 100.0}' 2>/dev/null || echo "N/A")
    log_data "🧠 메모리 사용률: $MEMORY_USAGE"
fi

# 디스크 사용률
DISK_USAGE=$(df -h . | awk 'NR==2{printf "%s", $5}' 2>/dev/null || echo "N/A")
log_data "💾 디스크 사용률: $DISK_USAGE"

echo ""

# 전체 상태 요약
log_status "전체 상태 요약"
echo "---------------"

RUNNING_COUNT=0
STATUS_MESSAGES=()

if [ ! -z "$MAIN_PROCESSES" ]; then
    ((RUNNING_COUNT++))
    STATUS_MESSAGES+=("✅ Python 메인 프로세스: 실행 중")
fi

if [ ! -z "$STREAMLIT_PROCESSES" ]; then
    ((RUNNING_COUNT++))
    STATUS_MESSAGES+=("✅ Streamlit 대시보드: 실행 중")
fi

if command -v lsof >/dev/null 2>&1 && lsof -i :$DASHBOARD_PORT >/dev/null 2>&1; then
    ((RUNNING_COUNT++))
    STATUS_MESSAGES+=("✅ 대시보드 포트: 활성")
elif [ ! -z "$STREAMLIT_PROCESSES" ]; then
    STATUS_MESSAGES+=("⚠️  대시보드 프로세스는 있지만 포트가 비활성")
fi

# 상태 메시지 출력
for msg in "${STATUS_MESSAGES[@]}"; do
    echo "   $msg"
done

if [ $RUNNING_COUNT -eq 0 ]; then
    STATUS_MESSAGES+=("❌ 모든 서비스가 중지된 상태")
fi

echo ""

# 최종 판단
if [ $RUNNING_COUNT -gt 0 ]; then
    log_info "🎯 CoinButler 시스템이 부분적으로 또는 완전히 실행 중입니다!"
    
    if [ -f "$PID_FILE" ]; then
        log_data "📊 상세 상태: ./start.sh --status"
        log_data "🛑 중지: ./stop.sh"  
        log_data "📝 로그 확인: tail -f $LOG_FILE"
    fi
    
    if command -v lsof >/dev/null 2>&1 && lsof -i :$DASHBOARD_PORT >/dev/null 2>&1; then
        EXTERNAL_IP=$(curl -s -m 3 ifconfig.me 2>/dev/null || echo "localhost")
        log_data "🌐 대시보드 접속: http://$EXTERNAL_IP:$DASHBOARD_PORT"
    fi
else
    log_error "❌ CoinButler 시스템이 실행 중이 아닙니다."
    log_data "🚀 시작: ./start.sh"
    log_data "📖 도움말: ./start.sh --help"
fi

echo ""
echo "=================================="