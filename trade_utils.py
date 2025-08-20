"""
업비트 API 연동을 위한 유틸리티 함수들
"""
import os
import requests
import jwt
import uuid
import hashlib
import time
from urllib.parse import urlencode
import pyupbit
from typing import Optional, Dict, List, Any
import pandas as pd
from datetime import datetime, timedelta
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class UpbitAPI:
    """업비트 API 래퍼 클래스"""
    
    def __init__(self, access_key: str, secret_key: str):
        self.access_key = access_key
        self.secret_key = secret_key
        self.server_url = "https://api.upbit.com"
        
    def _get_headers(self, query_string: str = "") -> Dict[str, str]:
        """JWT 토큰이 포함된 헤더 생성"""
        payload = {
            'access_key': self.access_key,
            'nonce': str(uuid.uuid4()),
        }
        
        if query_string:
            query_hash = hashlib.sha512(query_string.encode()).hexdigest()
            payload['query_hash'] = query_hash
            payload['query_hash_alg'] = 'SHA512'
        
        jwt_token = jwt.encode(payload, self.secret_key)
        return {
            'Authorization': f'Bearer {jwt_token}',
            'Accept': 'application/json',
        }
    
    def get_accounts(self) -> List[Dict[str, Any]]:
        """계정 정보(잔고) 조회"""
        try:
            headers = self._get_headers()
            response = requests.get(f"{self.server_url}/v1/accounts", headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"계정 정보 조회 실패: {e}")
            return []
    
    def get_krw_balance(self) -> float:
        """원화 잔고 조회"""
        accounts = self.get_accounts()
        for account in accounts:
            if account.get('currency') == 'KRW':
                return float(account.get('balance', 0))
        return 0.0
    
    def get_coin_balance(self, currency: str) -> float:
        """특정 코인 잔고 조회"""
        accounts = self.get_accounts()
        for account in accounts:
            if account.get('currency') == currency:
                return float(account.get('balance', 0))
        return 0.0
    
    def get_current_price(self, market: str) -> Optional[float]:
        """현재가 조회"""
        try:
            response = requests.get(f"{self.server_url}/v1/ticker", 
                                  params={'markets': market})
            response.raise_for_status()
            data = response.json()
            return float(data[0].get('trade_price', 0)) if data else None
        except Exception as e:
            logger.error(f"현재가 조회 실패 ({market}): {e}")
            return None
    
    def get_candles(self, market: str, minutes: int = 5, count: int = 200) -> List[Dict[str, Any]]:
        """분봉 데이터 조회"""
        try:
            response = requests.get(f"{self.server_url}/v1/candles/minutes/{minutes}",
                                  params={'market': market, 'count': count})
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"캔들 데이터 조회 실패 ({market}): {e}")
            return []
    
    def place_buy_order(self, market: str, price: float) -> Optional[Dict[str, Any]]:
        """시장가 매수 주문"""
        try:
            query = {
                'market': market,
                'side': 'bid',
                'price': str(price),
                'ord_type': 'price'
            }
            
            query_string = urlencode(query).encode()
            headers = self._get_headers(query_string.decode())
            
            response = requests.post(f"{self.server_url}/v1/orders",
                                   json=query, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"매수 주문 완료: {market}, 금액: {price}원")
            return result
            
        except Exception as e:
            logger.error(f"매수 주문 실패 ({market}): {e}")
            return None
    
    def place_sell_order(self, market: str, volume: float) -> Optional[Dict[str, Any]]:
        """시장가 매도 주문"""
        try:
            query = {
                'market': market,
                'side': 'ask',
                'volume': str(volume),
                'ord_type': 'market'
            }
            
            query_string = urlencode(query).encode()
            headers = self._get_headers(query_string.decode())
            
            response = requests.post(f"{self.server_url}/v1/orders",
                                   json=query, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"매도 주문 완료: {market}, 수량: {volume}")
            return result
            
        except Exception as e:
            logger.error(f"매도 주문 실패 ({market}): {e}")
            return None
    
    def get_order_info(self, uuid: str) -> Optional[Dict[str, Any]]:
        """주문 정보 조회"""
        try:
            query = {'uuid': uuid}
            query_string = urlencode(query)
            headers = self._get_headers(query_string)
            
            response = requests.get(f"{self.server_url}/v1/order?{query_string}",
                                  headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"주문 정보 조회 실패: {e}")
            return None
    
    def get_orders(self, market: str = None, state: str = 'wait') -> List[Dict[str, Any]]:
        """주문 목록 조회"""
        try:
            query = {'state': state}
            if market:
                query['market'] = market
                
            query_string = urlencode(query)
            headers = self._get_headers(query_string)
            
            response = requests.get(f"{self.server_url}/v1/orders?{query_string}",
                                  headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"주문 목록 조회 실패: {e}")
            return []

class MarketAnalyzer:
    """시장 분석 유틸리티"""
    
    def __init__(self, api: UpbitAPI):
        self.api = api
    
    def detect_volume_spike(self, market: str, threshold: float = 2.0) -> bool:
        """거래량 급등 감지"""
        try:
            candles = self.api.get_candles(market, minutes=5, count=10)
            if len(candles) < 5:
                return False
            
            # 최근 5분봉의 거래량
            recent_volume = float(candles[0]['candle_acc_trade_volume'])
            
            # 이전 4개 봉의 평균 거래량
            prev_volumes = [float(candle['candle_acc_trade_volume']) for candle in candles[1:5]]
            avg_volume = sum(prev_volumes) / len(prev_volumes) if prev_volumes else 0
            
            if avg_volume == 0:
                return False
            
            volume_ratio = recent_volume / avg_volume
            
            logger.info(f"{market} 거래량 비율: {volume_ratio:.2f}")
            
            return volume_ratio >= threshold
            
        except Exception as e:
            logger.error(f"거래량 급등 감지 실패 ({market}): {e}")
            return False
    
    def get_price_change(self, market: str) -> Optional[float]:
        """가격 변동률 조회"""
        try:
            response = requests.get(f"{self.api.server_url}/v1/ticker",
                                  params={'markets': market})
            response.raise_for_status()
            data = response.json()
            
            if data:
                return float(data[0].get('signed_change_rate', 0))
            return None
        except Exception as e:
            logger.error(f"가격 변동률 조회 실패 ({market}): {e}")
            return None
    
    def get_tradeable_markets(self) -> List[str]:
        """거래 가능한 KRW 마켓 목록 조회"""
        try:
            response = requests.get(f"{self.api.server_url}/v1/market/all")
            response.raise_for_status()
            markets = response.json()
            
            # KRW 마켓만 필터링하고 상위 거래량 기준으로 정렬
            krw_markets = [market['market'] for market in markets 
                          if market['market'].startswith('KRW-')]
            
            return krw_markets[:50]  # 상위 50개만 반환
            
        except Exception as e:
            logger.error(f"거래 가능한 마켓 조회 실패: {e}")
            return []

def get_upbit_api() -> UpbitAPI:
    """환경 변수에서 업비트 API 인스턴스 생성"""
    access_key = os.getenv('UPBIT_ACCESS_KEY')
    secret_key = os.getenv('UPBIT_SECRET_KEY')
    
    if not access_key or not secret_key:
        raise ValueError("업비트 API 키가 설정되지 않았습니다. .env 파일을 확인해주세요.")
    
    return UpbitAPI(access_key, secret_key)
