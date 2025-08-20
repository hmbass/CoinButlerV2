#!/bin/bash

# CoinButler 상태 확인 스크립트
# Ubuntu/Linux 환경에서 사용

set -e

echo "🔍 CoinButler 자동매매 시스템 상태 확인"
echo "============================================"

# 현재 시간
echo "📅 확인 시간: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# PID 파일 확인
if [ -f "coinbutler.pid" ]; then
    PID=$(cat coinbutler.pid)
    echo "📋 PID 파일: coinbutler.pid (PID: $PID)"
    
    if ps -p $PID > /dev/null 2>&1; then
        echo "✅ 메인 프로세스: 실행 중 (PID: $PID)"
        
        # 프로세스 정보 표시
        echo "📊 프로세스 정보:"
        ps -p $PID -o pid,ppid,pcpu,pmem,etime,cmd --no-headers | \
        awk '{printf "   PID: %s, CPU: %s%%, MEM: %s%%, 실행시간: %s\n", $1, $3, $4, $5}'
        
    else
        echo "❌ 메인 프로세스: 중지됨 (PID 파일은 존재하지만 프로세스 없음)"
        echo "⚠️  PID 파일을 정리하시겠습니까? (y/N)"
        read -r response
        if [[ "$response" =~ ^[Yy]$ ]]; then
            rm -f coinbutler.pid
            echo "🧹 PID 파일이 삭제되었습니다."
        fi
    fi
else
    echo "❌ PID 파일: 없음 (백그라운드로 실행되지 않음)"
fi

echo ""

# CoinButler 관련 프로세스 확인
echo "🔍 관련 프로세스 검색 중..."

MAIN_PROCESSES=$(pgrep -f "python.*main.py" 2>/dev/null || true)
BOT_PROCESSES=$(pgrep -f "CoinButler.*Bot" 2>/dev/null || true)
DASHBOARD_PROCESSES=$(pgrep -f "streamlit.*dashboard.py" 2>/dev/null || true)

if [ ! -z "$MAIN_PROCESSES" ]; then
    echo "✅ 메인 프로세스 실행 중:"
    ps -p $MAIN_PROCESSES -o pid,ppid,pcpu,pmem,etime,cmd --no-headers | \
    while read line; do
        echo "   $line"
    done
else
    echo "❌ 메인 프로세스: 실행 중이 아님"
fi

if [ ! -z "$BOT_PROCESSES" ]; then
    echo "✅ 트레이딩 봇 프로세스 실행 중:"
    ps -p $BOT_PROCESSES -o pid,ppid,pcpu,pmem,etime,cmd --no-headers | \
    while read line; do
        echo "   $line"
    done
else
    echo "❌ 트레이딩 봇: 실행 중이 아님"
fi

if [ ! -z "$DASHBOARD_PROCESSES" ]; then
    echo "✅ 대시보드 프로세스 실행 중:"
    ps -p $DASHBOARD_PROCESSES -o pid,ppid,pcpu,pmem,etime,cmd --no-headers | \
    while read line; do
        echo "   $line"
    done
    
    # 대시보드 URL 확인
    DASHBOARD_PORT=$(grep "DASHBOARD_PORT" .env 2>/dev/null | cut -d'=' -f2 || echo "8501")
    DASHBOARD_HOST=$(grep "DASHBOARD_HOST" .env 2>/dev/null | cut -d'=' -f2 || echo "0.0.0.0")
    echo "🌐 대시보드 URL: http://$DASHBOARD_HOST:$DASHBOARD_PORT"
    
else
    echo "❌ 대시보드: 실행 중이 아님"
fi

echo ""

# 로그 파일 확인
echo "📝 로그 파일 상태:"

if [ -f "coinbutler.log" ]; then
    LOG_SIZE=$(stat -f%z coinbutler.log 2>/dev/null || stat -c%s coinbutler.log 2>/dev/null)
    LOG_MODIFIED=$(stat -f%Sm coinbutler.log 2>/dev/null || stat -c%y coinbutler.log 2>/dev/null | cut -d' ' -f1-2)
    echo "   📄 coinbutler.log: 존재 (크기: $LOG_SIZE bytes, 수정: $LOG_MODIFIED)"
    
    # 최근 로그 에러 확인
    RECENT_ERRORS=$(tail -100 coinbutler.log 2>/dev/null | grep -i "error\|exception\|failed" | wc -l || echo "0")
    if [ "$RECENT_ERRORS" -gt 0 ]; then
        echo "   ⚠️  최근 100줄에서 오류 $RECENT_ERRORS개 발견"
        echo "   📝 최근 오류 확인: tail -50 coinbutler.log | grep -i error"
    else
        echo "   ✅ 최근 로그에서 오류 없음"
    fi
else
    echo "   ❌ coinbutler.log: 없음"
fi

if [ -f "coinbutler_main.log" ]; then
    LOG_SIZE=$(stat -f%z coinbutler_main.log 2>/dev/null || stat -c%s coinbutler_main.log 2>/dev/null)
    LOG_MODIFIED=$(stat -f%Sm coinbutler_main.log 2>/dev/null || stat -c%y coinbutler_main.log 2>/dev/null | cut -d' ' -f1-2)
    echo "   📄 coinbutler_main.log: 존재 (크기: $LOG_SIZE bytes, 수정: $LOG_MODIFIED)"
else
    echo "   ❌ coinbutler_main.log: 없음"
fi

if [ -f "logs/coinbutler_output.log" ]; then
    LOG_SIZE=$(stat -f%z logs/coinbutler_output.log 2>/dev/null || stat -c%s logs/coinbutler_output.log 2>/dev/null)
    LOG_MODIFIED=$(stat -f%Sm logs/coinbutler_output.log 2>/dev/null || stat -c%y logs/coinbutler_output.log 2>/dev/null | cut -d' ' -f1-2)
    echo "   📄 logs/coinbutler_output.log: 존재 (크기: $LOG_SIZE bytes, 수정: $LOG_MODIFIED)"
else
    echo "   ❌ logs/coinbutler_output.log: 없음"
fi

echo ""

# 데이터 파일 확인
echo "💾 데이터 파일 상태:"

if [ -f "trade_history.csv" ]; then
    TRADE_COUNT=$(tail -n +2 trade_history.csv 2>/dev/null | wc -l || echo "0")
    echo "   📊 trade_history.csv: 존재 (거래 기록 $TRADE_COUNT개)"
else
    echo "   ❌ trade_history.csv: 없음"
fi

if [ -f "daily_pnl.json" ]; then
    echo "   📈 daily_pnl.json: 존재"
else
    echo "   ❌ daily_pnl.json: 없음"
fi

echo ""

# 포트 사용 확인
echo "🌐 네트워크 포트 상태:"
DASHBOARD_PORT=$(grep "DASHBOARD_PORT" .env 2>/dev/null | cut -d'=' -f2 || echo "8501")

if command -v lsof >/dev/null 2>&1; then
    PORT_USAGE=$(lsof -i :$DASHBOARD_PORT 2>/dev/null || true)
    if [ ! -z "$PORT_USAGE" ]; then
        echo "   ✅ 포트 $DASHBOARD_PORT: 사용 중"
        echo "$PORT_USAGE" | head -5
    else
        echo "   ❌ 포트 $DASHBOARD_PORT: 사용 중이 아님"
    fi
elif command -v netstat >/dev/null 2>&1; then
    PORT_USAGE=$(netstat -tuln | grep ":$DASHBOARD_PORT " || true)
    if [ ! -z "$PORT_USAGE" ]; then
        echo "   ✅ 포트 $DASHBOARD_PORT: 사용 중"
        echo "   $PORT_USAGE"
    else
        echo "   ❌ 포트 $DASHBOARD_PORT: 사용 중이 아님"
    fi
else
    echo "   ❓ 포트 확인 도구 없음 (lsof 또는 netstat 필요)"
fi

echo ""

# 전체 상태 요약
echo "📋 전체 상태 요약:"

RUNNING_COUNT=0

if [ ! -z "$MAIN_PROCESSES" ] || [ ! -z "$BOT_PROCESSES" ] || [ ! -z "$DASHBOARD_PROCESSES" ]; then
    if [ ! -z "$MAIN_PROCESSES" ]; then
        ((RUNNING_COUNT++))
        echo "   ✅ 메인 프로세스: 실행 중"
    fi
    if [ ! -z "$BOT_PROCESSES" ] || [ ! -z "$MAIN_PROCESSES" ]; then
        ((RUNNING_COUNT++))
        echo "   ✅ 트레이딩 봇: 실행 중"
    fi
    if [ ! -z "$DASHBOARD_PROCESSES" ] || [ ! -z "$MAIN_PROCESSES" ]; then
        ((RUNNING_COUNT++))
        echo "   ✅ 대시보드: 실행 중"
    fi
    
    echo ""
    echo "🎯 CoinButler 시스템이 정상적으로 실행 중입니다!"
    
else
    echo "   ❌ 모든 프로세스가 중지된 상태입니다."
    echo ""
    echo "🚀 시작하려면: ./start.sh"
fi

echo ""
echo "============================================"
