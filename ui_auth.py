"""
Authentication UI components
"""
import streamlit as st
import time
from utils import persist_credentials, clear_credentials
from api_client import generate_login_url, generate_access_token, validate_access_token


def render_auth_ui():
    """Render authentication UI - handles login flow"""
    # Get stored credentials
    stored_api_key = st.session_state.get('api_key', '')
    stored_api_secret = st.session_state.get('api_secret', '')
    stored_access_token = st.session_state.get('access_token', '')
    login_url = st.session_state.get('login_url', '')
    
    # Step 1: Get API Key and Secret
    if not stored_api_key or not stored_api_secret:
        col_left, col_right = st.columns([1, 2])
        
        with col_left:
            st.markdown("### 🔐 Step 1: API Credentials")
        
        with col_right:
            with st.form("api_credentials_form", clear_on_submit=False):
                api_key = st.text_input("API Key", value=stored_api_key, help="Enter your Zerodha API Key", label_visibility="visible")
                api_secret = st.text_input("API Secret", type="password", value=stored_api_secret, help="Enter your Zerodha API Secret", label_visibility="visible")
                
                col1, col2 = st.columns(2)
                with col1:
                    submit_button = st.form_submit_button("➡️ Continue", type="primary", use_container_width=True)
                with col2:
                    clear_button = st.form_submit_button("🗑️ Clear", use_container_width=True)
                
                if submit_button:
                    if api_key and api_secret:
                        st.session_state['api_key'] = api_key
                        st.session_state['api_secret'] = api_secret
                        persist_credentials()
                        st.success("✅ API credentials saved!")
                        st.rerun()
                    else:
                        st.error("❌ Please fill in both fields")
                
                if clear_button:
                    clear_credentials()
                    st.info("🗑️ Credentials cleared")
                    st.rerun()
    
    # Step 2: Generate Login URL and get Request Token
    elif not login_url:
        col_left, col_right = st.columns([1, 2])
        
        with col_left:
            st.markdown("### 🔐 Step 2: Generate Login URL")
        
        with col_right:
            if st.button("🔗 Generate Login URL", type="primary", use_container_width=True):
                api_key = st.session_state.get('api_key', '')
                login_url = generate_login_url(api_key)
                
                if login_url:
                    st.session_state['login_url'] = login_url
                    st.success("✅ Login URL generated!")
                    st.rerun()
                else:
                    st.error("❌ Failed to generate login URL. Please check your API Key.")
            
            st.caption("💡 After generating, click the URL to log in to Zerodha.")
    
    # Step 3: Enter Request Token and Generate Access Token
    elif not stored_access_token or not validate_access_token(stored_api_key, stored_access_token):
        col_left, col_right = st.columns([1, 2])
        
        with col_left:
            st.markdown("### 🔐 Step 3: Generate Access Token")
        
        with col_right:
            login_url = st.session_state.get('login_url', '')
            if login_url:
                st.markdown(f'**🔗 Login URL:** <a href="{login_url}" target="_blank" style="font-size: 12px;">Click here to login</a>', unsafe_allow_html=True)
            
            with st.form("request_token_form", clear_on_submit=False):
                request_token = st.text_input(
                    "Request Token", 
                    help="Copy the 'request_token' from the URL after logging in",
                    label_visibility="visible"
                )
                
                col1, col2 = st.columns(2)
                with col1:
                    generate_button = st.form_submit_button("🔑 Generate Token", type="primary", use_container_width=True)
                with col2:
                    reset_button = st.form_submit_button("🔄 Reset", use_container_width=True)
                
                if generate_button:
                    if request_token:
                        api_key = st.session_state.get('api_key', '')
                        api_secret = st.session_state.get('api_secret', '')
                        
                        with st.spinner("Generating..."):
                            access_token, error = generate_access_token(api_key, api_secret, request_token)
                            
                            if access_token:
                                st.session_state['access_token'] = access_token
                                persist_credentials()
                                st.success("✅ Token generated! Redirecting...")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error(f"❌ Failed: {error}")
                    else:
                        st.error("❌ Please enter the request token")
                
                if reset_button:
                    if 'access_token' in st.session_state:
                        del st.session_state['access_token']
                        persist_credentials()
                    if 'login_url' in st.session_state:
                        del st.session_state['login_url']
                    st.info("🔄 Reset")
                    st.rerun()
            
            with st.expander("📝 How to get Request Token"):
                st.markdown("""
                1. Click the login URL above
                2. Log in to Zerodha
                3. After login, copy the `request_token` from the redirected URL
                4. Paste it above and click "Generate Token"
                """)
    
    # If we have all credentials but token is invalid, show error
    else:
        st.error("❌ Access token expired. Please regenerate.")
        if st.button("🔄 Generate New Token", type="primary"):
            if 'access_token' in st.session_state:
                del st.session_state['access_token']
                persist_credentials()
            if 'login_url' in st.session_state:
                del st.session_state['login_url']
            st.rerun()
    
    st.markdown("---")
    with st.expander("ℹ️ Help & Instructions"):
        st.caption("💡 Access tokens expire daily. Regenerate when needed.")
        st.caption("📝 Get API Key/Secret from: https://kite.trade/apps/")
    st.stop()

