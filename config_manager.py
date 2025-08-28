"""
동적 설정 관리 시스템
"""
import json
import os
import logging
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class ConfigManager:
    """동적 설정 관리"""
    
    def __init__(self, config_file: str = "bot_config.json"):
        self.config_file = config_file
        self.default_config = {
            # 매수 관련 설정
            "min_balance_for_buy": 30000,  # 매수 최소 잔고 (사용자 요구사항)
            "investment_amount": 30000,    # 기본 투자 금액
            "max_positions": 3,            # 최대 보유 종목 수 (사용자 요구사항: 3개 제한)
            
            # 수익/손실 설정
            "profit_rate": 0.03,           # 목표 수익률 (3%)
            "loss_rate": -0.02,            # 손절률 (-2%)
            
            # 거래량/가격 변동 임계값
            "volume_spike_threshold": 2.0,  # 거래량 급등 임계값
            "price_change_threshold": 0.05, # 가격 변동 임계값 (5%)
            
            # 시간 설정
            "check_interval": 60,          # 체크 간격 (초)
            "market_scan_interval": 10,    # 시장 스캔 간격 (분)
            
            # 리스크 관리
            "daily_loss_limit": -50000,    # 일일 손실 한도
            
            # AI 설정
            "ai_confidence_threshold": 7,  # AI 신뢰도 임계값 (6→7로 상향조정)
            
            # 마지막 업데이트 시간
            "last_updated": datetime.now().isoformat()
        }
        self.config = self.load_config()
    
    def load_config(self) -> Dict[str, Any]:
        """설정 파일 로드"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    
                # 기본값과 병합 (새로운 설정이 추가된 경우 대비)
                merged_config = self.default_config.copy()
                merged_config.update(config)
                
                logger.info(f"설정 파일 로드 완료: {self.config_file}")
                return merged_config
            else:
                logger.info("설정 파일이 없어서 기본값 사용")
                self.save_config(self.default_config)
                return self.default_config.copy()
                
        except Exception as e:
            logger.error(f"설정 파일 로드 실패: {e}")
            return self.default_config.copy()
    
    def save_config(self, config: Dict[str, Any] = None) -> bool:
        """설정 파일 저장"""
        try:
            if config is None:
                config = self.config
            
            # 마지막 업데이트 시간 추가
            config["last_updated"] = datetime.now().isoformat()
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2, default=str)
            
            self.config = config
            logger.info(f"설정 파일 저장 완료: {self.config_file}")
            return True
            
        except Exception as e:
            logger.error(f"설정 파일 저장 실패: {e}")
            return False
    
    def get(self, key: str, default=None) -> Any:
        """설정값 조회"""
        return self.config.get(key, default)
    
    def set(self, key: str, value: Any) -> bool:
        """설정값 변경"""
        try:
            old_value = self.config.get(key)
            self.config[key] = value
            
            # 즉시 저장
            if self.save_config():
                logger.info(f"설정 변경: {key} = {old_value} → {value}")
                return True
            else:
                # 저장 실패 시 롤백
                self.config[key] = old_value
                return False
                
        except Exception as e:
            logger.error(f"설정 변경 실패: {e}")
            return False
    
    def update_multiple(self, updates: Dict[str, Any]) -> bool:
        """여러 설정값 한번에 변경"""
        try:
            old_values = {}
            
            # 백업
            for key in updates:
                old_values[key] = self.config.get(key)
            
            # 업데이트
            self.config.update(updates)
            
            # 저장
            if self.save_config():
                for key, value in updates.items():
                    logger.info(f"설정 변경: {key} = {old_values.get(key)} → {value}")
                return True
            else:
                # 저장 실패 시 롤백
                for key, old_value in old_values.items():
                    if old_value is not None:
                        self.config[key] = old_value
                return False
                
        except Exception as e:
            logger.error(f"설정 일괄 변경 실패: {e}")
            return False
    
    def reset_to_default(self) -> bool:
        """기본값으로 초기화"""
        try:
            return self.save_config(self.default_config.copy())
        except Exception as e:
            logger.error(f"기본값 초기화 실패: {e}")
            return False
    
    def get_all_settings(self) -> Dict[str, Any]:
        """모든 설정값 반환"""
        return self.config.copy()
    
    def get_trading_settings(self) -> Dict[str, Any]:
        """거래 관련 설정만 반환"""
        trading_keys = [
            'min_balance_for_buy', 'investment_amount', 'max_positions',
            'profit_rate', 'loss_rate', 'volume_spike_threshold',
            'price_change_threshold', 'daily_loss_limit'
        ]
        return {key: self.config[key] for key in trading_keys if key in self.config}
    
    def get_ai_settings(self) -> Dict[str, Any]:
        """AI 관련 설정만 반환"""
        ai_keys = ['ai_confidence_threshold']
        return {key: self.config[key] for key in ai_keys if key in self.config}
    
    def get_system_settings(self) -> Dict[str, Any]:
        """시스템 관련 설정만 반환"""
        system_keys = ['check_interval', 'market_scan_interval']
        return {key: self.config[key] for key in system_keys if key in self.config}
    
    def validate_config(self) -> tuple[bool, list]:
        """설정값 유효성 검사"""
        errors = []
        
        # 숫자 범위 검사
        if self.config['min_balance_for_buy'] < 5000:
            errors.append("매수 최소 잔고는 5,000원 이상이어야 합니다.")
            
        if self.config['investment_amount'] < 5000:
            errors.append("투자 금액은 5,000원 이상이어야 합니다.")
            
        if self.config['max_positions'] < 1 or self.config['max_positions'] > 10:
            errors.append("최대 보유 종목 수는 1-10개 사이여야 합니다.")
            
        if self.config['profit_rate'] <= 0 or self.config['profit_rate'] > 1:
            errors.append("목표 수익률은 0%보다 크고 100% 이하여야 합니다.")
            
        if self.config['loss_rate'] >= 0 or self.config['loss_rate'] < -1:
            errors.append("손절률은 0%보다 작고 -100% 이상이어야 합니다.")
            
        if self.config['volume_spike_threshold'] < 1.1:
            errors.append("거래량 급등 임계값은 1.1배 이상이어야 합니다.")
            
        if self.config['check_interval'] < 10:
            errors.append("체크 간격은 10초 이상이어야 합니다.")
            
        if self.config['daily_loss_limit'] > 0:
            errors.append("일일 손실 한도는 음수여야 합니다.")
            
        # 논리적 관계 검사
        if self.config['min_balance_for_buy'] > self.config['investment_amount']:
            errors.append("매수 최소 잔고는 투자 금액보다 작거나 같아야 합니다.")
        
        return len(errors) == 0, errors

# 싱글톤 인스턴스
_config_manager = None

def get_config_manager() -> ConfigManager:
    """ConfigManager 싱글톤 인스턴스 반환"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager
