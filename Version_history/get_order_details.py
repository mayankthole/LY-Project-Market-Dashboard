from kiteconnect import KiteConnect
import os
import sys
import json
import gspread
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def get_kite_from_sheet() -> KiteConnect:
    load_dotenv()
    sheet_id = os.getenv("SHEET_ID")
    if not sheet_id:
        print("SHEET_ID environment variable is not set. Please create a .env file with SHEET_ID=<your_sheet_id>.")
        sys.exit(1)

    try:
        creds = Credentials.from_service_account_file('service_account.json', scopes=SCOPES)
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(sheet_id)
        info_sheet = spreadsheet.worksheet('Info')

        api_key = info_sheet.acell('B1').value
        api_secret = info_sheet.acell('B2').value
        access_token = info_sheet.acell('B3').value

        if not api_key or not api_secret:
            print("Missing API credentials in Info sheet (B1/B2).")
            sys.exit(1)

        kite = KiteConnect(api_key=api_key)
        if access_token:
            try:
                kite.set_access_token(access_token)
                kite.profile()
                return kite
            except Exception:
                print("Access token in sheet is invalid/expired. Please update B3.")
                sys.exit(1)
        else:
            print("Access token missing. Please generate and put it in Info! (B3)")
            sys.exit(1)
    except Exception as e:
        print(f"Failed to initialize Kite from Google Sheet: {e}")
        sys.exit(1)


def main():
    # Hardcoded order ID for quick testing
    order_id = "1965416523950727168"

    kite = get_kite_from_sheet()

    try:
        # order_history gives the lifecycle entries for the order id
        history = kite.order_history(order_id)
        print(json.dumps(history, indent=2, default=str))
    except Exception as e:
        print(f"Failed to fetch order details: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()


