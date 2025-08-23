#!/bin/bash

# CoinButler V2 중지 스크립트

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
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

# 변수 설정
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PID_FILE="$SCRIPT_DIR/coinbutler.pid"

echo "🛑 CoinButler V2 시스템 중지"
echo "============================"

# PID 파일 확인 및 프로세스 중지
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    
    if ps -p "$PID" > /dev/null 2>&1; then
        log_info "CoinButler 프로세스 중지 중... (PID: $PID)"
        
        # 정상 종료 시도
        kill -TERM "$PID" 2>/dev/null || true
        
        # 종료 확인 (최대 15초 대기)
        for i in {1..15}; do
            if ! ps -p "$PID" > /dev/null 2>&1; then
                log_info "✅ 프로세스가 정상적으로 중지되었습니다."
                break
            fi
            if [ $i -eq 15 ]; then
                log_warn "정상 종료 시간이 초과되어 강제 종료합니다..."
                kill -KILL "$PID" 2>/dev/null || true
                sleep 1
                if ! ps -p "$PID" > /dev/null 2>&1; then
                    log_info "✅ 프로세스가 강제 종료되었습니다."
                else
                    log_error "프로세스 종료에 실패했습니다."
                fi
            else
                echo -n "."
                sleep 1
            fi
        done
        
    else
        log_warn "해당 PID의 프로세스가 실행 중이 아닙니다."
    fi
    
    # PID 파일 삭제
    rm -f "$PID_FILE"
    log_info "PID 파일을 정리했습니다."
    
else
    log_warn "PID 파일을 찾을 수 없습니다."
fi

# 관련 프로세스 정리
log_info "관련 프로세스 정리 중..."

# CoinButler Python 프로세스 찾기
PYTHON_PIDS=$(pgrep -f "python.*main.py" 2>/dev/null || true)
if [ ! -z "$PYTHON_PIDS" ]; then
    log_info "CoinButler Python 프로세스 발견: $PYTHON_PIDS"
    echo "$PYTHON_PIDS" | xargs -r kill -TERM 2>/dev/null || true
    sleep 2
    
    # 여전히 실행 중인 프로세스 강제 종료
    REMAINING=$(pgrep -f "python.*main.py" 2>/dev/null || true)
    if [ ! -z "$REMAINING" ]; then
        log_warn "강제 종료: $REMAINING"
        echo "$REMAINING" | xargs -r kill -KILL 2>/dev/null || true
    fi
fi

# Streamlit 프로세스 정리
STREAMLIT_PIDS=$(pgrep -f "streamlit.*dashboard" 2>/dev/null || true)
if [ ! -z "$STREAMLIT_PIDS" ]; then
    log_info "Streamlit 프로세스 정리: $STREAMLIT_PIDS"
    echo "$STREAMLIT_PIDS" | xargs -r kill -TERM 2>/dev/null || true
    sleep 1
    
    # 강제 종료
    REMAINING=$(pgrep -f "streamlit.*dashboard" 2>/dev/null || true)
    if [ ! -z "$REMAINING" ]; then
        echo "$REMAINING" | xargs -r kill -KILL 2>/dev/null || true
    fi
fi

# 포트 8501 사용 프로세스 정리
if command -v lsof >/dev/null 2>&1; then
    PORT_PIDS=$(lsof -ti :8501 2>/dev/null || true)
    if [ ! -z "$PORT_PIDS" ]; then
        log_info "포트 8501 사용 프로세스 정리: $PORT_PIDS"
        echo "$PORT_PIDS" | xargs -r kill -TERM 2>/dev/null || true
        sleep 1
        
        # 강제 종료
        REMAINING=$(lsof -ti :8501 2>/dev/null || true)
        if [ ! -z "$REMAINING" ]; then
            echo "$REMAINING" | xargs -r kill -KILL 2>/dev/null || true
        fi
    fi
fi

log_info "✅ CoinButler 시스템이 완전히 중지되었습니다."

# 최종 상태 확인
echo ""
log_info "최종 상태 확인:"

RUNNING_PROCESSES=$(pgrep -f "CoinButler\|main\.py\|dashboard\.py" 2>/dev/null || true)
if [ -z "$RUNNING_PROCESSES" ]; then
    log_info "🔍 ✅ CoinButler 관련 프로세스가 모두 중지되었습니다."
else
    log_warn "⚠️  일부 프로세스가 여전히 실행 중입니다:"
    ps -p $RUNNING_PROCESSES -o pid,ppid,cmd 2>/dev/null || true
fi

# 포트 상태 확인
if command -v lsof >/dev/null 2>&1; then
    if lsof -i :8501 >/dev/null 2>&1; then
        log_warn "⚠️  포트 8501이 여전히 사용 중입니다."
        lsof -i :8501
    else
        log_info "🌐 ✅ 포트 8501이 해제되었습니다."
    fi
fi

echo ""
log_info "🚀 다시 시작하려면: ./start.sh"