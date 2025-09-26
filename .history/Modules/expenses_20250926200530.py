# File: Modules/expenses.py
import streamlit as st
import re
import os
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
from Modules.maintenance import solve_true_min_cost_mip, solve_true_min_cost_and_min_gap, solve_true_min_cost_and_max_gap

# Dynamic constants - no hardcoded years
CURRENT_YEAR = datetime.now().year
EXCEL_PATH = "Data/Budget Monitoring.xlsx"

class DynamicColumnManager:
    """Manages dynamic column detection and mapping for yearly data"""
    
    def __init__(self, df):
        # assume df.columns are already stripped where possible, but we keep defensive code
        df.columns = df.columns.astype(str).str.strip()
        self.df = df
        self.budget_cols, self.consumed_cols = self.detect_year_columns()
        self.available_years = self.get_available_years()
        self.current_year_str = str(CURRENT_YEAR)
        
    def detect_year_columns(self):
        """Dynamically detect budget and consumed columns by year.
        Stores the cleaned column name (no leading/trailing spaces) as value.
        Accepts variants like '2026 Budget' or '2026Budget' with optional separators.
        """
        budget_cols = {}
        consumed_cols = {}

        for col in self.df.columns:
            col_clean = str(col).strip()
            # Match budget columns (YYYY Budget) loosely (allow no space or multiple separators)
            m_budget = re.search(r"(\d{4})\s*[-_\s]*\s*Budget\b", col_clean, flags=re.IGNORECASE)
            if m_budget:
                year = m_budget.group(1)
                budget_cols[year] = col_clean
                continue

            # Match consumed columns (YYYY Consumed)
            m_consumed = re.search(r"(\d{4})\s*[-_\s]*\s*Consumed\b", col_clean, flags=re.IGNORECASE)
            if m_consumed:
                year = m_consumed.group(1)
                consumed_cols[year] = col_clean

        return budget_cols, consumed_cols

    def get_available_years(self):
        """Get all available years from the dataset (sorted descending numerically)"""
        all_years = set(self.budget_cols.keys()) | set(self.consumed_cols.keys())
        try:
            return sorted(list(all_years), key=lambda y: int(y), reverse=True)
        except Exception:
            return sorted(list(all_years), reverse=True)
    
    def get_budget_column(self, year=None):
        """Get budget column for a specific year. If year None -> default to CURRENT_YEAR string."""
        year = str(year) if year is not None else self.current_year_str
        return self.budget_cols.get(str(year))
    
    def get_consumed_column(self, year=None):
        """Get consumed column for a specific year."""
        year = str(year) if year is not None else self.current_year_str
        return self.consumed_cols.get(str(year))
    
    def get_latest_budget_column(self):
        """Get the most recent budget column available"""
        if self.available_years:
            latest_year = self.available_years[0]  # Already sorted desc
            return self.budget_cols.get(latest_year)
        return None
    
    def get_latest_consumed_column(self):
        """Get the most recent consumed column available"""
        if self.available_years:
            latest_year = self.available_years[0]
            return self.consumed_cols.get(latest_year)
        return None
    
    def create_unified_columns(self, force_latest=True, selected_year=None):
        """Create unified columns for current (or selected) year operations.

        - If selected_year provided -> use that.
        - Else if force_latest=True -> use the newest available year.
        - Else -> fallback to the runtime CURRENT_YEAR.
        """
        # Decide the year to use
        if selected_year is not None:
            year_to_use = str(selected_year)
        elif force_latest and self.available_years:
            year_to_use = str(self.available_years[0])
        else:
            year_to_use = str(CURRENT_YEAR)

        budget_col = self.get_budget_column(year_to_use) or self.get_latest_budget_column()
        consumed_col = self.get_consumed_column(year_to_use) or self.get_latest_consumed_column()
        
        # Ensure numeric conversion where columns exist
        if budget_col and budget_col in self.df.columns:
            self.df['Current_Budget'] = pd.to_numeric(self.df[budget_col], errors="coerce").fillna(0)
        else:
            self.df['Current_Budget'] = 0
            
        if consumed_col and consumed_col in self.df.columns:
            self.df['Current_Consumed'] = pd.to_numeric(self.df[consumed_col], errors="coerce").fillna(0)
        else:
            self.df['Current_Consumed'] = 0
            
        # Calculate available amount
        self.df['Current_Available'] = self.df['Current_Budget'] - self.df['Current_Consumed']
        
        # Legacy column names for backward compatibility
        self.df['Consumed Amount'] = self.df['Current_Consumed']
        self.df['Available Amount'] = self.df['Current_Available']
        
        return self.df
  
def create_unified_columns(self, force_latest=True):
    """Create unified columns for current or latest available year"""
    # If force_latest=True, use the most recent available year
    if force_latest and self.available_years:
        selected_year = self.available_years[0]  # newest year (sorted desc)
    else:
        selected_year = str(CURRENT_YEAR)

    budget_col = self.get_budget_column(selected_year)
    consumed_col = self.get_consumed_column(selected_year)

    if budget_col and budget_col in self.df.columns:
        self.df['Current_Budget'] = pd.to_numeric(self.df[budget_col], errors="coerce").fillna(0)
    else:
        self.df['Current_Budget'] = 0

    if consumed_col and consumed_col in self.df.columns:
        self.df['Current_Consumed'] = pd.to_numeric(self.df[consumed_col], errors="coerce").fillna(0)
    else:
        self.df['Current_Consumed'] = 0

    # Calculate available
    self.df['Current_Available'] = self.df['Current_Budget'] - self.df['Current_Consumed']

    # Legacy compatibility
    self.df['Consumed Amount'] = self.df['Current_Consumed']
    self.df['Available Amount'] = self.df['Current_Available']

    return self.df

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

@st.cache_data(ttl=300)
def load_budget_data_dynamic():
    """Load and process budget data with full dynamic year support"""
    try:
        # Load data
        if st.session_state.get('uploaded_file') is not None:
            df = st.session_state.uploaded_file.copy()
        else:
            df = pd.read_excel(EXCEL_PATH)
           # normalize headers immediately to remove trailing/leading spaces
            df.columns = df.columns.astype(str).str.strip()

# debug
            st.write("🔎 Columns in file (after strip):", df.columns.tolist()) 
        
        
        # Initialize column manager
        col_manager = DynamicColumnManager(df)
        
        # Force numeric for all detected budget & consumed columns
        numeric_columns = list(col_manager.budget_cols.values()) + list(col_manager.consumed_cols.values())
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        
        # Create unified current year columns
        df = col_manager.create_unified_columns()
        
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

        return df, cost_center_names, cost_center_numbers, account_names, account_numbers, col_manager

    except FileNotFoundError:
        st.error(f"Excel file not found at {EXCEL_PATH}")
        return pd.DataFrame(), [], [], [], [], None
    except Exception as e:
        st.error(f"Failed to load budget data: {e}")
        return pd.DataFrame(), [], [], [], [], None

def validate_excel_structure(df):
    """Validate Excel file structure"""
    required_columns = ["Cost Center Number", "Cost Center Name", "Account number", "Account name"]
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    if missing_columns:
        st.error(f"Missing required columns: {', '.join(missing_columns)}")
        return False
    
    # Check for at least one budget column
    col_manager = DynamicColumnManager(df)
    if not col_manager.budget_cols:
        st.warning("No budget columns found (expected format: 'YYYY Budget')")
        return False
    
    return True

def improved_append_expense_to_excel(new_data: dict):
    """Enhanced expense logging with better validation"""
    try:
        if st.session_state.get('uploaded_file') is not None:
            df = st.session_state.uploaded_file.copy()
        else:
            df = pd.read_excel(EXCEL_PATH)
            
        df.columns = df.columns.str.strip()

        # Check for similar entries (same cost center, account, and date)
        duplicate_check = df[
            (df["Cost Center Number"].astype(str) == str(new_data["Cost Center Number"])) &
            (df["Account number"].astype(str) == str(new_data["Account number"])) &
            (pd.to_datetime(df["Date"], errors='coerce').dt.date == new_data["Date"])
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
        if st.session_state.get('uploaded_file') is not None:
            st.session_state.uploaded_file = df
        else:
            df.to_excel(EXCEL_PATH, index=False, engine="openpyxl")
            
        return True

    except Exception as e:
        st.error(f"Error updating expense data: {e}")
        return False

def show_analysis_dashboard_dynamic(df, col_manager, cost_center_names, account_names):
    """Enhanced analysis dashboard with full dynamic year support"""
    st.subheader("📊 Analysis Filters")
    
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
                options=col_manager.available_years,
                default=col_manager.available_years[:3] if len(col_manager.available_years) >= 3 else col_manager.available_years,
                help="Choose years to compare"
            )
        else:
            selected_year = st.selectbox(
                "Select Year",
                options=col_manager.available_years,
                index=0 if col_manager.available_years else 0
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
    if "Account name" in filtered_df.columns:
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
        show_annual_analysis_dynamic(filtered_df, col_manager, selected_years)
    elif time_period == "Quarterly" and selected_quarters and col_manager.available_years:
        show_quarterly_analysis_dynamic(filtered_df, col_manager, selected_year, selected_quarters)

    # Data table with dynamic columns
    st.subheader("📋 Filtered Data")
    display_columns = ["Cost Center Name", "Account name", "Date", "Quarter"]
    
    # Add selected year budget/consumed columns dynamically
    if time_period == "Annual":
        for year in selected_years[:3]:  # Limit to first 3 for display
            budget_col = col_manager.get_budget_column(year)
            consumed_col = col_manager.get_consumed_column(year)
            if budget_col and budget_col in filtered_df.columns:
                display_columns.append(budget_col)
            if consumed_col and consumed_col in filtered_df.columns:
                display_columns.append(consumed_col)
    else:
        budget_col = col_manager.get_budget_column(selected_year)
        consumed_col = col_manager.get_consumed_column(selected_year)
        if budget_col and budget_col in filtered_df.columns:
            display_columns.append(budget_col)
        if consumed_col and consumed_col in filtered_df.columns:
            display_columns.append(consumed_col)
    
    # Add current unified columns
    display_columns.extend(['Current_Budget', 'Current_Consumed', 'Current_Available'])
    
    # Filter columns that actually exist
    display_columns = [col for col in display_columns if col in filtered_df.columns]
    
    if display_columns:
        st.dataframe(filtered_df[display_columns], use_container_width=True)
    else:
        st.warning("No data columns available for display")

def show_annual_analysis_dynamic(df, col_manager, selected_years):
    """Show annual analysis with full dynamic year support"""
    st.subheader("📈 Annual Analysis")
    
    annual_data = []
    for year in selected_years:
        budget_col = col_manager.get_budget_column(year)
        consumed_col = col_manager.get_consumed_column(year)
        
        if not budget_col:
            st.warning(f"No budget data found for {year}")
            continue
            
        if "Cost Center Name" in df.columns:
            agg_dict = {budget_col: "sum"}
            if consumed_col and consumed_col in df.columns:
                agg_dict[consumed_col] = "sum"
            
            year_summary = df.groupby("Cost Center Name").agg(agg_dict).reset_index()
            
            year_summary["Year"] = year
            year_summary.rename(columns={
                budget_col: "Budget",
                consumed_col: "Consumed" if consumed_col else "Consumed"
            }, inplace=True)
            
            # Fill missing consumed data with zeros
            if "Consumed" not in year_summary.columns:
                year_summary["Consumed"] = 0
            
            annual_data.append(year_summary)
    
    if annual_data:
        annual_df = pd.concat(annual_data, ignore_index=True)
        
        # Budget comparison chart
        if len(annual_df["Cost Center Name"].unique()) > 1:
            fig = px.bar(
                annual_df,
                x="Year",
                y="Budget",
                color="Cost Center Name",
                title="Annual Budget Comparison by Cost Center",
                barmode="group"
            )
        else:
            fig = px.bar(
                annual_df,
                x="Year",
                y="Budget",
                title="Annual Budget Comparison",
            )
        st.plotly_chart(fig, use_container_width=True)
        
        # Budget vs Consumed comparison
        if "Consumed" in annual_df.columns:
            summary_df = annual_df.groupby("Year")[["Budget", "Consumed"]].sum().reset_index()
            fig2 = px.bar(
                summary_df,
                x="Year",
                y=["Budget", "Consumed"],
                barmode="group",
                title="Total Budget vs Consumed by Year"
            )
            st.plotly_chart(fig2, use_container_width=True)

def show_quarterly_analysis_dynamic(df, col_manager, selected_year, selected_quarters):
    """Show quarterly analysis with dynamic year support"""
    st.subheader(f"📅 {selected_year} Quarterly Analysis")
    
    budget_col = col_manager.get_budget_column(selected_year)
    consumed_col = col_manager.get_consumed_column(selected_year)
    
    if not budget_col:
        st.error(f"No budget data available for {selected_year}")
        return
        
    quarter_filtered = df[
        (df["Year"] == int(selected_year)) &
        (df["Quarter"].isin(selected_quarters))
    ]
    
    if not quarter_filtered.empty:
        # Quarterly budget distribution
        agg_dict = {budget_col: "sum"}
        if consumed_col and consumed_col in quarter_filtered.columns:
            agg_dict[consumed_col] = "sum"
        else:
            # Use Current_Consumed as fallback
            agg_dict["Current_Consumed"] = "sum"
            consumed_col = "Current_Consumed"
            
        quarterly_summary = quarter_filtered.groupby("Quarter").agg(agg_dict).reset_index()
        
        # Create chart with available columns
        y_cols = [budget_col]
        if consumed_col in quarterly_summary.columns:
            y_cols.append(consumed_col)
            
        fig = px.bar(
            quarterly_summary,
            x="Quarter",
            y=y_cols,
            title=f"{selected_year} Quarterly Budget Analysis",
            barmode="group"
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Show summary metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            total_budget = quarterly_summary[budget_col].sum()
            st.metric("Total Budget", f"{total_budget:,.0f}")
        with col2:
            if consumed_col in quarterly_summary.columns:
                total_consumed = quarterly_summary[consumed_col].sum()
                st.metric("Total Consumed", f"{total_consumed:,.0f}")
        with col3:
            if consumed_col in quarterly_summary.columns:
                utilization = (total_consumed / total_budget * 100) if total_budget > 0 else 0
                st.metric("Utilization %", f"{utilization:.1f}%")


def create_file_upload_section():
    """Create file upload section for dynamic budget management"""
    st.subheader("📂 File Management")
    
    # Absolute path to your Budget Monitoring file
    file_path = r"C:\GASCO_DASHBOARD\Data\Budget Monitoring.xlsx"
    
    uploaded_file = st.file_uploader(
        "Upload Budget Excel File",
        type=['xlsx', 'xls'],
        help="Upload your Budget Monitoring Excel file"
    )
    
    if uploaded_file is not None:
        try:
            # Ensure parent directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            # Save uploaded file (overwrite existing)
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())

            # Debug: confirm file size
            size_kb = os.path.getsize(file_path) / 1024
            st.info(f"📂 File saved to: {file_path} ({size_kb:.1f} KB)")

            # ✅ Load saved file into DataFrame
            df = pd.read_excel(file_path)

            # ✅ Debug: inspect file contents
            st.write("🔎 Columns in file:", df.columns.tolist())
            st.write("📊 First rows of file:", df.head())

            # Validate structure
            if validate_excel_structure(df):
                st.session_state.uploaded_file = df
                st.success(f"✅ 'Budget Monitoring.xlsx' uploaded and replaced successfully! Found {len(df)} records.")

                # 🔎 Extra debug for budget year detection
                try:
                    col_manager = DynamicColumnManager(df)
                    st.write("✅ Detected budget year columns:", col_manager.budget_cols)
                except Exception as e:
                    st.warning(f"⚠️ Could not detect budget years: {e}")

            else:
                st.error("❌ Invalid file structure. Please check your Budget Monitoring Excel format.")
                return False

        except Exception as e:
            st.error(f"❌ Error processing file: {e}")
            return False
    
    # 🔹 Auto-load if no upload but file exists
    elif "uploaded_file" not in st.session_state and os.path.exists(file_path):
        try:
            df = pd.read_excel(file_path)

            # ✅ Debug when auto-loading
            st.write("🔎 Auto-loaded columns:", df.columns.tolist())
            st.write("📊 Auto-loaded first rows:", df.head())

            if validate_excel_structure(df):
                st.session_state.uploaded_file = df
                st.info("ℹ️ Loaded existing 'Budget Monitoring.xlsx' from disk.")

                # 🔎 Extra debug for budget year detection
                try:
                    col_manager = DynamicColumnManager(df)
                    st.write("✅ Detected budget year columns:", col_manager.budget_cols)
                except Exception as e:
                    st.warning(f"⚠️ Could not detect budget years: {e}")

            else:
                st.error("❌ Existing 'Budget Monitoring.xlsx' has an invalid structure.")
                return False
        except Exception as e:
            st.error(f"❌ Error loading saved file: {e}")
            return False

    return st.session_state.get('uploaded_file') is not None
# Add this to your show_filtered_dashboard_dynamic() function
# Replace the tab section that's currently misplaced with this:


def show_filtered_dashboard():
    """Legacy function - redirects to dynamic version"""
    show_filtered_dashboard_dynamic()
def show_analysis_dashboard_dynamic(df, col_manager, cost_center_names, account_names):
    """Enhanced analysis dashboard with comprehensive visualizations"""
    st.subheader("📊 Advanced Analysis Dashboard")
    
    # Enhanced Filter Section
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        analysis_type = st.selectbox(
            "Analysis Type",
            options=["Overview", "Cost Center Comparison", "Account Analysis", "Time Series", "Performance Matrix"],
            help="Choose the type of analysis to perform"
        )
    
    with col2:
        time_period = st.selectbox(
            "Time Period",
            options=["Annual", "Quarterly", "Monthly"],
            help="Choose time granularity"
        )
    
    with col3:
        if time_period == "Annual":
            selected_years = st.multiselect(
                "Select Years",
                options=col_manager.available_years,
                default=col_manager.available_years[:min(3, len(col_manager.available_years))],
                help="Choose years to compare"
            )
        elif time_period == "Quarterly":
            selected_year = st.selectbox("Year", options=col_manager.available_years, index=0)
            selected_quarters = st.multiselect(
                "Quarters",
                options=["Q1", "Q2", "Q3", "Q4"],
                default=["Q1", "Q2", "Q3", "Q4"]
            )
        else:  # Monthly
            selected_year = st.selectbox("Year", options=col_manager.available_years, index=0)
            selected_months = st.multiselect(
                "Months",
                options=[f"Month {i}" for i in range(1, 13)],
                default=[f"Month {i}" for i in range(1, 7)]
            )
    
    with col4:
        visualization_style = st.selectbox(
            "Chart Style",
            options=["Standard", "Interactive", "Advanced", "Executive Summary"],
            help="Choose visualization complexity"
        )

    # Advanced Filters
    with st.expander("🔍 Advanced Filters", expanded=False):
        filter_col1, filter_col2, filter_col3 = st.columns(3)
        
        with filter_col1:
            cc_options = ["All"] + cost_center_names
            selected_ccs = st.multiselect("Cost Centers", options=cc_options, default=["All"])
            
        with filter_col2:
            account_options = ["All"] + account_names[:20]  # Limit for performance
            selected_accounts = st.multiselect("Accounts", options=account_options, default=["All"])
            
        with filter_col3:
            budget_range = st.slider(
                "Budget Range Filter",
                min_value=0,
                max_value=int(df['Current_Budget'].max()) if 'Current_Budget' in df.columns else 100000,
                value=(0, int(df['Current_Budget'].max()) if 'Current_Budget' in df.columns else 100000),
                help="Filter by budget amount range"
            )

    # Apply filters
    filtered_df = apply_filters(df, selected_ccs, selected_accounts, budget_range)
    
    if filtered_df.empty:
        st.warning("No data matches the selected filters.")
        return

    st.markdown("---")
    
    # Route to appropriate analysis based on selection
    if analysis_type == "Overview":
        show_overview_analysis(filtered_df, col_manager, selected_years if time_period == "Annual" else [selected_year], visualization_style)
    elif analysis_type == "Cost Center Comparison":
        show_cost_center_comparison(filtered_df, col_manager, selected_years if time_period == "Annual" else [selected_year], visualization_style)
    elif analysis_type == "Account Analysis":
        show_account_analysis(filtered_df, col_manager, selected_years if time_period == "Annual" else [selected_year], visualization_style)
    elif analysis_type == "Time Series":
        show_time_series_analysis(filtered_df, col_manager, selected_years if time_period == "Annual" else [selected_year])
    elif analysis_type == "Performance Matrix":
        show_performance_matrix(filtered_df, col_manager, selected_years if time_period == "Annual" else [selected_year])

def apply_filters(df, selected_ccs, selected_accounts, budget_range):
    """Apply selected filters to dataframe"""
    filtered_df = df.copy()
    
    # Cost center filter
    if "All" not in selected_ccs and selected_ccs:
        filtered_df = filtered_df[filtered_df["Cost Center Name"].isin(selected_ccs)]
    
    # Account filter
    if "All" not in selected_accounts and selected_accounts:
        filtered_df = filtered_df[filtered_df["Account name"].isin(selected_accounts)]
    
    # Budget range filter
    if 'Current_Budget' in filtered_df.columns:
        filtered_df = filtered_df[
            (filtered_df['Current_Budget'] >= budget_range[0]) &
            (filtered_df['Current_Budget'] <= budget_range[1])
        ]
    
    return filtered_df

def show_overview_analysis(df, col_manager, selected_years, style):
    """Comprehensive overview analysis"""
    st.subheader("📈 Budget Overview Analysis")
    
    # KPI Cards
    show_kpi_cards(df, col_manager, selected_years)
    
    # Multi-year budget comparison
    if len(selected_years) > 1:
        st.subheader("💰 Multi-Year Budget Comparison")
        
        # Aggregate data by year
        yearly_data = []
        for year in selected_years:
            budget_col = col_manager.get_budget_column(year)
            consumed_col = col_manager.get_consumed_column(year)
            
            if budget_col and budget_col in df.columns:
                total_budget = df[budget_col].sum()
                total_consumed = df[consumed_col].sum() if consumed_col and consumed_col in df.columns else 0
                
                yearly_data.append({
                    "Year": year,
                    "Total Budget": total_budget,
                    "Total Consumed": total_consumed,
                    "Available": total_budget - total_consumed,
                    "Utilization %": (total_consumed / total_budget * 100) if total_budget > 0 else 0
                })
        
        if yearly_data:
            yearly_df = pd.DataFrame(yearly_data)
            
            # Create comprehensive comparison charts
            col1, col2 = st.columns(2)
            
            with col1:
                # Budget vs Consumed comparison
                fig1 = px.bar(
                    yearly_df,
                    x="Year",
                    y=["Total Budget", "Total Consumed", "Available"],
                    title="Budget Allocation vs Usage by Year",
                    barmode="group",
                    color_discrete_map={
                        "Total Budget": "#1f77b4",
                        "Total Consumed": "#ff7f0e", 
                        "Available": "#2ca02c"
                    }
                )
                fig1.update_layout(height=400)
                st.plotly_chart(fig1, use_container_width=True)
            
            with col2:
                # Utilization rate trend
                fig2 = px.line(
                    yearly_df,
                    x="Year",
                    y="Utilization %",
                    title="Budget Utilization Rate Trend",
                    markers=True,
                    line_shape="spline"
                )
                fig2.add_hline(y=80, line_dash="dash", line_color="red", 
                              annotation_text="Target 80%")
                fig2.update_layout(height=400, yaxis_range=[0, 100])
                st.plotly_chart(fig2, use_container_width=True)

    # Budget distribution analysis
    show_budget_distribution_analysis(df, col_manager, selected_years[0] if selected_years else col_manager.available_years[0])

def show_kpi_cards(df, col_manager, selected_years):
    """Display key performance indicators"""
    if not selected_years:
        return
    
    current_year = selected_years[0]
    budget_col = col_manager.get_budget_column(current_year)
    consumed_col = col_manager.get_consumed_column(current_year)
    
    if budget_col and budget_col in df.columns:
        total_budget = df[budget_col].sum()
        total_consumed = df[consumed_col].sum() if consumed_col and consumed_col in df.columns else 0
        total_available = total_budget - total_consumed
        utilization = (total_consumed / total_budget * 100) if total_budget > 0 else 0
        
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric(
                f"{current_year} Total Budget",
                f"${total_budget:,.0f}",
                help="Total allocated budget"
            )
        
        with col2:
            st.metric(
                "Total Consumed",
                f"${total_consumed:,.0f}",
                delta=f"{utilization:.1f}% used"
            )
        
        with col3:
            st.metric(
                "Available Balance",
                f"${total_available:,.0f}",
                delta=f"{100-utilization:.1f}% remaining"
            )
        
        with col4:
            efficiency_color = "normal"
            if utilization > 90:
                efficiency_color = "inverse"
            elif utilization < 50:
                efficiency_color = "off"
            
            st.metric(
                "Utilization Rate",
                f"{utilization:.1f}%",
                help="Budget utilization efficiency"
            )
        
        with col5:
            avg_per_cc = total_budget / len(df["Cost Center Name"].unique()) if len(df["Cost Center Name"].unique()) > 0 else 0
            st.metric(
                "Avg per Cost Center",
                f"${avg_per_cc:,.0f}",
                help="Average budget allocation per cost center"
            )

def show_cost_center_comparison(df, col_manager, selected_years, style):
    """Detailed cost center comparison analysis"""
    st.subheader("🏢 Cost Center Performance Analysis")
    
    # Cost center performance matrix
    cc_analysis = []
    for cc in df["Cost Center Name"].unique():
        cc_data = df[df["Cost Center Name"] == cc]
        
        for year in selected_years:
            budget_col = col_manager.get_budget_column(year)
            consumed_col = col_manager.get_consumed_column(year)
            
            if budget_col and budget_col in cc_data.columns:
                budget = cc_data[budget_col].sum()
                consumed = cc_data[consumed_col].sum() if consumed_col and consumed_col in cc_data.columns else 0
                utilization = (consumed / budget * 100) if budget > 0 else 0
                
                cc_analysis.append({
                    "Cost Center": cc,
                    "Year": year,
                    "Budget": budget,
                    "Consumed": consumed,
                    "Available": budget - consumed,
                    "Utilization %": utilization,
                    "Accounts": cc_data["Account name"].nunique()
                })
    
    if cc_analysis:
        cc_df = pd.DataFrame(cc_analysis)
        
        # Multi-dimensional analysis
        col1, col2 = st.columns(2)
        
        with col1:
            # Cost center budget comparison
            fig1 = px.bar(
                cc_df,
                x="Cost Center",
                y="Budget",
                color="Year",
                title="Budget Allocation by Cost Center & Year",
                barmode="group"
            )
            fig1.update_xaxes(tickangle=45)
            st.plotly_chart(fig1, use_container_width=True)
        
        with col2:
            # Utilization efficiency bubble chart
            fig2 = px.scatter(
                cc_df,
                x="Budget",
                y="Utilization %",
                size="Consumed",
                color="Cost Center",
                title="Budget Efficiency Analysis",
                hover_data=["Available", "Accounts"]
            )
            fig2.add_hline(y=80, line_dash="dash", annotation_text="Target Efficiency")
            st.plotly_chart(fig2, use_container_width=True)
        
        # Performance ranking table
        st.subheader("📊 Cost Center Performance Ranking")
        
        # Calculate performance scores
        latest_year_data = cc_df[cc_df["Year"] == selected_years[0]] if selected_years else cc_df
        latest_year_data = latest_year_data.copy()
        latest_year_data["Performance Score"] = (
            (latest_year_data["Utilization %"] * 0.4) +  # Utilization weight
            ((latest_year_data["Budget"] / latest_year_data["Budget"].max()) * 100 * 0.3) +  # Budget size weight
            ((latest_year_data["Accounts"] / latest_year_data["Accounts"].max()) * 100 * 0.3)  # Complexity weight
        )
        
        ranking_df = latest_year_data.sort_values("Performance Score", ascending=False)
        
        # Display ranking with styled metrics
        for idx, (_, row) in enumerate(ranking_df.head(10).iterrows(), 1):
            col1, col2, col3, col4, col5 = st.columns([1, 3, 2, 2, 2])
            
            with col1:
                st.write(f"**#{idx}**")
            with col2:
                st.write(row["Cost Center"])
            with col3:
                st.write(f"${row['Budget']:,.0f}")
            with col4:
                utilization_color = "🟢" if row["Utilization %"] > 70 else "🟡" if row["Utilization %"] > 50 else "🔴"
                st.write(f"{utilization_color} {row['Utilization %']:.1f}%")
            with col5:
                st.write(f"⭐ {row['Performance Score']:.1f}")

def show_account_analysis(df, col_manager, selected_years, style):
    """Detailed account-level analysis"""
    st.subheader("📋 Account Performance Analysis")
    
    # Account analysis preparation
    account_analysis = []
    for account in df["Account name"].unique():
        account_data = df[df["Account name"] == account]
        
        for year in selected_years:
            budget_col = col_manager.get_budget_column(year)
            consumed_col = col_manager.get_consumed_column(year)
            
            if budget_col and budget_col in account_data.columns:
                budget = account_data[budget_col].sum()
                consumed = account_data[consumed_col].sum() if consumed_col and consumed_col in account_data.columns else 0
                
                account_analysis.append({
                    "Account": account,
                    "Year": year,
                    "Budget": budget,
                    "Consumed": consumed,
                    "Utilization %": (consumed / budget * 100) if budget > 0 else 0,
                    "Cost Centers": account_data["Cost Center Name"].nunique()
                })
    
    if account_analysis:
        account_df = pd.DataFrame(account_analysis)
        
        # Account performance visualization
        col1, col2 = st.columns(2)
        
        with col1:
            # Top accounts by budget
            top_accounts = account_df.groupby("Account")["Budget"].sum().sort_values(ascending=False).head(15)
            
            fig1 = px.bar(
                x=top_accounts.index,
                y=top_accounts.values,
                title="Top 15 Accounts by Budget Allocation",
                labels={"x": "Account", "y": "Total Budget"}
            )
            fig1.update_xaxes(tickangle=45)
            st.plotly_chart(fig1, use_container_width=True)
        
        with col2:
            # Account utilization distribution
            latest_year_accounts = account_df[account_df["Year"] == selected_years[0]] if selected_years else account_df
            
            fig2 = px.histogram(
                latest_year_accounts,
                x="Utilization %",
                nbins=20,
                title="Account Utilization Distribution",
                labels={"count": "Number of Accounts"}
            )
            fig2.add_vline(x=80, line_dash="dash", line_color="red", annotation_text="Target")
            st.plotly_chart(fig2, use_container_width=True)
        
        # Account efficiency heatmap
        if len(selected_years) > 1:
            st.subheader("🔥 Account Efficiency Heatmap")
            
            # Prepare data for heatmap
            heatmap_data = account_df.pivot_table(
                index="Account",
                columns="Year", 
                values="Utilization %",
                fill_value=0
            )
            
            # Limit to top 20 accounts for readability
            top_20_accounts = account_df.groupby("Account")["Budget"].sum().sort_values(ascending=False).head(20).index
            heatmap_data_limited = heatmap_data.loc[heatmap_data.index.isin(top_20_accounts)]
            
            fig3 = px.imshow(
                heatmap_data_limited.values,
                labels=dict(x="Year", y="Account", color="Utilization %"),
                x=heatmap_data_limited.columns,
                y=heatmap_data_limited.index,
                color_continuous_scale="RdYlGn",
                title="Account Utilization Efficiency Over Years"
            )
            fig3.update_layout(height=600)
            st.plotly_chart(fig3, use_container_width=True)

def show_time_series_analysis(df, col_manager, selected_years):
    """Advanced time series analysis"""
    st.subheader("⏱️ Time Series Analysis")
    
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"])
        
        # Monthly trend analysis
        monthly_data = []
        for year in selected_years:
            budget_col = col_manager.get_budget_column(year)
            consumed_col = col_manager.get_consumed_column(year)
            
            if budget_col and budget_col in df.columns:
                year_data = df[df["Year"] == int(year)]
                
                # Group by month
                year_data["Month"] = year_data["Date"].dt.month
                monthly_summary = year_data.groupby("Month").agg({
                    budget_col: "sum",
                    consumed_col: "sum" if consumed_col and consumed_col in year_data.columns else lambda x: 0
                }).reset_index()
                
                monthly_summary["Year"] = year
                monthly_summary["Budget"] = monthly_summary[budget_col]
                monthly_summary["Consumed"] = monthly_summary[consumed_col] if consumed_col and consumed_col in monthly_summary.columns else 0
                
                monthly_data.append(monthly_summary[["Month", "Year", "Budget", "Consumed"]])
        
        if monthly_data:
            monthly_df = pd.concat(monthly_data, ignore_index=True)
            monthly_df["Month_Year"] = monthly_df["Month"].astype(str) + "/" + monthly_df["Year"].astype(str)
            
            # Time series visualization
            fig = px.line(
                monthly_df,
                x="Month_Year",
                y=["Budget", "Consumed"],
                title="Monthly Budget vs Consumption Trends",
                markers=True
            )
            fig.update_xaxes(tickangle=45)
            st.plotly_chart(fig, use_container_width=True)
        
        # Seasonal analysis
        show_seasonal_analysis(df, col_manager, selected_years)

def show_seasonal_analysis(df, col_manager, selected_years):
    """Seasonal spending pattern analysis"""
    st.subheader("🌟 Seasonal Analysis")
    
    seasonal_data = []
    for year in selected_years:
        consumed_col = col_manager.get_consumed_column(year)
        if consumed_col and consumed_col in df.columns:
            year_data = df[df["Year"] == int(year)]
            quarterly_summary = year_data.groupby("Quarter")[consumed_col].sum().reset_index()
            quarterly_summary["Year"] = year
            quarterly_summary["Consumed"] = quarterly_summary[consumed_col]
            seasonal_data.append(quarterly_summary[["Quarter", "Year", "Consumed"]])
    
    if seasonal_data:
        seasonal_df = pd.concat(seasonal_data, ignore_index=True)
        
        fig = px.bar(
            seasonal_df,
            x="Quarter",
            y="Consumed",
            color="Year",
            title="Quarterly Spending Patterns",
            barmode="group"
        )
        st.plotly_chart(fig, use_container_width=True)

def show_performance_matrix(df, col_manager, selected_years):
    """Advanced performance matrix analysis"""
    st.subheader("📊 Performance Matrix Analysis")
    
    # Create performance quadrants
    current_year = selected_years[0] if selected_years else col_manager.available_years[0]
    budget_col = col_manager.get_budget_column(current_year)
    consumed_col = col_manager.get_consumed_column(current_year)
    
    if budget_col and budget_col in df.columns:
        # Cost center performance matrix
        cc_performance = df.groupby("Cost Center Name").agg({
            budget_col: "sum",
            consumed_col: "sum" if consumed_col and consumed_col in df.columns else lambda x: 0
        }).reset_index()
        
        cc_performance["Budget"] = cc_performance[budget_col]
        cc_performance["Consumed"] = cc_performance[consumed_col] if consumed_col and consumed_col in cc_performance.columns else 0
        cc_performance["Utilization %"] = (cc_performance["Consumed"] / cc_performance["Budget"] * 100).fillna(0)
        
        # Calculate median values for quadrant division
        median_budget = cc_performance["Budget"].median()
        median_utilization = cc_performance["Utilization %"].median()
        
        # Create quadrant classifications
        cc_performance["Quadrant"] = cc_performance.apply(
            lambda row: classify_performance_quadrant(row["Budget"], row["Utilization %"], median_budget, median_utilization),
            axes=1
        )
        
        # Performance matrix scatter plot
        fig = px.scatter(
            cc_performance,
            x="Budget",
            y="Utilization %",
            size="Consumed",
            color="Quadrant",
            title="Cost Center Performance Matrix",
            hover_data=["Cost Center Name"],
            color_discrete_map={
                "High Budget - High Utilization": "#2E8B57",
                "High Budget - Low Utilization": "#FFD700", 
                "Low Budget - High Utilization": "#FF6347",
                "Low Budget - Low Utilization": "#708090"
            }
        )
        
        # Add quadrant lines
        fig.add_hline(y=median_utilization, line_dash="dash", line_color="gray")
        fig.add_vline(x=median_budget, line_dash="dash", line_color="gray")
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Quadrant analysis summary
        show_quadrant_summary(cc_performance)

def classify_performance_quadrant(budget, utilization, median_budget, median_utilization):
    """Classify performance into quadrants"""
    if budget >= median_budget and utilization >= median_utilization:
        return "High Budget - High Utilization"
    elif budget >= median_budget and utilization < median_utilization:
        return "High Budget - Low Utilization"
    elif budget < median_budget and utilization >= median_utilization:
        return "Low Budget - High Utilization"
    else:
        return "Low Budget - Low Utilization"

def show_quadrant_summary(performance_df):
    """Display quadrant analysis summary"""
    st.subheader("🎯 Quadrant Analysis")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**High Budget - High Utilization (Stars)**")
        stars = performance_df[performance_df["Quadrant"] == "High Budget - High Utilization"]
        if not stars.empty:
            for _, row in stars.iterrows():
                st.write(f"⭐ {row['Cost Center Name']}: ${row['Budget']:,.0f} ({row['Utilization %']:.1f}%)")
        else:
            st.write("No cost centers in this quadrant")
        
        st.write("**Low Budget - High Utilization (Efficient)**")
        efficient = performance_df[performance_df["Quadrant"] == "Low Budget - High Utilization"]
        if not efficient.empty:
            for _, row in efficient.iterrows():
                st.write(f"💪 {row['Cost Center Name']}: ${row['Budget']:,.0f} ({row['Utilization %']:.1f}%)")
        else:
            st.write("No cost centers in this quadrant")
    
    with col2:
        st.write("**High Budget - Low Utilization (Question Marks)**")
        questions = performance_df[performance_df["Quadrant"] == "High Budget - Low Utilization"]
        if not questions.empty:
            for _, row in questions.iterrows():
                st.write(f"❓ {row['Cost Center Name']}: ${row['Budget']:,.0f} ({row['Utilization %']:.1f}%)")
        else:
            st.write("No cost centers in this quadrant")
            
        st.write("**Low Budget - Low Utilization (Dogs)**")
        dogs = performance_df[performance_df["Quadrant"] == "Low Budget - Low Utilization"]
        if not dogs.empty:
            for _, row in dogs.iterrows():
                st.write(f"🐕 {row['Cost Center Name']}: ${row['Budget']:,.0f} ({row['Utilization %']:.1f}%)")
        else:
            st.write("No cost centers in this quadrant")

def show_budget_distribution_analysis(df, col_manager, year):
    """Comprehensive budget distribution analysis"""
    st.subheader("🥧 Budget Distribution Analysis")
    
    budget_col = col_manager.get_budget_column(year)
    if not budget_col or budget_col not in df.columns:
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Cost center distribution with Pareto analysis
        cc_budget = df.groupby("Cost Center Name")[budget_col].sum().sort_values(ascending=False)
        cc_budget_pct = (cc_budget / cc_budget.sum() * 100).cumsum()
        
        fig1 = go.Figure()
        fig1.add_trace(go.Bar(
            x=cc_budget.index,
            y=cc_budget.values,
            name="Budget",
            yaxes="y"
        ))
        fig1.add_trace(go.Scatter(
            x=cc_budget.index,
            y=cc_budget_pct.values,
            name="Cumulative %",
            yaxes="y2",
            mode="lines+markers",
            line=dict(color="red")
        ))
        
        fig1.update_layout(
            title="Budget Distribution with Pareto Analysis",
            xaxes_tickangle=-45,
            yaxes=dict(title="Budget Amount"),
            yaxes2=dict(title="Cumulative %", overlaying="y", side="right"),
            height=400
        )
        st.plotly_chart(fig1, use_container_width=True)
    
    with col2:
        # Account distribution treemap
        account_budget = df.groupby(["Cost Center Name", "Account name"])[budget_col].sum().reset_index()
        
        fig2 = px.treemap(
            account_budget,
            path=["Cost Center Name", "Account name"],
            values=budget_col,
            title="Budget Allocation Hierarchy"
        )
        fig2.update_layout(height=400)
        st.plotly_chart(fig2, use_container_width=True)

def show_summary_tab(df, col_manager):
    """Enhanced summary tab with comprehensive insights"""
    st.subheader("📋 Executive Summary")
    
    # Executive KPI Dashboard
    show_executive_summary(df, col_manager)
    
    # Strategic insights
    show_strategic_insights(df, col_manager)
    
    # Recommendations
    show_recommendations(df, col_manager)

def show_executive_summary(df, col_manager):
    """Executive level summary with key metrics"""
    st.subheader("🎯 Executive Dashboard")
    
    current_year = col_manager.available_years[0] if col_manager.available_years else str(CURRENT_YEAR)
    budget_col = col_manager.get_budget_column(current_year)
    consumed_col = col_manager.get_consumed_column(current_year)
    
    if budget_col and budget_col in df.columns:
        total_budget = df[budget_col].sum()
        total_consumed = df[consumed_col].sum() if consumed_col and consumed_col in df.columns else 0
        utilization_rate = (total_consumed / total_budget * 100) if total_budget > 0 else 0
        
        # Executive metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Portfolio Value",
                f"${total_budget:,.0f}",
                help="Total budget under management"
            )
        
        with col2:
            st.metric(
                "Deployment Rate", 
                f"{utilization_rate:.1f}%",
                help="Overall budget utilization"
            )
        
        with col3:
            efficiency_score = calculate_efficiency_score(df, col_manager, current_year)
            st.metric(
                "Efficiency Score",
                f"{efficiency_score:.1f}/100",
                help="Composite efficiency rating"
            )
        
        with col4:
            risk_level = assess_risk_level(df, col_manager, current_year)
            st.metric(
                "Risk Level",
                risk_level,
                help="Budget management risk assessment"
            )

def calculate_efficiency_score(df, col_manager, year):
    """Calculate composite efficiency score"""
    budget_col = col_manager.get_budget_column(year)
    consumed_col = col_manager.get_consumed_column(year)
    if not budget_col or budget_col not in df.columns:
        return 0
    total_budget = df[budget_col].sum()
    total_consumed = df[consumed_col].sum() if consumed_col and consumed_col in df.columns else 0
    utilization = (total_consumed / total_budget * 100) if total_budget > 0 else 0

    # Score: 50% utilization efficiency, 50% budget balance
    score = (min(utilization, 100) * 0.5) + ((total_budget - total_consumed) / total_budget * 100 * 0.5)
    return round(score, 1)

def assess_risk_level(df, col_manager, year):
    """Assess overall risk level based on utilization and budget balance"""
    budget_col = col_manager.get_budget_column(year)
    consumed_col = col_manager.get_consumed_column(year)
    if not budget_col or budget_col not in df.columns:
        return "Unknown"
    total_budget = df[budget_col].sum()
    total_consumed = df[consumed_col].sum() if consumed_col and consumed_col in df.columns else 0
    utilization = (total_consumed / total_budget * 100) if total_budget > 0 else 0

    if utilization > 95:
        return "High"
    elif utilization > 70:
        return "Moderate"
    else:
        return "Low"

def show_strategic_insights(df, col_manager):
    """Highlight strategic insights"""
    st.subheader("💡 Strategic Insights")
    if "Current_Budget" in df.columns and "Current_Consumed" in df.columns:
        df["Utilization %"] = (df["Current_Consumed"] / df["Current_Budget"] * 100).fillna(0)
        top_utilized = df.sort_values("Utilization %", ascending=False).head(5)
        st.markdown("**Top 5 Cost Centers by Utilization:**")
        for idx, row in top_utilized.iterrows():
            st.write(f"- {row['Cost Center Display']}: {row['Utilization %']:.1f}%")
        
        under_utilized = df.sort_values("Utilization %").head(5)
        st.markdown("**Top 5 Under-utilized Cost Centers:**")
        for idx, row in under_utilized.iterrows():
            st.write(f"- {row['Cost Center Display']}: {row['Utilization %']:.1f}%")

def show_filtered_dashboard_dynamic():
    """Main dashboard function with complete dynamic year support"""
    st.title("📊 Dynamic Budget Dashboard")

    # File upload section
    if create_file_upload_section():
        st.success("Using uploaded file for analysis")
    else:
        st.info("Using default Excel file for analysis")

    # Load data with dynamic column detection
    df, cost_center_names, cost_center_numbers, account_names, account_numbers, col_manager = load_budget_data_dynamic()
    
    if df.empty or not col_manager:
        st.warning("No data available to display.")
        st.info("Please upload a valid Excel file or check your data source.")
        return

    # Display available years info
    st.info(f"📅 Available budget years: {', '.join(col_manager.available_years)}")
    
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
            st.metric("Budget Years", len(col_manager.budget_cols))

    # Enhanced Expense Logging Section
    with st.expander("➕ Log New Expense", expanded=False):
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
                                current_budget_col = col_manager.get_budget_column()
                                
                                if current_budget_col:
                                    budget_amount = match[current_budget_col].iloc[0] if current_budget_col in match.columns else 0
                                    consumed_before = match['Current_Consumed'].iloc[0] if 'Current_Consumed' in match.columns else 0
                                    available_before = match['Current_Available'].iloc[0] if 'Current_Available' in match.columns else budget_amount
                                    
                                    # Display current status
                                    st.markdown("**📈 Current Budget Status:**")
                                    col1, col2, col3 = st.columns(3)
                                    with col1:
                                        st.metric(f"{CURRENT_YEAR} Budget", f"${budget_amount:,.2f}")
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
                                    
                                    # Form submission
                                    submit = st.form_submit_button("📝 Log Expense", type="primary")
                                    
                                    if submit and consumed_now > 0:
                                        try:
                                            new_consumed_total = consumed_before + consumed_now
                                            available_after = budget_amount - new_consumed_total
                                            
                                            # Create row data with all year columns
                                            row_data = {
                                                "Cost Center Number": selected_cc_number,
                                                "Cost Center Name": selected_cc_name,
                                                "Account number": selected_acc_number,
                                                "Account name": selected_acc_name,
                                                "Date": expense_date,
                                                "Quarter": get_quarter_from_date(pd.Timestamp(expense_date)),
                                                "Year": expense_date.year,
                                                "Current_Consumed": new_consumed_total,
                                                "Current_Available": available_after,
                                                "Consumed Amount": new_consumed_total,
                                                "Available Amount": available_after,
                                            }
                                            
                                            # Add all budget columns
                                            for year, col in col_manager.budget_cols.items():
                                                if col in match.columns:
                                                    row_data[col] = match[col].iloc[0]
                                            
                                            # Update the consumed column for current year
                                            current_consumed_col = col_manager.get_consumed_column()
                                            if current_consumed_col:
                                                row_data[current_consumed_col] = new_consumed_total
                                            
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

    # TABS SECTION - MOVED TO THE CORRECT PLACE
    st.markdown("---")
    tab1, tab2, tab3 = st.tabs(["📊 Analysis Dashboard", "📋 Summary & Insights", "📈 Advanced Analytics"])
    
    with tab1:
        show_analysis_dashboard_dynamic(df, col_manager, cost_center_names, account_names)
    
    with tab2:
        show_summary_tab(df, col_manager)
    
    with tab3:
        st.subheader("📈 Advanced Analytics")
        st.info("Advanced analytics features available")
        # Call your existing functions here if you have them
# Keep the original function name for backward compatibility

def show_current_analysis_tab(df, col_manager):
    """Current year analysis tab"""
    current_budget_col = col_manager.get_budget_column() or col_manager.get_latest_budget_column()
    
    if current_budget_col and current_budget_col in df.columns:
        # Budget distribution
        col1, col2 = st.columns(2)
        
        with col1:
            cc_distribution = df.groupby("Cost Center Name")[current_budget_col].sum()
            fig = px.pie(
                values=cc_distribution.values,
                names=cc_distribution.index,
                title=f"Budget Distribution by Cost Center ({col_manager.current_year_str})",
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            account_distribution = df.groupby("Account name")[current_budget_col].sum().head(10)
            fig = px.pie(
                values=account_distribution.values,
                names=account_distribution.index,
                title=f"Top 10 Accounts by Budget ({col_manager.current_year_str})",
            )
            st.plotly_chart(fig, use_container_width=True)

def show_recommendations(df, col_manager):
    """Provide actionable recommendations"""
    st.subheader("📝 Recommendations")
    if "Current_Budget" in df.columns and "Current_Consumed" in df.columns:
        df["Utilization %"] = (df["Current_Consumed"] / df["Current_Budget"] * 100).fillna(0)
        high_risk = df[df["Utilization %"] > 90]
        low_risk = df[df["Utilization %"] < 50]
        
        st.markdown("**High Utilization (Monitor Closely):**")
        for idx, row in high_risk.iterrows():
            st.write(f"- {row['Cost Center Display']}: {row['Utilization %']:.1f}% used")
        
        st.markdown("**Low Utilization (Reallocate Resources):**")
        for idx, row in low_risk.iterrows():
            st.write(f"- {row['Cost Center Display']}: {row['Utilization %']:.1f}% used")

def show_historical_trends_tab(df, col_manager):
    """Historical trends analysis tab"""
    if len(col_manager.available_years) >= 2:
        # Multi-year comparison by cost center
        cost_centers = df["Cost Center Name"].unique()[:5]  # Top 5 for readability
        
        trend_data = []
        for cc in cost_centers:
            cc_data = df[df["Cost Center Name"] == cc]
            for year in col_manager.available_years:
                budget_col = col_manager.get_budget_column(year)
                if budget_col and budget_col in cc_data.columns:
                    total = cc_data[budget_col].sum()
                    trend_data.append({
                        "Cost Center": cc,
                        "Year": year,
                        "Budget": total
                    })
        
        if trend_data:
            trend_df = pd.DataFrame(trend_data)
            fig = px.line(
                trend_df,
                x="Year",
                y="Budget",
                color="Cost Center",
                title="Budget Trends by Cost Center",
                markers=True
            )
            st.plotly_chart(fig, use_container_width=True)

def show_insights_tab(df, col_manager):
    """Insights and recommendations tab"""
    current_budget_col = col_manager.get_budget_column() or col_manager.get_latest_budget_column()
    
    if current_budget_col and current_budget_col in df.columns:
        total_budget = df[current_budget_col].sum()
        total_consumed = df['Current_Consumed'].sum()
        utilization_rate = (total_consumed / total_budget * 100) if total_budget > 0 else 0
        
        # Key insights
        st.subheader("💡 Key Insights")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Budget Efficiency:**")
            if utilization_rate > 80:
                st.success(f"High utilization rate ({utilization_rate:.1f}%) - Effective budget management")
            elif utilization_rate > 60:
                st.info(f"Moderate utilization rate ({utilization_rate:.1f}%) - Room for optimization")
            else:
                st.warning(f"Low utilization rate ({utilization_rate:.1f}%) - Consider budget reallocation")
        
        with col2:
            st.write("**Data Coverage:**")
            st.info(f"Analysis covers {len(col_manager.available_years)} years: {', '.join(col_manager.available_years)}")
            st.info(f"Current analysis based on {col_manager.current_year_str} data")


# Keep your existing optimizer function unchanged
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


def show_summary_tab(df, col_manager):
    """Display comprehensive summary and insights with dynamic column support"""
    st.header("📋 Summary & Insights")
    
    # Overall statistics
    st.subheader("📊 Overall Statistics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Cost Centers", df["Cost Center Name"].nunique())
        st.metric("Total Accounts", df["Account name"].nunique())
        st.metric("Total Records", len(df))
    
    with col2:
        # Dynamic year budget totals - show up to 3 available years
        for i, year in enumerate(col_manager.available_years[:3]):
            budget_col = col_manager.get_budget_column(year)
            if budget_col and budget_col in df.columns:
                total = df[budget_col].sum()
                st.metric(f"{year} Total Budget", f"{total:,.0f}")
    
    with col3:
        # Use dynamic consumed and available columns
        consumed_total = df['Current_Consumed'].sum() if 'Current_Consumed' in df.columns else 0
        available_total = df['Current_Available'].sum() if 'Current_Available' in df.columns else 0
        
        st.metric("Total Consumed", f"{consumed_total:,.0f}")
        st.metric("Total Available", f"{available_total:,.0f}")
        
        # Calculate utilization rate using current year budget
        current_budget_col = col_manager.get_budget_column()
        if current_budget_col and current_budget_col in df.columns:
            current_budget_total = df[current_budget_col].sum()
            utilization_rate = (consumed_total / current_budget_total * 100) if current_budget_total > 0 else 0
        else:
            utilization_rate = 0
            
        st.metric("Utilization Rate", f"{utilization_rate:.1f}%")
    
    with col4:
        if "Quarter" in df.columns:
            st.metric("Q1 Records", len(df[df["Quarter"] == "Q1"]))
            st.metric("Q2 Records", len(df[df["Quarter"] == "Q2"]))
            st.metric("Q3 Records", len(df[df["Quarter"] == "Q3"]))
            st.metric("Q4 Records", len(df[df["Quarter"] == "Q4"]))
        else:
            st.metric("Date Range", "N/A")
            st.metric("Latest Update", "N/A")
            st.metric("Data Quality", "Good")
    
    st.markdown("---")
    
    # Report Generation Button - use dynamic report function
    st.subheader("📄 Generate Report")
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        if st.button("📊 Generate Comprehensive Report", type="primary", use_container_width=True):
            with st.spinner("Generating report..."):
                # Use the dynamic report function
                buffer = generate_report(df, col_manager)
                if buffer:
                    st.success("Report generated successfully!")
                    
                    # Create download link
                    filename = f"GASCO_Budget_Report_{CURRENT_YEAR}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                    download_link = get_download_link(buffer, filename)
                    st.markdown(download_link, unsafe_allow_html=True)
                    
                    st.info("📋 Report includes:")
                    st.write("• Executive Summary")
                    st.write("• Key Performance Metrics")
                    st.write("• Top Performers Analysis")
                    st.write("• Year-over-Year Trends")
                    st.write("• Quarterly Analysis")
                    st.write("• Cost Center Breakdown")
                    st.write("• Key Insights & Recommendations")
                else:
                    st.error("Failed to generate report. Please try again.")
    
    st.markdown("---")
    
    # Top performers - use current year budget column
    st.subheader("🏆 Top Performers")
    
    col1, col2 = st.columns(2)
    
    current_budget_col = col_manager.get_budget_column() or col_manager.get_latest_budget_column()
    
    with col1:
        if current_budget_col and current_budget_col in df.columns:
            # Top cost centers by budget
            top_cc_budget = df.groupby("Cost Center Name")[current_budget_col].sum().sort_values(ascending=False).head(5)
            st.write(f"**Top 5 Cost Centers by Budget ({col_manager.current_year_str}):**")
            for i, (cc, budget) in enumerate(top_cc_budget.items(), 1):
                st.write(f"{i}. {cc}: {budget:,.0f}")
    
    with col2:
        if current_budget_col and current_budget_col in df.columns:
            # Top accounts by budget
            top_accounts_budget = df.groupby("Account name")[current_budget_col].sum().sort_values(ascending=False).head(5)
            st.write(f"**Top 5 Accounts by Budget ({col_manager.current_year_str}):**")
            for i, (account, budget) in enumerate(top_accounts_budget.items(), 1):
                st.write(f"{i}. {account}: {budget:,.0f}")
    
    st.markdown("---")
    
    # Budget distribution - use current year
    st.subheader("📊 Budget Distribution")
    
    col1, col2 = st.columns(2)
    
    if current_budget_col and current_budget_col in df.columns:
        with col1:
            # Cost center distribution
            cc_distribution = df.groupby("Cost Center Name")[current_budget_col].sum()
            fig = px.pie(values=cc_distribution.values, names=cc_distribution.index,
                         title=f"Budget Distribution by Cost Center ({col_manager.current_year_str})")
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Account distribution
            account_distribution = df.groupby("Account name")[current_budget_col].sum().head(10)
            fig = px.pie(values=account_distribution.values, names=account_distribution.index,
                         title=f"Top 10 Accounts by Budget ({col_manager.current_year_str})")
            st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # Year-over-year trends - dynamic years
    st.subheader("📈 Year-over-Year Trends")
    
    # Calculate trends for available years
    year_totals = {}
    for year in col_manager.available_years:
        budget_col = col_manager.get_budget_column(year)
        if budget_col and budget_col in df.columns:
            year_totals[year] = df[budget_col].sum()
    
    if len(year_totals) >= 2:
        sorted_years = sorted(year_totals.keys())
        
        # Calculate growth rates
        growth_rates = {}
        for i in range(1, len(sorted_years)):
            current_year = sorted_years[i]
            previous_year = sorted_years[i-1]
            current_total = year_totals[current_year]
            previous_total = year_totals[previous_year]
            growth = ((current_total - previous_total) / previous_total * 100) if previous_total > 0 else 0
            growth_rates[f"{previous_year}_to_{current_year}"] = growth
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            for year in sorted_years:
                st.metric(f"{year} Total", f"{year_totals[year]:,.0f}")
        
        with col2:
            for key, growth in list(growth_rates.items())[:3]:  # Show up to 3 growth rates
                years = key.replace('_to_', ' to ')
                st.metric(f"{years} Growth", f"{growth:+.1f}%", 
                         delta=f"{'Increase' if growth > 0 else 'Decrease'}")
        
        with col3:
            # Budget trend chart
            trend_data = pd.DataFrame({
                'Year': sorted_years,
                'Budget': [year_totals[year] for year in sorted_years]
            })
            fig = px.line(trend_data, x='Year', y='Budget', 
                         title="Budget Trend Over Years", markers=True)
            st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # Quarterly analysis (if available) - use current year
    if "Quarter" in df.columns and current_budget_col and current_budget_col in df.columns:
        st.subheader("📅 Quarterly Analysis")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Quarterly distribution
            quarterly_dist = df.groupby("Quarter")[current_budget_col].sum()
            fig = px.bar(x=quarterly_dist.index, y=quarterly_dist.values,
                        title=f"Budget Distribution by Quarter ({col_manager.current_year_str})",
                        color=quarterly_dist.index,
                        color_discrete_map={'Q1': '#1f77b4', 'Q2': '#ff7f0e', 'Q3': '#2ca02c', 'Q4': '#d62728'})
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Quarterly summary table
            quarterly_summary = df.groupby("Quarter").agg({
                current_budget_col: "sum",
                "Cost Center Name": "nunique",
                "Account name": "nunique"
            }).round(0)
            quarterly_summary.columns = ["Total Budget", "Cost Centers", "Accounts"]
            st.write("**Quarterly Summary:**")
            st.dataframe(quarterly_summary, use_container_width=True)
    
    st.markdown("---")
    
    # Key insights
    st.subheader("💡 Key Insights")
    
    # Budget efficiency
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Budget Efficiency:**")
        if utilization_rate > 80:
            st.success(f"High utilization rate ({utilization_rate:.1f}%) - Budget is being used effectively")
        elif utilization_rate > 60:
            st.info(f"Moderate utilization rate ({utilization_rate:.1f}%) - Room for optimization")
        else:
            st.warning(f"Low utilization rate ({utilization_rate:.1f}%) - Consider budget reallocation")
        
        # Growth insights - use latest available growth
        st.write("**Growth Analysis:**")
        if len(year_totals) >= 2:
            latest_years = sorted(year_totals.keys())[-2:]
            latest_growth = ((year_totals[latest_years[1]] - year_totals[latest_years[0]]) / 
                           year_totals[latest_years[0]] * 100) if year_totals[latest_years[0]] > 0 else 0
            if latest_growth > 0:
                st.success(f"Budget increased by {latest_growth:.1f}% from {latest_years[0]} to {latest_years[1]}")
            else:
                st.warning(f"Budget decreased by {abs(latest_growth):.1f}% from {latest_years[0]} to {latest_years[1]}")
    
    with col2:
        if current_budget_col and current_budget_col in df.columns:
            # Top cost center insights
            top_cc = df.groupby("Cost Center Name")[current_budget_col].sum().idxmax()
            top_cc_budget = df.groupby("Cost Center Name")[current_budget_col].sum().max()
            st.write("**Top Cost Center:**")
            st.write(f"**{top_cc}** with {top_cc_budget:,.0f} budget allocation")
            
            # Top account insights
            top_account = df.groupby("Account name")[current_budget_col].sum().idxmax()
            top_account_budget = df.groupby("Account name")[current_budget_col].sum().max()
            st.write("**Top Account:**")
            st.write(f"**{top_account}** with {top_account_budget:,.0f} budget allocation")
    
    st.markdown("---")
    
    # Key Factors & Top Indicators
    st.subheader("🎯 Key Factors & Top Indicators")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Key Performance Indicators
        st.write("**📊 Top Performance Indicators:**")
        
        # Budget efficiency indicator
        if utilization_rate >= 90:
            st.success(f"🔥 Excellent Efficiency: {utilization_rate:.1f}%")
        elif utilization_rate >= 75:
            st.info(f"✅ Good Efficiency: {utilization_rate:.1f}%")
        elif utilization_rate >= 50:
            st.warning(f"⚠️ Moderate Efficiency: {utilization_rate:.1f}%")
        else:
            st.error(f"❌ Low Efficiency: {utilization_rate:.1f}%")
        
        # Growth indicator (use latest available)
        if len(year_totals) >= 2:
            latest_years = sorted(year_totals.keys())[-2:]
            latest_growth = ((year_totals[latest_years[1]] - year_totals[latest_years[0]]) / 
                           year_totals[latest_years[0]] * 100) if year_totals[latest_years[0]] > 0 else 0
            
            if latest_growth >= 10:
                st.success(f"🚀 Strong Growth: +{latest_growth:.1f}%")
            elif latest_growth >= 5:
                st.info(f"📈 Positive Growth: +{latest_growth:.1f}%")
            elif latest_growth >= 0:
                st.warning(f"📊 Stable: {latest_growth:.1f}%")
            else:
                st.error(f"📉 Declining: {latest_growth:.1f}%")
        
        # Cost center diversity
        cc_count = df["Cost Center Name"].nunique()
        if cc_count >= 10:
            st.success(f"🏢 High Diversity: {cc_count} Cost Centers")
        elif cc_count >= 5:
            st.info(f"🏢 Moderate Diversity: {cc_count} Cost Centers")
        else:
            st.warning(f"🏢 Low Diversity: {cc_count} Cost Centers")
    
    with col2:
        # Key Risk Factors - use dynamic columns
        st.write("**⚠️ Key Risk Factors:**")
        
        if current_budget_col and current_budget_col in df.columns:
            # Budget overrun risk
            overrun_risk = (df['Current_Consumed'] > df[current_budget_col]).sum()
            if overrun_risk > 0:
                st.error(f"🚨 Budget Overrun Risk: {overrun_risk} items")
            else:
                st.success("✅ No Budget Overrun Risk")
            
            # Low utilization risk
            low_util_mask = (df['Current_Consumed'] / df[current_budget_col] < 0.3) & (df[current_budget_col] > 0)
            low_util_risk = low_util_mask.sum()
            if low_util_risk > 0:
                st.warning(f"⚠️ Low Utilization Risk: {low_util_risk} items")
            else:
                st.success("✅ Good Utilization Across All Items")
            
            # Zero budget risk
            zero_budget_risk = len(df[df[current_budget_col] == 0])
            if zero_budget_risk > 0:
                st.error(f"❌ Zero Budget Items: {zero_budget_risk}")
            else:
                st.success("✅ All Items Have Budget Allocation")
    
    st.markdown("---")
    
    # Budget Alarms & Remaining Analysis - use dynamic columns
    st.subheader("🚨 Budget Alarms & Remaining Analysis")
    
    col1, col2 = st.columns(2)
    
    if current_budget_col and current_budget_col in df.columns:
        with col1:
            # Critical alarms
            st.write("**🚨 Critical Alarms:**")
            
            # High consumption alarms
            high_consumption = df[(df[current_budget_col] > 0) & (df['Current_Consumed'] / df[current_budget_col] > 0.9)]
            if len(high_consumption) > 0:
                st.error(f"🔥 High Consumption Alert: {len(high_consumption)} items >90% consumed")
                for _, row in high_consumption.head(3).iterrows():
                    consumption_pct = row['Current_Consumed']/row[current_budget_col]*100
                    st.write(f"• {row['Cost Center Name']} - {row['Account name']}: {consumption_pct:.1f}%")
            else:
                st.success("✅ No High Consumption Alarms")
            
            # Budget depletion alarms
            depleted_budget = df[df['Current_Available'] < df[current_budget_col] * 0.1]
            if len(depleted_budget) > 0:
                st.error(f"💸 Budget Depletion Alert: {len(depleted_budget)} items <10% remaining")
            else:
                st.success("✅ No Budget Depletion Alarms")
        
        with col2:
            # Remaining budget analysis
            st.write("**💰 Remaining Budget Analysis:**")
            
            total_remaining = df['Current_Available'].sum()
            avg_remaining = df['Current_Available'].mean()
            
            st.metric("Total Remaining", f"{total_remaining:,.0f}")
            st.metric("Average Remaining", f"{avg_remaining:,.0f}")
            
            # Remaining by cost center
            remaining_by_cc = df.groupby("Cost Center Name")['Current_Available'].sum().sort_values(ascending=False)
            st.write("**Top 3 Cost Centers by Remaining Budget:**")
            for i, (cc, remaining) in enumerate(remaining_by_cc.head(3).items(), 1):
                st.write(f"{i}. {cc}: {remaining:,.0f}")
    
    st.markdown("---")
    
    # Insights Comparison (Increase/Decrease Analysis) - use dynamic columns
    st.subheader("📈📉 Insights Comparison")
    
    col1, col2 = st.columns(2)
    
    if current_budget_col and current_budget_col in df.columns:
        with col1:
            st.write("**📈 Positive Trends:**")
            
            # Budget increases
            if len(year_totals) >= 2:
                latest_years = sorted(year_totals.keys())[-2:]
                latest_growth = ((year_totals[latest_years[1]] - year_totals[latest_years[0]]) / 
                               year_totals[latest_years[0]] * 100) if year_totals[latest_years[0]] > 0 else 0
                if latest_growth > 0:
                    st.success(f"✅ Budget Growth: +{latest_growth:.1f}% increase")
            
            # High performers
            top_performers = df.groupby("Cost Center Name")[current_budget_col].sum().sort_values(ascending=False).head(3)
            st.write("🏆 Top 3 Budget Allocations:")
            for i, (cc, budget) in enumerate(top_performers.items(), 1):
                st.write(f"{i}. {cc}: {budget:,.0f}")
            
            # Efficient utilization
            efficient_cc = df.groupby("Cost Center Name").apply(
                lambda x: (x['Current_Consumed'].sum() / x[current_budget_col].sum() * 100) if x[current_budget_col].sum() > 0 else 0
            ).sort_values(ascending=False).head(3)
            
            st.write("⚡ Most Efficient Cost Centers:")
            for i, (cc, efficiency) in enumerate(efficient_cc.items(), 1):
                st.write(f"{i}. {cc}: {efficiency:.1f}% utilization")
        
        with col2:
            st.write("**📉 Areas of Concern:**")
            
            # Budget decreases
            if len(year_totals) >= 2:
                latest_years = sorted(year_totals.keys())[-2:]
                latest_growth = ((year_totals[latest_years[1]] - year_totals[latest_years[0]]) / 
                               year_totals[latest_years[0]] * 100) if year_totals[latest_years[0]] > 0 else 0
                if latest_growth < 0:
                    st.error(f"📉 Budget Decline: {abs(latest_growth):.1f}% decrease")
            
            # Low performers
            low_performers = df.groupby("Cost Center Name")[current_budget_col].sum().sort_values().head(3)
            st.write("🔻 Lowest Budget Allocations:")
            for i, (cc, budget) in enumerate(low_performers.items(), 1):
                st.write(f"{i}. {cc}: {budget:,.0f}")
            
            # Inefficient utilization
            inefficient_cc = df.groupby("Cost Center Name").apply(
                lambda x: (x['Current_Consumed'].sum() / x[current_budget_col].sum() * 100) if x[current_budget_col].sum() > 0 else 0
            ).sort_values().head(3)
            
            st.write("🐌 Least Efficient Cost Centers:")
            for i, (cc, efficiency) in enumerate(inefficient_cc.items(), 1):
                if efficiency > 0:
                    st.write(f"{i}. {cc}: {efficiency:.1f}% utilization")
                else:
                    st.write(f"{i}. {cc}: No consumption")
    
    # Year-over-year comparison insights - dynamic
    if len(year_totals) >= 2:
        st.markdown("---")
        st.subheader("📊 Year-over-Year Comparison Insights")
        
        sorted_years = sorted(year_totals.keys())
        cols = st.columns(min(3, len(sorted_years)-1))  # Create columns for comparisons
        
        for i in range(len(sorted_years)-1):
            current_year = sorted_years[i+1]
            previous_year = sorted_years[i]
            growth = ((year_totals[current_year] - year_totals[previous_year]) / year_totals[previous_year] * 100) if year_totals[previous_year] > 0 else 0
            
            with cols[i % 3]:  # Wrap around if more than 3 comparisons
                if growth > 0:
                    st.success(f"{previous_year} to {current_year}: +{growth:.1f}%")
                else:
                    st.error(f"{previous_year} to {current_year}: {growth:.1f}%")
        
        # Overall trend analysis
        st.markdown("---")
        if all(year_totals[sorted_years[i+1]] > year_totals[sorted_years[i]] for i in range(len(sorted_years)-1)):
            st.success("📈 Consistent Growth Trend Across All Years")
        elif all(year_totals[sorted_years[i+1]] < year_totals[sorted_years[i]] for i in range(len(sorted_years)-1)):
            st.error("📉 Consistent Decline Trend Across All Years")
        else:
            st.warning("📊 Mixed Growth Pattern")
"""
def show_summary_tab(df):
   
    st.header("📋 Summary & Insights")
    
    # Overall statistics
    st.subheader("📊 Overall Statistics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Cost Centers", df["Cost Center Name"].nunique())
        st.metric("Total Accounts", df["Account name"].nunique())
        st.metric("Total Records", len(df))
    
    with col2:
        st.metric("2025 Total Budget", f"{df['2025 Budget'].sum():,.0f}")
        st.metric("2024 Total Budget", f"{df['2024 Budget'].sum():,.0f}")
        st.metric("2023 Total Budget", f"{df['2023 Budget'].sum():,.0f}")
    
    with col3:
        st.metric("Total Consumed", f"{df[CONSUMED_COL].sum():,.0f}")
        st.metric("Total Available", f"{df[AVAILABLE_COL].sum():,.0f}")
        utilization_rate = (df[CONSUMED_COL].sum() / df['2025 Budget'].sum() * 100) if df['2025 Budget'].sum() > 0 else 0
        st.metric("Utilization Rate", f"{utilization_rate:.1f}%")
    
    with col4:
        if "Quarter" in df.columns:
            st.metric("Q1 Records", len(df[df["Quarter"] == "Q1"]))
            st.metric("Q2 Records", len(df[df["Quarter"] == "Q2"]))
            st.metric("Q3 Records", len(df[df["Quarter"] == "Q3"]))
            st.metric("Q4 Records", len(df[df["Quarter"] == "Q4"]))
        else:
            st.metric("Date Range", "N/A")
            st.metric("Latest Update", "N/A")
            st.metric("Data Quality", "Good")
    
    st.markdown("---")
    
    # Report Generation Button
    st.subheader("📄 Generate Report")
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        if st.button("📊 Generate Comprehensive Report", type="primary", use_container_width=True):
            with st.spinner("Generating report..."):
                buffer = generate_report(df)
                if buffer:
                    st.success("Report generated successfully!")
                    
                    # Create download link
                    filename = f"GASCO_Budget_Report_{CURRENT_YEAR}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                    download_link = get_download_link(buffer, filename)
                    st.markdown(download_link, unsafe_allow_html=True)
                    
                    st.info("📋 Report includes:")
                    st.write("• Executive Summary")
                    st.write("• Key Performance Metrics")
                    st.write("• Top Performers Analysis")
                    st.write("• Year-over-Year Trends")
                    st.write("• Quarterly Analysis")
                    st.write("• Cost Center Breakdown")
                    st.write("• Key Insights & Recommendations")
                else:
                    st.error("Failed to generate report. Please try again.")
    
    st.markdown("---")
    
    # Top performers
    st.subheader("🏆 Top Performers")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Top cost centers by budget
        top_cc_budget = df.groupby("Cost Center Name")["2025 Budget"].sum().sort_values(ascending=False).head(5)
        st.write("**Top 5 Cost Centers by Budget:**")
        for i, (cc, budget) in enumerate(top_cc_budget.items(), 1):
            st.write(f"{i}. {cc}: {budget:,.0f}")
    
    with col2:
        # Top accounts by budget
        top_accounts_budget = df.groupby("Account name")["2025 Budget"].sum().sort_values(ascending=False).head(5)
        st.write("**Top 5 Accounts by Budget:**")
        for i, (account, budget) in enumerate(top_accounts_budget.items(), 1):
            st.write(f"{i}. {account}: {budget:,.0f}")
    
    st.markdown("---")
    
    # Budget distribution
    st.subheader("📊 Budget Distribution")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Cost center distribution
        cc_distribution = df.groupby("Cost Center Name")["2025 Budget"].sum()
        fig = px.pie(values=cc_distribution.values, names=cc_distribution.index,
                     title="Budget Distribution by Cost Center")
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Account distribution
        account_distribution = df.groupby("Account name")["2025 Budget"].sum().head(10)
        fig = px.pie(values=account_distribution.values, names=account_distribution.index,
                     title="Top 10 Accounts by Budget")
        st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # Year-over-year trends
    st.subheader("📈 Year-over-Year Trends")
    
    # Calculate trends
    total_2023 = df["2023 Budget"].sum()
    total_2024 = df["2024 Budget"].sum()
    total_2025 = df["2025 Budget"].sum()
    
    growth_2024 = ((total_2024 - total_2023) / total_2023 * 100) if total_2023 > 0 else 0
    growth_2025 = ((total_2025 - total_2024) / total_2024 * 100) if total_2024 > 0 else 0
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("2023 Total", f"{total_2023:,.0f}")
        st.metric("2024 Total", f"{total_2024:,.0f}")
        st.metric("2025 Total", f"{total_2025:,.0f}")
    
    with col2:
        st.metric("2024 Growth", f"{growth_2024:+.1f}%", 
                 delta=f"{'Increase' if growth_2024 > 0 else 'Decrease'}")
        st.metric("2025 Growth", f"{growth_2025:+.1f}%",
                 delta=f"{'Increase' if growth_2025 > 0 else 'Decrease'}")
        st.metric("3-Year CAGR", f"{((total_2025/total_2023)**(1/2)-1)*100:.1f}%")
    
    with col3:
        # Budget trend chart
        trend_data = pd.DataFrame({
            'Year': ['2023', '2024', '2025'],
            'Budget': [total_2023, total_2024, total_2025]
        })
        fig = px.line(trend_data, x='Year', y='Budget', 
                     title="Budget Trend Over Years", markers=True)
        st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # Quarterly analysis (if available)
    if "Quarter" in df.columns:
        st.subheader("📅 Quarterly Analysis")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Quarterly distribution
            quarterly_dist = df.groupby("Quarter")["2025 Budget"].sum()
            fig = px.bar(x=quarterly_dist.index, y=quarterly_dist.values,
                        title="Budget Distribution by Quarter",
                        color=quarterly_dist.index,
                        color_discrete_map={'Q1': '#1f77b4', 'Q2': '#ff7f0e', 'Q3': '#2ca02c', 'Q4': '#d62728'})
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Quarterly summary table
            quarterly_summary = df.groupby("Quarter").agg({
                "2025 Budget": "sum",
                "Cost Center Name": "nunique",
                "Account name": "nunique"
            }).round(0)
            quarterly_summary.columns = ["Total Budget", "Cost Centers", "Accounts"]
            st.write("**Quarterly Summary:**")
            st.dataframe(quarterly_summary, use_container_width=True)
    
    st.markdown("---")
    
    # Key insights
    st.subheader("💡 Key Insights")
    
    # Budget efficiency
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Budget Efficiency:**")
        if utilization_rate > 80:
            st.success(f"High utilization rate ({utilization_rate:.1f}%) - Budget is being used effectively")
        elif utilization_rate > 60:
            st.info(f"Moderate utilization rate ({utilization_rate:.1f}%) - Room for optimization")
        else:
            st.warning(f"Low utilization rate ({utilization_rate:.1f}%) - Consider budget reallocation")
        
        # Growth insights
        st.write("**Growth Analysis:**")
        if growth_2025 > 0:
            st.success(f"Budget increased by {growth_2025:.1f}% in 2025")
        else:
            st.warning(f"Budget decreased by {abs(growth_2025):.1f}% in 2025")
    
    with col2:
        # Top cost center insights
        top_cc = df.groupby("Cost Center Name")["2025 Budget"].sum().idxmax()
        top_cc_budget = df.groupby("Cost Center Name")["2025 Budget"].sum().max()
        st.write("**Top Cost Center:**")
        st.write(f"**{top_cc}** with {top_cc_budget:,.0f} budget allocation")
        
        # Top account insights
        top_account = df.groupby("Account name")["2025 Budget"].sum().idxmax()
        top_account_budget = df.groupby("Account name")["2025 Budget"].sum().max()
        st.write("**Top Account:**")
        st.write(f"**{top_account}** with {top_account_budget:,.0f} budget allocation")
    
    st.markdown("---")
    
    # Key Factors & Top Indicators
    st.subheader("🎯 Key Factors & Top Indicators")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Key Performance Indicators
        st.write("**📊 Top Performance Indicators:**")
        
        # Budget efficiency indicator
        if utilization_rate >= 90:
            st.success(f"🔥 Excellent Efficiency: {utilization_rate:.1f}%")
        elif utilization_rate >= 75:
            st.info(f"✅ Good Efficiency: {utilization_rate:.1f}%")
        elif utilization_rate >= 50:
            st.warning(f"⚠️ Moderate Efficiency: {utilization_rate:.1f}%")
        else:
            st.error(f"❌ Low Efficiency: {utilization_rate:.1f}%")
        
        # Growth indicator
        if growth_2025 >= 10:
            st.success(f"🚀 Strong Growth: +{growth_2025:.1f}%")
        elif growth_2025 >= 5:
            st.info(f"📈 Positive Growth: +{growth_2025:.1f}%")
        elif growth_2025 >= 0:
            st.warning(f"📊 Stable: {growth_2025:.1f}%")
        else:
            st.error(f"📉 Declining: {growth_2025:.1f}%")
        
        # Cost center diversity
        cc_count = df["Cost Center Name"].nunique()
        if cc_count >= 10:
            st.success(f"🏢 High Diversity: {cc_count} Cost Centers")
        elif cc_count >= 5:
            st.info(f"🏢 Moderate Diversity: {cc_count} Cost Centers")
        else:
            st.warning(f"🏢 Low Diversity: {cc_count} Cost Centers")
    
    with col2:
        # Key Risk Factors
        st.write("**⚠️ Key Risk Factors:**")
        
        # Budget overrun risk
        overrun_risk = (df[CONSUMED_COL] > df["2025 Budget"]).sum()
        if overrun_risk > 0:
            st.error(f"🚨 Budget Overrun Risk: {overrun_risk} items")
        else:
            st.success("✅ No Budget Overrun Risk")
        
        # Low utilization risk
        low_util_risk = len(df[df[CONSUMED_COL] / df["2025 Budget"] < 0.3])
        if low_util_risk > 0:
            st.warning(f"⚠️ Low Utilization Risk: {low_util_risk} items")
        else:
            st.success("✅ Good Utilization Across All Items")
        
        # Zero budget risk
        zero_budget_risk = len(df[df["2025 Budget"] == 0])
        if zero_budget_risk > 0:
            st.error(f"❌ Zero Budget Items: {zero_budget_risk}")
        else:
            st.success("✅ All Items Have Budget Allocation")
    
    st.markdown("---")
    
    # Budget Alarms & Remaining Analysis
    st.subheader("🚨 Budget Alarms & Remaining Analysis")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Critical alarms
        st.write("**🚨 Critical Alarms:**")
        
        # High consumption alarms
        high_consumption = df[(df["2025 Budget"] > 0) & (df[CONSUMED_COL] / df["2025 Budget"] > 0.9)]
        if len(high_consumption) > 0:
            st.error(f"🔥 High Consumption Alert: {len(high_consumption)} items >90% consumed")
            for _, row in high_consumption.head(3).iterrows():
                st.write(f"• {row['Cost Center Name']} - {row['Account name']}: {row[CONSUMED_COL]/row['2025 Budget']*100:.1f}%")
        else:
            st.success("✅ No High Consumption Alarms")
        
        # Budget depletion alarms
        depleted_budget = df[df[AVAILABLE_COL] < df["2025 Budget"] * 0.1]
        if len(depleted_budget) > 0:
            st.error(f"💸 Budget Depletion Alert: {len(depleted_budget)} items <10% remaining")
        else:
            st.success("✅ No Budget Depletion Alarms")
    
    with col2:
        # Remaining budget analysis
        st.write("**💰 Remaining Budget Analysis:**")
        
        total_remaining = df[AVAILABLE_COL].sum()
        avg_remaining = df[AVAILABLE_COL].mean()
        
        st.metric("Total Remaining", f"{total_remaining:,.0f}")
        st.metric("Average Remaining", f"{avg_remaining:,.0f}")
        
        # Remaining by cost center
        remaining_by_cc = df.groupby("Cost Center Name")[AVAILABLE_COL].sum().sort_values(ascending=False)
        st.write("**Top 3 Cost Centers by Remaining Budget:**")
        for i, (cc, remaining) in enumerate(remaining_by_cc.head(3).items(), 1):
            st.write(f"{i}. {cc}: {remaining:,.0f}")
    
    st.markdown("---")
    
    # Insights Comparison (Increase/Decrease Analysis)
    st.subheader("📈📉 Insights Comparison")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**📈 Positive Trends:**")
        
        # Budget increases
        if growth_2025 > 0:
            st.success(f"✅ Budget Growth: +{growth_2025:.1f}% increase")
        
        # High performers
        top_performers = df.groupby("Cost Center Name")["2025 Budget"].sum().sort_values(ascending=False).head(3)
        st.write("🏆 Top 3 Budget Allocations:")
        for i, (cc, budget) in enumerate(top_performers.items(), 1):
            st.write(f"{i}. {cc}: {budget:,.0f}")
        
        # Efficient utilization
        efficient_cc = df.groupby("Cost Center Name").apply(
            lambda x: (x[CONSUMED_COL].sum() / x["2025 Budget"].sum() * 100) if x["2025 Budget"].sum() > 0 else 0
        ).sort_values(ascending=False).head(3)
        
        st.write("⚡ Most Efficient Cost Centers:")
        for i, (cc, efficiency) in enumerate(efficient_cc.items(), 1):
            st.write(f"{i}. {cc}: {efficiency:.1f}% utilization")
    
    with col2:
        st.write("**📉 Areas of Concern:**")
        
        # Budget decreases
        if growth_2025 < 0:
            st.error(f"📉 Budget Decline: {abs(growth_2025):.1f}% decrease")
        
        # Low performers
        low_performers = df.groupby("Cost Center Name")["2025 Budget"].sum().sort_values().head(3)
        st.write("🔻 Lowest Budget Allocations:")
        for i, (cc, budget) in enumerate(low_performers.items(), 1):
            st.write(f"{i}. {cc}: {budget:,.0f}")
        
        # Inefficient utilization
        inefficient_cc = df.groupby("Cost Center Name").apply(
            lambda x: (x[CONSUMED_COL].sum() / x["2025 Budget"].sum() * 100) if x["2025 Budget"].sum() > 0 else 0
        ).sort_values().head(3)
        
        st.write("🐌 Least Efficient Cost Centers:")
        for i, (cc, efficiency) in enumerate(inefficient_cc.items(), 1):
            if efficiency > 0:
                st.write(f"{i}. {cc}: {efficiency:.1f}% utilization")
            else:
                st.write(f"{i}. {cc}: No consumption")
    
    # Year-over-year comparison insights
    st.markdown("---")
    st.subheader("📊 Year-over-Year Comparison Insights")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # 2023-2024 comparison
        growth_2024_vs_2023 = ((total_2024 - total_2023) / total_2023 * 100) if total_2023 > 0 else 0
        if growth_2024_vs_2023 > 0:
            st.success(f"2024 vs 2023: +{growth_2024_vs_2023:.1f}%")
        else:
            st.error(f"2024 vs 2023: {growth_2024_vs_2023:.1f}%")
    
    with col2:
        # 2025-2024 comparison
        if growth_2025 > 0:
            st.success(f"2025 vs 2024: +{growth_2025:.1f}%")
        else:
            st.error(f"2025 vs 2024: {growth_2025:.1f}%")
    
    with col3:
        # 3-year trend
        if growth_2025 > 0 and growth_2024_vs_2023 > 0:
            st.success("📈 Consistent Growth Trend")
        elif growth_2025 < 0 and growth_2024_vs_2023 < 0:
            st.error("📉 Consistent Decline Trend")
        else:
            st.warning("📊 Mixed Growth Pattern")
"""

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
                    fig.update_layout(xaxes_title="Compressor", yaxes_title="Hours")
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
