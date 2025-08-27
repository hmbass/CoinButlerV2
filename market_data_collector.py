"""
외부 시장 데이터 수집기 - Fear & Greed Index, 글로벌 시장 데이터 등
"""
import os
import requests
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json

logger = logging.getLogger(__name__)

class MarketDataCollector:
    """외부 시장 데이터 수집 및 분석"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'CoinButler/1.0'
        })
        
    def get_fear_greed_index(self) -> Dict:
        """Fear & Greed Index 수집 (Alternative.me API)"""
        try:
            url = "https://api.alternative.me/fng/?limit=7&format=json"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if 'data' in data and len(data['data']) > 0:
                latest = data['data'][0]
                return {
                    'value': int(latest['value']),
                    'classification': latest['value_classification'],
                    'timestamp': datetime.fromtimestamp(int(latest['timestamp'])),
                    'trend': self._analyze_fng_trend(data['data'][:7])
                }
        except Exception as e:
            logger.error(f"Fear & Greed Index 수집 실패: {e}")
            
        return {
            'value': 50,
            'classification': 'Neutral',
            'timestamp': datetime.now(),
            'trend': 'STABLE'
        }
    
    def _analyze_fng_trend(self, fng_data: List[Dict]) -> str:
        """Fear & Greed Index 트렌드 분석"""
        if len(fng_data) < 2:
            return 'STABLE'
            
        values = [int(item['value']) for item in fng_data]
        recent_avg = sum(values[:3]) / 3  # 최근 3일 평균
        older_avg = sum(values[3:]) / len(values[3:])  # 이전 평균
        
        if recent_avg > older_avg + 10:
            return 'RISING'
        elif recent_avg < older_avg - 10:
            return 'FALLING'
        else:
            return 'STABLE'
    
    def get_bitcoin_dominance(self) -> Dict:
        """비트코인 도미넌스 수집 (CoinGecko API)"""
        try:
            url = "https://api.coingecko.com/api/v3/global"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            btc_dominance = data['data']['market_cap_percentage']['btc']
            
            return {
                'dominance': round(btc_dominance, 2),
                'interpretation': self._interpret_dominance(btc_dominance),
                'timestamp': datetime.now()
            }
        except Exception as e:
            logger.error(f"비트코인 도미넌스 수집 실패: {e}")
            
        return {
            'dominance': 45.0,
            'interpretation': 'NEUTRAL',
            'timestamp': datetime.now()
        }
    
    def _interpret_dominance(self, dominance: float) -> str:
        """비트코인 도미넌스 해석"""
        if dominance > 60:
            return 'BTC_STRONG'  # 비트코인 강세, 알트코인 약세
        elif dominance < 40:
            return 'ALT_SEASON'  # 알트코인 시즌
        else:
            return 'NEUTRAL'
    
    def get_global_market_data(self) -> Dict:
        """글로벌 시장 데이터 수집"""
        try:
            url = "https://api.coingecko.com/api/v3/global"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()['data']
            
            return {
                'total_market_cap': data.get('total_market_cap', {}).get('usd', 0),
                'total_volume': data.get('total_volume', {}).get('usd', 0),
                'market_cap_change_24h': data.get('market_cap_change_percentage_24h_usd', 0),
                'active_cryptocurrencies': data.get('active_cryptocurrencies', 0),
                'markets': data.get('markets', 0),
                'timestamp': datetime.now()
            }
        except Exception as e:
            logger.error(f"글로벌 시장 데이터 수집 실패: {e}")
            
        return {
            'total_market_cap': 0,
            'total_volume': 0,
            'market_cap_change_24h': 0,
            'active_cryptocurrencies': 0,
            'markets': 0,
            'timestamp': datetime.now()
        }
    
    def get_trending_coins(self) -> List[Dict]:
        """트렌딩 코인 정보 수집"""
        try:
            url = "https://api.coingecko.com/api/v3/search/trending"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            trending = []
            
            for coin in data.get('coins', [])[:5]:  # 상위 5개만
                trending.append({
                    'symbol': coin['item']['symbol'].upper(),
                    'name': coin['item']['name'],
                    'rank': coin['item']['market_cap_rank'],
                    'score': coin['item']['score']
                })
            
            return trending
        except Exception as e:
            logger.error(f"트렌딩 코인 수집 실패: {e}")
            return []
    
    def get_comprehensive_market_context(self) -> Dict:
        """종합 시장 컨텍스트 수집"""
        logger.info("종합 시장 데이터 수집 시작...")
        
        # 모든 데이터 수집
        fear_greed = self.get_fear_greed_index()
        dominance = self.get_bitcoin_dominance()
        global_data = self.get_global_market_data()
        trending = self.get_trending_coins()
        
        # 종합 시장 심리 분석
        market_sentiment = self._analyze_overall_sentiment(
            fear_greed, dominance, global_data
        )
        
        context = {
            'fear_greed': fear_greed,
            'btc_dominance': dominance,
            'global_market': global_data,
            'trending_coins': trending,
            'overall_sentiment': market_sentiment,
            'collected_at': datetime.now().isoformat()
        }
        
        # 캐시 저장
        self._save_market_context_cache(context)
        
        logger.info(f"시장 데이터 수집 완료 - 심리: {market_sentiment}")
        return context
    
    def _analyze_overall_sentiment(self, fear_greed: Dict, dominance: Dict, global_data: Dict) -> str:
        """종합 시장 심리 분석"""
        sentiment_score = 0
        
        # Fear & Greed Index 기여 (40%)
        fng_value = fear_greed['value']
        if fng_value >= 75:
            sentiment_score += 40
        elif fng_value >= 55:
            sentiment_score += 30
        elif fng_value >= 45:
            sentiment_score += 20
        elif fng_value >= 25:
            sentiment_score += 10
        else:
            sentiment_score += 0
        
        # 시장 변화율 기여 (30%)
        market_change = global_data.get('market_cap_change_24h', 0)
        if market_change >= 5:
            sentiment_score += 30
        elif market_change >= 2:
            sentiment_score += 20
        elif market_change >= -2:
            sentiment_score += 15
        elif market_change >= -5:
            sentiment_score += 10
        else:
            sentiment_score += 0
        
        # 비트코인 도미넌스 기여 (30%)
        dom_interpretation = dominance['interpretation']
        if dom_interpretation == 'ALT_SEASON':
            sentiment_score += 25  # 알트코인 시즌은 긍정적
        elif dom_interpretation == 'NEUTRAL':
            sentiment_score += 20
        else:  # BTC_STRONG
            sentiment_score += 15
        
        # 결과 분류
        if sentiment_score >= 80:
            return 'VERY_BULLISH'
        elif sentiment_score >= 60:
            return 'BULLISH'
        elif sentiment_score >= 40:
            return 'NEUTRAL'
        elif sentiment_score >= 20:
            return 'BEARISH'
        else:
            return 'VERY_BEARISH'
    
    def _save_market_context_cache(self, context: Dict):
        """시장 컨텍스트 캐시 저장"""
        try:
            cache_file = "market_context_cache.json"
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(context, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"시장 컨텍스트 캐시 저장 실패: {e}")
    
    def get_cached_market_context(self, max_age_minutes: int = 30) -> Optional[Dict]:
        """캐시된 시장 컨텍스트 조회"""
        try:
            cache_file = "market_context_cache.json"
            if not os.path.exists(cache_file):
                return None
            
            # 파일 수정 시간 확인
            file_time = datetime.fromtimestamp(os.path.getmtime(cache_file))
            if datetime.now() - file_time > timedelta(minutes=max_age_minutes):
                return None
            
            with open(cache_file, 'r', encoding='utf-8') as f:
                context = json.load(f)
                logger.info("캐시된 시장 컨텍스트 사용")
                return context
                
        except Exception as e:
            logger.error(f"시장 컨텍스트 캐시 조회 실패: {e}")
            return None

# 싱글톤 인스턴스
_market_data_collector = None

def get_market_data_collector() -> MarketDataCollector:
    """MarketDataCollector 싱글톤 인스턴스 반환"""
    global _market_data_collector
    if _market_data_collector is None:
        _market_data_collector = MarketDataCollector()
    return _market_data_collector
