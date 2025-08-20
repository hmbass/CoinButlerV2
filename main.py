"""
CoinButler 메인 실행 스크립트
봇과 대시보드를 병렬로 실행
"""
import os
import sys
import subprocess
import multiprocessing
import signal
import time
import logging
from datetime import datetime
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('coinbutler_main.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class CoinButlerManager:
    """CoinButler 시스템 관리자"""
    
    def __init__(self):
        self.bot_process = None
        self.dashboard_process = None
        self.is_running = False
        
        # 환경변수 검증
        self._validate_environment()
    
    def _validate_environment(self):
        """환경변수 검증"""
        required_vars = [
            'UPBIT_ACCESS_KEY',
            'UPBIT_SECRET_KEY'
        ]
        
        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            logger.error(f"필수 환경변수가 설정되지 않았습니다: {', '.join(missing_vars)}")
            logger.error(".env 파일을 확인해주세요.")
            sys.exit(1)
        
        logger.info("✅ 환경변수 검증 완료")
    
    def start_bot(self):
        """트레이딩 봇 시작 (별도 프로세스)"""
        try:
            logger.info("🤖 트레이딩 봇 시작 중...")
            
            # 봇을 별도 프로세스로 시작
            self.bot_process = multiprocessing.Process(
                target=self._run_bot_process,
                name="CoinButler-Bot"
            )
            self.bot_process.start()
            
            logger.info(f"✅ 트레이딩 봇 시작됨 (PID: {self.bot_process.pid})")
            return True
            
        except Exception as e:
            logger.error(f"봇 시작 실패: {e}")
            return False
    
    def start_dashboard(self):
        """대시보드 시작 (별도 프로세스)"""
        try:
            logger.info("📊 대시보드 시작 중...")
            
            host = os.getenv('DASHBOARD_HOST', '0.0.0.0')
            port = os.getenv('DASHBOARD_PORT', '8501')
            
            # Streamlit 대시보드를 별도 프로세스로 시작
            dashboard_cmd = [
                sys.executable, '-m', 'streamlit', 'run', 
                'dashboard.py',
                '--server.address', host,
                '--server.port', port,
                '--server.headless', 'true',
                '--server.fileWatcherType', 'none',
                '--browser.gatherUsageStats', 'false'
            ]
            
            self.dashboard_process = subprocess.Popen(
                dashboard_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            logger.info(f"✅ 대시보드 시작됨 (PID: {self.dashboard_process.pid})")
            logger.info(f"🌐 대시보드 URL: http://{host}:{port}")
            return True
            
        except Exception as e:
            logger.error(f"대시보드 시작 실패: {e}")
            return False
    
    def _run_bot_process(self):
        """봇 프로세스 실행 함수"""
        try:
            from trade_bot import main as bot_main
            bot_main()
        except Exception as e:
            logger.error(f"봇 프로세스 실행 오류: {e}")
    
    def start_all(self):
        """봇과 대시보드 모두 시작"""
        if self.is_running:
            logger.warning("시스템이 이미 실행 중입니다.")
            return
        
        logger.info("🚀 CoinButler 시스템 시작...")
        
        success = True
        
        # 봇 시작
        if not self.start_bot():
            success = False
        
        # 잠시 대기 (봇이 초기화될 시간)
        time.sleep(3)
        
        # 대시보드 시작
        if not self.start_dashboard():
            success = False
        
        if success:
            self.is_running = True
            logger.info("✅ CoinButler 시스템이 성공적으로 시작되었습니다!")
            self._print_startup_info()
        else:
            logger.error("❌ 시스템 시작에 실패했습니다.")
            self.stop_all()
    
    def stop_all(self):
        """봇과 대시보드 모두 중지"""
        logger.info("🛑 CoinButler 시스템 중지 중...")
        
        # 봇 프로세스 중지
        if self.bot_process and self.bot_process.is_alive():
            logger.info("봇 프로세스 중지 중...")
            self.bot_process.terminate()
            self.bot_process.join(timeout=10)
            
            if self.bot_process.is_alive():
                logger.warning("봇 프로세스 강제 종료")
                self.bot_process.kill()
                self.bot_process.join()
            
            logger.info("✅ 봇 프로세스 중지 완료")
        
        # 대시보드 프로세스 중지
        if self.dashboard_process and self.dashboard_process.poll() is None:
            logger.info("대시보드 프로세스 중지 중...")
            self.dashboard_process.terminate()
            
            try:
                self.dashboard_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                logger.warning("대시보드 프로세스 강제 종료")
                self.dashboard_process.kill()
            
            logger.info("✅ 대시보드 프로세스 중지 완료")
        
        self.is_running = False
        logger.info("✅ CoinButler 시스템이 중지되었습니다.")
    
    def restart_bot(self):
        """봇만 재시작"""
        logger.info("🔄 봇 재시작 중...")
        
        if self.bot_process and self.bot_process.is_alive():
            self.bot_process.terminate()
            self.bot_process.join(timeout=10)
        
        time.sleep(2)
        self.start_bot()
        
        logger.info("✅ 봇 재시작 완료")
    
    def get_status(self):
        """시스템 상태 조회"""
        bot_status = "실행 중" if self.bot_process and self.bot_process.is_alive() else "중지됨"
        dashboard_status = "실행 중" if self.dashboard_process and self.dashboard_process.poll() is None else "중지됨"
        
        return {
            'system_running': self.is_running,
            'bot_status': bot_status,
            'dashboard_status': dashboard_status,
            'bot_pid': self.bot_process.pid if self.bot_process else None,
            'dashboard_pid': self.dashboard_process.pid if self.dashboard_process else None
        }
    
    def _print_startup_info(self):
        """시작 정보 출력"""
        host = os.getenv('DASHBOARD_HOST', '0.0.0.0')
        port = os.getenv('DASHBOARD_PORT', '8501')
        
        print("\n" + "="*60)
        print("🤖 CoinButler 자동매매 시스템")
        print("="*60)
        print(f"📊 대시보드 URL: http://{host}:{port}")
        print(f"🤖 트레이딩 봇: 실행 중")
        print(f"📝 로그 파일: coinbutler.log, coinbutler_main.log")
        print("="*60)
        print("⚠️  중지하려면 Ctrl+C를 누르세요")
        print("="*60 + "\n")
    
    def monitor(self):
        """시스템 모니터링"""
        try:
            while self.is_running:
                # 봇 프로세스 상태 확인
                if self.bot_process and not self.bot_process.is_alive():
                    logger.error("봇 프로세스가 예기치 않게 종료되었습니다.")
                    # 자동 재시작 시도
                    logger.info("봇 자동 재시작 시도...")
                    time.sleep(5)
                    self.start_bot()
                
                # 대시보드 프로세스 상태 확인
                if self.dashboard_process and self.dashboard_process.poll() is not None:
                    logger.error("대시보드 프로세스가 예기치 않게 종료되었습니다.")
                    # 자동 재시작 시도
                    logger.info("대시보드 자동 재시작 시도...")
                    time.sleep(5)
                    self.start_dashboard()
                
                time.sleep(30)  # 30초마다 체크
                
        except KeyboardInterrupt:
            logger.info("사용자에 의한 중단 요청")
        except Exception as e:
            logger.error(f"모니터링 오류: {e}")
        finally:
            self.stop_all()

def signal_handler(signum, frame):
    """시그널 핸들러 (Ctrl+C 등)"""
    logger.info(f"시그널 {signum} 수신, 시스템 종료 중...")
    if 'manager' in globals():
        manager.stop_all()
    sys.exit(0)

def main():
    """메인 실행 함수"""
    # 시그널 핸들러 등록
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    global manager
    manager = CoinButlerManager()
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "bot":
            # 봇만 실행
            logger.info("봇 전용 모드로 실행")
            manager.start_bot()
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                manager.stop_all()
                
        elif command == "dashboard":
            # 대시보드만 실행
            logger.info("대시보드 전용 모드로 실행")
            manager.start_dashboard()
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                manager.stop_all()
                
        elif command == "status":
            # 상태 조회
            status = manager.get_status()
            print(f"시스템 상태: {'실행 중' if status['system_running'] else '중지됨'}")
            print(f"봇 상태: {status['bot_status']}")
            print(f"대시보드 상태: {status['dashboard_status']}")
            
        else:
            print("사용법: python main.py [bot|dashboard|status]")
            print("  bot      : 봇만 실행")
            print("  dashboard: 대시보드만 실행")  
            print("  status   : 상태 조회")
            print("  (인수 없음): 봇 + 대시보드 모두 실행")
    else:
        # 전체 시스템 실행
        manager.start_all()
        if manager.is_running:
            manager.monitor()

if __name__ == "__main__":
    # Windows에서 multiprocessing 오류 방지
    if os.name == 'nt':
        multiprocessing.freeze_support()
    
    main()
