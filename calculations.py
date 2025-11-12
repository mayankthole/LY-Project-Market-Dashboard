"""
Calculation functions for risk metrics, arbitrage, technical indicators, etc.
"""
import pandas as pd
import numpy as np
from datetime import datetime
from config import LOT_SIZE_MAP


def calculate_technical_indicators(df):
    """Calculate basic technical indicators"""
    if df.empty:
        return df
    
    # Simple Moving Averages
    df['sma_5'] = df['close'].rolling(window=5).mean()
    df['sma_20'] = df['close'].rolling(window=20).mean()
    
    # RSI (Relative Strength Index)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # MACD
    exp1 = df['close'].ewm(span=12).mean()
    exp2 = df['close'].ewm(span=26).mean()
    df['macd'] = exp1 - exp2
    df['macd_signal'] = df['macd'].ewm(span=9).mean()
    df['macd_histogram'] = df['macd'] - df['macd_signal']
    
    return df


def calculate_risk_metrics(holdings_df):
    """Calculate portfolio risk metrics"""
    if holdings_df.empty:
        return {}
    
    # Calculate returns
    holdings_df['returns'] = ((holdings_df['last_price'] - holdings_df['average_price']) / holdings_df['average_price']) * 100
    
    # Portfolio metrics
    total_investment = (holdings_df['quantity'] * holdings_df['average_price']).sum()
    total_market_value = (holdings_df['quantity'] * holdings_df['last_price']).sum()
    
    # Calculate weighted returns
    weights = (holdings_df['quantity'] * holdings_df['last_price']) / total_market_value
    portfolio_return = (weights * holdings_df['returns']).sum()
    
    # Risk metrics
    portfolio_volatility = holdings_df['returns'].std()
    sharpe_ratio = portfolio_return / portfolio_volatility if portfolio_volatility > 0 else 0
    
    # Diversification
    num_holdings = len(holdings_df)
    max_weight = weights.max()
    diversification_ratio = 1 / (weights ** 2).sum() if len(weights) > 0 else 0
    
    return {
        'portfolio_return': portfolio_return,
        'portfolio_volatility': portfolio_volatility,
        'sharpe_ratio': sharpe_ratio,
        'diversification_ratio': diversification_ratio,
        'max_weight': max_weight,
        'num_holdings': num_holdings,
        'total_investment': total_investment,
        'total_market_value': total_market_value
    }


def calculate_arbitrage_opportunities(live_prices_data, min_profit_threshold=0.05):
    """Calculate arbitrage opportunities between NSE and BSE with minimum profit threshold"""
    arbitrage_data = []
    
    if not live_prices_data:
        return arbitrage_data
    
    # Group stocks by symbol (without exchange)
    stock_groups = {}
    for stock in live_prices_data:
        symbol = stock['symbol']
        exchange = stock['exchange']
        
        if symbol not in stock_groups:
            stock_groups[symbol] = {}
        stock_groups[symbol][exchange] = stock
    
    # Find arbitrage opportunities
    for symbol, exchanges in stock_groups.items():
        if 'NSE' in exchanges and 'BSE' in exchanges:
            nse_data = exchanges['NSE']
            bse_data = exchanges['BSE']
            
            nse_price = nse_data['last_price']
            bse_price = bse_data['last_price']
            
            if nse_price > 0 and bse_price > 0:
                # Calculate price difference
                price_diff = abs(nse_price - bse_price)
                price_diff_pct = (price_diff / min(nse_price, bse_price)) * 100
                
                # Apply minimum profit threshold (brokerage + taxes)
                if price_diff_pct < min_profit_threshold:
                    continue  # Skip this opportunity as it's not profitable after costs
                
                # Determine which exchange has higher price
                if nse_price > bse_price:
                    higher_exchange = 'NSE'
                    lower_exchange = 'BSE'
                    higher_price = nse_price
                    lower_price = bse_price
                else:
                    higher_exchange = 'BSE'
                    lower_exchange = 'NSE'
                    higher_price = bse_price
                    lower_price = nse_price
                
                # Calculate profit per share (this is the net profit)
                profit_per_share = price_diff
                
                # Calculate volume-weighted arbitrage score
                nse_volume = nse_data.get('volume', 0)
                bse_volume = bse_data.get('volume', 0)
                avg_volume = (nse_volume + bse_volume) / 2
                
                # Arbitrage score (higher is better opportunity)
                arbitrage_score = price_diff_pct * (avg_volume / 1000000)  # Normalize volume
                
                # Profitable if gross price difference is greater than 0.05% (regardless of min_profit_threshold parameter)
                is_profitable = price_diff_pct > 0.05
                
                arbitrage_data.append({
                    'symbol': symbol,
                    'nse_price': nse_price,
                    'bse_price': bse_price,
                    'price_difference': price_diff,
                    'price_difference_pct': price_diff_pct,
                    'profit_per_share': profit_per_share,
                    'higher_exchange': higher_exchange,
                    'lower_exchange': lower_exchange,
                    'higher_price': higher_price,
                    'lower_price': lower_price,
                    'nse_volume': nse_volume,
                    'bse_volume': bse_volume,
                    'avg_volume': avg_volume,
                    'arbitrage_score': arbitrage_score,
                    'nse_change_pct': nse_data.get('change_pct', 0),
                    'bse_change_pct': bse_data.get('change_pct', 0),
                    'is_profitable': is_profitable
                })
    
    # Sort by arbitrage score (best opportunities first)
    arbitrage_data.sort(key=lambda x: x['arbitrage_score'], reverse=True)
    
    return arbitrage_data


def format_futures_order_symbol(stock_symbol, expiry_str):
    """
    Format futures trading symbol for order placement.
    Expected format: SYMBOL + YYMMM (e.g., RELIANCE25NOV)
    """
    if not stock_symbol or not expiry_str:
        return stock_symbol.upper() if stock_symbol else ""
    
    stock_clean = ''.join(ch for ch in stock_symbol.upper() if ch.isalnum())
    
    expiry_clean = expiry_str.strip()
    expiry_date = None
    
    # Try parsing common expiry formats
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%fZ"):
        try:
            expiry_date = datetime.strptime(expiry_clean, fmt)
            break
        except ValueError:
            continue
    
    if not expiry_date:
        # Fall back to returning cleaned symbol if parsing fails
        return stock_clean
    
    formatted_expiry = expiry_date.strftime("%y%b").upper()
    return f"{stock_clean}{formatted_expiry}"


def get_futures_contracts(kite, stock_symbols):
    """
    Get current month futures contracts for given stock symbols
    Returns dict with stock_symbol as key and futures data as value
    """
    futures_data = {}
    
    try:
        # Get all instruments from NFO exchange
        instruments = kite.instruments("NFO")
        
        if instruments is None or len(instruments) == 0:
            return futures_data
        
        # Convert to DataFrame if it's a list
        if isinstance(instruments, list):
            instruments = pd.DataFrame(instruments)
        
        # Get current date
        current_date = datetime.now()
        
        # Find futures contracts for each stock
        for stock in stock_symbols:
            try:
                stock_key = stock.upper()
                # Filter futures for this stock - check both 'name' and 'tradingsymbol' fields
                stock_futures = instruments[
                    ((instruments['name'] == stock) | (instruments['tradingsymbol'].str.startswith(stock))) &
                    (instruments['instrument_type'] == 'FUT')
                ]
                
                if not stock_futures.empty:
                    # Sort by expiry and get the nearest (current month)
                    stock_futures = stock_futures.sort_values('expiry')
                    
                    for _, fut_row in stock_futures.iterrows():
                        try:
                            expiry_str = str(fut_row['expiry'])
                            # Handle different date formats
                            if 'T' in expiry_str:
                                expiry_date = datetime.strptime(expiry_str.split('T')[0], '%Y-%m-%d')
                            else:
                                expiry_date = datetime.strptime(expiry_str, '%Y-%m-%d')
                            
                            days_to_expiry = (expiry_date - current_date).days
                            
                            if days_to_expiry > 0:  # Only future expiries
                                lot_size_value = LOT_SIZE_MAP.get(stock_key)
                                if lot_size_value is None:
                                    try:
                                        lot_size_value = int(fut_row.get('lot_size', 1))
                                    except Exception:
                                        lot_size_value = 1
                                if lot_size_value < 1:
                                    lot_size_value = 1
                                
                                futures_data[stock] = {
                                    'tradingsymbol': fut_row['tradingsymbol'],
                                    'order_tradingsymbol': format_futures_order_symbol(stock, expiry_str),
                                    'exchange': 'NFO',
                                    'expiry': expiry_str.split('T')[0] if 'T' in expiry_str else expiry_str,
                                    'days_to_expiry': days_to_expiry,
                                    'lot_size': lot_size_value
                                }
                                break  # Take the first valid future
                        except Exception as e:
                            continue
            except:
                continue
    except Exception as e:
        # Silently fail - futures might not be available for all stocks
        pass
    
    return futures_data


def calculate_cash_futures_opportunities(kite, stock_symbols, futures_data):
    """
    Calculate cash-futures theta capture opportunities
    Strategy: Buy cash, Sell futures (when futures premium is high)
    At expiry, futures and cash prices converge - capture the time value (theta)
    This is a time value decay strategy, not arbitrage
    """
    opportunities = []
    
    try:
        # Prepare symbols for quote
        quote_symbols = []
        
        for stock in stock_symbols:
            if stock in futures_data:
                # Add cash market symbol
                cash_symbol = f"NSE:{stock}"
                quote_symbols.append(cash_symbol)
                
                # Add futures symbol
                fut_data = futures_data[stock]
                fut_symbol = f"NFO:{fut_data['tradingsymbol']}"
                quote_symbols.append(fut_symbol)
        
        if not quote_symbols:
            return opportunities
        
        # Get quotes
        quotes = kite.quote(quote_symbols)
        
        # Process opportunities
        for stock in stock_symbols:
            if stock not in futures_data:
                continue
            
            stock_key = stock.upper()
            cash_symbol = f"NSE:{stock}"
            fut_data = futures_data[stock]
            fut_symbol_api = fut_data['tradingsymbol']
            fut_symbol = f"NFO:{fut_symbol_api}"
            
            if cash_symbol in quotes and fut_symbol in quotes:
                cash_quote = quotes[cash_symbol]
                fut_quote = quotes[fut_symbol]
                
                cash_price = cash_quote.get('last_price', 0)
                fut_price = fut_quote.get('last_price', 0)
                lot_size_value = LOT_SIZE_MAP.get(stock_key, fut_data.get('lot_size', 1))
                if lot_size_value is None or lot_size_value < 1:
                    lot_size_value = 1
                
                if cash_price > 0 and fut_price > 0:
                    # Calculate premium (futures - cash)
                    premium = fut_price - cash_price
                    premium_pct = (premium / cash_price) * 100 if cash_price > 0 else 0
                    
                    # Calculate annualized premium (time value)
                    days_to_expiry = fut_data['days_to_expiry']
                    if days_to_expiry > 0:
                        # Annualized return = (premium_pct / days) * 365
                        annualized_premium = (premium_pct / days_to_expiry) * 365
                    else:
                        annualized_premium = 0
                    
                    # Calculate profit per share (this is the premium we capture)
                    profit_per_share = premium
                    
                    # Calculate lot size
                    lot_size = lot_size_value
                    
                    # Opportunity score (higher premium and more days = better)
                    # Weight by premium percentage and days to expiry
                    opportunity_score = premium_pct * (days_to_expiry / 30) if days_to_expiry > 0 else 0
                    
                    opportunities.append({
                        'symbol': stock,
                        'cash_price': cash_price,
                        'futures_price': fut_price,
                        'premium': premium,
                        'premium_pct': premium_pct,
                        'annualized_premium': annualized_premium,
                        'days_to_expiry': days_to_expiry,
                        'expiry_date': fut_data['expiry'],
                        'futures_symbol': fut_data.get('order_tradingsymbol', fut_symbol_api),
                        'futures_symbol_api': fut_symbol_api,
                        'lot_size': lot_size,
                        'profit_per_share': profit_per_share,
                        'opportunity_score': opportunity_score,
                        'cash_volume': cash_quote.get('volume', 0),
                        'futures_volume': fut_quote.get('volume', 0),
                        'cash_change_pct': cash_quote.get('ohlc', {}).get('close', 0) and ((cash_price - cash_quote.get('ohlc', {}).get('close', cash_price)) / cash_quote.get('ohlc', {}).get('close', cash_price)) * 100 or 0
                    })
        
        # Sort by opportunity score
        opportunities.sort(key=lambda x: x['opportunity_score'], reverse=True)
        
    except Exception as e:
        import streamlit as st
        st.error(f"Error calculating cash-futures opportunities: {e}")
    
    return opportunities


def calculate_margin_required(price, quantity, product="MIS"):
    """
    Calculate approximate margin required for an order
    For MIS: Typically 20-40% of order value
    For CNC: 100% of order value
    For NRML: 100% of order value
    """
    order_value = price * quantity
    
    if product == "CNC":
        # CNC requires full payment
        return order_value
    elif product == "MIS":
        # MIS typically requires 20-40% margin, using 30% as average
        return order_value * 0.30
    elif product == "NRML":
        # NRML typically requires 20-40% margin, using 30% as average
        return order_value
    else:
        # Default to 30% for unknown products
        return order_value * 0.30


def get_available_margin(kite, data=None):
    """
    Get available margin from Zerodha API
    Returns available cash margin for equity trading
    """
    available_margin = 0
    
    try:
        # First try fetching directly from kite (most reliable)
        margins = kite.margins()
        
        if margins:
            # Zerodha API structure: margins['equity']['available']['cash']
            if 'equity' in margins:
                equity_margins = margins['equity']
                if 'available' in equity_margins:
                    available = equity_margins['available']
                    if isinstance(available, dict):
                        # Try different possible keys
                        available_margin = available.get('cash') or available.get('available') or available.get('net') or 0
                    elif isinstance(available, (int, float)):
                        available_margin = available or 0
                # Also try 'net' directly in equity
                if available_margin == 0 and 'net' in equity_margins:
                    net = equity_margins['net']
                    if isinstance(net, (int, float)):
                        available_margin = net or 0
            
            # Fallback: try direct access
            if available_margin == 0:
                if 'available' in margins:
                    available = margins['available']
                    if isinstance(available, dict):
                        available_margin = available.get('cash') or available.get('equity', {}).get('cash') or 0
                    elif isinstance(available, (int, float)):
                        available_margin = available or 0
        
        # If still 0, try from cached data
        if available_margin == 0 and data and 'margins' in data:
            margins_data = data['margins']
            if isinstance(margins_data, dict):
                if 'equity' in margins_data:
                    equity_margins = margins_data['equity']
                    if 'available' in equity_margins:
                        available = equity_margins['available']
                        if isinstance(available, dict):
                            available_margin = available.get('cash') or available.get('available') or available.get('net') or 0
                        elif isinstance(available, (int, float)):
                            available_margin = available or 0
    except Exception as e:
        # Silently fail - return 0
        pass
    
    return float(available_margin) if available_margin else 0.0


def get_arbitrage_insights(arbitrage_data):
    """Generate insights about arbitrage opportunities"""
    from utils import get_indian_time
    
    insights = []
    
    if not arbitrage_data:
        insights.append("📊 **No Arbitrage Data**: No NSE-BSE pairs found")
        return insights
    
    # Count opportunities
    total_opportunities = len(arbitrage_data)
    profitable_opportunities = len([a for a in arbitrage_data if a['is_profitable']])
    significant_opportunities = len([a for a in arbitrage_data if a['price_difference_pct'] > 0.5])
    high_volume_opportunities = len([a for a in arbitrage_data if a['avg_volume'] > 1000000])
    
    insights.append(f"🔍 **All Arbitrage Opportunities**: {total_opportunities} NSE-BSE pairs found")
    
    if profitable_opportunities > 0:
        insights.append(f"💰 **Profitable Opportunities**: {profitable_opportunities} pairs above 0.05% gross price difference")
    else:
        insights.append("❌ **No Profitable Opportunities**: No pairs above 0.05% threshold found")
    
    if significant_opportunities > 0:
        insights.append(f"⚡ **High Margin Opportunities**: {significant_opportunities} pairs with >0.5% price difference")
    
    if high_volume_opportunities > 0:
        insights.append(f"📈 **High Volume Opportunities**: {high_volume_opportunities} pairs with good liquidity")
    
    # Best opportunity
    if arbitrage_data:
        best = arbitrage_data[0]
        insights.append(f"🏆 **Best Opportunity**: {best['symbol']} - {best['price_difference_pct']:.2f}% difference (₹{best['profit_per_share']:.2f} per share)")
    
    # Market timing
    current_time = get_indian_time()
    if current_time.hour >= 9 and current_time.hour < 17:
        insights.append("⏰ **Market Open**: Arbitrage opportunities are live and actionable")
    else:
        insights.append("⏰ **Market Closed**: Opportunities are for next trading session")
    
    # Threshold information
    insights.append("💡 **Threshold**: Opportunities above 0.05% gross price difference are marked as profitable")
    
    return insights


def get_market_insights(holdings_df, market_data):
    """Generate market insights and recommendations"""
    from utils import format_currency, get_indian_time
    
    insights = []
    
    if holdings_df.empty:
        insights.append("💡 **Start Building Your Portfolio**: Consider adding some stocks to begin tracking your investments.")
        return insights
    
    # P&L Analysis
    total_pnl = holdings_df['pnl'].sum()
    if total_pnl > 0:
        insights.append(f"🎉 **Portfolio is in Profit**: Your total P&L is {format_currency(total_pnl)}. Great job!")
    elif total_pnl < 0:
        insights.append(f"📉 **Portfolio is in Loss**: Your total P&L is {format_currency(total_pnl)}. Consider reviewing your positions.")
    
    # Top Performer
    best_stock = holdings_df.loc[holdings_df['pnl'].idxmax()]
    insights.append(f"🏆 **Best Performer**: {best_stock['tradingsymbol']} with {format_currency(best_stock['pnl'])} profit")
    
    # Diversification Check
    if len(holdings_df) < 3:
        insights.append("⚠️ **Low Diversification**: Consider adding more stocks to reduce risk")
    elif len(holdings_df) > 10:
        insights.append("✅ **Well Diversified**: Your portfolio has good diversification")
    
    # Market Status
    current_time = get_indian_time()
    if current_time.hour >= 9 and current_time.hour < 15:
        insights.append("🟢 **Market is Open**: Good time to monitor and trade")
    else:
        insights.append("🔴 **Market is Closed**: Use this time to plan your next moves")
    
    return insights

