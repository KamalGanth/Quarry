# db.py
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

DB_FILE = "quarry_ops.db"

def get_conn():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database and create tables (with username column). Also create default Admin."""
    conn = get_conn()
    cur = conn.cursor()

    # Users table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('admin','user')),
        created_at TEXT NOT NULL
    )
    """)

    # Production (with username)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS production (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        hourly_tons REAL,
        daily_tons REAL,
        block_w REAL,
        block_h REAL,
        block_l REAL,
        block_volume REAL,
        notes TEXT,
        username TEXT
    )
    """)

    # Equipment (with username)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS equipment (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        equipment_type TEXT,
        equipment_id TEXT,
        status TEXT,
        start_time TEXT,
        end_time TEXT,
        running_time REAL,
        production_tons REAL,
        username TEXT,
        last_updated TEXT
    )
    """)

    # Inventory (with username)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        location TEXT,
        material_type TEXT,
        quantity REAL,
        unit TEXT,
        date_stocked TEXT,
        username TEXT
    )
    """)

    # Workers (with username)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS workers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        role TEXT,
        shift TEXT,
        start_time TEXT,
        end_time TEXT,
        working_hours REAL,
        working_place TEXT,
        hired_on TEXT,
        username TEXT
    )
    """)

    # Environment (with username)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS environment (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        noise_db REAL,
        air_quality TEXT,
        water_usage_l REAL,
        compliance_status TEXT,
        notes TEXT,
        username TEXT
    )
    """)

    conn.commit()

    # Ensure default Admin exists (username: Admin, password: ad_01)
    try:
        cur.execute("SELECT id FROM users WHERE username = ?", ("Admin",))
        existing = cur.fetchone()
        if not existing:
            pw_hash = generate_password_hash("ad_01")
            cur.execute(
                "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
                ("Admin", pw_hash, "admin", datetime.utcnow().isoformat())
            )
            conn.commit()
    except Exception as e:
        # ignore if insertion fails for any reason
        pass

    conn.close()

# User functions
def create_user(username, password, role='user'):
    conn = get_conn()
    cur = conn.cursor()
    password_hash = generate_password_hash(password)
    try:
        cur.execute(
            "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
            (username, password_hash, role, datetime.utcnow().isoformat())
        )
        conn.commit()
        return True, "User created"
    except sqlite3.IntegrityError:
        return False, "Username already exists"
    finally:
        conn.close()

def authenticate_user(username, password):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username = ?", (username,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return False, "User not found"
    if check_password_hash(row["password_hash"], password):
        user = {"id": row["id"], "username": row["username"], "role": row["role"]}
        return True, user
    else:
        return False, "Invalid password"

# Generic insert helpers for modules (all now accept username)
def insert_production(record: dict):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO production (timestamp, hourly_tons, daily_tons, block_w, block_h, block_l, block_volume, notes, username)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        record.get("timestamp"),
        record.get("hourly_tons"),
        record.get("daily_tons"),
        record.get("block_w"),
        record.get("block_h"),
        record.get("block_l"),
        record.get("block_volume"),
        record.get("notes"),
        record.get("username")
    ))
    conn.commit()
    conn.close()

def insert_equipment(e):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO equipment (equipment_type, equipment_id, status, start_time, end_time, running_time, production_tons, username, last_updated)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        e.get("equipment_type"),
        e.get("equipment_id"),
        e.get("status"),
        e.get("start_time"),
        e.get("end_time"),
        e.get("running_time"),
        e.get("production_tons"),
        e.get("username"),
        datetime.utcnow().isoformat()
    ))
    conn.commit()
    conn.close()

def update_equipment(equipment_id, status, start_time, end_time, running_time, production_tons):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        UPDATE equipment
        SET status = ?, start_time = ?, end_time = ?, running_time = ?, production_tons = ?, last_updated = ?
        WHERE equipment_id = ?
    """, (status, start_time, end_time, running_time, production_tons, datetime.utcnow().isoformat(), equipment_id))
    conn.commit()
    conn.close()

def insert_inventory(i):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO inventory (location, material_type, quantity, unit, date_stocked, username)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (i.get("location"), i.get("material_type"), i.get("quantity"), i.get("unit"), i.get("date_stocked"), i.get("username")))
    conn.commit()
    conn.close()

def insert_worker(w):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO workers (name, role, shift, start_time, end_time, working_hours, working_place, hired_on, username)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        w.get("name"),
        w.get("role"),
        w.get("shift"),
        w.get("start_time"),
        w.get("end_time"),
        w.get("working_hours"),
        w.get("working_place"),
        w.get("hired_on"),
        w.get("username")
    ))
    conn.commit()
    conn.close()

def insert_environment(e):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO environment (timestamp, noise_db, air_quality, water_usage_l, compliance_status, notes, username)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (e.get("timestamp"), e.get("noise_db"), e.get("air_quality"), e.get("water_usage_l"), e.get("compliance_status"), e.get("notes"), e.get("username")))
    conn.commit()
    conn.close()

# Fetch helpers (optionally filter by username)
def fetch_all(table, username=None):
    conn = get_conn()
    cur = conn.cursor()
    if username:
        cur.execute(f"SELECT * FROM {table} WHERE username = ? ORDER BY id DESC", (username,))
    else:
        cur.execute(f"SELECT * FROM {table} ORDER BY id DESC")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def fetch_users():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT username, role, created_at FROM users ORDER BY username")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

# Admin destructive operation: clear all data tables (preserve users table)
def clear_all_data():
    conn = get_conn()
    cur = conn.cursor()
    tables = ["production", "equipment", "inventory", "workers", "environment"]
    for t in tables:
        cur.execute(f"DELETE FROM {t}")
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
