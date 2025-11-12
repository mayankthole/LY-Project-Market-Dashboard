from kiteconnect import KiteConnect
import os
import csv
import time
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
from google.auth.transport.requests import Request

# Google Sheets setup
scopes = ["https://www.googleapis.com/auth/spreadsheets"]

def get_credentials_from_sheet():
    """
    Get API credentials and access token from Google Sheet 'Info'
    """
    try:
        # Initialize Google Sheets API
        creds = Credentials.from_service_account_file(
            'service_account.json',  # You'll need to create this file
            scopes=scopes
        )
        
        client = gspread.authorize(creds)
        
        # Open the spreadsheet and Info sheet
        # Replace 'your_spreadsheet_name' with your actual spreadsheet name
        spreadsheet = client.open_by_key('1xHoWl9HZdpuRVM9Mh_WLuPeeCd4CZAhIDpoeYVfvHTE')
        info_sheet = spreadsheet.worksheet('Info')
        
        # Read API credentials from B column
        api_key = info_sheet.acell('B1').value  # B1 for api_key
        api_secret = info_sheet.acell('B2').value  # B2 for api_secret
        
        # Read access token from B column (B3)
        access_token = info_sheet.acell('B3').value
        
        print("Successfully loaded credentials from Google Sheet")
        return api_key, api_secret, access_token
        
    except Exception as e:
        print(f"Error reading from Google Sheet: {e}")
        print("Please ensure you have:")
        print("1. service_account.json file in the same directory")
        print("2. Google Sheet with ID '1xHoWl9HZdpuRVM9Mh_WLuPeeCd4CZAhIDpoeYVfvHTE' with 'Info' sheet")
        print("3. API credentials in B1, B2, and access token in B3")
        return None, None, None

# Get credentials from Google Sheet
api_key, api_secret, access_token = get_credentials_from_sheet()

if not api_key or not api_secret:
    print("Failed to load API credentials. Exiting...")
    exit()

kite = KiteConnect(api_key=api_key)

def set_access_token_from_sheet():
    """
    Set access token from Google Sheet
    """
    global access_token
    if access_token:
        try:
            kite.set_access_token(access_token)
            kite.profile()
            print("Using access token from Google Sheet.")
            return True
        except Exception:
            print("Access token from sheet is invalid or expired.")
            return False
    return False

if not set_access_token_from_sheet():
    print("Login URL:", kite.login_url())
    request_token = input("Enter the request_token from the URL: ")
    data = kite.generate_session(request_token, api_secret=api_secret)
    access_token = data["access_token"]
    kite.set_access_token(access_token)
    print("Access token set successfully")

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

def place_order(symbol, direction, quantity, product=None):
    # Automatically detect exchange based on symbol
    if sum(1 for char in symbol if char.isdigit()) >= 2:
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
        # Always return a tuple to avoid unpacking errors upstream
        return None, None
    
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
        return order_id, best_price
    except Exception as e:
        print(f"Error: {e}")
        return None, None


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



def process_place_orders():
    """
    Read orders from Google Sheet 'Place_Orders' and process rows without status.
    Columns:
      A: symbol, B: direction (BUY/SELL), C: quantity, D: status, E: timestamp
    Starts from row 2 (row 1 is header). If D == 'Order_Placed', skip.
    """
    try:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Polling Place_Orders...", flush=True)
        creds = Credentials.from_service_account_file('service_account.json', scopes=scopes)
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key('1xHoWl9HZdpuRVM9Mh_WLuPeeCd4CZAhIDpoeYVfvHTE')
        sheet = spreadsheet.worksheet('Place_Orders')

        rows = sheet.get_all_values()
        if len(rows) <= 1:
            print("No data rows found (only header).", flush=True)
            return
        placed_count = 0
        skipped_count = 0
        invalid_count = 0
        # rows[0] is header; start from index 1
        for idx in range(1, len(rows)):
            row = rows[idx]
            # Safely access columns with defaults
            symbol = row[0].strip() if len(row) > 0 else ""
            direction = (row[1] or "").strip().upper() if len(row) > 1 else ""
            quantity_str = (row[2] or "").strip() if len(row) > 2 else ""
            status = (row[3] or "").strip().upper() if len(row) > 3 else ""

            # Skip empty or already processed rows
            if not symbol or not direction or not quantity_str:
                invalid_count += 1
                continue
            if status == "ORDER_PLACED":
                skipped_count += 1
                continue

            try:
                quantity = int(float(quantity_str))
            except Exception:
                print(f"Invalid quantity at row {idx+1}: '{quantity_str}'")
                continue

            # Place the order
            print(f"Placing order for row {idx+1}: {symbol} {direction} {quantity}", flush=True)
            order_id, limit_price = place_order(symbol, direction, quantity)

            # On success, write status and timestamp
            if order_id:
                row_num = idx + 1  # 1-based row in sheet
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                try:
                    # Update status, timestamp and limit price in a single call (D, E, F columns)
                    sheet.update(range_name=f"D{row_num}:F{row_num}", values=[["Order_Placed", timestamp, limit_price]])
                    placed_count += 1
                except Exception as e:
                    print(f"Failed updating status for row {row_num}: {e}")
            
            # Add a small delay between processing rows
            time.sleep(1)
        total_rows = len(rows) - 1
        print(f"Cycle done: total={total_rows}, placed={placed_count}, skipped={skipped_count}, invalid={invalid_count}", flush=True)
    except Exception as e:
        print(f"process_place_orders error: {e}", flush=True)


if __name__ == "__main__":
    print("Starting Place_Orders poller (runs every 10s)...", flush=True)
    while True:
        process_place_orders()
        time.sleep(10)