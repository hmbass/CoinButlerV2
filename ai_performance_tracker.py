"""
AI 추천 성과 추적 및 백테스팅 시스템
"""
import os
import json
import pandas as pd
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import sqlite3

logger = logging.getLogger(__name__)

@dataclass
class AIRecommendation:
    """AI 추천 데이터 클래스"""
    timestamp: str
    market: str
    recommended_coin: str
    confidence: int
    reason: str
    risk_level: str
    entry_strategy: str
    target_return: float
    stop_loss: float
    holding_period: str
    
    # 시장 컨텍스트 정보
    btc_price: float
    fear_greed_index: int
    btc_dominance: float
    market_sentiment: str
    
    # 기술적 지표
    rsi: float
    macd_trend: str
    volume_ratio: float
    price_change: float
    
    # 실제 결과 (추후 업데이트)
    executed: bool = False
    execution_price: Optional[float] = None
    exit_price: Optional[float] = None
    exit_timestamp: Optional[str] = None
    actual_return: Optional[float] = None
    holding_days: Optional[int] = None
    success: Optional[bool] = None

@dataclass
class PerformanceMetrics:
    """성과 지표 데이터 클래스"""
    total_recommendations: int
    executed_recommendations: int
    success_rate: float
    average_return: float
    best_return: float
    worst_return: float
    avg_confidence: float
    confidence_vs_success_correlation: float
    
    # 신뢰도별 성과
    high_confidence_success_rate: float  # 8+ 신뢰도
    medium_confidence_success_rate: float  # 6-7 신뢰도
    low_confidence_success_rate: float  # 5 이하 신뢰도
    
    # 시장 상황별 성과
    bullish_market_success_rate: float
    bearish_market_success_rate: float
    neutral_market_success_rate: float

class AIPerformanceTracker:
    """AI 추천 성과 추적 및 분석"""
    
    def __init__(self, db_path: str = "ai_recommendations.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """데이터베이스 초기화"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ai_recommendations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    market TEXT NOT NULL,
                    recommended_coin TEXT NOT NULL,
                    confidence INTEGER NOT NULL,
                    reason TEXT,
                    risk_level TEXT,
                    entry_strategy TEXT,
                    target_return REAL,
                    stop_loss REAL,
                    holding_period TEXT,
                    
                    btc_price REAL,
                    fear_greed_index INTEGER,
                    btc_dominance REAL,
                    market_sentiment TEXT,
                    
                    rsi REAL,
                    macd_trend TEXT,
                    volume_ratio REAL,
                    price_change REAL,
                    
                    executed BOOLEAN DEFAULT FALSE,
                    execution_price REAL,
                    exit_price REAL,
                    exit_timestamp TEXT,
                    actual_return REAL,
                    holding_days INTEGER,
                    success BOOLEAN
                )
            """)
            
            # 인덱스 생성
            conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON ai_recommendations(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_market ON ai_recommendations(market)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_confidence ON ai_recommendations(confidence)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_executed ON ai_recommendations(executed)")
    
    def save_recommendation(self, recommendation: AIRecommendation) -> int:
        """AI 추천 저장"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    INSERT INTO ai_recommendations (
                        timestamp, market, recommended_coin, confidence, reason, risk_level,
                        entry_strategy, target_return, stop_loss, holding_period,
                        btc_price, fear_greed_index, btc_dominance, market_sentiment,
                        rsi, macd_trend, volume_ratio, price_change,
                        executed, execution_price, exit_price, exit_timestamp,
                        actual_return, holding_days, success
                    ) VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                    )
                """, (
                    recommendation.timestamp, recommendation.market, recommendation.recommended_coin,
                    recommendation.confidence, recommendation.reason, recommendation.risk_level,
                    recommendation.entry_strategy, recommendation.target_return, recommendation.stop_loss,
                    recommendation.holding_period, recommendation.btc_price, recommendation.fear_greed_index,
                    recommendation.btc_dominance, recommendation.market_sentiment, recommendation.rsi,
                    recommendation.macd_trend, recommendation.volume_ratio, recommendation.price_change,
                    recommendation.executed, recommendation.execution_price, recommendation.exit_price,
                    recommendation.exit_timestamp, recommendation.actual_return, recommendation.holding_days,
                    recommendation.success
                ))
                
                rec_id = cursor.lastrowid
                logger.info(f"AI 추천 저장 완료: {recommendation.recommended_coin} (ID: {rec_id})")
                return rec_id
                
        except Exception as e:
            logger.error(f"AI 추천 저장 실패: {e}")
            return -1
    
    def update_recommendation_result(self, recommendation_id: int, execution_price: float,
                                   exit_price: Optional[float] = None, 
                                   exit_timestamp: Optional[str] = None) -> bool:
        """추천 결과 업데이트"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                if exit_price is None:
                    # 매수 실행만 업데이트
                    conn.execute("""
                        UPDATE ai_recommendations 
                        SET executed = TRUE, execution_price = ?
                        WHERE id = ?
                    """, (execution_price, recommendation_id))
                else:
                    # 매도 완료 업데이트
                    actual_return = ((exit_price - execution_price) / execution_price) * 100
                    success = actual_return > 0
                    
                    # 보유 기간 계산
                    cursor = conn.execute("SELECT timestamp FROM ai_recommendations WHERE id = ?", (recommendation_id,))
                    row = cursor.fetchone()
                    if row:
                        start_time = datetime.fromisoformat(row[0])
                        end_time = datetime.fromisoformat(exit_timestamp) if exit_timestamp else datetime.now()
                        holding_days = (end_time - start_time).days
                    else:
                        holding_days = 0
                    
                    conn.execute("""
                        UPDATE ai_recommendations 
                        SET executed = TRUE, execution_price = ?, exit_price = ?, 
                            exit_timestamp = ?, actual_return = ?, holding_days = ?, success = ?
                        WHERE id = ?
                    """, (execution_price, exit_price, exit_timestamp, actual_return, holding_days, success, recommendation_id))
                
                logger.info(f"추천 결과 업데이트 완료: ID {recommendation_id}")
                return True
                
        except Exception as e:
            logger.error(f"추천 결과 업데이트 실패: {e}")
            return False
    
    def get_performance_metrics(self, days: int = 30) -> PerformanceMetrics:
        """성과 지표 계산"""
        try:
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            with sqlite3.connect(self.db_path) as conn:
                # 전체 통계
                cursor = conn.execute("""
                    SELECT COUNT(*), AVG(confidence), 
                           COUNT(CASE WHEN executed = 1 THEN 1 END),
                           COUNT(CASE WHEN success = 1 THEN 1 END),
                           AVG(CASE WHEN actual_return IS NOT NULL THEN actual_return END),
                           MAX(CASE WHEN actual_return IS NOT NULL THEN actual_return END),
                           MIN(CASE WHEN actual_return IS NOT NULL THEN actual_return END)
                    FROM ai_recommendations 
                    WHERE timestamp >= ?
                """, (cutoff_date,))
                
                total, avg_conf, executed, successful, avg_return, best_return, worst_return = cursor.fetchone()
                
                if total == 0:
                    return self._empty_metrics()
                
                success_rate = (successful / executed * 100) if executed > 0 else 0
                
                # 신뢰도별 성과
                high_conf_success = self._get_confidence_success_rate(conn, cutoff_date, 8, 10)
                med_conf_success = self._get_confidence_success_rate(conn, cutoff_date, 6, 7)
                low_conf_success = self._get_confidence_success_rate(conn, cutoff_date, 0, 5)
                
                # 시장 상황별 성과
                bullish_success = self._get_market_sentiment_success_rate(conn, cutoff_date, ['BULLISH', 'VERY_BULLISH'])
                bearish_success = self._get_market_sentiment_success_rate(conn, cutoff_date, ['BEARISH', 'VERY_BEARISH'])
                neutral_success = self._get_market_sentiment_success_rate(conn, cutoff_date, ['NEUTRAL'])
                
                # 신뢰도와 성공률 상관관계 (간단한 계산)
                confidence_correlation = self._calculate_confidence_correlation(conn, cutoff_date)
                
                return PerformanceMetrics(
                    total_recommendations=total,
                    executed_recommendations=executed,
                    success_rate=success_rate,
                    average_return=avg_return or 0,
                    best_return=best_return or 0,
                    worst_return=worst_return or 0,
                    avg_confidence=avg_conf or 0,
                    confidence_vs_success_correlation=confidence_correlation,
                    high_confidence_success_rate=high_conf_success,
                    medium_confidence_success_rate=med_conf_success,
                    low_confidence_success_rate=low_conf_success,
                    bullish_market_success_rate=bullish_success,
                    bearish_market_success_rate=bearish_success,
                    neutral_market_success_rate=neutral_success
                )
                
        except Exception as e:
            logger.error(f"성과 지표 계산 실패: {e}")
            return self._empty_metrics()
    
    def _empty_metrics(self) -> PerformanceMetrics:
        """빈 성과 지표 반환"""
        return PerformanceMetrics(
            total_recommendations=0, executed_recommendations=0, success_rate=0,
            average_return=0, best_return=0, worst_return=0, avg_confidence=0,
            confidence_vs_success_correlation=0, high_confidence_success_rate=0,
            medium_confidence_success_rate=0, low_confidence_success_rate=0,
            bullish_market_success_rate=0, bearish_market_success_rate=0,
            neutral_market_success_rate=0
        )
    
    def _get_confidence_success_rate(self, conn, cutoff_date: str, min_conf: int, max_conf: int) -> float:
        """신뢰도 범위별 성공률"""
        cursor = conn.execute("""
            SELECT COUNT(CASE WHEN success = 1 THEN 1 END), COUNT(*)
            FROM ai_recommendations 
            WHERE timestamp >= ? AND confidence >= ? AND confidence <= ? AND executed = 1
        """, (cutoff_date, min_conf, max_conf))
        
        successful, total = cursor.fetchone()
        return (successful / total * 100) if total > 0 else 0
    
    def _get_market_sentiment_success_rate(self, conn, cutoff_date: str, sentiments: List[str]) -> float:
        """시장 심리별 성공률"""
        placeholders = ','.join(['?' for _ in sentiments])
        cursor = conn.execute(f"""
            SELECT COUNT(CASE WHEN success = 1 THEN 1 END), COUNT(*)
            FROM ai_recommendations 
            WHERE timestamp >= ? AND market_sentiment IN ({placeholders}) AND executed = 1
        """, (cutoff_date, *sentiments))
        
        successful, total = cursor.fetchone()
        return (successful / total * 100) if total > 0 else 0
    
    def _calculate_confidence_correlation(self, conn, cutoff_date: str) -> float:
        """신뢰도와 성공률 상관관계 계산"""
        cursor = conn.execute("""
            SELECT confidence, success
            FROM ai_recommendations 
            WHERE timestamp >= ? AND executed = 1 AND success IS NOT NULL
        """, (cutoff_date,))
        
        data = cursor.fetchall()
        if len(data) < 3:
            return 0
        
        # 간단한 상관관계 계산
        confidences = [row[0] for row in data]
        successes = [1 if row[1] else 0 for row in data]
        
        n = len(data)
        sum_conf = sum(confidences)
        sum_succ = sum(successes)
        sum_conf_succ = sum(c * s for c, s in zip(confidences, successes))
        sum_conf_sq = sum(c * c for c in confidences)
        sum_succ_sq = sum(s * s for s in successes)
        
        numerator = n * sum_conf_succ - sum_conf * sum_succ
        denominator = ((n * sum_conf_sq - sum_conf * sum_conf) * (n * sum_succ_sq - sum_succ * sum_succ)) ** 0.5
        
        return numerator / denominator if denominator != 0 else 0
    
    def get_recent_recommendations(self, limit: int = 10) -> List[Dict]:
        """최근 추천 목록"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT timestamp, market, recommended_coin, confidence, reason, 
                           executed, actual_return, success
                    FROM ai_recommendations 
                    ORDER BY timestamp DESC LIMIT ?
                """, (limit,))
                
                recommendations = []
                for row in cursor.fetchall():
                    recommendations.append({
                        'timestamp': row[0],
                        'market': row[1],
                        'recommended_coin': row[2],
                        'confidence': row[3],
                        'reason': row[4],
                        'executed': bool(row[5]),
                        'actual_return': row[6],
                        'success': bool(row[7]) if row[7] is not None else None
                    })
                
                return recommendations
                
        except Exception as e:
            logger.error(f"최근 추천 조회 실패: {e}")
            return []
    
    def export_to_csv(self, filename: str = None) -> str:
        """데이터를 CSV로 내보내기"""
        if filename is None:
            filename = f"ai_recommendations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                df = pd.read_sql_query("SELECT * FROM ai_recommendations", conn)
                df.to_csv(filename, index=False, encoding='utf-8-sig')
                logger.info(f"AI 추천 데이터 CSV 내보내기 완료: {filename}")
                return filename
                
        except Exception as e:
            logger.error(f"CSV 내보내기 실패: {e}")
            return ""
    
    def generate_performance_report(self, days: int = 30) -> Dict:
        """성과 리포트 생성"""
        metrics = self.get_performance_metrics(days)
        recent_recs = self.get_recent_recommendations(20)
        
        return {
            'metrics': asdict(metrics),
            'recent_recommendations': recent_recs,
            'report_generated_at': datetime.now().isoformat(),
            'analysis_period_days': days
        }

# 싱글톤 인스턴스
_ai_performance_tracker = None

def get_ai_performance_tracker() -> AIPerformanceTracker:
    """AIPerformanceTracker 싱글톤 인스턴스 반환"""
    global _ai_performance_tracker
    if _ai_performance_tracker is None:
        _ai_performance_tracker = AIPerformanceTracker()
    return _ai_performance_tracker
