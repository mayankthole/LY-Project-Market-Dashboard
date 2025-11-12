from kiteconnect import KiteConnect
import os
import csv
import time
from datetime import datetime
import pytz
import gspread
from google.oauth2.service_account import Credentials
from google.auth.transport.requests import Request
from dotenv import load_dotenv, dotenv_values
import warnings

# Google Sheets setup
scopes = ["https://www.googleapis.com/auth/spreadsheets"]

# Load environment variables from .env if present
load_dotenv()
# Suppress deprecation warnings from dependencies to keep output clean
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Indian timezone
IST = pytz.timezone('Asia/Kolkata')

def get_indian_time():
    """
    Get current time in Indian Standard Time (IST)
    """
    return datetime.now(IST)

def get_indian_timestamp():
    """
    Get current timestamp in IST format: YYYY-MM-DD HH:MM:SS
    """
    return get_indian_time().strftime('%Y-%m-%d %H:%M:%S')

def get_indian_time_log():
    """
    Get current time in IST format for logging: HH:MM:SS
    """
    return get_indian_time().strftime('%H:%M:%S')

# Read Google Sheet ID strictly from .env (no runtime env fallback)
_env_values = dotenv_values()
SHEET_ID = _env_values.get("SHEET_ID")
if not SHEET_ID:
    print("SHEET_ID is not set in .env. Please create a .env file with SHEET_ID=<your_sheet_id>.")
    exit(1)

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
        spreadsheet = client.open_by_key(SHEET_ID)
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
        print(f"2. Google Sheet with ID '{SHEET_ID}' with 'Info' sheet")
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


def place_order_with_kite(kite, symbol, direction, quantity, product=None, limit_price=None):
    # Automatically detect exchange based on symbol
    if sum(1 for char in symbol if char.isdigit()) >= 2:
        # Check if it's CDS (Currency Derivatives) first
        if any(currency in symbol.upper() for currency in ['USDINR', 'EURINR', 'GBPINR', 'JPYINR', 'INR']):
            exchange = "CDS"  # Currency derivatives
            # concise logs: no per-symbol exchange print
        else:
            exchange = "NFO"  # Other derivatives (options/futures)
            # concise logs: no per-symbol exchange print
    else:
        exchange = "NSE"  # No numbers = equity shares
        # concise logs: no per-symbol exchange print
    
    exchanges = {"NSE": kite.EXCHANGE_NSE, "NFO": kite.EXCHANGE_NFO, "CDS": kite.EXCHANGE_CDS}
    directions = {"BUY": kite.TRANSACTION_TYPE_BUY, "SELL": kite.TRANSACTION_TYPE_SELL}
    products = {"CNC": kite.PRODUCT_CNC, "MIS": kite.PRODUCT_MIS, "NRML": kite.PRODUCT_NRML}
    
    # Set default product based on exchange if not specified
    if product is None:
        if exchange == "NSE":
            product = "CNC"  # Cash and Carry for equity shares
        elif exchange in ["NFO", "CDS"]:
            product = "NRML"  # Normal margin for derivatives
        # concise logs: no per-symbol exchange print
    
    # Use provided price or try to get the best price from quotes for LIMIT orders
    best_price = limit_price
    if best_price is None:
        try:
            # Get quote for the symbol
            quote_symbol = f"{exchange}:{symbol}"
            quotes = kite.quote(quote_symbol)
            
            if direction == "BUY":
                # For BUY order, use best bid price (what buyers are willing to pay)
                best_price = quotes[quote_symbol]['depth']['buy'][0]['price']
                # concise logs: no per-symbol exchange print
            else:  # SELL
                # For SELL order, use best ask price (what sellers are asking)
                best_price = quotes[quote_symbol]['depth']['sell'][0]['price']
                # concise logs: no per-symbol exchange print
            
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
        # concise logs: no per-symbol exchange print
        return order_id, best_price
    except Exception as e:
        print(f"Order error: {e}")
        return None, None

def check_order_status(kite, order_id):
    """
    Check the status of an order using order ID
    Returns the LATEST (LAST) order status or None if error
    """
    try:
        order_history = kite.order_history(order_id)
        if order_history and len(order_history) > 0:
            # Sort by exchange_timestamp to get the most recent status
            # Convert timestamp to datetime for proper sorting
            def get_timestamp(status_item):
                timestamp_str = status_item.get('exchange_timestamp', '')
                if timestamp_str:
                    try:
                        # Parse the timestamp (format: 2024-01-15 14:30:25)
                        return datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                    except:
                        return datetime.min
                return datetime.min
            
            # Sort by timestamp ascending (oldest first) to get the LAST (most recent) status
            sorted_history = sorted(order_history, key=get_timestamp, reverse=False)
            latest_status = sorted_history[-1]  # LAST (most recent) status
            
            # Keep output clean: no verbose per-status logs
            
            # Get the status and additional details from the LAST entry
            status = latest_status.get('status', 'UNKNOWN')
            filled_quantity = latest_status.get('filled_quantity', 0)
            pending_quantity = latest_status.get('pending_quantity', 0)
            exchange_timestamp = latest_status.get('exchange_timestamp', '')
            
            # Create a more detailed status
            if status == 'COMPLETE':
                return f"COMPLETE ({filled_quantity} filled)"
            elif status == 'OPEN' and pending_quantity > 0:
                return f"OPEN PENDING ({pending_quantity} pending)"
            elif status == 'OPEN':
                return "OPEN"
            elif status == 'CANCELLED':
                return "CANCELLED"
            elif status == 'REJECTED':
                return "REJECTED"
            else:
                return status
                
        return None
    except Exception as e:
        print(f"Error checking order status for {order_id}: {e}")
        return None

def update_order_statuses(kite, sheet_id):
    """
    Check and update order statuses for all orders with action_status = "Order_Placed"
    """
    try:
        print(f"[{get_indian_time_log()}] Checking order statuses...", flush=True)
        creds = Credentials.from_service_account_file('service_account.json', scopes=scopes)
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(sheet_id)
        sheet = spreadsheet.worksheet('Actions')

        rows = sheet.get_all_values()
        if len(rows) <= 1:
            print("No data rows found for status update.", flush=True)
            return "No data rows found"
        
        updated_count = 0
        error_count = 0
        status_updates = []
        
        # Check each row for orders that need status update
        for idx in range(1, len(rows)):
            row = rows[idx]
            
            # Safely access columns with defaults
            action_status = (row[3] or "").strip().upper() if len(row) > 3 else ""
            order_id = (row[6] or "").strip() if len(row) > 6 else ""  # Column G (index 6)
            
            # Only check status for orders that are placed
            if action_status == "ORDER_PLACED" and order_id:
                try:
                    # Check the order status
                    status = check_order_status(kite, order_id)
                    if status:
                        row_num = idx + 1  # 1-based row in sheet
                        timestamp = get_indian_timestamp()
                        # Accumulate updates for batch write
                        status_updates.append({
                            'range': f"H{row_num}:I{row_num}",
                            'values': [[status, timestamp]]
                        })
                        updated_count += 1
                    else:
                        print(f"Could not get status for order {order_id}")
                        error_count += 1
                        
                except Exception as e:
                    print(f"Error updating status for order {order_id}: {e}")
                    error_count += 1
                
                # Add a small delay between API calls
                time.sleep(0.5)

        # Perform one batch update for all status rows
        if status_updates:
            try:
                sheet.batch_update(status_updates)
                print(f"Applied {len(status_updates)} status updates in batch.")
            except Exception as e:
                print(f"Batch status update error: {e}")
        
        result = f"status_updated={updated_count}, errors={error_count}"
        print(f"Status update cycle done: {result}", flush=True)
        return result
        
    except Exception as e:
        print(f"update_order_statuses error: {e}", flush=True)
        return f"Error: {e}"

def update_portfolio_data(kite, sheet_id):
    """
    Update Google Sheets tabs: Holdings, Positions, OrdersToday using Kite data.
    Uses IST timestamps and gspread client already used elsewhere.
    """
    try:
        print(f"[{get_indian_time_log()}] Updating portfolio data (Holdings, Positions, OrdersToday)...", flush=True)
        creds = Credentials.from_service_account_file('service_account.json', scopes=scopes)
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(sheet_id)

        # Prepare worksheets (create if missing)
        def get_or_create_worksheet(name, rows=1000, cols=26):
            try:
                return spreadsheet.worksheet(name)
            except Exception:
                return spreadsheet.add_worksheet(title=name, rows=str(rows), cols=str(cols))

        ws_holdings = get_or_create_worksheet('Holdings')
        ws_positions = get_or_create_worksheet('Positions')
        ws_orders_today = get_or_create_worksheet('OrdersToday')

        # Clear existing content
        try:
            ws_holdings.clear()
            ws_positions.clear()
            ws_orders_today.clear()
        except Exception:
            pass

        # Holdings
        holdings_data = [[
            "Instrument", "Exchange", "ISIN", "Qty", "T1 Qty", "Collateral Qty",
            "Avg Price", "Last Price", "P&L"
        ]]
        try:
            holdings = kite.holdings()
            for item in holdings:
                if not item.get('tradingsymbol'):
                    continue
                holdings_data.append([
                    item.get('tradingsymbol', ''),
                    item.get('exchange', ''),
                    item.get('isin', ''),
                    item.get('quantity', 0),
                    item.get('t1_quantity', 0),
                    item.get('collateral_quantity', 0),
                    item.get('average_price', 0.0),
                    item.get('last_price', 0.0),
                    item.get('pnl', 0.0),
                ])
        except Exception as e:
            print(f"Holdings fetch error: {e}")

        if holdings_data:
            ws_holdings.update(range_name='A1', values=holdings_data)

        # Positions (net)
        positions_data = [[
            "Instrument", "Exchange", "Product", "Qty", "Overnight Qty",
            "Avg Price", "Last Price", "P&L", "Realised", "Unrealised"
        ]]
        try:
            positions = kite.positions().get('net', [])
            for p in positions:
                if not p.get('tradingsymbol'):
                    continue
                positions_data.append([
                    p.get('tradingsymbol', ''),
                    p.get('exchange', ''),
                    p.get('product', ''),
                    p.get('quantity', 0),
                    p.get('overnight_quantity', 0),
                    p.get('average_price', 0.0),
                    p.get('last_price', 0.0),
                    p.get('pnl', 0.0),
                    p.get('realised', 0.0),
                    p.get('unrealised', 0.0),
                ])
        except Exception as e:
            print(f"Positions fetch error: {e}")

        if positions_data:
            ws_positions.update(range_name='A1', values=positions_data)

        # OrdersToday
        orders_today_data = [[
            "Order ID", "Instrument", "Exchange", "Order Type", "Product",
            "Transaction Type", "Variety", "Status", "Order Timestamp", "Qty",
            "Filled Qty", "Price"
        ]]
        try:
            orders = kite.orders()
            today_ist_date = get_indian_time().date()

            for o in orders:
                order_ts = o.get('order_timestamp')
                if not order_ts:
                    continue

                # Normalize to datetime
                if isinstance(order_ts, str):
                    try:
                        # Attempt ISO parse first
                        ts_dt = datetime.fromisoformat(order_ts)
                    except Exception:
                        # Fallback to known format
                        try:
                            ts_dt = datetime.strptime(order_ts, '%Y-%m-%d %H:%M:%S')
                        except Exception:
                            continue
                else:
                    ts_dt = order_ts

                # Compare by IST date
                try:
                    ts_ist = ts_dt if ts_dt.tzinfo else ts_dt.replace(tzinfo=pytz.utc)
                    ts_ist = ts_ist.astimezone(IST)
                except Exception:
                    # If timezone conversion fails, best effort compare naive date
                    ts_ist = ts_dt

                if ts_ist.date() == today_ist_date:
                    orders_today_data.append([
                        o.get('order_id', ''),
                        o.get('tradingsymbol', ''),
                        o.get('exchange', ''),
                        o.get('order_type', ''),
                        o.get('product', ''),
                        o.get('transaction_type', ''),
                        o.get('variety', ''),
                        o.get('status', ''),
                        ts_ist.strftime('%Y-%m-%d %H:%M:%S'),
                        o.get('quantity', 0),
                        o.get('filled_quantity', 0),
                        o.get('average_price', 0.0) or o.get('price', 0.0),
                    ])
        except Exception as e:
            print(f"Orders fetch error: {e}")

        if orders_today_data:
            ws_orders_today.update(range_name='A1', values=orders_today_data)

        # Update Info! last_updated timestamp (IST) similar to update-data.py logic
        try:
            ws_info = get_or_create_worksheet('Info')
            values = ws_info.get('A1:B20') or []
            target_row = None
            for idx, row in enumerate(values, start=1):
                if len(row) >= 1 and str(row[0]).strip().lower() == 'last_updated':
                    target_row = idx
                    break
            if target_row is not None:
                ws_info.update(range_name=f'B{target_row}', values=[[get_indian_timestamp()]])
            else:
                # If not found, append the key-value at the end (next row after current values)
                next_row = len(values) + 1
                ws_info.update(range_name=f'A{next_row}:B{next_row}', values=[['last_updated', get_indian_timestamp()]])
        except Exception as e:
            print(f"Info! last_updated write error: {e}")

        print(f"[{get_indian_time_log()}] Portfolio data update done.", flush=True)
        return "Portfolio update done"
    except Exception as e:
        print(f"update_portfolio_data error: {e}", flush=True)
        return f"Error: {e}"

def place_order(symbol, direction, quantity, product=None):
    # Automatically detect exchange based on symbol
    if sum(1 for char in symbol if char.isdigit()) >= 2:
        # Check if it's CDS (Currency Derivatives) first
        if any(currency in symbol.upper() for currency in ['USDINR', 'EURINR', 'GBPINR', 'JPYINR', 'INR']):
            exchange = "CDS"  # Currency derivatives
            # concise logs: no per-symbol exchange print
        else:
            exchange = "NFO"  # Other derivatives (options/futures)
            # concise logs: no per-symbol exchange print
    else:
        exchange = "NSE"  # No numbers = equity shares
        # concise logs: no per-symbol exchange print
    
    exchanges = {"NSE": kite.EXCHANGE_NSE, "NFO": kite.EXCHANGE_NFO, "CDS": kite.EXCHANGE_CDS}
    directions = {"BUY": kite.TRANSACTION_TYPE_BUY, "SELL": kite.TRANSACTION_TYPE_SELL}
    products = {"CNC": kite.PRODUCT_CNC, "MIS": kite.PRODUCT_MIS, "NRML": kite.PRODUCT_NRML}
    
    # Set default product based on exchange if not specified
    if product is None:
        if exchange == "NSE":
            product = "CNC"  # Cash and Carry for equity shares
        elif exchange in ["NFO", "CDS"]:
            product = "NRML"  # Normal margin for derivatives
        # concise logs: no per-symbol exchange print
    
    # Always get the best price from quotes for LIMIT orders
    try:
        # Get quote for the symbol
        quote_symbol = f"{exchange}:{symbol}"
        quotes = kite.quote(quote_symbol)
        
        if direction == "BUY":
            # For BUY order, use best bid price (what buyers are willing to pay)
            best_price = quotes[quote_symbol]['depth']['buy'][0]['price']
            # concise logs: no per-symbol exchange print
        else:  # SELL
            # For SELL order, use best ask price (what sellers are asking)
            best_price = quotes[quote_symbol]['depth']['sell'][0]['price']
            # concise logs: no per-symbol exchange print
        
    except Exception as e:
        print(f"Error getting quote for price: {e}")
        # Always return a tuple to avoid unpacking errors upstream
        return None, None
    
    try:
        order_id = kite.place_order(
            # variety=kite.VARIETY_AMO, # make this regular # PLEASE UPDTE THIS AND MAKE IT REGULAR AFTERTESTING
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
        # concise logs: no per-symbol exchange print
        return order_id, best_price
    except Exception as e:
        print(f"Order error: {e}")
        return None, None



def process_place_orders_with_kite(kite, sheet_id):
    """
    Read orders from Google Sheet 'Actions' and process rows without action_status.
    First places all pending orders, then checks status of placed orders.
    This version accepts kite and sheet_id as parameters for Cloud Functions.
    """
    try:
        print(f"[{get_indian_time_log()}] Starting order processing cycle...", flush=True)
        
        # STEP 1: Place all pending orders
        print(f"[{get_indian_time_log()}] Step 1: Placing pending orders...", flush=True)
        creds = Credentials.from_service_account_file('service_account.json', scopes=scopes)
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(sheet_id)
        sheet = spreadsheet.worksheet('Actions')

        rows = sheet.get_all_values()
        if len(rows) <= 1:
            print("No data rows found (only header).", flush=True)
            return "No data rows found"
        
        placed_count = 0
        skipped_count = 0
        invalid_count = 0
        
        # rows[0] is header; start from index 1
        placements_updates = []
        for idx in range(1, len(rows)):
            row = rows[idx]
            # Safely access columns with defaults
            symbol = row[0].strip() if len(row) > 0 else ""
            direction = (row[1] or "").strip().upper() if len(row) > 1 else ""
            quantity_str = (row[2] or "").strip() if len(row) > 2 else ""
            action_status = (row[3] or "").strip().upper() if len(row) > 3 else ""

            # Skip empty or already processed rows
            if not symbol or not direction or not quantity_str:
                invalid_count += 1
                continue
            if action_status == "ORDER_PLACED":
                skipped_count += 1
                continue

            try:
                quantity = int(float(quantity_str))
            except Exception:
                print(f"Invalid quantity at row {idx+1}: '{quantity_str}'")
                continue

            # Place the order using the provided kite object
            print(f"Placing order for row {idx+1}: {symbol} {direction} {quantity}", flush=True)
            order_id, limit_price = place_order_with_kite(kite, symbol, direction, quantity)

            # On success, accumulate action_status and timestamp update
            if order_id:
                row_num = idx + 1  # 1-based row in sheet
                timestamp = get_indian_timestamp()
                placements_updates.append({
                    'range': f"D{row_num}:G{row_num}",
                    'values': [["Order_Placed", timestamp, limit_price, order_id]]
                })
                placed_count += 1
            
            # Add a small delay between processing rows
            time.sleep(0.5)
        
        # Perform one batch update for all placements
        if placements_updates:
            try:
                sheet.batch_update(placements_updates)
                print(f"Applied {len(placements_updates)} placement updates in batch.")
            except Exception as e:
                print(f"Batch placements update error: {e}")

        total_rows = len(rows) - 1
        place_result = f"total={total_rows}, placed={placed_count}, skipped={skipped_count}, invalid={invalid_count}"
        print(f"Order placement cycle done: {place_result}", flush=True)
        
        # STEP 2: Check status of all placed orders
        print(f"[{get_indian_time_log()}] Step 2: Checking order statuses...", flush=True)
        status_result = update_order_statuses(kite, sheet_id)
        
        # STEP 3: Update portfolio snapshots
        print(f"[{get_indian_time_log()}] Step 3: Updating portfolio data...", flush=True)
        portfolio_result = update_portfolio_data(kite, sheet_id)

        # Combine results
        final_result = f"Placement: {place_result} | Status: {status_result} | Portfolio: {portfolio_result}"
        print(f"Complete cycle done: {final_result}", flush=True)
        
        return final_result
        
    except Exception as e:
        print(f"process_place_orders_with_kite error: {e}", flush=True)
        return f"Error: {e}"

def process_place_orders():
    """
    Read orders from Google Sheet 'Actions' and process rows without action_status.
    First places all pending orders, then checks status of placed orders.
    Columns:
      A: symbol, B: direction (BUY/SELL), C: quantity, D: action_status, E: timestamp, F: limit_price, G: order_id, H: order_status, I: status_timestamp
    Starts from row 2 (row 1 is header). If D == 'Order_Placed', skip.
    """
    try:
        print(f"[{get_indian_time_log()}] Starting order processing cycle...", flush=True)
        
        # STEP 1: Place all pending orders
        print(f"[{get_indian_time_log()}] Step 1: Placing pending orders...", flush=True)
        creds = Credentials.from_service_account_file('service_account.json', scopes=scopes)
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(SHEET_ID)
        sheet = spreadsheet.worksheet('Actions')

        rows = sheet.get_all_values()
        if len(rows) <= 1:
            print("No data rows found (only header).", flush=True)
            return
        placed_count = 0
        skipped_count = 0
        invalid_count = 0
        placements_updates = []
        # rows[0] is header; start from index 1
        for idx in range(1, len(rows)):
            row = rows[idx]
            # Safely access columns with defaults
            symbol = row[0].strip() if len(row) > 0 else ""
            direction = (row[1] or "").strip().upper() if len(row) > 1 else ""
            quantity_str = (row[2] or "").strip() if len(row) > 2 else ""
            action_status = (row[3] or "").strip().upper() if len(row) > 3 else ""

            # Skip empty or already processed rows
            if not symbol or not direction or not quantity_str:
                invalid_count += 1
                continue
            if action_status == "ORDER_PLACED":
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

            # On success, accumulate action_status and timestamp
            if order_id:
                row_num = idx + 1  # 1-based row in sheet
                timestamp = get_indian_timestamp()
                placements_updates.append({
                    'range': f"D{row_num}:G{row_num}",
                    'values': [["Order_Placed", timestamp, limit_price, order_id]]
                })
                placed_count += 1
            
            # Add a small delay between processing rows
            time.sleep(0.5)
        
        # Perform one batch update for all placements
        if placements_updates:
            try:
                sheet.batch_update(placements_updates)
                print(f"Applied {len(placements_updates)} placement updates in batch.")
            except Exception as e:
                print(f"Batch placements update error: {e}")

        total_rows = len(rows) - 1
        place_result = f"total={total_rows}, placed={placed_count}, skipped={skipped_count}, invalid={invalid_count}"
        print(f"Order placement cycle done: {place_result}", flush=True)
        
        # STEP 2: Check status of all placed orders
        print(f"[{get_indian_time_log()}] Step 2: Checking order statuses...", flush=True)
        status_result = update_order_statuses(kite, SHEET_ID)
        
        # STEP 3: Update portfolio snapshots
        print(f"[{get_indian_time_log()}] Step 3: Updating portfolio data...", flush=True)
        portfolio_result = update_portfolio_data(kite, SHEET_ID)

        # Combine results
        final_result = f"Placement: {place_result} | Status: {status_result} | Portfolio: {portfolio_result}"
        print(f"Complete cycle done: {final_result}", flush=True)
        
    except Exception as e:
        print(f"process_place_orders error: {e}", flush=True)


if __name__ == "__main__":
    print("Starting Actions run (single execution)...", flush=True)
    process_place_orders()

# Google Cloud Functions HTTP entry point
def hello_http(request):
    try:
        print(f"[{get_indian_time_log()}] Starting Cloud Function execution...")
        
        # Initialize everything inside the function for Cloud Functions
        # Load environment variables
        load_dotenv()
        
        # Use module-level SHEET_ID loaded from .env
        if not SHEET_ID:
            return ("SHEET_ID is not set in .env.", 500, {"Content-Type": "text/plain"})
        
        # Get credentials from Google Sheet
        api_key, api_secret, access_token = get_credentials_from_sheet()
        
        if not api_key or not api_secret:
            return ("Failed to load API credentials.", 500, {"Content-Type": "text/plain"})
        
        # Initialize Kite Connect
        kite = KiteConnect(api_key=api_key)
        
        # Set access token
        if access_token:
            try:
                kite.set_access_token(access_token)
                kite.profile()
                print(f"[{get_indian_time_log()}] Using access token from Google Sheet.")
            except Exception:
                return ("Access token from sheet is invalid or expired.", 500, {"Content-Type": "text/plain"})
        else:
            return ("No access token available.", 500, {"Content-Type": "text/plain"})
        
        # Now process orders with the initialized kite object (places orders + checks status)
        print(f"[{get_indian_time_log()}] Starting order processing and status checking...")
        result = process_place_orders_with_kite(kite, SHEET_ID)
        print(f"[{get_indian_time_log()}] Cloud Function cycle completed: {result}")
        
        # Return detailed response with Indian timestamp
        response_time = get_indian_timestamp()
        return (f"[{response_time}] Processed Actions and checked statuses. {result}", 200, {"Content-Type": "text/plain"})
        
    except Exception as e:
        error_time = get_indian_timestamp()
        print(f"[{error_time}] Cloud Function error: {e}")
        return (f"[{error_time}] Error while processing: {e}", 500, {"Content-Type": "text/plain"})