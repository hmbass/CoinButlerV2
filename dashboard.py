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
from dotenv import load_dotenv

from trade_bot import get_bot
from risk_manager import get_risk_manager
from trade_utils import get_upbit_api

# 환경변수 로드
load_dotenv()

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
        
        return {
            'krw_balance': krw_balance,
            'daily_pnl': daily_pnl,
            'trading_stats': trading_stats,
            'positions': {
                'total_positions': total_positions,
                'max_positions': int(os.getenv('MAX_POSITIONS', 3)),
                'available_slots': int(os.getenv('MAX_POSITIONS', 3)) - total_positions,
                'positions': positions_data
            }
        }
    except Exception as e:
        st.error(f"시스템 상태 조회 오류: {e}")
        return {
            'krw_balance': 0,
            'daily_pnl': 0,
            'trading_stats': {'total_trades': 0, 'win_rate': 0, 'total_pnl': 0},
            'positions': {'total_positions': 0, 'max_positions': 3, 'available_slots': 3, 'positions': {}}
        }

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
    tab1, tab2, tab3 = st.tabs(["📊 대시보드", "💼 보유 종목", "📈 거래 내역"])
    
    with tab1:
        show_realtime_status(system_status, risk_manager)
    
    with tab2:
        show_positions(system_status, risk_manager)
    
    with tab3:
        show_trading_history()
    
    # 자동 새로고침
    if st.session_state.auto_refresh:
        time.sleep(5)
        st.rerun()

def show_realtime_status(system_status, risk_manager):
    """실시간 현황 탭"""
    st.subheader("📊 실시간 거래 현황")
    
    # 현재 포지션 요약
    positions_info = system_status.get('positions', {})
    positions_data = positions_info.get('positions', {})
    
    # 포지션 요약 계산
    total_investment = 0
    total_current_value = 0
    total_pnl = 0
    
    for market, pos_info in positions_data.items():
        if pos_info.get('current_price', 0) > 0:
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
    
    positions = system_status['positions']['positions']
    
    if not positions:
        st.info("🔍 현재 보유 중인 종목이 없습니다.")
        st.write("새로운 거래 기회를 기다리고 있습니다.")
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
        
        # 각 종목별 컨테이너
        with st.container():
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
        
        if df.empty:
            st.info("거래 내역이 없습니다.")
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
        st.info("거래 내역 파일이 없습니다.")
    except Exception as e:
        st.error(f"거래 내역 로드 오류: {e}")

if __name__ == "__main__":
    main()
