from kiteconnect import KiteConnect
import os
import csv

# Your credentials
api_key = "hfjm51l7tcyyuq0b"
api_secret = "yi24vzq6ibpcerdg06y1wzm944ad9ah9"
access_token_file = "access_token.txt"

kite = KiteConnect(api_key=api_key)

def get_instrument_token(exchange, trading_symbol):
    """
    Get the instrument token for a given exchange and trading symbol.
    
    Args:
        exchange (str): Exchange name (e.g., 'NSE', 'BSE', 'NFO')
        trading_symbol (str): Trading symbol (e.g., 'RELIANCE', 'SBIN')
    
    Returns:
        int or None: Instrument token if found, None otherwise
    """
    try:
        with open('instruments.csv', 'r') as file:
            csv_reader = csv.reader(file)
            next(csv_reader)  # Skip header row
            
            for row in csv_reader:
                if len(row) >= 12:  # Ensure row has enough columns
                    # Check if exchange and trading symbol match
                    if row[11] == exchange and row[2] == trading_symbol:
                        instrument_token = int(row[0])
                        print(f"Found instrument token: {instrument_token} for {trading_symbol} on {exchange}")
                        return instrument_token
            
            print(f"No instrument found for {trading_symbol} on {exchange}")
            return None
            
    except FileNotFoundError:
        print("instruments.csv file not found")
        return None
    except Exception as e:
        print(f"Error reading instruments.csv: {e}")
        return None

def set_access_token_from_file():
    if os.path.exists(access_token_file):
        with open(access_token_file, "r") as f:
            token = f.read().strip()
            if token:
                try:
                    kite.set_access_token(token)
                    kite.profile()
                    print("Using saved access token.")
                    return True
                except Exception:
                    pass
    return False

if not set_access_token_from_file():
    print("Login URL:", kite.login_url())
    request_token = input("Enter the request_token from the URL: ")
    data = kite.generate_session(request_token, api_secret=api_secret)
    access_token = data["access_token"]
    kite.set_access_token(access_token)
    with open(access_token_file, "w") as f:
        f.write(access_token)
    print("Access token saved to access_token.txt")

def place_order(symbol, direction, quantity, exchange="NSE", order_type="MARKET", product="CNC", price=None):
    exchanges = {"NSE": kite.EXCHANGE_NSE, "NFO": kite.EXCHANGE_NFO}
    directions = {"BUY": kite.TRANSACTION_TYPE_BUY, "SELL": kite.TRANSACTION_TYPE_SELL}
    order_types = {"MARKET": kite.ORDER_TYPE_MARKET, "LIMIT": kite.ORDER_TYPE_LIMIT}
    products = {"CNC": kite.PRODUCT_CNC, "MIS": kite.PRODUCT_MIS}
    
    try:
        order_id = kite.place_order(
            variety=kite.VARIETY_REGULAR,
            exchange=exchanges[exchange],
            tradingsymbol=symbol,
            transaction_type=directions[direction],
            quantity=quantity,
            product=products[product],
            order_type=order_types[order_type],
            price=price,
            validity=kite.VALIDITY_DAY
        )
        print(f"Order placed: {order_id}")
        return order_id
    except Exception as e:
        print(f"Error: {e}")
        return None

# Usage
# place_order("RELIANCE", "BUY", 1)
# place_order("SBIN", "BUY", 10, "NSE", "LIMIT", "CNC", 800)

# Example usage of get_instrument_token function
# print("\n--- Testing get_instrument_token function ---")
# get_instrument_token("NSE", "RELIANCE")
# get_instrument_token("NSE", "SBIN")
# get_instrument_token("BSE", "RELIANCE")
# get_instrument_token("NSE", "INVALID_SYMBOL")






def get_quote(*args):
    """
    Get quote with market depth for instruments
    Args:
        Can pass in two ways:
        1. Full format: get_quote("NSE:RELIANCE", "NFO:BANKNIFTY24JAN50000CE")
        2. Separate format: get_quote("NSE", "RELIANCE") or get_quote("NFO", "BANKNIFTY24JAN50000CE")
    Returns:
        Dictionary with full quote data including market depth or None if failed
    """
    try:
        symbols = []
        
        # Check if args contain ":" - if yes, assume full format
        if any(":" in str(arg) for arg in args):
            symbols = list(args)
        else:
            # Assume separate format: exchange, symbol pairs
            if len(args) % 2 != 0:
                print("Error: Need even number of arguments for exchange, symbol pairs")
                return None
            for i in range(0, len(args), 2):
                exchange = args[i]
                stock = args[i + 1]
                symbols.append(f"{exchange}:{stock}")
            
        quotes = kite.quote(*symbols)
        for symbol, data in quotes.items():
            print(f"{symbol}: LTP={data['last_price']}, Vol={data['volume']}")
            if 'depth' in data:
                print(f"  Best Buy: {data['depth']['buy'][0]['price']} x {data['depth']['buy'][0]['quantity']}")
                print(f"  Best Sell: {data['depth']['sell'][0]['price']} x {data['depth']['sell'][0]['quantity']}")
        return quotes
    except Exception as e:
        print(f"Quote Error: {e}")
        return None

# Usage examples (uncomment to use):
# place_order("RELIANCE", "BUY", 1)
# get_quote("NSE", "RELIANCE")
# get_quote("NSE:SBIN", "NFO:BANKNIFTY24JAN50000CE")

# 1,300.00	

# get_quote("NFO", "RELIANCE25OCT1300PE")

get_quote("NFO", "TCS25OCT2800PE")

# RELIANCE25OCT1300PE
