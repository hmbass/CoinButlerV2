#!/usr/bin/env python3
"""
텔레그램 알림 기능 테스트 스크립트
"""
import os
import sys
import logging
from dotenv import load_dotenv
from notifier import init_notifier, notify_buy, notify_sell

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """텔레그램 알림 테스트"""
    print("🔧 CoinButler 텔레그램 알림 테스트")
    print("=" * 50)
    
    # 환경변수 로드
    load_dotenv()
    
    # 환경변수 확인
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    print(f"📋 환경변수 확인:")
    print(f"   TELEGRAM_BOT_TOKEN: {'✅ 설정됨' if bot_token else '❌ 설정되지 않음'}")
    print(f"   TELEGRAM_CHAT_ID: {'✅ 설정됨' if chat_id else '❌ 설정되지 않음'}")
    print()
    
    if not bot_token or not chat_id:
        print("❌ 텔레그램 환경변수가 설정되지 않았습니다.")
        print("💡 .env 파일에 다음 설정을 추가하세요:")
        print("   TELEGRAM_BOT_TOKEN=your_bot_token")
        print("   TELEGRAM_CHAT_ID=your_chat_id")
        print()
        print("📚 텔레그램 봇 설정 방법:")
        print("   1. @BotFather에게 /newbot 명령으로 봇 생성")
        print("   2. 받은 토큰을 TELEGRAM_BOT_TOKEN에 설정")
        print("   3. 봇에게 메시지를 보낸 후 Chat ID 확인")
        print("   4. Chat ID를 TELEGRAM_CHAT_ID에 설정")
        sys.exit(1)
    
    # 알림 시스템 초기화
    print("📱 텔레그램 알림 시스템 초기화 중...")
    init_notifier()
    print()
    
    # 연결 테스트 완료 후 실제 거래 알림 테스트
    print("🧪 거래 알림 테스트 중...")
    
    # 매수 알림 테스트
    print("   📈 매수 알림 테스트...")
    notify_buy(
        market="KRW-BTC",
        price=50000000,
        amount=30000,
        reason="테스트 매수 (거래량 2.5배 급등)"
    )
    
    # 매도 알림 테스트 (수익)
    print("   📉 매도 알림 테스트 (수익)...")
    notify_sell(
        market="KRW-BTC",
        price=51500000,
        amount=30000,
        profit_loss=900,
        profit_rate=3.0,
        reason="테스트 매도 (목표 수익률 달성)"
    )
    
    # 매도 알림 테스트 (손실)
    print("   📉 매도 알림 테스트 (손실)...")
    notify_sell(
        market="KRW-ETH",
        price=2900000,
        amount=30000,
        profit_loss=-600,
        profit_rate=-2.0,
        reason="테스트 손절매 (손절률 도달)"
    )
    
    print()
    print("✅ 텔레그램 알림 테스트 완료!")
    print("📱 텔레그램에서 메시지가 도착했는지 확인해주세요.")

if __name__ == "__main__":
    main()
