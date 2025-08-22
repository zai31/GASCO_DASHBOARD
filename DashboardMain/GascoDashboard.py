# File: dashboard.py
import streamlit as st
import sys
import os

# Add parent path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from Modules.auth import login, register, logout
from Modules.expenses import show_filtered_dashboard, show_optimizer_dashboard

st.set_page_config(page_title="Gasco Dashboard", layout="wide")

# --- Session setup ---
if 'authentication_status' not in st.session_state:
    st.session_state.authentication_status = None

# Sidebar Menu
st.sidebar.title("Navigation")

# --- Authenticated user flow ---
if st.session_state.authentication_status:
    st.sidebar.success(f"Welcome *{st.session_state.name}*")

    if st.sidebar.button("Logout"):
        logout()

    # Navigation after login
    choice = st.sidebar.radio("Go to:", ["Budget Dashboard", "Compressor Optimization"])

    st.write(f"# Welcome *{st.session_state.name}*")

    if choice == "Budget Dashboard":
        show_filtered_dashboard()
    elif choice == "Compressor Optimization":
        show_optimizer_dashboard()

   

# --- Not logged in yet ---
else:
    choice = st.sidebar.radio("Go to", ["Login", "Register"])

    if choice == "Register":
        register()

    elif choice == "Login":
        result = login()

        if result is None or result == (None, None, None):
            st.info("Please register first or check if users exist.")
        else:
            authenticator, name, authentication_status = result

            if authentication_status is False:
                st.error("Username/password is incorrect")
            elif authentication_status is None:
                st.warning("Please enter your username and password")
