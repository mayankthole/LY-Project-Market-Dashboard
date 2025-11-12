"""
KiteConnect API client wrapper functions
"""
from kiteconnect import KiteConnect
import logging

logger = logging.getLogger(__name__)


def validate_access_token(api_key, access_token):
    """Validate if access token is still valid"""
    if not api_key or not access_token:
        return False
    
    try:
        kite = KiteConnect(api_key=api_key)
        kite.set_access_token(access_token)
        kite.profile()  # Test if token works
        return True
    except Exception as e:
        return False


def generate_login_url(api_key):
    """Generate login URL for Zerodha"""
    try:
        kite = KiteConnect(api_key=api_key)
        login_url = kite.login_url()
        return login_url
    except Exception as e:
        return None


def generate_access_token(api_key, api_secret, request_token):
    """Generate access token from request token"""
    try:
        kite = KiteConnect(api_key=api_key)
        data = kite.generate_session(request_token, api_secret=api_secret)
        access_token = data["access_token"]
        return access_token, None
    except Exception as e:
        return None, str(e)


def is_authenticated():
    """Check if user is authenticated and token is valid"""
    import streamlit as st
    
    api_key = st.session_state.get('api_key', '')
    api_secret = st.session_state.get('api_secret', '')
    access_token = st.session_state.get('access_token', '')
    
    if not api_key or not api_secret or not access_token:
        return False
    
    # Validate access token
    return validate_access_token(api_key, access_token)

