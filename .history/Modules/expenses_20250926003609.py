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
        utilization_rate = (
            (df[CONSUMED_COL].sum() / df["2025 Budget"].sum() * 100)
            if df["2025 Budget"].sum() > 0
            else 0
        )
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
        if st.button(
            "📊 Generate Comprehensive Report", type="primary", use_container_width=True
        ):
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
        top_cc_budget = (
            df.groupby("Cost Center Name")["2025 Budget"]
            .sum()
            .sort_values(ascending=False)
            .head(5)
        )
        st.write("**Top 5 Cost Centers by Budget:**")
        for i, (cc, budget) in enumerate(top_cc_budget.items(), 1):
            st.write(f"{i}. {cc}: {budget:,.0f}")

    with col2:
        # Top accounts by budget
        top_accounts_budget = (
            df.groupby("Account name")["2025 Budget"]
            .sum()
            .sort_values(ascending=False)
            .head(5)
        )
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
        fig = px.pie(
            values=cc_distribution.values,
            names=cc_distribution.index,
            title="Budget Distribution by Cost Center",
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        # Account distribution
        account_distribution = df.groupby("Account name")["2025 Budget"].sum().head(10)
        fig = px.pie(
            values=account_distribution.values,
            names=account_distribution.index,
            title="Top 10 Accounts by Budget",
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # Year-over-year trends
    st.subheader("📈 Year-over-Year Trends")

    # Calculate trends
    total_2023 = df["2023 Budget"].sum()
    total_2024 = df["2024 Budget"].sum()
    total_2025 = df["2025 Budget"].sum()

    growth_2024 = (
        ((total_2024 - total_2023) / total_2023 * 100) if total_2023 > 0 else 0
    )
    growth_2025 = (
        ((total_2025 - total_2024) / total_2024 * 100) if total_2024 > 0 else 0
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("2023 Total", f"{total_2023:,.0f}")
        st.metric("2024 Total", f"{total_2024:,.0f}")
        st.metric("2025 Total", f"{total_2025:,.0f}")

    with col2:
        st.metric(
            "2024 Growth",
            f"{growth_2024:+.1f}%",
            delta=f"{'Increase' if growth_2024 > 0 else 'Decrease'}",
        )
        st.metric(
            "2025 Growth",
            f"{growth_2025:+.1f}%",
            delta=f"{'Increase' if growth_2025 > 0 else 'Decrease'}",
        )
        st.metric("3-Year CAGR", f"{((total_2025/total_2023)**(1/2)-1)*100:.1f}%")

    with col3:
        # Budget trend chart
        trend_data = pd.DataFrame(
            {
                "Year": ["2023", "2024", "2025"],
                "Budget": [total_2023, total_2024, total_2025],
            }
        )
        fig = px.line(
            trend_data,
            x="Year",
            y="Budget",
            title="Budget Trend Over Years",
            markers=True,
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # Quarterly analysis (if available)
    if "Quarter" in df.columns:
        st.subheader("📅 Quarterly Analysis")

        col1, col2 = st.columns(2)

        with col1:
            # Quarterly distribution
            quarterly_dist = df.groupby("Quarter")["2025 Budget"].sum()
            fig = px.bar(
                x=quarterly_dist.index,
                y=quarterly_dist.values,
                title="Budget Distribution by Quarter",
                color=quarterly_dist.index,
                color_discrete_map={
                    "Q1": "#1f77b4",
                    "Q2": "#ff7f0e",
                    "Q3": "#2ca02c",
                    "Q4": "#d62728",
                },
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            # Quarterly summary table
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
            st.success(
                f"High utilization rate ({utilization_rate:.1f}%) - Budget is being used effectively"
            )
        elif utilization_rate > 60:
            st.info(
                f"Moderate utilization rate ({utilization_rate:.1f}%) - Room for optimization"
            )
        else:
            st.warning(
                f"Low utilization rate ({utilization_rate:.1f}%) - Consider budget reallocation"
            )

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
        high_consumption = df[
            (df["2025 Budget"] > 0) & (df[CONSUMED_COL] / df["2025 Budget"] > 0.9)
        ]
        if len(high_consumption) > 0:
            st.error(
                f"🔥 High Consumption Alert: {len(high_consumption)} items >90% consumed"
            )
            for _, row in high_consumption.head(3).iterrows():
                st.write(
                    f"• {row['Cost Center Name']} - {row['Account name']}: {row[CONSUMED_COL]/row['2025 Budget']*100:.1f}%"
                )
        else:
            st.success("✅ No High Consumption Alarms")

        # Budget depletion alarms
        depleted_budget = df[df[AVAILABLE_COL] < df["2025 Budget"] * 0.1]
        if len(depleted_budget) > 0:
            st.error(
                f"💸 Budget Depletion Alert: {len(depleted_budget)} items <10% remaining"
            )
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
        remaining_by_cc = (
            df.groupby("Cost Center Name")[AVAILABLE_COL]
            .sum()
            .sort_values(ascending=False)
        )
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
        top_performers = (
            df.groupby("Cost Center Name")["2025 Budget"]
            .sum()
            .sort_values(ascending=False)
            .head(3)
        )
        st.write("🏆 Top 3 Budget Allocations:")
        for i, (cc, budget) in enumerate(top_performers.items(), 1):
            st.write(f"{i}. {cc}: {budget:,.0f}")

        # Efficient utilization
        efficient_cc = (
            df.groupby("Cost Center Name")
            .apply(
                lambda x: (
                    (x[CONSUMED_COL].sum() / x["2025 Budget"].sum() * 100)
                    if x["2025 Budget"].sum() > 0
                    else 0
                )
            )
            .sort_values(ascending=False)
            .head(3)
        )

        st.write("⚡ Most Efficient Cost Centers:")
        for i, (cc, efficiency) in enumerate(efficient_cc.items(), 1):
            st.write(f"{i}. {cc}: {efficiency:.1f}% utilization")

    with col2:
        st.write("**📉 Areas of Concern:**")

        # Budget decreases
        if growth_2025 < 0:
            st.error(f"📉 Budget Decline: {abs(growth_2025):.1f}% decrease")

        # Low performers
        low_performers = (
            df.groupby("Cost Center Name")["2025 Budget"].sum().sort_values().head(3)
        )
        st.write("🔻 Lowest Budget Allocations:")
        for i, (cc, budget) in enumerate(low_performers.items(), 1):
            st.write(f"{i}. {cc}: {budget:,.0f}")

        # Inefficient utilization
        inefficient_cc = (
            df.groupby("Cost Center Name")
            .apply(
                lambda x: (
                    (x[CONSUMED_COL].sum() / x["2025 Budget"].sum() * 100)
                    if x["2025 Budget"].sum() > 0
                    else 0
                )
            )
            .sort_values()
            .head(3)
        )

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
        growth_2024_vs_2023 = (
            ((total_2024 - total_2023) / total_2023 * 100) if total_2023 > 0 else 0
        )
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
