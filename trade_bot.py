"""
코인 자동매매 봇의 핵심 로직
"""
import os
import time
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import google.generativeai as genai
from dotenv import load_dotenv

from trade_utils import UpbitAPI, MarketAnalyzer, get_upbit_api
from risk_manager import RiskManager, get_risk_manager
from notifier import (
    init_notifier, notify_buy, notify_sell
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
    """Google Gemini를 이용한 종목 분석기"""
    
    def __init__(self, api_key: str):
        if api_key:
            try:
                genai.configure(api_key=api_key)
                # 최신 모델명으로 변경: gemini-pro → gemini-1.5-flash
                self.model = genai.GenerativeModel('gemini-1.5-flash')
                self.enabled = True
                logger.info("Gemini AI 모델(gemini-1.5-flash)이 성공적으로 초기화되었습니다.")
            except Exception as e:
                logger.error(f"Gemini AI 초기화 실패: {e}")
                # 대체 모델 시도
                try:
                    self.model = genai.GenerativeModel('gemini-1.5-pro')
                    self.enabled = True
                    logger.info("대체 모델(gemini-1.5-pro)로 초기화 완료")
                except:
                    logger.error("모든 Gemini 모델 초기화 실패")
                    self.enabled = False
        else:
            self.enabled = False
        
    def analyze_market_condition(self, market_data: List[Dict]) -> Dict[str, any]:
        """시장 상황을 분석하여 매수할 종목 추천"""
        if not self.enabled:
            logger.info("Gemini API 키가 없어서 AI 분석을 건너뜁니다.")
            return {
                "recommended_coin": None,
                "confidence": 0,
                "reason": "AI 분석 비활성화",
                "risk_level": "MEDIUM"
            }
        
        try:
            # 거래량 급등 종목들의 정보를 텍스트로 정리
            market_info = []
            for data in market_data[:3]:  # 상위 3개만 분석 (Gemini는 더 관대함)
                market_info.append(
                    f"- {data['market']}: 거래량 {data.get('volume_ratio', 2.0):.1f}배 증가, "
                    f"가격변동 {data['price_change']:+.2f}%, 현재가 {data['current_price']:,.0f}원"
                )
            
            market_text = "\n".join(market_info)
            
            prompt = f"""
암호화폐 거래 전문가로서 다음 거래량 급등 종목들을 분석하고 가장 매수하기 좋은 1개를 추천해주세요:

{market_text}

다음 JSON 형식으로만 응답해주세요:
{{
  "recommended_coin": "BTC",
  "confidence": 8,
  "reason": "추천 이유를 한 줄로",
  "risk_level": "LOW"
}}

기준:
1. 거래량 증가의 지속성
2. 기술적 분석 상승 여력  
3. 리스크 대비 수익성
4. 현재 시장 상황

JSON만 출력하세요.
            """
            
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            # JSON 부분만 추출 (```json 태그 제거)
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            
            # JSON 파싱
            import json
            result = json.loads(response_text)
            logger.info(f"Gemini AI 분석 결과: {result}")
            
            return result
            
        except genai.types.BrokenResponseError as e:
            logger.error(f"Gemini AI 응답 파싱 오류: {e}")
            return {
                "recommended_coin": None,
                "confidence": 0,
                "reason": "AI 응답 파싱 실패",
                "risk_level": "HIGH"
            }
        except Exception as e:
            logger.error(f"Gemini AI 분석 실패: {e}")
            # 첫 번째 종목을 기본값으로 반환
            if market_data:
                first_coin = market_data[0]['market'].replace('KRW-', '')
                return {
                    "recommended_coin": first_coin,
                    "confidence": 5,
                    "reason": "AI 분석 실패로 첫 번째 종목 선택",
                    "risk_level": "MEDIUM"
                }
            return {
                "recommended_coin": None,
                "confidence": 0,
                "reason": "AI 분석 실패",
                "risk_level": "HIGH"
            }
    
    def analyze_position_amount(self, market_data: Dict, krw_balance: float, 
                              current_positions: int, max_positions: int) -> Dict[str, any]:
        """분할매수 금액 결정을 위한 AI 분석"""
        if not self.enabled:
            return {
                "investment_amount": min(30000, krw_balance * 0.8),
                "reason": "AI 분석 비활성화 - 기본 금액 사용",
                "split_ratio": 1.0
            }
        
        try:
            market = market_data.get('market', '')
            current_price = market_data.get('current_price', 0)
            volume_ratio = market_data.get('volume_ratio', 2.0)
            price_change = market_data.get('price_change', 0)
            
            available_balance = krw_balance
            remaining_slots = max_positions - current_positions
            
            prompt = f"""
암호화폐 분할매수 전문가로서 다음 정보를 바탕으로 최적의 투자 금액을 결정해주세요:

**종목 정보:**
- 종목: {market}
- 현재가: {current_price:,.0f}원
- 거래량 증가: {volume_ratio:.1f}배
- 가격 변동: {price_change:+.2f}%

**계정 정보:**
- 사용 가능 잔고: {available_balance:,.0f}원
- 현재 보유 포지션: {current_positions}개
- 남은 포지션 슬롯: {remaining_slots}개

다음 JSON 형식으로만 응답해주세요:
{{
  "investment_amount": 25000,
  "split_ratio": 0.8,
  "reason": "분할매수 결정 이유",
  "risk_assessment": "LOW"
}}

분할매수 기준:
1. 거래량 급등이 클수록 더 큰 금액 투자
2. 잔고의 60-80% 내에서 결정
3. 남은 포지션 슬롯을 고려한 분산 투자
4. 변동성이 높으면 작은 금액으로 시작

JSON만 출력하세요.
            """
            
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            # JSON 부분 추출
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            
            import json
            result = json.loads(response_text)
            
            # 안전 검증
            investment_amount = min(result.get('investment_amount', 30000), available_balance * 0.8)
            investment_amount = max(investment_amount, 10000)  # 최소 1만원
            
            result['investment_amount'] = investment_amount
            logger.info(f"Gemini 분할매수 분석: {investment_amount:,.0f}원 ({result.get('split_ratio', 1.0):.1f} 비율)")
            
            return result
            
        except Exception as e:
            logger.error(f"분할매수 AI 분석 실패: {e}")
            return {
                "investment_amount": min(30000, krw_balance * 0.7),
                "reason": "AI 분석 실패로 기본 금액 사용",
                "split_ratio": 0.7,
                "risk_assessment": "MEDIUM"
            }
    
    def analyze_position_swap(self, losing_positions: List[Dict], market_opportunities: List[Dict]) -> Dict[str, any]:
        """손절매수 전환 분석 - 마이너스 포지션을 더 나은 종목으로 교체"""
        if not self.enabled:
            return {
                "should_swap": False,
                "reason": "AI 분석 비활성화",
                "sell_market": None,
                "buy_market": None
            }
        
        if not losing_positions or not market_opportunities:
            return {
                "should_swap": False,
                "reason": "손실 포지션이나 매수 기회가 없음",
                "sell_market": None,
                "buy_market": None
            }
        
        try:
            # 손실 포지션 정보 정리
            losing_info = []
            for pos in losing_positions:
                days_held = (datetime.now() - datetime.fromisoformat(pos['entry_time'])).days
                losing_info.append(
                    f"- {pos['market']}: 손실률 {pos['pnl_rate']:.2f}%, "
                    f"보유 {days_held}일, 손실액 {pos['pnl']:,.0f}원"
                )
            
            # 매수 기회 정리
            opportunity_info = []
            for opp in market_opportunities[:3]:
                opportunity_info.append(
                    f"- {opp['market']}: 거래량 {opp.get('volume_ratio', 2.0):.1f}배, "
                    f"가격변동 {opp['price_change']:+.2f}%"
                )
            
            prompt = f"""
암호화폐 포지션 최적화 전문가로서 손절 후 재투자 여부를 결정해주세요.

**현재 손실 포지션들:**
{chr(10).join(losing_info)}

**새로운 매수 기회들:**
{chr(10).join(opportunity_info)}

다음 JSON 형식으로만 응답해주세요:
{{
  "should_swap": true,
  "sell_market": "KRW-BTC",
  "buy_market": "KRW-ETH",
  "confidence": 8,
  "reason": "포지션 교체 결정 이유",
  "expected_recovery_days": 3
}}

판단 기준:
1. 손실 포지션이 1일 이상 보유되고 -5% 이상 손실
2. 새로운 기회의 상승 가능성이 현재 포지션보다 높음
3. 거래량 급등 강도와 기술적 지표 고려
4. 손절 손실보다 새 투자 수익 예상이 클 때만 교체

교체하지 않으면 should_swap: false로 설정하세요.
JSON만 출력하세요.
            """
            
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            # JSON 부분 추출
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            
            import json
            result = json.loads(response_text)
            
            logger.info(f"Gemini 포지션 교체 분석: {result.get('should_swap', False)} - {result.get('reason', '')}")
            return result
            
        except Exception as e:
            logger.error(f"포지션 교체 AI 분석 실패: {e}")
            return {
                "should_swap": False,
                "reason": "AI 분석 실패",
                "sell_market": None,
                "buy_market": None
            }

class CoinButler:
    """코인 자동매매 봇 메인 클래스"""
    
    def __init__(self):
        # API 인스턴스 초기화
        self.upbit_api = get_upbit_api()
        self.market_analyzer = MarketAnalyzer(self.upbit_api)
        self.risk_manager = get_risk_manager()
        
        # AI 분석기 초기화 (Google Gemini)
        gemini_key = os.getenv('GEMINI_API_KEY')
        self.ai_analyzer = AIAnalyzer(gemini_key) if gemini_key else None
        
        # 설정값 로드
        self.investment_amount = float(os.getenv('INVESTMENT_AMOUNT', 30000))
        self.profit_rate = float(os.getenv('PROFIT_RATE', 0.03))
        self.loss_rate = float(os.getenv('LOSS_RATE', -0.02))
        self.volume_spike_threshold = float(os.getenv('VOLUME_SPIKE_THRESHOLD', 2.0))
        self.price_change_threshold = float(os.getenv('PRICE_CHANGE_THRESHOLD', 0.05))
        self.check_interval = int(os.getenv('CHECK_INTERVAL', 60))
        
        # 상태 변수
        self.is_running = False
        self.is_paused = False
        self.last_market_scan = datetime.now() - timedelta(minutes=10)
        self.last_balance_check = datetime.now() - timedelta(minutes=30)
        
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
        
        # 기존 포지션 복원 시도
        self._restore_existing_positions()
        
        # 초기 잔고 확인
        krw_balance = self.upbit_api.get_krw_balance()
        logger.info(f"현재 KRW 잔고: {krw_balance:,.0f}원")
        
        if krw_balance < self.investment_amount:
            warning_msg = f"⚠️ 잔고 부족! 현재: {krw_balance:,.0f}원, 필요: {self.investment_amount:,.0f}원"
            logger.warning(warning_msg)
            logger.info("잔고가 부족하지만 봇은 계속 실행됩니다. 매수는 잔고가 충분할 때만 실행됩니다.")
        
        # 메인 루프 시작 (잔고 부족 시에도 실행)
        self._main_loop()
    
    def stop(self):
        """봇 중지"""
        self.is_running = False
        logger.info("🛑 CoinButler 중지!")
    
    def pause(self):
        """봇 일시정지"""
        self.is_paused = True
        logger.info("⏸️ CoinButler 일시정지!")
    
    def resume(self):
        """봇 재개"""
        self.is_paused = False
        logger.info("▶️ CoinButler 재개!")
    
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
                    logger.warning(f"일일 손실 한도 초과! 현재: {daily_pnl:,.0f}원, 한도: {self.risk_manager.daily_loss_limit:,.0f}원")
                    self.pause()
                    continue
                
                # 기존 포지션 관리 (매도 조건 체크)
                self._manage_positions()
                
                # 잔고 상태 주기적 체크 (30분마다)
                if datetime.now() - self.last_balance_check > timedelta(minutes=30):
                    self._check_balance_status()
                    self.last_balance_check = datetime.now()
                
                # 새로운 매수 기회 탐색 (10분마다로 주기 확장)
                if datetime.now() - self.last_market_scan > timedelta(minutes=10):
                    self._scan_for_opportunities()
                    self.last_market_scan = datetime.now()
                
                time.sleep(self.check_interval)
                
        except KeyboardInterrupt:
            logger.info("사용자에 의한 중단")
        except Exception as e:
            logger.error(f"메인 루프 오류: {e}")
        finally:
            self.stop()
    
    def _manage_positions(self):
        """기존 포지션 관리 (매도 조건 체크 및 포지션 교체 분석)"""
        open_positions = self.risk_manager.get_open_positions()
        losing_positions = []  # 손실 포지션 수집
        
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
                        
                        # 손실 포지션 수집 (포지션 교체 분석용)
                        if pnl_rate < -5.0:  # -5% 이상 손실
                            entry_time = position.get('entry_time', datetime.now().isoformat())
                            try:
                                days_held = (datetime.now() - datetime.fromisoformat(entry_time)).days
                                if days_held >= 1:  # 1일 이상 보유
                                    losing_positions.append({
                                        'market': market,
                                        'entry_price': position['entry_price'],
                                        'current_price': current_price,
                                        'pnl_rate': pnl_rate,
                                        'pnl': pnl,
                                        'entry_time': entry_time,
                                        'days_held': days_held,
                                        'position': position
                                    })
                            except:
                                pass  # 날짜 파싱 실패시 스킵
                        
            except Exception as e:
                logger.error(f"포지션 관리 오류 ({market}): {e}")
        
        # 손실 포지션이 있고 AI가 활성화된 경우 교체 분석 (5분마다만)
        if (losing_positions and 
            self.ai_analyzer and 
            self.ai_analyzer.enabled and 
            hasattr(self, 'last_swap_check') and
            datetime.now() - self.last_swap_check > timedelta(minutes=5)):
            
            self._analyze_position_swap(losing_positions)
            self.last_swap_check = datetime.now()
        elif not hasattr(self, 'last_swap_check'):
            self.last_swap_check = datetime.now()
    
    def _check_balance_status(self):
        """잔고 상태 체크 및 정보 제공"""
        try:
            krw_balance = self.upbit_api.get_krw_balance()
            
            if krw_balance >= self.investment_amount:
                logger.info(f"💰 잔고 상태: 양호 ({krw_balance:,.0f}원 / {self.investment_amount:,.0f}원 필요)")
            else:
                shortage = self.investment_amount - krw_balance
                logger.warning(f"💰 잔고 부족: {krw_balance:,.0f}원 (부족: {shortage:,.0f}원)")
                logger.info(f"💡 매수를 위해 {shortage:,.0f}원을 입금해주세요.")
                
        except Exception as e:
            logger.error(f"잔고 상태 체크 오류: {e}")
    
    def _restore_existing_positions(self):
        """봇 재시작 시 기존 포지션 복원"""
        try:
            logger.info("🔄 기존 포지션 복원 시도 중...")
            
            # 1. 파일에서 포지션 복원 (이미 RiskManager 초기화 시 완료)
            open_positions = self.risk_manager.get_open_positions()
            
            if open_positions:
                logger.info(f"파일에서 {len(open_positions)}개 포지션 복원")
                for market, position in open_positions.items():
                    logger.info(f"- {market}: 진입가 {position.entry_price:,.0f}원, 수량 {position.quantity:.6f}")
            else:
                logger.info("저장된 포지션이 없습니다.")
            
            # 2. Upbit API에서 실제 잔고 확인 및 동기화
            logger.info("Upbit 실제 잔고와 동기화 중...")
            self.risk_manager.restore_positions_from_upbit(self.upbit_api)
            
            # 3. 복원 완료 후 현재 포지션 상태 표시
            final_positions = self.risk_manager.get_open_positions()
            if final_positions:
                logger.info(f"✅ 총 {len(final_positions)}개 포지션 복원 완료:")
                
                total_investment = 0
                total_current_value = 0
                
                for market, position in final_positions.items():
                    current_price = self.upbit_api.get_current_price(market)
                    if current_price:
                        current_value = position.quantity * current_price
                        pnl = current_value - position.investment_amount
                        pnl_rate = (pnl / position.investment_amount) * 100
                        
                        total_investment += position.investment_amount
                        total_current_value += current_value
                        
                        logger.info(f"  {market}: {pnl:,.0f}원 ({pnl_rate:+.2f}%)")
                
                if total_investment > 0:
                    total_pnl = total_current_value - total_investment
                    total_pnl_rate = (total_pnl / total_investment) * 100
                    logger.info(f"📊 전체 미실현 손익: {total_pnl:,.0f}원 ({total_pnl_rate:+.2f}%)")
            else:
                logger.info("복원된 포지션이 없습니다. 새로 거래를 시작합니다.")
                
        except Exception as e:
            logger.error(f"포지션 복원 중 오류: {e}")
            logger.info("포지션 복원에 실패했지만 봇은 계속 실행됩니다.")
    
    def _scan_for_opportunities(self):
        """새로운 매수 기회 탐색"""
        if not self.risk_manager.can_open_position():
            logger.info("최대 포지션 수 도달로 인한 매수 스킵")
            return
        
        try:
            logger.info("🔍 매수 기회 탐색 중...")
            
            # 거래 가능한 마켓 조회
            try:
                markets = self.market_analyzer.get_tradeable_markets()
                if not markets:
                    logger.warning("거래 가능한 마켓 조회 실패")
                    return
            except Exception as e:
                logger.error(f"마켓 목록 조회 실패: {e}")
                return
            
            spike_candidates = []
            
            # 거래량 급등 종목 찾기 (속도 조절)
            scan_count = min(20, len(markets))  # 최대 20개만 스캔
            logger.info(f"상위 {scan_count}개 종목 스캔 중...")
            
            for i, market in enumerate(markets[:scan_count]):
                try:
                    # 매 5번째 종목마다 짧은 휴식 (API 제한 완화)
                    if i > 0 and i % 5 == 0:
                        time.sleep(1)
                    
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
                                
                                # 거래량 급등 로그 (알림은 제거)
                                logger.info(f"거래량 급등 감지: {market} ({self.volume_spike_threshold:.1f}배, {price_change:+.2f}%)")
                                
                except Exception as e:
                    logger.error(f"시장 스캔 오류 ({market}): {e}")
                    # API 오류 시 잠시 대기
                    time.sleep(2)
                    continue
            
            if not spike_candidates:
                logger.info("거래량 급등 종목 없음")
                return
            
            logger.info(f"거래량 급등 감지: {len(spike_candidates)}개 종목")
            
            # AI 분석 (옵션)
            best_candidate = spike_candidates[0]  # 기본값: 첫 번째 후보
            
            if self.ai_analyzer and self.ai_analyzer.enabled and len(spike_candidates) > 1:
                try:
                    ai_result = self.ai_analyzer.analyze_market_condition(spike_candidates)
                    
                    if (ai_result.get('recommended_coin') and 
                        ai_result.get('confidence', 0) >= 6 and 
                        ai_result.get('risk_level') != 'HIGH'):
                        
                        # AI 추천 종목 찾기
                        recommended_market = f"KRW-{ai_result['recommended_coin']}"
                        for candidate in spike_candidates:
                            if candidate['market'] == recommended_market:
                                best_candidate = candidate
                                logger.info(f"AI 추천 종목 선택: {recommended_market} (신뢰도: {ai_result['confidence']})")
                                break
                        else:
                            logger.info(f"AI 추천 종목({recommended_market})이 후보에 없어서 첫 번째 후보 선택")
                    else:
                        logger.info(f"AI 분석 결과 신뢰도 부족 또는 고위험 - 첫 번째 후보 선택")
                        
                except Exception as e:
                    logger.error(f"AI 분석 중 오류: {e}")
                    logger.info("AI 분석 실패로 첫 번째 후보 선택")
            else:
                if not self.ai_analyzer or not self.ai_analyzer.enabled:
                    logger.info("AI 분석 비활성화 - 첫 번째 후보 선택")
                else:
                    logger.info("후보가 1개뿐이어서 AI 분석 건너뜀")
            
            # 매수 실행
            self._execute_buy(best_candidate)
            
        except Exception as e:
            logger.error(f"매수 기회 탐색 오류: {e}")
    
    def _execute_buy(self, candidate: Dict):
        """매수 실행 (분할매수 지원)"""
        market = candidate['market']
        current_price = candidate['current_price']
        
        try:
            # 현재 잔고 확인
            krw_balance = self.upbit_api.get_krw_balance()
            if krw_balance < 30000:  # 최소 잔고 확인
                logger.warning(f"💰 잔고 부족으로 매수 스킵: {market} (현재: {krw_balance:,.0f}원, 필요: 30,000원 이상)")
                return
            
            # AI 분할매수 분석
            open_positions = self.risk_manager.get_open_positions()
            current_positions = len(open_positions)
            
            if self.ai_analyzer and self.ai_analyzer.enabled:
                amount_analysis = self.ai_analyzer.analyze_position_amount(
                    candidate, krw_balance, current_positions, self.risk_manager.max_positions
                )
                investment_amount = amount_analysis['investment_amount']
                logger.info(f"🤖 AI 분할매수 결정: {investment_amount:,.0f}원 - {amount_analysis['reason']}")
            else:
                # AI가 없는 경우 기본 로직
                investment_amount = min(self.investment_amount, krw_balance * 0.8)
                logger.info(f"💰 기본 매수 금액: {investment_amount:,.0f}원")
            
            # 최종 잔고 체크
            if krw_balance < investment_amount:
                logger.warning(f"💰 잔고 부족으로 매수 스킵: {market} (현재: {krw_balance:,.0f}원, 필요: {investment_amount:,.0f}원)")
                return
            
            # 매수 주문 실행
            order_result = self.upbit_api.place_buy_order(market, investment_amount)
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
                    # 포지션 추가 (실제 투자된 금액 사용)
                    actual_investment = executed_volume * avg_price
                    success = self.risk_manager.add_position(
                        market=market,
                        entry_price=avg_price,
                        quantity=executed_volume,
                        investment_amount=actual_investment
                    )
                    
                    if success:
                        # 매수 알림
                        if self.ai_analyzer and self.ai_analyzer.enabled:
                            reason = f"AI 분할매수 {investment_amount:,.0f}원 (거래량 {candidate.get('volume_ratio', 0):.1f}배)"
                        else:
                            reason = f"거래량 {candidate.get('volume_ratio', 0):.1f}배 급등"
                        notify_buy(market, avg_price, actual_investment, reason)
                        logger.info(f"✅ 매수 완료: {market}, 가격: {avg_price:,.0f}, 수량: {executed_volume}, 실제투자: {actual_investment:,.0f}원")
                    else:
                        logger.error(f"포지션 추가 실패: {market}")
                else:
                    logger.error(f"체결 수량 0: {market}")
            else:
                logger.error(f"주문 체결 확인 실패: {market}")
                
        except Exception as e:
            logger.error(f"매수 실행 오류 ({market}): {e}")
    
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
    
    def _analyze_position_swap(self, losing_positions: List[Dict]):
        """포지션 교체 분석 및 실행"""
        try:
            # 새로운 매수 기회 탐색
            markets = get_tradeable_markets()
            if not markets:
                return
            
            opportunities = []
            for market in markets[:15]:  # 상위 15개 시장만 확인
                try:
                    # 현재 보유중인 종목은 제외
                    current_positions = self.risk_manager.get_open_positions()
                    if market in current_positions:
                        continue
                    
                    current_price = get_current_price(market)
                    candle_data = get_candles(market, count=10)
                    if not current_price or not candle_data:
                        continue
                    
                    # 거래량 급등 확인
                    latest_volume = candle_data[0]['candle_acc_trade_volume']
                    avg_volume = sum(c['candle_acc_trade_volume'] for c in candle_data[1:6]) / 5
                    volume_ratio = latest_volume / avg_volume if avg_volume > 0 else 1
                    
                    price_change = get_price_change(market)
                    
                    if volume_ratio >= 2.0:  # 거래량 2배 이상 증가
                        opportunities.append({
                            'market': market,
                            'current_price': current_price,
                            'volume_ratio': volume_ratio,
                            'price_change': price_change or 0
                        })
                except Exception as e:
                    logger.debug(f"시장 데이터 조회 실패 ({market}): {e}")
                    continue
            
            if not opportunities:
                logger.info("📊 포지션 교체 기회 없음 - 새로운 매수 기회가 부족")
                return
            
            logger.info(f"🔍 포지션 교체 분석 중: 손실 포지션 {len(losing_positions)}개, 매수 기회 {len(opportunities)}개")
            
            # AI 포지션 교체 분석
            swap_analysis = self.ai_analyzer.analyze_position_swap(losing_positions, opportunities)
            
            if (swap_analysis.get('should_swap') and 
                swap_analysis.get('sell_market') and 
                swap_analysis.get('buy_market')):
                
                sell_market = swap_analysis['sell_market']
                buy_market = swap_analysis['buy_market']
                confidence = swap_analysis.get('confidence', 5)
                
                logger.info(f"🔄 AI 포지션 교체 결정 (신뢰도: {confidence}/10)")
                logger.info(f"📤 매도: {sell_market}")
                logger.info(f"📥 매수: {buy_market}")
                logger.info(f"💡 이유: {swap_analysis['reason']}")
                
                # 해당 손실 포지션 찾기
                sell_position = next((pos for pos in losing_positions if pos['market'] == sell_market), None)
                buy_opportunity = next((opp for opp in opportunities if opp['market'] == buy_market), None)
                
                if sell_position and buy_opportunity and confidence >= 6:  # 신뢰도 6 이상만 실행
                    # 손절매 실행
                    logger.info(f"🔸 손절매 실행: {sell_market}")
                    self._execute_sell(sell_market, sell_position['current_price'], 
                                     f"AI 포지션 교체 (손절, 신뢰도: {confidence})")
                    
                    # 잠시 대기 후 새로운 종목 매수
                    time.sleep(3)
                    logger.info(f"🔹 신규 매수 실행: {buy_market}")
                    self._execute_buy(buy_opportunity)
                    
                    logger.info(f"🎯 포지션 교체 완료: {sell_market} → {buy_market}")
                else:
                    logger.info(f"⚠️ 포지션 교체 취소: 신뢰도 부족 또는 종목 정보 오류 (신뢰도: {confidence})")
            else:
                logger.info("📊 AI 분석 결과: 포지션 교체 불필요")
                if swap_analysis.get('reason'):
                    logger.info(f"💡 이유: {swap_analysis['reason']}")
                    
        except Exception as e:
            logger.error(f"포지션 교체 분석 오류: {e}")

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
    finally:
        bot.stop()

if __name__ == "__main__":
    main()
