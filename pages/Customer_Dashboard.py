import streamlit as st
import requests
import cv2
import numpy as np
import pandas as pd
from pyzbar.pyzbar import decode

API_URL = "http://localhost:8000"

st.set_page_config(page_title="Customer Dashboard", page_icon="📷", layout="centered")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');
    html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
    .stApp { background: #0f0f13; color: #e8e8e8; }
    .rfid-badge {
        display: inline-block;
        background: #0a2e1f; color: #00e5a0;
        border: 1px solid #00e5a0; border-radius: 8px;
        padding: 6px 16px; font-family: 'IBM Plex Mono', monospace;
        font-size: 1.1rem; margin-bottom: 1rem;
    }
    .txn-row {
        background: #181820; border: 1px solid #2a2a35;
        border-radius: 8px; padding: 0.6rem 1rem;
        margin-bottom: 0.5rem; display: flex;
        justify-content: space-between; align-items: center;
    }
    .flagged-row { border-color: #ff5c5c !important; background: #1a0d0d !important; }
    .stButton > button {
        border-radius: 8px; font-family: 'IBM Plex Mono', monospace;
        background: #00e5a0; color: #0f0f13;
        font-weight: 600; border: none;
    }
    div[data-testid="metric-container"] {
        background: #181820; border: 1px solid #2a2a35;
        border-radius: 12px; padding: 0.8rem;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("# 📷 Customer Portal")
st.markdown("Scan your RFID QR code to access your account.")
st.markdown("---")

if st.button("← Back to Home"):
    st.switch_page("app.py")

st.subheader("Scan QR Code")
img = st.camera_input("Point camera at your RFID QR code")

if img:
    file_bytes = img.getvalue()
    nparr = np.frombuffer(file_bytes, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    decoded = decode(frame)

    if not decoded:
        st.warning("⚠️ No QR code detected. Please try again with better lighting.")
    else:
        rfid = decoded[0].data.decode("utf-8").strip()

        st.markdown(f'<div class="rfid-badge">✅ RFID: {rfid}</div>', unsafe_allow_html=True)
        st.markdown("---")

        try:
            res = requests.get(f"{API_URL}/rfid/{rfid}", timeout=5)

            if res.status_code == 200:
                data = res.json()

                # Account Info
                st.subheader("💳 Account Summary")
                c1, c2 = st.columns(2)
                c1.metric("RFID", rfid)
                c2.metric("Balance", f"₹{data['balance']}")
                st.caption(f"Linked ESP: `{data['esp_id'] or 'Not assigned'}`")

                st.markdown("---")

                # Transactions
                st.subheader("📜 Transaction History")
                try:
                    tr = requests.get(f"{API_URL}/transactions/{rfid}?limit=50", timeout=5)
                    if tr.status_code == 200:
                        txns = tr.json()

                        # Spend chart
                        df = pd.DataFrame(txns)
                        purchases = df[df["esp_id"] != "TOPUP"].copy() if not df.empty else pd.DataFrame()
                        if not purchases.empty and "timestamp" in purchases.columns:
                            purchases["timestamp"] = pd.to_datetime(purchases["timestamp"])
                            purchases = purchases.sort_values("timestamp")
                            st.area_chart(
                                purchases.set_index("timestamp")[["amount"]],
                                color="#00e5a0",
                            )

                        # Transaction list
                        for t in txns[:20]:
                            is_topup = t["esp_id"] == "TOPUP"
                            is_flagged = t.get("flagged", False)
                            icon = "⬆️" if is_topup else ("🚨" if is_flagged else "🔹")
                            amt_color = "#00e5a0" if is_topup else ("#ff5c5c" if is_flagged else "#e8e8e8")
                            sign = "+" if is_topup else "-"
                            ts = t.get("timestamp", "")[:16].replace("T", " ") if t.get("timestamp") else ""
                            row_class = "flagged-row" if is_flagged else ""
                            label = "Top-up" if is_topup else f"ESP: {t['esp_id']}"

                            st.markdown(f"""
                            <div class="txn-row {row_class}">
                                <span>{icon} {label}</span>
                                <span style="color:#888;font-size:0.8rem">{ts}</span>
                                <span style="color:{amt_color};font-family:'IBM Plex Mono',monospace;font-weight:600">
                                    {sign}₹{t['amount']}
                                </span>
                            </div>
                            """, unsafe_allow_html=True)

                        if len(txns) == 0:
                            st.info("No transactions yet.")
                        else:
                            st.caption(f"Showing latest {min(20, len(txns))} of {len(txns)} transactions")

                    elif tr.status_code == 404:
                        st.info("No transactions found.")
                    else:
                        st.error("Could not load transactions.")

                except requests.exceptions.ConnectionError:
                    st.error("⚠️ API connection error.")

            elif res.status_code == 404:
                st.error("❌ RFID not registered. Please contact support.")
            else:
                st.error("⚠️ Something went wrong. Try again.")

        except requests.exceptions.ConnectionError:
            st.error("⚠️ Cannot connect to API server.")