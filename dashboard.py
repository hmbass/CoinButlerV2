"""
Streamlit 기반 웹 대시보드
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import time
import os
import logging
from dotenv import load_dotenv

from trade_bot import get_bot
from risk_manager import get_risk_manager
from trade_utils import get_upbit_api
from ai_performance_tracker import get_ai_performance_tracker
from config_manager import get_config_manager

# 환경변수 로드
load_dotenv()

# 로거 설정
logger = logging.getLogger(__name__)
if not logger.handlers:
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# 페이지 설정
st.set_page_config(
    page_title="CoinButler 모니터링",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 스타일 설정
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #1f4037, #99f2c8);
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: #f0f2f6;
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #1f77b4;
    }
    .profit-positive {
        color: #00d4aa;
        font-weight: bold;
    }
    .profit-negative {
        color: #ff4b4b;
        font-weight: bold;
    }
    .status-running {
        color: #00d4aa;
    }
    .status-stopped {
        color: #ff4b4b;
    }
    .status-paused {
        color: #ffa726;
    }
</style>
""", unsafe_allow_html=True)

def init_session_state():
    """세션 상태 초기화"""
    if 'last_update' not in st.session_state:
        st.session_state.last_update = datetime.now()
    if 'auto_refresh' not in st.session_state:
        st.session_state.auto_refresh = True

def format_currency(amount):
    """통화 포맷팅"""
    return f"{amount:,.0f}원"

def format_percentage(rate):
    """퍼센트 포맷팅"""
    return f"{rate:+.2f}%"

def get_status_color(status):
    """상태에 따른 색상 반환"""
    colors = {
        'running': '#00d4aa',
        'stopped': '#ff4b4b',
        'paused': '#ffa726'
    }
    return colors.get(status, '#666666')

def get_system_status():
    """시스템 상태 정보 조회 (봇 상태 확인 제거)"""
    try:
        import json
        
        # 일일 손익 정보
        daily_pnl = 0
        if os.path.exists("daily_pnl.json"):
            try:
                with open("daily_pnl.json", 'r', encoding='utf-8') as f:
                    data = json.load(f)
                today = datetime.now().date().isoformat()
                daily_pnl = data.get(today, 0)
            except:
                daily_pnl = 0
        
        # 거래 통계 (간단 버전)
        trading_stats = {'total_trades': 0, 'win_rate': 0, 'total_pnl': 0}
        if os.path.exists("trade_history.csv"):
            try:
                import pandas as pd
                df = pd.read_csv("trade_history.csv")
                if not df.empty:
                    sell_trades = df[df['action'] == 'SELL']
                    if not sell_trades.empty:
                        trading_stats['total_trades'] = len(sell_trades)
                        winning_trades = len(sell_trades[sell_trades['profit_loss'] > 0])
                        trading_stats['win_rate'] = (winning_trades / len(sell_trades)) * 100
                        trading_stats['total_pnl'] = sell_trades['profit_loss'].sum()
            except:
                pass
        
        # 실제 업비트 계좌 정보 조회
        upbit_api = get_upbit_api()
        actual_upbit_balances = {}
        try:
            accounts = upbit_api.get_accounts()
            for account in accounts:
                currency = account.get('currency')
                balance = float(account.get('balance', 0))
                if currency != 'KRW' and balance > 0:  # 코인 잔고만 (KRW 제외)
                    market = f"KRW-{currency}"
                    actual_upbit_balances[market] = {
                        'currency': currency,
                        'balance': balance,
                        'avg_buy_price': float(account.get('avg_buy_price', 0)),
                        'locked': float(account.get('locked', 0))
                    }
        except Exception as e:
            logger.error(f"업비트 실제 잔고 조회 실패: {e}")
        
        # 현재 포지션 정보 (positions.json에서 읽기)
        positions_data = {}
        total_positions = 0
        
        if os.path.exists("positions.json"):
            try:
                with open("positions.json", 'r', encoding='utf-8') as f:
                    positions_file_data = json.load(f)
                    
                for market, pos_data in positions_file_data.items():
                    if pos_data.get('status') == 'open':
                        try:
                            # 현재가 조회해서 실시간 손익 계산
                            upbit_api = get_upbit_api()
                            current_price = upbit_api.get_current_price(market)
                            
                            if current_price:
                                entry_price = pos_data['entry_price']
                                quantity = pos_data['quantity']
                                investment_amount = pos_data['investment_amount']
                                current_value = quantity * current_price
                                pnl = current_value - investment_amount
                                pnl_rate = (pnl / investment_amount) * 100
                                
                                positions_data[market] = {
                                    'entry_price': entry_price,
                                    'current_price': current_price,
                                    'quantity': quantity,
                                    'investment_amount': investment_amount,
                                    'current_value': current_value,
                                    'pnl': pnl,
                                    'pnl_rate': pnl_rate,
                                    'entry_time': pos_data['entry_time']
                                }
                                total_positions += 1
                        except:
                            # API 호출 실패 시 기본 정보만 표시
                            positions_data[market] = {
                                'entry_price': pos_data['entry_price'],
                                'current_price': 0,
                                'quantity': pos_data['quantity'],
                                'investment_amount': pos_data['investment_amount'],
                                'current_value': 0,
                                'pnl': 0,
                                'pnl_rate': 0,
                                'entry_time': pos_data['entry_time']
                            }
                            total_positions += 1
            except:
                pass
        
        # KRW 잔고 (API 호출)
        krw_balance = 0
        try:
            upbit_api = get_upbit_api()
            krw_balance = upbit_api.get_krw_balance()
        except:
            krw_balance = 0
        
        # 실제 업비트 잔고와 positions.json 동기화 분석
        sync_status = _analyze_balance_sync(actual_upbit_balances, positions_data)
        
        return {
            'krw_balance': krw_balance,
            'daily_pnl': daily_pnl,
            'trading_stats': trading_stats,
            'positions': {
                'total_positions': total_positions,
                'max_positions': int(os.getenv('MAX_POSITIONS', 3)),
                'available_slots': int(os.getenv('MAX_POSITIONS', 3)) - total_positions,
                'positions': positions_data
            },
            'actual_upbit_balances': actual_upbit_balances,  # 실제 업비트 잔고
            'sync_status': sync_status  # 동기화 상태
        }
    except Exception as e:
        st.error(f"시스템 상태 조회 오류: {e}")
        return {
            'krw_balance': 0,
            'daily_pnl': 0,
            'trading_stats': {'total_trades': 0, 'win_rate': 0, 'total_pnl': 0},
            'positions': {'total_positions': 0, 'max_positions': 3, 'available_slots': 3, 'positions': {}},
            'actual_upbit_balances': {},
            'sync_status': {'is_synced': True, 'differences': [], 'needs_sync': False}
        }

def _analyze_balance_sync(actual_upbit_balances: dict, positions_data: dict) -> dict:
    """실제 업비트 잔고와 positions.json 동기화 상태 분석"""
    try:
        differences = []
        needs_sync = False
        
        # positions.json에는 있지만 실제 업비트에는 없는 종목
        for market, pos_data in positions_data.items():
            if market not in actual_upbit_balances:
                differences.append({
                    'type': 'missing_in_upbit',
                    'market': market,
                    'description': f"{market.replace('KRW-', '')} - 봇 기록에는 있지만 실제 업비트에는 없음",
                    'bot_amount': pos_data.get('quantity', 0),
                    'upbit_amount': 0
                })
                needs_sync = True
        
        # 실제 업비트에는 있지만 positions.json에는 없는 종목  
        for market, upbit_data in actual_upbit_balances.items():
            if market not in positions_data:
                differences.append({
                    'type': 'missing_in_bot',
                    'market': market,
                    'description': f"{market.replace('KRW-', '')} - 실제 업비트에는 있지만 봇 기록에는 없음 (수동 거래 의심)",
                    'bot_amount': 0,
                    'upbit_amount': upbit_data['balance']
                })
                needs_sync = True
        
        # 둘 다 있지만 수량이 다른 경우
        for market in set(positions_data.keys()) & set(actual_upbit_balances.keys()):
            bot_quantity = positions_data[market].get('quantity', 0)
            upbit_quantity = actual_upbit_balances[market]['balance']
            
            # 소량 차이는 무시 (거래 수수료 등으로 인한 차이)
            if abs(bot_quantity - upbit_quantity) > 0.001:  # 0.001개 이상 차이
                differences.append({
                    'type': 'quantity_mismatch',
                    'market': market,
                    'description': f"{market.replace('KRW-', '')} - 수량 불일치 (부분 매도/매수 의심)",
                    'bot_amount': bot_quantity,
                    'upbit_amount': upbit_quantity
                })
                needs_sync = True
        
        return {
            'is_synced': not needs_sync,
            'differences': differences,
            'needs_sync': needs_sync,
            'total_differences': len(differences)
        }
        
    except Exception as e:
        logger.error(f"잔고 동기화 분석 오류: {e}")
        return {
            'is_synced': True,  # 오류 시 안전하게 동기화됨으로 표시
            'differences': [],
            'needs_sync': False,
            'error': str(e)
        }

def _sync_with_upbit(actual_upbit_balances: dict) -> bool:
    """실제 업비트 잔고를 기준으로 positions.json 동기화"""
    try:
        import json
        
        logger.info("🔄 업비트 잔고와 동기화 시작...")
        
        # 현재 positions.json 읽기
        current_positions = {}
        if os.path.exists("positions.json"):
            try:
                with open("positions.json", 'r', encoding='utf-8') as f:
                    current_positions = json.load(f)
            except Exception as e:
                logger.error(f"positions.json 읽기 실패: {e}")
                current_positions = {}
        
        # 새로운 포지션 데이터 구성
        new_positions = {}
        
        # 실제 업비트 잔고 기반으로 포지션 생성
        for market, balance_info in actual_upbit_balances.items():
            coin_name = market.replace('KRW-', '')
            quantity = balance_info['balance']
            avg_buy_price = balance_info['avg_buy_price']
            
            if quantity > 0.001:  # 소량은 무시
                # 기존 positions.json에서 정보가 있으면 유지, 없으면 새로 생성
                if market in current_positions:
                    # 기존 데이터 유지하되 수량과 가격만 업데이트
                    existing_pos = current_positions[market].copy()
                    existing_pos['quantity'] = quantity
                    existing_pos['entry_price'] = avg_buy_price if avg_buy_price > 0 else existing_pos.get('entry_price', 0)
                    existing_pos['status'] = 'open'
                    new_positions[market] = existing_pos
                else:
                    # 새로운 수동 거래로 추정되는 포지션 생성
                    investment_amount = quantity * avg_buy_price if avg_buy_price > 0 else 30000
                    new_positions[market] = {
                        'market': market,
                        'entry_price': avg_buy_price if avg_buy_price > 0 else 0,
                        'quantity': quantity,
                        'investment_amount': investment_amount,
                        'buy_time': datetime.now().isoformat(),
                        'status': 'open',
                        'source': 'manual_sync'  # 수동 동기화로 생성됨을 표시
                    }
                
                logger.info(f"🔄 동기화: {coin_name} {quantity:.6f}개")
        
        # 백업 파일 생성
        backup_file = f"positions_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        try:
            if current_positions:
                with open(backup_file, 'w', encoding='utf-8') as f:
                    json.dump(current_positions, f, ensure_ascii=False, indent=2)
                logger.info(f"📋 기존 포지션 백업: {backup_file}")
        except Exception as e:
            logger.warning(f"백업 파일 생성 실패: {e}")
        
        # 새로운 positions.json 저장
        with open("positions.json", 'w', encoding='utf-8') as f:
            json.dump(new_positions, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✅ 업비트 잔고 동기화 완료: {len(new_positions)}개 종목")
        
        # 동기화 기록을 CSV에도 추가
        _record_manual_sync(actual_upbit_balances, new_positions)
        
        return True
        
    except Exception as e:
        logger.error(f"업비트 잔고 동기화 실패: {e}")
        return False

def _record_manual_sync(upbit_balances: dict, synced_positions: dict):
    """수동 동기화 기록을 trade_history.csv에 추가"""
    try:
        sync_records = []
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        for market, balance_info in upbit_balances.items():
            coin_name = market.replace('KRW-', '')
            sync_records.append({
                'timestamp': current_time,
                'market': market,
                'action': 'SYNC',
                'price': balance_info['avg_buy_price'],
                'quantity': balance_info['balance'],
                'amount': balance_info['balance'] * balance_info['avg_buy_price'],
                'profit_loss': 0,  # 동기화는 손익 없음
                'status': '수동 거래 동기화',
                'source': 'manual_trade_detection'
            })
        
        if sync_records:
            # 기존 trade_history.csv에 추가
            if os.path.exists("trade_history.csv"):
                existing_df = pd.read_csv("trade_history.csv")
                sync_df = pd.DataFrame(sync_records)
                combined_df = pd.concat([existing_df, sync_df], ignore_index=True)
            else:
                combined_df = pd.DataFrame(sync_records)
            
            combined_df.to_csv("trade_history.csv", index=False)
            logger.info(f"📝 수동 거래 동기화 기록 저장: {len(sync_records)}건")
            
    except Exception as e:
        logger.error(f"수동 동기화 기록 실패: {e}")

def main():
    """메인 대시보드"""
    init_session_state()
    
    # 헤더
    st.markdown("""
    <div class="main-header">
        <h1 style="color: white; margin: 0;">📊 CoinButler 모니터링</h1>
        <p style="color: white; margin: 0; opacity: 0.8;">실시간 거래 현황 및 포지션 모니터링</p>
    </div>
    """, unsafe_allow_html=True)
    
    # 사이드바 - 시스템 정보
    with st.sidebar:
        st.header("📊 시스템 정보")
        
        # 마지막 업데이트 시간만 표시
        st.caption(f"업데이트: {datetime.now().strftime('%H:%M:%S')}")
        
        st.markdown("---")
        
        # 거래 설정 정보
        st.subheader("⚙️ 거래 설정")
        
        investment_amount = float(os.getenv('INVESTMENT_AMOUNT', 30000))
        profit_rate = float(os.getenv('PROFIT_RATE', 0.03))
        loss_rate = float(os.getenv('LOSS_RATE', -0.02))
        daily_loss_limit = float(os.getenv('DAILY_LOSS_LIMIT', -50000))
        max_positions = int(os.getenv('MAX_POSITIONS', 3))
        
        st.metric("투자 금액", format_currency(investment_amount))
        st.metric("목표 수익률", f"{profit_rate*100:.1f}%")
        st.metric("손절 수익률", f"{loss_rate*100:.1f}%")
        st.metric("최대 포지션", f"{max_positions}개")
        st.metric("일일 손실한도", format_currency(daily_loss_limit))
        
        st.markdown("---")
        
        # 자동 새로고침 설정
        st.subheader("🔄 새로고침")
        st.session_state.auto_refresh = st.checkbox("자동 새로고침 (5초)", value=st.session_state.auto_refresh)
        
        if st.button("수동 새로고침", use_container_width=True):
            st.session_state.last_update = datetime.now()
            st.rerun()
            
        st.markdown("---")
        
        # 간단한 안내
        st.subheader("💡 안내")
        st.info("""
        **실시간 모니터링 대시보드**
        - 자동 새로고침으로 실시간 업데이트
        - 보유 종목 상태 및 손익 확인
        - 거래 내역 및 통계 제공
        """)
    
    # 메인 컨텐츠
    system_status = get_system_status()
    risk_manager = get_risk_manager()
    
    # 상단 메트릭
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="💰 KRW 잔고",
            value=format_currency(system_status['krw_balance']),
            delta=None
        )
    
    with col2:
        daily_pnl = system_status['daily_pnl']
        pnl_color = "normal" if daily_pnl >= 0 else "inverse"
        st.metric(
            label="📊 일일 손익",
            value=format_currency(daily_pnl),
            delta=format_percentage((daily_pnl / 30000) * 100) if daily_pnl != 0 else None,
            delta_color=pnl_color
        )
    
    with col3:
        positions_info = system_status['positions']
        st.metric(
            label="📋 보유 포지션",
            value=f"{positions_info['total_positions']}/{positions_info['max_positions']}",
            delta=f"여유: {positions_info['available_slots']}개"
        )
    
    with col4:
        trading_stats = system_status['trading_stats']
        st.metric(
            label="🎯 승률",
            value=f"{trading_stats['win_rate']:.1f}%",
            delta=f"총 {trading_stats['total_trades']}회"
        )
    
    # 탭 생성
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📊 대시보드", "💼 보유 종목", "📈 거래 내역", "🤖 AI 성과", "⚙️ 설정", "🔄 실제 잔고"])
    
    with tab1:
        show_realtime_status(system_status, risk_manager)
    
    with tab2:
        show_positions(system_status, risk_manager)
    
    with tab3:
        show_trading_history()
    
    with tab4:
        show_ai_performance()
    
    with tab5:
        show_settings()
    
    with tab6:
        show_actual_upbit_balances(system_status)
    
    # 자동 새로고침
    if st.session_state.auto_refresh:
        time.sleep(5)
        st.rerun()

def show_realtime_status(system_status, risk_manager):
    """실시간 현황 탭"""
    st.subheader("📊 실시간 거래 현황")
    
    # 🚨 동기화 상태 최우선 표시
    sync_status = system_status.get('sync_status', {})
    if not sync_status.get('is_synced', True):
        st.error(f"⚠️ **실제 업비트 계좌와 불일치 감지!** ({sync_status.get('total_differences', 0)}개 차이점)")
        st.write("📱 **업비트 앱에서 직접 거래한 내역이 감지되었습니다.**")
        
        with st.expander("🔍 상세 차이점 및 해결방법", expanded=True):
            differences = sync_status.get('differences', [])
            for diff in differences:
                if diff['type'] == 'missing_in_bot':
                    st.warning(f"🔸 **{diff['description']}**")
                    st.write(f"   📊 실제 보유량: **{diff['upbit_amount']:.6f}개**")
                    st.write(f"   💡 **업비트 앱에서 직접 매수한 것으로 추정됩니다.**")
                elif diff['type'] == 'missing_in_upbit':
                    st.error(f"🔸 **{diff['description']}**") 
                    st.write(f"   📋 봇 기록량: **{diff['bot_amount']:.6f}개**")
                    st.write(f"   💡 **업비트 앱에서 직접 매도한 것으로 추정됩니다.**")
                elif diff['type'] == 'quantity_mismatch':
                    st.warning(f"🔸 **{diff['description']}**")
                    st.write(f"   📋 봇 기록: **{diff['bot_amount']:.6f}개**")
                    st.write(f"   📊 실제 보유: **{diff['upbit_amount']:.6f}개**")
                    st.write(f"   💡 **부분 매도/매수가 발생한 것으로 추정됩니다.**")
                
                st.divider()
        
        # 동기화 버튼
        col_sync1, col_sync2, col_sync3 = st.columns(3)
        with col_sync1:
            if st.button("🔄 **실제 업비트 잔고와 동기화**", type="primary"):
                if _sync_with_upbit(system_status['actual_upbit_balances']):
                    st.success("✅ 동기화가 완료되었습니다!")
                    st.info("🔄 새로고침하여 변경사항을 확인하세요.")
                    time.sleep(2)
                    st.rerun()
                else:
                    st.error("❌ 동기화에 실패했습니다. 로그를 확인해주세요.")
        
        with col_sync2:
            if st.button("🔍 실제 업비트 잔고 보기"):
                st.subheader("📊 실제 업비트 계좌 현황")
                actual_balances = system_status.get('actual_upbit_balances', {})
                if actual_balances:
                    for market, balance_info in actual_balances.items():
                        coin_name = market.replace('KRW-', '')
                        st.write(f"💰 **{coin_name}**: {balance_info['balance']:.6f}개")
                        st.write(f"   평균 매수가: {balance_info['avg_buy_price']:,.0f}원")
                        st.divider()
                else:
                    st.info("📋 실제 업비트에 보유 중인 코인이 없습니다.")
        
        with col_sync3:
            if st.button("⚠️ 수동 거래 알림 해제"):
                st.session_state['manual_trade_dismissed'] = True
                st.rerun()
    else:
        st.success("✅ 실제 업비트 계좌와 완전히 동기화됨")
        if st.button("🔍 동기화 상태 재확인"):
            st.rerun()
    
    # 현재 포지션 요약
    positions_info = system_status.get('positions', {})
    positions_data = positions_info.get('positions', {})
    
    # 포지션 요약 계산
    total_investment = 0
    total_current_value = 0
    total_pnl = 0
    
    if positions_data:  # 포지션 데이터가 있는 경우에만
        for market, pos_info in positions_data.items():
            if isinstance(pos_info, dict) and pos_info.get('current_price', 0) > 0:
                total_investment += pos_info.get('investment_amount', 0)
                total_current_value += pos_info.get('current_value', 0)
                total_pnl += pos_info.get('pnl', 0)
    
    # 계정 정보 섹션 (항상 표시)
    st.subheader("💰 계정 현황")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        krw_balance = system_status.get('krw_balance', 0)
        st.metric("KRW 잔고", format_currency(krw_balance))
    
    with col2:
        daily_pnl = system_status.get('daily_pnl', 0)
        pnl_color = "normal" if daily_pnl >= 0 else "inverse"
        st.metric("오늘 실현손익", format_currency(daily_pnl), delta_color=pnl_color)
    
    with col3:
        total_positions = positions_info.get('total_positions', 0)
        max_positions = positions_info.get('max_positions', 3)
        st.metric("보유 포지션", f"{total_positions}/{max_positions}개")
    
    with col4:
        if total_investment > 0:
            total_pnl_rate = (total_pnl / total_investment * 100)
            st.metric("미실현 손익", format_currency(total_pnl), f"{total_pnl_rate:+.2f}%")
        else:
            st.metric("미실현 손익", "0원", "0.00%")
    
    # 포지션이 있는 경우 추가 요약 정보
    if positions_data:
        st.subheader("💼 포지션 요약")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("총 투자금액", format_currency(total_investment))
        with col2:
            st.metric("현재 가치", format_currency(total_current_value))
        with col3:
            available_balance = system_status.get('krw_balance', 0)
            st.metric("사용 가능 잔고", format_currency(available_balance))
    
    st.markdown("---")
    
    # 주요 시장 정보 및 통계
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("💹 주요 코인 현황")
        try:
            upbit_api = get_upbit_api()
            major_coins = ["KRW-BTC", "KRW-ETH", "KRW-XRP"]
            
            for coin in major_coins:
                try:
                    price = upbit_api.get_current_price(coin)
                    if price:
                        coin_name = coin.replace('KRW-', '')
                        st.metric(f"{coin_name} 현재가", f"{price:,.0f}원")
                except:
                    continue
        except:
            st.error("시장 정보 로드 실패")
    
    with col2:
        st.subheader("📈 거래 성과")
        stats = system_status['trading_stats']
        
        # 거래 통계 메트릭
        col2_1, col2_2 = st.columns(2)
        
        with col2_1:
            st.metric("총 거래 횟수", f"{stats['total_trades']}회")
            st.metric("수익 거래", f"{stats.get('winning_trades', 0)}회")
            
        with col2_2:
            st.metric("거래 승률", f"{stats['win_rate']:.1f}%")
            st.metric("평균 손익", format_currency(stats.get('avg_profit', 0)))
        
        # 일일 손익 표시
        daily_pnl = system_status['daily_pnl']
        pnl_color = "normal" if daily_pnl >= 0 else "inverse"
        st.metric(
            "오늘 실현 손익",
            format_currency(daily_pnl),
            delta_color=pnl_color
        )
    
    # 포지션 상태 정보 (봇 상태 표시 제거)
    st.markdown("---")
    st.subheader("📊 투자 현황")
    
    col1, col2 = st.columns(2)
    
    with col1:
        position_status = f"{positions_info['total_positions']}/{positions_info['max_positions']}"
        st.info(f"**보유 포지션:** {position_status}")
    
    with col2:
        investment_amount = float(os.getenv('INVESTMENT_AMOUNT', 30000))
        can_trade = "가능" if system_status['krw_balance'] >= investment_amount else "불가능"
        st.info(f"**신규 매수:** {can_trade}")
    
    # 최근 활동 (거래 내역에서 최근 5건)
    st.markdown("---")
    st.subheader("📋 최근 거래")
    
    try:
        if os.path.exists("trade_history.csv"):
            df = pd.read_csv("trade_history.csv")
            if not df.empty:
                recent_trades = df.tail(5).sort_values('timestamp', ascending=False)
                
                for _, trade in recent_trades.iterrows():
                    action_icon = "🟢" if trade['action'] == 'BUY' else "🔴"
                    market_name = trade['market'].replace('KRW-', '')
                    timestamp = pd.to_datetime(trade['timestamp']).strftime('%m-%d %H:%M')
                    
                    if trade['action'] == 'SELL' and trade['profit_loss'] != 0:
                        pnl_text = f"({trade['profit_loss']:+,.0f}원)"
                        st.write(f"{action_icon} **{market_name}** {trade['action']} - {timestamp} {pnl_text}")
                    else:
                        st.write(f"{action_icon} **{market_name}** {trade['action']} - {timestamp}")
            else:
                st.info("거래 내역이 없습니다.")
        else:
            st.info("거래 내역 파일이 없습니다.")
    except Exception as e:
        st.error(f"최근 거래 조회 오류: {e}")

def show_positions(system_status, risk_manager):
    """보유 종목 상세 정보 탭"""
    st.subheader("💼 보유 종목 현황")

    # 동기화 상태 간단 표시
    sync_status = system_status.get('sync_status', {})
    if not sync_status.get('is_synced', True):
        st.warning(f"⚠️ 실제 업비트와 {sync_status.get('total_differences', 0)}개 차이점 있음 - 📊 대시보드 탭에서 동기화하세요")

    positions_info = system_status.get('positions', {})
    positions = positions_info.get('positions', {})
    actual_balances = system_status.get('actual_upbit_balances', {})
    
    if not positions:
        st.info("🔍 현재 보유 중인 종목이 없습니다.")
        st.write("새로운 거래 기회를 기다리고 있습니다.")
        
        # 시스템 정보 표시
        st.subheader("📊 시스템 정보")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("KRW 잔고", format_currency(system_status.get('krw_balance', 0)))
        with col2:
            max_positions = positions_info.get('max_positions', 3)
            st.metric("최대 포지션", f"0/{max_positions}개")
        with col3:
            st.metric("사용 가능 슬롯", f"{max_positions}개")
        return
    
    # 전체 포지션 요약 (상단)
    total_investment = 0
    total_current_value = 0
    total_pnl = 0
    
    for market, pos_info in positions.items():
        if pos_info['current_price'] > 0:
            total_investment += pos_info['investment_amount']
            total_current_value += pos_info['current_value']
            total_pnl += pos_info['pnl']
    
    if total_investment > 0:
        total_pnl_rate = (total_pnl / total_investment) * 100
        
        st.subheader("📊 전체 포지션 요약")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("총 투자금액", format_currency(total_investment))
        with col2:
            st.metric("현재 가치", format_currency(total_current_value))
        with col3:
            pnl_color = "normal" if total_pnl >= 0 else "inverse"
            st.metric(
                "미실현 손익", 
                format_currency(total_pnl),
                delta_color=pnl_color
            )
        with col4:
            st.metric("수익률", f"{total_pnl_rate:+.2f}%")
    
    st.markdown("---")
    
    # 개별 종목 상세 정보
    st.subheader("📈 개별 종목 상세")
    
    for i, (market, pos_info) in enumerate(positions.items()):
        coin_name = market.replace('KRW-', '')
        
        # 실제 업비트 잔고와 비교
        actual_balance_info = actual_balances.get(market)
        is_synced = True
        sync_warning = ""
        
        if actual_balance_info:
            bot_quantity = pos_info.get('quantity', 0)
            upbit_quantity = actual_balance_info['balance']
            
            if abs(bot_quantity - upbit_quantity) > 0.001:
                is_synced = False
                if upbit_quantity > bot_quantity:
                    sync_warning = f"⚠️ 실제 보유량이 더 많음 (+{upbit_quantity - bot_quantity:.6f}개)"
                else:
                    sync_warning = f"⚠️ 실제 보유량이 더 적음 ({upbit_quantity - bot_quantity:.6f}개)"
        else:
            is_synced = False
            sync_warning = "❌ 실제 업비트에서 이 종목을 찾을 수 없음"
        
        # 각 종목별 컨테이너
        with st.container():
            # 동기화 상태 알림 (종목별)
            if not is_synced:
                st.warning(f"🔸 **{coin_name}** {sync_warning}")
            
            # 종목 헤더
            col_header1, col_header2 = st.columns([3, 1])
            
            with col_header1:
                if pos_info['current_price'] > 0 and pos_info['pnl'] >= 0:
                    st.markdown(f"### 🟢 **{coin_name}** ({market})")
                elif pos_info['current_price'] > 0 and pos_info['pnl'] < 0:
                    st.markdown(f"### 🔴 **{coin_name}** ({market})")
                else:
                    st.markdown(f"### ⚪ **{coin_name}** ({market})")
            
            with col_header2:
                if pos_info['current_price'] > 0:
                    pnl_rate = pos_info['pnl_rate']
                    if pnl_rate >= 0:
                        st.markdown(f"**<span style='color:#00d4aa'>+{pnl_rate:.2f}%</span>**", unsafe_allow_html=True)
                    else:
                        st.markdown(f"**<span style='color:#ff4b4b'>{pnl_rate:.2f}%</span>**", unsafe_allow_html=True)
            
            # 종목 상세 정보
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.write("**진입 정보**")
                st.write(f"🎯 진입가: **{pos_info['entry_price']:,.0f}원**")
                st.write(f"📊 수량: **{pos_info['quantity']:.6f}**")
                entry_time = pos_info.get('entry_time', '')
                if entry_time:
                    formatted_time = pd.to_datetime(entry_time).strftime('%m-%d %H:%M') if entry_time else "알 수 없음"
                    st.write(f"⏰ 진입: **{formatted_time}**")
            
            with col2:
                st.write("**현재 정보**")
                if pos_info['current_price'] > 0:
                    st.write(f"💰 현재가: **{pos_info['current_price']:,.0f}원**")
                    price_diff = pos_info['current_price'] - pos_info['entry_price']
                    price_diff_rate = (price_diff / pos_info['entry_price']) * 100
                    if price_diff >= 0:
                        st.write(f"📈 가격변동: **+{price_diff:,.0f}원 (+{price_diff_rate:.2f}%)**")
                    else:
                        st.write(f"📉 가격변동: **{price_diff:,.0f}원 ({price_diff_rate:.2f}%)**")
                else:
                    st.write("💰 현재가: **조회 실패**")
                    st.write("📈 가격변동: **-**")
            
            with col3:
                st.write("**투자 현황**")
                st.write(f"💵 투자금액: **{pos_info['investment_amount']:,.0f}원**")
                if pos_info['current_price'] > 0:
                    st.write(f"💎 현재가치: **{pos_info['current_value']:,.0f}원**")
                else:
                    st.write("💎 현재가치: **조회 실패**")
            
            with col4:
                st.write("**손익 현황**")
                if pos_info['current_price'] > 0:
                    if pos_info['pnl'] >= 0:
                        st.write(f"💹 손익: **<span style='color:#00d4aa'>+{pos_info['pnl']:,.0f}원</span>**", unsafe_allow_html=True)
                    else:
                        st.write(f"💹 손익: **<span style='color:#ff4b4b'>{pos_info['pnl']:,.0f}원</span>**", unsafe_allow_html=True)
                    
                    # 목표가/손절가 표시 (설정값 기반)
                    profit_rate = float(os.getenv('PROFIT_RATE', 0.03))
                    loss_rate = float(os.getenv('LOSS_RATE', -0.02))
                    profit_target = pos_info['entry_price'] * (1 + profit_rate)
                    loss_target = pos_info['entry_price'] * (1 + loss_rate)
                    st.write(f"🎯 목표가: **{profit_target:,.0f}원** ({profit_rate*100:+.1f}%)")
                    st.write(f"⛔ 손절가: **{loss_target:,.0f}원** ({loss_rate*100:+.1f}%)")
                else:
                    st.write("💹 손익: **조회 실패**")
            
            st.markdown("---")
    
    # 하단 표 형태로도 제공
    st.subheader("📋 포지션 요약표")
    
    position_data = []
    for market, pos_info in positions.items():
        if pos_info['current_price'] > 0:
            position_data.append({
                '종목': market.replace('KRW-', ''),
                '진입가': f"{pos_info['entry_price']:,.0f}원",
                '현재가': f"{pos_info['current_price']:,.0f}원",
                '수량': f"{pos_info['quantity']:.6f}",
                '투자금액': f"{pos_info['investment_amount']:,.0f}원",
                '현재가치': f"{pos_info['current_value']:,.0f}원",
                '손익': f"{pos_info['pnl']:,.0f}원",
                '손익률': f"{pos_info['pnl_rate']:+.2f}%"
            })
        else:
            position_data.append({
                '종목': market.replace('KRW-', ''),
                '진입가': f"{pos_info['entry_price']:,.0f}원",
                '현재가': "조회 실패",
                '수량': f"{pos_info['quantity']:.6f}",
                '투자금액': f"{pos_info['investment_amount']:,.0f}원",
                '현재가치': "조회 실패",
                '손익': "조회 실패",
                '손익률': "조회 실패"
            })
    
    if position_data:
        df = pd.DataFrame(position_data)
        st.dataframe(df, use_container_width=True)

def show_trading_history():
    """거래 내역 탭"""
    st.subheader("📈 거래 내역")
    
    try:
        # CSV 파일에서 거래 내역 로드
        df = pd.read_csv("trade_history.csv")
        
        if df.empty or len(df) <= 1:  # 헤더만 있는 경우도 체크
            st.info("📝 아직 거래 내역이 없습니다.")
            st.write("봇이 시작되면 이곳에 거래 내역이 표시됩니다.")
            return
        
        # 최근 거래부터 표시
        df = df.sort_values('timestamp', ascending=False)
        
        # 날짜 필터
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input(
                "시작 날짜",
                value=datetime.now() - timedelta(days=7),
                max_value=datetime.now()
            )
        with col2:
            end_date = st.date_input(
                "종료 날짜",
                value=datetime.now(),
                max_value=datetime.now()
            )
        
        # 날짜 필터링
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        mask = (df['timestamp'].dt.date >= start_date) & (df['timestamp'].dt.date <= end_date)
        filtered_df = df.loc[mask]
        
        if filtered_df.empty:
            st.info("해당 기간에 거래 내역이 없습니다.")
            return
        
        # 거래 내역 테이블
        display_df = filtered_df.copy()
        display_df['timestamp'] = display_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
        display_df['market'] = display_df['market'].str.replace('KRW-', '')
        display_df['price'] = display_df['price'].apply(lambda x: f"{x:,.0f}원")
        display_df['amount'] = display_df['amount'].apply(lambda x: f"{x:,.0f}원")
        display_df['profit_loss'] = display_df['profit_loss'].apply(lambda x: f"{x:,.0f}원" if x != 0 else "-")
        
        st.dataframe(
            display_df[['timestamp', 'market', 'action', 'price', 'amount', 'profit_loss', 'status']],
            column_config={
                'timestamp': '시간',
                'market': '종목',
                'action': '구분',
                'price': '가격',
                'amount': '금액',
                'profit_loss': '손익',
                'status': '상태'
            },
            use_container_width=True
        )
        
        # 거래 통계
        st.subheader("📊 거래 통계")
        
        sell_trades = filtered_df[filtered_df['action'] == 'SELL']
        if not sell_trades.empty:
            total_trades = len(sell_trades)
            total_profit = sell_trades['profit_loss'].sum()
            winning_trades = len(sell_trades[sell_trades['profit_loss'] > 0])
            win_rate = (winning_trades / total_trades) * 100
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("총 거래", f"{total_trades}회")
            with col2:
                st.metric("총 손익", format_currency(total_profit))
            with col3:
                st.metric("승률", f"{win_rate:.1f}%")
            with col4:
                st.metric("평균 손익", format_currency(total_profit / total_trades))
        
    except FileNotFoundError:
        st.info("📝 거래 내역 파일이 없습니다.")
        st.write("봇이 시작되면 자동으로 거래 내역 파일이 생성됩니다.")
    except Exception as e:
        st.error(f"거래 내역 로드 오류: {e}")
        st.write("오류가 발생했지만 봇 동작에는 영향을 주지 않습니다.")

def show_ai_performance():
    """AI 추천 성과 표시"""
    st.header("🤖 AI 추천 성과 분석")
    
    try:
        tracker = get_ai_performance_tracker()
        
        # 기간 선택
        col1, col2 = st.columns([1, 3])
        with col1:
            days = st.selectbox(
                "분석 기간",
                [7, 14, 30, 60, 90],
                index=2,  # 기본값: 30일
                help="AI 추천 성과를 분석할 기간을 선택하세요"
            )
        
        # 성과 지표 가져오기
        metrics = tracker.get_performance_metrics(days)
        
        if metrics.total_recommendations == 0:
            st.info("📊 아직 AI 추천 데이터가 없습니다.")
            st.write("봇이 실행되고 AI가 추천을 시작하면 여기에 성과가 표시됩니다.")
            return
        
        # 주요 성과 지표
        st.subheader("📈 주요 성과 지표")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "총 추천 수", 
                metrics.total_recommendations,
                help="AI가 추천한 총 종목 수"
            )
        
        with col2:
            execution_rate = (metrics.executed_recommendations / metrics.total_recommendations * 100) if metrics.total_recommendations > 0 else 0
            st.metric(
                "실행률", 
                f"{execution_rate:.1f}%",
                delta=f"{metrics.executed_recommendations}회 실행",
                help="AI 추천 중 실제로 매수가 실행된 비율"
            )
        
        with col3:
            success_color = "normal"
            if metrics.success_rate >= 70:
                success_color = "inverse"
            elif metrics.success_rate <= 30:
                success_color = "off"
                
            st.metric(
                "성공률", 
                f"{metrics.success_rate:.1f}%",
                delta="수익 기준",
                help="매수 후 수익을 낸 거래의 비율"
            )
        
        with col4:
            return_color = "normal"
            if metrics.average_return > 2:
                return_color = "inverse"
            elif metrics.average_return < -2:
                return_color = "off"
                
            st.metric(
                "평균 수익률", 
                f"{metrics.average_return:.2f}%",
                delta=f"최고: {metrics.best_return:.2f}%",
                help="AI 추천으로 매수한 종목들의 평균 수익률"
            )
        
        # 신뢰도별 성과 분석
        st.subheader("🎯 신뢰도별 성과")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "높은 신뢰도 (8-10)", 
                f"{metrics.high_confidence_success_rate:.1f}%",
                help="신뢰도 8 이상 추천의 성공률"
            )
        
        with col2:
            st.metric(
                "중간 신뢰도 (6-7)", 
                f"{metrics.medium_confidence_success_rate:.1f}%",
                help="신뢰도 6-7 추천의 성공률"
            )
        
        with col3:
            st.metric(
                "낮은 신뢰도 (1-5)", 
                f"{metrics.low_confidence_success_rate:.1f}%",
                help="신뢰도 5 이하 추천의 성공률"
            )
        
        # 시장 상황별 성과
        st.subheader("📊 시장 상황별 성과")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "강세장 성과", 
                f"{metrics.bullish_market_success_rate:.1f}%",
                help="시장이 강세일 때의 AI 추천 성공률"
            )
        
        with col2:
            st.metric(
                "보합 성과", 
                f"{metrics.neutral_market_success_rate:.1f}%",
                help="시장이 보합일 때의 AI 추천 성공률"
            )
        
        with col3:
            st.metric(
                "약세장 성과", 
                f"{metrics.bearish_market_success_rate:.1f}%",
                help="시장이 약세일 때의 AI 추천 성과"
            )
        
        # 최근 추천 목록
        st.subheader("📋 최근 AI 추천 내역")
        recent_recs = tracker.get_recent_recommendations(15)
        
        if recent_recs:
            df_recs = pd.DataFrame(recent_recs)
            df_recs['timestamp'] = pd.to_datetime(df_recs['timestamp']).dt.strftime('%m-%d %H:%M')
            df_recs['executed'] = df_recs['executed'].map({True: '✅', False: '⏳'})
            df_recs['success'] = df_recs['success'].map({True: '🟢', False: '🔴', None: '⏳'})
            
            # 수익률 포맷팅
            df_recs['actual_return'] = df_recs['actual_return'].apply(
                lambda x: f"{x:.2f}%" if pd.notna(x) else "-"
            )
            
            # 컬럼명 한글화
            df_display = df_recs[['timestamp', 'recommended_coin', 'confidence', 'executed', 'actual_return', 'success', 'reason']].copy()
            df_display.columns = ['시간', '추천코인', '신뢰도', '실행', '수익률', '결과', '추천이유']
            
            st.dataframe(
                df_display,
                use_container_width=True,
                height=400
            )
        else:
            st.info("아직 AI 추천 내역이 없습니다.")
        
        # 성과 분석 차트
        if metrics.total_recommendations > 0:
            st.subheader("📈 성과 분석 차트")
            
            # 신뢰도별 성공률 차트
            confidence_data = {
                '신뢰도 구간': ['높음 (8-10)', '중간 (6-7)', '낮음 (1-5)'],
                '성공률': [
                    metrics.high_confidence_success_rate,
                    metrics.medium_confidence_success_rate,
                    metrics.low_confidence_success_rate
                ]
            }
            
            fig = px.bar(
                confidence_data, 
                x='신뢰도 구간', 
                y='성공률',
                title="신뢰도별 성공률 비교",
                color='성공률',
                color_continuous_scale='RdYlGn'
            )
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
            
            # 시장 상황별 성과 차트
            market_data = {
                '시장 상황': ['강세장', '보합', '약세장'],
                '성공률': [
                    metrics.bullish_market_success_rate,
                    metrics.neutral_market_success_rate,
                    metrics.bearish_market_success_rate
                ]
            }
            
            fig2 = px.bar(
                market_data, 
                x='시장 상황', 
                y='성공률',
                title="시장 상황별 성공률 비교",
                color='성공률',
                color_continuous_scale='RdYlBu'
            )
            fig2.update_layout(height=400)
            st.plotly_chart(fig2, use_container_width=True)
        
        # 성과 개선 제안
        st.subheader("💡 성과 개선 제안")
        
        suggestions = []
        
        if metrics.high_confidence_success_rate > metrics.medium_confidence_success_rate + 10:
            suggestions.append("🎯 높은 신뢰도 추천의 성과가 좋습니다. 신뢰도 임계값을 높이는 것을 고려해보세요.")
        
        if metrics.bullish_market_success_rate > metrics.bearish_market_success_rate + 20:
            suggestions.append("📈 강세장에서의 성과가 뛰어납니다. 약세장에서는 더욱 보수적인 접근이 필요할 수 있습니다.")
        
        if metrics.success_rate < 50:
            suggestions.append("⚠️ 성공률이 50% 미만입니다. AI 모델 파라미터 조정이나 추가 지표 도입을 검토해보세요.")
        
        if metrics.average_return < 1:
            suggestions.append("📊 평균 수익률이 낮습니다. 수익 목표를 상향 조정하거나 손절 기준을 최적화해보세요.")
        
        if not suggestions:
            suggestions.append("✅ 현재 AI 성과가 양호합니다. 지속적인 모니터링을 통해 성과를 유지하세요.")
        
        for suggestion in suggestions:
            st.write(suggestion)
        
        # 데이터 내보내기
        st.subheader("📤 데이터 내보내기")
        if st.button("AI 추천 데이터 CSV 다운로드"):
            csv_file = tracker.export_to_csv()
            if csv_file:
                st.success(f"✅ 데이터가 {csv_file}에 저장되었습니다.")
            else:
                st.error("❌ 데이터 내보내기 실패")
        
    except Exception as e:
        st.error(f"AI 성과 분석 오류: {e}")
        st.write("AI 성과 추적 시스템에 문제가 있습니다. 로그를 확인해주세요.")

def show_settings():
    """봇 설정 페이지"""
    st.header("⚙️ 봇 설정")
    
    try:
        config_manager = get_config_manager()
        current_config = config_manager.get_all_settings()
        
        # 설정 변경 감지용
        if 'config_changed' not in st.session_state:
            st.session_state.config_changed = False
        
        st.info("💡 설정을 변경하면 즉시 봇에 적용됩니다. 신중하게 설정해주세요.")
        
        # 거래 관련 설정
        st.subheader("💰 거래 설정")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # 매수 최소 잔고 설정
            min_balance = st.number_input(
                "매수 최소 잔고 (원)",
                min_value=5000,
                max_value=1000000,
                value=current_config['min_balance_for_buy'],
                step=5000,
                help="이 금액 이상일 때만 매수를 실행합니다. 현재 요청사항: 사용자 설정 가능"
            )
            
            # 기본 투자 금액
            investment_amount = st.number_input(
                "기본 투자 금액 (원)",
                min_value=5000,
                max_value=1000000,
                value=current_config['investment_amount'],
                step=5000,
                help="한 번에 투자할 기본 금액입니다."
            )
            
            # 최대 보유 종목 수
            max_positions = st.number_input(
                "최대 보유 종목 수 (개)",
                min_value=1,
                max_value=10,
                value=current_config['max_positions'],
                step=1,
                help="동시에 보유할 수 있는 최대 종목 수입니다. 현재 요청사항: 3개로 제한"
            )
        
        with col2:
            # 목표 수익률
            profit_rate = st.number_input(
                "목표 수익률 (%)",
                min_value=0.1,
                max_value=100.0,
                value=current_config['profit_rate'] * 100,
                step=0.1,
                help="이 수익률에 도달하면 자동 매도합니다."
            ) / 100
            
            # 손절률
            loss_rate = st.number_input(
                "손절률 (%)",
                min_value=-100.0,
                max_value=-0.1,
                value=current_config['loss_rate'] * 100,
                step=0.1,
                help="이 손실률에 도달하면 자동 손절합니다."
            ) / 100
            
            # 일일 손실 한도
            daily_loss_limit = st.number_input(
                "일일 손실 한도 (원)",
                min_value=-1000000,
                max_value=-1000,
                value=current_config['daily_loss_limit'],
                step=1000,
                help="하루 총 손실이 이 금액을 초과하면 봇을 정지합니다."
            )
        
        # 기술적 분석 설정
        st.subheader("📊 기술적 분석 설정")
        
        col3, col4 = st.columns(2)
        
        with col3:
            # 거래량 급등 임계값
            volume_spike_threshold = st.number_input(
                "거래량 급등 임계값 (배)",
                min_value=1.1,
                max_value=10.0,
                value=current_config['volume_spike_threshold'],
                step=0.1,
                help="평균 거래량의 몇 배 이상일 때 거래량 급등으로 판단할지 설정합니다."
            )
            
            # 가격 변동 임계값
            price_change_threshold = st.number_input(
                "가격 변동 임계값 (%)",
                min_value=1.0,
                max_value=50.0,
                value=current_config['price_change_threshold'] * 100,
                step=0.1,
                help="이 값을 초과하는 급격한 가격 변동은 제외합니다."
            ) / 100
        
        with col4:
            # AI 신뢰도 임계값
            ai_confidence_threshold = st.number_input(
                "AI 신뢰도 임계값",
                min_value=1,
                max_value=10,
                value=current_config['ai_confidence_threshold'],
                step=1,
                help="AI 추천 신뢰도가 이 값 이상일 때만 매수를 실행합니다."
            )
        
        # 시스템 설정
        st.subheader("🔧 시스템 설정")
        
        col5, col6 = st.columns(2)
        
        with col5:
            # 체크 간격
            check_interval = st.number_input(
                "체크 간격 (초)",
                min_value=10,
                max_value=300,
                value=current_config['check_interval'],
                step=10,
                help="봇이 시장을 체크하는 주기입니다."
            )
        
        with col6:
            # 시장 스캔 간격
            market_scan_interval = st.number_input(
                "시장 스캔 간격 (분)",
                min_value=1,
                max_value=60,
                value=current_config['market_scan_interval'],
                step=1,
                help="새로운 매수 기회를 찾는 주기입니다."
            )
        
        # 현재 설정 vs 새 설정 비교
        new_config = {
            'min_balance_for_buy': min_balance,
            'investment_amount': investment_amount,
            'max_positions': max_positions,
            'profit_rate': profit_rate,
            'loss_rate': loss_rate,
            'daily_loss_limit': daily_loss_limit,
            'volume_spike_threshold': volume_spike_threshold,
            'price_change_threshold': price_change_threshold,
            'ai_confidence_threshold': ai_confidence_threshold,
            'check_interval': check_interval,
            'market_scan_interval': market_scan_interval
        }
        
        # 변경사항 표시
        changes = []
        for key, new_value in new_config.items():
            old_value = current_config[key]
            if old_value != new_value:
                changes.append(f"• {get_setting_display_name(key)}: {format_setting_value(old_value)} → {format_setting_value(new_value)}")
        
        if changes:
            st.subheader("📝 변경사항")
            for change in changes:
                st.write(change)
        
        # 설정 저장 버튼
        col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 1])
        
        with col_btn1:
            if st.button("💾 설정 저장", type="primary"):
                # 유효성 검사
                is_valid, errors = config_manager.validate_config()
                
                # 새 설정으로 임시 업데이트해서 검사
                temp_config = current_config.copy()
                temp_config.update(new_config)
                config_manager.config = temp_config
                is_valid, errors = config_manager.validate_config()
                
                if is_valid:
                    if config_manager.update_multiple(new_config):
                        st.success("✅ 설정이 저장되었습니다!")
                        st.info("🔄 새로운 설정이 봇에 즉시 적용됩니다.")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ 설정 저장에 실패했습니다.")
                else:
                    st.error("❌ 설정값에 오류가 있습니다:")
                    for error in errors:
                        st.write(f"• {error}")
        
        with col_btn2:
            if st.button("🔄 기본값 복원"):
                if st.session_state.get('confirm_reset', False):
                    if config_manager.reset_to_default():
                        st.success("✅ 기본값으로 복원되었습니다!")
                        st.session_state.confirm_reset = False
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ 기본값 복원에 실패했습니다.")
                else:
                    st.warning("⚠️ 정말 기본값으로 복원하시겠습니까?")
                    st.session_state.confirm_reset = True
        
        with col_btn3:
            if st.button("📄 설정 파일 보기"):
                st.subheader("현재 설정 파일 내용")
                st.json(current_config)
        
        # 설정 설명
        st.subheader("ℹ️ 설정 가이드")
        
        with st.expander("💰 거래 설정 가이드"):
            st.write("""
            **매수 최소 잔고**: 이 금액 이상이 있을 때만 새로운 종목을 매수합니다.
            - 추천값: 30,000 - 100,000원
            - 너무 낮으면 소액으로 여러 번 매수될 수 있음
            
            **최대 보유 종목 수**: 동시에 보유할 수 있는 최대 종목 수입니다.
            - 3개로 설정하면 3개 종목 보유 시 추가 매수 중단
            - 매도 후에만 새로운 매수 가능
            - 리스크 분산과 집중 투자의 균형점
            
            **목표 수익률**: 이 수익률 도달 시 자동 매도
            - 추천값: 2-5%
            - 너무 높으면 매도 기회를 놓칠 수 있음
            
            **손절률**: 이 손실률 도달 시 자동 손절
            - 추천값: -1% ~ -3%
            - 리스크 관리에 매우 중요
            """)
        
        with st.expander("📊 기술적 분석 설정 가이드"):
            st.write("""
            **거래량 급등 임계값**: 평균 거래량 대비 몇 배 이상일 때 매수 신호로 판단
            - 추천값: 2.0 - 3.0배
            - 너무 낮으면 잦은 매수, 너무 높으면 기회 부족
            
            **AI 신뢰도 임계값**: AI 추천 신뢰도가 이 값 이상일 때만 매수
            - 추천값: 7-8 (최적화됨: 6→7로 상향조정)
            - 높을수록 안전하지만 기회 감소
            """)
        
        # 현재 적용된 설정 상태
        st.subheader("📊 현재 설정 상태")
        
        col_status1, col_status2, col_status3, col_status4 = st.columns(4)
        
        with col_status1:
            st.metric(
                "매수 최소 잔고",
                f"{current_config['min_balance_for_buy']:,}원",
                help="현재 설정된 매수 최소 잔고"
            )
        
        with col_status2:
            st.metric(
                "최대 보유 종목",
                f"{current_config['max_positions']}개",
                help="현재 설정된 최대 보유 종목 수"
            )
        
        with col_status3:
            st.metric(
                "목표 수익률",
                f"{current_config['profit_rate']*100:.1f}%",
                help="현재 설정된 목표 수익률"
            )
        
        with col_status4:
            st.metric(
                "손절률",
                f"{current_config['loss_rate']*100:.1f}%",
                help="현재 설정된 손절률"
            )
        
        # 마지막 업데이트 시간
        if 'last_updated' in current_config:
            try:
                last_updated = datetime.fromisoformat(current_config['last_updated'])
                st.caption(f"마지막 업데이트: {last_updated.strftime('%Y-%m-%d %H:%M:%S')}")
            except:
                pass
    
    except Exception as e:
        st.error(f"설정 페이지 오류: {e}")
        st.write("설정 시스템에 문제가 있습니다. 로그를 확인해주세요.")

def get_setting_display_name(key: str) -> str:
    """설정 키를 사용자 친화적 이름으로 변환"""
    names = {
        'min_balance_for_buy': '매수 최소 잔고',
        'investment_amount': '기본 투자 금액',
        'max_positions': '최대 보유 종목 수',
        'profit_rate': '목표 수익률',
        'loss_rate': '손절률',
        'daily_loss_limit': '일일 손실 한도',
        'volume_spike_threshold': '거래량 급등 임계값',
        'price_change_threshold': '가격 변동 임계값',
        'ai_confidence_threshold': 'AI 신뢰도 임계값',
        'check_interval': '체크 간격',
        'market_scan_interval': '시장 스캔 간격'
    }
    return names.get(key, key)

def format_setting_value(value) -> str:
    """설정값을 사용자 친화적 형식으로 포맷"""
    if isinstance(value, float):
        if 0 < value < 1:
            return f"{value*100:.1f}%"
        else:
            return f"{value:.2f}"
    elif isinstance(value, int):
        if abs(value) >= 1000:
            return f"{value:,}"
        else:
            return str(value)
    else:
        return str(value)

def show_actual_upbit_balances(system_status):
    """실제 업비트 계좌 현황 탭"""
    st.header("🔄 실제 업비트 계좌 현황")
    
    actual_balances = system_status.get('actual_upbit_balances', {})
    sync_status = system_status.get('sync_status', {})
    
    # 동기화 상태 상단 표시
    if sync_status.get('is_synced', True):
        st.success("✅ **봇 기록과 실제 업비트 계좌가 완전히 동기화되어 있습니다.**")
    else:
        st.error(f"⚠️ **{sync_status.get('total_differences', 0)}개의 차이점이 발견되었습니다.**")
        if st.button("🔄 지금 동기화하기", type="primary"):
            if _sync_with_upbit(actual_balances):
                st.success("✅ 동기화 완료!")
                st.rerun()
    
    # 새로고침 버튼
    col_refresh1, col_refresh2 = st.columns([1, 4])
    with col_refresh1:
        if st.button("🔄 새로고침"):
            st.rerun()
    
    st.divider()
    
    # 실제 업비트 잔고 표시
    if actual_balances:
        st.subheader("💰 실제 보유 코인 현황")
        
        # 총 투자 금액 계산
        total_investment_krw = 0
        total_current_value_krw = 0
        
        upbit_api = get_upbit_api()
        
        for market, balance_info in actual_balances.items():
            coin_name = market.replace('KRW-', '')
            quantity = balance_info['balance']
            avg_buy_price = balance_info['avg_buy_price']
            locked = balance_info['locked']
            
            # 현재가 조회
            try:
                current_price = upbit_api.get_current_price(market)
            except:
                current_price = 0
            
            # 투자 금액 및 현재 가치 계산
            investment_krw = quantity * avg_buy_price if avg_buy_price > 0 else 0
            current_value_krw = quantity * current_price if current_price > 0 else 0
            pnl = current_value_krw - investment_krw if investment_krw > 0 else 0
            pnl_rate = (pnl / investment_krw * 100) if investment_krw > 0 else 0
            
            total_investment_krw += investment_krw
            total_current_value_krw += current_value_krw
            
            # 각 코인 정보 표시
            with st.container():
                # 수익/손실에 따른 색상
                if pnl >= 0:
                    st.markdown(f"### 🟢 **{coin_name}** ({market})")
                else:
                    st.markdown(f"### 🔴 **{coin_name}** ({market})")
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("보유 수량", f"{quantity:.6f}", help="실제 업비트 보유량")
                    if locked > 0:
                        st.caption(f"🔒 주문중: {locked:.6f}")
                
                with col2:
                    st.metric("평균 매수가", f"{avg_buy_price:,.0f}원" if avg_buy_price > 0 else "정보 없음")
                    st.metric("현재가", f"{current_price:,.0f}원" if current_price > 0 else "조회 실패")
                
                with col3:
                    st.metric("투자 금액", f"{investment_krw:,.0f}원" if investment_krw > 0 else "계산 불가")
                    st.metric("현재 가치", f"{current_value_krw:,.0f}원" if current_value_krw > 0 else "계산 불가")
                
                with col4:
                    if pnl != 0:
                        pnl_color = "normal" if pnl >= 0 else "inverse"
                        st.metric(
                            "손익",
                            f"{pnl:+,.0f}원",
                            delta=f"{pnl_rate:+.2f}%",
                            delta_color=pnl_color
                        )
                    else:
                        st.metric("손익", "계산 불가")
                
                # 동기화 상태 표시
                positions_data = system_status.get('positions', {}).get('positions', {})
                if market in positions_data:
                    bot_quantity = positions_data[market].get('quantity', 0)
                    if abs(bot_quantity - quantity) <= 0.001:
                        st.success("✅ 봇 기록과 일치")
                    else:
                        quantity_diff = quantity - bot_quantity
                        st.warning(f"⚠️ 수량 차이: {quantity_diff:+.6f}개")
                else:
                    st.info("📱 수동 거래로 추정됨 (봇 기록 없음)")
                
                st.divider()
        
        # 총합 표시
        st.subheader("📊 총 투자 현황")
        col_total1, col_total2, col_total3 = st.columns(3)
        
        with col_total1:
            st.metric("총 투자 금액", f"{total_investment_krw:,.0f}원")
        
        with col_total2:
            st.metric("총 현재 가치", f"{total_current_value_krw:,.0f}원")
        
        with col_total3:
            total_pnl = total_current_value_krw - total_investment_krw
            total_pnl_rate = (total_pnl / total_investment_krw * 100) if total_investment_krw > 0 else 0
            pnl_color = "normal" if total_pnl >= 0 else "inverse"
            st.metric(
                "총 손익", 
                f"{total_pnl:+,.0f}원",
                delta=f"{total_pnl_rate:+.2f}%",
                delta_color=pnl_color
            )
        
    else:
        st.info("📋 **실제 업비트 계좌에 보유 중인 코인이 없습니다.**")
        st.write("모든 코인이 원화로 정리되어 있거나, API 조회에 실패했을 수 있습니다.")
        
        # KRW 잔고 표시  
        krw_balance = system_status.get('krw_balance', 0)
        st.markdown("### 💵 원화 잔고")
        st.metric("KRW 잔고", f"{krw_balance:,.0f}원")

if __name__ == "__main__":
    main()
