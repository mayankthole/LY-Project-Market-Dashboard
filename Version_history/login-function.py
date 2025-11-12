import logging
from kiteconnect import KiteConnect
import pandas as pd
import os
import datetime
import numpy as np
import time

logging.basicConfig(level=logging.INFO)

api_key = "qj4khkfuzvwgbt4w"
api_secret = "cg70gpdtl83lqxjee0hassoc3hup48rk"
access_token_file = "access_token.txt"

kite = KiteConnect(api_key=api_key)

def set_access_token_from_file():
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

if not set_access_token_from_file():
    print("Login URL:", kite.login_url())
    request_token = input("Enter the request_token from the URL: ")
    data = kite.generate_session(request_token, api_secret=api_secret)
    access_token = data["access_token"]
    kite.set_access_token(access_token)
    with open(access_token_file, "w") as f:
        f.write(access_token)
    logging.info("Access token saved to access_token.txt")
# Load instruments.csv, refresh if older than 12 hours
def get_instrument_list(local_file="instruments.csv", url="https://api.kite.trade/instruments", max_age_hours=12):
    if os.path.exists(local_file):
        file_age = (time.time() - os.path.getmtime(local_file)) / 3600
        if file_age < max_age_hours:
            logging.info(f"Using cached instruments file ({local_file}), age: {file_age:.2f} hours.")
            return pd.read_csv(local_file)
        else:
            logging.info(f"Cached instruments file is older than {max_age_hours} hours. Downloading new file...")
    else:
        logging.info("No cached instruments file found. Downloading new file...")
    df = pd.read_csv(url)
    df.to_csv(local_file, index=False)
    return df

# Use the function to load instruments
instruments = get_instrument_list()
