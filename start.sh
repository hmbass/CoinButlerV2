#!/bin/bash

# CoinButler 시작 스크립트
# Ubuntu/Linux 환경에서 사용

set -e

echo "🤖 CoinButler 자동매매 시스템 시작 중..."
echo "============================================"

# Python 버전 체크
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3가 설치되지 않았습니다."
    exit 1
fi

# 가상환경 확인 및 생성
if [ ! -d "venv" ]; then
    echo "📦 Python 가상환경 생성 중..."
    python3 -m venv venv
fi

# 가상환경 활성화
echo "🔧 가상환경 활성화 중..."
source venv/bin/activate

# 의존성 패키지 설치
echo "📥 패키지 설치 중..."
pip install -r requirements.txt

# .env 파일 확인
if [ ! -f ".env" ]; then
    echo "⚠️  .env 파일이 없습니다."
    if [ -f "env_example.txt" ]; then
        echo "📝 env_example.txt를 .env로 복사합니다."
        cp env_example.txt .env
        echo "✏️  .env 파일을 편집하여 API 키를 설정해주세요."
        echo "    nano .env"
        exit 1
    else
        echo "❌ env_example.txt 파일도 없습니다."
        exit 1
    fi
fi

# 로그 디렉토리 생성
mkdir -p logs

# 백그라운드 실행 여부 확인
if [ "$1" = "--daemon" ] || [ "$1" = "-d" ]; then
    echo "🚀 백그라운드 모드로 CoinButler 시작 중..."
    nohup python3 main.py > logs/coinbutler_output.log 2>&1 &
    
    # PID 저장
    echo $! > coinbutler.pid
    
    echo "✅ CoinButler가 백그라운드에서 시작되었습니다."
    echo "📄 PID: $(cat coinbutler.pid)"
    echo "📊 대시보드: http://0.0.0.0:8501"
    echo "📝 로그: logs/coinbutler_output.log"
    echo ""
    echo "중지하려면: ./stop.sh"
    echo "상태 확인: ./status.sh"
    
elif [ "$1" = "--bot-only" ]; then
    echo "🤖 봇 전용 모드로 시작..."
    python3 main.py bot
    
elif [ "$1" = "--dashboard-only" ]; then
    echo "📊 대시보드 전용 모드로 시작..."
    python3 main.py dashboard
    
else
    echo "🚀 CoinButler 시작 중..."
    echo "📊 대시보드: http://0.0.0.0:8501"
    echo "🛑 중지하려면 Ctrl+C를 누르세요"
    echo ""
    
    python3 main.py
fi

echo "✅ 완료!"
