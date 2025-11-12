import gspread
from google.oauth2.service_account import Credentials

# Google Sheets setup
scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def test_connection():
    try:
        print("1. Loading service account credentials...")
        creds = Credentials.from_service_account_file(
            'service_account.json',  # Make sure this file exists
            scopes=scopes
        )
        print("✅ Service account loaded successfully")
        
        print("2. Authorizing with gspread...")
        client = gspread.authorize(creds)
        print("✅ gspread authorization successful")
        
        print("3. Opening spreadsheet...")
        spreadsheet = client.open_by_key('1xHoWl9HZdpuRVM9Mh_WLuPeeCd4CZAhIDpoeYVfvHTE')
        print("✅ Spreadsheet opened successfully")
        
        print("4. Accessing Info sheet...")
        info_sheet = spreadsheet.worksheet('Info')
        print("✅ Info sheet accessed successfully")
        
        print("5. Reading cells...")
        api_key = info_sheet.acell('B1').value
        api_secret = info_sheet.acell('B2').value
        access_token = info_sheet.acell('B3').value
        
        print(f"✅ API Key: {api_key[:10]}..." if api_key else "❌ API Key: None")
        print(f"✅ API Secret: {api_secret[:10]}..." if api_secret else "❌ API Secret: None")
        print(f"✅ Access Token: {access_token[:10]}..." if access_token else "❌ Access Token: None")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print(f"Error type: {type(e).__name__}")
        return False

if __name__ == "__main__":
    print("Testing Google Sheets connection...")
    test_connection()