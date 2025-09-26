import streamlit as st
import pandas as pd
from openpyxl import load_workbook
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io
import base64
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
from Modules.maintenance import  solve_true_min_cost_mip, solve_true_min_cost_and_min_gap, solve_true_min_cost_and_max_gap

# Import compressor data functions
try:
    from Modules.compressor_data import show_compressor_data_entry, show_compressor_data_view
    COMPRESSOR_MODULE_AVAILABLE = True
except ImportError as e:
    COMPRESSOR_MODULE_AVAILABLE = False
    def show_compressor_data_entry():
        st.error(f"Compressor data module not available: {e}")
    def show_compressor_data_view():
        st.error(f"Compressor data module not available: {e}")



CURRENT_YEAR = datetime.now().year
EXCEL_PATH = "Data/Budget Monitoring.xlsx"

BUDGET_COLUMNS = {
    "2023": "2023 Budget",
    "2024": "2024 Budget",
    "2025": "2025 Budget"
}

CONSUMED_COLUMNS = {
    "2023": "2023 Consumed",
    "2024": "2024 Consumed",
    "2025": "2025 Consumed"
}


CONSUMED_COL = "Consumed Amount"
AVAILABLE_COL = "Available Amount"

def get_quarter_from_date(date):
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
    if pd.isna(date):
        return None
    return date.year

# REPLACE YOUR EXISTING load_budget_data() FUNCTION WITH THIS:



def append_expense_to_excel(new_data: dict):
    try:
        df = pd.read_excel(EXCEL_PATH)
        df.columns = df.columns.str.strip()

        new_row = pd.DataFrame([new_data])

        # Avoid duplicates
        if ((df == new_row.iloc[0]).all(axis=1)).any():
            st.warning("This exact record already exists.")
            return False

        df = pd.concat([df, new_row], ignore_index=True)
        df.to_excel(EXCEL_PATH, index=False, engine='openpyxl')
        return True
    except Exception as e:
        st.error(f"Error writing to Excel: {e}")
        return False


def load_budget_data():
    try:
        df = pd.read_excel(EXCEL_PATH)
        df.columns = df.columns.str.strip()  # clean column names

        # Force numeric for budget & amount columns
        for col in list(BUDGET_COLUMNS.values()) + [CONSUMED_COL]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

        # Calculate Available
        if AVAILABLE_COL not in df.columns:
            df[AVAILABLE_COL] = df[BUDGET_COLUMNS["2025"]] - df[CONSUMED_COL]

        # Process Date
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
            df["Quarter"] = df["Date"].apply(get_quarter_from_date)
            df["Year"] = df["Date"].apply(get_year_from_date)
        else:
            df["Date"] = pd.to_datetime("2025-01-01")
            df["Quarter"] = "Q1"
            df["Year"] = 2025

        # Combined cost center for dropdown
        if "Cost Center Number" in df.columns and "Cost Center Name" in df.columns:
            df["Cost Center Display"] = df["Cost Center Number"].astype(str) + " - " + df["Cost Center Name"]

        # Combined account for dropdown
        if "Account number" in df.columns and "Account name" in df.columns:
            df["Account Display"] = df["Account number"].astype(str) + " - " + df["Account name"]

        # Extract unique values for the expected return
        cost_center_names = sorted(df["Cost Center Name"].dropna().unique().tolist()) if "Cost Center Name" in df.columns else []
        cost_center_numbers = sorted(df["Cost Center Number"].dropna().unique().tolist()) if "Cost Center Number" in df.columns else []
        account_names = sorted(df["Account name"].dropna().unique().tolist()) if "Account name" in df.columns else []
        account_numbers = sorted(df["Account number"].dropna().unique().tolist()) if "Account number" in df.columns else []

        return df, cost_center_names, cost_center_numbers, account_names, account_numbers
        
    except Exception as e:
        st.error(f"Failed to load budget data: {e}")
        # Return empty values for all expected returns
        return pd.DataFrame(), [], [], [], []

def log_expense_form():
    df, _, _, _, _ = load_budget_data()
    if df.empty:
        return

    with st.form("log_expense_form"):
        # Step 1: Select Cost Center (combined name + number)
        selected_cc_display = st.selectbox("Cost Center", sorted(df["Cost Center Display"].unique()))
        cc_row = df[df["Cost Center Display"] == selected_cc_display].iloc[0]
        selected_cc_number = cc_row["Cost Center Number"]
        selected_cc_name = cc_row["Cost Center Name"]

        # Step 2: Select Account (combined number + name)
        filtered_acc_displays = df[df["Cost Center Display"] == selected_cc_display]["Account Display"].dropna().unique().tolist()
        selected_acc_display = st.selectbox("Select Account", sorted(filtered_acc_displays))
        
        # Extract account number and name from the selected display
        acc_row = df[
            (df["Cost Center Display"] == selected_cc_display) &
            (df["Account Display"] == selected_acc_display)
        ].iloc[0]
        selected_acc_number = acc_row["Account number"]
        selected_acc_name = acc_row["Account name"]

        # Step 3: Date
        date_val = st.date_input("Date", pd.Timestamp.today())

        # Step 4: Budget info
        match = df[
            (df["Cost Center Number"] == selected_cc_number) &
            (df["Cost Center Name"] == selected_cc_name) &
            (df["Account name"] == selected_acc_name) &
            (df["Account number"] == selected_acc_number)
        ]

        budget_2025 = match["2025 Budget"].iloc[0] if not match.empty else 0
        consumed_before = match["Consumed Amount"].iloc[0] if not match.empty else 0
        available_before = match["Available Amount"].iloc[0] if not match.empty else 0

        st.write(f"**2025 Budget:** {budget_2025}")
        st.write(f"**Consumed Before:** {consumed_before}")
        st.write(f"**Available Before:** {available_before}")

        consumed_now = st.number_input("Consumed Amount", min_value=0.0, step=0.01)
        available_after = available_before - consumed_now
        st.write(f"**Available After:** {available_after}")

        submitted = st.form_submit_button("Submit Expense")
        if submitted:
            new_row = {
                "Cost Center Number": selected_cc_number,
                "Cost Center Name": selected_cc_name,
                "Account number": selected_acc_number,
                "Account name": selected_acc_name,
                "Date": date_val,
                "Quarter": get_quarter_from_date(date_val),
                "Year": date_val.year,
                "2023 Budget": match["2023 Budget"].iloc[0] if not match.empty else 0,
                "2024 Budget": match["2024 Budget"].iloc[0] if not match.empty else 0,
                "2025 Budget": budget_2025,
                "Consumed Amount": consumed_now,
                "Available Amount": available_after
            }
            if append_expense_to_excel(new_row):
                st.success("Expense logged successfully.")

def show_filtered_dashboard():
    st.title("📊 Budget Dashboard")

    # ------------------ 📥 Load Data First ------------------
    df, cost_center_names, cost_center_numbers, account_names, account_numbers = load_budget_data()
    if df.empty:
        st.warning("No data available to display.")
        return

    # ------------------ 🔧 Log Expense ------------------
    with st.expander("➕ Log New Expense", expanded=True):
        # STEP 1: Cost Center selection OUTSIDE the form (so it can update dynamically)
        if "Cost Center Display" in df.columns and not df.empty:
            cost_center_options = sorted(df["Cost Center Display"].dropna().unique())
            
            if cost_center_options:
                selected_cc_display = st.selectbox(
                    "🏢 Select Cost Center", 
                    cost_center_options,
                    key="cost_center_selector"
                )
                
                # Get the selected cost center details
                cc_rows = df[df["Cost Center Display"] == selected_cc_display]
                if not cc_rows.empty:
                    selected_cc_number = cc_rows["Cost Center Number"].iloc[0]
                    selected_cc_name = cc_rows["Cost Center Name"].iloc[0]
                    filtered_acc_displays = cc_rows["Account Display"].dropna().unique().tolist()
                    if filtered_acc_displays:
                        with st.form("log_expense_form_main"):
                            selected_acc_display = st.selectbox("📊 Select Account", sorted(filtered_acc_displays), key="account_display_selector")
                            acc_row = cc_rows[cc_rows["Account Display"] == selected_acc_display].iloc[0]
                            selected_acc_number = acc_row["Account number"]
                            selected_acc_name = acc_row["Account name"]
                            expense_date = st.date_input("📅 Expense Date", value=datetime.now())
                            match = df[(df["Cost Center Number"] == selected_cc_number) & (df["Cost Center Name"] == selected_cc_name) & (df["Account name"] == selected_acc_name) & (df["Account number"] == selected_acc_number)]
                            if not match.empty:
                                budget_2025 = match["2025 Budget"].iloc[0] if "2025 Budget" in match.columns else 0
                                budget_2024 = match["2024 Budget"].iloc[0] if "2024 Budget" in match.columns else 0
                                budget_2023 = match["2023 Budget"].iloc[0] if "2023 Budget" in match.columns else 0
                                consumed_before = match[CONSUMED_COL].iloc[0] if CONSUMED_COL in match.columns else 0
                                available_before = match[AVAILABLE_COL].iloc[0] if AVAILABLE_COL in match.columns else budget_2025
                                st.markdown("**📈 Current Budget Status:**")
                                col1, col2, col3 = st.columns(3)
                                with col1:
                                    st.metric("2025 Budget", f"${budget_2025:,.2f}")
                                with col2:
                                    st.metric("Consumed", f"${consumed_before:,.2f}")
                                with col3:
                                    st.metric("Available", f"${available_before:,.2f}")
                                consumed_now = st.number_input("💰 New Expense Amount", min_value=0.0, step=0.01, help="Enter the amount you want to log as consumed")
                                if consumed_now > 0:
                                    new_consumed_total = consumed_before + consumed_now
                                    available_after = budget_2025 - new_consumed_total
                                    st.markdown("**📊 After This Expense:**")
                                    col1a, col2a = st.columns(2)
                                    with col1a:
                                        st.write(f"**Total Consumed:** ${new_consumed_total:,.2f}")
                                    with col2a:
                                        st.write(f"**Available:** ${available_after:,.2f}")
                                    if available_after < 0:
                                        st.error("⚠️ This expense will exceed the available budget!")
                                    elif available_after < (budget_2025 * 0.1):
                                        st.warning("⚠️ Low budget remaining!")
                                form_data = {'selected_cc_number': selected_cc_number, 'selected_cc_name': selected_cc_name, 'selected_acc_name': selected_acc_name, 'selected_acc_number': selected_acc_number, 'expense_date': expense_date, 'consumed_now': consumed_now, 'budget_2025': budget_2025, 'budget_2024': budget_2024, 'budget_2023': budget_2023, 'consumed_before': consumed_before}
                            else:
                                st.error("❌ No exact match found for the selected combination.")
                                consumed_now = 0
                                form_data = {}
                            submit = st.form_submit_button("📝 Log Expense", type="primary")
                        if submit and 'form_data' in locals() and form_data and consumed_now > 0:
                            try:
                                new_consumed_total = form_data['consumed_before'] + form_data['consumed_now']
                                available_after = form_data['budget_2025'] - new_consumed_total
                                row = {"Cost Center Number": form_data['selected_cc_number'], "Cost Center Name": form_data['selected_cc_name'], "Account number": form_data['selected_acc_number'], "Account name": form_data['selected_acc_name'], "Date": form_data['expense_date'], "Quarter": get_quarter_from_date(form_data['expense_date']), "Year": form_data['expense_date'].year, "2023 Budget": form_data['budget_2023'], "2024 Budget": form_data['budget_2024'], "2025 Budget": form_data['budget_2025'], CONSUMED_COL: new_consumed_total, AVAILABLE_COL: available_after}
                                success = append_expense_to_excel(row)
                                if success:
                                    st.success("✅ Expense logged and saved successfully!")
                                    st.balloons()
                                    st.rerun()
                                else:
                                    st.error("❌ Failed to log the expense. Please try again.")
                            except Exception as e:
                                st.error(f"❌ Error logging expense: {str(e)}")
                        elif submit and consumed_now <= 0:
                            st.warning("⚠️ Please enter an expense amount greater than 0.")

    tab1, tab2 = st.tabs(["📊 Analysis Dashboard", "📋 Summary & Insights"])
    with tab1:
        st.markdown("---")
        st.subheader("🎯 Filters")
        col1, col2, col3 = st.columns(3)
        with col1:
            time_period = st.selectbox("Select Time Period Type", options=["Annual", "Quarterly"], help="Choose between annual or quarterly analysis")
        with col2:
            if time_period == "Annual":
                selected_years = st.multiselect("Select Years to Compare", options=list(BUDGET_COLUMNS.keys()), default=["2025", "2024", "2023"])
            else:
                available_years = sorted(df["Year"].unique()) if "Year" in df.columns else []
                if available_years:
                    selected_year = st.selectbox("Select Year for Quarterly Analysis", options=available_years, index=len(available_years) - 1)
                    selected_quarters = st.multiselect("Select Quarters to Compare", options=["Q1", "Q2", "Q3", "Q4"], default=["Q1", "Q2", "Q3", "Q4"])
                else:
                    selected_year, selected_quarters = None, []
        with col3:
            cc_options = ["All"] + cost_center_names
            selected_ccs = st.multiselect("Select Cost Centers", options=cc_options, default=["All"])
        
        # Filter by Cost Center
        if "All" in selected_ccs or not selected_ccs:
            filtered_df = df
        else:
            filtered_df = df[df["Cost Center Name"].isin(selected_ccs)]

        # Filter by Account
        account_options = ["All"] + sorted(filtered_df["Account name"].unique())
        selected_accounts = st.multiselect("Select Accounts", options=account_options, default=["All"])
        if "All" not in selected_accounts and selected_accounts:
            filtered_df = filtered_df[filtered_df["Account name"].isin(selected_accounts)]
        st.markdown("---")
        if time_period == "Annual":
            if "All" not in selected_accounts and selected_accounts:
                st.subheader("Consumed vs. Available Budget")
                account_summary = filtered_df.groupby(["Cost Center Name", "Account name"]) [[CONSUMED_COL, AVAILABLE_COL]].sum().reset_index()
                melted_data = pd.melt(account_summary, id_vars=["Cost Center Name", "Account name"], value_vars=[CONSUMED_COL, AVAILABLE_COL], var_name="Budget Type", value_name="Amount")
                if not melted_data.empty:
                    fig_con_avail = px.bar(melted_data, x="Account name", y="Amount", color="Budget Type", barmode="group", title="Consumed vs. Available by Account", color_discrete_map={CONSUMED_COL: '#d62728', AVAILABLE_COL: '#2ca02c'}, text="Amount", facet_col="Cost Center Name", facet_col_wrap=4)
                    fig_con_avail.update_traces(texttemplate='$%{text:,.0f}', textposition='outside')
                    fig_con_avail.update_layout(yaxis_title="Amount ($)")
                    st.plotly_chart(fig_con_avail, use_container_width=True)
            if not selected_years:
                st.warning("Please select at least one year.")
            else:
                st.subheader("📈 Annual Budget Comparison")
              """  annual_data = []
                # Use full dataframe if no cost centers are selected, otherwise use the filtered one
                source_df = df if not selected_ccs else filtered_df
                for year in selected_years:
                    budget_col = BUDGET_COLUMNS.get(str(year))
                    if budget_col and budget_col in source_df.columns:
                        if not selected_ccs:
                            # Total budget per year if no CC is selected
                            total_budget = source_df[budget_col].sum()
                            annual_data.append({'Year': year, 'Budget': total_budget})
                        else:
                            # Budget per selected CC per year
                            yearly_sum = source_df.groupby("Cost Center Name")[budget_col].sum().reset_index()
                            yearly_sum.rename(columns={budget_col: 'Budget'}, inplace=True)
                            yearly_sum['Year'] = year
                            annual_data.append(yearly_sum)""""
                
                annual_data = []
                for year in selected_years:
                    budget_col = BUDGET_COLUMNS.get(str(year))
                    consumed_col = CONSUMED_COLUMNS.get(str(year))
                   if budget_col in filtered_df.columns and consumed_col in filtered_df.columns:
                      yearly = filtered_df.groupby("Cost Center Name")[[budget_col, consumed_col]].sum().reset_index()
                      yearly["Year"] = year
                      yearly.rename(columns={budget_col: "Budget", consumed_col: "Consumed"}, inplace=True)
                      annual_data.append(yearly)

                   if annual_data:
                      annual_df = pd.concat(annual_data, ignore_index=True)

                   # Stacked bars: Budget vs Consumed
                      fig = px.bar(
                         annual_df,
                         x="Year", y=["Budget", "Consumed"],
                         color_discrete_map={"Budget": "#1f77b4", "Consumed": "#d62728"},
                        barmode="group",
                        title="Annual Budget vs Consumed"
                      )
                      st.plotly_chart(fig, use_container_width=True)

                
                
                
                if annual_data:
                    annual_df = pd.concat([pd.DataFrame([x]) if isinstance(x, dict) else x for x in annual_data], ignore_index=True)
                    if not annual_df.empty and annual_df['Budget'].sum() > 0:
                        if not selected_ccs:
                            fig_annual = px.bar(annual_df, x='Year', y='Budget', title='Total Annual Budget Comparison', text='Budget')
                            fig_annual.update_traces(texttemplate='$%{text:,.2s}', textposition='outside')
                        else:
                            fig_annual = px.bar(annual_df, x='Year', y='Budget', color='Cost Center Name', barmode='group', title='Annual Budget Comparison by Cost Center')
                        st.plotly_chart(fig_annual, use_container_width=True)

                        # --- Annual Trend Line Chart ---
                        st.subheader("📈 Annual Budget Trend")
                        if not selected_ccs:
                            fig_annual_trend = px.line(annual_df, x='Year', y='Budget', title='Total Annual Budget Trend', markers=True)
                        else:
                            fig_annual_trend = px.line(annual_df, x='Year', y='Budget', color='Cost Center Name', title='Annual Budget Trend by Cost Center', markers=True)
                        fig_annual_trend.update_traces(textposition="top center")
                        st.plotly_chart(fig_annual_trend, use_container_width=True)
                        fig_trend = px.line(
                            annual_df,
                            x="Year", y="Consumed", color="Cost Center Name",
                            title="Annual Consumed Trend by Cost Center",
                            markers=True
                        )
                        st.plotly_chart(fig_trend, use_container_width=True)


                # --- Chart by Account --- 
                if selected_accounts:
                    st.subheader("📊 Annual Budget by Account")
                    account_annual_data = []
                    for year in selected_years:
                        budget_col = BUDGET_COLUMNS.get(str(year))
                        if budget_col and budget_col in filtered_df.columns:
                            year_data = filtered_df.groupby(["Cost Center Name", "Account name"])[budget_col].sum().reset_index()
                            year_data.rename(columns={budget_col: 'Budget'}, inplace=True)
                            year_data['Year'] = year
                            account_annual_data.append(year_data)
                    
                    if account_annual_data:
                        account_df = pd.concat(account_annual_data, ignore_index=True)
                        if not account_df.empty and account_df['Budget'].sum() > 0:
                            fig_accounts = px.bar(account_df, x="Account name", y="Budget", color="Year", barmode="group",
                                                  title="Annual Budget by Account", facet_col="Cost Center Name", facet_col_wrap=4)
                            st.plotly_chart(fig_accounts, use_container_width=True)
        else:  # Quarterly Analysis
            if not selected_quarters or selected_year is None:
                st.warning("Please select a year and at least one quarter.")
            else:
                st.subheader(f"📈 {selected_year} Quarterly Consumption Trend")
                budget_col = BUDGET_COLUMNS.get(str(selected_year))
                if budget_col and budget_col in filtered_df.columns:
                    quarter_filtered = filtered_df[(filtered_df["Year"] == selected_year) & (filtered_df["Quarter"].isin(selected_quarters))].copy()
                    
                    if not quarter_filtered.empty:
                        # Ensure quarters are sorted correctly
                        quarter_order = [f'Q{i}' for i in range(1, 5)]
                        quarter_filtered['Quarter'] = pd.Categorical(quarter_filtered['Quarter'], categories=quarter_order, ordered=True)
                        
                        # Aggregate data for consumption
                        quarterly_consumed_agg = quarter_filtered.groupby(["Cost Center Name", "Account name", "Quarter"])[CONSUMED_COL].sum().reset_index()
                        
                        if not quarterly_consumed_agg.empty and quarterly_consumed_agg[CONSUMED_COL].sum() > 0:
                            fig_quarterly_trend = px.line(
                                quarterly_consumed_agg,
                                x='Quarter',
                                y=CONSUMED_COL,
                                color='Account name',
                                markers=True,
                                title=f'Quarterly Consumption Trend for {selected_year}',
                                facet_col="Cost Center Name",
                                facet_col_wrap=4
                            )
                            st.plotly_chart(fig_quarterly_trend, use_container_width=True)

                            # --- Quarterly Consumed Amount Bar Chart ---
                            st.subheader(f'📊 {selected_year} Consumed Amount by Quarter')
                            consumed_agg = quarter_filtered.groupby(["Cost Center Name", "Account name", "Quarter"])[CONSUMED_COL].sum().reset_index()
                            if not consumed_agg.empty and consumed_agg[CONSUMED_COL].sum() > 0:
                                fig_consumed_bar = px.bar(
                                    consumed_agg,
                                    x='Account name',
                                    y=CONSUMED_COL,
                                    color='Quarter',
                                    barmode='group',
                                    title=f'Consumed Amount for {selected_year}',
                                    facet_col="Cost Center Name",
                                    facet_col_wrap=4
                                )
                                st.plotly_chart(fig_consumed_bar, use_container_width=True)
                            else:
                                st.info("No consumption data to display for the selected period.")

                            # --- Consumed Amount by Cost Center Bar Chart ---
                            st.subheader(f'📊 {selected_year} Consumed Amount by Cost Center')
                            consumed_by_cc = quarter_filtered.groupby("Cost Center Name")[CONSUMED_COL].sum().reset_index()
                            if not consumed_by_cc.empty and consumed_by_cc[CONSUMED_COL].sum() > 0:
                                fig_consumed_cc_bar = px.bar(
                                    consumed_by_cc,
                                    x='Cost Center Name',
                                    y=CONSUMED_COL,
                                    title=f'Consumed Amount by Cost Center for {selected_year}',
                                    text=CONSUMED_COL
                                )
                                fig_consumed_cc_bar.update_traces(texttemplate='$%{text:,.2s}', textposition='outside')
                                st.plotly_chart(fig_consumed_cc_bar, use_container_width=True)
                        else:
                            st.info("No budget data to display for the selected quarterly period.")
                    else:
                        st.info("No data available for the selected quarters.")
        st.markdown("---")
        st.subheader("📋 Detailed Data View")
        st.dataframe(filtered_df)
    
    with tab2:
        show_summary_tab(df)
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
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            alignment=1  # Center alignment
        )
        story.append(Paragraph(f"GASCO Budget Analysis Report - {CURRENT_YEAR}", title_style))
        story.append(Spacer(1, 20))
        
        # Executive Summary
        story.append(Paragraph("Executive Summary", styles['Heading2']))
        story.append(Spacer(1, 12))
        
        # Key metrics
        total_budget_2025 = df["2025 Budget"].sum()
        total_consumed = df[CONSUMED_COL].sum()
        total_available = df[AVAILABLE_COL].sum()
        utilization_rate = (total_consumed / total_budget_2025 * 100) if total_budget_2025 > 0 else 0
        
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
        story.append(Paragraph(summary_text, styles['Normal']))
        story.append(Spacer(1, 20))
        
        # Top Performers
        story.append(Paragraph("Top Performers", styles['Heading2']))
        story.append(Spacer(1, 12))
        
        # Top cost centers
        top_cc = df.groupby("Cost Center Name")["2025 Budget"].sum().sort_values(ascending=False).head(5)
        cc_text = "<b>Top 5 Cost Centers by Budget:</b><br/>"
        for i, (cc, budget) in enumerate(top_cc.items(), 1):
            cc_text += f"{i}. {cc}: {budget:,.0f}<br/>"
        story.append(Paragraph(cc_text, styles['Normal']))
        story.append(Spacer(1, 12))
        
        # Top accounts
        top_accounts = df.groupby("Account name")["2025 Budget"].sum().sort_values(ascending=False).head(5)
        account_text = "<b>Top 5 Accounts by Budget:</b><br/>"
        for i, (account, budget) in enumerate(top_accounts.items(), 1):
            account_text += f"{i}. {account}: {budget:,.0f}<br/>"
        story.append(Paragraph(account_text, styles['Normal']))
        story.append(Spacer(1, 20))
        
        # Year-over-Year Analysis
        story.append(Paragraph("Year-over-Year Analysis", styles['Heading2']))
        story.append(Spacer(1, 12))
        
        total_2023 = df["2023 Budget"].sum()
        total_2024 = df["2024 Budget"].sum()
        total_2025 = df["2025 Budget"].sum()
        
        growth_2024 = ((total_2024 - total_2023) / total_2023 * 100) if total_2023 > 0 else 0
        growth_2025 = ((total_2025 - total_2024) / total_2024 * 100) if total_2024 > 0 else 0
        
        yoy_text = f"""
        <b>Budget Trends:</b><br/>
        • 2023 Total: {total_2023:,.0f}<br/>
        • 2024 Total: {total_2024:,.0f}<br/>
        • 2025 Total: {total_2025:,.0f}<br/>
        • 2024 Growth: {growth_2024:+.1f}%<br/>
        • 2025 Growth: {growth_2025:+.1f}%<br/>
        • 3-Year CAGR: {((total_2025/total_2023)**(1/2)-1)*100:.1f}%
        """
        story.append(Paragraph(yoy_text, styles['Normal']))
        story.append(Spacer(1, 20))
        
        # Quarterly Analysis (if available)
        if "Quarter" in df.columns:
            story.append(Paragraph("Quarterly Analysis", styles['Heading2']))
            story.append(Spacer(1, 12))
            
            quarterly_summary = df.groupby("Quarter").agg({
                "2025 Budget": "sum",
                "Cost Center Name": "nunique",
                "Account name": "nunique"
            }).round(0)
            
            # Create quarterly table
            q_data = [["Quarter", "Total Budget", "Cost Centers", "Accounts"]]
            for quarter in ["Q1", "Q2", "Q3", "Q4"]:
                if quarter in quarterly_summary.index:
                    row = quarterly_summary.loc[quarter]
                    q_data.append([quarter, f"{row['2025 Budget']:,.0f}", str(row['Cost Center Name']), str(row['Account name'])])
            
            q_table = Table(q_data)
            q_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(q_table)
            story.append(Spacer(1, 20))
        
        # Cost Center Breakdown
        story.append(Paragraph("Cost Center Breakdown", styles['Heading2']))
        story.append(Spacer(1, 12))
        
        cc_breakdown = df.groupby("Cost Center Name").agg({
            "2025 Budget": "sum",
            CONSUMED_COL: "sum",
            AVAILABLE_COL: "sum"
        }).round(0)
        
        # Create cost center table
        cc_data = [["Cost Center", "Budget", "Consumed", "Available", "Utilization %"]]
        for cc in cc_breakdown.index:
            row = cc_breakdown.loc[cc]
            utilization = (row[CONSUMED_COL] / row["2025 Budget"] * 100) if row["2025 Budget"] > 0 else 0
            cc_data.append([
                cc, 
                f"{row['2025 Budget']:,.0f}", 
                f"{row[CONSUMED_COL]:,.0f}", 
                f"{row[AVAILABLE_COL]:,.0f}",
                f"{utilization:.1f}%"
            ])
        
        cc_table = Table(cc_data)
        cc_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 8)
        ]))
        story.append(cc_table)
        story.append(Spacer(1, 20))
        
        # Key Insights
        story.append(Paragraph("Key Insights & Recommendations", styles['Heading2']))
        story.append(Spacer(1, 12))
        
        insights = []
        if utilization_rate > 80:
            insights.append("• High utilization rate indicates effective budget management")
        elif utilization_rate > 60:
            insights.append("• Moderate utilization rate - consider optimizing budget allocation")
        else:
            insights.append("• Low utilization rate - review budget allocation strategy")
        
        if growth_2025 > 0:
            insights.append("• Budget growth indicates expanding operations")
        else:
            insights.append("• Budget reduction suggests cost optimization efforts")
        
        if len(df) < 50:
            insights.append("• Consider adding more data for comprehensive analysis")
        
        insights.append("• Regular monitoring of quarterly performance recommended")
        insights.append("• Review cost center allocations periodically")
        
        insights_text = "<b>Insights:</b><br/>" + "<br/>".join(insights)
        story.append(Paragraph(insights_text, styles['Normal']))
        story.append(Spacer(1, 20))
        
        # Report footer
        story.append(Paragraph(f"Report generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
        
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

def show_summary_tab(df):
    """Display comprehensive summary and insights"""
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
			compressor_name = st.text_input("Compressor Name", value=f"Compressor {compressor_id}")
			current_hours = st.number_input("Current Hours", min_value=0, value=500, step=1)
		
		with col2:
			status = st.selectbox("Status", ["Active", "Maintenance", "Inactive", "Repair"])
			notes = st.text_area("Notes", placeholder="Enter notes here")
		
		if st.form_submit_button("Save Data"):
			# Simple save to Excel
			try:
				data = {
					'Compressor ID': [compressor_id],
					'Compressor Name': [compressor_name], 
					'Current Hours': [current_hours],
					'Date Updated': [datetime.now().date()],
					'Status': [status],
					'Notes': [notes]
				}
				df_new = pd.DataFrame(data)
				
				# Delete the corrupted file if it exists and recreate it
				if os.path.exists("Data/Compressor_Data.xlsx"):
					try:
						df_existing = pd.read_excel("Data/Compressor_Data.xlsx", engine='openpyxl')
					except:
						# File is corrupted, delete and recreate
						os.remove("Data/Compressor_Data.xlsx")
						# Create initial data
						initial_data = {
							'Compressor ID': ['A', 'B', 'C'],
							'Compressor Name': ['Compressor A', 'Compressor B', 'Compressor C'],
							'Current Hours': [500, 79300, 76900],
							'Date Updated': [datetime.now().date()] * 3,
							'Status': ['Active', 'Active', 'Active'],
							'Notes': ['Initial setup', 'High usage unit', 'Standard operation']
						}
						df_existing = pd.DataFrame(initial_data)
						df_existing.to_excel("Data/Compressor_Data.xlsx", index=False, engine='openpyxl')
					
					# Update if exists, otherwise append
					if compressor_id in df_existing['Compressor ID'].values:
						mask = df_existing['Compressor ID'] == compressor_id
						for key, value in data.items():
							df_existing.loc[mask, key] = value[0]
						df_existing.to_excel("Data/Compressor_Data.xlsx", index=False, engine='openpyxl')
					else:
						df_combined = pd.concat([df_existing, df_new], ignore_index=True)
						df_combined.to_excel("Data/Compressor_Data.xlsx", index=False, engine='openpyxl')
				else:
					# Create new file with initial data plus new entry
					initial_data = {
						'Compressor ID': ['A', 'B', 'C', compressor_id],
						'Compressor Name': ['Compressor A', 'Compressor B', 'Compressor C', compressor_name],
						'Current Hours': [500, 79300, 76900, current_hours],
						'Date Updated': [datetime.now().date()] * 4,
						'Status': ['Active', 'Active', 'Active', status],
						'Notes': ['Initial setup', 'High usage unit', 'Standard operation', notes]
					}
					df_all = pd.DataFrame(initial_data)
					df_all.to_excel("Data/Compressor_Data.xlsx", index=False, engine='openpyxl')
				
				st.success("✅ Data saved successfully!")
			except Exception as e:
				st.error(f"Error saving data: {e}")
	
	# Add data viewing section
	st.markdown("---")
	st.write("📊 **Current Compressor Data**")
	
	try:
		if os.path.exists("Data/Compressor_Data.xlsx"):
			df_view = pd.read_excel("Data/Compressor_Data.xlsx", engine='openpyxl')
			
			if not df_view.empty:
				# Display metrics
				col1, col2, col3, col4 = st.columns(4)
				with col1:
					st.metric("Total Compressors", len(df_view))
				with col2:
					active_count = len(df_view[df_view['Status'] == 'Active']) if 'Status' in df_view.columns else 0
					st.metric("Active Units", active_count)
				with col3:
					total_hours = df_view['Current Hours'].sum() if 'Current Hours' in df_view.columns else 0
					st.metric("Total Hours", f"{total_hours:,}")
				with col4:
					avg_hours = df_view['Current Hours'].mean() if 'Current Hours' in df_view.columns else 0
					st.metric("Average Hours", f"{avg_hours:,.0f}")
				
				# Display data table
				st.subheader("📋 Compressor Details")
				st.dataframe(df_view, use_container_width=True, hide_index=True)
				
				# Add status breakdown chart
				if 'Status' in df_view.columns:
					st.subheader("📈 Status Distribution")
					status_counts = df_view['Status'].value_counts()
					fig = px.pie(values=status_counts.values, names=status_counts.index, 
								title="Compressor Status Distribution")
					st.plotly_chart(fig, use_container_width=True)
				
				# Add hours comparison chart
				if 'Current Hours' in df_view.columns and 'Compressor Name' in df_view.columns:
					st.subheader("⏱️ Operating Hours Comparison")
					fig = px.bar(df_view, x='Compressor Name', y='Current Hours',
								title="Current Operating Hours by Compressor",
								color='Status' if 'Status' in df_view.columns else None)
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
	if 'opt_results' not in st.session_state:
		st.session_state.opt_results = {}

	# Gap trade-off for models 2 and 3
	lambda_val = st.slider("Gap trade-off (lambda)", min_value=0.0, max_value=1.0, value=0.1, step=0.05, help="Higher values weight the gap objective more strongly")

	# Run-all control
	run_all = st.button("Run All Models", type="primary")

	col1, col2, col3 = st.columns(3)

	with col1:
		if st.button("Run Model 1: Minimize Cost") or run_all:
			df1 = solve_true_min_cost_mip()
			total_hours = float(df1['Assigned Hours'].sum()) if 'Assigned Hours' in df1.columns else 0.0
			total_cost = float(df1['Exact Cost'].sum()) if 'Exact Cost' in df1.columns else 0.0
			st.session_state.opt_results['m1'] = {
				'df': df1,
				'total_hours': total_hours,
				'total_cost': total_cost
			}

	with col2:
		if st.button("Run Model 2: Cost + Max Gap") or run_all:
			df2, gap2, total_cost2 = solve_true_min_cost_and_max_gap(lambda_gap=lambda_val)
			total_hours2 = float(df2['Assigned Hours'].sum()) if 'Assigned Hours' in df2.columns else 0.0
			st.session_state.opt_results['m2'] = {
				'df': df2,
				'total_hours': total_hours2,
				'total_cost': float(total_cost2),
				'gap': float(gap2),
				'lambda': lambda_val
			}

	with col3:
		if st.button("Run Model 3: Cost + Min Gap") or run_all:
			df3, gap3, total_cost3 = solve_true_min_cost_and_min_gap(lambda_gap=lambda_val)
			total_hours3 = float(df3['Assigned Hours'].sum()) if 'Assigned Hours' in df3.columns else 0.0
			st.session_state.opt_results['m3'] = {
				'df': df3,
				'total_hours': total_hours3,
				'total_cost': float(total_cost3),
				'gap': float(gap3),
				'lambda': lambda_val
			}

	st.markdown("---")

	# Render results for each model if available
	exp1, exp2, exp3 = st.tabs([
		"Model 1: Minimize Cost",
		"Model 2: Cost + Max Gap",
		"Model 3: Cost + Min Gap"
	])

	with exp1:
		res = st.session_state.opt_results.get('m1')
		if res:
			c1, c2 = st.columns(2)
			c1.metric("Total Assigned Hours", f"{res['total_hours']:,.0f}")
			c2.metric("Total Exact Cost", f"{res['total_cost']:,.2f}")
			st.dataframe(res['df'], use_container_width=True)
		else:
			st.info("Run Model 1 to view results.")

	with exp2:
		res = st.session_state.opt_results.get('m2')
		if res:
			c1, c2, c3 = st.columns(3)
			c1.metric("Total Assigned Hours", f"{res['total_hours']:,.0f}")
			c2.metric("Total Exact Cost", f"{res['total_cost']:,.2f}")
			c3.metric("Range Gap (hrs)", f"{res['gap']:,.0f}")
			st.caption(f"λ = {res['lambda']}")
			st.dataframe(res['df'], use_container_width=True)
		else:
			st.info("Run Model 2 to view results.")

	with exp3:
		res = st.session_state.opt_results.get('m3')
		if res:
			c1, c2, c3 = st.columns(3)
			c1.metric("Total Assigned Hours", f"{res['total_hours']:,.0f}")
			c2.metric("Total Exact Cost", f"{res['total_cost']:,.2f}")
			c3.metric("Range Gap (hrs)", f"{res['gap']:,.0f}")
			st.caption(f"λ = {res['lambda']}")
			st.dataframe(res['df'], use_container_width=True)
		else:
			st.info("Run Model 3 to view results.")
