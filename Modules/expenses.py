import streamlit as st
import pandas as pd
import os

LOG_FILE = "Data/maintenance_log.csv"

def load_maintenance_data():
    if not os.path.exists(LOG_FILE) or os.path.getsize(LOG_FILE) == 0:
        df = pd.DataFrame(columns=["date", "description", "cost", "type"])
        df.to_csv(LOG_FILE, index=False)
    return pd.read_csv(LOG_FILE)

def save_maintenance_entry(date, description, cost, maint_type):
    df = load_maintenance_data()
    new_entry = pd.DataFrame([[date, description, cost, maint_type]], columns=["date", "description", "cost", "type"])
    df = pd.concat([df, new_entry], ignore_index=True)
    df.to_csv(LOG_FILE, index=False)

def maintenance_log_ui():
    st.subheader("✍️ Expense Log Entry")
    with st.form("Expense Form"):
        date = st.date_input("Date")
        description = st.text_input("Description")
        cost = st.number_input("Cost (EGP)", min_value=0.0)
        maint_type = st.selectbox("Type", ["Routine", "Emergency", "Upgrade"])
        submitted = st.form_submit_button("Add Entry")
        if submitted:
            save_maintenance_entry(date, description, cost, maint_type)
            st.success("✅ Log saved successfully!")

import plotly.express as px

def show_filtered_dashboard():
    st.subheader("🔍 Filter Logs")
    df = load_maintenance_data()

    if df.empty:
        st.info("No data to display yet.")
        return

    df['date'] = pd.to_datetime(df['date'])

   
    with st.expander("Filter"):
        col1, col2, col3 = st.columns(3)

        with col1:
            start_date = st.date_input("Start Date", value=df['date'].min().date())
        with col2:
            end_date = st.date_input("End Date", value=df['date'].max().date())
        with col3:
            type_options = df['type'].unique().tolist()
            maint_type_filter = st.multiselect("Maintenance Type", options=type_options, default=type_options)

        # Optional search field
        search_term = st.text_input("🔍 Search Description")

    # Apply filters
    filtered_df = df[
        (df['date'] >= pd.to_datetime(start_date)) &
        (df['date'] <= pd.to_datetime(end_date)) &
        (df['type'].isin(maint_type_filter))
    ]

    if search_term:
        filtered_df = filtered_df[filtered_df['description'].str.contains(search_term, case=False, na=False)]

    st.write("### 📋 Filtered Maintenance Log")
    st.dataframe(filtered_df)

    if not filtered_df.empty:
        # Pie chart
        st.write("### 📊 Maintenance Type Distribution")
        pie_chart = px.pie(filtered_df, names='type', title="Maintenance Type Distribution")
        st.plotly_chart(pie_chart)

        # Line chart: monthly trend
        st.write("### 📈 Monthly Expense Trend")
        monthly_summary = (
            filtered_df.groupby(filtered_df['date'].dt.to_period('M'))['cost']
            .sum().reset_index()
        )
        monthly_summary['date'] = monthly_summary['date'].astype(str)
        line_chart = px.line(monthly_summary, x='date', y='cost', title='Monthly Maintenance Costs', markers=True)
        st.plotly_chart(line_chart)

        # Summary
        st.metric("Total Filtered Cost", f"{filtered_df['cost'].sum():.2f} EGP")
    else:
        st.warning("No results match the applied filters.")
