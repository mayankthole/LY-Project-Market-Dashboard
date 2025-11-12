"""
Main dashboard overview UI components
"""
import streamlit as st
import pandas as pd
from utils import format_currency, get_indian_time
from calculations import calculate_risk_metrics, get_market_insights
from data_fetcher import format_live_price_data


def render_dashboard_overview(holdings_df, net_positions_df, orders_df, data):
    """Render main dashboard overview section"""
    # Main metrics
    st.subheader("📊 Portfolio Overview")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_pnl = holdings_df['pnl'].sum() if not holdings_df.empty else 0
        pnl_class = "positive" if total_pnl >= 0 else "negative"
        pnl_emoji = "📈" if total_pnl >= 0 else "📉"
        st.markdown(f"""
        <div class="metric-card">
            <h3>{pnl_emoji} Total P&L</h3>
            <div class="{pnl_class}">{format_currency(total_pnl)}</div>
            <small>All Holdings</small>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        total_holdings = len(holdings_df) if not holdings_df.empty else 0
        st.markdown(f"""
        <div class="metric-card">
            <h3>💼 Holdings</h3>
            <div style="font-size: 2rem;">{total_holdings}</div>
            <small>Stocks Owned</small>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        total_positions = len(net_positions_df) if not net_positions_df.empty else 0
        st.markdown(f"""
        <div class="metric-card">
            <h3>📈 Positions</h3>
            <div style="font-size: 2rem;">{total_positions}</div>
            <small>Active Trades</small>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        pending_orders = len(orders_df[orders_df['status'] == 'OPEN']) if not orders_df.empty else 0
        st.markdown(f"""
        <div class="metric-card">
            <h3>📋 Pending</h3>
            <div style="font-size: 2rem;">{pending_orders}</div>
            <small>Open Orders</small>
        </div>
        """, unsafe_allow_html=True)
    
    # Additional metrics row
    if not holdings_df.empty or not net_positions_df.empty:
        st.subheader("📈 Detailed Metrics")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if not holdings_df.empty:
                total_investment = (holdings_df['quantity'] * holdings_df['average_price']).sum()
                st.metric("Total Investment", format_currency(total_investment))
            else:
                st.metric("Total Investment", "₹0")
        
        with col2:
            if not holdings_df.empty:
                total_market_value = (holdings_df['quantity'] * holdings_df['last_price']).sum()
                st.metric("Current Value", format_currency(total_market_value))
            else:
                st.metric("Current Value", "₹0")
        
        with col3:
            if not orders_df.empty:
                total_orders = len(orders_df)
                st.metric("Total Orders", total_orders)
            else:
                st.metric("Total Orders", "0")
        
        with col4:
            if not orders_df.empty:
                success_rate = (len(orders_df[orders_df['status'] == 'COMPLETE']) / len(orders_df)) * 100
                st.metric("Success Rate", f"{success_rate:.1f}%")
            else:
                st.metric("Success Rate", "0%")
    
    # Quick Market Overview (Compact)
    st.subheader("📊 Quick Market Overview")
    
    live_prices_data = format_live_price_data(data.get('live_prices', {}))
    
    if live_prices_data:
        # Show only top 5 gainers and losers in compact format
        gainers = [s for s in live_prices_data if s['change'] > 0][:3]
        losers = [s for s in live_prices_data if s['change'] < 0][:3]
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**📈 Top Gainers**")
            for stock in gainers:
                st.write(f"**{stock['symbol']}**: ₹{stock['last_price']:,.2f} (+{stock['change_pct']:.2f}%)")
        
        with col2:
            st.markdown("**📉 Top Losers**")
            for stock in losers:
                st.write(f"**{stock['symbol']}**: ₹{stock['last_price']:,.2f} ({stock['change_pct']:.2f}%)")
    
    else:
        st.info("Market data will appear here when market is open")
    
    # Market insights
    st.subheader("🎯 Market Insights & Recommendations")
    insights = get_market_insights(holdings_df, data.get('market_data', {}))
    
    # Display insights in columns
    if insights:
        cols = st.columns(min(len(insights), 3))
        for i, insight in enumerate(insights):
            with cols[i % 3]:
                st.info(insight)
    
    # Risk metrics
    if not holdings_df.empty:
        st.subheader("📊 Risk Analysis")
        risk_metrics = calculate_risk_metrics(holdings_df)
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Portfolio Return", f"{risk_metrics.get('portfolio_return', 0):.2f}%")
        with col2:
            st.metric("Volatility", f"{risk_metrics.get('portfolio_volatility', 0):.2f}%")
        with col3:
            st.metric("Sharpe Ratio", f"{risk_metrics.get('sharpe_ratio', 0):.2f}")
        with col4:
            st.metric("Diversification", f"{risk_metrics.get('diversification_ratio', 0):.1f}")

