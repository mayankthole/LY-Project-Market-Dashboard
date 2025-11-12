"""
Data fetching functions from Zerodha API
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


def get_portfolio_data(kite):
    """Fetch comprehensive portfolio data from Zerodha API"""
    try:
        holdings = kite.holdings()
        positions = kite.positions()
        orders = kite.orders()
        margins = kite.margins()
        profile = kite.profile()
        
        # Get additional data for advanced features
        historical_data = {}
        market_data = {}
        live_prices = {}
        
        # Get historical data for top holdings
        if holdings:
            top_holdings = sorted(holdings, key=lambda x: x.get('pnl', 0), reverse=True)[:5]
            symbols = [f"{h['exchange']}:{h['tradingsymbol']}" for h in top_holdings if h.get('tradingsymbol')]
            
            if symbols:
                try:
                    # Get quotes for top holdings
                    quotes = kite.quote(symbols)
                    market_data['quotes'] = quotes
                    
                    # Get historical data for analysis
                    for symbol in symbols[:3]:  # Limit to 3 symbols to avoid API limits
                        try:
                            hist_data = kite.historical_data(
                                symbol.split(':')[1], 
                                symbol.split(':')[0], 
                                from_date=(datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'),
                                to_date=datetime.now().strftime('%Y-%m-%d'),
                                interval='day'
                            )
                            historical_data[symbol] = hist_data
                        except:
                            continue
                except:
                    pass
        
        # Get live prices for comprehensive stock list - NSE and BSE equivalents
        try:
            # Comprehensive stock list provided by user
            stock_symbols = [
                "360ONE", "ABB", "ABCAPITAL", "ADANIENSOL", "ADANIENT", "ADANIGREEN", "ADANIPORTS",
                "ALKEM", "AMBER", "AMBUJACEM", "ANGELONE", "APLAPOLLO", "APOLLOHOSP", "ASHOKLEY",
                "ASIANPAINT", "ASTRAL", "AUBANK", "AUROPHARMA", "AXISBANK", "BAJAJ-AUTO", "BAJAJFINSV",
                "BAJFINANCE", "BANDHANBNK", "BANKBARODA", "BANKINDIA", "BDL", "BEL", "BHARATFORG",
                "BHARTIARTL", "BHEL", "BIOCON", "BLUESTARCO", "BOSCHLTD", "BPCL", "BRITANNIA", "MRF"
                "CAMS", "CANBK", "CGPOWER", "CHOLAFIN", "CIPLA", "COALINDIA", "COFORGE",
                "COLPAL", "CONCOR", "CROMPTON", "CUMMINSIND", "CYIENT", "DABUR", "DALBHARAT",
                "DELHIVERY", "DIVISLAB", "DIXON", "DLF", "DMART", "DRREDDY", "EICHERMOT", "ETERNAL",
                "EXIDEIND", "FEDERALBNK", "FORTIS", "GAIL", "GLENMARK", "GMRAIRPORT", "GODREJCP",
                "GODREJPROP", "GRASIM", "HAL", "HAVELLS", "HCLTECH", "HDFCAMC", "HDFCBANK", "HDFCLIFE",
                "HEROMOTOCO", "HFCL", "HINDALCO", "HINDPETRO", "HINDUNILVR", "HINDZINC", "HUDCO",
                "ICICIBANK", "ICICIGI", "ICICIPRULI", "IDEA", "IDFCFIRSTB", "IEX", "IGL", "IIFL",
                "INDHOTEL", "INDIANB", "INDIGO", "INDUSINDBK", "INDUSTOWER", "INFY", "INOXWIND",
                "IOC", "IRCTC", "IREDA", "IRFC", "ITC", "JINDALSTEL", "JIOFIN", "JSWENERGY",
                "JSWSTEEL", "JUBLFOOD", "KALYANKJIL", "KAYNES", "KEI", "KFINTECH", "KOTAKBANK",
                "KPITTECH", "LAURUSLABS", "LICHSGFIN", "LICI", "LODHA", "LT", "LTF", "LTIM", "LUPIN",
                "M&M", "MANAPPURAM", "MANKIND", "MARICO", "MARUTI", "MAXHEALTH", "MAZDOCK", "MCX",
                "MFSL", "MOTHERSON", "MPHASIS", "MUTHOOTFIN", "NATIONALUM", "NAUKRI", "NBCC", "NCC",
                "NESTLEIND", "NHPC", "NMDC", "NTPC", "NUVAMA", "NYKAA", "OBEROIRLTY", "OFSS", "OIL",
                "ONGC", "PAGEIND", "PATANJALI", "PAYTM", "PERSISTENT", "PETRONET", "PFC", "PGEL",
                "PHOENIXLTD", "PIDILITIND", "PIIND", "PNB", "PNBHOUSING", "POLICYBZR", "POLYCAB",
                "POWERGRID", "POWERINDIA", "PPLPHARMA", "PRESTIGE", "RBLBANK", "RECLTD", "RELIANCE",
                "RVNL", "SAIL", "SAMMAANCAP", "SBICARD", "SBILIFE", "SBIN", "SHREECEM", "SHRIRAMFIN",
                "SIEMENS", "SOLARINDS", "SONACOMS", "SRF", "SUNPHARMA", "SUPREMEIND", "SUZLON",
                "SYNGENE", "TATACONSUM", "TATAELXSI", "TATAMOTORS", "TATAPOWER", "TATASTEEL",
                "TATATECH", "TCS", "TECHM", "TIINDIA", "TITAGARH", "TITAN", "TORNTPHARM",
                "TORNTPOWER", "TRENT", "TVSMOTOR", "ULTRACEMCO", "UNIONBANK", "UNITDSPR",
                "UNOMINDA", "UPL", "VBL", "VEDL", "VOLTAS", "WIPRO", "YESBANK", "ZYDUSLIFE"
            ]
            
            # Create NSE and BSE symbols
            popular_stocks = []
            for symbol in stock_symbols:
                popular_stocks.append(f"NSE:{symbol}")
                popular_stocks.append(f"BSE:{symbol}")
            live_quotes = kite.quote(popular_stocks)
            live_prices = live_quotes
        except:
            pass
        
        return {
            'holdings': holdings,
            'net_positions': positions.get('net', []),
            'day_positions': positions.get('day', []),
            'orders': orders,
            'margins': margins,
            'profile': profile,
            'historical_data': historical_data,
            'market_data': market_data,
            'live_prices': live_prices
        }
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return None


def format_live_price_data(live_prices):
    """Format live price data for display"""
    if not live_prices:
        return []
    
    formatted_data = []
    for symbol, data in live_prices.items():
        if data and 'last_price' in data:
            last_price = data.get('last_price', 0)
            close_price = data.get('ohlc', {}).get('close', 0)
            
            # Calculate change from previous close price
            if close_price > 0:
                change = last_price - close_price
                change_pct = (change / close_price) * 100
            else:
                change = data.get('change', 0)
                change_pct = data.get('change_percent', 0)
            
            formatted_data.append({
                'symbol': symbol.split(':')[1],
                'exchange': symbol.split(':')[0],
                'last_price': last_price,
                'change': change,
                'change_pct': change_pct,
                'volume': data.get('volume', 0),
                'high': data.get('ohlc', {}).get('high', 0),
                'low': data.get('ohlc', {}).get('low', 0),
                'open': data.get('ohlc', {}).get('open', 0),
                'close': close_price
            })
    
    return sorted(formatted_data, key=lambda x: abs(x['change_pct']), reverse=True)

