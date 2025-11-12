# def place_order(self,
#                 variety,
#                 exchange,
#                 tradingsymbol,
#                 transaction_type,
#                 quantity,
#                 product,
#                 order_type,
#                 price=None,
#                 validity=None,
#                 disclosed_quantity=None,
#                 trigger_price=None,
#                 squareoff=None,
#                 stoploss=None,
#                 trailing_stoploss=None,
#                 tag=None):
#     """Place an order."""
#     params = locals()
#     del(params["self"])
#     for k in list(params.keys()):
#         if params[k] is None:
#             del(params[k])
#     return self._post("order.place",
#                       url_args={"variety": variety},
#                       params=params)["order_id"]



import logging
from kiteconnect import KiteConnect
import os

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Your API credentials
api_key = "4zh29s26x8rfrwom"
api_secret = "kscytrsv5vhvf2wzp12gvja3wqwqti3u"
access_token_file = "access_token.txt"

# Initialize Kite
kite = KiteConnect(api_key=api_key)

def set_access_token_from_file():
    """Load saved access token if available and valid"""
    if os.path.exists(access_token_file):
        with open(access_token_file, "r") as f:
            token = f.read().strip()
            if token:
                try:
                    kite.set_access_token(token)
                    kite.profile()
                    logging.info("Using saved access token.")
                    return True
                except Exception:
                    pass
    return False

def authenticate():
    """Handle Zerodha authentication"""
    if not set_access_token_from_file():
        print("Login URL:", kite.login_url())
        request_token = input("Enter the request_token from the URL: ")
        data = kite.generate_session(request_token, api_secret=api_secret)
        access_token = data["access_token"]
        kite.set_access_token(access_token)
        with open(access_token_file, "w") as f:
            f.write(access_token)
        logging.info("Access token saved to access_token.txt")

def place_order(symbol, direction, quantity, exchange="NFO", order_type="MARKET", product="MIS", price=None):
    """
    Simple function to place order via Zerodha Kite API
    
    Args:
        symbol: Trading symbol (e.g., "RELIANCE", "BANKNIFTY24JAN50000CE")
        direction: "BUY" or "SELL"
        quantity: Number of shares/lots
        exchange: "NSE", "BSE", "NFO", "MCX" (default: "NFO")
        order_type: "MARKET" or "LIMIT" (default: "MARKET")
        product: "MIS", "CNC", "NRML" (default: "MIS")
        price: Price for limit orders (optional)
    
    Returns:
        order_id if successful, None if failed
    """
    
    # Map string values to Kite constants
    exchanges = {
        "NSE": kite.EXCHANGE_NSE,
        "BSE": kite.EXCHANGE_BSE,
        "NFO": kite.EXCHANGE_NFO,
        "MCX": kite.EXCHANGE_MCX
    }
    
    transaction_types = {
        "BUY": kite.TRANSACTION_TYPE_BUY,
        "SELL": kite.TRANSACTION_TYPE_SELL
    }
    
    order_types = {
        "MARKET": kite.ORDER_TYPE_MARKET,
        "LIMIT": kite.ORDER_TYPE_LIMIT
    }
    
    products = {
        "MIS": kite.PRODUCT_MIS,
        "CNC": kite.PRODUCT_CNC,
        "NRML": kite.PRODUCT_NRML
    }
    
    try:
        order_id = kite.place_order(
            variety=kite.VARIETY_REGULAR,
            exchange=exchanges[exchange],
            tradingsymbol=symbol,
            transaction_type=transaction_types[direction],
            quantity=quantity,
            product=products[product],
            order_type=order_types[order_type],
            price=price,
            validity=kite.VALIDITY_DAY
        )
        
        logging.info(f"✅ Order placed: {symbol} | {direction} | Qty: {quantity} | Order ID: {order_id}")
        return order_id
        
    except Exception as e:
        logging.error(f"❌ Order failed: {symbol} | Error: {e}")
        return None

def main():
    """Main function to run the trading script"""
    
    # Authenticate
    authenticate()
    
    # Example usage - place some sample orders
    print("\n" + "="*50)
    print("PLACING SAMPLE ORDERS")
    print("="*50)
    
    # Example 1: Buy equity stock (market order)
    place_order("RELIANCE", "BUY", 1, "NSE", "MARKET", "CNC")
    
    # Example 2: Buy option (market order) - replace with actual symbol
    # place_order("BANKNIFTY24JAN50000CE", "BUY", 25, "NFO", "MARKET", "MIS")
    
    # Example 3: Limit order for equity
    # place_order("SBIN", "BUY", 10, "NSE", "LIMIT", "CNC", 500.50)
    
    # Example 4: Sell order
    # place_order("TCS", "SELL", 1, "NSE", "MARKET", "CNC")
    
    print("\n" + "="*50)
    print("SCRIPT COMPLETED")
    print("="*50)

if __name__ == "__main__":
    main()