"""
Utility functions for formatting, time, and credentials management
"""
import streamlit as st
import pandas as pd
import pytz
import json
import os
import logging

from datetime import datetime
from config import CREDENTIALS_FILE

logger = logging.getLogger(__name__)

# Indian timezone
IST = pytz.timezone('Asia/Kolkata')


def get_indian_time():
    """Get current Indian time"""
    return datetime.now(IST)


def format_currency(value):
    """Format currency value with appropriate units"""
    if pd.isna(value) or value is None:
        return "₹0"
    if abs(value) >= 10000000:
        return f"₹{value/10000000:.2f}Cr"
    elif abs(value) >= 100000:
        return f"₹{value/100000:.2f}L"
    else:
        return f"₹{value:,.2f}"


def get_credentials():
    """Get credentials from session state"""
    api_key = st.session_state.get('api_key', '')
    api_secret = st.session_state.get('api_secret', '')
    access_token = st.session_state.get('access_token', '')
    
    return api_key, api_secret, access_token


def load_persisted_credentials():
    """Load credentials from persistent storage into session state."""
    if st.session_state.get('_credentials_loaded', False):
        return
    
    try:
        with open(CREDENTIALS_FILE, 'r') as file:
            data = json.load(file)
    except FileNotFoundError:
        st.session_state['_credentials_loaded'] = True
        return
    except json.JSONDecodeError:
        logger.warning("Credentials file is corrupted. Ignoring stored credentials.")
        st.session_state['_credentials_loaded'] = True
        return
    
    for key in ['api_key', 'api_secret', 'access_token']:
        if key not in st.session_state and data.get(key):
            st.session_state[key] = data.get(key)
    
    st.session_state['_credentials_loaded'] = True


def persist_credentials():
    """Persist current credentials to disk."""
    data = {
        'api_key': st.session_state.get('api_key', ''),
        'api_secret': st.session_state.get('api_secret', ''),
        'access_token': st.session_state.get('access_token', '')
    }
    
    # Avoid writing empty files if everything is blank
    if not any(data.values()):
        if os.path.exists(CREDENTIALS_FILE):
            try:
                os.remove(CREDENTIALS_FILE)
            except OSError as exc:
                logger.warning(f"Unable to remove credentials file: {exc}")
        return
    
    try:
        with open(CREDENTIALS_FILE, 'w') as file:
            json.dump(data, file)
    except OSError as exc:
        logger.error(f"Failed to persist credentials: {exc}")


def clear_credentials():
    """Clear stored credentials"""
    if 'api_key' in st.session_state:
        del st.session_state['api_key']
    if 'api_secret' in st.session_state:
        del st.session_state['api_secret']
    if 'access_token' in st.session_state:
        del st.session_state['access_token']
    if 'login_url' in st.session_state:
        del st.session_state['login_url']
    if os.path.exists(CREDENTIALS_FILE):
        try:
            os.remove(CREDENTIALS_FILE)
        except OSError as exc:
            logger.warning(f"Unable to delete credentials file: {exc}")


def skip_next_auto_refresh():
    """Flag to skip the auto refresh sleep/rerun for the current interaction."""
    st.session_state['skip_auto_refresh'] = True

