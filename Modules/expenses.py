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

CURRENT_YEAR = datetime.now().year
EXCEL_PATH = "Data/Budget Monitoring.xlsx"

# Budget columns for different years
BUDGET_COLUMNS = {
    "2023": "2023 Budget",
    "2024": "2024 Budget", 
    "2025": "2025 Budget"
}

CONSUMED_COL = "Consumed Amount"
AVAILABLE_COL = "Available Amount"

def get_quarter_from_date(date):
    """Get quarter (Q1, Q2, Q3, Q4) from a date"""
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
    """Get year from a date"""
    if pd.isna(date):
        return None
    return date.year

def load_budget_data():
    try:
        df = pd.read_excel(EXCEL_PATH)
        df.columns = df.columns.str.strip()  # Remove extra spaces

        # Force numeric types for all budget columns
        for year, col_name in BUDGET_COLUMNS.items():
            df[col_name] = pd.to_numeric(df[col_name], errors="coerce").fillna(0)
        
        df[CONSUMED_COL] = pd.to_numeric(df[CONSUMED_COL], errors="coerce").fillna(0)
        df[AVAILABLE_COL] = df[BUDGET_COLUMNS["2025"]] - df[CONSUMED_COL]

        # Process date column if it exists
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
            df["Quarter"] = df["Date"].apply(get_quarter_from_date)
            df["Year"] = df["Date"].apply(get_year_from_date)
        else:
            # If no date column, create dummy dates for 2025
            df["Date"] = pd.to_datetime("2025-01-01")
            df["Quarter"] = "Q1"
            df["Year"] = 2025

        return df
    except Exception as e:
        st.error(f"Failed to load budget data: {e}")
        return pd.DataFrame(columns=[
            "Cost Center Number", "Cost Center Name", "Account number",
            "Account name", "Date", "Quarter", "Year", "2023 Budget", "2024 Budget", "2025 Budget", 
            "Consumed Amount", "Available Amount"
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
        high_consumption = df[df[CONSUMED_COL] / df["2025 Budget"] > 0.9]
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
    


def show_filtered_dashboard():
    st.title("📊 Budget Dashboard")

    # ------------------ 🔧 Log Expense ------------------
    with st.expander("➕ Log New Expense", expanded=True):
        with st.form("log_expense_form"):
            col1, col2, col3 = st.columns(3)
            with col1:
                cost_center_number = st.text_input("Cost Center Number")
                account_number = st.text_input("Account Number")
                budget_2025 = st.number_input("2025 Budget", min_value=0.0, value=0.0)
            with col2:
                cost_center_name = st.text_input("Cost Center Name")
                account_name = st.text_input("Account Name")
                consumed = st.number_input("Consumed Amount", min_value=0.0, value=0.0)
            with col3:
                budget_2024 = st.number_input("2024 Budget", min_value=0.0, value=0.0)
                budget_2023 = st.number_input("2023 Budget", min_value=0.0, value=0.0)
                expense_date = st.date_input("Expense Date", value=datetime.now())
                submit = st.form_submit_button("Log Expense")

        if submit:
            available = budget_2025 - consumed
            row = {
                "Cost Center Number": cost_center_number,
                "Cost Center Name": cost_center_name,
                "Account number": account_number,
                "Account name": account_name,
                "Date": expense_date,
                "2023 Budget": budget_2023,
                "2024 Budget": budget_2024,
                "2025 Budget": budget_2025,
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

    # ------------------ 📑 Tabbed Interface ------------------
    tab1, tab2 = st.tabs(["📊 Analysis Dashboard", "📋 Summary & Insights"])
    
    with tab1:
        # ------------------ 🎯 Advanced Filters ------------------
        st.markdown("---")
        st.subheader("🎯 Filters")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Time period selection
            time_period = st.selectbox(
                "Select Time Period Type",
                options=["Annual", "Quarterly"],
                help="Choose between annual or quarterly analysis"
            )
        
        with col2:
            if time_period == "Annual":
                # Multi-year selection for annual data
                selected_years = st.multiselect(
                    "Select Years to Compare", 
                    options=list(BUDGET_COLUMNS.keys()),
                    default=["2025", "2024", "2023"]
                )
            else:
                # Year selection for quarterly data
                available_years = sorted(df["Year"].unique())
                selected_year = st.selectbox(
                    "Select Year for Quarterly Analysis",
                    options=available_years,
                    index=len(available_years)-1 if available_years else 0
                )
                selected_quarters = st.multiselect(
                    "Select Quarters to Compare",
                    options=["Q1", "Q2", "Q3", "Q4"],
                    default=["Q1", "Q2", "Q3", "Q4"]
                )
        
        with col3:
            cost_centers = ["All"] + sorted(df["Cost Center Name"].unique())
            selected_cc = st.selectbox("Select Cost Center", options=cost_centers)

        # Filter data based on selections
        filtered_df = df.copy()
        if selected_cc != "All":
            filtered_df = filtered_df[filtered_df["Cost Center Name"] == selected_cc]

        # ------------------ 🔢 KPI Summary ------------------
        if time_period == "Annual":
            if not selected_years:
                st.warning("Please select at least one year to display data.")
                return
            
            # Get the primary year for KPI calculations
            primary_year = selected_years[0]
            primary_budget_col = BUDGET_COLUMNS[primary_year]
            
            total_budget = filtered_df[primary_budget_col].sum()
            total_consumed = filtered_df[CONSUMED_COL].sum()
            total_remaining = filtered_df[AVAILABLE_COL].sum()

            col1, col2, col3 = st.columns(3)
            col1.metric(f"{primary_year} Total Budget", f"{total_budget:,.0f}")
            col2.metric("Total Consumed", f"{total_consumed:,.0f}")
            col3.metric("Total Remaining", f"{total_remaining:,.0f}")
            
        else:
            if not selected_quarters:
                st.warning("Please select at least one quarter to display data.")
                return
            
            # Filter by selected year and quarters
            year_filtered = filtered_df[filtered_df["Year"] == selected_year]
            quarter_filtered = year_filtered[year_filtered["Quarter"].isin(selected_quarters)]
            
            # Calculate quarterly KPIs based on date-filtered data
            total_quarterly_budget = quarter_filtered[BUDGET_COLUMNS[str(selected_year)]].sum()
            total_consumed = quarter_filtered[CONSUMED_COL].sum()
            total_remaining = quarter_filtered[AVAILABLE_COL].sum()

            col1, col2, col3 = st.columns(3)
            col1.metric(f"{selected_year} Quarterly Budget", f"{total_quarterly_budget:,.0f}")
            col2.metric("Total Consumed", f"{total_consumed:,.0f}")
            col3.metric("Total Remaining", f"{total_remaining:,.0f}")

        # ------------------ 📊 Visualizations ------------------
        st.markdown("---")
        
        if time_period == "Annual":
            st.subheader("📈 Annual Budget Comparison")
            
            if selected_cc != "All":
                # Show multi-year comparison for selected cost center
                yearly_data = []
                for year in selected_years:
                    col_name = BUDGET_COLUMNS[year]
                    yearly_data.append({
                        'Year': year,
                        'Budget': filtered_df[col_name].sum()
                    })
                
                yearly_df = pd.DataFrame(yearly_data)
                
                # Create color map for selected years
                colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']
                color_map = {year: colors[i % len(colors)] for i, year in enumerate(selected_years)}
                
                fig = px.bar(yearly_df, x='Year', y='Budget', 
                            title=f"{selected_cc} - Annual Budget by Year",
                            color='Year', color_discrete_map=color_map)
                st.plotly_chart(fig, use_container_width=True)
                
                # Add line chart for trend visualization
                fig_line = px.line(yearly_df, x='Year', y='Budget', 
                                  title=f"{selected_cc} - Annual Budget Trend",
                                  markers=True)
                st.plotly_chart(fig_line, use_container_width=True)
                
            else:
                # Show multi-year comparison for all cost centers
                yearly_by_cc = []
                for year in selected_years:
                    col_name = BUDGET_COLUMNS[year]
                    year_data = df.groupby("Cost Center Name")[col_name].sum().reset_index()
                    year_data['Year'] = year
                    yearly_by_cc.append(year_data)
                
                yearly_cc_df = pd.concat(yearly_by_cc, ignore_index=True)
                
                # Create color map for selected years
                colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']
                color_map = {year: colors[i % len(colors)] for i, year in enumerate(selected_years)}
                
                fig = px.bar(yearly_cc_df, x="Cost Center Name", y=col_name, 
                            color="Year", barmode="group",
                            title="Annual Budget by Cost Center and Year",
                            color_discrete_map=color_map)
                st.plotly_chart(fig, use_container_width=True)
        
        else:
            st.subheader("📈 Quarterly Budget Analysis")
            
            # Filter data for selected year and quarters
            year_filtered = filtered_df[filtered_df["Year"] == selected_year]
            quarter_filtered = year_filtered[year_filtered["Quarter"].isin(selected_quarters)]
            
            if selected_cc != "All":
                # Show quarterly comparison for selected cost center
                quarterly_data = []
                for quarter in selected_quarters:
                    quarter_budget = quarter_filtered[quarter_filtered["Quarter"] == quarter][BUDGET_COLUMNS[str(selected_year)]].sum()
                    quarterly_data.append({
                        'Quarter': quarter,
                        'Budget': quarter_budget
                    })
                
                quarterly_df = pd.DataFrame(quarterly_data)
                
                # Create color map for quarters
                quarter_colors = {'Q1': '#1f77b4', 'Q2': '#ff7f0e', 'Q3': '#2ca02c', 'Q4': '#d62728'}
                
                fig = px.bar(quarterly_df, x='Quarter', y='Budget', 
                            title=f"{selected_cc} - {selected_year} Quarterly Budget",
                            color='Quarter', color_discrete_map=quarter_colors)
                st.plotly_chart(fig, use_container_width=True)
                
                # Add line chart for quarterly trend
                fig_line = px.line(quarterly_df, x='Quarter', y='Budget', 
                                  title=f"{selected_cc} - {selected_year} Quarterly Trend",
                                  markers=True)
                st.plotly_chart(fig_line, use_container_width=True)
                
            else:
                # Show quarterly comparison for all cost centers
                quarterly_by_cc = []
                for quarter in selected_quarters:
                    quarter_data = quarter_filtered[quarter_filtered["Quarter"] == quarter].groupby("Cost Center Name")[BUDGET_COLUMNS[str(selected_year)]].sum().reset_index()
                    quarter_data['Quarter'] = quarter
                    quarterly_by_cc.append(quarter_data)
                
                if quarterly_by_cc:
                    quarterly_cc_df = pd.concat(quarterly_by_cc, ignore_index=True)
                    
                    # Create color map for quarters
                    quarter_colors = {'Q1': '#1f77b4', 'Q2': '#ff7f0e', 'Q3': '#2ca02c', 'Q4': '#d62728'}
                    
                    fig = px.bar(quarterly_cc_df, x="Cost Center Name", y=BUDGET_COLUMNS[str(selected_year)], 
                                color="Quarter", barmode="group",
                                title=f"{selected_year} Quarterly Budget by Cost Center",
                                color_discrete_map=quarter_colors)
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Add heatmap for quarterly visualization
                    pivot_df = quarterly_cc_df.pivot(index="Cost Center Name", columns="Quarter", values=BUDGET_COLUMNS[str(selected_year)])
                    fig_heatmap = px.imshow(pivot_df, 
                                           title=f"{selected_year} Quarterly Budget Heatmap",
                                           aspect="auto",
                                           color_continuous_scale="Viridis")
                    st.plotly_chart(fig_heatmap, use_container_width=True)

        st.markdown("---")

        # ------------------ 📊 Additional Charts ------------------
        if time_period == "Annual" and len(selected_years) == 1:
            # Single year selected - show traditional charts
            selected_budget_col = BUDGET_COLUMNS[selected_years[0]]
            bar_df = filtered_df.groupby("Cost Center Name")[[CONSUMED_COL, AVAILABLE_COL]].sum().reset_index()
            pie_df = filtered_df.groupby("Cost Center Name")[selected_budget_col].sum().reset_index()

            st.subheader(f"📉 {selected_years[0]} Budget Usage")
            st.plotly_chart(px.bar(bar_df, x="Cost Center Name", y=[CONSUMED_COL, AVAILABLE_COL],
                                   barmode="group", title=f"{selected_years[0]} Budget Usage"))

            st.subheader(f"🥧 {selected_years[0]} Budget Breakdown by Cost Center")
            st.plotly_chart(px.pie(pie_df, names="Cost Center Name", values=selected_budget_col,
                                   title=f"{selected_years[0]} Budget Share"))
        
        elif time_period == "Quarterly":
            # Quarterly pie chart
            quarterly_summary = []
            for quarter in selected_quarters:
                quarter_budget = quarter_filtered[quarter_filtered["Quarter"] == quarter][BUDGET_COLUMNS[str(selected_year)]].sum()
                quarterly_summary.append({
                    'Quarter': quarter,
                    'Budget': quarter_budget
                })
            
            if quarterly_summary:
                quarterly_summary_df = pd.DataFrame(quarterly_summary)
                st.subheader(f"🥧 {selected_year} Quarterly Budget Distribution")
                st.plotly_chart(px.pie(quarterly_summary_df, names="Quarter", values="Budget",
                                       title=f"{selected_year} Quarterly Budget Share"))

        # ------------------ 🎯 Filtered Table View ------------------
        st.subheader("📋 Detailed Data View")
        
        if time_period == "Annual":
            # Show the filtered data with selected years
            display_columns = [
                "Cost Center Number", "Cost Center Name", "Account number", "Account name", "Date", "Quarter"
            ] + [BUDGET_COLUMNS[year] for year in selected_years] + [CONSUMED_COL, AVAILABLE_COL]
        else:
            # Show the filtered data with selected quarters
            display_columns = [
                "Cost Center Number", "Cost Center Name", "Account number", "Account name", "Date", "Quarter"
            ] + [BUDGET_COLUMNS[str(selected_year)]] + [CONSUMED_COL, AVAILABLE_COL]
        
        # Filter display data based on time period
        if time_period == "Quarterly":
            display_df = quarter_filtered
        else:
            display_df = filtered_df
        
        st.dataframe(display_df[display_columns].reset_index(drop=True), use_container_width=True)

        if selected_cc != "All":
            # Account-wise breakdown for selected cost center
            st.subheader(f"📊 {selected_cc} - Account-wise Breakdown")
            
            if time_period == "Annual":
                # Account-wise charts for selected years
                account_comparison_data = []
                for year in selected_years:
                    col_name = BUDGET_COLUMNS[year]
                    account_data = filtered_df.groupby("Account name")[col_name].sum().reset_index()
                    account_data['Year'] = year
                    account_comparison_data.append(account_data)
                
                account_comparison_df = pd.concat(account_comparison_data, ignore_index=True)
                
                # Create color map for selected years
                colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']
                color_map = {year: colors[i % len(colors)] for i, year in enumerate(selected_years)}
                
                st.plotly_chart(
                    px.bar(account_comparison_df, x="Account name", y=col_name,
                           color="Year", barmode="group",
                           title=f"{selected_cc} - Account-wise Annual Budget Comparison")
                )

                # Account-wise Table with selected years
                account_display_cols = ["Account number", "Account name", "Date", "Quarter"] + [BUDGET_COLUMNS[year] for year in selected_years] + [CONSUMED_COL, AVAILABLE_COL]
                st.dataframe(
                    filtered_df[account_display_cols].reset_index(drop=True),
                    use_container_width=True
                )
            
            else:
                # Account-wise charts for selected quarters
                account_quarterly_data = []
                for quarter in selected_quarters:
                    quarter_account_data = quarter_filtered[quarter_filtered["Quarter"] == quarter].groupby("Account name")[BUDGET_COLUMNS[str(selected_year)]].sum().reset_index()
                    quarter_account_data['Quarter'] = quarter
                    account_quarterly_data.append(quarter_account_data)
                
                if account_quarterly_data:
                    account_quarterly_df = pd.concat(account_quarterly_data, ignore_index=True)
                    
                    # Create color map for quarters
                    quarter_colors = {'Q1': '#1f77b4', 'Q2': '#ff7f0e', 'Q3': '#2ca02c', 'Q4': '#d62728'}
                    
                    st.plotly_chart(
                        px.bar(account_quarterly_df, x="Account name", y=BUDGET_COLUMNS[str(selected_year)],
                               color="Quarter", barmode="group",
                               title=f"{selected_cc} - Account-wise Quarterly Budget Comparison")
                    )

                    # Account-wise Table with selected quarters
                    account_display_cols = ["Account number", "Account name", "Date", "Quarter", BUDGET_COLUMNS[str(selected_year)], CONSUMED_COL, AVAILABLE_COL]
                    st.dataframe(
                        quarter_filtered[account_display_cols].reset_index(drop=True),
                        use_container_width=True
                    )
    
    with tab2:
        show_summary_tab(df)
