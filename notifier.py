"""
텔레그램 알림 기능 모듈
"""
import os
import asyncio
import logging
from datetime import datetime
from typing import Optional
import requests
from telegram import Bot
from telegram.error import TelegramError

logger = logging.getLogger(__name__)

class TelegramNotifier:
    """텔레그램 알림 클래스"""
    
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.bot = Bot(token=bot_token)
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        
    def send_message_sync(self, message: str) -> bool:
        """동기 방식으로 메시지 전송 (requests 사용)"""
        try:
            url = f"{self.base_url}/sendMessage"
            data = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            
            response = requests.post(url, data=data, timeout=10)
            response.raise_for_status()
            
            logger.info(f"텔레그램 메시지 전송 성공")
            return True
            
        except Exception as e:
            logger.error(f"텔레그램 메시지 전송 실패: {e}")
            return False
    
    async def send_message_async(self, message: str) -> bool:
        """비동기 방식으로 메시지 전송"""
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='HTML'
            )
            logger.info("텔레그램 메시지 전송 성공 (비동기)")
            return True
            
        except TelegramError as e:
            logger.error(f"텔레그램 메시지 전송 실패 (비동기): {e}")
            return False
    
    def send_buy_notification(self, market: str, price: float, amount: float, 
                             reason: str = "") -> bool:
        """매수 알림"""
        coin_name = market.replace('KRW-', '')
        message = f"""
🟢 <b>매수 알림</b>
━━━━━━━━━━━━━━━━━━━━
💰 종목: <b>{coin_name}</b>
💵 가격: <b>{price:,.0f}원</b>
💸 금액: <b>{amount:,.0f}원</b>
📊 사유: {reason}
⏰ 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
━━━━━━━━━━━━━━━━━━━━
        """.strip()
        
        return self.send_message_sync(message)
    
    def send_sell_notification(self, market: str, price: float, amount: float,
                              profit_loss: float, profit_rate: float, 
                              reason: str = "") -> bool:
        """매도 알림"""
        coin_name = market.replace('KRW-', '')
        profit_emoji = "🔴" if profit_loss < 0 else "🟢"
        profit_text = "손실" if profit_loss < 0 else "수익"
        
        message = f"""
{profit_emoji} <b>매도 알림</b>
━━━━━━━━━━━━━━━━━━━━
💰 종목: <b>{coin_name}</b>
💵 가격: <b>{price:,.0f}원</b>
💸 금액: <b>{amount:,.0f}원</b>
📈 {profit_text}: <b>{profit_loss:,.0f}원 ({profit_rate:+.2f}%)</b>
📊 사유: {reason}
⏰ 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
━━━━━━━━━━━━━━━━━━━━
        """.strip()
        
        return self.send_message_sync(message)
    
    def send_daily_summary(self, total_pnl: float, trade_count: int, 
                          win_rate: float, positions: int) -> bool:
        """일일 요약 알림"""
        pnl_emoji = "🔴" if total_pnl < 0 else "🟢"
        pnl_text = "손실" if total_pnl < 0 else "수익"
        
        message = f"""
📊 <b>일일 거래 요약</b>
━━━━━━━━━━━━━━━━━━━━
{pnl_emoji} 총 {pnl_text}: <b>{total_pnl:,.0f}원</b>
🔢 거래 횟수: <b>{trade_count}회</b>
🎯 승률: <b>{win_rate:.1f}%</b>
📋 현재 포지션: <b>{positions}개</b>
⏰ 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
━━━━━━━━━━━━━━━━━━━━
        """.strip()
        
        return self.send_message_sync(message)
    
    def send_error_notification(self, error_type: str, error_message: str) -> bool:
        """에러 알림"""
        message = f"""
🚨 <b>시스템 오류</b>
━━━━━━━━━━━━━━━━━━━━
⚠️ 유형: <b>{error_type}</b>
📝 내용: {error_message}
⏰ 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
━━━━━━━━━━━━━━━━━━━━
        """.strip()
        
        return self.send_message_sync(message)
    
    def send_bot_status(self, status: str, message: str = "") -> bool:
        """봇 상태 알림"""
        status_emoji = {
            "started": "🟢",
            "stopped": "🔴", 
            "paused": "🟡",
            "error": "🚨"
        }
        
        emoji = status_emoji.get(status, "ℹ️")
        
        notification = f"""
{emoji} <b>CoinButler 상태</b>
━━━━━━━━━━━━━━━━━━━━
📊 상태: <b>{status.upper()}</b>
📝 메시지: {message}
⏰ 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
━━━━━━━━━━━━━━━━━━━━
        """.strip()
        
        return self.send_message_sync(notification)
    
    def send_daily_loss_limit_alert(self, current_loss: float, limit: float) -> bool:
        """일일 손실 한도 초과 알림"""
        message = f"""
🚨 <b>일일 손실 한도 초과!</b>
━━━━━━━━━━━━━━━━━━━━
💸 현재 손실: <b>{current_loss:,.0f}원</b>
⚠️ 설정 한도: <b>{limit:,.0f}원</b>
🛑 거래 중단됨
⏰ 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
━━━━━━━━━━━━━━━━━━━━
🔄 내일 자정에 자동으로 거래가 재개됩니다.
        """.strip()
        
        return self.send_message_sync(message)
    
    def send_volume_spike_alert(self, market: str, volume_ratio: float, 
                               price_change: float) -> bool:
        """거래량 급등 감지 알림"""
        coin_name = market.replace('KRW-', '')
        
        message = f"""
🚀 <b>거래량 급등 감지!</b>
━━━━━━━━━━━━━━━━━━━━
💰 종목: <b>{coin_name}</b>
📊 거래량 증가: <b>{volume_ratio:.1f}배</b>
📈 가격 변동: <b>{price_change:+.2f}%</b>
⏰ 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
━━━━━━━━━━━━━━━━━━━━
        """.strip()
        
        return self.send_message_sync(message)
    
    def test_connection(self) -> bool:
        """텔레그램 연결 테스트"""
        test_message = f"""
🔧 <b>CoinButler 연결 테스트</b>
━━━━━━━━━━━━━━━━━━━━
✅ 텔레그램 연결이 정상적으로 작동합니다.
⏰ 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
━━━━━━━━━━━━━━━━━━━━
        """.strip()
        
        return self.send_message_sync(test_message)

def get_telegram_notifier() -> Optional[TelegramNotifier]:
    """환경 변수에서 텔레그램 알림기 인스턴스 생성"""
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    if not bot_token or not chat_id:
        logger.warning("텔레그램 설정이 없습니다. 알림 기능이 비활성화됩니다.")
        return None
    
    notifier = TelegramNotifier(bot_token, chat_id)
    
    # 연결 테스트
    if not notifier.test_connection():
        logger.error("텔레그램 연결 테스트 실패")
        return None
    
    return notifier

# 전역 알림기 인스턴스
_notifier: Optional[TelegramNotifier] = None

def init_notifier():
    """전역 알림기 초기화"""
    global _notifier
    _notifier = get_telegram_notifier()

def notify_buy(market: str, price: float, amount: float, reason: str = ""):
    """매수 알림 전송"""
    if _notifier:
        _notifier.send_buy_notification(market, price, amount, reason)

def notify_sell(market: str, price: float, amount: float, profit_loss: float, 
               profit_rate: float, reason: str = ""):
    """매도 알림 전송"""
    if _notifier:
        _notifier.send_sell_notification(market, price, amount, profit_loss, profit_rate, reason)

def notify_error(error_type: str, error_message: str):
    """에러 알림 전송"""
    if _notifier:
        _notifier.send_error_notification(error_type, error_message)

def notify_bot_status(status: str, message: str = ""):
    """봇 상태 알림 전송"""
    if _notifier:
        _notifier.send_bot_status(status, message)

def notify_daily_loss_limit(current_loss: float, limit: float):
    """일일 손실 한도 초과 알림 전송"""
    if _notifier:
        _notifier.send_daily_loss_limit_alert(current_loss, limit)

def notify_volume_spike(market: str, volume_ratio: float, price_change: float):
    """거래량 급등 감지 알림 전송"""
    if _notifier:
        _notifier.send_volume_spike_alert(market, volume_ratio, price_change)
