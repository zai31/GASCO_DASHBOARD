import streamlit as st
import re
import pandas as pd
from openpyxl import load_workbook
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io
import base64
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import (
    SimpleDocDocument, Paragraph, Spacer, Table, TableStyle, Image,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import os

# CONSTANTS - Updated to match your Excel structure
CURRENT_YEAR = datetime.now().year
EXCEL_PATH = "Data/Budget Monitoring.xlsx"

# Updated to match your actual Excel columns
BUDGET_COLUMNS = {
    "2023": "2023 Budget", 
    "2024": "2024 Budget", 
    "2025": "2025 Budget"
}

CONSUMED_COLUMNS = {
    "2023": "2023 Consumed",
    "2024": "2024 Consumed", 
    "2025": "2025 Consumed",
}

# Use the current year's consumed column as the main consumed column
CONSUMED_COL = "2025 Consumed"  # Changed from "Consumed Amount"
AVAILABLE_COL = "Available Amount"


def detect_year_columns(df):
    """Dynamically detect budget and consumed columns by year"""
    budget_cols = {}
    consumed_cols = {}

    for col in df.columns:
        # Match budget columns (YYYY Budget)
        match = re.match(r"(\d{4})\s+Budget", col)
        if match:
            year = match.group(1)
            budget_cols[year] = col

        # Match consumed columns (YYYY Consumed)
        match = re.match(r"(\d{4})\s+Consumed", col)
        if match:
            year = match.group(1)
            consumed_cols[year] = col

    return budget_cols, consumed_cols


def get_available_years(df):
    """Get all available years from the dataset"""
    budget_cols, consumed_cols = detect_year_columns(df)
    all_years = set(budget_cols.keys()) | set(consumed_cols.keys())
    return sorted(list(all_years), reverse=True)


def get_quarter_from_date(date):
    """Extract quarter from date"""
    if pd.isna(date):
        return None
    month = date.month
    if month <= 3:
        return "Q1"
    elif month <= 6:
        return "Q2"
    elif month <= 9:
        return "Q3"
    else:
        return "Q4"


def get_year_from_date(date):
    """Extract year from date"""
    if pd.isna(date):
        return None
    return date.year


@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_budget_data():
    """Load and process budget data with enhanced error handling"""
    try:
        df = pd.read_excel(EXCEL_PATH)
        df.columns = df.columns.str.strip()
        
        # Dynamically detect year columns
        budget_cols, consumed_cols = detect_year_columns(df)
        
        # Force numeric for all detected budget & consumed columns
        numeric_columns = list(budget_cols.values()) + list(consumed_cols.values()) + [AVAILABLE_COL]
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

        # Calculate Available Amount if missing
        if AVAILABLE_COL not in df.columns:
            current_year_str = str(CURRENT_YEAR)
            current_consumed_col = consumed_cols.get(current_year_str, "2025 Consumed")
            current_budget_col = budget_cols.get(current_year_str, "2025 Budget")
            
            if current_budget_col in df.columns and current_consumed_col in df.columns:
                df[AVAILABLE_COL] = df[current_budget_col] - df[current_consumed_col]
            else:
                df[AVAILABLE_COL] = 0

        # Process dates
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
            df["Date"].fillna(pd.Timestamp.now(), inplace=True)
            df["Quarter"] = df["Date"].apply(get_quarter_from_date)
            df["Year"] = df["Date"].apply(get_year_from_date)
        else:
            current_date = pd.Timestamp.now()
            df["Date"] = current_date
            df["Quarter"] = get_quarter_from_date(current_date)
            df["Year"] = current_date.year

        # Create display columns
        if "Cost Center Number" in df.columns and "Cost Center Name" in df.columns:
            df["Cost Center Number"] = df["Cost Center Number"].astype(str).str.strip()
            df["Cost Center Name"] = df["Cost Center Name"].astype(str).str.strip()
            df["Cost Center Display"] = df["Cost Center Number"] + " - " + df["Cost Center Name"]

        if "Account number" in df.columns and "Account name" in df.columns:
            df["Account number"] = df["Account number"].astype(str).str.strip()
            df["Account name"] = df["Account name"].astype(str).str.strip()
            df["Account Display"] = df["Account number"] + " - " + df["Account name"]

        # Remove rows with missing critical data
        critical_cols = ["Cost Center Name", "Account name"]
        for col in critical_cols:
            if col in df.columns:
                df = df.dropna(subset=[col])

        # Extract unique values
        cost_center_names = sorted(df["Cost Center Name"].dropna().unique()) if "Cost Center Name" in df.columns else []
        cost_center_numbers = sorted(df["Cost Center Number"].dropna().unique()) if "Cost Center Number" in df.columns else []
        account_names = sorted(df["Account name"].dropna().unique()) if "Account name" in df.columns else []
        account_numbers = sorted(df["Account number"].dropna().unique()) if "Account number" in df.columns else []

        return df, cost_center_names, cost_center_numbers, account_names, account_numbers

    except FileNotFoundError:
        st.error(f"Excel file not found at {EXCEL_PATH}")
        return pd.DataFrame(), [], [], [], []
    except Exception as e:
        st.error(f"Failed to load budget data: {e}")
        return pd.DataFrame(), [], [], [], []


def improved_append_expense_to_excel(new_data: dict):
    """Enhanced expense logging with better validation"""
    try:
        df = pd.read_excel(EXCEL_PATH)
        df.columns = df.columns.str.strip()

        # Check for similar entries
        duplicate_check = df[
            (df["Cost Center Number"].astype(str) == str(new_data["Cost Center Number"])) &
            (df["Account number"].astype(str) == str(new_data["Account number"])) &
            (pd.to_datetime(df["Date"]).dt.date == new_data["Date"])
        ]

        if not duplicate_check.empty:
            # Update existing entry
            idx = duplicate_check.index[0]
            for key, value in new_data.items():
                if key in df.columns:
                    df.at[idx, key] = value
            st.info("Updated existing expense entry for this date.")
        else:
            # Add new entry
            new_row = pd.DataFrame([new_data])
            df = pd.concat([df, new_row], ignore_index=True)

        # Save back to Excel
        df.to_excel(EXCEL_PATH, index=False, engine="openpyxl")
        return True

    except Exception as e:
        st.error(f"Error updating expense data: {e}")
        return False


def show_filtered_dashboard():
    """Main dashboard function"""
    st.title("Budget Dashboard")

    # Load data
    df, cost_center_names, cost_center_numbers, account_names, account_numbers = load_budget_data()
    
    if df.empty:
        st.warning("No data available to display.")
        st.info("Please ensure your Excel file exists at: " + EXCEL_PATH)
        return

    # Get dynamic year columns
    budget_cols, consumed_cols = detect_year_columns(df)
    available_years = get_available_years(df)

    # Display data info
    with st.expander("Dataset Information", expanded=False):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Records", len(df))
        with col2:
            st.metric("Cost Centers", len(cost_center_names))
        with col3:
            st.metric("Accounts", len(account_names))
        with col4:
            st.metric("Budget Years", len(budget_cols))

    # Enhanced Expense Logging Section
    with st.expander("Log New Expense", expanded=True):
        if "Cost Center Display" in df.columns and not df.empty:
            cost_center_options = sorted(df["Cost Center Display"].dropna().unique())

            if cost_center_options:
                selected_cc_display = st.selectbox(
                    "Select Cost Center",
                    cost_center_options,
                    key="cost_center_selector",
                )

                cc_rows = df[df["Cost Center Display"] == selected_cc_display]
                if not cc_rows.empty:
                    selected_cc_number = cc_rows["Cost Center Number"].iloc[0]
                    selected_cc_name = cc_rows["Cost Center Name"].iloc[0]
                    filtered_acc_displays = cc_rows["Account Display"].dropna().unique().tolist()
                    
                    if filtered_acc_displays:
                        with st.form("log_expense_form_main"):
                            selected_acc_display = st.selectbox(
                                "Select Account",
                                sorted(filtered_acc_displays),
                                key="account_display_selector",
                            )
                            
                            acc_row = cc_rows[cc_rows["Account Display"] == selected_acc_display].iloc[0]
                            selected_acc_number = acc_row["Account number"]
                            selected_acc_name = acc_row["Account name"]
                            
                            expense_date = st.date_input("Expense Date", value=datetime.now())
                            
                            # Find matching record
                            match = df[
                                (df["Cost Center Number"] == selected_cc_number) &
                                (df["Cost Center Name"] == selected_cc_name) &
                                (df["Account name"] == selected_acc_name) &
                                (df["Account number"] == selected_acc_number)
                            ]
                            
                            if not match.empty:
                                # Get budget information for current year
                                current_year_str = str(CURRENT_YEAR)
                                budget_col = budget_cols.get(current_year_str, "2025 Budget")
                                consumed_col = consumed_cols.get(current_year_str, "2025 Consumed")
                                
                                if budget_col in match.columns:
                                    budget_amount = match[budget_col].iloc[0]
                                    consumed_before = match[consumed_col].iloc[0] if consumed_col in match.columns else 0
                                    available_before = match[AVAILABLE_COL].iloc[0] if AVAILABLE_COL in match.columns else budget_amount
                                    
                                    # Display current status
                                    st.markdown("**Current Budget Status:**")
                                    col1, col2, col3 = st.columns(3)
                                    with col1:
                                        st.metric(f"{current_year_str} Budget", f"${budget_amount:,.2f}")
                                    with col2:
                                        st.metric("Consumed", f"${consumed_before:,.2f}")
                                    with col3:
                                        st.metric("Available", f"${available_before:,.2f}")
                                    
                                    # Expense input
                                    consumed_now = st.number_input(
                                        "New Expense Amount",
                                        min_value=0.0,
                                        step=0.01,
                                        help="Enter the amount you want to log as consumed",
                                    )
                                    
                                    # Calculate impact
                                    if consumed_now > 0:
                                        new_consumed_total = consumed_before + consumed_now
                                        available_after = budget_amount - new_consumed_total
                                        
                                        st.markdown("**After This Expense:**")
                                        col1a, col2a = st.columns(2)
                                        with col1a:
                                            st.write(f"**Total Consumed:** ${new_consumed_total:,.2f}")
                                        with col2a:
                                            st.write(f"**Available:** ${available_after:,.2f}")
                                        
                                        if available_after < 0:
                                            st.error("This expense will exceed the available budget!")
                                        elif available_after < (budget_amount * 0.1):
                                            st.warning("Low budget remaining!")
                                    
                                    # Form submission
                                    submit = st.form_submit_button("Log Expense", type="primary")
                                    
                                    if submit and consumed_now > 0:
                                        try:
                                            new_consumed_total = consumed_before + consumed_now
                                            available_after = budget_amount - new_consumed_total
                                            
                                            # Get all budget values for different years
                                            budget_values = {}
                                            for year, col in budget_cols.items():
                                                budget_values[col] = match[col].iloc[0] if col in match.columns else 0
                                            
                                            # Get all consumed values
                                            consumed_values = {}
                                            for year, col in consumed_cols.items():
                                                if year == current_year_str:
                                                    consumed_values[col] = new_consumed_total
                                                else:
                                                    consumed_values[col] = match[col].iloc[0] if col in match.columns else 0
                                            
                                            row_data = {
                                                "Cost Center Number": selected_cc_number,
                                                "Cost Center Name": selected_cc_name,
                                                "Account number": selected_acc_number,
                                                "Account name": selected_acc_name,
                                                "Date": expense_date,
                                                "Quarter": get_quarter_from_date(expense_date),
                                                "Year": expense_date.year,
                                                AVAILABLE_COL: available_after,
                                                **budget_values,
                                                **consumed_values
                                            }
                                            
                                            success = improved_append_expense_to_excel(row_data)
                                            if success:
                                                st.success("Expense logged successfully!")
                                                st.balloons()
                                                st.rerun()
                                            else:
                                                st.error("Failed to log expense.")
                                                
                                        except Exception as e:
                                            st.error(f"Error logging expense: {str(e)}")
                                    
                                    elif submit and consumed_now <= 0:
                                        st.warning("Please enter an expense amount greater than 0.")
                                else:
                                    st.error("No budget column found for current year")
                            else:
                                st.error("No matching record found.")

    # Analytics Section
    st.markdown("---")
    tab1, tab2 = st.tabs(["Analysis Dashboard", "Summary & Insights"])
    
    with tab1:
        show_analysis_dashboard(df, budget_cols, consumed_cols, available_years, cost_center_names, account_names)
    
    with tab2:
        show_summary_tab(df)


def show_analysis_dashboard(df, budget_cols, consumed_cols, available_years, cost_center_names, account_names):
    """Analysis dashboard with dynamic year support"""
    st.subheader("Filters")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        time_period = st.selectbox(
            "Time Period Type",
            options=["Annual", "Quarterly"],
            help="Choose analysis type"
        )
    
    with col2:
        if time_period == "Annual":
            selected_years = st.multiselect(
                "Select Years",
                options=available_years,
                default=available_years[:3] if len(available_years) >= 3 else available_years,
                help="Choose years to compare"
            )
        else:
            if available_years:
                selected_year = st.selectbox(
                    "Select Year",
                    options=available_years,
                    index=0
                )
                selected_quarters = st.multiselect(
                    "Select Quarters",
                    options=["Q1", "Q2", "Q3", "Q4"],
                    default=["Q1", "Q2", "Q3", "Q4"]
                )
            else:
                selected_year = None
                selected_quarters = []
    
    with col3:
        cc_options = ["All"] + cost_center_names
        selected_ccs = st.multiselect(
            "Cost Centers",
            options=cc_options,
            default=["All"]
        )

    # Filter data
    filtered_df = df.copy()
    
    if "All" not in selected_ccs and selected_ccs:
        filtered_df = filtered_df[filtered_df["Cost Center Name"].isin(selected_ccs)]

    st.markdown("---")

    # Generate visualizations based on time period
    if time_period == "Annual" and selected_years:
        show_annual_analysis(filtered_df, budget_cols, consumed_cols, selected_years)
    elif time_period == "Quarterly" and selected_quarters and selected_year:
        show_quarterly_analysis(filtered_df, budget_cols, selected_year, selected_quarters)

    # Data table
    st.subheader("Filtered Data")
    display_columns = ["Cost Center Name", "Account name", "Date", "Quarter", AVAILABLE_COL]
    
    # Add selected year columns
    if time_period == "Annual":
        for year in selected_years:
            if year in budget_cols:
                display_columns.extend([budget_cols[year]])
            if year in consumed_cols:
                display_columns.extend([consumed_cols[year]])
    else:
        if selected_year and selected_year in budget_cols:
            display_columns.extend([budget_cols[selected_year]])
        if selected_year and selected_year in consumed_cols:
            display_columns.extend([consumed_cols[selected_year]])
    
    # Filter columns that exist
    display_columns = [col for col in display_columns if col in filtered_df.columns]
    
    if display_columns:
        st.dataframe(filtered_df[display_columns], use_container_width=True)


def show_annual_analysis(df, budget_cols, consumed_cols, selected_years):
    """Show annual analysis"""
    st.subheader("Annual Analysis")
    
    # Prepare annual data
    annual_data = []
    for year in selected_years:
        if year in budget_cols:
            budget_col = budget_cols[year]
            consumed_col = consumed_cols.get(year, CONSUMED_COL)
            
            year_summary = df.groupby("Cost Center Name").agg({
                budget_col: "sum",
                consumed_col: "sum" if consumed_col in df.columns else lambda x: 0
            }).reset_index()
            
            year_summary["Year"] = year
            year_summary.rename(columns={
                budget_col: "Budget",
                consumed_col: "Consumed"
            }, inplace=True)
            
            annual_data.append(year_summary)
    
    if annual_data:
        annual_df = pd.concat(annual_data, ignore_index=True)
        
        # Budget comparison chart
        fig = px.bar(
            annual_df,
            x="Year",
            y="Budget",
            color="Cost Center Name" if len(annual_df["Cost Center Name"].unique()) > 1 else None,
            title="Annual Budget Comparison",
            barmode="group"
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Trend analysis
        trend_data = annual_df.groupby("Year")[["Budget", "Consumed"]].sum().reset_index()
        
        fig3 = px.line(
            trend_data,
            x="Year",
            y=["Budget", "Consumed"],
            title="Budget and Consumption Trends",
            markers=True
        )
        st.plotly_chart(fig3, use_container_width=True)


def show_quarterly_analysis(df, budget_cols, selected_year, selected_quarters):
    """Show quarterly analysis"""
    st.subheader(f"{selected_year} Quarterly Analysis")
    
    if selected_year in budget_cols:
        budget_col = budget_cols[selected_year]
        consumed_col = consumed_cols.get(selected_year, CONSUMED_COL)
        
        quarter_filtered = df[
            (df["Year"] == int(selected_year)) &
            (df["Quarter"].isin(selected_quarters))
        ]
        
        if not quarter_filtered.empty:
            # Quarterly summary
            quarterly_summary = quarter_filtered.groupby("Quarter").agg({
                budget_col: "sum",
                consumed_col: "sum" if consumed_col in quarter_filtered.columns else lambda x: 0
            }).reset_index()
            
            fig = px.bar(
                quarterly_summary,
                x="Quarter",
                y=[budget_col, consumed_col],
                title=f"{selected_year} Quarterly Budget vs Consumed",
                barmode="group"
            )
            st.plotly_chart(fig, use_container_width=True)


def show_summary_tab(df):
    """Enhanced summary tab"""
    st.subheader("Summary & Insights")
    
    budget_cols, consumed_cols = detect_year_columns(df)
    available_years = sorted(budget_cols.keys(), reverse=True)
    
    if not available_years:
        st.warning("No budget data available for analysis")
        return
    
    # Current year metrics
    current_year = available_years[0]
    current_budget_col = budget_cols[current_year]
    current_consumed_col = consumed_cols.get(current_year, CONSUMED_COL)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_budget = df[current_budget_col].sum()
        st.metric(f"{current_year} Total Budget", f"${total_budget:,.0f}")
    
    with col2:
        total_consumed = df[current_consumed_col].sum() if current_consumed_col in df.columns else 0
        st.metric("Total Consumed", f"${total_consumed:,.0f}")
    
    with col3:
        total_available = df[AVAILABLE_COL].sum()
        st.metric("Total Available", f"${total_available:,.0f}")
    
    with col4:
        utilization = (total_consumed / total_budget * 100) if total_budget > 0 else 0
        st.metric("Utilization Rate", f"{utilization:.1f}%")

    st.markdown("---")

    # Top performers
    st.subheader("Top Performers")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Top Cost Centers by Budget:**")
        top_cc = df.groupby("Cost Center Name")[current_budget_col].sum().sort_values(ascending=False).head(5)
        for i, (cc, budget) in enumerate(top_cc.items(), 1):
            st.write(f"{i}. {cc}: ${budget:,.0f}")
    
    with col2:
        st.write("**Top Accounts by Budget:**")
        top_accounts = df.groupby("Account name")[current_budget_col].sum().sort_values(ascending=False).head(5)
        for i, (account, budget) in enumerate(top_accounts.items(), 1):
            st.write(f"{i}. {account}: ${budget:,.0f}")

    # Budget distribution charts
    st.markdown("---")
    st.subheader("Budget Distribution")
    
    col1, col2 = st.columns(2)
    
    with col1:
        cc_distribution = df.groupby("Cost Center Name")[current_budget_col].sum()
        fig = px.pie(
            values=cc_distribution.values,
            names=cc_distribution.index,
            title="Budget by Cost Center"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        account_dist = df.groupby("Account name")[current_budget_col].sum().head(10)
        fig = px.pie(
            values=account_dist.values,
            names=account_dist.index,
            title="Top 10 Accounts by Budget"
        )
        st.plotly_chart(fig, use_container_width=True)

def generate_report(df):
    """Generate a comprehensive PDF report"""
    try:
        # Create a buffer for the PDF
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        story = []
        styles = getSampleStyleSheet()

        # Title
        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Heading1"],
            fontSize=24,
            spaceAfter=30,
            alignment=1,  # Center alignment
        )
        story.append(
            Paragraph(f"GASCO Budget Analysis Report - {CURRENT_YEAR}", title_style)
        )
        story.append(Spacer(1, 20))

        # Executive Summary
        story.append(Paragraph("Executive Summary", styles["Heading2"]))
        story.append(Spacer(1, 12))

        # Key metrics
        total_budget_2025 = df["2025 Budget"].sum()
        total_consumed = df[CONSUMED_COL].sum()
        total_available = df[AVAILABLE_COL].sum()
        utilization_rate = (
            (total_consumed / total_budget_2025 * 100) if total_budget_2025 > 0 else 0
        )

        summary_text = f"""
        <b>Key Metrics:</b><br/>
        • Total Budget ({CURRENT_YEAR}): {total_budget_2025:,.0f}<br/>
        • Total Consumed: {total_consumed:,.0f}<br/>
        • Total Available: {total_available:,.0f}<br/>
        • Utilization Rate: {utilization_rate:.1f}%<br/>
        • Total Cost Centers: {df["Cost Center Name"].nunique()}<br/>
        • Total Accounts: {df["Account name"].nunique()}<br/>
        • Total Records: {len(df)}
        """
        story.append(Paragraph(summary_text, styles["Normal"]))
        story.append(Spacer(1, 20))

        # Top Performers
        story.append(Paragraph("Top Performers", styles["Heading2"]))
        story.append(Spacer(1, 12))

        # Top cost centers
        top_cc = (
            df.groupby("Cost Center Name")["2025 Budget"]
            .sum()
            .sort_values(ascending=False)
            .head(5)
        )
        cc_text = "<b>Top 5 Cost Centers by Budget:</b><br/>"
        for i, (cc, budget) in enumerate(top_cc.items(), 1):
            cc_text += f"{i}. {cc}: {budget:,.0f}<br/>"
        story.append(Paragraph(cc_text, styles["Normal"]))
        story.append(Spacer(1, 12))

        # Top accounts
        top_accounts = (
            df.groupby("Account name")["2025 Budget"]
            .sum()
            .sort_values(ascending=False)
            .head(5)
        )
        account_text = "<b>Top 5 Accounts by Budget:</b><br/>"
        for i, (account, budget) in enumerate(top_accounts.items(), 1):
            account_text += f"{i}. {account}: {budget:,.0f}<br/>"
        story.append(Paragraph(account_text, styles["Normal"]))
        story.append(Spacer(1, 20))

        # Year-over-Year Analysis
        story.append(Paragraph("Year-over-Year Analysis", styles["Heading2"]))
        story.append(Spacer(1, 12))

        total_2023 = df["2023 Budget"].sum()
        total_2024 = df["2024 Budget"].sum()
        total_2025 = df["2025 Budget"].sum()

        growth_2024 = (
            ((total_2024 - total_2023) / total_2023 * 100) if total_2023 > 0 else 0
        )
        growth_2025 = (
            ((total_2025 - total_2024) / total_2024 * 100) if total_2024 > 0 else 0
        )

        yoy_text = f"""
        <b>Budget Trends:</b><br/>
        • 2023 Total: {total_2023:,.0f}<br/>
        • 2024 Total: {total_2024:,.0f}<br/>
        • 2025 Total: {total_2025:,.0f}<br/>
        • 2024 Growth: {growth_2024:+.1f}%<br/>
        • 2025 Growth: {growth_2025:+.1f}%<br/>
        • 3-Year CAGR: {((total_2025/total_2023)**(1/2)-1)*100:.1f}%
        """
        story.append(Paragraph(yoy_text, styles["Normal"]))
        story.append(Spacer(1, 20))

        # Quarterly Analysis (if available)
        if "Quarter" in df.columns:
            story.append(Paragraph("Quarterly Analysis", styles["Heading2"]))
            story.append(Spacer(1, 12))

            quarterly_summary = (
                df.groupby("Quarter")
                .agg(
                    {
                        "2025 Budget": "sum",
                        "Cost Center Name": "nunique",
                        "Account name": "nunique",
                    }
                )
                .round(0)
            )

            # Create quarterly table
            q_data = [["Quarter", "Total Budget", "Cost Centers", "Accounts"]]
            for quarter in ["Q1", "Q2", "Q3", "Q4"]:
                if quarter in quarterly_summary.index:
                    row = quarterly_summary.loc[quarter]
                    q_data.append(
                        [
                            quarter,
                            f"{row['2025 Budget']:,.0f}",
                            str(row["Cost Center Name"]),
                            str(row["Account name"]),
                        ]
                    )

            q_table = Table(q_data)
            q_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, 0), 12),
                        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                        ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                        ("GRID", (0, 0), (-1, -1), 1, colors.black),
                    ]
                )
            )
            story.append(q_table)
            story.append(Spacer(1, 20))

        # Cost Center Breakdown
        story.append(Paragraph("Cost Center Breakdown", styles["Heading2"]))
        story.append(Spacer(1, 12))

        cc_breakdown = (
            df.groupby("Cost Center Name")
            .agg({"2025 Budget": "sum", CONSUMED_COL: "sum", AVAILABLE_COL: "sum"})
            .round(0)
        )

        # Create cost center table
        cc_data = [["Cost Center", "Budget", "Consumed", "Available", "Utilization %"]]
        for cc in cc_breakdown.index:
            row = cc_breakdown.loc[cc]
            utilization = (
                (row[CONSUMED_COL] / row["2025 Budget"] * 100)
                if row["2025 Budget"] > 0
                else 0
            )
            cc_data.append(
                [
                    cc,
                    f"{row['2025 Budget']:,.0f}",
                    f"{row[CONSUMED_COL]:,.0f}",
                    f"{row[AVAILABLE_COL]:,.0f}",
                    f"{utilization:.1f}%",
                ]
            )

        cc_table = Table(cc_data)
        cc_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                    ("FONTSIZE", (0, 1), (-1, -1), 8),
                ]
            )
        )
        story.append(cc_table)
        story.append(Spacer(1, 20))

        # Key Insights
        story.append(Paragraph("Key Insights & Recommendations", styles["Heading2"]))
        story.append(Spacer(1, 12))

        insights = []
        if utilization_rate > 80:
            insights.append(
                "• High utilization rate indicates effective budget management"
            )
        elif utilization_rate > 60:
            insights.append(
                "• Moderate utilization rate - consider optimizing budget allocation"
            )
        else:
            insights.append(
                "• Low utilization rate - review budget allocation strategy"
            )

        if growth_2025 > 0:
            insights.append("• Budget growth indicates expanding operations")
        else:
            insights.append("• Budget reduction suggests cost optimization efforts")

        if len(df) < 50:
            insights.append("• Consider adding more data for comprehensive analysis")

        insights.append("• Regular monitoring of quarterly performance recommended")
        insights.append("• Review cost center allocations periodically")

        insights_text = "<b>Insights:</b><br/>" + "<br/>".join(insights)
        story.append(Paragraph(insights_text, styles["Normal"]))
        story.append(Spacer(1, 20))

        # Report footer
        story.append(
            Paragraph(
                f"Report generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                styles["Normal"],
            )
        )

        # Build PDF
        doc.build(story)
        buffer.seek(0)

        return buffer

    except Exception as e:
        st.error(f"Error generating report: {e}")
        return None


def get_download_link(buffer, filename):
    """Generate download link for PDF"""
    b64 = base64.b64encode(buffer.getvalue()).decode()
    href = f'<a href="data:application/pdf;base64,{b64}" download="{filename}">Download Report</a>'
    return href
def show_optimizer_dashboard():
    import os

    st.title("⚙️ Compressor Optimization")

    # Simple test to ensure section appears
    st.write("🔧 **Compressor Data Management**")

    # Create a simple form directly
    with st.form("simple_compressor_form"):
        st.write("**Update Compressor Data**")
        col1, col2 = st.columns(2)

        with col1:
            compressor_id = st.selectbox("Compressor ID", ["A", "B", "C", "D"])
            compressor_name = st.text_input(
                "Compressor Name", value=f"Compressor {compressor_id}"
            )
            current_hours = st.number_input(
                "Current Hours", min_value=0, value=500, step=1
            )

        with col2:
            status = st.selectbox(
                "Status", ["Active", "Maintenance", "Inactive", "Repair"]
            )
            notes = st.text_area("Notes", placeholder="Enter notes here")

        if st.form_submit_button("Save Data"):
            # Simple save to Excel
            try:
                data = {
                    "Compressor ID": [compressor_id],
                    "Compressor Name": [compressor_name],
                    "Current Hours": [current_hours],
                    "Date Updated": [datetime.now().date()],
                    "Status": [status],
                    "Notes": [notes],
                }
                df_new = pd.DataFrame(data)

                # Delete the corrupted file if it exists and recreate it
                if os.path.exists("Data/Compressor_Data.xlsx"):
                    try:
                        df_existing = pd.read_excel(
                            "Data/Compressor_Data.xlsx", engine="openpyxl"
                        )
                    except:
                        # File is corrupted, delete and recreate
                        os.remove("Data/Compressor_Data.xlsx")
                        # Create initial data
                        initial_data = {
                            "Compressor ID": ["A", "B", "C"],
                            "Compressor Name": [
                                "Compressor A",
                                "Compressor B",
                                "Compressor C",
                            ],
                            "Current Hours": [500, 79300, 76900],
                            "Date Updated": [datetime.now().date()] * 3,
                            "Status": ["Active", "Active", "Active"],
                            "Notes": [
                                "Initial setup",
                                "High usage unit",
                                "Standard operation",
                            ],
                        }
                        df_existing = pd.DataFrame(initial_data)
                        df_existing.to_excel(
                            "Data/Compressor_Data.xlsx", index=False, engine="openpyxl"
                        )

                    # Update if exists, otherwise append
                    if compressor_id in df_existing["Compressor ID"].values:
                        mask = df_existing["Compressor ID"] == compressor_id
                        for key, value in data.items():
                            df_existing.loc[mask, key] = value[0]
                        df_existing.to_excel(
                            "Data/Compressor_Data.xlsx", index=False, engine="openpyxl"
                        )
                    else:
                        df_combined = pd.concat(
                            [df_existing, df_new], ignore_index=True
                        )
                        df_combined.to_excel(
                            "Data/Compressor_Data.xlsx", index=False, engine="openpyxl"
                        )
                else:
                    # Create new file with initial data plus new entry
                    initial_data = {
                        "Compressor ID": ["A", "B", "C", compressor_id],
                        "Compressor Name": [
                            "Compressor A",
                            "Compressor B",
                            "Compressor C",
                            compressor_name,
                        ],
                        "Current Hours": [500, 79300, 76900, current_hours],
                        "Date Updated": [datetime.now().date()] * 4,
                        "Status": ["Active", "Active", "Active", status],
                        "Notes": [
                            "Initial setup",
                            "High usage unit",
                            "Standard operation",
                            notes,
                        ],
                    }
                    df_all = pd.DataFrame(initial_data)
                    df_all.to_excel(
                        "Data/Compressor_Data.xlsx", index=False, engine="openpyxl"
                    )

                st.success("✅ Data saved successfully!")
            except Exception as e:
                st.error(f"Error saving data: {e}")

    # Add data viewing section
    st.markdown("---")
    st.write("📊 **Current Compressor Data**")

    try:
        if os.path.exists("Data/Compressor_Data.xlsx"):
            df_view = pd.read_excel("Data/Compressor_Data.xlsx", engine="openpyxl")

            if not df_view.empty:
                # Display metrics
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Compressors", len(df_view))
                with col2:
                    active_count = (
                        len(df_view[df_view["Status"] == "Active"])
                        if "Status" in df_view.columns
                        else 0
                    )
                    st.metric("Active Units", active_count)
                with col3:
                    total_hours = (
                        df_view["Current Hours"].sum()
                        if "Current Hours" in df_view.columns
                        else 0
                    )
                    st.metric("Total Hours", f"{total_hours:,}")
                with col4:
                    avg_hours = (
                        df_view["Current Hours"].mean()
                        if "Current Hours" in df_view.columns
                        else 0
                    )
                    st.metric("Average Hours", f"{avg_hours:,.0f}")

                # Display data table
                st.subheader("📋 Compressor Details")
                st.dataframe(df_view, use_container_width=True, hide_index=True)

                # Add status breakdown chart
                if "Status" in df_view.columns:
                    st.subheader("📈 Status Distribution")
                    status_counts = df_view["Status"].value_counts()
                    fig = px.pie(
                        values=status_counts.values,
                        names=status_counts.index,
                        title="Compressor Status Distribution",
                    )
                    st.plotly_chart(fig, use_container_width=True)

                # Add hours comparison chart
                if (
                    "Current Hours" in df_view.columns
                    and "Compressor Name" in df_view.columns
                ):
                    st.subheader("⏱️ Operating Hours Comparison")
                    fig = px.bar(
                        df_view,
                        x="Compressor Name",
                        y="Current Hours",
                        title="Current Operating Hours by Compressor",
                        color="Status" if "Status" in df_view.columns else None,
                    )
                    fig.update_layout(xaxis_title="Compressor", yaxis_title="Hours")
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("No compressor data available")
        else:
            st.warning("No data file found. Add some compressor data first.")
    except Exception as e:
        st.error(f"Error loading data: {e}")

    st.markdown("---")

    # Persist results so multiple runs can be viewed together
    if "opt_results" not in st.session_state:
        st.session_state.opt_results = {}

    # Gap trade-off for models 2 and 3
    lambda_val = st.slider(
        "Gap trade-off (lambda)",
        min_value=0.0,
        max_value=1.0,
        value=0.1,
        step=0.05,
        help="Higher values weight the gap objective more strongly",
    )

    # Run-all control
    run_all = st.button("Run All Models", type="primary")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Run Model 1: Minimize Cost") or run_all:
            df1 = solve_true_min_cost_mip()
            total_hours = (
                float(df1["Assigned Hours"].sum())
                if "Assigned Hours" in df1.columns
                else 0.0
            )
            total_cost = (
                float(df1["Exact Cost"].sum()) if "Exact Cost" in df1.columns else 0.0
            )
            st.session_state.opt_results["m1"] = {
                "df": df1,
                "total_hours": total_hours,
                "total_cost": total_cost,
            }

    with col2:
        if st.button("Run Model 2: Cost + Max Gap") or run_all:
            df2, gap2, total_cost2 = solve_true_min_cost_and_max_gap(
                lambda_gap=lambda_val
            )
            total_hours2 = (
                float(df2["Assigned Hours"].sum())
                if "Assigned Hours" in df2.columns
                else 0.0
            )
            st.session_state.opt_results["m2"] = {
                "df": df2,
                "total_hours": total_hours2,
                "total_cost": float(total_cost2),
                "gap": float(gap2),
                "lambda": lambda_val,
            }

    with col3:
        if st.button("Run Model 3: Cost + Min Gap") or run_all:
            df3, gap3, total_cost3 = solve_true_min_cost_and_min_gap(
                lambda_gap=lambda_val
            )
            total_hours3 = (
                float(df3["Assigned Hours"].sum())
                if "Assigned Hours" in df3.columns
                else 0.0
            )
            st.session_state.opt_results["m3"] = {
                "df": df3,
                "total_hours": total_hours3,
                "total_cost": float(total_cost3),
                "gap": float(gap3),
                "lambda": lambda_val,
            }

    st.markdown("---")

    # Render results for each model if available
    exp1, exp2, exp3 = st.tabs(
        ["Model 1: Minimize Cost", "Model 2: Cost + Max Gap", "Model 3: Cost + Min Gap"]
    )

    with exp1:
        res = st.session_state.opt_results.get("m1")
        if res:
            c1, c2 = st.columns(2)
            c1.metric("Total Assigned Hours", f"{res['total_hours']:,.0f}")
            c2.metric("Total Exact Cost", f"{res['total_cost']:,.2f}")
            st.dataframe(res["df"], use_container_width=True)
        else:
            st.info("Run Model 1 to view results.")

    with exp2:
        res = st.session_state.opt_results.get("m2")
        if res:
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Assigned Hours", f"{res['total_hours']:,.0f}")
            c2.metric("Total Exact Cost", f"{res['total_cost']:,.2f}")
            c3.metric("Range Gap (hrs)", f"{res['gap']:,.0f}")
            st.caption(f"λ = {res['lambda']}")
            st.dataframe(res["df"], use_container_width=True)
        else:
            st.info("Run Model 2 to view results.")

    with exp3:
        res = st.session_state.opt_results.get("m3")
        if res:
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Assigned Hours", f"{res['total_hours']:,.0f}")
            c2.metric("Total Exact Cost", f"{res['total_cost']:,.2f}")
            c3.metric("Range Gap (hrs)", f"{res['gap']:,.0f}")
            st.caption(f"λ = {res['lambda']}")
            st.dataframe(res["df"], use_container_width=True)
        else:
            st.info("Run Model 3 to view results.")
