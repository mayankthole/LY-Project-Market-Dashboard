from kiteconnect import KiteConnect
import os
import sys
import json
import argparse
import gspread
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials

# Google Sheets scope
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def load_env_and_sheet_id() -> str:
    load_dotenv()
    sheet_id = os.getenv("SHEET_ID")
    if not sheet_id:
        print("SHEET_ID environment variable is not set. Please create a .env file with SHEET_ID=<your_sheet_id>.")
        sys.exit(1)
    return sheet_id


def get_kite_from_sheet(sheet_id: str) -> tuple[KiteConnect, str]:
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

        # Try to set token from sheet first
        if access_token:
            try:
                kite.set_access_token(access_token)
                kite.profile()
                return kite, api_secret
            except Exception:
                print("Access token in sheet is invalid/expired. You must login and update B3.")
                # Fall through to require manual login
        print("Access token missing or invalid. Please generate a new one via login flow and update Info!\nLogin URL:", kite.login_url())
        sys.exit(1)
    except Exception as e:
        print(f"Failed to initialize Kite from Google Sheet: {e}")
        sys.exit(1)


def auto_detect_exchange(symbol: str) -> str:
    if sum(1 for c in symbol if c.isdigit()) >= 2:
        if any(curr in symbol.upper() for curr in ['USDINR', 'EURINR', 'GBPINR', 'JPYINR', 'INR']):
            return "CDS"
        return "NFO"
    return "NSE"


def fetch_best_limit_price(kite: KiteConnect, exchange: str, symbol: str, direction: str) -> float:
    quote_symbol = f"{exchange}:{symbol}"
    quotes = kite.quote(quote_symbol)
    if direction.upper() == "BUY":
        return quotes[quote_symbol]['depth']['buy'][0]['price']
    return quotes[quote_symbol]['depth']['sell'][0]['price']


def main():
    parser = argparse.ArgumentParser(description="Place a single LIMIT order and print full API response.")
    parser.add_argument("symbol", help="Trading symbol, e.g. RELIANCE or NIFTY24SEP24000CE")
    parser.add_argument("direction", choices=["BUY", "SELL", "buy", "sell"], help="BUY or SELL")
    parser.add_argument("quantity", type=int, help="Order quantity")
    parser.add_argument("--product", choices=["CNC", "MIS", "NRML"], help="Product type (default based on exchange)")
    parser.add_argument("--variety", choices=["REGULAR", "AMO"], default="REGULAR", help="Order variety")
    args = parser.parse_args()

    sheet_id = load_env_and_sheet_id()
    kite, _api_secret = get_kite_from_sheet(sheet_id)

    symbol = args.symbol
    direction = args.direction.upper()
    quantity = int(args.quantity)

    exchange = auto_detect_exchange(symbol)
    print(f"Exchange detected: {exchange}")

    # Default product
    product = args.product
    if product is None:
        product = "CNC" if exchange == "NSE" else "NRML"

    # Enums
    exchanges = {"NSE": kite.EXCHANGE_NSE, "NFO": kite.EXCHANGE_NFO, "CDS": kite.EXCHANGE_CDS}
    directions = {"BUY": kite.TRANSACTION_TYPE_BUY, "SELL": kite.TRANSACTION_TYPE_SELL}
    products = {"CNC": kite.PRODUCT_CNC, "MIS": kite.PRODUCT_MIS, "NRML": kite.PRODUCT_NRML}
    varieties = {"REGULAR": kite.VARIETY_REGULAR, "AMO": kite.VARIETY_AMO}

    try:
        best_price = fetch_best_limit_price(kite, exchange, symbol, direction)
        print(f"Best {direction} limit price: {best_price}")
    except Exception as e:
        print(f"Failed to fetch quote: {e}")
        sys.exit(1)

    try:
        response = kite.place_order(
            variety=varieties[args.variety],
            exchange=exchanges[exchange],
            tradingsymbol=symbol,
            transaction_type=directions[direction],
            quantity=quantity,
            product=products[product],
            order_type=kite.ORDER_TYPE_LIMIT,
            price=best_price,
            validity=kite.VALIDITY_DAY,
        )
        # The SDK returns order_id (str). For a full response, we can print order_id and then fetch order info.
        print("Place order response (order_id):", response)
        try:
            # Fetch and print orderbook entry for more details
            orderbook = kite.orders()
            details = [o for o in orderbook if o.get('order_id') == response]
            print("Order details:")
            print(json.dumps(details[0] if details else {}, indent=2, default=str))
        except Exception as e2:
            print(f"Failed to fetch order details: {e2}")
    except Exception as e:
        print(f"Failed to place order: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()


