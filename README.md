# 📈 Stock Market Dashboard - Zerodha Trading Platform

A comprehensive, modular Streamlit-based dashboard for Zerodha KiteConnect API integration, providing real-time portfolio management, arbitrage opportunities, cash-futures strategies, and historical analytics.



<img width="1505" height="802" alt="Screenshot 2025-11-12 at 9 13 01 PM" src="https://github.com/user-attachments/assets/1b095a6f-4df0-4c9b-abf7-3cb6a7208de5" />
<img width="1512" height="802" alt="Screenshot 2025-11-12 at 9 13 12 PM" src="https://github.com/user-attachments/assets/ed66b5fe-6010-42d3-ba03-faeba5fda5ca" />
<img width="1510" height="814" alt="Screenshot 2025-11-12 at 9 13 41 PM" src="https://github.com/user-attachments/assets/81d614d3-d15f-493a-a249-cfead7cd6aba" />
<img width="1509" height="796" alt="Screenshot 2025-11-12 at 9 13 56 PM" src="https://github.com/user-attachments/assets/3752a64b-51b6-4eae-b974-c89e93bd17f5" />
<img width="1509" height="802" alt="Screenshot 2025-11-12 at 9 14 53 PM" src="https://github.com/user-attachments/assets/67951c39-da4a-4e77-8fb4-938e73f758d3" />

## 🎯 Project Overview

This project is a full-featured algorithmic trading dashboard that connects to Zerodha's KiteConnect API to provide:

- **Real-time Portfolio Management**: View holdings, positions, orders, and account details
- **Arbitrage Opportunities**: NSE vs BSE price difference analysis and automated trading
- **Theta Capture Strategy**: Cash-futures spread analysis for time value decay strategies
- **Historical Analytics**: Database-driven insights and trend analysis
- **Live Market Data**: Real-time prices, gainers/losers, and sector-wise filtering
- **Advanced Analytics**: Technical indicators, risk metrics, and correlation analysis

## ✨ Key Features

### 📊 Dashboard Features
- **Portfolio Overview**: Total P&L, holdings count, active positions, pending orders
- **Risk Analysis**: Portfolio return, volatility, Sharpe ratio, diversification metrics
- **Market Insights**: Automated recommendations based on portfolio and market data
- **Live Prices**: Real-time market data with sector filtering

### ⚖️ Arbitrage Trading
- **NSE vs BSE Analysis**: Automatic detection of price differences between exchanges
- **Profitability Scoring**: Advanced scoring algorithm considering spread, volume, and liquidity
- **One-Click Trading**: Execute buy/sell orders simultaneously on both exchanges
- **Margin Calculation**: Real-time margin requirements and availability checks
- **Bulk Order Execution**: Place orders for all profitable opportunities at once

### 📅 Theta Capture Strategy
- **Cash-Futures Spread Analysis**: Identify premium opportunities
- **Annualized Return Calculation**: Time-adjusted return metrics
- **Expiry Tracking**: Days to expiry and convergence analysis
- **Pair Trading**: Automated cash and futures order placement

### 📊 Historical Analytics
- **Spread History**: Track arbitrage and cash-futures spreads over time
- **Trend Analysis**: Visual charts showing spread trends and profitability
- **Top Performers**: Identify best symbols by average spread/premium
- **Order History**: Complete execution history with success rates
- **Database Storage**: SQLite database for persistent historical data

### 🔐 Security & Authentication
- **Secure Credential Storage**: Encrypted local storage of API keys
- **Token Management**: Automatic token validation and regeneration
- **Session Management**: Persistent login across sessions

## 🏗️ Project Structure

```
LY Project/
├── main.py                 # Main Streamlit application entry point
├── config.py              # Configuration constants (lot sizes, credentials path)
├── utils.py               # Utility functions (time, currency, credentials)
├── api_client.py          # KiteConnect API wrapper functions
├── data_fetcher.py        # Portfolio and market data fetching
├── calculations.py        # Business logic (arbitrage, risk, indicators)
├── order_manager.py       # Order placement and execution
├── database.py            # SQLite database operations
├── ui_auth.py             # Authentication UI components
├── ui_sidebar.py          # Sidebar UI components
├── ui_dashboard.py        # Main dashboard overview UI
├── requirements.txt       # Python dependencies
└── README.md             # This file
```

## 📦 Installation

### Prerequisites
- Python 3.8 or higher
- Zerodha KiteConnect API credentials (API Key & Secret)
- Active Zerodha trading account

### Setup Steps

1. **Clone or download the project**
   ```bash
   cd "LY Project"
   ```

2. **Create a virtual environment (recommended)**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Get Zerodha API Credentials**
   - Visit https://kite.trade/apps/
   - Create a new app or use existing one
   - Note down your API Key and API Secret

## 🚀 Running the Application

1. **Start the Streamlit app**
   ```bash
   python3 -m streamlit run main.py --server.port 8530
   ```

2. **Access the dashboard**
   - Open your browser and navigate to: `http://localhost:8530`

3. **First-time Setup**
   - Enter your Zerodha API Key and API Secret
   - Generate login URL and authenticate
   - Enter request token to get access token
   - Start using the dashboard!

## 📚 Module Documentation

### `main.py`
Main application file that orchestrates all components. Handles:
- Authentication flow
- Data fetching and processing
- Tab navigation and UI rendering
- Auto-refresh functionality

### `config.py`
Configuration constants:
- `CREDENTIALS_FILE`: Path to stored credentials
- `LOT_SIZE_MAP`: Mapping of symbols to their lot sizes

### `utils.py`
Utility functions:
- `get_indian_time()`: Get current IST time
- `format_currency()`: Format numbers as currency
- `get_credentials()`: Retrieve stored credentials
- `persist_credentials()`: Save credentials securely
- `clear_credentials()`: Remove stored credentials

### `api_client.py`
KiteConnect API wrapper:
- `validate_access_token()`: Check if token is valid
- `generate_login_url()`: Create Zerodha login URL
- `generate_access_token()`: Exchange request token for access token
- `is_authenticated()`: Check authentication status

### `data_fetcher.py`
Data fetching functions:
- `get_portfolio_data()`: Fetch holdings, positions, orders, margins
- `format_live_price_data()`: Format live market prices

### `calculations.py`
Business logic and calculations:
- `calculate_arbitrage_opportunities()`: Find NSE-BSE arbitrage opportunities
- `calculate_cash_futures_opportunities()`: Find cash-futures spread opportunities
- `calculate_risk_metrics()`: Portfolio risk analysis
- `calculate_technical_indicators()`: SMA, RSI, MACD calculations
- `calculate_margin_required()`: Margin calculation for orders
- `get_available_margin()`: Get available margin from account

### `order_manager.py`
Order execution:
- `place_order()`: Place single order
- `place_arbitrage_orders()`: Place buy/sell pair for arbitrage
- `place_cash_futures_orders()`: Place cash and futures pair
- `execute_order_sequence()`: Execute multiple orders sequentially

### `database.py`
SQLite database operations:
- `init_database()`: Initialize database and create tables
- `store_arbitrage_spread()`: Store arbitrage spread data
- `store_cash_futures_spread()`: Store cash-futures spread data
- `store_order_history()`: Store order execution details
- `get_arbitrage_spread_history()`: Retrieve historical arbitrage data
- `get_cash_futures_spread_history()`: Retrieve historical cash-futures data
- `get_order_history()`: Retrieve order execution history
- `get_arbitrage_insights_from_db()`: Generate insights from arbitrage data
- `get_cash_futures_insights_from_db()`: Generate insights from cash-futures data
- `cleanup_old_data()`: Remove old data (default: >90 days)

### `ui_auth.py`
Authentication UI components:
- `render_auth_ui()`: Complete authentication flow UI

### `ui_sidebar.py`
Sidebar UI components:
- `render_sidebar()`: Sidebar with user info, refresh controls, market status

### `ui_dashboard.py`
Main dashboard UI:
- `render_dashboard_overview()`: Portfolio overview, metrics, market insights

## 🎨 Dashboard Tabs

1. **💼 Holdings**: Portfolio holdings with P&L, charts, and performance metrics
2. **📈 Positions**: Active trading positions and net positions
3. **📋 Orders**: Order management, status tracking, and execution history
4. **💰 Account**: Account information, profile details, and margin data
5. **📊 Analytics**: Advanced analytics including correlation matrices and sector analysis
6. **🔍 Market Analysis**: Technical analysis with candlestick charts and indicators
7. **📊 Live Prices**: Real-time market prices with sector filtering
8. **🔥 Market Data**: Detailed market data with top movers
9. **⚖️ Arbitrage**: NSE vs BSE arbitrage opportunities and trading
10. **📅 Theta Capture**: Cash-futures spread analysis and theta decay strategies
11. **📊 Historical Insights**: Historical data analytics and trend visualization

## ⚙️ Configuration

### Credentials Storage
Credentials are stored in: `~/.ly_dashboard_credentials.json`

### Database
SQLite database file: `trading_data.db` (created automatically)

### Auto-Refresh
Configure auto-refresh interval from sidebar:
- Options: 30s, 60s, 120s, 300s
- Toggle auto-refresh on/off

## 🔒 Security Notes

- **API Credentials**: Stored locally in encrypted format
- **Access Tokens**: Expire daily - regenerate when needed
- **No Cloud Storage**: All data stored locally on your machine
- **Database**: SQLite file stored in project directory

## 📊 Database Schema

### `arbitrage_spreads`
Stores historical arbitrage spread data:
- Symbol, NSE/BSE prices, price difference
- Profit per share, arbitrage score
- Volume data, profitability flags

### `cash_futures_spreads`
Stores historical cash-futures spread data:
- Symbol, cash/futures prices, premium
- Annualized premium, days to expiry
- Opportunity scores

### `order_history`
Stores order execution history:
- Symbol, order type, transaction type
- Exchange, quantity, price
- Order ID, status, expected profit

## 🛠️ Dependencies

- **streamlit**: Web application framework
- **pandas**: Data manipulation and analysis
- **plotly**: Interactive charts and visualizations
- **pytz**: Timezone handling
- **kiteconnect**: Zerodha KiteConnect API client
- **numpy**: Numerical computations

## 📝 Usage Examples

### Viewing Arbitrage Opportunities
1. Navigate to **⚖️ Arbitrage** tab
2. View top opportunities sorted by price difference
3. Click on an opportunity to see details
4. Set quantity and order type
5. Click "Execute Orders" to place buy/sell pair

### Theta Capture Strategy
1. Navigate to **📅 Theta Capture** tab
2. Set minimum premium % and days to expiry filters
3. Click "Find Theta Capture Opportunities"
4. Review opportunities with annualized returns
5. Execute cash-futures pair orders

### Historical Analysis
1. Navigate to **📊 Historical Insights** tab
2. Select analysis period (7, 14, 30, 60, or 90 days)
3. View spread trends, top performers, and insights
4. Analyze order execution history

## ⚠️ Important Notes

- **Market Hours**: Orders can only be placed during market hours (9:15 AM - 3:30 PM IST)
- **Margin Requirements**: Ensure sufficient margin before placing orders
- **Risk Warning**: Trading involves risk. Use at your own discretion
- **Token Expiry**: Access tokens expire daily. Regenerate when needed
- **Data Collection**: Historical data is collected automatically as you use the dashboard

## 🐛 Troubleshooting

### Token Expired Error
- Navigate to sidebar
- Click "Regenerate Token"
- Follow authentication flow again

### No Data Available
- Ensure market is open (9:15 AM - 3:30 PM IST)
- Check internet connection
- Verify API credentials are correct

### Database Errors
- Database is created automatically on first run
- If issues persist, delete `trading_data.db` and restart

## 📈 Future Enhancements

- [ ] Real-time notifications for arbitrage opportunities
- [ ] Backtesting framework for strategies
- [ ] Multi-account support
- [ ] Advanced order types (bracket orders, cover orders)
- [ ] Portfolio optimization algorithms
- [ ] Export reports (PDF, Excel)
- [ ] Mobile-responsive design

## 📄 License

This project is for educational and personal use. Ensure compliance with Zerodha's terms of service.

## 👥 Contributors

- Developed as part of Algorithmic Trading Engine project

## 📞 Support

For issues or questions:
- Check Zerodha KiteConnect documentation: https://kite.trade/docs/
- Review Streamlit documentation: https://docs.streamlit.io/

---

**⚠️ Disclaimer**: This software is provided "as is" without warranty. Trading involves financial risk. Use at your own discretion and ensure you understand the risks involved.

