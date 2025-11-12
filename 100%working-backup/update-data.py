# update_data_function.py


from kiteconnect import KiteConnect
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from datetime import datetime
import pytz
import os


ist = pytz.timezone('Asia/Kolkata')


SPREADSHEET_ID = os.environ.get('SPREADSHEET_ID')
SERVICE_ACCOUNT_FILE = 'service_account.json'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']


def get_sheet_service():
   creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
   return build('sheets', 'v4', credentials=creds).spreadsheets()


sheet_service = get_sheet_service()


def get_info_values():
   result = sheet_service.values().get(
       spreadsheetId=SPREADSHEET_ID,
       range='Info!A1:B20'
   ).execute()
   values = result.get('values', [])
   info_dict = {}
   for row in values:
       if len(row) >= 2:
           info_dict[row[0].strip().lower()] = row[1].strip()
   return info_dict


def update_info_cell(key, value):
   key = key.lower()
   result = sheet_service.values().get(
       spreadsheetId=SPREADSHEET_ID,
       range='Info!A1:B20'
   ).execute()
   values = result.get('values', [])
   for i, row in enumerate(values):
       if len(row) >= 1 and row[0].strip().lower() == key:
           range_name = f"Info!B{i+1}"
           sheet_service.values().update(
               spreadsheetId=SPREADSHEET_ID,
               range=range_name,
               valueInputOption='RAW',
               body={'values': [[value]]}
           ).execute()
           return


def clear_sheet_range(sheet_name):
   sheet_service.values().clear(
       spreadsheetId=SPREADSHEET_ID,
       range=f'{sheet_name}!A1:Z1000'
   ).execute()


def write_to_sheet(sheet_name, data):
   sheet_service.values().update(
       spreadsheetId=SPREADSHEET_ID,
       range=f'{sheet_name}!A1',
       valueInputOption='RAW',
       body={'values': data}
   ).execute()


def update_data():
   info = get_info_values()
   api_key = info.get("api_key")
   api_secret = info.get("api_secret")
   access_token = info.get("access_token")


   if not api_key or not api_secret or not access_token:
       print("Missing API key, secret, or access token.")
       return "Missing credentials", 400


   kite = KiteConnect(api_key=api_key)
   kite.set_access_token(access_token)


   try:
       clear_sheet_range("Holdings")
       clear_sheet_range("Positions")
       clear_sheet_range("OrdersToday")


       holdings = kite.holdings()
       holdings_data = [["Instrument", "Exchange", "ISIN", "Qty", "T1 Qty", "Collateral Qty",
                       "Avg Price", "Last Price", "P&L"]]


       for h in holdings:
           if not h.get("tradingsymbol"):
               continue


           holdings_data.append([
               h.get("tradingsymbol", ""),
               h.get("exchange", ""),
               h.get("isin", ""),
               h.get("quantity", 0),
               h.get("t1_quantity", 0),
               h.get("collateral_quantity", 0),
               h.get("average_price", 0.0),
               h.get("last_price", 0.0),
               h.get("pnl", 0.0)
           ])


       write_to_sheet("Holdings", holdings_data)


       positions = kite.positions().get("net", [])


       positions_data = [["Instrument", "Exchange", "Product", "Qty", "Overnight Qty",
                       "Avg Price", "Last Price", "P&L", "Realised", "Unrealised"]]


       for p in positions:
           if not p.get("tradingsymbol"):
               continue


           positions_data.append([
               p.get("tradingsymbol", ""),
               p.get("exchange", ""),
               p.get("product", ""),
               p.get("quantity", 0),
               p.get("overnight_quantity", 0),
               p.get("average_price", 0.0),
               p.get("last_price", 0.0),
               p.get("pnl", 0.0),
               p.get("realised", 0.0),
               p.get("unrealised", 0.0)
           ])


       write_to_sheet("Positions", positions_data)


       orders = kite.orders()
       today = datetime.now().date()


       orders_data = [["Order ID", "Instrument", "Exchange", "Order Type", "Product", "Transaction Type",
                       "Variety", "Status", "Order Timestamp", "Qty", "Filled Qty", "Price"]]


       for o in orders:
           timestamp = o.get("order_timestamp")
           if not timestamp:
               continue


           if isinstance(timestamp, str):
               timestamp_dt = datetime.fromisoformat(timestamp)
           else:
               timestamp_dt = timestamp


           if timestamp_dt.date() == today:
               orders_data.append([
                   o.get("order_id", ""),
                   o.get("tradingsymbol", ""),
                   o.get("exchange", ""),
                   o.get("order_type", ""),
                   o.get("product", ""),
                   o.get("transaction_type", ""),
                   o.get("variety", ""),
                   o.get("status", ""),
                   str(timestamp),
                   o.get("quantity", 0),
                   o.get("filled_quantity", 0),
                   o.get("average_price", 0.0) or o.get("price", 0.0)
               ])


       write_to_sheet("OrdersToday", orders_data)


       now_ist = datetime.now(ist)
       update_info_cell("last_updated", now_ist.strftime("%Y-%m-%d %H:%M:%S"))


       return "Data updated successfully", 200


   except Exception as e:
       return f"Error processing data or updating sheets: {e}", 500


def update_data_entry_point(request):
   return update_data()


