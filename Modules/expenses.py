import streamlit as st
import pandas as pd
from openpyxl import load_workbook
from datetime import datetime
import plotly.express as px

CURRENT_YEAR = datetime.now().year
EXCEL_PATH = "Data/Budget Monitoring.xlsx"

# Fallback column names (used if Excel doesn't contain consistent headers)
BUDGET_COL = "2025 Budget"
CONSUMED_COL = "Consumed Amount"
AVAILABLE_COL = "Available Amount"

def load_budget_data():
    try:
        df = pd.read_excel(EXCEL_PATH)
        df.columns = df.columns.str.strip()  # Remove extra spaces

        # Force numeric types
        df["2025 Budget"] = pd.to_numeric(df["2025 Budget"], errors="coerce").fillna(0)
        df["Consumed Amount"] = pd.to_numeric(df["Consumed Amount"], errors="coerce").fillna(0)
        df["Available Amount"] = df["2025 Budget"] - df["Consumed Amount"]

        return df
    except Exception as e:
        st.error(f"Failed to load budget data: {e}")
        return pd.DataFrame(columns=[
            "Cost Center Number", "Cost Center Name", "Account number",
            "Account name", "2025 Budget", "Consumed Amount", "Available Amount"
        ])



def append_expense_to_excel(new_data: dict):
    try:
        df = pd.read_excel(EXCEL_PATH)
        df.columns = df.columns.str.strip()
        new_row = pd.DataFrame([new_data])
        df = pd.concat([df, new_row], ignore_index=True)
        df.to_excel(EXCEL_PATH, index=False, engine='openpyxl')
        return True
    except Exception as e:
        st.error(f"Error writing to Excel: {e}")
        return False


def show_filtered_dashboard():
    st.title("📊 Budget Dashboard")

    # ------------------ 🔧 Log Expense ------------------
    with st.expander("➕ Log New Expense", expanded=True):
        with st.form("log_expense_form"):
            col1, col2, col3 = st.columns(3)
            with col1:
                cost_center_number = st.text_input("Cost Center Number")
                account_number = st.text_input("Account Number")
                budget = st.number_input(f"{CURRENT_YEAR} Budget", min_value=0.0, value=0.0)
            with col2:
                cost_center_name = st.text_input("Cost Center Name")
                account_name = st.text_input("Account Name")
                consumed = st.number_input("Consumed Amount", min_value=0.0, value=0.0)
            with col3:
                st.write("")
                st.write("")
                submit = st.form_submit_button("Log Expense")

        if submit:
            available = budget - consumed
            row = {
                "Cost Center Number": cost_center_number,
                "Cost Center Name": cost_center_name,
                "Account number": account_number,
                "Account name": account_name,
                BUDGET_COL: budget,
                CONSUMED_COL: consumed,
                AVAILABLE_COL: available
            }

            success = append_expense_to_excel(row)
            if success:
                st.success("Expense logged and saved.")
            else:
                st.error("Failed to log the expense.")

    # ------------------ 📥 Load Updated Excel ------------------
    df = load_budget_data()
    if df.empty:
        st.warning("No data available to display.")
        return

    # ------------------ 🔢 KPI Summary ------------------
    total_budget = df[BUDGET_COL].sum()
    total_consumed = df[CONSUMED_COL].sum()
    total_remaining = df[AVAILABLE_COL].sum()

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Budget", f"{total_budget:,.0f}")
    col2.metric("Total Consumed", f"{total_consumed:,.0f}")
    col3.metric("Total Remaining", f"{total_remaining:,.0f}")

    st.markdown("---")

    # ------------------ 📊 Charts ------------------
    bar_df = df.groupby("Cost Center Name")[[CONSUMED_COL, AVAILABLE_COL]].sum().reset_index()
    pie_df = df.groupby("Cost Center Name")[BUDGET_COL].sum().reset_index()

    st.subheader("📉 Consumed vs Remaining by Cost Center")
    st.plotly_chart(px.bar(bar_df, x="Cost Center Name", y=[CONSUMED_COL, AVAILABLE_COL],
                           barmode="group", title="Budget Usage"))

    st.subheader("🥧 Budget Breakdown by Cost Center")
    st.plotly_chart(px.pie(pie_df, names="Cost Center Name", values=BUDGET_COL,
                           title="Budget Share"))

    # ------------------ 🎯 Filtered Table View ------------------
    st.subheader("Cost Center Breakdown")
    selected_cc = st.selectbox("Select Cost Center", options=["All"] + sorted(df["Cost Center Name"].unique()))

    if selected_cc != "All":
        filtered = df[df["Cost Center Name"] == selected_cc]
    else:
        filtered = df

    st.dataframe(filtered.reset_index(drop=True), use_container_width=True)

    if selected_cc != "All":
        total_cc_budget = filtered[BUDGET_COL].sum()
        total_cc_consumed = filtered[CONSUMED_COL].sum()
        total_cc_available = filtered[AVAILABLE_COL].sum()

        col1, col2, col3 = st.columns(3)
        col1.metric("Budget", f"{total_cc_budget:,.0f}")
        col2.metric("Consumed", f"{total_cc_consumed:,.0f}")
        col3.metric("Available", f"{total_cc_available:,.0f}")

        # Account-wise Charts
        st.plotly_chart(
            px.bar(filtered, x="Account name", y=[CONSUMED_COL, AVAILABLE_COL],
                   barmode="group", title=f"{selected_cc} - Account-wise Budget Usage")
        )

        st.plotly_chart(
            px.pie(filtered, names="Account name", values=BUDGET_COL,
                   title=f"{selected_cc} - Budget Share by Account")
        )

        # Account-wise Table
        st.dataframe(
            filtered[["Account number", "Account name", CONSUMED_COL, AVAILABLE_COL]].reset_index(drop=True),
            use_container_width=True
        )
