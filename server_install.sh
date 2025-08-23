#!/bin/bash

# CoinButler V2 서버 설치 스크립트
# Ubuntu 20.04+ 기준

set -e

echo "🚀 CoinButler V2 서버 설치를 시작합니다..."
echo "=============================================="

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

# 권한 확인
if [[ $EUID -eq 0 ]]; then
   log_error "이 스크립트는 root 권한으로 실행하면 안됩니다."
   log_info "다음과 같이 실행하세요: bash server_install.sh"
   exit 1
fi

# 1. 시스템 업데이트
log_info "시스템 업데이트 중..."
sudo apt update && sudo apt upgrade -y

# 2. 기본 패키지 설치
log_info "기본 패키지 설치 중..."
sudo apt install -y curl wget git nano vim htop unzip tree
sudo apt install -y build-essential software-properties-common
sudo apt install -y lsof net-tools iotop nethogs

# 3. Python 및 개발 도구 설치
log_info "Python 및 개발 도구 설치 중..."
sudo apt install -y python3 python3-pip python3-venv python3-dev
sudo apt install -y python3-distutils python3-setuptools

# 4. 컴파일 라이브러리 설치
log_info "컴파일 라이브러리 설치 중..."
sudo apt install -y gcc g++ make cmake
sudo apt install -y libffi-dev libssl-dev
sudo apt install -y libxml2-dev libxslt1-dev zlib1g-dev

# 5. 이미지 처리 라이브러리 설치
log_info "이미지 처리 라이브러리 설치 중..."
sudo apt install -y libjpeg-dev libpng-dev libtiff-dev
sudo apt install -y libfreetype6-dev liblcms2-dev libwebp-dev

# 6. 기타 필수 라이브러리
log_info "기타 필수 라이브러리 설치 중..."
sudo apt install -y pkg-config libhdf5-dev
sudo apt install -y libcairo2-dev libgirepository1.0-dev

# 7. 방화벽 설정
log_info "방화벽 설정 중..."
sudo ufw --force enable
sudo ufw allow ssh
sudo ufw allow 8501/tcp comment 'Streamlit Dashboard'
sudo ufw reload

# 8. 타임존 설정
log_info "타임존을 한국시간으로 설정 중..."
sudo timedatectl set-timezone Asia/Seoul

# 9. Python pip 업그레이드
log_info "Python pip 업그레이드 중..."
python3 -m pip install --upgrade pip

# 10. 시스템 사용자 추가 (coinbutler 전용)
log_info "coinbutler 시스템 사용자 생성 중..."
if ! id "coinbutler" &>/dev/null; then
    sudo adduser --system --group --home /opt/coinbutler coinbutler
    sudo mkdir -p /opt/coinbutler
    sudo chown coinbutler:coinbutler /opt/coinbutler
    log_info "coinbutler 사용자가 생성되었습니다."
else
    log_warn "coinbutler 사용자가 이미 존재합니다."
fi

# 11. 로그 디렉토리 생성
log_info "로그 디렉토리 설정 중..."
sudo mkdir -p /var/log/coinbutler
sudo chown coinbutler:coinbutler /var/log/coinbutler
sudo chmod 755 /var/log/coinbutler

# 12. 로그 로테이션 설정
log_info "로그 로테이션 설정 중..."
sudo tee /etc/logrotate.d/coinbutler > /dev/null <<EOF
/var/log/coinbutler/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    copytruncate
    su coinbutler coinbutler
}
EOF

# 13. systemd 서비스 파일 생성
log_info "systemd 서비스 파일 생성 중..."
sudo tee /etc/systemd/system/coinbutler.service > /dev/null <<EOF
[Unit]
Description=CoinButler V2 Auto Trading Bot
After=network.target

[Service]
Type=simple
User=coinbutler
Group=coinbutler
WorkingDirectory=/opt/coinbutler
ExecStart=/opt/coinbutler/venv/bin/python /opt/coinbutler/main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=coinbutler

# 환경 변수
Environment=PYTHONPATH=/opt/coinbutler
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

# 14. 자동 업데이트 설정
log_info "자동 보안 업데이트 설정 중..."
sudo apt install -y unattended-upgrades
echo 'Unattended-Upgrade::Automatic-Reboot "false";' | sudo tee -a /etc/apt/apt.conf.d/50unattended-upgrades

# 15. 모니터링 스크립트 생성
log_info "시스템 모니터링 스크립트 생성 중..."
sudo tee /usr/local/bin/coinbutler-monitor.sh > /dev/null <<'EOF'
#!/bin/bash
# CoinButler 모니터링 스크립트

echo "=== CoinButler 시스템 모니터링 ==="
echo "시간: $(date)"
echo ""

# 시스템 리소스
echo "--- 시스템 리소스 ---"
echo "CPU 사용률: $(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)"
echo "메모리 사용률: $(free | grep Mem | awk '{printf("%.2f%%"), $3/$2 * 100.0}')"
echo "디스크 사용률: $(df -h / | awk 'NR==2{printf "%s", $5}')"
echo ""

# CoinButler 프로세스 상태
echo "--- CoinButler 프로세스 ---"
if systemctl is-active --quiet coinbutler; then
    echo "상태: 실행 중 ✓"
    echo "PID: $(systemctl show -p MainPID coinbutler | cut -d= -f2)"
else
    echo "상태: 중지됨 ✗"
fi

# 포트 확인
echo ""
echo "--- 포트 상태 ---"
if netstat -tuln | grep -q ":8501"; then
    echo "대시보드 포트(8501): 열림 ✓"
else
    echo "대시보드 포트(8501): 닫힘 ✗"
fi

echo ""
echo "================================"
EOF

sudo chmod +x /usr/local/bin/coinbutler-monitor.sh

# 16. 설치 완료 정보 출력
echo ""
echo "=============================================="
log_info "🎉 CoinButler V2 서버 설치가 완료되었습니다!"
echo "=============================================="
echo ""
echo "📋 설치된 구성 요소:"
echo "  ✓ Python 3.8+ 및 필수 패키지"
echo "  ✓ 개발 라이브러리 및 도구"
echo "  ✓ 방화벽 설정 (포트 8501 열림)"
echo "  ✓ 타임존 설정 (Asia/Seoul)"
echo "  ✓ coinbutler 시스템 사용자"
echo "  ✓ systemd 서비스 설정"
echo "  ✓ 로그 로테이션 설정"
echo "  ✓ 모니터링 도구"
echo ""
echo "📁 중요 경로:"
echo "  • 설치 경로: /opt/coinbutler"
echo "  • 로그 경로: /var/log/coinbutler"
echo "  • 서비스 파일: /etc/systemd/system/coinbutler.service"
echo ""
echo "🔧 다음 단계:"
echo "  1. CoinButler 소스코드를 /opt/coinbutler에 복사"
echo "  2. 가상환경 생성 및 패키지 설치"
echo "  3. .env 파일 설정 (API 키 등)"
echo "  4. systemctl enable coinbutler"
echo "  5. systemctl start coinbutler"
echo ""
echo "📊 모니터링 명령어:"
echo "  • 상태 확인: sudo /usr/local/bin/coinbutler-monitor.sh"
echo "  • 서비스 상태: systemctl status coinbutler"
echo "  • 로그 확인: journalctl -u coinbutler -f"
echo ""
echo "🌐 접속 정보:"
echo "  • 대시보드: http://$(curl -s ifconfig.me):8501"
echo "  • SSH: ssh $(whoami)@$(curl -s ifconfig.me)"
echo ""
log_info "서버 설치가 완료되었습니다. 이제 CoinButler를 설치하세요!"
