# run the file by : python3 -m streamlit run main.py --server.port 8530

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import pytz
import time
import numpy as np
import warnings
warnings.filterwarnings('ignore')
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)
try:
	st.set_option('logger.level', 'error')
except Exception:
	pass

# Import modules
from config import CREDENTIALS_FILE, LOT_SIZE_MAP
from utils import (
    get_indian_time, format_currency, get_credentials,
    load_persisted_credentials, persist_credentials, clear_credentials,
    skip_next_auto_refresh
)
from api_client import (
    validate_access_token, generate_login_url, generate_access_token, is_authenticated
)
from data_fetcher import get_portfolio_data, format_live_price_data
from calculations import (
    calculate_technical_indicators, calculate_risk_metrics,
    calculate_arbitrage_opportunities, format_futures_order_symbol,
    get_futures_contracts, calculate_cash_futures_opportunities,
    calculate_margin_required, get_available_margin,
    get_arbitrage_insights, get_market_insights
)
from order_manager import (
    place_order, execute_order_sequence, place_arbitrage_orders,
    place_cash_futures_orders
)
from database import (
    init_database, store_arbitrage_spread, store_cash_futures_spread,
    store_order_history, get_arbitrage_spread_history, get_cash_futures_spread_history,
    get_order_history, get_arbitrage_insights_from_db, get_cash_futures_insights_from_db,
    get_top_arbitrage_symbols, get_top_cash_futures_symbols, cleanup_old_data
)
from kiteconnect import KiteConnect

# Import UI modules
from ui_auth import render_auth_ui
from ui_sidebar import render_sidebar
from ui_dashboard import render_dashboard_overview

# Initialize database on startup
init_database()


# Page configuration
st.set_page_config(
    page_title="My Stock Market Dashboard",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 0.5rem;
        color: white;
        text-align: center;
        margin: 0.5rem 0;
    }
    .positive { color: #00C851; font-weight: bold; }
    .negative { color: #ff4444; font-weight: bold; }
    .compact-card {
        background: #f8f9fa;
        border: 1px solid #e5e7eb;
        border-radius: 0.5rem;
        padding: 0.75rem 1rem;
        margin-bottom: 0.5rem;
    }
    .compact-card h4 {
        font-size: 1rem;
        margin: 0 0 0.35rem 0;
        color: #1f2937;
    }
    .compact-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-size: 0.9rem;
        margin-bottom: 0.25rem;
    }
    .compact-row span.value {
        font-weight: 600;
        color: #111827;
    }
    .compact-note {
        font-size: 0.75rem;
        color: #6b7280;
        margin-top: 0.25rem;
    }
</style>
""", unsafe_allow_html=True)


def main():
    # Header
    st.markdown('<h1 class="main-header">📈 Stock Market Dashboard</h1>', unsafe_allow_html=True)
    
    # Load persisted credentials once per session
    load_persisted_credentials()
    
    # Check if user is authenticated
    if not is_authenticated():
        render_auth_ui()
    
    # Initialize sidebar controls
    auto_refresh = st.session_state.get('auto_refresh', False)
    refresh_interval = st.session_state.get('refresh_interval', 30)
    auto_refresh, refresh_interval, market_open = render_sidebar(auto_refresh, refresh_interval)
    st.session_state['auto_refresh'] = auto_refresh
    st.session_state['refresh_interval'] = refresh_interval
    
    # Get credentials from session state
    api_key, api_secret, access_token = get_credentials()
    
    if not api_key or not api_secret or not access_token:
        st.error("❌ Please login with your Zerodha credentials")
        st.rerun()
    
    # Validate access token before proceeding
    if not validate_access_token(api_key, access_token):
        st.error("❌ Your access token has expired. Please regenerate it.")
        if st.button("🔄 Regenerate Access Token"):
            # Clear access token to trigger regeneration
            if 'access_token' in st.session_state:
                del st.session_state['access_token']
                persist_credentials()
            if 'login_url' in st.session_state:
                del st.session_state['login_url']
            st.rerun()
        st.stop()
    
    # Initialize Kite Connect
    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(access_token)
    
    # Test connection and store profile
    try:
        profile = kite.profile()
        # Store profile in session state for sidebar display
        st.session_state['user_profile'] = profile
        st.success(f"✅ Connected as: {profile.get('user_name', 'Unknown')}")
    except Exception as e:
        error_msg = str(e)
        if "Invalid" in error_msg or "expired" in error_msg.lower() or "token" in error_msg.lower():
            st.error(f"❌ Access token expired or invalid: {error_msg}")
            st.warning("🔄 Please regenerate your access token.")
            if st.button("🔄 Regenerate Access Token"):
                # Clear access token to trigger regeneration
                if 'access_token' in st.session_state:
                    del st.session_state['access_token']
                    persist_credentials()
                if 'login_url' in st.session_state:
                    del st.session_state['login_url']
                st.rerun()
        else:
            st.error(f"❌ Connection failed: {error_msg}")
        st.stop()
    
    # Get portfolio data
    with st.spinner("🔄 Fetching real-time data..."):
        data = get_portfolio_data(kite)
    
    if not data:
        st.error("❌ Unable to fetch portfolio data")
        st.warning("🔄 Will retry automatically...")
        time.sleep(5)
        st.rerun()
    
    # Store profile from portfolio data if available (in case it wasn't stored earlier)
    if data.get('profile') and 'user_profile' not in st.session_state:
        st.session_state['user_profile'] = data['profile']
    
    # Convert to DataFrames
    holdings_df = pd.DataFrame(data['holdings'])
    net_positions_df = pd.DataFrame(data['net_positions'])
    orders_df = pd.DataFrame(data['orders'])
    
    # Get live prices data for use in tabs
    live_prices_data = format_live_price_data(data.get('live_prices', {}))
    
    # Render main dashboard overview
    render_dashboard_overview(holdings_df, net_positions_df, orders_df, data)
    
    
    # Tabs
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10, tab11 = st.tabs([
        "💼 Holdings", "📈 Positions", "📋 Orders", "💰 Account", "📊 Analytics", "🔍 Market Analysis", "📊 Live Prices", "🔥 Market Data", "⚖️ Arbitrage", "📅 Theta Capture", "📊 Historical Insights"
    ])
    
    with tab1:
        st.subheader("💼 Your Holdings")
        
        if not holdings_df.empty:
            # Calculate additional metrics
            holdings_df['market_value'] = holdings_df['quantity'] * holdings_df['last_price']
            holdings_df['investment_value'] = holdings_df['quantity'] * holdings_df['average_price']
            holdings_df['return_pct'] = ((holdings_df['last_price'] - holdings_df['average_price']) / holdings_df['average_price']) * 100
            
            # Top performers
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("🏆 Top Performers")
                top_performers = holdings_df.nlargest(3, 'pnl')[['tradingsymbol', 'pnl', 'return_pct']]
                for _, row in top_performers.iterrows():
                    pnl_emoji = "🟢" if row['pnl'] >= 0 else "🔴"
                    st.write(f"{pnl_emoji} **{row['tradingsymbol']}**: {format_currency(row['pnl'])} ({row['return_pct']:.2f}%)")
            
            with col2:
                st.subheader("📉 Underperformers")
                underperformers = holdings_df.nsmallest(3, 'pnl')[['tradingsymbol', 'pnl', 'return_pct']]
                for _, row in underperformers.iterrows():
                    pnl_emoji = "🟢" if row['pnl'] >= 0 else "🔴"
                    st.write(f"{pnl_emoji} **{row['tradingsymbol']}**: {format_currency(row['pnl'])} ({row['return_pct']:.2f}%)")
            
            # P&L Chart
            fig = px.bar(
                holdings_df, 
                x='tradingsymbol', 
                y='pnl',
                title="P&L by Stock",
                color='pnl',
                color_continuous_scale=['#ff4444', '#00C851'],
                color_continuous_midpoint=0
            )
            fig.update_layout(height=400, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
            
            # Portfolio allocation pie chart
            if len(holdings_df) > 1:
                fig_pie = px.pie(
                    holdings_df, 
                    values='market_value', 
                    names='tradingsymbol',
                    title="Portfolio Allocation by Market Value"
                )
                fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig_pie, use_container_width=True)
            
            # Performance comparison chart
            if len(holdings_df) > 1:
                fig_perf = px.bar(
                    holdings_df, 
                    x='tradingsymbol', 
                    y='return_pct',
                    title="Return % by Stock",
                    color='return_pct',
                    color_continuous_scale=['#ff4444', '#00C851'],
                    color_continuous_midpoint=0
                )
                fig_perf.update_layout(height=400, showlegend=False)
                st.plotly_chart(fig_perf, use_container_width=True)
            
            # Risk vs Return scatter plot
            if len(holdings_df) > 2:
                holdings_df['risk_score'] = holdings_df['return_pct'].rolling(window=min(5, len(holdings_df))).std().fillna(0)
                fig_risk = px.scatter(
                    holdings_df, 
                    x='risk_score', 
                    y='return_pct',
                    size='market_value',
                    hover_name='tradingsymbol',
                    title="Risk vs Return Analysis",
                    color='pnl',
                    color_continuous_scale=['#ff4444', '#00C851']
                )
                fig_risk.update_layout(height=400)
                st.plotly_chart(fig_risk, use_container_width=True)
            
            # Holdings table with more details
            display_holdings = holdings_df.copy()
            display_holdings['pnl'] = display_holdings['pnl'].apply(format_currency)
            display_holdings['average_price'] = display_holdings['average_price'].apply(format_currency)
            display_holdings['last_price'] = display_holdings['last_price'].apply(format_currency)
            display_holdings['market_value'] = display_holdings['market_value'].apply(format_currency)
            display_holdings['investment_value'] = display_holdings['investment_value'].apply(format_currency)
            display_holdings['return_pct'] = display_holdings['return_pct'].apply(lambda x: f"{x:.2f}%")
            
            st.dataframe(
                display_holdings[['tradingsymbol', 'exchange', 'quantity', 'average_price', 'last_price', 'market_value', 'investment_value', 'return_pct', 'pnl']],
                use_container_width=True
            )
        else:
            st.info("No holdings found")
            st.markdown("**💡 Tip:** Start by buying some stocks to see your portfolio here!")
    
    with tab2:
        st.subheader("📈 Active Positions")
        
        if not net_positions_df.empty:
            # Position summary
            col1, col2, col3 = st.columns(3)
            
            with col1:
                total_position_value = (net_positions_df['quantity'] * net_positions_df['last_price']).sum()
                st.metric("Total Position Value", format_currency(total_position_value))
            
            with col2:
                total_position_pnl = net_positions_df['pnl'].sum()
                pnl_emoji = "📈" if total_position_pnl >= 0 else "📉"
                st.metric("Position P&L", f"{pnl_emoji} {format_currency(total_position_pnl)}")
            
            with col3:
                st.metric("Active Positions", len(net_positions_df))
            
            # Positions table
            st.dataframe(net_positions_df, use_container_width=True)
        else:
            st.info("No active positions")
            st.markdown("**💡 Tip:** Positions appear when you have open trades or intraday positions!")
    
    with tab3:
        st.subheader("📋 Order Management")
        
        if not orders_df.empty:
            # Order status summary
            status_counts = orders_df['status'].value_counts()
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Open", status_counts.get('OPEN', 0))
            with col2:
                st.metric("Complete", status_counts.get('COMPLETE', 0))
            with col3:
                st.metric("Cancelled", status_counts.get('CANCELLED', 0))
            with col4:
                st.metric("Rejected", status_counts.get('REJECTED', 0))
            
            # Order analysis
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("📊 Order Analysis")
                total_orders = len(orders_df)
                successful_orders = len(orders_df[orders_df['status'] == 'COMPLETE'])
                success_rate = (successful_orders / total_orders) * 100 if total_orders > 0 else 0
                
                st.metric("Total Orders", total_orders)
                st.metric("Success Rate", f"{success_rate:.1f}%")
                
                # Today's orders
                try:
                    # Convert order_timestamp to string first, then filter
                    orders_df['order_timestamp_str'] = orders_df['order_timestamp'].astype(str)
                    today_orders = orders_df[orders_df['order_timestamp_str'].str.contains(get_indian_time().strftime('%Y-%m-%d'))]
                    st.metric("Today's Orders", len(today_orders))
                except:
                    st.metric("Today's Orders", "0")
            
            with col2:
                st.subheader("📈 Today's Orders")
                try:
                    # Get today's orders
                    today = get_indian_time().strftime('%Y-%m-%d')
                    orders_chart = orders_df.copy()
                    orders_chart['order_timestamp_str'] = orders_chart['order_timestamp'].astype(str)
                    today_orders = orders_chart[orders_chart['order_timestamp_str'].str.contains(today)]
                    
                    if not today_orders.empty:
                        # Group by hour for today's orders
                        today_orders['hour'] = pd.to_datetime(today_orders['order_timestamp_str']).dt.hour
                        hourly_orders = today_orders.groupby('hour').size().reset_index(name='count')
                        
                        # Create simple bar chart
                        fig_orders = px.bar(
                            hourly_orders, 
                            x='hour', 
                            y='count', 
                            title=f"Orders Today ({today})",
                            color='count',
                            color_continuous_scale='blues'
                        )
                        fig_orders.update_layout(
                            height=300,
                            showlegend=False,
                            xaxis_title="Hour",
                            yaxis_title="Number of Orders"
                        )
                        st.plotly_chart(fig_orders, use_container_width=True)
                    else:
                        st.info("No orders placed today yet")
                except:
                    st.info("Unable to generate today's orders chart")
            
            # Recent orders with more details
            st.subheader("📋 Recent Orders")
            recent_orders = orders_df.head(20)[['tradingsymbol', 'transaction_type', 'quantity', 'price', 'status', 'order_timestamp']]
            st.dataframe(recent_orders, use_container_width=True)
        else:
            st.info("No orders found")
            st.markdown("**💡 Tip:** Orders will appear here when you place trades!")
    
    with tab4:
        st.subheader("💰 Account Information")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("👤 Profile Details")
            profile = data['profile']
            
            # Profile info with better formatting
            st.markdown(f"""
            **👤 User Name:** {profile.get('user_name', 'N/A')}  
            **📧 Email:** {profile.get('email', 'N/A')}  
            **🏢 Broker:** {profile.get('broker', 'N/A')}  
            **🆔 User ID:** {profile.get('user_id', 'N/A')}  
            **📱 Mobile:** {profile.get('mobile', 'N/A')}  
            **🏠 City:** {profile.get('city', 'N/A')}  
            **📅 Member Since:** {profile.get('member_since', 'N/A')}  
            """)
            
            # Products and order types
            if profile.get('products'):
                st.markdown("**📦 Available Products:**")
                for product in profile.get('products', []):
                    st.write(f"• {product}")
            
            if profile.get('order_types'):
                st.markdown("**📋 Order Types:**")
                for order_type in profile.get('order_types', []):
                    st.write(f"• {order_type}")
        
        with col2:
            st.subheader("💳 Margin Information")
            margins = data['margins']
            
            # Equity margins
            equity = margins.get('equity', {})
            if equity:
                st.markdown("**📈 Equity Margins:**")
                available = equity.get('available', {})
                utilised = equity.get('utilised', {})
                
                available_cash = available.get('cash', 0)
                utilised_cash = utilised.get('cash', 0)
                total_cash = available_cash + utilised_cash
                
                st.metric("Available Cash", format_currency(available_cash))
                st.metric("Used Cash", format_currency(utilised_cash))
                
                if total_cash > 0:
                    utilization_pct = (utilised_cash / total_cash) * 100
                    st.metric("Cash Utilization", f"{utilization_pct:.1f}%")
                
                # Additional margin details
                st.markdown("**📊 Additional Details:**")
                st.write(f"• Opening Balance: {format_currency(equity.get('opening', {}).get('cash', 0))}")
                st.write(f"• Payin: {format_currency(equity.get('payin', {}).get('cash', 0))}")
                st.write(f"• Payout: {format_currency(equity.get('payout', {}).get('cash', 0))}")
            
            # Commodity margins
            commodity = margins.get('commodity', {})
            if commodity:
                st.markdown("**🥇 Commodity Margins:**")
                available = commodity.get('available', {})
                utilised = commodity.get('utilised', {})
                
                st.metric("Available Cash", format_currency(available.get('cash', 0)))
                st.metric("Used Cash", format_currency(utilised.get('cash', 0)))
        
        # Account summary
        st.subheader("📊 Account Summary")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if not holdings_df.empty:
                total_investment = (holdings_df['quantity'] * holdings_df['average_price']).sum()
                st.metric("Total Investment", format_currency(total_investment))
            else:
                st.metric("Total Investment", "₹0")
        
        with col2:
            if not holdings_df.empty:
                total_market_value = (holdings_df['quantity'] * holdings_df['last_price']).sum()
                st.metric("Current Portfolio Value", format_currency(total_market_value))
            else:
                st.metric("Current Portfolio Value", "₹0")
        
        with col3:
            if not orders_df.empty:
                st.metric("Total Orders Placed", len(orders_df))
            else:
                st.metric("Total Orders Placed", "0")
    
    # New Analytics Tab
    with tab5:
        st.subheader("📊 Advanced Analytics")
        
        if not holdings_df.empty:
            # Portfolio performance over time simulation
            st.subheader("📈 Portfolio Performance Simulation")
            
            # Create a simple performance chart
            dates = pd.date_range(start=datetime.now() - timedelta(days=30), end=datetime.now(), freq='D')
            performance_data = []
            
            for i, date in enumerate(dates):
                # Simulate portfolio value based on current holdings
                simulated_value = total_market_value * (1 + (i * 0.001))  # Simple simulation
                performance_data.append({
                    'date': date,
                    'portfolio_value': simulated_value,
                    'pnl': simulated_value - total_investment
                })
            
            perf_df = pd.DataFrame(performance_data)
            
            # Create performance chart
            fig_perf = make_subplots(
                rows=2, cols=1,
                subplot_titles=('Portfolio Value Over Time', 'P&L Over Time'),
                vertical_spacing=0.1
            )
            
            fig_perf.add_trace(
                go.Scatter(x=perf_df['date'], y=perf_df['portfolio_value'], 
                          name='Portfolio Value', line=dict(color='blue')),
                row=1, col=1
            )
            
            fig_perf.add_trace(
                go.Scatter(x=perf_df['date'], y=perf_df['pnl'], 
                          name='P&L', line=dict(color='green')),
                row=2, col=1
            )
            
            fig_perf.update_layout(height=600, showlegend=True)
            st.plotly_chart(fig_perf, use_container_width=True)
            
            # Sector analysis (simplified)
            st.subheader("🏭 Sector Analysis")
            if 'exchange' in holdings_df.columns:
                sector_counts = holdings_df['exchange'].value_counts()
                fig_sector = px.bar(
                    x=sector_counts.index, 
                    y=sector_counts.values,
                    title="Holdings by Exchange",
                    color=sector_counts.values,
                    color_continuous_scale='viridis'
                )
                st.plotly_chart(fig_sector, use_container_width=True)
            
            # Correlation matrix
            st.subheader("🔗 Stock Correlation Analysis")
            if len(holdings_df) > 1:
                # Create correlation matrix for returns
                returns_data = holdings_df[['tradingsymbol', 'return_pct']].set_index('tradingsymbol')
                correlation_matrix = returns_data.T.corr()
                
                fig_corr = px.imshow(
                    correlation_matrix,
                    title="Stock Returns Correlation Matrix",
                    color_continuous_scale='RdBu',
                    aspect='auto'
                )
                st.plotly_chart(fig_corr, use_container_width=True)
        
        else:
            st.info("No holdings available for analytics")
    
    # New Market Analysis Tab
    with tab6:
        st.subheader("🔍 Market Analysis")
        
        # Market overview
        st.subheader("📊 Market Overview")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Market Status", "Open" if market_open else "Closed")
        with col2:
            st.metric("Current Time", get_indian_time().strftime('%H:%M:%S'))
        with col3:
            st.metric("Trading Day", get_indian_time().strftime('%Y-%m-%d'))
        
        # Market insights
        st.subheader("💡 Trading Insights")
        
        insights_list = [
            "📈 **Market Hours**: 9:15 AM - 3:30 PM IST",
            "💰 **Best Trading Times**: 9:15-10:30 AM and 2:30-3:30 PM",
            "⚠️ **High Volatility**: First and last 30 minutes of trading",
            "📊 **Market Analysis**: Use technical indicators for better decisions",
            "🎯 **Risk Management**: Never risk more than 2% of portfolio on single trade"
        ]
        
        for insight in insights_list:
            st.info(insight)
        
        # Historical data analysis
        if data.get('historical_data'):
            st.subheader("📈 Historical Analysis")
            
            for symbol, hist_data in list(data['historical_data'].items())[:3]:  # Show top 3
                if hist_data:
                    hist_df = pd.DataFrame(hist_data)
                    hist_df = calculate_technical_indicators(hist_df)
                    
                    # Create candlestick chart with indicators
                    fig_candlestick = make_subplots(
                        rows=2, cols=1,
                        subplot_titles=(f'{symbol} - Price Chart', 'RSI'),
                        vertical_spacing=0.1,
                        row_heights=[0.7, 0.3]
                    )
                    
                    # Candlestick
                    fig_candlestick.add_trace(
                        go.Candlestick(
                            x=hist_df['date'],
                            open=hist_df['open'],
                            high=hist_df['high'],
                            low=hist_df['low'],
                            close=hist_df['close'],
                            name='Price'
                        ),
                        row=1, col=1
                    )
                    
                    # Moving averages
                    fig_candlestick.add_trace(
                        go.Scatter(x=hist_df['date'], y=hist_df['sma_5'], 
                                  name='SMA 5', line=dict(color='orange')),
                        row=1, col=1
                    )
                    
                    fig_candlestick.add_trace(
                        go.Scatter(x=hist_df['date'], y=hist_df['sma_20'], 
                                  name='SMA 20', line=dict(color='blue')),
                        row=1, col=1
                    )
                    
                    # RSI
                    fig_candlestick.add_trace(
                        go.Scatter(x=hist_df['date'], y=hist_df['rsi'], 
                                  name='RSI', line=dict(color='purple')),
                        row=2, col=1
                    )
                    
                    # RSI levels
                    fig_candlestick.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
                    fig_candlestick.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)
                    
                    fig_candlestick.update_layout(height=600, showlegend=True)
                    st.plotly_chart(fig_candlestick, use_container_width=True)
        
        # Trading recommendations
        st.subheader("🎯 Trading Recommendations")
        
        recommendations = [
            "📊 **Technical Analysis**: Use RSI, MACD, and moving averages for entry/exit points",
            "💰 **Position Sizing**: Risk only 1-2% of portfolio per trade",
            "⏰ **Timing**: Enter positions during market hours for better liquidity",
            "🛡️ **Stop Loss**: Always set stop loss to limit downside risk",
            "📈 **Trend Following**: Trade in direction of major trend for better success rate"
        ]
        
        for rec in recommendations:
            st.success(rec)
    
    # New Live Prices Tab
    with tab7:
        st.subheader("📊 Live Market Prices & Real-time Data")
        
        # Market status
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Market Status", "🟢 Open" if market_open else "🔴 Closed")
        with col2:
            st.metric("Last Updated", get_indian_time().strftime('%H:%M:%S'))
        with col3:
            st.metric("Data Source", "Zerodha API")
        
        # Sector filter
        if live_prices_data:
            st.subheader("🔍 Filter by Sector")
            
            # Define sectors
            sectors = {
                "All": live_prices_data,
                "Banking": [s for s in live_prices_data if any(bank in s['symbol'] for bank in ['HDFC', 'ICICI', 'KOTAK', 'AXIS', 'INDUS', 'BANDHAN', 'PNB', 'IDFC', 'SBI'])],
                "IT & Tech": [s for s in live_prices_data if any(tech in s['symbol'] for tech in ['TCS', 'INFY', 'WIPRO', 'HCL', 'TECHM', 'LTIM', 'MINDTREE', 'MPHASIS', 'COFORGE', 'PERSISTENT', 'LTTS', 'ZENSAR'])],
                "FMCG": [s for s in live_prices_data if any(fmcg in s['symbol'] for fmcg in ['ITC', 'NESTLE', 'MARICO', 'BRITANNIA', 'DABUR', 'GODREJCP', 'COLPAL', 'UBL', 'PGHH', 'EMAMI'])],
                "Auto": [s for s in live_prices_data if any(auto in s['symbol'] for auto in ['MARUTI', 'TATAMOTORS', 'BAJAJ-AUTO', 'HEROMOTOCO', 'EICHERMOT', 'ASHOKLEY', 'BOSCHLTD', 'EXIDEIND', 'MRF', 'APOLLOTYRE'])],
                "Pharma": [s for s in live_prices_data if any(pharma in s['symbol'] for pharma in ['SUNPHARMA', 'DRREDDY', 'CIPLA', 'BIOCON', 'AUROPHARMA', 'DIVISLAB', 'GLENMARK', 'LUPIN', 'CADILAHC', 'TORNTPHARM'])],
                "Energy": [s for s in live_prices_data if any(energy in s['symbol'] for energy in ['ONGC', 'GAIL', 'BPCL', 'IOC', 'HPCL', 'PETRONET', 'OIL', 'ADANIGREEN', 'TATAPOWER', 'NTPC'])],
                "Metals": [s for s in live_prices_data if any(metal in s['symbol'] for metal in ['TATASTEEL', 'JSWSTEEL', 'SAIL', 'HINDALCO', 'VEDL', 'COALINDIA', 'JINDALSTEL', 'WELCORP', 'RATNAMANI', 'MOIL'])],
                "Telecom": [s for s in live_prices_data if any(telco in s['symbol'] for telco in ['BHARTIARTL', 'IDEA', 'ZEE', 'SUNTV', 'NETWORK18'])],
                "Real Estate": [s for s in live_prices_data if any(realty in s['symbol'] for realty in ['DLF', 'GODREJPROP', 'SOBHA', 'BRIGADE', 'MAHLIFE', 'ADANIPORTS', 'CONCOR', 'IRCTC', 'RVNL', 'IRFC'])]
            }
            
            # Create filter buttons
            selected_sector = st.selectbox("Choose Sector:", list(sectors.keys()))
            filtered_data = sectors[selected_sector]
            
            st.info(f"Showing {len(filtered_data)} stocks from {selected_sector} sector")
        else:
            filtered_data = []
        
        # Live prices grid
        if filtered_data:
            st.subheader("🔥 Top Movers - Live Prices")
            
            # Top gainers
            gainers = [stock for stock in filtered_data if stock['change'] > 0]
            if gainers:
                st.markdown("**📈 Top Gainers**")
                gainers_df = pd.DataFrame(gainers[:5])
                
                cols = st.columns(len(gainers_df))
                for i, (_, stock) in enumerate(gainers_df.iterrows()):
                    with cols[i]:
                        st.markdown(f"""
                        <div style="
                            border: 2px solid #00C851;
                            border-radius: 10px;
                            padding: 15px;
                            margin: 5px;
                            background: linear-gradient(135deg, #e8f5e8 0%, #c8e6c9 100%);
                            text-align: center;
                        ">
                            <h3 style="margin: 0; color: #2e7d32;">{stock['symbol']}</h3>
                            <p style="margin: 5px 0; font-size: 20px; font-weight: bold; color: #00C851;">
                                📈 ₹{stock['last_price']:,.2f}
                            </p>
                            <p style="margin: 0; font-size: 14px; color: #00C851;">
                                +{stock['change']:.2f} (+{stock['change_pct']:.2f}%)
                            </p>
                        </div>
                        """, unsafe_allow_html=True)
            
            # Top losers
            losers = [stock for stock in filtered_data if stock['change'] < 0]
            if losers:
                st.markdown("**📉 Top Losers**")
                losers_df = pd.DataFrame(losers[:5])
                
                cols = st.columns(len(losers_df))
                for i, (_, stock) in enumerate(losers_df.iterrows()):
                    with cols[i]:
                        st.markdown(f"""
                        <div style="
                            border: 2px solid #ff4444;
                            border-radius: 10px;
                            padding: 15px;
                            margin: 5px;
                            background: linear-gradient(135deg, #ffebee 0%, #ffcdd2 100%);
                            text-align: center;
                        ">
                            <h3 style="margin: 0; color: #c62828;">{stock['symbol']}</h3>
                            <p style="margin: 5px 0; font-size: 20px; font-weight: bold; color: #ff4444;">
                                📉 ₹{stock['last_price']:,.2f}
                            </p>
                            <p style="margin: 0; font-size: 14px; color: #ff4444;">
                                {stock['change']:.2f} ({stock['change_pct']:.2f}%)
                            </p>
                        </div>
                        """, unsafe_allow_html=True)
            
            # Live prices chart
            st.subheader("📊 Live Price Movement Chart")
            
            # Create a chart showing price changes
            chart_data = pd.DataFrame(filtered_data)
            chart_data = chart_data.sort_values('change_pct', ascending=False)
            
            fig_live = px.bar(
                chart_data,
                x='symbol',
                y='change_pct',
                color='change_pct',
                color_continuous_scale=['#ff4444', '#ffa500', '#00C851'],
                color_continuous_midpoint=0,
                title="Live Price Changes (%)",
                labels={'change_pct': 'Change %', 'symbol': 'Stock Symbol'}
            )
            fig_live.update_layout(height=500, showlegend=False)
            st.plotly_chart(fig_live, use_container_width=True)
            
            # Detailed live prices table
            st.subheader("📋 Complete Live Prices Table")
            
            live_df = pd.DataFrame(filtered_data)
            live_df['last_price'] = live_df['last_price'].apply(format_currency)
            live_df['change'] = live_df['change'].apply(lambda x: f"{x:+.2f}")
            live_df['change_pct'] = live_df['change_pct'].apply(lambda x: f"{x:+.2f}%")
            live_df['high'] = live_df['high'].apply(format_currency)
            live_df['low'] = live_df['low'].apply(format_currency)
            live_df['open'] = live_df['open'].apply(format_currency)
            live_df['close'] = live_df['close'].apply(format_currency)
            live_df['volume'] = live_df['volume'].apply(lambda x: f"{x:,}")
            
            # Add color coding for the table
            def color_code_change(val):
                if isinstance(val, str) and val.startswith('+'):
                    return 'background-color: #e8f5e8; color: #2e7d32;'
                elif isinstance(val, str) and val.startswith('-'):
                    return 'background-color: #ffebee; color: #c62828;'
                return ''
            
            styled_df = live_df[['symbol', 'exchange', 'last_price', 'change', 'change_pct', 'high', 'low', 'open', 'volume']].style.applymap(
                color_code_change, subset=['change', 'change_pct']
            )
            
            st.dataframe(styled_df, use_container_width=True)
            
            # Market summary
            st.subheader("📊 Market Summary")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Stocks", len(filtered_data))
            with col2:
                gainers_count = len([s for s in filtered_data if s['change'] > 0])
                st.metric("Gainers", gainers_count)
            with col3:
                losers_count = len([s for s in filtered_data if s['change'] < 0])
                st.metric("Losers", losers_count)
            with col4:
                unchanged_count = len([s for s in filtered_data if s['change'] == 0])
                st.metric("Unchanged", unchanged_count)
        
        else:
            st.info("🕐 Live prices will be available when market is open")
            st.markdown("**Market Hours:** 9:15 AM - 3:30 PM IST")
            
            # Show market countdown
            current_time = get_indian_time()
            if current_time.hour < 9 or current_time.hour >= 15:
                if current_time.hour < 9:
                    next_open = current_time.replace(hour=9, minute=15, second=0, microsecond=0)
                else:
                    next_open = (current_time + timedelta(days=1)).replace(hour=9, minute=15, second=0, microsecond=0)
                
                time_diff = next_open - current_time
                hours, remainder = divmod(time_diff.seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                
                st.markdown(f"""
                <div style="
                    border: 2px solid #1f77b4;
                    border-radius: 10px;
                    padding: 20px;
                    text-align: center;
                    background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
                ">
                    <h3 style="color: #1976d2;">⏰ Market Opens In</h3>
                    <h1 style="color: #1976d2; margin: 10px 0;">{hours:02d}:{minutes:02d}:{seconds:02d}</h1>
                    <p style="color: #666;">Next trading session starts at 9:15 AM IST</p>
                </div>
                """, unsafe_allow_html=True)
    
    # New Market Data Tab - Detailed Live Prices
    with tab8:
        st.subheader("🔥 Detailed Market Data & Live Prices")
        
        # Market status
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Market Status", "🟢 Open" if market_open else "🔴 Closed")
        with col2:
            st.metric("Last Updated", get_indian_time().strftime('%H:%M:%S'))
        with col3:
            st.metric("Total Stocks", len(live_prices_data) if live_prices_data else 0)
        
        if live_prices_data:
            # Create a grid of live price cards
            st.subheader("🔥 Top Movers - Real-time Prices")
            
            # Display in rows of 5
            for i in range(0, len(live_prices_data), 5):
                cols = st.columns(5)
                for j, col in enumerate(cols):
                    if i + j < len(live_prices_data):
                        stock = live_prices_data[i + j]
                        
                        # Determine color based on change
                        if stock['change'] > 0:
                            color = "#00C851"
                            arrow = "📈"
                        elif stock['change'] < 0:
                            color = "#ff4444"
                            arrow = "📉"
                        else:
                            color = "#ffa500"
                            arrow = "➡️"
                        
                        with col:
                            st.markdown(f"""
                            <div style="
                                border: 1px solid #ddd;
                                border-radius: 8px;
                                padding: 10px;
                                margin: 5px;
                                background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
                                text-align: center;
                            ">
                                <h4 style="margin: 0; color: #333;">{stock['symbol']}</h4>
                                <p style="margin: 5px 0; font-size: 18px; font-weight: bold; color: {color};">
                                    {arrow} ₹{stock['last_price']:,.2f}
                                </p>
                                <p style="margin: 0; font-size: 12px; color: {color};">
                                    {stock['change']:+.2f} ({stock['change_pct']:+.2f}%)
                                </p>
                                <p style="margin: 0; font-size: 10px; color: #666;">
                                    Vol: {stock['volume']:,}
                                </p>
                            </div>
                            """, unsafe_allow_html=True)
            
            # Detailed live prices table
            st.subheader("📋 Complete Live Prices Table")
            
            live_df = pd.DataFrame(live_prices_data)
            live_df['last_price'] = live_df['last_price'].apply(format_currency)
            live_df['change'] = live_df['change'].apply(lambda x: f"{x:+.2f}")
            live_df['change_pct'] = live_df['change_pct'].apply(lambda x: f"{x:+.2f}%")
            live_df['high'] = live_df['high'].apply(format_currency)
            live_df['low'] = live_df['low'].apply(format_currency)
            live_df['open'] = live_df['open'].apply(format_currency)
            live_df['close'] = live_df['close'].apply(format_currency)
            live_df['volume'] = live_df['volume'].apply(lambda x: f"{x:,}")
            
            st.dataframe(
                live_df[['symbol', 'exchange', 'last_price', 'change', 'change_pct', 'high', 'low', 'open', 'volume']],
                use_container_width=True,
                column_config={
                    "symbol": "Stock",
                    "exchange": "Exchange",
                    "last_price": "LTP",
                    "change": "Change",
                    "change_pct": "Change %",
                    "high": "High",
                    "low": "Low",
                    "open": "Open",
                    "volume": "Volume"
                }
            )
        else:
            st.info("🕐 Live prices will be available when market is open")
            st.markdown("**Market Hours:** 9:15 AM - 3:30 PM IST")
    
    # New Arbitrage Tab
    with tab9:
        st.subheader("⚖️ NSE vs BSE Arbitrage Opportunities")
        
        # Fixed threshold configuration
        st.subheader("⚙️ Arbitrage Settings")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("Profitability Threshold", "0.05%", help="Opportunities above 0.05% gross price difference are marked as profitable")
        
        with col2:
            st.metric("Trading Strategy", "Bidirectional", help="Buy from lower price exchange, sell to higher price exchange")
        
        # Calculate arbitrage opportunities (show all, but mark profitable ones)
        arbitrage_data = calculate_arbitrage_opportunities(live_prices_data, min_profit_threshold=0.0)
        
        # Store arbitrage data in database
        if arbitrage_data:
            try:
                store_arbitrage_spread(arbitrage_data)
            except Exception as e:
                logger.error(f"Error storing arbitrage data: {e}")
        
        # Market status
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Market Status", "🟢 Open" if market_open else "🔴 Closed")
        with col2:
            st.metric("Arbitrage Pairs", len(arbitrage_data))
        with col3:
            significant_opps = len([a for a in arbitrage_data if a['price_difference_pct'] > 0.5])
            st.metric("Significant Opportunities", significant_opps)
        
        # Arbitrage insights
        st.subheader("💡 Arbitrage Insights")
        arbitrage_insights = get_arbitrage_insights(arbitrage_data)
        
        if arbitrage_insights:
            cols = st.columns(min(len(arbitrage_insights), 3))
            for i, insight in enumerate(arbitrage_insights):
                with cols[i % 3]:
                    st.info(insight)
        
        if arbitrage_data:
            # Filter profitable opportunities
            profitable_opportunities = [opp for opp in arbitrage_data if opp['is_profitable']]
            
            # Top arbitrage opportunities based on price difference percentage
            st.markdown("### 🏆 Top Arbitrage Opportunities (by Price Difference %)")
            
            # Sort by price difference percentage and show top 5
            top_opportunities = sorted(arbitrage_data, key=lambda x: x['price_difference_pct'], reverse=True)[:5]
            
            # Display in a compact grid layout
            for i in range(0, len(top_opportunities), 2):
                cols = st.columns(2)
                for j, col in enumerate(cols):
                    if i + j < len(top_opportunities):
                        opp = top_opportunities[i + j]
                        
                        # Determine color and styling based on profitability
                        if opp['is_profitable']:
                            if opp['price_difference_pct'] > 0.5:
                                bg_color = "#fff5f5"
                                border_color = "#ff6b6b"
                                text_color = "#c92a2a"
                                emoji = "🔥"
                                badge = "HIGH"
                            elif opp['price_difference_pct'] > 0.2:
                                bg_color = "#fff4e6"
                                border_color = "#ffa726"
                                text_color = "#d97706"
                                emoji = "⚡"
                                badge = "MEDIUM"
                            else:
                                bg_color = "#f0fdf4"
                                border_color = "#66bb6a"
                                text_color = "#15803d"
                                emoji = "💡"
                                badge = "LOW"
                        else:
                            bg_color = "#fff7ed"
                            border_color = "#ff9800"
                            text_color = "#ea580c"
                            emoji = "⚠️"
                            badge = "BELOW"
                        
                        with col:
                            # Compact card design
                            st.markdown(f"""
                            <div style="
                                border: 1px solid {border_color};
                                border-left: 3px solid {border_color};
                                border-radius: 6px;
                                padding: 8px;
                                margin-bottom: 6px;
                                background: {bg_color};
                                box-shadow: 0 1px 2px rgba(0,0,0,0.05);
                            ">
                                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                                    <h3 style="margin: 0; color: {text_color}; font-size: 15px;">{emoji} {opp['symbol']}</h3>
                                    <span style="
                                        background: {border_color};
                                        color: white;
                                        padding: 1px 6px;
                                        border-radius: 10px;
                                        font-size: 9px;
                                        font-weight: bold;
                                    ">{badge}</span>
                                </div>
                                <div style="display: flex; justify-content: space-between; margin-bottom: 3px;">
                                    <span style="color: #666; font-size: 11px;">Price Diff:</span>
                                    <span style="color: {text_color}; font-weight: bold; font-size: 12px;">{opp['price_difference_pct']:.2f}%</span>
                                </div>
                                <div style="display: flex; justify-content: space-between; margin-bottom: 3px;">
                                    <span style="color: #666; font-size: 11px;">Profit/Share:</span>
                                    <span style="color: {text_color}; font-weight: bold; font-size: 12px;">₹{opp['profit_per_share']:.2f}</span>
                                </div>
                                <div style="border-top: 1px solid #e5e7eb; padding-top: 3px; margin-top: 3px;">
                                    <div style="display: flex; justify-content: space-between; font-size: 10px;">
                                        <span style="color: #666;">NSE: <strong>₹{opp['nse_price']:,.2f}</strong></span>
                                        <span style="color: #666;">BSE: <strong>₹{opp['bse_price']:,.2f}</strong></span>
                                    </div>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # Compact order placement button
                            if st.button(f"📋 Trade {opp['symbol']}", key=f"trade_btn_{opp['symbol']}", use_container_width=True):
                                # Toggle expander state
                                if f"expanded_{opp['symbol']}" not in st.session_state:
                                    st.session_state[f"expanded_{opp['symbol']}"] = True
                                else:
                                    st.session_state[f"expanded_{opp['symbol']}"] = not st.session_state[f"expanded_{opp['symbol']}"]
                            
                            # Order placement section for each opportunity
                            expanded = st.session_state.get(f"expanded_{opp['symbol']}", False)
                            with st.expander(f"📋 Place Orders - {opp['symbol']}", expanded=expanded):
                                # Strategy and Profit Info in a compact layout
                                col_strategy, col_profit = st.columns([2, 1])
                                
                                with col_strategy:
                                    if opp['higher_exchange'] == 'NSE':
                                        st.markdown(f"**🟢 Strategy:** Buy BSE @ ₹{opp['bse_price']:,.2f} → Sell NSE @ ₹{opp['nse_price']:,.2f}")
                                    else:
                                        st.error("❌ Market is closed. Cash-futures pair orders require market hours (9:15 AM - 3:30 PM IST).")
                                        st.markdown(f"**🟢 Strategy:** Buy NSE @ ₹{opp['nse_price']:,.2f} → Sell BSE @ ₹{opp['bse_price']:,.2f}")
                                
                                with col_profit:
                                    st.metric("Profit/Share", format_currency(opp['profit_per_share']), delta=f"{opp['price_difference_pct']:.2f}%")
                                
                                st.markdown("---")
                                
                                # Order placement form in compact layout
                                col_qty, col_type = st.columns(2)
                                
                                with col_qty:
                                    quantity = st.number_input(
                                        "Quantity",
                                        min_value=1,
                                        max_value=1000,
                                        value=1,
                                        step=1,
                                        key=f"qty_{opp['symbol']}",
                                        help=f"Number of shares for {opp['symbol']}"
                                    )
                                
                                with col_type:
                                    order_type = st.selectbox(
                                        "Order Type",
                                        ["MIS", "CNC", "NRML"],
                                        key=f"order_type_{opp['symbol']}",
                                        help="MIS: Intraday, CNC: Delivery, NRML: Carry Forward"
                                    )
                                
                                # Calculate margins and profit
                                buy_price = opp['bse_price'] if opp['higher_exchange'] == 'NSE' else opp['nse_price']
                                sell_price = opp['nse_price'] if opp['higher_exchange'] == 'NSE' else opp['bse_price']
                                
                                buy_margin = calculate_margin_required(buy_price, quantity, order_type)
                                sell_margin = calculate_margin_required(sell_price, quantity, order_type)
                                total_margin = buy_margin + sell_margin
                                expected_profit = quantity * opp['profit_per_share']
                                
                                # Get available margin - try multiple sources
                                available_margin = 0
                                try:
                                    # First try from data
                                    if data and 'margins' in data:
                                        margins_data = data['margins']
                                        if isinstance(margins_data, dict):
                                            equity_margins = margins_data.get('equity', {})
                                            if equity_margins:
                                                available = equity_margins.get('available', {})
                                                if isinstance(available, dict):
                                                    available_margin = available.get('cash', 0)
                                    
                                    # If still 0, try fetching directly from kite
                                    if available_margin == 0:
                                        try:
                                            margins = kite.margins()
                                            if margins and 'equity' in margins:
                                                equity_margins = margins['equity']
                                                if 'available' in equity_margins:
                                                    available = equity_margins['available']
                                                    if isinstance(available, dict):
                                                        available_margin = available.get('cash', 0)
                                                    elif isinstance(available, (int, float)):
                                                        available_margin = available
                                        except:
                                            pass
                                except:
                                    pass
                                
                                # Display margin and profit info in compact format
                                col_margin1, col_margin2, col_profit_total = st.columns(3)
                                
                                with col_margin1:
                                    st.metric("Buy Margin", format_currency(buy_margin))
                                
                                with col_margin2:
                                    st.metric("Sell Margin", format_currency(sell_margin))
                                
                                with col_profit_total:
                                    st.metric("Total Profit", format_currency(expected_profit), delta=f"{opp['price_difference_pct']:.2f}%")
                                
                                # Total margin required
                                col_total_margin, col_available = st.columns(2)
                                
                                with col_total_margin:
                                    margin_status = "✅" if available_margin >= total_margin else "❌"
                                    st.metric(
                                        "Total Margin Required",
                                        format_currency(total_margin),
                                        delta=f"{margin_status} {format_currency(available_margin)} available" if available_margin > 0 else None
                                    )
                                
                                with col_available:
                                    if available_margin > 0:
                                        margin_utilization = (total_margin / available_margin) * 100
                                        if margin_utilization <= 100:
                                            st.metric(
                                                "Available Margin",
                                                format_currency(available_margin),
                                                delta=f"{margin_utilization:.1f}% utilized"
                                            )
                                        else:
                                            st.metric(
                                                "Available Margin",
                                                format_currency(available_margin),
                                                delta="❌ Insufficient margin"
                                            )
                                
                                st.markdown("---")
                                
                                # Place orders button
                                if st.button(f"🚀 Execute Orders - {opp['symbol']}", 
                                           type="primary", 
                                           use_container_width=True,
                                           key=f"execute_{opp['symbol']}"):
                                    
                                    skip_next_auto_refresh()
                                    if market_open:
                                        with st.spinner(f"Placing orders for {opp['symbol']}..."):
                                            # Place arbitrage orders
                                            order_results = place_arbitrage_orders(kite, opp, quantity)
                                            
                                            # Store order history
                                            for order_result in order_results:
                                                try:
                                                    store_order_history({
                                                        'symbol': opp['symbol'],
                                                        'order_type': order_result.get('order_type', 'LIMIT'),
                                                        'transaction_type': order_result.get('action', ''),
                                                        'exchange': order_result.get('exchange', ''),
                                                        'quantity': order_result.get('quantity', quantity),
                                                        'price': order_result.get('price', 0),
                                                        'order_id': order_result['result'].get('order_id', ''),
                                                        'status': 'COMPLETE' if order_result['result'].get('success') else 'FAILED',
                                                        'profit_expected': quantity * opp['profit_per_share']
                                                    })
                                                except Exception as e:
                                                    logger.error(f"Error storing order history: {e}")
                                            
                                            # Show compact inline feedback
                                            successful_orders = [r for r in order_results if r['result']['success']]
                                            
                                            # Compact result display
                                            if len(successful_orders) == 2:
                                                buy_result = next((r for r in order_results if r['action'] == 'BUY'), None)
                                                sell_result = next((r for r in order_results if r['action'] == 'SELL'), None)
                                                buy_id = buy_result['result'].get('order_id', 'N/A')[:8] if buy_result else 'N/A'
                                                sell_id = sell_result['result'].get('order_id', 'N/A')[:8] if sell_result else 'N/A'
                                                st.success(f"✅ **{opp['symbol']}**: BUY {buy_id}... | SELL {sell_id}...")
                                            elif len(successful_orders) == 1:
                                                failed_result = next((r for r in order_results if not r['result']['success']), None)
                                                if failed_result:
                                                    error_msg = failed_result['result']['message']
                                                    if "Insufficient funds" in error_msg:
                                                        st.warning(f"⚠️ **{opp['symbol']}**: Partial - {failed_result['action']} {failed_result['exchange']} failed (Insufficient margin)")
                                                    else:
                                                        short_msg = error_msg[:40] + "..." if len(error_msg) > 40 else error_msg
                                                        st.warning(f"⚠️ **{opp['symbol']}**: Partial - {failed_result['action']} {failed_result['exchange']} failed")
                                            else:
                                                # Both failed - show concise error
                                                error_msg = order_results[0]['result']['message']
                                                if "Insufficient funds" in error_msg:
                                                    st.error(f"❌ **{opp['symbol']}**: Both failed - Insufficient margin")
                                                else:
                                                    st.error(f"❌ **{opp['symbol']}**: Both orders failed")
                                    
                                    else:
                                        st.error("❌ Market is closed. Orders can only be placed during market hours (9:15 AM - 3:30 PM IST)")
                                
                                # Risk warning
                                st.caption("⚠️ **Risk Warning**: Arbitrage trading involves risks. Ensure sufficient funds before placing orders.")
            
            # Place orders for all profitable opportunities
            if profitable_opportunities:
                st.markdown("### 🚀 Place Orders for All Profitable Opportunities")
                
                with st.expander("📋 Place Orders for All Profitable Stocks", expanded=False):
                    # Compact summary metrics
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.metric("Profitable Opportunities", len(profitable_opportunities))
                    
                    with col2:
                        avg_profit_pct = sum(opp['price_difference_pct'] for opp in profitable_opportunities) / len(profitable_opportunities) if profitable_opportunities else 0
                        st.metric("Average Profit (%)", f"{avg_profit_pct:.2f}%")
                    
                    with col3:
                        default_qty = 1
                        total_expected_profit_preview = sum(default_qty * opp['profit_per_share'] for opp in profitable_opportunities)
                        st.metric("Projected Profit (Qty=1)", format_currency(total_expected_profit_preview))
                    
                    with col4:
                        total_orders = len(profitable_opportunities) * 2
                        st.metric("Total Orders Needed", total_orders)
                    
                    # Compact order settings
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        all_quantity = st.number_input(
                            "Quantity per stock",
                            min_value=1,
                            max_value=100,
                            value=1,
                            step=1,
                            key="all_profitable_quantity",
                            help="Quantity to trade for each profitable opportunity"
                        )
                    
                    with col2:
                        all_order_type = st.selectbox(
                            "Order Type",
                            ["MIS", "CNC", "NRML"],
                            key="all_profitable_order_type",
                            help="MIS: Intraday, CNC: Delivery, NRML: Carry Forward"
                        )
                    
                    # Calculate total margin required
                    total_margin_required = 0
                    total_expected_profit = 0
                    for opp in profitable_opportunities:
                        buy_price = opp['bse_price'] if opp['higher_exchange'] == 'NSE' else opp['nse_price']
                        sell_price = opp['nse_price'] if opp['higher_exchange'] == 'NSE' else opp['bse_price']
                        buy_margin = calculate_margin_required(buy_price, all_quantity, all_order_type)
                        sell_margin = calculate_margin_required(sell_price, all_quantity, all_order_type)
                        total_margin_required += (buy_margin + sell_margin)
                        total_expected_profit += (all_quantity * opp['profit_per_share'])
                    
                    # Get available margin
                    available_margin = get_available_margin(kite, data)
                    
                    # Compact margin and profit information
                    col_margin1, col_margin2, col_margin3, col_profit = st.columns(4)
                    
                    with col_margin1:
                        st.metric("Total Margin Required (₹)", format_currency(total_margin_required))
                    
                    with col_margin2:
                        st.metric("Available Margin (₹)", format_currency(available_margin))
                    
                    with col_margin3:
                        if available_margin > 0:
                            margin_utilization = (total_margin_required / available_margin) * 100 if available_margin > 0 else 0
                            st.metric("Margin Utilization (%)", f"{margin_utilization:.1f}%")
                        else:
                            st.metric("Margin Utilization (%)", "N/A")
                    
                    with col_profit:
                        st.metric("Projected Profit (Selected Qty)", format_currency(total_expected_profit))

                    st.caption("Margin Required = Funds needed to place both buy and sell legs. Available Margin = Capital currently free in your broker account.")
                    
                    # Warning if insufficient margin
                    if available_margin > 0 and total_margin_required > available_margin:
                        st.info(f"ℹ️ Margin gap: Required {format_currency(total_margin_required)}, Available {format_currency(available_margin)}. Orders will still be attempted.")
                    
                    # Compact top opportunities preview
                    with st.expander("📊 Top 10 Opportunities Preview", expanded=False):
                        top_opps = sorted(profitable_opportunities, key=lambda x: x['profit_per_share'] * all_quantity, reverse=True)[:10]
                        for opp in top_opps:
                            profit = all_quantity * opp['profit_per_share']
                            st.text(f"• {opp['symbol']}: {opp['price_difference_pct']:.2f}% → {format_currency(profit)}")
                    
                    # Execute orders for all profitable opportunities
                    if st.button("🚀 Execute Orders for All Profitable Opportunities", type="primary", use_container_width=True, key="execute_all_profitable"):
                        if market_open:
                            skip_next_auto_refresh()
                            with st.spinner(f"Placing {len(profitable_opportunities) * 2} orders for {len(profitable_opportunities)} opportunities..."):
                                all_results = []
                                order_by_symbol = {}  # Group orders by symbol
                                
                                for opp in profitable_opportunities:
                                    # Place arbitrage orders for this opportunity
                                    order_results = place_arbitrage_orders(kite, opp, all_quantity)
                                    all_results.extend(order_results)
                                    order_by_symbol[opp['symbol']] = order_results
                                    
                                    # Store order history
                                    for order_result in order_results:
                                        try:
                                            store_order_history({
                                                'symbol': opp['symbol'],
                                                'order_type': order_result.get('order_type', 'LIMIT'),
                                                'transaction_type': order_result.get('action', ''),
                                                'exchange': order_result.get('exchange', ''),
                                                'quantity': order_result.get('quantity', all_quantity),
                                                'price': order_result.get('price', 0),
                                                'order_id': order_result['result'].get('order_id', ''),
                                                'status': 'COMPLETE' if order_result['result'].get('success') else 'FAILED',
                                                'profit_expected': all_quantity * opp['profit_per_share']
                                            })
                                        except Exception as e:
                                            logger.error(f"Error storing order history: {e}")
                                
                                # Calculate summary
                                successful_count = 0
                                failed_count = 0
                                successful_symbols = []
                                failed_symbols = []
                                
                                for symbol, results in order_by_symbol.items():
                                    symbol_success = all(r['result']['success'] for r in results)
                                    if symbol_success:
                                        successful_count += len(results)
                                        successful_symbols.append(symbol)
                                    else:
                                        failed_count += sum(1 for r in results if not r['result']['success'])
                                        successful_count += sum(1 for r in results if r['result']['success'])
                                        failed_symbols.append(symbol)
                                
                                # Show compact summary with inline failed symbols
                                st.markdown("---")
                                st.markdown("### 📊 Execution Summary")
                                col1, col2, col3, col4 = st.columns(4)
                                
                                with col1:
                                    st.metric("Total Orders", len(all_results))
                                with col2:
                                    st.metric("Successful", successful_count, delta=f"{len(successful_symbols)} pairs")
                                with col3:
                                    st.metric("Failed", failed_count, delta=f"{len(failed_symbols)} pairs")
                                with col4:
                                    success_rate = (successful_count / len(all_results)) * 100 if all_results else 0
                                    st.metric("Success Rate", f"{success_rate:.1f}%")
                                
                                # Compact status message with failed symbols
                                if successful_count == len(all_results):
                                    st.success("🎉 **All orders placed successfully!**")
                                elif successful_count > 0:
                                    failed_list = ", ".join(failed_symbols[:5])
                                    if len(failed_symbols) > 5:
                                        failed_list += f" +{len(failed_symbols)-5} more"
                                    st.warning(f"⚠️ **Partial**: {successful_count}/{len(all_results)} orders placed. Failed: {failed_list}")
                                else:
                                    st.error("❌ **All orders failed** - Check margin requirements")
                        
                        else:
                            st.error("❌ Market is closed. Orders can only be placed during market hours (9:15 AM - 3:30 PM IST)")
                    
                    # Single risk warning
                    st.caption("⚠️ **Risk Warning**: Placing orders for all opportunities simultaneously involves significant risk. Ensure sufficient funds and monitor positions carefully.")
            
            # Arbitrage opportunities table
            st.subheader("📊 Complete Arbitrage Opportunities Table")
            
            # Create DataFrame for display
            arbitrage_df = pd.DataFrame(arbitrage_data)
            
            # Format the data for display
            display_df = arbitrage_df.copy()
            display_df['nse_price'] = display_df['nse_price'].apply(format_currency)
            display_df['bse_price'] = display_df['bse_price'].apply(format_currency)
            display_df['price_difference'] = display_df['price_difference'].apply(format_currency)
            display_df['profit_per_share'] = display_df['profit_per_share'].apply(format_currency)
            display_df['price_difference_pct'] = display_df['price_difference_pct'].apply(lambda x: f"{x:.2f}%")
            display_df['arbitrage_score'] = display_df['arbitrage_score'].apply(lambda x: f"{x:.2f}")
            display_df['nse_volume'] = display_df['nse_volume'].apply(lambda x: f"{x:,}")
            display_df['bse_volume'] = display_df['bse_volume'].apply(lambda x: f"{x:,}")
            display_df['avg_volume'] = display_df['avg_volume'].apply(lambda x: f"{x:,}")
            display_df['nse_change_pct'] = display_df['nse_change_pct'].apply(lambda x: f"{x:+.2f}%")
            display_df['bse_change_pct'] = display_df['bse_change_pct'].apply(lambda x: f"{x:+.2f}%")
            
            # Format profitability status with threshold consideration
            def format_profitability(x):
                if x:  # is_profitable is True (price_difference_pct > 0.05%)
                    return "✅ Profitable"
                else:  # is_profitable is False (price_difference_pct <= 0.05%)
                    return "❌ Below Threshold"
            
            display_df['is_profitable'] = display_df['is_profitable'].apply(format_profitability)
            
            # Display the table
            st.dataframe(
                display_df[['symbol', 'nse_price', 'bse_price', 'price_difference_pct', 
                           'higher_exchange', 'profit_per_share', 'is_profitable', 
                           'avg_volume', 'arbitrage_score', 'nse_change_pct', 'bse_change_pct']],
                use_container_width=True,
                column_config={
                    "symbol": "Stock",
                    "nse_price": "NSE Price",
                    "bse_price": "BSE Price",
                    "price_difference_pct": "Price Diff %",
                    "higher_exchange": "Higher Exchange",
                    "profit_per_share": "Profit/Share",
                    "is_profitable": "Profitable?",
                    "avg_volume": "Avg Volume",
                    "arbitrage_score": "Score",
                    "nse_change_pct": "NSE Change %",
                    "bse_change_pct": "BSE Change %"
                }
            )
            
            # Arbitrage charts
            st.subheader("📈 Arbitrage Analysis Charts")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Price difference percentage chart
                fig_diff = px.bar(
                    arbitrage_df.head(10),
                    x='symbol',
                    y='price_difference_pct',
                    title="Top 10 Price Differences (%)",
                    color='price_difference_pct',
                    color_continuous_scale='Reds'
                )
                fig_diff.update_layout(height=400, showlegend=False)
                st.plotly_chart(fig_diff, use_container_width=True)
            
            with col2:
                # Arbitrage score chart
                fig_score = px.bar(
                    arbitrage_df.head(10),
                    x='symbol',
                    y='arbitrage_score',
                    title="Top 10 Arbitrage Scores",
                    color='arbitrage_score',
                    color_continuous_scale='Blues'
                )
                fig_score.update_layout(height=400, showlegend=False)
                st.plotly_chart(fig_score, use_container_width=True)
            
            # Volume vs Price Difference scatter plot
            st.subheader("📊 Volume vs Price Difference Analysis")
            
            fig_scatter = px.scatter(
                arbitrage_df,
                x='avg_volume',
                y='price_difference_pct',
                size='arbitrage_score',
                hover_name='symbol',
                title="Volume vs Price Difference (Size = Arbitrage Score)",
                color='price_difference_pct',
                color_continuous_scale='Viridis'
            )
            fig_scatter.update_layout(height=500)
            st.plotly_chart(fig_scatter, use_container_width=True)
            
            # Exchange comparison
            st.subheader("📊 Exchange Performance Comparison")
            
            nse_avg_change = arbitrage_df['nse_change_pct'].mean()
            bse_avg_change = arbitrage_df['bse_change_pct'].mean()
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("NSE Avg Change", f"{nse_avg_change:.2f}%")
            with col2:
                st.metric("BSE Avg Change", f"{bse_avg_change:.2f}%")
            with col3:
                exchange_diff = nse_avg_change - bse_avg_change
                st.metric("Exchange Difference", f"{exchange_diff:+.2f}%")
            
            # Recent arbitrage orders
            st.subheader("📋 Recent Arbitrage Orders")
            
            # Get recent orders from the orders tab data
            if not orders_df.empty:
                # Filter for recent orders (last 24 hours)
                try:
                    orders_df['order_timestamp_str'] = orders_df['order_timestamp'].astype(str)
                    recent_orders = orders_df.head(10)  # Show last 10 orders
                    
                    if not recent_orders.empty:
                        st.dataframe(
                            recent_orders[['tradingsymbol', 'transaction_type', 'quantity', 'price', 'status', 'order_timestamp']],
                            use_container_width=True
                        )
                    else:
                        st.info("No recent orders found")
                except:
                    st.info("Unable to load recent orders")
            else:
                st.info("No orders found")
            
            # Order status monitoring
            st.subheader("📊 Order Status Monitoring")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                if not orders_df.empty:
                    open_orders = len(orders_df[orders_df['status'] == 'OPEN'])
                    st.metric("Open Orders", open_orders)
                else:
                    st.metric("Open Orders", 0)
            
            with col2:
                if not orders_df.empty:
                    complete_orders = len(orders_df[orders_df['status'] == 'COMPLETE'])
                    st.metric("Completed Orders", complete_orders)
                else:
                    st.metric("Completed Orders", 0)
            
            with col3:
                if not orders_df.empty:
                    cancelled_orders = len(orders_df[orders_df['status'] == 'CANCELLED'])
                    st.metric("Cancelled Orders", cancelled_orders)
                else:
                    st.metric("Cancelled Orders", 0)
            
            with col4:
                if not orders_df.empty:
                    rejected_orders = len(orders_df[orders_df['status'] == 'REJECTED'])
                    st.metric("Rejected Orders", rejected_orders)
                else:
                    st.metric("Rejected Orders", 0)
            
            # Trading recommendations
            st.subheader("🎯 Arbitrage Trading Recommendations")
            
            recommendations = [
                "⚡ **Quick Execution**: Arbitrage opportunities are time-sensitive, execute quickly",
                "💰 **Minimum Profit**: Only trade if profit covers transaction costs and taxes",
                "📊 **Volume Check**: Ensure sufficient volume for both buy and sell orders",
                "⏰ **Market Hours**: Execute during market hours for best liquidity",
                "🛡️ **Risk Management**: Set stop-losses and don't risk more than 2% of capital",
                "📈 **Trend Analysis**: Check if price differences are increasing or decreasing",
                "🔄 **Continuous Monitoring**: Arbitrage opportunities change rapidly",
                "💡 **Order Management**: Monitor order status and be ready to cancel if needed",
                "📱 **Real-time Alerts**: Set up alerts for significant price differences"
            ]
            
            for rec in recommendations:
                st.success(rec)
        
        else:
            st.info("🕐 No arbitrage opportunities found or market data not available")
            st.markdown("**Note:** Arbitrage opportunities will appear when:")
            st.markdown("• Market is open and both NSE and BSE data is available")
            st.markdown("• Price differences exist between exchanges")
            st.markdown("• Sufficient volume is available for trading")
    
    # Theta Capture Strategy Tab (Time Value Decay)
    with tab10:
        st.subheader("📅 Theta Capture Strategy (Time Value Decay)")
        
        st.info("""
        **Strategy Overview**: 
        - Buy in cash market, Sell futures contract
        - Futures typically trade at premium to cash (time value/theta)
        - At expiry, prices converge - capture the premium as theta decays
        - This is a **time value decay strategy**, not arbitrage
        - Best when futures premium is high relative to days to expiry
        """)
        
        # Strategy settings
        col1, col2, col3 = st.columns(3)
        
        with col1:
            min_premium_pct = st.number_input(
                "Minimum Premium %",
                min_value=0.0,
                max_value=10.0,
                value=0.1,
                step=0.1,
                help="Minimum premium percentage to show opportunity"
            )
        
        with col2:
            min_days_expiry = st.number_input(
                "Min Days to Expiry",
                min_value=1,
                max_value=30,
                value=1,
                step=1,
                help="Minimum days remaining until futures expiry"
            )
        
        with col3:
            max_days_expiry = st.number_input(
                "Max Days to Expiry",
                min_value=1,
                max_value=60,
                value=30,
                step=1,
                help="Maximum days remaining until futures expiry"
            )
        
        # Get popular stocks for analysis
        popular_stocks = [
            "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "HINDUNILVR", "SBIN",
            "BHARTIARTL", "ITC", "KOTAKBANK", "LT", "AXISBANK", "ASIANPAINT", "MARUTI",
            "TITAN", "NESTLEIND", "ULTRACEMCO", "HCLTECH", "WIPRO", "SUNPHARMA", "BAJFINANCE",
            "TATAMOTORS", "TATASTEEL", "JSWSTEEL", "ADANIENT", "ONGC", "NTPC", "POWERGRID"
        ]
        
        if st.button("🔍 Find Theta Capture Opportunities", type="primary"):
            with st.spinner("Fetching futures contracts and prices..."):
                # Get futures contracts
                futures_data = get_futures_contracts(kite, popular_stocks)
                
                if futures_data:
                    st.success(f"✅ Found {len(futures_data)} stocks with futures contracts")
                    
                    # Calculate opportunities
                    opportunities = calculate_cash_futures_opportunities(kite, list(futures_data.keys()), futures_data)
                    
                    # Store cash-futures data in database
                    if opportunities:
                        try:
                            store_cash_futures_spread(opportunities)
                        except Exception as e:
                            logger.error(f"Error storing cash-futures data: {e}")
                    
                    # Filter opportunities
                    filtered_opps = [
                        opp for opp in opportunities
                        if opp['premium_pct'] >= min_premium_pct
                        and min_days_expiry <= opp['days_to_expiry'] <= max_days_expiry
                    ]
                    
                    if filtered_opps:
                        st.subheader(f"🎯 Found {len(filtered_opps)} Opportunities")
                        
                        # Display top opportunities
                        for opp in filtered_opps[:10]:  # Show top 10
                            cash_product = "CNC"
                            fut_product = "NRML"
                            
                            theta_feedback = st.session_state.setdefault("theta_feedback", {})
                            symbol_feedback = theta_feedback.setdefault(opp['symbol'], {
                                "status": None,
                                "messages": []
                            })
                            expanded_state = st.session_state.get(f"theta_expanded_{opp['symbol']}", False)
                            if symbol_feedback.get("status") or symbol_feedback.get("messages"):
                                expanded_state = True

                            with st.expander(
                                f"📊 {opp['symbol']} - Premium: {opp['premium_pct']:.2f}% | Days: {opp['days_to_expiry']} | Annualized: {opp['annualized_premium']:.1f}%",
                                expanded=expanded_state
                                ):
                                lot_size = opp.get('lot_size') or 1
                                map_lot = LOT_SIZE_MAP.get(opp['symbol'].upper())
                                if map_lot:
                                    lot_size = map_lot
                                try:
                                    lot_size = int(lot_size)
                                except Exception:
                                    lot_size = 1
                                if lot_size < 1:
                                    lot_size = 1

                                order_type_value = "MARKET"

                                cash_price_fmt = format_currency(opp['cash_price'])
                                futures_price_fmt = format_currency(opp['futures_price'])
                                premium_fmt = format_currency(opp['premium'])
                                expected_per_share_fmt = format_currency(opp['profit_per_share'])

                                # Price Snapshot Section
                                with st.container(border=True):
                                    st.markdown("### 💰 Price Snapshot")
                                    price_cols = st.columns(3)
                                    with price_cols[0]:
                                        st.metric("Cash", cash_price_fmt)
                                    with price_cols[1]:
                                        st.metric("Futures", futures_price_fmt)
                                    with price_cols[2]:
                                        st.metric("Premium", premium_fmt)
                                    st.caption(f"Premium: {opp['premium_pct']:.2f}% | Profit/share: {expected_per_share_fmt}")

                                # Expiry Detail Section
                                with st.container(border=True):
                                    st.markdown("### 📅 Expiry Detail")
                                    expiry_cols = st.columns(3)
                                    with expiry_cols[0]:
                                        st.metric("Days to Expiry", opp['days_to_expiry'])
                                    with expiry_cols[1]:
                                        st.metric("Expiry Date", opp['expiry_date'])
                                    with expiry_cols[2]:
                                        st.metric("Annualized Return", f"{opp['annualized_premium']:.1f}%")
                                    st.caption("Strategy: Buy cash, sell futures to capture theta decay")

                                # Quantity Input
                                num_lots = st.number_input(
                                    "Quantity (lots)",
                                    min_value=1,
                                    max_value=100,
                                    value=1,
                                    step=1,
                                    key=f"cf_qty_{opp['symbol']}",
                                    help=f"Lot size: {lot_size} shares. Total quantity = lots × lot size."
                                )

                                actual_qty = num_lots * lot_size
                                expected_profit = actual_qty * opp['profit_per_share']

                                cash_margin = calculate_margin_required(opp['cash_price'], actual_qty, cash_product)
                                fut_margin = calculate_margin_required(opp['futures_price'], actual_qty, fut_product)
                                total_margin = cash_margin + fut_margin
                                expected_profit_fmt = format_currency(expected_profit)
                                cash_margin_fmt = format_currency(cash_margin)
                                fut_margin_fmt = format_currency(fut_margin)
                                total_margin_fmt = format_currency(total_margin)

                                available_margin = get_available_margin(kite, data)
                                available_margin_fmt = format_currency(available_margin)

                                # Position Summary Section
                                with st.container(border=True):
                                    st.markdown("### 📊 Position Summary")
                                    pos_cols = st.columns(3)
                                    with pos_cols[0]:
                                        st.metric("Lots", num_lots)
                                    with pos_cols[1]:
                                        st.metric("Lot Size", lot_size)
                                    with pos_cols[2]:
                                        st.metric("Total Quantity", actual_qty)
                                    st.caption(f"Cash Product: {cash_product} | Futures Product: {fut_product}")

                                # Margin & Profit Section
                                with st.container(border=True):
                                    st.markdown("### 💵 Margin & Profit")
                                    margin_cols = st.columns(2)
                                    with margin_cols[0]:
                                        st.metric("Cash Margin", cash_margin_fmt)
                                        st.metric("Futures Margin", fut_margin_fmt)
                                    with margin_cols[1]:
                                        st.metric("Total Margin", total_margin_fmt)
                                        st.metric("Expected Profit", expected_profit_fmt, delta=f"{opp['premium_pct']:.2f}%")
                                    st.caption(f"Available Margin: {available_margin_fmt}")

                                if available_margin > 0 and total_margin > available_margin:
                                    st.warning(f"⚠️ Margin gap: Need {total_margin_fmt}, available {available_margin_fmt}. Broker will validate at execution.")
                                elif available_margin == 0:
                                    st.info("ℹ️ Available margin not detected. Orders will still be attempted and validated by broker.")

                                # Session state to track order statuses per symbol
                                if "theta_order_status" not in st.session_state:
                                    st.session_state["theta_order_status"] = {}
                                symbol_status_key = opp['symbol']
                                symbol_status_list = st.session_state["theta_order_status"].setdefault(symbol_status_key, [])

                                # Combined execution controls
                                # ------------------------------------------------------------------
                                # Cash-futures execution: 1-click action with inline feedback persisted in session state
                                # ------------------------------------------------------------------
                                def render_theta_feedback(feedback):
                                    status_info = feedback.get("status")
                                    if status_info and status_info.get("content"):
                                        status_type = status_info.get("type", "info")
                                        content = status_info["content"]
                                        if status_type == "success":
                                            st.success(content)
                                        elif status_type == "error":
                                            st.error(content)
                                        elif status_type == "warning":
                                            st.warning(content)
                                        else:
                                            st.info(content)

                                    for msg in feedback.get("messages", []):
                                        msg_type = msg.get("type", "info")
                                        content = msg.get("content", "")
                                        if not content:
                                            continue
                                        if msg_type == "success":
                                            st.success(content)
                                        elif msg_type == "error":
                                            st.error(content)
                                        elif msg_type == "warning":
                                            st.warning(content)
                                        else:
                                            st.info(content)

                                # Execution Section
                                with st.container(border=True):
                                    st.markdown("### ⚙️ Execution")
                                    st.caption("Place the cash and futures legs together with one click")
                                    button_clicked = st.button(
                                        "🚀 Execute Pair",
                                        key=f"theta_execute_pair_{opp['symbol']}",
                                        use_container_width=True,
                                        type="primary"
                                    )

                                if button_clicked:
                                    st.session_state[f"theta_expanded_{opp['symbol']}"] = True
                                    logging.info(
                                        "Theta pair button clicked | symbol=%s lots=%s order_type=%s",
                                        opp['symbol'], num_lots, order_type_value
                                    )
                                    skip_next_auto_refresh()

                                    symbol_feedback["messages"] = []
                                    
                                    if market_open:
                                        start_msg = f"🚀 Executing cash-futures orders for {opp['symbol']}..."
                                        symbol_feedback["status"] = {"type": "info", "content": start_msg}
                                        try:
                                            pair_results = place_cash_futures_orders(
                                                kite=kite,
                                                opportunity=opp,
                                                lots=num_lots,
                                                cash_product=cash_product,
                                                futures_product=fut_product
                                            )
                                            
                                            # Store order history
                                            for leg_result in pair_results:
                                                try:
                                                    store_order_history({
                                                        'symbol': opp['symbol'],
                                                        'order_type': 'MARKET',
                                                        'transaction_type': leg_result.get('action', ''),
                                                        'exchange': leg_result.get('exchange', ''),
                                                        'quantity': leg_result.get('quantity', actual_qty),
                                                        'price': leg_result.get('price', 0),
                                                        'order_id': leg_result['result'].get('order_id', ''),
                                                        'status': 'COMPLETE' if leg_result['result'].get('success') else 'FAILED',
                                                        'profit_expected': expected_profit
                                                    })
                                                except Exception as e:
                                                    logger.error(f"Error storing order history: {e}")
                                        except Exception as exec_err:
                                            logging.exception("Theta pair order failed for %s: %s", opp['symbol'], exec_err)
                                            error_text = f"❌ Order processing failed for {opp['symbol']}: {exec_err}"
                                            symbol_feedback["status"] = {"type": "error", "content": error_text}
                                            symbol_feedback["messages"].append({"type": "error", "content": error_text})
                                        else:
                                            new_history = []
                                            success_count = 0
                                            for leg_result in pair_results:
                                                feedback = leg_result.get("result", {})
                                                success_flag = feedback.get("success", False)
                                                message_text = feedback.get("message", "Unknown error")
                                                order_id = feedback.get("order_id", "")
                                                display_qty = leg_result.get("quantity", actual_qty)
                                                action_text = leg_result.get("action", "")
                                                market_text = leg_result.get("market", "")
                                                
                                                leg_market = leg_result.get("market", "")
                                                product_used = fut_product if leg_market == "FUTURES" else cash_product
                                                leg_label = f"{action_text} {'FUT' if leg_market == 'FUTURES' else 'CASH'}".strip()
                                                
                                                new_history.append({
                                                    "time": get_indian_time().strftime('%H:%M:%S'),
                                                    "leg": leg_label,
                                                    "market": leg_market if leg_market else "",
                                                    "product": product_used,
                                                    "quantity": display_qty,
                                                    "price": "Market",
                                                    "status": "✅" if success_flag else "❌",
                                                    "order_id": order_id,
                                                    "message": message_text
                                                })
                                                
                                                leg_desc = f"{action_text} {leg_market}".strip() if leg_market else action_text
                                                order_text = f"{leg_desc}: {display_qty} @ Market"
                                                if order_id:
                                                    order_text += f" (Order: {order_id})"
                                                
                                                if success_flag:
                                                    symbol_feedback["messages"].append({
                                                        "type": "success",
                                                        "content": f"✅ {order_text}"
                                                    })
                                                    success_count += 1
                                                else:
                                                    error_msg = message_text or "Order failed"
                                                    symbol_feedback["messages"].append({
                                                        "type": "error",
                                                        "content": f"❌ {order_text} — {error_msg}"
                                                    })
                                            
                                            symbol_status_list.extend(new_history)
                                            
                                            if success_count == len(pair_results):
                                                symbol_feedback["status"] = {
                                                    "type": "success",
                                                    "content": f"✅ Orders processed for {opp['symbol']}"
                                                }
                                            elif success_count > 0:
                                                symbol_feedback["status"] = {
                                                    "type": "warning",
                                                    "content": f"⚠️ Partial execution for {opp['symbol']}. Review the order legs below."
                                                }
                                            else:
                                                symbol_feedback["status"] = {
                                                    "type": "error",
                                                    "content": f"❌ Orders failed for {opp['symbol']}"
                                                }
                                    else:
                                        symbol_feedback["status"] = {
                                            "type": "error",
                                            "content": "❌ Market is closed. Cash-futures pair orders require market hours (9:15 AM - 3:30 PM IST)."
                                        }

                                    st.session_state["theta_feedback"][opp['symbol']] = symbol_feedback
                                    render_theta_feedback(symbol_feedback)
                                else:
                                    render_theta_feedback(symbol_feedback)
                                
                                
                                # Display order status history for this symbol
                                if symbol_status_list:
                                    status_df = pd.DataFrame(symbol_status_list[::-1])  # Latest first
                                    status_df_display = status_df.copy()
                                    # Trim message length for display
                                    status_df_display["message"] = status_df_display["message"].apply(
                                        lambda x: (x[:77] + "...") if isinstance(x, str) and len(x) > 80 else x
                                    )
                                    status_df_display.rename(
                                        columns={
                                            "time": "Time",
                                            "leg": "Leg",
                                            "market": "Market",
                                            "product": "Product",
                                            "quantity": "Qty",
                                            "price": "Price",
                                            "status": "Status",
                                            "order_id": "Order ID",
                                            "message": "Exchange Response"
                                        },
                                        inplace=True
                                    )
                                    st.markdown("#### 📋 Order Status History")
                                    st.dataframe(
                                        status_df_display,
                                        use_container_width=True
                                    )
                        
                        # Summary table
                        if len(filtered_opps) > 1:
                            st.subheader("📊 All Opportunities Summary")
                            
                            summary_df = pd.DataFrame(filtered_opps)
                            display_df = summary_df.copy()
                            display_df['cash_price'] = display_df['cash_price'].apply(format_currency)
                            display_df['futures_price'] = display_df['futures_price'].apply(format_currency)
                            display_df['premium'] = display_df['premium'].apply(format_currency)
                            display_df['premium_pct'] = display_df['premium_pct'].apply(lambda x: f"{x:.2f}%")
                            display_df['annualized_premium'] = display_df['annualized_premium'].apply(lambda x: f"{x:.1f}%")
                            display_df['profit_per_share'] = display_df['profit_per_share'].apply(format_currency)
                            
                            st.dataframe(
                                display_df[['symbol', 'cash_price', 'futures_price', 'premium', 'premium_pct', 
                                          'days_to_expiry', 'annualized_premium', 'profit_per_share']],
                                use_container_width=True
                            )
                    else:
                        st.warning(f"No opportunities found matching criteria (Premium ≥{min_premium_pct}%, Days: {min_days_expiry}-{max_days_expiry})")
                else:
                    st.warning("No futures contracts found for the selected stocks. Try different stocks or check if futures are available.")
        
        # Strategy explanation
        st.markdown("---")
        st.subheader("📚 Strategy Explanation")
        
        col_exp1, col_exp2 = st.columns(2)
        
        with col_exp1:
            st.markdown("""
            **How It Works (Theta Decay):**
            1. Futures contracts typically trade at a premium to cash
            2. This premium represents time value (theta)
            3. Buy cash, sell futures to lock in the premium
            4. As time passes, theta decays - premium erodes
            5. At expiry, prices converge - you capture the premium
            6. **This is time value decay, not arbitrage**
            """)
        
        with col_exp2:
            st.markdown("""
            **Key Metrics:**
            - **Premium %**: How much futures is above cash
            - **Days to Expiry**: Time remaining for theta decay
            - **Annualized Return**: Premium return if held to expiry
            - **Opportunity Score**: Combines premium and time
            - **Theta**: Rate of time value decay
            """)
        
        st.warning("⚠️ **Risk**: This is a theta capture strategy (time value decay), not arbitrage. Requires holding until expiry. Monitor positions and be aware of margin requirements.")
    
    # Historical Insights Tab
    with tab11:
        st.subheader("📊 Historical Spread Insights & Analytics")
        
        # Time period selector
        col1, col2, col3 = st.columns(3)
        with col1:
            days_back = st.selectbox(
                "Analysis Period",
                [7, 14, 30, 60, 90],
                index=0,
                format_func=lambda x: f"Last {x} days"
            )
        with col2:
            st.metric("Database Status", "✅ Active")
        with col3:
            if st.button("🧹 Cleanup Old Data (>90 days)", help="Remove data older than 90 days"):
                result = cleanup_old_data(days_to_keep=90)
                if result:
                    st.success(f"Cleaned: {result['arbitrage_deleted']} arbitrage, {result['cash_futures_deleted']} cash-futures, {result['orders_deleted']} orders")
        
        # Arbitrage Historical Insights
        st.subheader("⚖️ Arbitrage Spread History")
        
        arbitrage_insights = get_arbitrage_insights_from_db(days=days_back)
        
        if arbitrage_insights['total_records'] > 0:
            col1, col2, col3, col4, col5 = st.columns(5)
            
            with col1:
                st.metric("Total Records", f"{arbitrage_insights['total_records']:,}")
            with col2:
                st.metric("Unique Symbols", arbitrage_insights['unique_symbols'])
            with col3:
                st.metric("Avg Spread %", f"{arbitrage_insights['avg_spread_pct']:.3f}%")
            with col4:
                st.metric("Max Spread %", f"{arbitrage_insights['max_spread_pct']:.3f}%")
            with col5:
                st.metric("Profitable Rate", f"{arbitrage_insights['profitable_pct']:.1f}%")
            
            # Best performing symbols
            st.subheader("🏆 Top Performing Arbitrage Symbols")
            top_arbitrage = get_top_arbitrage_symbols(days=days_back, limit=10)
            
            if not top_arbitrage.empty:
                st.dataframe(
                    top_arbitrage[['symbol', 'avg_spread', 'max_spread', 'profitability_rate', 'count']],
                    use_container_width=True,
                    column_config={
                        "symbol": "Symbol",
                        "avg_spread": st.column_config.NumberColumn("Avg Spread %", format="%.3f%%"),
                        "max_spread": st.column_config.NumberColumn("Max Spread %", format="%.3f%%"),
                        "profitability_rate": st.column_config.NumberColumn("Profitability %", format="%.1f%%"),
                        "count": "Records"
                    }
                )
                
                # Chart for top symbols
                fig_arb = px.bar(
                    top_arbitrage.head(10),
                    x='symbol',
                    y='avg_spread',
                    title=f"Top 10 Symbols by Average Spread (Last {days_back} days)",
                    color='profitability_rate',
                    color_continuous_scale='Greens'
                )
                fig_arb.update_layout(height=400, showlegend=False)
                st.plotly_chart(fig_arb, use_container_width=True)
            
            # Historical spread trend
            st.subheader("📈 Historical Spread Trend")
            hist_df = get_arbitrage_spread_history(days=days_back)
            
            if not hist_df.empty:
                st.markdown("<div style='height:0.75rem'></div>", unsafe_allow_html=True)
                hist_df['date'] = pd.to_datetime(hist_df['timestamp']).dt.date
                daily_stats = hist_df.groupby('date').agg({
                    'price_difference_pct': ['mean', 'max', 'min'],
                    'is_profitable': 'sum'
                }).reset_index()
                daily_stats.columns = ['date', 'avg_spread', 'max_spread', 'min_spread', 'profitable_count']
                
                fig_trend = make_subplots(
                    rows=2, cols=1,
                    subplot_titles=('Average Spread % Over Time', 'Profitable Opportunities Count'),
                    vertical_spacing=0.15,
                    row_heights=[0.6, 0.4],
                    specs=[[{"secondary_y": False}], [{"secondary_y": False}]]
                )
                
                # Add traces first
                fig_trend.add_trace(
                    go.Scatter(x=daily_stats['date'], y=daily_stats['avg_spread'], 
                              name='Avg Spread', line=dict(color='blue', width=2)),
                    row=1, col=1
                )
                fig_trend.add_trace(
                    go.Scatter(x=daily_stats['date'], y=daily_stats['max_spread'], 
                              name='Max Spread', line=dict(color='red', dash='dash', width=2)),
                    row=1, col=1
                )
                
                fig_trend.add_trace(
                    go.Bar(x=daily_stats['date'], y=daily_stats['profitable_count'], 
                           name='Profitable Count', marker_color='green', opacity=0.7),
                    row=2, col=1
                )
                
                # Update layout after adding traces
                fig_trend.update_layout(
                    height=700,
                    margin=dict(l=50, r=40, t=100, b=60),
                    legend=dict(orientation='h', yanchor='bottom', y=-0.15, xanchor='center', x=0.5),
                    showlegend=True
                )
                
                # Update axes and annotations
                fig_trend.update_annotations(font=dict(size=14), yshift=10)
                fig_trend.update_xaxes(title_text="Date", row=2, col=1, showgrid=True)
                fig_trend.update_xaxes(title_text="", row=1, col=1, showgrid=True)
                fig_trend.update_yaxes(title_text="Avg Spread (%)", row=1, col=1, showgrid=True)
                fig_trend.update_yaxes(title_text="Profitable Count", row=2, col=1, showgrid=True)
                st.plotly_chart(fig_trend, use_container_width=True)
                st.markdown("<div style='height:1.25rem'></div>", unsafe_allow_html=True)
                
                # Trend insights
                if len(daily_stats) > 1:
                    trend_change = ((daily_stats['avg_spread'].iloc[-1] - daily_stats['avg_spread'].iloc[0]) / 
                                   daily_stats['avg_spread'].iloc[0]) * 100 if daily_stats['avg_spread'].iloc[0] != 0 else 0
                    trend_direction = "📈 Increasing" if trend_change > 0 else "📉 Decreasing"
                    st.info(f"**Trend**: {trend_direction} by {abs(trend_change):.2f}% over the period")
        else:
            st.info("No arbitrage spread data available. Data will be collected as you use the Arbitrage tab.")
        
        # Cash-Futures Historical Insights
        st.subheader("📅 Cash-Futures Spread History")
        
        cash_futures_insights = get_cash_futures_insights_from_db(days=days_back)
        
        if cash_futures_insights['total_records'] > 0:
            col1, col2, col3, col4, col5 = st.columns(5)
            
            with col1:
                st.metric("Total Records", f"{cash_futures_insights['total_records']:,}")
            with col2:
                st.metric("Unique Symbols", cash_futures_insights['unique_symbols'])
            with col3:
                st.metric("Avg Premium %", f"{cash_futures_insights['avg_premium_pct']:.3f}%")
            with col4:
                st.metric("Max Premium %", f"{cash_futures_insights['max_premium_pct']:.3f}%")
            with col5:
                st.metric("Avg Annualized", f"{cash_futures_insights['avg_annualized_premium']:.1f}%")
            
            # Best performing symbols
            st.subheader("🏆 Top Performing Cash-Futures Symbols")
            top_cf = get_top_cash_futures_symbols(days=days_back, limit=10)
            
            if not top_cf.empty:
                st.dataframe(
                    top_cf[['symbol', 'avg_premium', 'max_premium', 'avg_annualized']],
                    use_container_width=True,
                    column_config={
                        "symbol": "Symbol",
                        "avg_premium": st.column_config.NumberColumn("Avg Premium %", format="%.3f%%"),
                        "max_premium": st.column_config.NumberColumn("Max Premium %", format="%.3f%%"),
                        "avg_annualized": st.column_config.NumberColumn("Avg Annualized %", format="%.1f%%")
                    }
                )
                
                # Chart for top symbols
                fig_cf = px.bar(
                    top_cf.head(10),
                    x='symbol',
                    y='avg_premium',
                    title=f"Top 10 Symbols by Average Premium (Last {days_back} days)",
                    color='avg_annualized',
                    color_continuous_scale='Blues'
                )
                fig_cf.update_layout(height=400, showlegend=False)
                st.plotly_chart(fig_cf, use_container_width=True)
            
            # Historical premium trend
            st.subheader("📈 Historical Premium Trend")
            cf_hist_df = get_cash_futures_spread_history(days=days_back)
            
            if not cf_hist_df.empty:
                cf_hist_df['date'] = pd.to_datetime(cf_hist_df['timestamp']).dt.date
                daily_cf_stats = cf_hist_df.groupby('date').agg({
                    'premium_pct': ['mean', 'max', 'min'],
                    'annualized_premium': 'mean'
                }).reset_index()
                daily_cf_stats.columns = ['date', 'avg_premium', 'max_premium', 'min_premium', 'avg_annualized']
                
                fig_cf_trend = make_subplots(
                    rows=2, cols=1,
                    subplot_titles=('Average Premium % Over Time', 'Average Annualized Return %'),
                    vertical_spacing=0.15,
                    row_heights=[0.6, 0.4],
                    specs=[[{"secondary_y": False}], [{"secondary_y": False}]]
                )
                
                # Add traces first
                fig_cf_trend.add_trace(
                    go.Scatter(x=daily_cf_stats['date'], y=daily_cf_stats['avg_premium'], 
                              name='Avg Premium', line=dict(color='purple', width=2)),
                    row=1, col=1
                )
                fig_cf_trend.add_trace(
                    go.Scatter(x=daily_cf_stats['date'], y=daily_cf_stats['max_premium'], 
                              name='Max Premium', line=dict(color='red', dash='dash', width=2)),
                    row=1, col=1
                )
                
                fig_cf_trend.add_trace(
                    go.Scatter(x=daily_cf_stats['date'], y=daily_cf_stats['avg_annualized'], 
                              name='Avg Annualized', line=dict(color='green', width=2)),
                    row=2, col=1
                )
                
                # Update layout after adding traces
                fig_cf_trend.update_layout(
                    height=700,
                    margin=dict(l=50, r=40, t=100, b=60),
                    legend=dict(orientation='h', yanchor='bottom', y=-0.15, xanchor='center', x=0.5),
                    showlegend=True
                )
                
                # Update axes and annotations
                fig_cf_trend.update_annotations(font=dict(size=14), yshift=10)
                fig_cf_trend.update_xaxes(title_text="Date", row=2, col=1, showgrid=True)
                fig_cf_trend.update_xaxes(title_text="", row=1, col=1, showgrid=True)
                fig_cf_trend.update_yaxes(title_text="Premium (%)", row=1, col=1, showgrid=True)
                fig_cf_trend.update_yaxes(title_text="Annualized Return (%)", row=2, col=1, showgrid=True)
                st.plotly_chart(fig_cf_trend, use_container_width=True)
        else:
            st.info("No cash-futures spread data available. Data will be collected as you use the Theta Capture tab.")
        
        # Order History
        st.subheader("📋 Order Execution History")
        
        order_hist = get_order_history(days=days_back)
        
        if not order_hist.empty:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Orders", len(order_hist))
            with col2:
                successful = len(order_hist[order_hist['status'] == 'COMPLETE'])
                st.metric("Successful", successful)
            with col3:
                success_rate = (successful / len(order_hist)) * 100 if len(order_hist) > 0 else 0
                st.metric("Success Rate", f"{success_rate:.1f}%")
            
            # Recent orders table
            st.dataframe(
                order_hist[['symbol', 'order_type', 'transaction_type', 'exchange', 'quantity', 'price', 'status', 'timestamp']].head(50),
                use_container_width=True
            )
        else:
            st.info("No order history available. Orders will be tracked when you place trades.")
        
        # Summary Insights
        st.subheader("💡 Key Insights")
        
        insights_list = []
        
        if arbitrage_insights['total_records'] > 0:
            if arbitrage_insights.get('best_symbol'):
                insights_list.append(f"🏆 **Best Arbitrage Symbol**: {arbitrage_insights['best_symbol']} with avg spread of {arbitrage_insights.get('best_symbol_avg_spread', 0):.3f}%")
            
            if arbitrage_insights.get('trend') != 'no_data':
                insights_list.append(f"📈 **Arbitrage Trend**: {arbitrage_insights['trend']} by {abs(arbitrage_insights.get('trend_change_pct', 0)):.2f}%")
            
            insights_list.append(f"💰 **Profitable Opportunities**: {arbitrage_insights['profitable_opportunities']} out of {arbitrage_insights['total_records']} ({arbitrage_insights['profitable_pct']:.1f}%)")
        
        if cash_futures_insights['total_records'] > 0:
            if cash_futures_insights.get('best_symbol'):
                insights_list.append(f"🏆 **Best Cash-Futures Symbol**: {cash_futures_insights['best_symbol']} with avg premium of {cash_futures_insights.get('best_symbol_avg_premium', 0):.3f}%")
            
            insights_list.append(f"📊 **Average Annualized Return**: {cash_futures_insights['avg_annualized_premium']:.1f}%")
        
        if insights_list:
            for insight in insights_list:
                st.success(insight)
        else:
            st.info("💡 **Tip**: Use the Arbitrage and Theta Capture tabs to start collecting historical data for insights.")
    
    # Footer
    st.markdown("---")
    st.markdown(f"**Last updated:** {get_indian_time().strftime('%Y-%m-%d %H:%M:%S IST')}")
    
    # Auto-refresh indicator
    if auto_refresh:
        st.markdown(f"🔄 **Auto-refreshing every {refresh_interval} seconds**")
    
    # Auto-refresh logic
    skip_auto = st.session_state.pop('skip_auto_refresh', False)
    if auto_refresh and not skip_auto:
        time.sleep(refresh_interval)
        st.rerun()

if __name__ == "__main__":
    main()