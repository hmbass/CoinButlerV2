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
    page_title="CoinButler Dashboard",
    page_icon="🤖",
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

def get_real_bot_status():
    """실제 봇 상태를 파일 시스템에서 확인"""
    try:
        import subprocess
        import json
        
        # PID 파일들 확인
        bot_pid_file = "pids/coinbutler_bot.pid"
        dashboard_pid_file = "pids/coinbutler_dashboard.pid"
        
        bot_running = False
        if os.path.exists(bot_pid_file):
            try:
                with open(bot_pid_file, 'r') as f:
                    pid = int(f.read().strip())
                # 프로세스가 실제로 실행 중인지 확인 (Unix 시스템용)
                result = subprocess.run(['kill', '-0', str(pid)], 
                                      capture_output=True, text=True)
                bot_running = result.returncode == 0
            except:
                bot_running = False
        
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
        
        # KRW 잔고 (API 호출)
        krw_balance = 0
        try:
            upbit_api = get_upbit_api()
            krw_balance = upbit_api.get_krw_balance()
        except:
            krw_balance = 0
        
        return {
            'is_running': bot_running,
            'is_paused': False,  # 로그에서 파악해야 하지만 일단 False
            'krw_balance': krw_balance,
            'daily_pnl': daily_pnl,
            'trading_stats': trading_stats,
            'positions': {
                'total_positions': 0,  # 실제 포지션 파일이 있다면 여기서 읽어야 함
                'max_positions': int(os.getenv('MAX_POSITIONS', 3)),
                'available_slots': int(os.getenv('MAX_POSITIONS', 3)),
                'positions': {}
            }
        }
    except Exception as e:
        st.error(f"봇 상태 조회 오류: {e}")
        return {
            'is_running': False,
            'is_paused': False,
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
        <h1 style="color: white; margin: 0;">🤖 CoinButler Dashboard</h1>
        <p style="color: white; margin: 0; opacity: 0.8;">업비트 자동매매 시스템</p>
    </div>
    """, unsafe_allow_html=True)
    
    # 사이드바 - 봇 제어
    with st.sidebar:
        st.header("🎛️ 봇 제어")
        
        bot_status = get_real_bot_status()
        
        # 상태 표시
        if bot_status['is_running']:
            if bot_status['is_paused']:
                status_text = "⏸️ 일시정지"
                status_color = "status-paused"
            else:
                status_text = "🟢 실행 중"
                status_color = "status-running"
        else:
            status_text = "🔴 중지됨"
            status_color = "status-stopped"
        
        st.markdown(f'<p class="{status_color}"><strong>{status_text}</strong></p>', 
                   unsafe_allow_html=True)
        
        # 제어 버튼 - 현재는 상태 표시만 (실제 제어는 터미널에서)
        st.info("🎛️ **봇 제어는 터미널에서 수행하세요:**")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.code("./start.sh", language="bash")
            st.caption("봇 시작")
        with col2:
            st.code("./status.sh", language="bash") 
            st.caption("상태 확인")
        with col3:
            st.code("./stop.sh", language="bash")
            st.caption("봇 중지")
            
        # 봇 상태에 따른 추가 정보
        if bot_status['is_running']:
            if bot_status['is_paused']:
                st.warning("⏸️ 봇이 일시정지 상태입니다. (일일 손실 한도 초과 등)")
            else:
                st.success("🟢 봇이 정상 실행 중입니다.")
        else:
            st.error("🔴 봇이 중지된 상태입니다.")
        
        st.markdown("---")
        
        # 설정 정보
        st.subheader("⚙️ 설정")
        st.write(f"💰 투자금액: {format_currency(float(os.getenv('INVESTMENT_AMOUNT', 100000)))}")
        st.write(f"📈 목표수익률: {float(os.getenv('PROFIT_RATE', 0.03))*100:.1f}%")
        st.write(f"📉 손절률: {float(os.getenv('LOSS_RATE', -0.02))*100:.1f}%")
        st.write(f"🚨 일일손실한도: {format_currency(float(os.getenv('DAILY_LOSS_LIMIT', -50000)))}")
        
        st.markdown("---")
        
        # 자동 새로고침
        st.session_state.auto_refresh = st.checkbox("🔄 자동 새로고침", value=st.session_state.auto_refresh)
        
        if st.button("🔄 수동 새로고침"):
            st.session_state.last_update = datetime.now()
            st.rerun()
    
    # 메인 컨텐츠
    bot_status = get_real_bot_status()
    risk_manager = get_risk_manager()
    
    # 상단 메트릭
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="💰 KRW 잔고",
            value=format_currency(bot_status['krw_balance']),
            delta=None
        )
    
    with col2:
        daily_pnl = bot_status['daily_pnl']
        pnl_color = "normal" if daily_pnl >= 0 else "inverse"
        st.metric(
            label="📊 일일 손익",
            value=format_currency(daily_pnl),
            delta=format_percentage((daily_pnl / 100000) * 100) if daily_pnl != 0 else None,
            delta_color=pnl_color
        )
    
    with col3:
        positions_info = bot_status['positions']
        st.metric(
            label="📋 보유 포지션",
            value=f"{positions_info['total_positions']}/{positions_info['max_positions']}",
            delta=f"여유: {positions_info['available_slots']}개"
        )
    
    with col4:
        trading_stats = bot_status['trading_stats']
        st.metric(
            label="🎯 승률",
            value=f"{trading_stats['win_rate']:.1f}%",
            delta=f"총 {trading_stats['total_trades']}회"
        )
    
    # 탭 생성
    tab1, tab2, tab3, tab4 = st.tabs(["📊 실시간 현황", "💼 포지션 관리", "📈 거래 내역", "📋 로그"])
    
    with tab1:
        show_realtime_status(bot_status, risk_manager)
    
    with tab2:
        show_positions(bot_status, risk_manager)
    
    with tab3:
        show_trading_history()
    
    with tab4:
        show_logs()
    
    # 자동 새로고침
    if st.session_state.auto_refresh:
        time.sleep(5)
        st.rerun()

def show_realtime_status(bot_status, risk_manager):
    """실시간 현황 탭"""
    st.subheader("📊 실시간 거래 현황")
    
    # 일일 손익 차트
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # 가상의 시간별 손익 데이터 (실제로는 DB에서 조회)
        hours = list(range(24))
        pnl_data = [0] * 24  # 실제로는 시간별 누적 손익 데이터
        pnl_data[-1] = bot_status['daily_pnl']  # 현재 손익
        
        fig_pnl = go.Figure()
        fig_pnl.add_trace(go.Scatter(
            x=hours,
            y=pnl_data,
            mode='lines+markers',
            name='일일 손익',
            line=dict(color='#00d4aa' if bot_status['daily_pnl'] >= 0 else '#ff4b4b'),
            fill='tonexty'
        ))
        
        fig_pnl.update_layout(
            title="일일 손익 추이",
            xaxis_title="시간",
            yaxis_title="손익 (원)",
            height=400,
            showlegend=False
        )
        
        st.plotly_chart(fig_pnl, use_container_width=True)
    
    with col2:
        st.subheader("💹 시장 정보")
        
        # 비트코인 가격 (예시)
        try:
            upbit_api = get_upbit_api()
            btc_price = upbit_api.get_current_price("KRW-BTC")
            if btc_price:
                st.metric("BTC 가격", f"{btc_price:,.0f}원")
        except:
            st.write("시장 정보 로드 실패")
        
        # 거래 통계
        stats = bot_status['trading_stats']
        st.write("**거래 통계**")
        st.write(f"• 총 거래: {stats['total_trades']}회")
        st.write(f"• 수익 거래: {stats.get('winning_trades', 0)}회")
        st.write(f"• 손실 거래: {stats.get('losing_trades', 0)}회")
        st.write(f"• 평균 손익: {format_currency(stats.get('avg_profit', 0))}")

def show_positions(bot_status, risk_manager):
    """포지션 관리 탭"""
    st.subheader("💼 현재 포지션")
    
    positions = bot_status['positions']['positions']
    
    if not positions:
        st.info("현재 보유 중인 포지션이 없습니다.")
        return
    
    # 포지션 테이블
    position_data = []
    total_investment = 0
    total_current_value = 0
    
    upbit_api = get_upbit_api()
    
    for market, pos_info in positions.items():
        try:
            current_price = upbit_api.get_current_price(market)
            if current_price:
                current_value = pos_info['quantity'] * current_price
                pnl = current_value - pos_info['investment_amount']
                pnl_rate = (pnl / pos_info['investment_amount']) * 100
                
                total_investment += pos_info['investment_amount']
                total_current_value += current_value
                
                position_data.append({
                    '종목': market.replace('KRW-', ''),
                    '진입가': f"{pos_info['entry_price']:,.0f}원",
                    '현재가': f"{current_price:,.0f}원",
                    '수량': f"{pos_info['quantity']:.6f}",
                    '투자금액': f"{pos_info['investment_amount']:,.0f}원",
                    '현재가치': f"{current_value:,.0f}원",
                    '손익': f"{pnl:,.0f}원",
                    '손익률': f"{pnl_rate:+.2f}%",
                    '진입시간': pos_info['entry_time'][:16]
                })
        except:
            position_data.append({
                '종목': market.replace('KRW-', ''),
                '진입가': f"{pos_info['entry_price']:,.0f}원",
                '현재가': "조회 실패",
                '수량': f"{pos_info['quantity']:.6f}",
                '투자금액': f"{pos_info['investment_amount']:,.0f}원",
                '현재가치': "조회 실패",
                '손익': "조회 실패",
                '손익률': "조회 실패",
                '진입시간': pos_info['entry_time'][:16]
            })
    
    if position_data:
        df = pd.DataFrame(position_data)
        st.dataframe(df, use_container_width=True)
        
        # 포지션 요약
        if total_investment > 0:
            total_pnl = total_current_value - total_investment
            total_pnl_rate = (total_pnl / total_investment) * 100
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("총 투자금액", format_currency(total_investment))
            with col2:
                st.metric("현재 가치", format_currency(total_current_value))
            with col3:
                pnl_color = "normal" if total_pnl >= 0 else "inverse"
                st.metric(
                    "미실현 손익", 
                    format_currency(total_pnl),
                    format_percentage(total_pnl_rate),
                    delta_color=pnl_color
                )

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

def show_logs():
    """로그 탭"""
    st.subheader("📋 시스템 로그")
    
    try:
        # 로그 파일 읽기 (새로운 경로 구조)
        log_files = ["logs/coinbutler_bot.log", "logs/coinbutler.log", "coinbutler.log"]
        logs = []
        
        for log_file in log_files:
            if os.path.exists(log_file):
                with open(log_file, "r", encoding="utf-8") as f:
                    logs = f.readlines()
                break
        
        if not logs:
            st.info("로그 파일이 없습니다.")
            return
            
        # 최근 100줄만 표시
        recent_logs = logs[-100:] if len(logs) > 100 else logs
        
        # 로그 레벨 필터
        log_level = st.selectbox("로그 레벨", ["ALL", "ERROR", "WARNING", "INFO"])
        
        filtered_logs = []
        for log in recent_logs:
            if log_level == "ALL":
                filtered_logs.append(log)
            elif log_level in log.upper():
                filtered_logs.append(log)
        
        if filtered_logs:
            log_text = "".join(reversed(filtered_logs))  # 최신 로그부터 표시
            st.code(log_text, language="text")
        else:
            st.info("해당 레벨의 로그가 없습니다.")
            
    except Exception as e:
        st.error(f"로그 로드 오류: {e}")

if __name__ == "__main__":
    main()
