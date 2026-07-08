"""
RM Sales Intelligence Dashboard
Polymer Additive Trading Business
Covers: Descriptive, Diagnostic, Predictive, Prescriptive analytics
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import timedelta

st.set_page_config(page_title="RM Sales Intelligence Dashboard", layout="wide", page_icon="📊")

REQUIRED_COLS = ["Date", "GST", "Buyers", "Product", "Sales", "Voucher", "Quantity", "Rate", "Value"]

# ----------------------------------------------------------------------------------
# SAMPLE DATA GENERATOR (used until real data is uploaded)
# ----------------------------------------------------------------------------------
@st.cache_data
def generate_sample_data(seed=42, months=15):
    rng = np.random.default_rng(seed)

    products = [
        "PVC Stabilizer - Ca/Zn", "PVC Stabilizer - Pb", "CPE 135A", "ACR Impact Modifier",
        "Processing Aid ACR", "PE Wax", "Lubricant - Internal", "Lubricant - External",
        "Impact Modifier MBS"
    ]
    states = ["DL", "GJ", "MH"]

    buyer_pool = []
    for i in range(38):
        state = rng.choice(states, p=[0.45, 0.25, 0.30])
        buyer_pool.append({
            "Buyers": f"{rng.choice(['Shree','Om','Jai','Balaji','National','Prime','Supreme','Krishna'])} "
                      f"{rng.choice(['Polymers','Plastics','Compounds','Industries','Extrusions','Pipes'])} "
                      f"{'Pvt Ltd' if rng.random() > 0.4 else ''}".strip(),
            "GST": f"{rng.integers(1,37):02d}AAAA{rng.integers(1000,9999)}A1Z{rng.integers(1,9)}",
            "state": state,
            "tier": rng.choice(["A", "B", "C"], p=[0.15, 0.35, 0.5])
        })

    start = pd.Timestamp("2025-04-01")
    dates = pd.date_range(start, periods=months, freq="MS")

    rows = []
    voucher_no = 1000

    for m_idx, month_start in enumerate(dates):
        # mild seasonality: dip in monsoon months (Jul-Sep), pickup in Oct-Mar
        month_num = month_start.month
        season_factor = 1.15 if month_num in [10, 11, 12, 1, 2, 3] else (0.85 if month_num in [7, 8, 9] else 1.0)
        # slight overall growth trend
        trend_factor = 1 + (m_idx * 0.012)

        n_orders = int(rng.integers(25, 45) * season_factor)

        for _ in range(n_orders):
            buyer = buyer_pool[rng.integers(0, len(buyer_pool))]
            # Tier A buyers order more often & bigger
            tier_qty_mult = {"A": 3.0, "B": 1.6, "C": 1.0}[buyer["tier"]]
            product = rng.choice(products, p=[0.20,0.10,0.13,0.11,0.09,0.09,0.10,0.09,0.09])

            base_rate = {
                "PVC Stabilizer - Ca/Zn": 145, "PVC Stabilizer - Pb": 120, "CPE 135A": 155,
                "ACR Impact Modifier": 210, "Processing Aid ACR": 195, "PE Wax": 135,
                "Lubricant - Internal": 165, "Lubricant - External": 160, "Impact Modifier MBS": 225
            }[product]
            rate = round(base_rate * rng.uniform(0.94, 1.08) * (1 + m_idx*0.003), 2)
            qty = round(rng.uniform(500, 3000) * tier_qty_mult * trend_factor, 0)
            day = rng.integers(1, 28)
            po_date = month_start + timedelta(days=int(day))

            voucher_no += 1
            rows.append({
                "Date": po_date,
                "GST": buyer["GST"],
                "Buyers": buyer["Buyers"],
                "Product": product,
                "Sales": buyer["state"],
                "Voucher": f"V{voucher_no}",
                "Quantity": qty,
                "Rate": rate,
                "Value": round(qty * rate, 2)
            })

    # simulate churn: some buyers stop ordering in last 2-3 months
    df = pd.DataFrame(rows)
    churn_buyers = [b["Buyers"] for b in buyer_pool if b["tier"] == "C"]
    churn_sample = rng.choice(churn_buyers, size=min(4, len(churn_buyers)), replace=False)
    cutoff = dates[-3]
    df = df[~((df["Buyers"].isin(churn_sample)) & (df["Date"] >= cutoff))]

    return df.sort_values("Date").reset_index(drop=True)


def validate_columns(df):
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    return missing


@st.cache_data
def load_uploaded(file):
    if file.name.endswith(".csv"):
        df = pd.read_csv(file)
    else:
        df = pd.read_excel(file)
    return df


# ----------------------------------------------------------------------------------
# SIDEBAR — DATA SOURCE
# ----------------------------------------------------------------------------------
st.sidebar.title("📁 Data Source")
uploaded_file = st.sidebar.file_uploader("Upload your RM sales file (.xlsx or .csv)", type=["xlsx", "xls", "csv"])

using_sample = False
if uploaded_file is not None:
    try:
        raw_df = load_uploaded(uploaded_file)
        missing = validate_columns(raw_df)
        if missing:
            st.sidebar.error(f"Missing required columns: {', '.join(missing)}\n\nExpected: {', '.join(REQUIRED_COLS)}")
            st.sidebar.warning("Showing sample data instead until you fix the file.")
            raw_df = generate_sample_data()
            using_sample = True
        else:
            st.sidebar.success(f"Loaded {len(raw_df)} rows from your file ✅")
    except Exception as e:
        st.sidebar.error(f"Could not read file: {e}")
        raw_df = generate_sample_data()
        using_sample = True
else:
    raw_df = generate_sample_data()
    using_sample = True
    st.sidebar.info("No file uploaded — showing **sample data** so you can preview the dashboard. Upload your real file above to replace it.")

# clean/parse
df = raw_df.copy()
df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
df = df.dropna(subset=["Date"])
for col in ["Quantity", "Rate", "Value"]:
    df[col] = pd.to_numeric(df[col], errors="coerce")
df = df.dropna(subset=["Quantity", "Rate", "Value"])
df["Month"] = df["Date"].dt.to_period("M").dt.to_timestamp()

if using_sample:
    st.warning("⚠️ You're viewing **sample / dummy data** (randomly generated) so you can see how the dashboard works. Upload your actual Excel file in the sidebar to see your real RM's numbers.", icon="⚠️")

# ----------------------------------------------------------------------------------
# SIDEBAR — FILTERS
# ----------------------------------------------------------------------------------
st.sidebar.title("🔎 Filters")
min_d, max_d = df["Date"].min(), df["Date"].max()
date_range = st.sidebar.date_input("Date range", value=(min_d, max_d), min_value=min_d, max_value=max_d)
if len(date_range) == 2:
    df = df[(df["Date"] >= pd.Timestamp(date_range[0])) & (df["Date"] <= pd.Timestamp(date_range[1]))]

sel_states = st.sidebar.multiselect("Territory (Sales)", sorted(df["Sales"].unique()), default=sorted(df["Sales"].unique()))
sel_products = st.sidebar.multiselect("Product", sorted(df["Product"].unique()), default=sorted(df["Product"].unique()))
df = df[df["Sales"].isin(sel_states) & df["Product"].isin(sel_products)]

st.title("📊 RM Sales Intelligence Dashboard")
st.caption("Polymer Additive Trading — Descriptive · Diagnostic · Predictive · Prescriptive")

tab1, tab2, tab3, tab4 = st.tabs(["📈 Descriptive", "🔍 Diagnostic", "🔮 Predictive", "🎯 Prescriptive"])

# ====================================================================================
# TAB 1 — DESCRIPTIVE
# ====================================================================================
with tab1:
    st.subheader("Performance Scorecard")

    total_value = df["Value"].sum()
    total_qty = df["Quantity"].sum()
    n_customers = df["GST"].nunique()
    n_orders = df["Voucher"].nunique()
    avg_order_value = total_value / n_orders if n_orders else 0

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Revenue", f"₹{total_value/1e5:,.1f}L")
    c2.metric("Total Volume", f"{total_qty/1000:,.1f} MT")
    c3.metric("Active Customers", n_customers)
    c4.metric("Total Orders", n_orders)
    c5.metric("Avg Order Value", f"₹{avg_order_value/1000:,.1f}K")

    st.divider()

    colA, colB = st.columns(2)
    with colA:
        monthly = df.groupby("Month").agg(Revenue=("Value", "sum"), Quantity=("Quantity","sum")).reset_index()
        fig = px.line(monthly, x="Month", y="Revenue", markers=True, title="Monthly Revenue Trend")
        fig.update_layout(yaxis_title="Revenue (₹)")
        st.plotly_chart(fig, use_container_width=True)

    with colB:
        territory = df.groupby("Sales")["Value"].sum().reset_index()
        fig2 = px.pie(territory, names="Sales", values="Value", title="Revenue by Territory", hole=0.4)
        st.plotly_chart(fig2, use_container_width=True)

    colC, colD = st.columns(2)
    with colC:
        prod = df.groupby("Product")["Value"].sum().sort_values(ascending=True).reset_index()
        fig3 = px.bar(prod, x="Value", y="Product", orientation="h", title="Revenue by Product")
        st.plotly_chart(fig3, use_container_width=True)

    with colD:
        top_customers = df.groupby("Buyers")["Value"].sum().sort_values(ascending=False).head(10).reset_index()
        fig4 = px.bar(top_customers, x="Value", y="Buyers", orientation="h", title="Top 10 Customers by Revenue")
        fig4.update_layout(yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig4, use_container_width=True)

    st.divider()
    st.subheader("🔽 Customer Drill-down")
    sel_buyer = st.selectbox("Select a customer to inspect", sorted(df["Buyers"].unique()))
    buyer_df = df[df["Buyers"] == sel_buyer].sort_values("Date", ascending=False)

    b1, b2, b3, b4 = st.columns(4)
    b1.metric("Total Value", f"₹{buyer_df['Value'].sum()/1000:,.1f}K")
    b2.metric("Total Qty", f"{buyer_df['Quantity'].sum():,.0f} kg")
    b3.metric("Orders", buyer_df["Voucher"].nunique())
    b4.metric("Avg Rate", f"₹{buyer_df['Rate'].mean():,.1f}")

    st.dataframe(buyer_df[["Date","Voucher","Product","Quantity","Rate","Value"]], use_container_width=True, hide_index=True)

# ====================================================================================
# TAB 2 — DIAGNOSTIC
# ====================================================================================
with tab2:
    st.subheader("Why is performance moving the way it is?")

    monthly_pv = df.groupby("Month").agg(Revenue=("Value","sum"), Quantity=("Quantity","sum")).reset_index()
    monthly_pv["Avg_Rate"] = monthly_pv["Revenue"] / monthly_pv["Quantity"]
    monthly_pv["Rev_Growth_%"] = monthly_pv["Revenue"].pct_change() * 100
    monthly_pv["Qty_Growth_%"] = monthly_pv["Quantity"].pct_change() * 100
    monthly_pv["Rate_Growth_%"] = monthly_pv["Avg_Rate"].pct_change() * 100

    st.markdown("**Revenue growth decomposition — is growth from price or volume?**")
    fig5 = go.Figure()
    fig5.add_trace(go.Bar(x=monthly_pv["Month"], y=monthly_pv["Qty_Growth_%"], name="Volume Growth %"))
    fig5.add_trace(go.Bar(x=monthly_pv["Month"], y=monthly_pv["Rate_Growth_%"], name="Price/Rate Growth %"))
    fig5.update_layout(barmode="group", title="Month-on-Month: Volume vs Price Growth")
    st.plotly_chart(fig5, use_container_width=True)

    colA, colB = st.columns(2)
    with colA:
        st.markdown("**Customer concentration (Pareto)**")
        cust_val = df.groupby("Buyers")["Value"].sum().sort_values(ascending=False).reset_index()
        cust_val["Cum_%"] = cust_val["Value"].cumsum() / cust_val["Value"].sum() * 100
        fig6 = go.Figure()
        fig6.add_trace(go.Bar(x=cust_val["Buyers"], y=cust_val["Value"], name="Revenue"))
        fig6.add_trace(go.Scatter(x=cust_val["Buyers"], y=cust_val["Cum_%"], name="Cumulative %", yaxis="y2"))
        fig6.update_layout(
            yaxis=dict(title="Revenue"),
            yaxis2=dict(title="Cumulative %", overlaying="y", side="right", range=[0,100]),
            xaxis=dict(showticklabels=False),
            title="Customer Pareto — Top few driving how much revenue?"
        )
        st.plotly_chart(fig6, use_container_width=True)
        top20pct_n = max(1, int(len(cust_val)*0.2))
        top20_share = cust_val.head(top20pct_n)["Value"].sum() / cust_val["Value"].sum() * 100
        st.info(f"Top {top20pct_n} customers ({int(20)}% of base) drive **{top20_share:.0f}%** of revenue.")

    with colB:
        st.markdown("**New vs Repeat business**")
        first_order = df.groupby("Buyers")["Month"].min().reset_index().rename(columns={"Month":"First_Month"})
        merged = df.merge(first_order, on="Buyers")
        merged["Type"] = np.where(merged["Month"] == merged["First_Month"], "New", "Repeat")
        nr = merged.groupby(["Month","Type"])["Value"].sum().reset_index()
        fig7 = px.bar(nr, x="Month", y="Value", color="Type", title="New vs Repeat Customer Revenue", barmode="stack")
        st.plotly_chart(fig7, use_container_width=True)

    st.divider()
    st.markdown("**⚠️ Churn watch — customers active earlier but silent recently**")
    last_month = df["Month"].max()
    lookback = last_month - pd.DateOffset(months=2)
    active_recent = set(df[df["Month"] >= lookback]["Buyers"].unique())
    all_buyers = set(df["Buyers"].unique())
    lapsed = all_buyers - active_recent

    if lapsed:
        lapsed_df = df[df["Buyers"].isin(lapsed)].groupby("Buyers").agg(
            Last_Order=("Date","max"), Historical_Value=("Value","sum"), Orders=("Voucher","nunique")
        ).sort_values("Historical_Value", ascending=False).reset_index()
        st.dataframe(lapsed_df, use_container_width=True, hide_index=True)
    else:
        st.success("No lapsed customers detected in the last 2 months of data.")

    st.markdown("**Territory-level realized price comparison**")
    terr_rate = df.groupby("Sales").agg(Avg_Rate=("Rate","mean"), Revenue=("Value","sum"), Volume=("Quantity","sum")).reset_index()
    st.dataframe(terr_rate, use_container_width=True, hide_index=True)

# ====================================================================================
# TAB 3 — PREDICTIVE
# ====================================================================================
with tab3:
    st.subheader("What's likely to happen next?")

    monthly_rev = df.groupby("Month")["Value"].sum().reset_index().sort_values("Month")
    monthly_rev["t"] = range(len(monthly_rev))

    if len(monthly_rev) >= 4:
        from numpy.polynomial import polynomial as P
        coeffs = np.polyfit(monthly_rev["t"], monthly_rev["Value"], 1)
        slope, intercept = coeffs[0], coeffs[1]

        future_periods = 3
        future_t = range(len(monthly_rev), len(monthly_rev) + future_periods)
        future_months = pd.date_range(monthly_rev["Month"].max() + pd.DateOffset(months=1), periods=future_periods, freq="MS")
        future_vals = [slope * t + intercept for t in future_t]

        # simple seasonal adjustment using historical month-of-year average deviation, if enough history
        monthly_rev["month_num"] = monthly_rev["Month"].dt.month
        overall_mean = monthly_rev["Value"].mean()
        seasonal_idx = (monthly_rev.groupby("month_num")["Value"].mean() / overall_mean).to_dict()

        adj_future_vals = []
        for m, v in zip(future_months, future_vals):
            idx = seasonal_idx.get(m.month, 1.0)
            adj_future_vals.append(v * idx)

        forecast_df = pd.DataFrame({"Month": future_months, "Value": adj_future_vals, "Type": "Forecast"})
        hist_df = monthly_rev[["Month","Value"]].copy()
        hist_df["Type"] = "Actual"
        combo = pd.concat([hist_df, forecast_df], ignore_index=True)

        fig8 = px.line(combo, x="Month", y="Value", color="Type", markers=True, title="Revenue Forecast — Next 3 Months")
        st.plotly_chart(fig8, use_container_width=True)

        st.caption("Forecast = linear trend + simple seasonal adjustment based on month-of-year pattern in your historical data. With ~15 months of history this is directional, not a guarantee — treat it as a planning input, not a hard target.")

        f1, f2, f3 = st.columns(3)
        for col, m, v in zip([f1,f2,f3], future_months, adj_future_vals):
            col.metric(m.strftime("%b %Y"), f"₹{v/1e5:,.1f}L")
    else:
        st.warning("Not enough months of data to forecast reliably (need at least 4).")

    st.divider()
    st.markdown("**📅 Predicted next order date per customer** (based on historical order cadence)")

    cust_orders = df.groupby("Buyers")["Date"].apply(lambda x: sorted(x)).reset_index()
    rows = []
    for _, r in cust_orders.iterrows():
        dates_list = r["Date"]
        if len(dates_list) >= 2:
            gaps = [(dates_list[i+1]-dates_list[i]).days for i in range(len(dates_list)-1)]
            avg_gap = np.mean(gaps)
            last_order = dates_list[-1]
            predicted_next = last_order + timedelta(days=avg_gap)
            days_overdue = (df["Date"].max() - predicted_next).days
            rows.append({
                "Buyers": r["Buyers"], "Last_Order": last_order.date(), "Avg_Gap_Days": round(avg_gap,0),
                "Predicted_Next_Order": predicted_next.date(),
                "Status": "🔴 Overdue" if days_overdue > 0 else "🟢 On track"
            })
    if rows:
        cadence_df = pd.DataFrame(rows).sort_values("Predicted_Next_Order")
        st.dataframe(cadence_df, use_container_width=True, hide_index=True)
    else:
        st.info("Not enough repeat orders yet to predict cadence.")

# ====================================================================================
# TAB 4 — PRESCRIPTIVE
# ====================================================================================
with tab4:
    st.subheader("What should the RM actually do?")

    snapshot_date = df["Date"].max() + pd.Timedelta(days=1)
    rfm = df.groupby("Buyers").agg(
        Recency=("Date", lambda x: (snapshot_date - x.max()).days),
        Frequency=("Voucher", "nunique"),
        Monetary=("Value", "sum")
    ).reset_index()

    rfm["R_Score"] = pd.qcut(rfm["Recency"].rank(method="first"), 5, labels=[5,4,3,2,1]).astype(int)
    rfm["F_Score"] = pd.qcut(rfm["Frequency"].rank(method="first"), 5, labels=[1,2,3,4,5]).astype(int)
    rfm["M_Score"] = pd.qcut(rfm["Monetary"].rank(method="first"), 5, labels=[1,2,3,4,5]).astype(int)
    rfm["RFM_Score"] = rfm["R_Score"] + rfm["F_Score"] + rfm["M_Score"]

    def segment(row):
        if row["RFM_Score"] >= 13:
            return "🏆 Champions — call this week"
        elif row["RFM_Score"] >= 10:
            return "💎 Loyal — upsell/cross-sell"
        elif row["RFM_Score"] >= 7:
            return "⚠️ At Risk — re-engage soon"
        else:
            return "❄️ Dormant/Low value — win-back or deprioritize"

    rfm["Segment"] = rfm.apply(segment, axis=1)
    rfm = rfm.sort_values("RFM_Score", ascending=False)

    seg_summary = rfm["Segment"].value_counts().reset_index()
    seg_summary.columns = ["Segment", "Customers"]
    fig9 = px.bar(seg_summary, x="Segment", y="Customers", title="Customer Segments (RFM)", color="Segment")
    st.plotly_chart(fig9, use_container_width=True)

    st.markdown("**Full RFM action list** — sort/filter to build the RM's call list")
    st.dataframe(
        rfm[["Buyers","Recency","Frequency","Monetary","RFM_Score","Segment"]].reset_index(drop=True),
        use_container_width=True, hide_index=True
    )

    st.divider()
    colA, colB = st.columns(2)

    with colA:
        st.markdown("**🔗 Cross-sell opportunity**")
        st.caption("Customers buying a narrow slice of your product basket — potential to sell more categories")
        basket_size = df["Product"].nunique()
        cust_breadth = df.groupby("Buyers")["Product"].nunique().reset_index().rename(columns={"Product":"Products_Bought"})
        cust_breadth["Basket_Coverage_%"] = (cust_breadth["Products_Bought"] / basket_size * 100).round(0)
        cust_breadth = cust_breadth.merge(rfm[["Buyers","Monetary"]], on="Buyers")
        cross_sell = cust_breadth[cust_breadth["Basket_Coverage_%"] < 30].sort_values("Monetary", ascending=False)
        st.dataframe(cross_sell, use_container_width=True, hide_index=True)

    with colB:
        st.markdown("**📞 Win-back priority list**")
        st.caption("High historical value but gone quiet — call before a competitor does")
        winback = rfm[(rfm["Segment"].str.contains("Dormant") | rfm["Segment"].str.contains("At Risk"))].sort_values("Monetary", ascending=False).head(10)
        st.dataframe(winback[["Buyers","Recency","Monetary","Segment"]], use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("**💰 Pricing consistency check**")
    st.caption("Same product, different realized rates across customers — margin leakage or negotiation inconsistency?")
    pricing_check = df.groupby("Product").agg(
        Min_Rate=("Rate","min"), Max_Rate=("Rate","max"), Avg_Rate=("Rate","mean")
    ).reset_index()
    pricing_check["Spread_%"] = ((pricing_check["Max_Rate"] - pricing_check["Min_Rate"]) / pricing_check["Avg_Rate"] * 100).round(1)
    pricing_check = pricing_check.sort_values("Spread_%", ascending=False)
    st.dataframe(pricing_check, use_container_width=True, hide_index=True)
    if pricing_check["Spread_%"].max() > 15:
        st.warning(f"⚠️ {pricing_check.iloc[0]['Product']} shows a {pricing_check.iloc[0]['Spread_%']:.0f}% rate spread across customers — worth a pricing review.")

st.divider()
st.caption("Built for RM performance review · Descriptive · Diagnostic · Predictive · Prescriptive")
