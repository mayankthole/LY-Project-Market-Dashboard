"""
Sidebar UI components
"""
import streamlit as st
from utils import get_indian_time, clear_credentials, persist_credentials
from api_client import validate_access_token


def render_sidebar(auto_refresh, refresh_interval):
    """Render sidebar with controls and user info"""
    with st.sidebar:
        st.header("⚙️ Dashboard Controls")
        
        # Authentication status
        st.markdown("---")
        st.markdown("**🔐 Authentication**")
        api_key_display = st.session_state.get('api_key', '')
        access_token = st.session_state.get('access_token', '')
        user_profile = st.session_state.get('user_profile', {})
        
        if api_key_display:
            # Show masked API key
            masked_key = api_key_display[:8] + "..." + api_key_display[-4:] if len(api_key_display) > 12 else "***"
            
            # Check token validity
            if access_token:
                is_valid = validate_access_token(api_key_display, access_token)
                if is_valid:
                    st.success(f"✅ Token Valid: {masked_key}")
                    
                    # Display user profile details
                    if user_profile:
                        st.markdown("**👤 User Details:**")
                        user_name = user_profile.get('user_name', 'N/A')
                        user_id = user_profile.get('user_id', 'N/A')
                        email = user_profile.get('email', 'N/A')
                        broker = user_profile.get('broker', 'N/A')
                        user_shortname = user_profile.get('user_shortname', 'N/A')
                        
                        st.markdown(f"**Name:** {user_name}")
                        if user_shortname and user_shortname != user_name:
                            st.markdown(f"**Short Name:** {user_shortname}")
                        st.markdown(f"**User ID:** {user_id}")
                        if email and email != 'N/A':
                            st.markdown(f"**Email:** {email}")
                        st.markdown(f"**Broker:** {broker}")
                        
                        # Show member since if available
                        member_since = user_profile.get('member_since', '')
                        if member_since:
                            st.markdown(f"**Member Since:** {member_since}")
                else:
                    st.error(f"❌ Token Expired: {masked_key}")
                    st.warning("⚠️ Your access token has expired. Please regenerate it.")
                    if st.button("🔄 Regenerate Token", use_container_width=True, type="primary"):
                        # Clear access token to trigger regeneration
                        if 'access_token' in st.session_state:
                            del st.session_state['access_token']
                            persist_credentials()
                        if 'login_url' in st.session_state:
                            del st.session_state['login_url']
                        if 'user_profile' in st.session_state:
                            del st.session_state['user_profile']
                        st.rerun()
            else:
                st.info(f"🔑 API Key: {masked_key}")
        
        if st.button("🚪 Logout", use_container_width=True):
            clear_credentials()
            if 'user_profile' in st.session_state:
                del st.session_state['user_profile']
            st.success("✅ Logged out successfully!")
            st.rerun()
        
        st.markdown("---")
        
        # Auto-refresh settings
        auto_refresh = st.checkbox("🔄 Auto Refresh", value=auto_refresh)
        refresh_interval = st.selectbox(
            "Refresh Interval",
            [30, 60, 120, 300],
            index=[30, 60, 120, 300].index(refresh_interval) if refresh_interval in [30, 60, 120, 300] else 0,
            format_func=lambda x: f"{x} seconds"
        )
        
        # Manual refresh
        if st.button("🔄 Refresh Now", type="primary"):
            st.rerun()
        
        st.markdown("---")
        st.markdown("**Last Updated:**")
        st.info(get_indian_time().strftime('%H:%M:%S IST'))
        
        # Market status
        current_time = get_indian_time()
        market_open = current_time.hour >= 9 and current_time.hour < 17
        market_status = "🟢 Market Open" if market_open else "🔴 Market Closed"
        st.success(market_status)
        
        # Market timings
        st.markdown("**Market Timings:**")
        st.info("9:15 AM - 3:30 PM IST")
        
        return auto_refresh, refresh_interval, market_open

