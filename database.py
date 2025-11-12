"""
Database module for storing and retrieving historical spread data
"""
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import logging
import os

logger = logging.getLogger(__name__)

# Database file path
DB_FILE = os.path.join(os.path.expanduser("~"), ".ly_dashboard.db")


def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    """Initialize database tables"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Table for arbitrage spread data (NSE-BSE)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS arbitrage_spreads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            timestamp DATETIME NOT NULL,
            nse_price REAL NOT NULL,
            bse_price REAL NOT NULL,
            price_difference REAL NOT NULL,
            price_difference_pct REAL NOT NULL,
            nse_volume INTEGER,
            bse_volume INTEGER,
            avg_volume INTEGER,
            is_profitable INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Table for cash-futures spread data (theta capture)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cash_futures_spreads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            timestamp DATETIME NOT NULL,
            cash_price REAL NOT NULL,
            futures_price REAL NOT NULL,
            premium REAL NOT NULL,
            premium_pct REAL NOT NULL,
            annualized_premium REAL,
            days_to_expiry INTEGER,
            expiry_date TEXT,
            opportunity_score REAL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Table for order execution history
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS order_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            order_type TEXT NOT NULL,
            transaction_type TEXT NOT NULL,
            exchange TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            price REAL,
            order_id TEXT,
            status TEXT,
            profit_expected REAL,
            profit_actual REAL,
            timestamp DATETIME NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create indexes for faster queries
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_arbitrage_symbol_timestamp ON arbitrage_spreads(symbol, timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cash_futures_symbol_timestamp ON cash_futures_spreads(symbol, timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_order_symbol_timestamp ON order_history(symbol, timestamp)")
    
    conn.commit()
    conn.close()
    logger.info("Database initialized successfully")


def store_arbitrage_spread(arbitrage_data):
    """Store arbitrage spread data"""
    if not arbitrage_data:
        return
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    timestamp = datetime.now()
    
    try:
        for opp in arbitrage_data:
            cursor.execute("""
                INSERT INTO arbitrage_spreads 
                (symbol, timestamp, nse_price, bse_price, price_difference, price_difference_pct,
                 nse_volume, bse_volume, avg_volume, is_profitable)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                opp['symbol'],
                timestamp,
                opp['nse_price'],
                opp['bse_price'],
                opp['price_difference'],
                opp['price_difference_pct'],
                opp.get('nse_volume', 0),
                opp.get('bse_volume', 0),
                opp.get('avg_volume', 0),
                1 if opp.get('is_profitable', False) else 0
            ))
        
        conn.commit()
        logger.info(f"Stored {len(arbitrage_data)} arbitrage spread records")
    except Exception as e:
        logger.error(f"Error storing arbitrage spread data: {e}")
        conn.rollback()
    finally:
        conn.close()


def store_cash_futures_spread(opportunities):
    """Store cash-futures spread data"""
    if not opportunities:
        return
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    timestamp = datetime.now()
    
    try:
        for opp in opportunities:
            cursor.execute("""
                INSERT INTO cash_futures_spreads 
                (symbol, timestamp, cash_price, futures_price, premium, premium_pct,
                 annualized_premium, days_to_expiry, expiry_date, opportunity_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                opp['symbol'],
                timestamp,
                opp['cash_price'],
                opp['futures_price'],
                opp['premium'],
                opp['premium_pct'],
                opp.get('annualized_premium', 0),
                opp.get('days_to_expiry', 0),
                opp.get('expiry_date', ''),
                opp.get('opportunity_score', 0)
            ))
        
        conn.commit()
        logger.info(f"Stored {len(opportunities)} cash-futures spread records")
    except Exception as e:
        logger.error(f"Error storing cash-futures spread data: {e}")
        conn.rollback()
    finally:
        conn.close()


def store_order_history(order_data):
    """Store order execution history"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    timestamp = datetime.now()
    
    try:
        cursor.execute("""
            INSERT INTO order_history 
            (symbol, order_type, transaction_type, exchange, quantity, price,
             order_id, status, profit_expected, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            order_data.get('symbol', ''),
            order_data.get('order_type', ''),
            order_data.get('transaction_type', ''),
            order_data.get('exchange', ''),
            order_data.get('quantity', 0),
            order_data.get('price', 0),
            order_data.get('order_id', ''),
            order_data.get('status', ''),
            order_data.get('profit_expected', 0),
            timestamp
        ))
        
        conn.commit()
        logger.info("Stored order history record")
    except Exception as e:
        logger.error(f"Error storing order history: {e}")
        conn.rollback()
    finally:
        conn.close()


def get_arbitrage_spread_history(symbol=None, days=7):
    """Get historical arbitrage spread data"""
    conn = get_db_connection()
    
    try:
        query = """
            SELECT * FROM arbitrage_spreads
            WHERE timestamp >= datetime('now', '-' || ? || ' days')
        """
        params = [days]
        
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        
        query += " ORDER BY timestamp DESC"
        
        df = pd.read_sql_query(query, conn, params=params)
        return df
    except Exception as e:
        logger.error(f"Error retrieving arbitrage spread history: {e}")
        return pd.DataFrame()
    finally:
        conn.close()


def get_cash_futures_spread_history(symbol=None, days=7):
    """Get historical cash-futures spread data"""
    conn = get_db_connection()
    
    try:
        query = """
            SELECT * FROM cash_futures_spreads
            WHERE timestamp >= datetime('now', '-' || ? || ' days')
        """
        params = [days]
        
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        
        query += " ORDER BY timestamp DESC"
        
        df = pd.read_sql_query(query, conn, params=params)
        return df
    except Exception as e:
        logger.error(f"Error retrieving cash-futures spread history: {e}")
        return pd.DataFrame()
    finally:
        conn.close()


def get_order_history(symbol=None, days=30):
    """Get order execution history"""
    conn = get_db_connection()
    
    try:
        query = """
            SELECT * FROM order_history
            WHERE timestamp >= datetime('now', '-' || ? || ' days')
        """
        params = [days]
        
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        
        query += " ORDER BY timestamp DESC"
        
        df = pd.read_sql_query(query, conn, params=params)
        return df
    except Exception as e:
        logger.error(f"Error retrieving order history: {e}")
        return pd.DataFrame()
    finally:
        conn.close()


def get_arbitrage_insights_from_db(days=7):
    """Generate insights from historical arbitrage data"""
    df = get_arbitrage_spread_history(days=days)
    
    if df.empty:
        return {
            'total_records': 0,
            'unique_symbols': 0,
            'avg_spread_pct': 0,
            'max_spread_pct': 0,
            'profitable_opportunities': 0,
            'best_symbol': None,
            'trend': 'no_data'
        }
    
    insights = {
        'total_records': len(df),
        'unique_symbols': df['symbol'].nunique(),
        'avg_spread_pct': df['price_difference_pct'].mean(),
        'max_spread_pct': df['price_difference_pct'].max(),
        'min_spread_pct': df['price_difference_pct'].min(),
        'profitable_opportunities': df['is_profitable'].sum(),
        'profitable_pct': (df['is_profitable'].sum() / len(df)) * 100 if len(df) > 0 else 0,
        'trend': 'flat',
        'trend_change_pct': 0.0
    }
    
    # Best performing symbol
    symbol_stats = df.groupby('symbol').agg({
        'price_difference_pct': ['mean', 'max', 'count'],
        'is_profitable': 'sum'
    }).reset_index()
    symbol_stats.columns = ['symbol', 'avg_spread', 'max_spread', 'count', 'profitable_count']
    symbol_stats['profitability_rate'] = (symbol_stats['profitable_count'] / symbol_stats['count']) * 100
    
    if not symbol_stats.empty:
        best_symbol = symbol_stats.loc[symbol_stats['avg_spread'].idxmax()]
        insights['best_symbol'] = best_symbol['symbol']
        insights['best_symbol_avg_spread'] = best_symbol['avg_spread']
    
    # Trend analysis
    df['date'] = pd.to_datetime(df['timestamp']).dt.date
    daily_avg = df.groupby('date')['price_difference_pct'].mean()
    if len(daily_avg) > 1:
        trend = 'increasing' if daily_avg.iloc[-1] > daily_avg.iloc[0] else 'decreasing'
        insights['trend'] = trend
        insights['trend_change_pct'] = ((daily_avg.iloc[-1] - daily_avg.iloc[0]) / daily_avg.iloc[0]) * 100 if daily_avg.iloc[0] != 0 else 0
    elif len(daily_avg) == 1:
        insights['trend'] = 'flat'
        insights['trend_change_pct'] = 0.0
    
    return insights


def get_cash_futures_insights_from_db(days=7):
    """Generate insights from historical cash-futures data"""
    df = get_cash_futures_spread_history(days=days)
    
    if df.empty:
        return {
            'total_records': 0,
            'unique_symbols': 0,
            'avg_premium_pct': 0,
            'max_premium_pct': 0,
            'best_symbol': None
        }
    
    insights = {
        'total_records': len(df),
        'unique_symbols': df['symbol'].nunique(),
        'avg_premium_pct': df['premium_pct'].mean(),
        'max_premium_pct': df['premium_pct'].max(),
        'min_premium_pct': df['premium_pct'].min(),
        'avg_annualized_premium': df['annualized_premium'].mean(),
        'max_annualized_premium': df['annualized_premium'].max()
    }
    
    # Best performing symbol
    symbol_stats = df.groupby('symbol').agg({
        'premium_pct': ['mean', 'max'],
        'annualized_premium': 'mean'
    }).reset_index()
    symbol_stats.columns = ['symbol', 'avg_premium', 'max_premium', 'avg_annualized']
    
    if not symbol_stats.empty:
        best_symbol = symbol_stats.loc[symbol_stats['avg_premium'].idxmax()]
        insights['best_symbol'] = best_symbol['symbol']
        insights['best_symbol_avg_premium'] = best_symbol['avg_premium']
        insights['best_symbol_annualized'] = best_symbol['avg_annualized']
    
    return insights


def get_top_arbitrage_symbols(days=7, limit=10):
    """Get top symbols by average spread"""
    df = get_arbitrage_spread_history(days=days)
    
    if df.empty:
        return pd.DataFrame()
    
    symbol_stats = df.groupby('symbol').agg({
        'price_difference_pct': ['mean', 'max', 'std', 'count'],
        'is_profitable': 'sum'
    }).reset_index()
    symbol_stats.columns = ['symbol', 'avg_spread', 'max_spread', 'std_spread', 'count', 'profitable_count']
    symbol_stats['profitability_rate'] = (symbol_stats['profitable_count'] / symbol_stats['count']) * 100
    symbol_stats = symbol_stats.sort_values('avg_spread', ascending=False).head(limit)
    
    return symbol_stats


def get_top_cash_futures_symbols(days=7, limit=10):
    """Get top symbols by average premium"""
    df = get_cash_futures_spread_history(days=days)
    
    if df.empty:
        return pd.DataFrame()
    
    symbol_stats = df.groupby('symbol').agg({
        'premium_pct': ['mean', 'max', 'std'],
        'annualized_premium': 'mean'
    }).reset_index()
    symbol_stats.columns = ['symbol', 'avg_premium', 'max_premium', 'std_premium', 'avg_annualized']
    symbol_stats = symbol_stats.sort_values('avg_premium', ascending=False).head(limit)
    
    return symbol_stats


def cleanup_old_data(days_to_keep=90):
    """Clean up old data beyond specified days"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        # Delete old arbitrage data
        cursor.execute("""
            DELETE FROM arbitrage_spreads 
            WHERE timestamp < ?
        """, (cutoff_date,))
        arbitrage_deleted = cursor.rowcount
        
        # Delete old cash-futures data
        cursor.execute("""
            DELETE FROM cash_futures_spreads 
            WHERE timestamp < ?
        """, (cutoff_date,))
        cash_futures_deleted = cursor.rowcount
        
        # Delete old order history
        cursor.execute("""
            DELETE FROM order_history 
            WHERE timestamp < ?
        """, (cutoff_date,))
        orders_deleted = cursor.rowcount
        
        conn.commit()
        logger.info(f"Cleaned up old data: {arbitrage_deleted} arbitrage, {cash_futures_deleted} cash-futures, {orders_deleted} orders")
        return {
            'arbitrage_deleted': arbitrage_deleted,
            'cash_futures_deleted': cash_futures_deleted,
            'orders_deleted': orders_deleted
        }
    except Exception as e:
        logger.error(f"Error cleaning up old data: {e}")
        conn.rollback()
        return None
    finally:
        conn.close()

