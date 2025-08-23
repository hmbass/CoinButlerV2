#!/bin/bash

# CoinButler V2 서버 배포 스크립트
# 서버에서 실행하여 CoinButler 애플리케이션을 배포합니다.

set -e

echo "🚀 CoinButler V2 애플리케이션 배포를 시작합니다..."
echo "================================================="

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
INSTALL_DIR="/opt/coinbutler"
SERVICE_USER="coinbutler"
GITHUB_REPO="your_username/CoinButlerV2"  # 실제 GitHub 저장소로 변경

# 1. 권한 확인
if [[ $EUID -eq 0 ]]; then
   log_error "이 스크립트는 root 권한으로 실행하면 안됩니다."
   log_info "다음과 같이 실행하세요: bash deploy.sh"
   exit 1
fi

# 2. coinbutler 사용자 존재 확인
if ! id "$SERVICE_USER" &>/dev/null; then
    log_error "coinbutler 사용자가 존재하지 않습니다."
    log_info "먼저 server_install.sh를 실행해주세요."
    exit 1
fi

# 3. 소스코드 다운로드 또는 복사
log_step "소스코드 준비 중..."

if [ -d "$INSTALL_DIR" ]; then
    log_warn "기존 설치 디렉토리가 존재합니다. 백업 생성 중..."
    sudo mv "$INSTALL_DIR" "${INSTALL_DIR}.backup.$(date +%Y%m%d_%H%M%S)"
fi

# 설치 디렉토리 생성
sudo mkdir -p "$INSTALL_DIR"

# 현재 디렉토리에서 소스코드 복사 (GitHub 클론 대신)
log_info "현재 디렉토리에서 소스코드 복사 중..."
sudo cp -r . "$INSTALL_DIR/"

# 소유권 변경
sudo chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"

# 4. Python 가상환경 생성
log_step "Python 가상환경 생성 중..."
cd "$INSTALL_DIR"
sudo -u "$SERVICE_USER" python3 -m venv venv

# 5. 의존성 패키지 설치
log_step "Python 패키지 설치 중..."
sudo -u "$SERVICE_USER" bash -c "
    source venv/bin/activate && 
    pip install --upgrade pip && 
    pip install -r requirements.txt
"

# 6. 스크립트 실행 권한 부여
log_step "실행 권한 설정 중..."
sudo chmod +x "$INSTALL_DIR"/*.sh

# 7. 환경변수 파일 설정
log_step "환경변수 파일 설정 중..."
if [ ! -f "$INSTALL_DIR/.env" ]; then
    if [ -f "$INSTALL_DIR/env_example.txt" ]; then
        sudo -u "$SERVICE_USER" cp "$INSTALL_DIR/env_example.txt" "$INSTALL_DIR/.env"
        log_info ".env 파일이 생성되었습니다. API 키를 설정해주세요."
    else
        log_error "env_example.txt 파일을 찾을 수 없습니다."
        exit 1
    fi
else
    log_info "기존 .env 파일이 존재합니다."
fi

# 8. 로그 디렉토리 링크 생성
log_step "로그 디렉토리 설정 중..."
sudo -u "$SERVICE_USER" mkdir -p "$INSTALL_DIR/logs"
sudo ln -sf "$INSTALL_DIR"/*.log /var/log/coinbutler/ 2>/dev/null || true

# 9. systemd 서비스 등록 및 활성화
log_step "systemd 서비스 등록 중..."
sudo systemctl daemon-reload
sudo systemctl enable coinbutler

# 10. 방화벽 확인
log_step "방화벽 상태 확인 중..."
if sudo ufw status | grep -q "8501"; then
    log_info "방화벽에서 포트 8501이 열려 있습니다."
else
    log_warn "방화벽에서 포트 8501을 열어주세요: sudo ufw allow 8501"
fi

# 11. 헬스체크 스크립트 생성
log_step "헬스체크 스크립트 생성 중..."
sudo tee /usr/local/bin/coinbutler-health.sh > /dev/null <<'EOF'
#!/bin/bash
# CoinButler 헬스체크 스크립트

INSTALL_DIR="/opt/coinbutler"
LOG_FILE="/var/log/coinbutler/health.log"

# 로그 함수
log_health() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | sudo tee -a "$LOG_FILE"
}

# 서비스 상태 확인
if systemctl is-active --quiet coinbutler; then
    log_health "✓ CoinButler 서비스가 정상 실행 중입니다."
else
    log_health "✗ CoinButler 서비스가 중지되어 있습니다."
    log_health "서비스 재시작을 시도합니다..."
    sudo systemctl start coinbutler
    if systemctl is-active --quiet coinbutler; then
        log_health "✓ CoinButler 서비스가 성공적으로 재시작되었습니다."
    else
        log_health "✗ CoinButler 서비스 재시작에 실패했습니다."
        exit 1
    fi
fi

# 대시보드 포트 확인
if netstat -tuln | grep -q ":8501"; then
    log_health "✓ 대시보드 포트(8501)가 정상적으로 열려 있습니다."
else
    log_health "✗ 대시보드 포트(8501)에 접근할 수 없습니다."
fi

# 디스크 공간 확인 (90% 이상 시 경고)
DISK_USAGE=$(df -h "$INSTALL_DIR" | awk 'NR==2{print $5}' | sed 's/%//g')
if [ "$DISK_USAGE" -gt 90 ]; then
    log_health "⚠ 디스크 사용률이 ${DISK_USAGE}%입니다. 공간을 확보해주세요."
fi

# 메모리 사용률 확인
MEMORY_USAGE=$(free | grep Mem | awk '{printf("%.0f"), $3/$2 * 100.0}')
if [ "$MEMORY_USAGE" -gt 90 ]; then
    log_health "⚠ 메모리 사용률이 ${MEMORY_USAGE}%입니다."
fi

log_health "헬스체크 완료"
EOF

sudo chmod +x /usr/local/bin/coinbutler-health.sh

# 12. 크론잡 설정 (5분마다 헬스체크)
log_step "자동 헬스체크 설정 중..."
(sudo crontab -l 2>/dev/null || true; echo "*/5 * * * * /usr/local/bin/coinbutler-health.sh") | sudo crontab -

# 13. 배포 완료 확인
log_step "배포 상태 확인 중..."

# .env 파일 API 키 확인
if grep -q "your_.*_key_here" "$INSTALL_DIR/.env"; then
    log_warn "⚠ API 키가 아직 설정되지 않았습니다!"
    API_CONFIGURED=false
else
    log_info "✓ API 키가 설정되어 있습니다."
    API_CONFIGURED=true
fi

# 14. 배포 완료 정보 출력
echo ""
echo "================================================="
log_info "🎉 CoinButler V2 배포가 완료되었습니다!"
echo "================================================="
echo ""
echo "📋 배포 정보:"
echo "  • 설치 경로: $INSTALL_DIR"
echo "  • 서비스 사용자: $SERVICE_USER"
echo "  • Python 환경: $INSTALL_DIR/venv"
echo "  • 로그 경로: /var/log/coinbutler"
echo ""
echo "🔧 서비스 관리 명령어:"
echo "  • 서비스 시작: sudo systemctl start coinbutler"
echo "  • 서비스 중지: sudo systemctl stop coinbutler"
echo "  • 서비스 상태: sudo systemctl status coinbutler"
echo "  • 서비스 로그: journalctl -u coinbutler -f"
echo ""
echo "📊 모니터링 도구:"
echo "  • 시스템 모니터: sudo /usr/local/bin/coinbutler-monitor.sh"
echo "  • 헬스체크: sudo /usr/local/bin/coinbutler-health.sh"
echo "  • 상태 스크립트: cd $INSTALL_DIR && ./status.sh"
echo ""
echo "🌐 접속 정보:"
EXTERNAL_IP=$(curl -s ifconfig.me 2>/dev/null || echo "SERVER_IP")
echo "  • 대시보드: http://$EXTERNAL_IP:8501"
echo "  • SSH: ssh $(whoami)@$EXTERNAL_IP"
echo ""

if [ "$API_CONFIGURED" = false ]; then
    echo "⚠️  다음 단계가 필요합니다:"
    echo "  1. API 키 설정: sudo nano $INSTALL_DIR/.env"
    echo "     - UPBIT_ACCESS_KEY: 업비트 API 액세스 키"
    echo "     - UPBIT_SECRET_KEY: 업비트 API 시크릿 키"
    echo "     - OPENAI_API_KEY: OpenAI API 키"
    echo "     - TELEGRAM_BOT_TOKEN: 텔레그램 봇 토큰 (선택)"
    echo "     - TELEGRAM_CHAT_ID: 텔레그램 채팅 ID (선택)"
    echo ""
    echo "  2. 서비스 시작: sudo systemctl start coinbutler"
    echo ""
else
    echo "✅ API 키가 설정되어 있습니다. 서비스를 시작할 수 있습니다:"
    echo "   sudo systemctl start coinbutler"
    echo ""
fi

echo "📚 추가 정보:"
echo "  • README.md: $INSTALL_DIR/README.md"
echo "  • 설정 예제: $INSTALL_DIR/env_example.txt"
echo "  • 로그 파일: $INSTALL_DIR/*.log"
echo ""

log_info "배포가 성공적으로 완료되었습니다!"
echo ""
