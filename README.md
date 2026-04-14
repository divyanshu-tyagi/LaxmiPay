# RFID-Based Contactless Payment System with Fraud Detection

> A full-stack IoT payment system integrating ESP8266 RFID readers, a FastAPI backend, and a Streamlit admin/customer portal — with built-in real-time fraud detection heuristics.

---

## Abstract

This project presents a contactless payment system built on passive RFID technology, designed for deployment in environments such as college canteens, public transit, or campus access control. The system integrates IoT hardware (ESP8266 + MFRC522) with a RESTful API backend (FastAPI + SQLite) and a multi-role web dashboard (Streamlit). A lightweight fraud detection module applies velocity-based and threshold-based heuristics to flag anomalous transactions in real time — achieving this without reliance on external ML services, making the system deployable in low-resource environments.

---

## System Architecture

```
┌──────────────────────────────────────────────────────────┐
│                      CLIENT LAYER                        │
│  ┌─────────────────────┐    ┌────────────────────────┐   │
│  │  Customer Dashboard  │    │   Admin Dashboard       │   │
│  │  (QR Scan + History) │    │  (Analytics + Audit)    │   │
│  └──────────┬──────────┘    └──────────┬─────────────┘   │
└─────────────┼──────────────────────────┼─────────────────┘
              │           HTTP/REST        │
┌─────────────▼──────────────────────────▼─────────────────┐
│                    API LAYER (FastAPI)                    │
│  /authenticate  /rfid  /transactions  /topup  /deduct    │
│  /analytics/summary   /audit-log   /rfid-list            │
│                                                           │
│          ┌──────────────────────────────┐                 │
│          │     Fraud Detection Engine   │                 │
│          │  • Velocity Check (5 txn/min)│                 │
│          │  • High-Value Threshold (₹2k)│                 │
│          └──────────────────────────────┘                 │
└───────────────────────────┬──────────────────────────────┘
                            │ SQLite
┌───────────────────────────▼──────────────────────────────┐
│                     DATA LAYER                           │
│  RFIDTable | Transactions | UserAuth | ESPNumber         │
│  AuditLog                                                 │
└───────────────────────────────────────────────────────────┘
              │ Hardware (optional)
┌─────────────▼─────────────────────────────────────────────┐
│  ESP8266 + MFRC522 RFID Reader → POST /deduct             │
└────────────────────────────────────────────────────────────┘
```

---

## Features

| Feature | Description |
|---|---|
| **RFID Card Management** | Register, update, and view RFID cards with balance and ESP linkage |
| **QR Code Identity** | Each card has a downloadable QR code for customer-side verification |
| **Contactless Payment** | ESP8266 triggers `/deduct` on card tap; balance deducted atomically |
| **Top-Up** | Admin can add balance to any registered card |
| **Fraud Detection** | Velocity check (>5 txn/min) + high-value threshold (≥₹2,000) |
| **Transaction Ledger** | Timestamped, immutable transaction log with fraud flag column |
| **Audit Log** | Every admin/system action is recorded in `AuditLog` table |
| **Analytics Dashboard** | Daily volume chart, top spenders, flagged transaction rate |
| **Role-based Access** | Customer (QR scan) and Admin (login) with session guard |

---

## Fraud Detection Design

The fraud detection module operates as a **pre-processing gate** on every `/deduct` call. Two independent heuristics are applied:

### 1. Velocity Check
A transaction is flagged if the same RFID card has been used **≥5 times within the last 60 seconds**. This detects card cloning and replay attacks where an attacker rapidly deducts small amounts.

```
flag = COUNT(transactions WHERE rfid = X AND timestamp >= now - 60s) >= 5
```

### 2. High-Value Threshold
Any single transaction exceeding ₹2,000 is flagged as potentially fraudulent for review. This is configurable via `FRAUD_AMOUNT_THRESHOLD` in `api.py`.

```
flag = amount >= FRAUD_AMOUNT_THRESHOLD
```

**Important:** Flagged transactions are **not blocked** — they are processed normally but marked in the `Transactions` table (`flagged = 1`) and recorded in the `AuditLog`. This is consistent with real-world fraud systems that prefer soft-blocking over hard-blocking to avoid false positives disrupting legitimate high-value payments.

---

## Database Schema

```sql
-- Master card registry
CREATE TABLE RFIDTable (
    RFID               INTEGER PRIMARY KEY,
    Balance            INTEGER NOT NULL DEFAULT 0,
    ESPID              INTEGER,
    "Transaction Amount" INTEGER
);

-- Immutable transaction ledger
CREATE TABLE Transactions (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    rfid      TEXT    NOT NULL,
    esp_id    TEXT    NOT NULL,
    amount    INTEGER NOT NULL,
    timestamp TEXT    NOT NULL,         -- ISO 8601 UTC
    flagged   INTEGER NOT NULL DEFAULT 0
);

-- Admin/system action trail
CREATE TABLE AuditLog (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    action    TEXT NOT NULL,
    rfid      TEXT,
    detail    TEXT,
    timestamp TEXT NOT NULL
);

-- Customer authentication
CREATE TABLE UserAuth (
    RFID     INTEGER PRIMARY KEY,
    Password TEXT NOT NULL              -- SHA-256 hashed
);
```

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Health check |
| `POST` | `/authenticate/customer` | Customer login |
| `POST` | `/authenticate/admin` | Admin login |
| `GET` | `/rfid/{rfid}` | Card details |
| `GET` | `/balance/{rfid}` | Balance only |
| `GET` | `/transactions/{rfid}` | Transaction history |
| `POST` | `/deduct` | Process payment (with fraud check) |
| `POST` | `/topup` | Add balance |
| `PUT` | `/update-rfid` | Update card ESP/amount settings |
| `GET` | `/rfid-list` | All registered RFIDs |
| `GET` | `/analytics/summary` | System-wide analytics |
| `GET` | `/audit-log` | Admin action log |

Full interactive docs available at `http://localhost:8000/docs` (Swagger UI).

---

## Setup & Running

### Prerequisites
```
python >= 3.10
```

### Install dependencies
```bash
pip install fastapi uvicorn streamlit requests qrcode opencv-python-headless pyzbar pandas pydantic
```

### Initialize database
```bash
python sm.py
```

### Start API server
```bash
uvicorn api:app --reload --port 8000
```

### Start Streamlit app (separate terminal)
```bash
streamlit run app.py
```

### Generate QR codes
```bash
# Single RFID
python qr.py 1234

# All RFIDs in database
python qr.py --batch --out ./qr_codes
```

---

## Project Structure

```
rfid-payment-system/
├── app.py                  # Streamlit entry point (home + admin login)
├── api.py                  # FastAPI backend
├── sm.py                   # DB schema + seeding
├── qr.py                   # QR generation utility
├── Database.db             # SQLite database (auto-created)
└── pages/
    ├── Admin_Dashboard.py  # Admin analytics + RFID manager
    └── Customer_Dashboard.py  # Customer QR scan + history
```

---

## Security Notes

- Admin credentials are currently hardcoded (`admin/admin`) — replace with environment variables for production.
- Customer passwords are stored as **SHA-256 hashes** (upgraded from plaintext).
- RFID values should be treated as sensitive identifiers; TLS should be enforced in production deployment.
- The fraud detection engine is intentionally lightweight for embedded/low-resource deployment; it can be extended with ML-based anomaly detection (e.g., Isolation Forest on transaction embeddings).

---

## Future Work

- Replace SQLite with PostgreSQL for concurrent multi-reader deployments
- Add ML-based anomaly detection (Isolation Forest / Autoencoders) to the fraud module
- Implement JWT-based authentication for the API
- Add SMS/email alert when a transaction is flagged
- Deploy on Raspberry Pi as an edge gateway with MQTT for ESP8266 communication

---

## References

1. Want, R. (2006). An Introduction to RFID Technology. *IEEE Pervasive Computing*, 5(1), 25–33.
2. Bhattacharyya, R. et al. (2010). RFID-based System for Automated Contactless Payment. *IEEE RFID Conference*.
3. FastAPI Documentation — https://fastapi.tiangolo.com
4. Streamlit Documentation — https://docs.streamlit.io
