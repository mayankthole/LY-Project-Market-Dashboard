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

def place_order(symbol, direction, quantity, product=None):
    # Automatically detect exchange based on symbol
    if any(char.isdigit() for char in symbol):
        # Check if it's CDS (Currency Derivatives) first
        if any(currency in symbol.upper() for currency in ['USDINR', 'EURINR', 'GBPINR', 'JPYINR', 'INR']):
            exchange = "CDS"  # Currency derivatives
            print(f"Auto-detected exchange: CDS for symbol {symbol}")
        else:
            exchange = "NFO"  # Other derivatives (options/futures)
            print(f"Auto-detected exchange: NFO for symbol {symbol}")
    else:
        exchange = "NSE"  # No numbers = equity shares
        print(f"Auto-detected exchange: NSE for symbol {symbol}")
    
    exchanges = {"NSE": kite.EXCHANGE_NSE, "NFO": kite.EXCHANGE_NFO, "CDS": kite.EXCHANGE_CDS}
    directions = {"BUY": kite.TRANSACTION_TYPE_BUY, "SELL": kite.TRANSACTION_TYPE_SELL}
    products = {"CNC": kite.PRODUCT_CNC, "MIS": kite.PRODUCT_MIS, "NRML": kite.PRODUCT_NRML}
    
    # Set default product based on exchange if not specified
    if product is None:
        if exchange == "NSE":
            product = "CNC"  # Cash and Carry for equity shares
        elif exchange in ["NFO", "CDS"]:
            product = "NRML"  # Normal margin for derivatives
        print(f"Auto-setting product to {product} for {exchange} exchange")
    
    # Always get the best price from quotes for LIMIT orders
    try:
        # Get quote for the symbol
        quote_symbol = f"{exchange}:{symbol}"
        quotes = kite.quote(quote_symbol)
        
        if direction == "BUY":
            # For BUY order, use best bid price (what buyers are willing to pay)
            best_price = quotes[quote_symbol]['depth']['buy'][0]['price']
            print(f"Auto-setting BUY limit price to best bid: ₹{best_price}")
        else:  # SELL
            # For SELL order, use best ask price (what sellers are asking)
            best_price = quotes[quote_symbol]['depth']['sell'][0]['price']
            print(f"Auto-setting SELL limit price to best ask: ₹{best_price}")
        
    except Exception as e:
        print(f"Error getting quote for price: {e}")
        return None
    
    try:
        order_id = kite.place_order(
            variety=kite.VARIETY_REGULAR,
            exchange=exchanges[exchange],
            tradingsymbol=symbol,
            transaction_type=directions[direction],
            quantity=quantity,
            product=products[product],
            order_type=kite.ORDER_TYPE_LIMIT,  # Always LIMIT
            price=best_price,  # Use the fetched price
            validity=kite.VALIDITY_DAY
        )
        print(f"Order placed: {order_id}")
        return order_id
    except Exception as e:
        print(f"Error: {e}")
        return None


def get_quote(*args, order_type="BUY"):
    """
    Get best quote for trading
    Args:
        args: Instrument symbols (exchange, symbol pairs OR full format)
        order_type: "BUY" (best ask), "SELL" (best bid) - defaults to "BUY"
    Returns:
        Best prices for trading
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
        result = {}
        
        for symbol, data in quotes.items():
            if order_type.upper() == "BUY":
                # For BUY order, get best bid (buy price) - what buyers are willing to pay
                best_price = data['depth']['buy'][0]['price']
                best_qty = data['depth']['buy'][0]['quantity']
                print(f"{symbol} - Best BID for BUY: ₹{best_price} (Qty: {best_qty})")
            else:  # SELL
                # For SELL order, get best ask (sell price) - what sellers are asking
                best_price = data['depth']['sell'][0]['price']
                best_qty = data['depth']['sell'][0]['quantity']
                print(f"{symbol} - Best ASK for SELL: ₹{best_price} (Qty: {best_qty})")
            
            result[symbol] = {"price": best_price, "quantity": best_qty}
        return result
        
    except Exception as e:
        print(f"Quote Error: {e}")
        return None



place_order("TCS25OCT2800PE", "SELL", 100)            # Auto → NFO + NRML

# More examples showing automatic exchange detection:
# place_order("TCS25OCT2800PE", "BUY", 175)     # Auto → NFO + NRML (contains numbers)
# place_order("SBIN", "SELL", 100)              # Auto → NSE + CNC (no numbers)
# place_order("BANKNIFTY25OCT50000CE", "BUY", 25)  # Auto → NFO + NRML (contains numbers)
# place_order("INFY", "BUY", 50)                # Auto → NSE + CNC (no numbers)

# CDS (Currency Derivatives) examples:
# place_order("USDINR25AUGFUT", "BUY", 1000)   # Auto → CDS + NRML (currency futures)
# place_order("EURINR25AUGFUT", "SELL", 500)   # Auto → CDS + NRML (currency futures)
# place_order("GBPINR25AUGFUT", "BUY", 200)    # Auto → CDS + NRML (currency futures)

