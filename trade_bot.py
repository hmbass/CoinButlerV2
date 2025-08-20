"""
코인 자동매매 봇의 핵심 로직
"""
import os
import time
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import openai
from dotenv import load_dotenv

from trade_utils import UpbitAPI, MarketAnalyzer, get_upbit_api
from risk_manager import RiskManager, get_risk_manager
from notifier import (
    init_notifier, notify_buy, notify_sell, notify_error, 
    notify_bot_status, notify_daily_loss_limit, notify_volume_spike
)

# 환경변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('coinbutler.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AIAnalyzer:
    """ChatGPT를 이용한 종목 분석기"""
    
    def __init__(self, api_key: str):
        self.client = openai.OpenAI(api_key=api_key)
        
    def analyze_market_condition(self, market_data: List[Dict]) -> Dict[str, any]:
        """시장 상황을 분석하여 매수할 종목 추천"""
        try:
            # 거래량 급등 종목들의 정보를 텍스트로 정리
            market_info = []
            for data in market_data[:10]:  # 상위 10개만 분석
                market_info.append(
                    f"- {data['market']}: 거래량 {data['volume_ratio']:.1f}배 증가, "
                    f"가격변동 {data['price_change']:+.2f}%, 현재가 {data['current_price']:,.0f}원"
                )
            
            market_text = "\n".join(market_info)
            
            prompt = f"""
당신은 암호화폐 거래 전문가입니다. 
다음은 최근 거래량이 급등한 코인들의 정보입니다:

{market_text}

다음 기준을 고려하여 가장 매수하기 좋은 1개 종목을 추천해주세요:
1. 거래량 급등의 지속 가능성
2. 기술적 분석 관점에서의 상승 여력
3. 리스크 대비 수익 가능성
4. 현재 시장 트렌드와의 부합성

응답 형식:
{{
  "recommended_coin": "추천 코인명 (예: BTC, ETH)",
  "confidence": 신뢰도 (1-10),
  "reason": "추천 이유 (한 줄로)",
  "risk_level": "HIGH/MEDIUM/LOW"
}}

JSON 형식으로만 응답해주세요.
            """
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "당신은 암호화폐 거래 전문가입니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=200
            )
            
            # JSON 응답 파싱
            import json
            result = json.loads(response.choices[0].message.content)
            logger.info(f"AI 분석 결과: {result}")
            
            return result
            
        except Exception as e:
            logger.error(f"AI 분석 실패: {e}")
            return {
                "recommended_coin": None,
                "confidence": 0,
                "reason": "분석 실패",
                "risk_level": "HIGH"
            }

class CoinButler:
    """코인 자동매매 봇 메인 클래스"""
    
    def __init__(self):
        # API 인스턴스 초기화
        self.upbit_api = get_upbit_api()
        self.market_analyzer = MarketAnalyzer(self.upbit_api)
        self.risk_manager = get_risk_manager()
        
        # AI 분석기 초기화
        openai_key = os.getenv('OPENAI_API_KEY')
        self.ai_analyzer = AIAnalyzer(openai_key) if openai_key else None
        
        # 설정값 로드
        self.investment_amount = float(os.getenv('INVESTMENT_AMOUNT', 100000))
        self.profit_rate = float(os.getenv('PROFIT_RATE', 0.03))
        self.loss_rate = float(os.getenv('LOSS_RATE', -0.02))
        self.volume_spike_threshold = float(os.getenv('VOLUME_SPIKE_THRESHOLD', 2.0))
        self.price_change_threshold = float(os.getenv('PRICE_CHANGE_THRESHOLD', 0.05))
        self.check_interval = int(os.getenv('CHECK_INTERVAL', 60))
        
        # 상태 변수
        self.is_running = False
        self.is_paused = False
        self.last_market_scan = datetime.now() - timedelta(minutes=10)
        
        # 텔레그램 알림 초기화
        init_notifier()
        
    def start(self):
        """봇 시작"""
        if self.is_running:
            logger.warning("봇이 이미 실행 중입니다.")
            return
        
        self.is_running = True
        self.is_paused = False
        
        logger.info("🚀 CoinButler 시작!")
        notify_bot_status("started", "자동매매 봇이 시작되었습니다.")
        
        # 초기 잔고 확인
        krw_balance = self.upbit_api.get_krw_balance()
        logger.info(f"현재 KRW 잔고: {krw_balance:,.0f}원")
        
        if krw_balance < self.investment_amount:
            error_msg = f"잔고 부족! 현재: {krw_balance:,.0f}원, 필요: {self.investment_amount:,.0f}원"
            logger.error(error_msg)
            notify_error("잔고 부족", error_msg)
            self.stop()
            return
        
        # 메인 루프 시작
        self._main_loop()
    
    def stop(self):
        """봇 중지"""
        self.is_running = False
        logger.info("🛑 CoinButler 중지!")
        notify_bot_status("stopped", "자동매매 봇이 중지되었습니다.")
    
    def pause(self):
        """봇 일시정지"""
        self.is_paused = True
        logger.info("⏸️ CoinButler 일시정지!")
        notify_bot_status("paused", "자동매매 봇이 일시정지되었습니다.")
    
    def resume(self):
        """봇 재개"""
        self.is_paused = False
        logger.info("▶️ CoinButler 재개!")
        notify_bot_status("started", "자동매매 봇이 재개되었습니다.")
    
    def _main_loop(self):
        """메인 거래 루프"""
        try:
            while self.is_running:
                if self.is_paused:
                    time.sleep(self.check_interval)
                    continue
                
                # 일일 손실 한도 체크
                if self.risk_manager.check_daily_loss_limit():
                    daily_pnl = self.risk_manager.get_daily_pnl()
                    notify_daily_loss_limit(daily_pnl, self.risk_manager.daily_loss_limit)
                    self.pause()
                    continue
                
                # 기존 포지션 관리 (매도 조건 체크)
                self._manage_positions()
                
                # 새로운 매수 기회 탐색 (5분마다)
                if datetime.now() - self.last_market_scan > timedelta(minutes=5):
                    self._scan_for_opportunities()
                    self.last_market_scan = datetime.now()
                
                time.sleep(self.check_interval)
                
        except KeyboardInterrupt:
            logger.info("사용자에 의한 중단")
        except Exception as e:
            logger.error(f"메인 루프 오류: {e}")
            notify_error("시스템 오류", str(e))
        finally:
            self.stop()
    
    def _manage_positions(self):
        """기존 포지션 관리 (매도 조건 체크)"""
        open_positions = self.risk_manager.get_open_positions()
        
        for market, position in open_positions.items():
            try:
                current_price = self.upbit_api.get_current_price(market)
                if not current_price:
                    continue
                
                # 매도 조건 확인
                should_sell, reason = self.risk_manager.should_sell(
                    market, current_price, self.profit_rate, self.loss_rate
                )
                
                if should_sell:
                    self._execute_sell(market, current_price, reason)
                else:
                    # 현재 손익 로깅
                    pnl_info = self.risk_manager.get_position_pnl(market, current_price)
                    if pnl_info:
                        pnl, pnl_rate = pnl_info
                        logger.info(f"{market} 현재 손익: {pnl:,.0f}원 ({pnl_rate:+.2f}%)")
                        
            except Exception as e:
                logger.error(f"포지션 관리 오류 ({market}): {e}")
    
    def _scan_for_opportunities(self):
        """새로운 매수 기회 탐색"""
        if not self.risk_manager.can_open_position():
            logger.info("최대 포지션 수 도달로 인한 매수 스킵")
            return
        
        try:
            logger.info("🔍 매수 기회 탐색 중...")
            
            # 거래 가능한 마켓 조회
            markets = self.market_analyzer.get_tradeable_markets()
            spike_candidates = []
            
            # 거래량 급등 종목 찾기
            for market in markets[:30]:  # 상위 30개만 체크
                try:
                    if self.market_analyzer.detect_volume_spike(market, self.volume_spike_threshold):
                        current_price = self.upbit_api.get_current_price(market)
                        price_change = self.market_analyzer.get_price_change(market)
                        
                        if current_price and price_change is not None:
                            # 가격 급등/급락 필터링 (너무 큰 변동은 위험)
                            if abs(price_change) < self.price_change_threshold:
                                spike_candidates.append({
                                    'market': market,
                                    'current_price': current_price,
                                    'price_change': price_change,
                                    'volume_ratio': self.volume_spike_threshold
                                })
                                
                                # 거래량 급등 알림
                                notify_volume_spike(market, self.volume_spike_threshold, price_change)
                                
                except Exception as e:
                    logger.error(f"시장 스캔 오류 ({market}): {e}")
                    continue
            
            if not spike_candidates:
                logger.info("거래량 급등 종목 없음")
                return
            
            logger.info(f"거래량 급등 감지: {len(spike_candidates)}개 종목")
            
            # AI 분석 (옵션)
            best_candidate = spike_candidates[0]  # 기본값: 첫 번째 후보
            
            if self.ai_analyzer and len(spike_candidates) > 1:
                ai_result = self.ai_analyzer.analyze_market_condition(spike_candidates)
                
                if ai_result.get('recommended_coin') and ai_result.get('confidence', 0) >= 6:
                    # AI 추천 종목 찾기
                    recommended_market = f"KRW-{ai_result['recommended_coin']}"
                    for candidate in spike_candidates:
                        if candidate['market'] == recommended_market:
                            best_candidate = candidate
                            logger.info(f"AI 추천 종목 선택: {recommended_market}")
                            break
            
            # 매수 실행
            self._execute_buy(best_candidate)
            
        except Exception as e:
            logger.error(f"매수 기회 탐색 오류: {e}")
            notify_error("매수 탐색 오류", str(e))
    
    def _execute_buy(self, candidate: Dict):
        """매수 실행"""
        market = candidate['market']
        current_price = candidate['current_price']
        
        try:
            # 현재 잔고 확인
            krw_balance = self.upbit_api.get_krw_balance()
            if krw_balance < self.investment_amount:
                logger.warning(f"잔고 부족으로 매수 스킵: {market}")
                return
            
            # 매수 주문 실행
            order_result = self.upbit_api.place_buy_order(market, self.investment_amount)
            if not order_result:
                logger.error(f"매수 주문 실패: {market}")
                return
            
            # 주문 완료까지 대기 및 확인
            time.sleep(3)
            order_info = self.upbit_api.get_order_info(order_result['uuid'])
            
            if order_info and order_info.get('state') == 'done':
                # 실제 체결된 수량과 평균가 계산
                executed_volume = float(order_info.get('executed_volume', 0))
                avg_price = float(order_info.get('avg_price', current_price))
                
                if executed_volume > 0:
                    # 포지션 추가
                    success = self.risk_manager.add_position(
                        market=market,
                        entry_price=avg_price,
                        quantity=executed_volume,
                        investment_amount=self.investment_amount
                    )
                    
                    if success:
                        # 매수 알림
                        reason = f"거래량 {candidate.get('volume_ratio', 0):.1f}배 급등"
                        notify_buy(market, avg_price, self.investment_amount, reason)
                        logger.info(f"✅ 매수 완료: {market}, 가격: {avg_price:,.0f}, 수량: {executed_volume}")
                    else:
                        logger.error(f"포지션 추가 실패: {market}")
                else:
                    logger.error(f"체결 수량 0: {market}")
            else:
                logger.error(f"주문 체결 확인 실패: {market}")
                
        except Exception as e:
            logger.error(f"매수 실행 오류 ({market}): {e}")
            notify_error("매수 실행 오류", f"{market}: {str(e)}")
    
    def _execute_sell(self, market: str, current_price: float, reason: str):
        """매도 실행"""
        try:
            position = self.risk_manager.positions.get(market)
            if not position or position.status != "open":
                logger.warning(f"매도할 포지션 없음: {market}")
                return
            
            # 매도 주문 실행
            order_result = self.upbit_api.place_sell_order(market, position.quantity)
            if not order_result:
                logger.error(f"매도 주문 실패: {market}")
                return
            
            # 주문 완료까지 대기
            time.sleep(3)
            order_info = self.upbit_api.get_order_info(order_result['uuid'])
            
            if order_info and order_info.get('state') == 'done':
                avg_price = float(order_info.get('avg_price', current_price))
                
                # 포지션 종료 및 손익 계산
                profit_loss = self.risk_manager.close_position(market, avg_price)
                
                if profit_loss is not None:
                    profit_rate = (profit_loss / position.investment_amount) * 100
                    
                    # 매도 알림
                    notify_sell(market, avg_price, position.quantity * avg_price, 
                               profit_loss, profit_rate, reason)
                    
                    logger.info(f"✅ 매도 완료: {market}, 가격: {avg_price:,.0f}, "
                               f"손익: {profit_loss:,.0f}원 ({profit_rate:+.2f}%)")
                else:
                    logger.error(f"포지션 종료 실패: {market}")
            else:
                logger.error(f"매도 주문 체결 확인 실패: {market}")
                
        except Exception as e:
            logger.error(f"매도 실행 오류 ({market}): {e}")
            notify_error("매도 실행 오류", f"{market}: {str(e)}")
    
    def get_status(self) -> Dict:
        """봇 현재 상태 반환"""
        return {
            'is_running': self.is_running,
            'is_paused': self.is_paused,
            'krw_balance': self.upbit_api.get_krw_balance(),
            'positions': self.risk_manager.get_position_summary(),
            'daily_pnl': self.risk_manager.get_daily_pnl(),
            'trading_stats': self.risk_manager.get_trading_stats()
        }

# 전역 봇 인스턴스
_bot: Optional[CoinButler] = None

def get_bot() -> CoinButler:
    """전역 봇 인스턴스 반환"""
    global _bot
    if _bot is None:
        _bot = CoinButler()
    return _bot

def main():
    """메인 실행 함수"""
    bot = get_bot()
    
    try:
        bot.start()
    except KeyboardInterrupt:
        logger.info("사용자 중단")
    except Exception as e:
        logger.error(f"실행 오류: {e}")
        notify_error("시스템 오류", str(e))
    finally:
        bot.stop()

if __name__ == "__main__":
    main()
