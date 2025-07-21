import streamlit as st
import pandas as pd
import streamlit_authenticator as stauth
import os
import bcrypt

USER_FILE = "Data/users.csv"

def load_users():
    if not os.path.exists(USER_FILE):
        os.makedirs(os.path.dirname(USER_FILE), exist_ok=True)
        df = pd.DataFrame(columns=["name", "username", "password"])
        df.to_csv(USER_FILE, index=False)
    return pd.read_csv(USER_FILE)

def save_user(name, username, password):
    df = load_users()
    # Use bcrypt directly for reliable hashing
    hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    new_user = pd.DataFrame([[name, username, hashed_pw]], columns=["name", "username", "password"])
    df = pd.concat([df, new_user], ignore_index=True)
    df.to_csv(USER_FILE, index=False)

def verify_password(password, hashed):
    """Verify a password against its hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def login():
    users = load_users()
    
    if users.empty:
        st.warning("No users found. Please register first.")
        return None, None, None
    
    # Manual login form
    st.subheader("Login")
    
    # Initialize session state for authentication
    if 'authentication_status' not in st.session_state:
        st.session_state.authentication_status = None
    if 'name' not in st.session_state:
        st.session_state.name = None
    if 'username' not in st.session_state:
        st.session_state.username = None
    
    # Check if already authenticated
    if st.session_state.authentication_status:
        return 'manual_auth', st.session_state.name, st.session_state.authentication_status
    
    # Login form
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        
        if submitted:
            if username and password:
                # Check if user exists
                user_row = users[users['username'] == username]
                if not user_row.empty:
                    stored_password = user_row.iloc[0]['password']
                    if verify_password(password, stored_password):
                        # Successful login
                        st.session_state.authentication_status = True
                        st.session_state.name = user_row.iloc[0]['name']
                        st.session_state.username = username
                        st.success("Login successful!")
                        st.rerun()
                    else:
                        st.session_state.authentication_status = False
                        st.error("Password is incorrect")
                else:
                    st.session_state.authentication_status = False
                    st.error("Username not found")
            else:
                st.error("Please enter both username and password")
    
    return 'manual_auth', st.session_state.name, st.session_state.authentication_status

def logout():
    """Manual logout function"""
    st.session_state.authentication_status = None
    st.session_state.name = None
    st.session_state.username = None
    st.rerun()

def register():
    st.subheader("Register")
    with st.form("RegisterForm"):
        name = st.text_input("Full Name")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Register")
        
        if submit:
            if not name or not username or not password:
                st.error("Please fill in all fields.")
            else:
                df = load_users()
                if username in df["username"].values:
                    st.error("Username already exists.")
                else:
                    save_user(name, username, password)
                    st.success("User registered! You can now log in.")