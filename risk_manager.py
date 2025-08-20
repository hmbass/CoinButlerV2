"""
리스크 관리 및 손익 계산 모듈
"""
import os
import csv
import pandas as pd
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple
import logging
import json

logger = logging.getLogger(__name__)

class Position:
    """포지션 정보 클래스"""
    
    def __init__(self, market: str, entry_price: float, quantity: float, 
                 entry_time: datetime, investment_amount: float):
        self.market = market
        self.entry_price = entry_price
        self.quantity = quantity
        self.entry_time = entry_time
        self.investment_amount = investment_amount
        self.exit_price: Optional[float] = None
        self.exit_time: Optional[datetime] = None
        self.status = "open"  # open, closed, stop_loss
        self.profit_loss: Optional[float] = None
    
    def calculate_current_pnl(self, current_price: float) -> float:
        """현재 가격 기준 손익 계산"""
        current_value = self.quantity * current_price
        return current_value - self.investment_amount
    
    def calculate_pnl_rate(self, current_price: float) -> float:
        """손익률 계산"""
        pnl = self.calculate_current_pnl(current_price)
        return (pnl / self.investment_amount) * 100
    
    def close_position(self, exit_price: float, exit_time: datetime) -> float:
        """포지션 종료"""
        self.exit_price = exit_price
        self.exit_time = exit_time
        self.status = "closed"
        self.profit_loss = self.calculate_current_pnl(exit_price)
        return self.profit_loss
    
    def to_dict(self) -> Dict:
        """딕셔너리로 변환"""
        return {
            'market': self.market,
            'entry_price': self.entry_price,
            'exit_price': self.exit_price,
            'quantity': self.quantity,
            'entry_time': self.entry_time.isoformat() if self.entry_time else None,
            'exit_time': self.exit_time.isoformat() if self.exit_time else None,
            'investment_amount': self.investment_amount,
            'profit_loss': self.profit_loss,
            'status': self.status
        }

class RiskManager:
    """리스크 관리 클래스"""
    
    def __init__(self, daily_loss_limit: float, max_positions: int = 3):
        self.daily_loss_limit = daily_loss_limit  # 하루 손실 한도 (음수)
        self.max_positions = max_positions
        self.positions: Dict[str, Position] = {}  # 현재 보유 포지션
        self.trade_history_file = "trade_history.csv"
        self.daily_pnl_file = "daily_pnl.json"
        
        # CSV 파일 초기화
        self._initialize_trade_history()
        
    def _initialize_trade_history(self):
        """거래 이력 CSV 파일 초기화"""
        if not os.path.exists(self.trade_history_file):
            headers = [
                'timestamp', 'market', 'action', 'price', 'quantity', 
                'amount', 'profit_loss', 'cumulative_pnl', 'status'
            ]
            with open(self.trade_history_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
    
    def can_open_position(self) -> bool:
        """새로운 포지션을 열 수 있는지 확인"""
        active_positions = len([p for p in self.positions.values() if p.status == "open"])
        return active_positions < self.max_positions
    
    def add_position(self, market: str, entry_price: float, quantity: float, 
                    investment_amount: float) -> bool:
        """새로운 포지션 추가"""
        if not self.can_open_position():
            logger.warning(f"최대 포지션 수({self.max_positions}) 초과로 인한 매수 거부: {market}")
            return False
        
        if market in self.positions and self.positions[market].status == "open":
            logger.warning(f"이미 보유 중인 포지션: {market}")
            return False
        
        position = Position(
            market=market,
            entry_price=entry_price,
            quantity=quantity,
            entry_time=datetime.now(),
            investment_amount=investment_amount
        )
        
        self.positions[market] = position
        
        # 거래 기록
        self._record_trade(
            market=market,
            action="BUY",
            price=entry_price,
            quantity=quantity,
            amount=investment_amount,
            status="포지션 진입"
        )
        
        logger.info(f"포지션 추가: {market}, 진입가: {entry_price:,.0f}, 수량: {quantity:.6f}")
        return True
    
    def close_position(self, market: str, exit_price: float) -> Optional[float]:
        """포지션 종료"""
        if market not in self.positions or self.positions[market].status != "open":
            logger.warning(f"종료할 포지션이 없음: {market}")
            return None
        
        position = self.positions[market]
        profit_loss = position.close_position(exit_price, datetime.now())
        
        # 거래 기록
        self._record_trade(
            market=market,
            action="SELL",
            price=exit_price,
            quantity=position.quantity,
            amount=position.quantity * exit_price,
            profit_loss=profit_loss,
            status="포지션 종료"
        )
        
        # 일일 손익 업데이트
        self._update_daily_pnl(profit_loss)
        
        logger.info(f"포지션 종료: {market}, 손익: {profit_loss:,.0f}원")
        return profit_loss
    
    def get_position_pnl(self, market: str, current_price: float) -> Optional[Tuple[float, float]]:
        """포지션의 현재 손익과 손익률 반환"""
        if market not in self.positions or self.positions[market].status != "open":
            return None
        
        position = self.positions[market]
        pnl = position.calculate_current_pnl(current_price)
        pnl_rate = position.calculate_pnl_rate(current_price)
        
        return pnl, pnl_rate
    
    def should_sell(self, market: str, current_price: float, 
                   profit_rate: float, loss_rate: float) -> Tuple[bool, str]:
        """매도 조건 확인 (익절/손절)"""
        pnl_info = self.get_position_pnl(market, current_price)
        if not pnl_info:
            return False, ""
        
        pnl, pnl_rate = pnl_info
        
        # 익절 조건
        if pnl_rate >= profit_rate * 100:
            return True, f"익절 (수익률: {pnl_rate:.2f}%)"
        
        # 손절 조건
        if pnl_rate <= loss_rate * 100:
            return True, f"손절 (손실률: {pnl_rate:.2f}%)"
        
        return False, ""
    
    def get_daily_pnl(self) -> float:
        """오늘의 총 손익 조회"""
        try:
            if not os.path.exists(self.daily_pnl_file):
                return 0.0
            
            with open(self.daily_pnl_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            today = date.today().isoformat()
            return data.get(today, 0.0)
            
        except Exception as e:
            logger.error(f"일일 손익 조회 실패: {e}")
            return 0.0
    
    def _update_daily_pnl(self, profit_loss: float):
        """일일 손익 업데이트"""
        try:
            data = {}
            if os.path.exists(self.daily_pnl_file):
                with open(self.daily_pnl_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            
            today = date.today().isoformat()
            data[today] = data.get(today, 0.0) + profit_loss
            
            with open(self.daily_pnl_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.error(f"일일 손익 업데이트 실패: {e}")
    
    def check_daily_loss_limit(self) -> bool:
        """일일 손실 한도 초과 확인"""
        daily_pnl = self.get_daily_pnl()
        
        # 현재 보유 포지션의 미실현 손익도 고려
        unrealized_pnl = 0.0
        for market, position in self.positions.items():
            if position.status == "open":
                # 현재가 정보가 없으므로 여기서는 실현 손익만 체크
                pass
        
        total_pnl = daily_pnl + unrealized_pnl
        
        if total_pnl <= self.daily_loss_limit:
            logger.warning(f"일일 손실 한도 초과! 현재 손익: {total_pnl:,.0f}원, 한도: {self.daily_loss_limit:,.0f}원")
            return True
        
        return False
    
    def _record_trade(self, market: str, action: str, price: float, quantity: float,
                     amount: float, profit_loss: float = 0.0, status: str = ""):
        """거래 기록을 CSV에 저장"""
        try:
            cumulative_pnl = self.get_daily_pnl() + profit_loss
            
            with open(self.trade_history_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.now().isoformat(),
                    market,
                    action,
                    price,
                    quantity,
                    amount,
                    profit_loss,
                    cumulative_pnl,
                    status
                ])
                
        except Exception as e:
            logger.error(f"거래 기록 저장 실패: {e}")
    
    def get_open_positions(self) -> Dict[str, Position]:
        """현재 보유 중인 포지션 반환"""
        return {market: position for market, position in self.positions.items() 
                if position.status == "open"}
    
    def get_position_summary(self) -> Dict:
        """포지션 요약 정보 반환"""
        open_positions = self.get_open_positions()
        
        return {
            'total_positions': len(open_positions),
            'max_positions': self.max_positions,
            'available_slots': self.max_positions - len(open_positions),
            'daily_pnl': self.get_daily_pnl(),
            'daily_loss_limit': self.daily_loss_limit,
            'positions': {market: {
                'entry_price': pos.entry_price,
                'quantity': pos.quantity,
                'investment_amount': pos.investment_amount,
                'entry_time': pos.entry_time.isoformat()
            } for market, pos in open_positions.items()}
        }
    
    def get_trading_stats(self, days: int = 7) -> Dict:
        """거래 통계 조회"""
        try:
            df = pd.read_csv(self.trade_history_file)
            
            if df.empty:
                return {'total_trades': 0, 'total_pnl': 0, 'win_rate': 0}
            
            # 날짜 필터링
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            cutoff_date = datetime.now() - timedelta(days=days)
            df = df[df['timestamp'] >= cutoff_date]
            
            # 매도 거래만 필터링 (실현 손익)
            sell_trades = df[df['action'] == 'SELL']
            
            if sell_trades.empty:
                return {'total_trades': 0, 'total_pnl': 0, 'win_rate': 0}
            
            total_trades = len(sell_trades)
            total_pnl = sell_trades['profit_loss'].sum()
            winning_trades = len(sell_trades[sell_trades['profit_loss'] > 0])
            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
            
            return {
                'total_trades': total_trades,
                'total_pnl': total_pnl,
                'win_rate': win_rate,
                'winning_trades': winning_trades,
                'losing_trades': total_trades - winning_trades,
                'avg_profit': total_pnl / total_trades if total_trades > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"거래 통계 조회 실패: {e}")
            return {'total_trades': 0, 'total_pnl': 0, 'win_rate': 0}

def get_risk_manager() -> RiskManager:
    """환경 변수에서 리스크 매니저 인스턴스 생성"""
    daily_loss_limit = float(os.getenv('DAILY_LOSS_LIMIT', -50000))
    max_positions = int(os.getenv('MAX_POSITIONS', 3))
    
    return RiskManager(daily_loss_limit, max_positions)
