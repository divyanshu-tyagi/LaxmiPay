import streamlit as st
import requests
import pandas as pd
import qrcode
from io import BytesIO
import json

API_URL = "http://localhost:8000"

# ---------- Auth Guard ----------
if not st.session_state.get("authenticated_admin"):
    st.error("❌ Access Denied. Please log in as Admin.")
    if st.button("Go to Login"):
        st.switch_page("app.py")
    st.stop()

st.set_page_config(page_title="Admin Dashboard", page_icon="🛠️", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');
    html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
    .stApp { background: #0f0f13; color: #e8e8e8; }
    .metric-card {
        background: #181820; border: 1px solid #2a2a35;
        border-radius: 12px; padding: 1rem 1.2rem; text-align: center;
    }
    .metric-val { font-family: 'IBM Plex Mono', monospace; font-size: 2rem; color: #00e5a0; font-weight: 600; }
    .metric-lbl { font-size: 0.78rem; color: #777; text-transform: uppercase; letter-spacing: 1px; }
    .flag-badge { background: #2e0a0a; color: #ff5c5c; border-radius: 4px; padding: 2px 8px; font-size: 0.75rem; }
    .ok-badge   { background: #0a2e1f; color: #00e5a0; border-radius: 4px; padding: 2px 8px; font-size: 0.75rem; }
    [data-testid="stSidebar"] { background: #0d0d11 !important; border-right: 1px solid #1e1e28; }
    .stButton > button { border-radius: 8px; font-family: 'IBM Plex Mono', monospace; }
    div[data-testid="metric-container"] { background: #181820; border: 1px solid #2a2a35; border-radius: 12px; padding: 0.8rem; }
</style>
""", unsafe_allow_html=True)


# ---------- Sidebar ----------
with st.sidebar:
    st.markdown("## 🛠️ Admin Panel")
    st.markdown("---")
    section = st.radio("Navigate", ["📊 Analytics", "🔍 RFID Manager", "📋 Audit Log"])
    st.markdown("---")
    if st.button("🚪 Logout"):
        del st.session_state.authenticated_admin
        st.switch_page("app.py")


# ---------- Helpers ----------
@st.cache_data(ttl=30)
def fetch_rfid_list():
    try:
        r = requests.get(f"{API_URL}/rfid-list", timeout=5)
        if r.status_code == 200:
            return r.json().get("rfids", [])
    except Exception:
        pass
    return []

@st.cache_data(ttl=30)
def fetch_analytics():
    try:
        r = requests.get(f"{API_URL}/analytics/summary", timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


# ============================================================
# SECTION: Analytics
# ============================================================
if section == "📊 Analytics":
    st.title("📊 System Analytics")
    st.markdown("---")

    data = fetch_analytics()
    if not data:
        st.error("Could not load analytics. Is the API running?")
        st.stop()

    # KPI Row
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 Total Balance in Circulation", f"₹{data['total_balance_in_circulation']:,}")
    c2.metric("📦 Total Transactions", data["transaction_count"])
    c3.metric("📈 Avg Transaction (₹)", f"₹{data['avg_transaction_amount']}")
    c4.metric("🚨 Flagged Transactions", data["flagged_transactions"])

    st.markdown("---")

    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.subheader("📅 Daily Transaction Volume (Last 14 Days)")
        if data["daily_volume"]:
            df_daily = pd.DataFrame(data["daily_volume"])
            df_daily["day"] = pd.to_datetime(df_daily["day"])
            df_daily = df_daily.sort_values("day")
            df_daily = df_daily.rename(columns={"day": "Date", "volume": "Volume (₹)"})
            st.area_chart(df_daily.set_index("Date"), color="#00e5a0")
        else:
            st.info("No transaction data yet.")

    with col_right:
        st.subheader("🏆 Top 5 Spenders")
        if data["top_spenders"]:
            df_top = pd.DataFrame(data["top_spenders"])
            df_top.columns = ["RFID", "Total Spent (₹)"]
            df_top = df_top.sort_values("Total Spent (₹)", ascending=True)
            st.bar_chart(df_top.set_index("RFID"), color="#00e5a0")
        else:
            st.info("No spending data yet.")

    st.markdown("---")
    st.subheader("🚨 Fraud Detection Overview")
    fraud_pct = (
        round(data["flagged_transactions"] / data["transaction_count"] * 100, 2)
        if data["transaction_count"] > 0 else 0
    )
    col_f1, col_f2 = st.columns([1, 2])
    col_f1.metric("Fraud Rate", f"{fraud_pct}%", delta=None)
    with col_f2:
        st.markdown(f"""
        **Detection Heuristics Active:**
        - **Velocity check** — flags >5 transactions/minute from the same RFID
        - **High-value check** — flags single transactions ≥ ₹2,000

        Current fraud rate: `{fraud_pct}%` of total transactions
        """)


# ============================================================
# SECTION: RFID Manager
# ============================================================
elif section == "🔍 RFID Manager":
    st.title("🔍 RFID Manager")
    st.markdown("---")

    rfid_list = fetch_rfid_list()
    if not rfid_list:
        st.error("⚠️ Could not load RFID list. Is the API running?")
        st.stop()

    col1, col2 = st.columns(2)
    with col1:
        selected_rfid = st.selectbox("Choose RFID from list:", rfid_list)
    with col2:
        manual_rfid = st.text_input("Or enter RFID manually:")
        if manual_rfid.strip():
            selected_rfid = manual_rfid.strip()

    st.markdown("---")

    if selected_rfid:
        col_info, col_qr = st.columns([2, 1])

        with col_info:
            st.subheader(f"📋 Details — `{selected_rfid}`")
            try:
                res = requests.get(f"{API_URL}/rfid/{selected_rfid}", timeout=5)
                if res.status_code == 200:
                    d = res.json()
                    c1, c2 = st.columns(2)
                    c1.metric("💰 Balance", f"₹{d['balance']}")
                    c2.metric("📡 ESPID", str(d['esp_id'] or "Not assigned"))
                elif res.status_code == 404:
                    st.warning("RFID not found.")
                else:
                    st.error("Failed to fetch details.")
            except requests.exceptions.ConnectionError:
                st.error("API connection error.")

        with col_qr:
            st.subheader("📲 QR Code")
            qr_img = qrcode.make(str(selected_rfid))
            buf = BytesIO()
            qr_img.save(buf, format="PNG")
            qr_bytes = buf.getvalue()
            st.image(qr_bytes, width=160, caption=f"RFID: {selected_rfid}")
            st.download_button(
                label="⬇️ Download QR",
                data=qr_bytes,
                file_name=f"rfid_{selected_rfid}_qr.png",
                mime="image/png",
            )

        st.markdown("---")

        # Transactions
        st.subheader("📜 Transaction History")
        if st.button("Load Transactions"):
            try:
                tr_res = requests.get(f"{API_URL}/transactions/{selected_rfid}?limit=100", timeout=5)
                if tr_res.status_code == 200:
                    rows = tr_res.json()
                    df = pd.DataFrame(rows)
                    df["flagged"] = df["flagged"].apply(
                        lambda x: "🚨 Flagged" if x else "✅ OK"
                    )
                    df = df.rename(columns={
                        "rfid": "RFID", "esp_id": "ESP ID",
                        "amount": "Amount (₹)", "timestamp": "Timestamp", "flagged": "Status"
                    })
                    st.dataframe(df, use_container_width=True)
                    st.caption(f"Total: {len(df)} transactions")

                    # Spend over time mini-chart
                    df_plot = pd.DataFrame(rows)
                    if "timestamp" in df_plot.columns:
                        df_plot["timestamp"] = pd.to_datetime(df_plot["timestamp"])
                        df_plot = df_plot[df_plot["esp_id"] != "TOPUP"]
                        if not df_plot.empty:
                            df_plot = df_plot.set_index("timestamp")[["amount"]].sort_index()
                            st.area_chart(df_plot, color="#00e5a0")
                elif tr_res.status_code == 404:
                    st.info("No transactions found for this RFID.")
                else:
                    st.error(f"Error: {tr_res.json().get('detail', 'Unknown error')}")
            except requests.exceptions.ConnectionError:
                st.error("API connection error.")

        st.markdown("---")

        # Top Up
        st.subheader("💳 Top Up Balance")
        with st.form("topup_form"):
            topup_amount = st.number_input("Amount (₹)", min_value=1, max_value=10000, step=50)
            topup_submitted = st.form_submit_button("Add Balance")
        if topup_submitted:
            try:
                res = requests.post(
                    f"{API_URL}/topup",
                    json={"rfid": str(selected_rfid), "amount": topup_amount},
                    timeout=5,
                )
                if res.status_code == 200:
                    st.success(f"✅ New balance: ₹{res.json()['new_balance']}")
                    st.cache_data.clear()
                else:
                    st.error(f"Failed: {res.json().get('detail', 'Unknown')}")
            except requests.exceptions.ConnectionError:
                st.error("API connection error.")

        st.markdown("---")

        # Deduct (simulate ESP payment)
        st.subheader("💸 Simulate Payment Deduction")
        with st.form("deduct_form"):
            deduct_espid = st.text_input("ESP ID", value="ESP01")
            deduct_amount = st.number_input("Amount (₹)", min_value=1, max_value=5000, step=10)
            deduct_submitted = st.form_submit_button("Process Payment")
        if deduct_submitted:
            try:
                res = requests.post(
                    f"{API_URL}/deduct",
                    json={"rfid": str(selected_rfid), "espid": deduct_espid, "amount": deduct_amount},
                    timeout=5,
                )
                if res.status_code == 200:
                    d = res.json()
                    if d.get("flagged"):
                        st.warning(f"⚠️ Transaction processed but flagged: {d['fraud_reason']}")
                    else:
                        st.success(f"✅ Payment processed. New balance: ₹{d['new_balance']}")
                    st.cache_data.clear()
                else:
                    st.error(f"Failed: {res.json().get('detail', 'Unknown')}")
            except requests.exceptions.ConnectionError:
                st.error("API connection error.")

        st.markdown("---")

        # Update RFID
        st.subheader("⚙️ Update RFID Settings")
        with st.form("update_rfid_form"):
            new_espid = st.text_input("New ESPID")
            new_txn_amt = st.number_input("New Transaction Amount (₹)", min_value=0, step=10)
            update_submitted = st.form_submit_button("Update")
        if update_submitted:
            if not new_espid:
                st.warning("Please enter a valid ESPID.")
            else:
                try:
                    res = requests.put(
                        f"{API_URL}/update-rfid",
                        json={"rfid": str(selected_rfid), "espid": new_espid, "transaction_amount": new_txn_amt},
                        timeout=5,
                    )
                    if res.status_code == 200:
                        st.success("✅ RFID updated successfully!")
                    else:
                        st.error(f"Failed: {res.json().get('detail', 'Unknown')}")
                except requests.exceptions.ConnectionError:
                    st.error("API connection error.")


# ============================================================
# SECTION: Audit Log
# ============================================================
elif section == "📋 Audit Log":
    st.title("📋 Audit Log")
    st.markdown("Immutable trail of all admin and system actions.")
    st.markdown("---")

    try:
        res = requests.get(f"{API_URL}/audit-log?limit=200", timeout=5)
        if res.status_code == 200:
            logs = res.json()
            if logs:
                df = pd.DataFrame(logs)
                df.columns = ["Action", "RFID", "Detail", "Timestamp"]
                st.dataframe(df, use_container_width=True)
                st.caption(f"Showing {len(df)} latest entries")
            else:
                st.info("Audit log is empty.")
        else:
            st.error("Could not load audit log.")
    except requests.exceptions.ConnectionError:
        st.error("API connection error.")