"""
sm.py — Database schema setup and seeding script for the RFID Payment System.

Tables:
  RFIDTable    — Master card registry (balance, linked ESP, transaction amount)
  ESPNumber    — ESP device registry (legacy compatibility)
  UserAuth     — Customer credentials (SHA-256 hashed passwords)
  Transactions — Immutable ledger with timestamp + fraud flag
  AuditLog     — Admin/system action trail
"""

import sqlite3
import random
import hashlib
from datetime import datetime, timezone, timedelta

DB_PATH = "./Database.db"


def _hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def create_tables():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.executescript("""
        CREATE TABLE IF NOT EXISTS ESPNumber (
            ESPID     INTEGER PRIMARY KEY AUTOINCREMENT,
            RFID      INTEGER NOT NULL,
            TransactionAmt INTEGER
        );

        CREATE TABLE IF NOT EXISTS RFIDTable (
            RFID               INTEGER PRIMARY KEY,
            Balance            INTEGER NOT NULL DEFAULT 0,
            ESPID              INTEGER,
            "Transaction Amount" INTEGER
        );

        CREATE TABLE IF NOT EXISTS UserAuth (
            RFID     INTEGER PRIMARY KEY,
            Password TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS Transactions (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            rfid      TEXT    NOT NULL,
            esp_id    TEXT    NOT NULL,
            amount    INTEGER NOT NULL,
            timestamp TEXT    NOT NULL,
            flagged   INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS AuditLog (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            action    TEXT NOT NULL,
            rfid      TEXT,
            detail    TEXT,
            timestamp TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_txn_rfid      ON Transactions(rfid);
        CREATE INDEX IF NOT EXISTS idx_txn_timestamp ON Transactions(timestamp);
        CREATE INDEX IF NOT EXISTS idx_audit_rfid    ON AuditLog(rfid);
    """)

    conn.commit()
    conn.close()
    print("✅ Tables created.")


def insert_dummy_data():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    rfid_numbers = random.sample(range(1000, 9999), 20)
    esp_ids = [f"ESP{i:02d}" for i in range(1, 6)]

    # --- Cards & Auth ---
    for rfid in rfid_numbers:
        balance = random.randint(200, 8000)
        txn_amt = random.randint(10, 500)
        password = _hash(f"pass{rfid}")

        c.execute(
            'INSERT OR IGNORE INTO RFIDTable (RFID, Balance, ESPID, "Transaction Amount") VALUES (?, ?, ?, ?)',
            (rfid, balance, None, txn_amt),
        )
        c.execute(
            "INSERT OR IGNORE INTO UserAuth (RFID, Password) VALUES (?, ?)",
            (rfid, password),
        )

    # --- ESP legacy entries ---
    for rfid in rfid_numbers:
        for _ in range(random.randint(1, 3)):
            c.execute(
                "INSERT INTO ESPNumber (RFID, TransactionAmt) VALUES (?, ?)",
                (rfid, random.randint(10, 500)),
            )

    # --- Realistic transaction history (last 14 days) ---
    now = datetime.now(timezone.utc)
    fraud_velocity_window: dict = {}  # rfid -> list of timestamps

    for _ in range(200):
        rfid = str(random.choice(rfid_numbers))
        esp = random.choice(esp_ids)
        amount = random.randint(10, 600)
        days_ago = random.uniform(0, 14)
        ts = (now - timedelta(days=days_ago)).isoformat()

        # Simple fraud simulation: occasionally generate a burst
        flagged = 0
        if random.random() < 0.05:   # 5% chance of high-value flag
            amount = random.randint(2000, 5000)
            flagged = 1
        elif random.random() < 0.03:  # 3% chance of velocity flag
            flagged = 1

        c.execute(
            "INSERT INTO Transactions (rfid, esp_id, amount, timestamp, flagged) VALUES (?, ?, ?, ?, ?)",
            (rfid, esp, amount, ts, flagged),
        )

    # --- Topup events ---
    for rfid in random.sample(rfid_numbers, 8):
        ts = (now - timedelta(days=random.uniform(0, 7))).isoformat()
        c.execute(
            "INSERT INTO Transactions (rfid, esp_id, amount, timestamp, flagged) VALUES (?, ?, ?, ?, ?)",
            (str(rfid), "TOPUP", random.randint(500, 2000), ts, 0),
        )

    # --- Seed audit log ---
    for rfid in random.sample(rfid_numbers, 5):
        c.execute(
            "INSERT INTO AuditLog (action, rfid, detail, timestamp) VALUES (?, ?, ?, ?)",
            ("SYSTEM_INIT", str(rfid), "Card registered during setup", now.isoformat()),
        )

    conn.commit()
    conn.close()
    print("✅ Dummy data inserted.")


if __name__ == "__main__":
    create_tables()
    insert_dummy_data()
    print("✅ Database ready!")