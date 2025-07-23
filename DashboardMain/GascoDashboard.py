# File: dashboard.py
import streamlit as st
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from Modules.auth import login, register, logout
from Modules.expenses import show_filtered_dashboard

st.set_page_config(page_title="Gasco Dashboard", layout="wide")

# Check if user is already logged in
if 'authentication_status' not in st.session_state:
    st.session_state.authentication_status = None

# Sidebar Menu
st.sidebar.title("Navigation")

# Show logout button and dashboard only if authenticated
if st.session_state.authentication_status:
    st.sidebar.success(f"Welcome *{st.session_state.name}*")

    if st.sidebar.button("Logout"):
        logout()

    # Show dashboard navigation
    selected = st.sidebar.selectbox("Choose View", ["Log Maintenance", "Budget Dashboard"])

    st.write(f"# Welcome *{st.session_state.name}*")
    st.write("You are logged in. Show your dashboard here.")

    
    if selected == "Budget Dashboard":
        show_filtered_dashboard()

# Show login/register options if not authenticated
else:
    choice = st.sidebar.radio("Go to", ["Login", "Register"])

    if choice == "Register":
        register()

    elif choice == "Login":
        result = login()

        # Check if login returned None (e.g. no users)
        if result is None or result == (None, None, None):
            st.info("Please register first or check if users exist.")
        else:
            authenticator, name, authentication_status = result

            if authentication_status == False:
                st.error("Username/password is incorrect")
            elif authentication_status == None:
                st.warning("Please enter your username and password")
            # If authentication is True, Streamlit will rerun and show the dashboard
