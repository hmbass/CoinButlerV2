#!/bin/bash

# CoinButler 중지 스크립트
# Ubuntu/Linux 환경에서 사용

set -e

echo "🛑 CoinButler 자동매매 시스템 중지 중..."
echo "============================================"

# PID 파일 확인
if [ -f "coinbutler.pid" ]; then
    PID=$(cat coinbutler.pid)
    
    if ps -p $PID > /dev/null 2>&1; then
        echo "📋 프로세스 중지 중... (PID: $PID)"
        
        # 프로세스와 자식 프로세스 모두 종료
        pkill -P $PID 2>/dev/null || true
        kill $PID 2>/dev/null || true
        
        # 종료 확인 (최대 10초 대기)
        for i in {1..10}; do
            if ! ps -p $PID > /dev/null 2>&1; then
                echo "✅ 프로세스가 정상적으로 중지되었습니다."
                break
            fi
            echo "⏳ 프로세스 종료 대기 중... ($i/10)"
            sleep 1
        done
        
        # 여전히 실행 중이면 강제 종료
        if ps -p $PID > /dev/null 2>&1; then
            echo "⚠️  강제 종료 실행 중..."
            kill -9 $PID 2>/dev/null || true
            echo "✅ 프로세스가 강제 종료되었습니다."
        fi
        
    else
        echo "⚠️  해당 PID의 프로세스가 실행 중이 아닙니다."
    fi
    
    # PID 파일 삭제
    rm -f coinbutler.pid
    
else
    echo "⚠️  coinbutler.pid 파일을 찾을 수 없습니다."
fi

# 관련 프로세스 정리
echo "🧹 관련 프로세스 정리 중..."

# CoinButler 관련 프로세스 찾아서 종료
PIDS=$(pgrep -f "python.*main.py" 2>/dev/null || true)
if [ ! -z "$PIDS" ]; then
    echo "📋 CoinButler 프로세스 발견: $PIDS"
    echo "$PIDS" | xargs -r kill -TERM
    sleep 2
    
    # 여전히 실행 중인 프로세스 강제 종료
    REMAINING=$(pgrep -f "python.*main.py" 2>/dev/null || true)
    if [ ! -z "$REMAINING" ]; then
        echo "⚠️  강제 종료: $REMAINING"
        echo "$REMAINING" | xargs -r kill -9
    fi
fi

# Streamlit 프로세스 정리
STREAMLIT_PIDS=$(pgrep -f "streamlit.*dashboard.py" 2>/dev/null || true)
if [ ! -z "$STREAMLIT_PIDS" ]; then
    echo "📊 Streamlit 프로세스 정리: $STREAMLIT_PIDS"
    echo "$STREAMLIT_PIDS" | xargs -r kill -TERM
    sleep 1
    
    # 여전히 실행 중인 프로세스 강제 종료
    REMAINING=$(pgrep -f "streamlit.*dashboard.py" 2>/dev/null || true)
    if [ ! -z "$REMAINING" ]; then
        echo "$REMAINING" | xargs -r kill -9
    fi
fi

echo "✅ CoinButler가 완전히 중지되었습니다."

# 실행 중인 CoinButler 프로세스 확인
RUNNING_PROCESSES=$(pgrep -f "CoinButler\|main\.py\|dashboard\.py" 2>/dev/null || true)
if [ -z "$RUNNING_PROCESSES" ]; then
    echo "🔍 확인 완료: CoinButler 관련 프로세스가 모두 중지되었습니다."
else
    echo "⚠️  일부 프로세스가 여전히 실행 중입니다:"
    ps -p $RUNNING_PROCESSES -o pid,ppid,cmd 2>/dev/null || true
fi
