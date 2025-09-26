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
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np


# CONSTANTS
CURRENT_YEAR = datetime.now().year
EXCEL_PATH = "Data/Budget Monitoring.xlsx"
CONSUMED_COL = "Consumed Amount"
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
        if not st.session_state.get('uploaded_file'):
            df = pd.read_excel(EXCEL_PATH)
        else:
            df = st.session_state.uploaded_file
            
        df.columns = df.columns.str.strip()

        # Dynamically detect year columns
        budget_cols, consumed_cols = detect_year_columns(df)
        
        # Force numeric for all detected budget & consumed columns
        numeric_columns = list(budget_cols.values()) + list(consumed_cols.values()) + [CONSUMED_COL]
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

        # Calculate Available Amount using current year or latest available year
        if AVAILABLE_COL not in df.columns:
            current_year_str = str(CURRENT_YEAR)
            if current_year_str in budget_cols and CONSUMED_COL in df.columns:
                df[AVAILABLE_COL] = df[budget_cols[current_year_str]] - df[CONSUMED_COL]
            elif budget_cols:  # Use latest available year
                latest_year = max(budget_cols.keys())
                df[AVAILABLE_COL] = df[budget_cols[latest_year]] - df[CONSUMED_COL]
            else:
                df[AVAILABLE_COL] = 0

        # Process dates with better handling
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

        # Create display columns safely
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


def validate_excel_structure(df):
    """Validate Excel file structure"""
    required_columns = ["Cost Center Number", "Cost Center Name", "Account number", "Account name"]
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    if missing_columns:
        st.error(f"Missing required columns: {', '.join(missing_columns)}")
        return False
    
    # Check for at least one budget column
    budget_cols, _ = detect_year_columns(df)
    if not budget_cols:
        st.warning("No budget columns found (expected format: 'YYYY Budget')")
        return False
    
    return True


def improved_append_expense_to_excel(new_data: dict):
    """Enhanced expense logging with better validation"""
    try:
        if not st.session_state.get('uploaded_file'):
            df = pd.read_excel(EXCEL_PATH)
        else:
            df = st.session_state.uploaded_file
            
        df.columns = df.columns.str.strip()

        # Check for similar entries (same cost center, account, and date)
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

        # Save back to Excel or update session state
        if not st.session_state.get('uploaded_file'):
            df.to_excel(EXCEL_PATH, index=False, engine="openpyxl")
        else:
            st.session_state.uploaded_file = df
            
        return True

    except Exception as e:
        st.error(f"Error updating expense data: {e}")
        return False


def create_file_upload_section():
    """Create file upload section for dynamic budget management"""
    st.subheader("📂 File Management")
    
    uploaded_file = st.file_uploader(
        "Upload Budget Excel File",
        type=['xlsx', 'xls'],
        help="Upload your budget monitoring Excel file"
    )
    
    if uploaded_file is not None:
        try:
            df = pd.read_excel(uploaded_file)
            if validate_excel_structure(df):
                st.session_state.uploaded_file = df
                st.success(f"✅ File uploaded successfully! Found {len(df)} records.")
                
                # Show file info
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Records", len(df))
                with col2:
                    budget_cols, _ = detect_year_columns(df)
                    st.metric("Budget Years", len(budget_cols))
                with col3:
                    st.metric("Cost Centers", df["Cost Center Name"].nunique() if "Cost Center Name" in df.columns else 0)
                
                return True
            else:
                st.error("❌ Invalid file structure. Please check your Excel format.")
                return False
        except Exception as e:
            st.error(f"❌ Error reading file: {e}")
            return False
    
    return st.session_state.get('uploaded_file') is not None


def add_new_year_budget():
    """Add new year budget functionality"""
    st.subheader("➕ Add New Year Budget")
    
    with st.expander("Add Budget for New Year", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            new_year = st.number_input(
                "Year",
                min_value=2020,
                max_value=2050,
                value=CURRENT_YEAR + 1,
                step=1
            )
            
        with col2:
            budget_type = st.selectbox(
                "Budget Type",
                ["Budget", "Consumed"],
                help="Select whether to add budget or consumed amounts"
            )
        
        if st.button(f"Add {new_year} {budget_type} Column"):
            try:
                # Load current data
                if st.session_state.get('uploaded_file') is not None:
                    df = st.session_state.uploaded_file.copy()
                else:
                    df = pd.read_excel(EXCEL_PATH)
                
                # Add new column
                new_col = f"{new_year} {budget_type}"
                if new_col not in df.columns:
                    df[new_col] = 0.0
                    
                    # Update session state or save to file
                    if st.session_state.get('uploaded_file') is not None:
                        st.session_state.uploaded_file = df
                    else:
                        df.to_excel(EXCEL_PATH, index=False, engine="openpyxl")
                    
                    st.success(f"✅ Added {new_col} column successfully!")
                    st.rerun()
                else:
                    st.warning(f"⚠️ Column {new_col} already exists!")
                    
            except Exception as e:
                st.error(f"❌ Error adding new year column: {e}")


def show_filtered_dashboard():
    """Main dashboard function with enhanced features"""
    st.title("📊 Dynamic Budget Dashboard")

    # File upload section
    if create_file_upload_section():
        st.success("Using uploaded file for analysis")
    else:
        st.info("Using default Excel file for analysis")

    # Add new year functionality
    add_new_year_budget()

    # Load data
    df, cost_center_names, cost_center_numbers, account_names, account_numbers = load_budget_data()
    
    if df.empty:
        st.warning("No data available to display.")
        st.info("Please upload a valid Excel file or check your data source.")
        return

    # Get dynamic year columns
    budget_cols, consumed_cols = detect_year_columns(df)
    available_years = get_available_years(df)

    # Display data info
    with st.expander("📊 Dataset Information", expanded=False):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Records", len(df))
        with col2:
            st.metric("Cost Centers", len(cost_center_names))
        with col3:
            st.metric("Accounts", len(account_names))
        with col4:
            st.metric("Budget Years", len(budget_cols))
        
        st.write("**Available Budget Years:**", ", ".join(available_years))
        st.write("**Available Columns:**")
        st.write(", ".join(df.columns.tolist()))

    # Enhanced Expense Logging Section
    with st.expander("➕ Log New Expense", expanded=True):
        if "Cost Center Display" in df.columns and not df.empty:
            cost_center_options = sorted(df["Cost Center Display"].dropna().unique())

            if cost_center_options:
                selected_cc_display = st.selectbox(
                    "🏢 Select Cost Center",
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
                                "📊 Select Account",
                                sorted(filtered_acc_displays),
                                key="account_display_selector",
                            )
                            
                            acc_row = cc_rows[cc_rows["Account Display"] == selected_acc_display].iloc[0]
                            selected_acc_number = acc_row["Account number"]
                            selected_acc_name = acc_row["Account name"]
                            
                            expense_date = st.date_input("📅 Expense Date", value=datetime.now())
                            
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
                                budget_col = budget_cols.get(current_year_str, list(budget_cols.values())[0] if budget_cols else None)
                                
                                if budget_col:
                                    budget_amount = match[budget_col].iloc[0] if budget_col in match.columns else 0
                                    consumed_before = match[CONSUMED_COL].iloc[0] if CONSUMED_COL in match.columns else 0
                                    available_before = match[AVAILABLE_COL].iloc[0] if AVAILABLE_COL in match.columns else budget_amount
                                    
                                    # Display current status
                                    st.markdown("**📈 Current Budget Status:**")
                                    col1, col2, col3 = st.columns(3)
                                    with col1:
                                        st.metric(f"{current_year_str} Budget", f"${budget_amount:,.2f}")
                                    with col2:
                                        st.metric("Consumed", f"${consumed_before:,.2f}")
                                    with col3:
                                        st.metric("Available", f"${available_before:,.2f}")
                                    
                                    # Expense input
                                    consumed_now = st.number_input(
                                        "💰 New Expense Amount",
                                        min_value=0.0,
                                        step=0.01,
                                        help="Enter the amount you want to log as consumed",
                                    )
                                    
                                    # Calculate impact
                                    if consumed_now > 0:
                                        new_consumed_total = consumed_before + consumed_now
                                        available_after = budget_amount - new_consumed_total
                                        
                                        st.markdown("**📊 After This Expense:**")
                                        col1a, col2a = st.columns(2)
                                        with col1a:
                                            st.write(f"**Total Consumed:** ${new_consumed_total:,.2f}")
                                        with col2a:
                                            st.write(f"**Available:** ${available_after:,.2f}")
                                        
                                        if available_after < 0:
                                            st.error("⚠️ This expense will exceed the available budget!")
                                        elif available_after < (budget_amount * 0.1):
                                            st.warning("⚠️ Low budget remaining!")
                                    
                                    # Form submission
                                    submit = st.form_submit_button("📝 Log Expense", type="primary")
                                    
                                    if submit and consumed_now > 0:
                                        try:
                                            new_consumed_total = consumed_before + consumed_now
                                            available_after = budget_amount - new_consumed_total
                                            
                                            # Get all budget values for different years
                                            budget_values = {}
                                            for year, col in budget_cols.items():
                                                budget_values[f"{year} Budget"] = match[col].iloc[0] if col in match.columns else 0
                                            
                                            row_data = {
                                                "Cost Center Number": selected_cc_number,
                                                "Cost Center Name": selected_cc_name,
                                                "Account number": selected_acc_number,
                                                "Account name": selected_acc_name,
                                                "Date": expense_date,
                                                "Quarter": get_quarter_from_date(expense_date),
                                                "Year": expense_date.year,
                                                CONSUMED_COL: new_consumed_total,
                                                AVAILABLE_COL: available_after,
                                                **budget_values
                                            }
                                            
                                            success = improved_append_expense_to_excel(row_data)
                                            if success:
                                                st.success("✅ Expense logged successfully!")
                                                st.balloons()
                                                st.rerun()
                                            else:
                                                st.error("❌ Failed to log expense.")
                                                
                                        except Exception as e:
                                            st.error(f"❌ Error logging expense: {str(e)}")
                                    
                                    elif submit and consumed_now <= 0:
                                        st.warning("⚠️ Please enter an expense amount greater than 0.")
                                else:
                                    st.error("No budget column found for current year")
                            else:
                                st.error("❌ No matching record found.")

    # Enhanced Analytics Section
    st.markdown("---")
    tab1, tab2, tab3 = st.tabs(["📊 Analysis Dashboard", "📋 Summary & Insights", "📈 Advanced Analytics"])
    
    with tab1:
        show_analysis_dashboard(df, budget_cols, consumed_cols, available_years, cost_center_names, account_names)
    
    with tab2:
        show_summary_tab(df, budget_cols, consumed_cols)
    
    with tab3:
        show_advanced_analytics(df, budget_cols, consumed_cols, available_years)


def show_analysis_dashboard(df, budget_cols, consumed_cols, available_years, cost_center_names, account_names):
    """Enhanced analysis dashboard with dynamic year support"""
    st.subheader("🎯 Filters")
    
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
            selected_year = st.selectbox(
                "Select Year",
                options=available_years,
                index=0 if available_years else 0
            )
            selected_quarters = st.multiselect(
                "Select Quarters",
                options=["Q1", "Q2", "Q3", "Q4"],
                default=["Q1", "Q2", "Q3", "Q4"]
            )
    
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

    # Account filter
    account_options = ["All"] + sorted(filtered_df["Account name"].unique())
    selected_accounts = st.multiselect(
        "Accounts",
        options=account_options,
        default=["All"]
    )
    
    if "All" not in selected_accounts and selected_accounts:
        filtered_df = filtered_df[filtered_df["Account name"].isin(selected_accounts)]

    st.markdown("---")

    # Generate visualizations based on time period
    if time_period == "Annual" and selected_years:
        show_annual_analysis(filtered_df, budget_cols, consumed_cols, selected_years)
    elif time_period == "Quarterly" and selected_quarters:
        show_quarterly_analysis(filtered_df, budget_cols, selected_year, selected_quarters)

    # Data table
    st.subheader("📋 Filtered Data")
    display_columns = ["Cost Center Name", "Account name", "Date", "Quarter", CONSUMED_COL, AVAILABLE_COL]
    
    # Add selected year budget columns
    if time_period == "Annual":
        for year in selected_years:
            if year in budget_cols:
                display_columns.append(budget_cols[year])
    else:
        if selected_year in budget_cols:
            display_columns.append(budget_cols[selected_year])
    
    # Filter columns that exist
    display_columns = [col for col in display_columns if col in filtered_df.columns]
    
    st.dataframe(filtered_df[display_columns], use_container_width=True)


def show_annual_analysis(df, budget_cols, consumed_cols, selected_years):
    """Show annual analysis with dynamic year support"""
    st.subheader("📈 Annual Analysis")
    
    # Prepare annual data
    annual_data = []
    for year in selected_years:
        if year in budget_cols:
            budget_col = budget_cols[year]
            consumed_col = consumed_cols.get(year, CONSUMED_COL)  # Fallback to general consumed
            
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
        
        # Budget vs Consumed
        if "Consumed" in annual_df.columns:
            fig2 = px.bar(
                annual_df,
                x="Year",
                y=["Budget", "Consumed"],
                barmode="group",
                title="Budget vs Consumed by Year"
            )
            st.plotly_chart(fig2, use_container_width=True)
        
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
    st.subheader(f"📅 {selected_year} Quarterly Analysis")
    
    if selected_year in budget_cols:
        budget_col = budget_cols[selected_year]
        
        quarter_filtered = df[
            (df["Year"] == int(selected_year)) &
            (df["Quarter"].isin(selected_quarters))
        ]
        
        if not quarter_filtered.empty:
            # Quarterly budget distribution
            quarterly_summary = quarter_filtered.groupby("Quarter").agg({
                budget_col: "sum",
                CONSUMED_COL: "sum"
            }).reset_index()
            
            fig = px.bar(
                quarterly_summary,
                x="Quarter",
                y=[budget_col, CONSUMED_COL],
                title=f"{selected_year} Quarterly Budget vs Consumed",
                barmode="group"
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # Quarterly trends by cost center
            cc_quarterly = quarter_filtered.groupby(["Quarter", "Cost Center Name"]).agg({
                budget_col: "sum",
                CONSUMED_COL: "sum"
            }).reset_index()
            
            fig2 = px.line(
                cc_quarterly,
                x="Quarter",
                y=CONSUMED_COL,
                color="Cost Center Name",
                title=f"{selected_year} Quarterly Consumption by Cost Center",
                markers=True
            )
            st.plotly_chart(fig2, use_container_width=True)


def show_advanced_analytics(df, budget_cols, consumed_cols, available_years):
    """Advanced analytics with predictive insights"""
    st.subheader("🔮 Advanced Analytics")
    
    # Year-over-year growth analysis
    if len(available_years) >= 2:
        st.subheader("📈 Growth Analysis")
        
        growth_data = []
        for i in range(1, len(available_years)):
            current_year = available_years[i-1]
            previous_year = available_years[i]
            
            if current_year in budget_cols and previous_year in budget_cols:
                current_total = df[budget_cols[current_year]].sum()
                previous_total = df[budget_cols[previous_year]].sum()
                
                if previous_total > 0:
                    growth_rate = ((current_total - previous_total) / previous_total) * 100
                    growth_data.append({
                        "Period": f"{previous_year} to {current_year}",
                        "Growth Rate (%)": growth_rate,
                        "Current Year Total": current_total,
                        "Previous Year Total": previous_total
                    })
        
        if growth_data:
            growth_df = pd.DataFrame(growth_data)
            
            col1, col2 = st.columns(2)
            with col1:
                st.dataframe(growth_df, use_container_width=True)
            
            with col2:
                fig = px.bar(
                    growth_df,
                    x="Period",
                    y="Growth Rate (%)",
                    title="Year-over-Year Growth Rates",
                    color="Growth Rate (%)",
                    color_continuous_scale="RdYlGn"
                )
                st.plotly_chart(fig, use_container_width=True)
    
    # Budget utilization efficiency
    st.subheader("⚡ Utilization Efficiency")
    
    if available_years and CONSUMED_COL in df.columns:
        latest_year = available_years[0]
        if latest_year in budget_cols:
            budget_col = budget_cols[latest_year]
            
            efficiency_df = df.groupby("Cost Center Name").agg({
                budget_col: "sum",
                CONSUMED_COL: "sum"
            }).reset_index()
            
            efficiency_df["Utilization (%)"] = (
                efficiency_df[CONSUMED_COL] / efficiency_df[budget_col] * 100
            ).fillna(0)
            
            efficiency_df = efficiency_df.sort_values("Utilization (%)", ascending=False)
            
            fig = px.bar(
                efficiency_df,
                x="Cost Center Name",
                y="Utilization (%)",
                title=f"{latest_year} Budget Utilization by Cost Center",
                color="Utilization (%)",
                color_continuous_scale="Viridis"
            )
            fig.update_xaxis(tickangle=45)
            st.plotly_chart(fig, use_container_width=True)
            
            # Efficiency metrics
            col1, col2, col3 = st.columns(3)
            with col1:
                avg_utilization = efficiency_df["Utilization (%)"].mean()
                st.metric("Average Utilization", f"{avg_utilization:.1f}%")
            with col2:
                high_efficiency = len(efficiency_df[efficiency_df["Utilization (%)"] >= 80])
                st.metric("High Efficiency Units", f"{high_efficiency}/{len(efficiency_df)}")