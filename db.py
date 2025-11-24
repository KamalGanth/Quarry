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
    # Production
    cur.execute("""
    CREATE TABLE IF NOT EXISTS production (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        hourly_tons REAL,
        daily_tons REAL,
        block_w REAL,
        block_h REAL,
        block_l REAL,
        latitude REAL,
        longitude REAL,
        notes TEXT
    )
    """)
    # Equipment
    cur.execute("""
    CREATE TABLE IF NOT EXISTS equipment (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        equipment_id TEXT,
        name TEXT,
        status TEXT,
        running_hours REAL,
        production_tons REAL,
        last_updated TEXT
    )
    """)
    # Inventory
    cur.execute("""
    CREATE TABLE IF NOT EXISTS inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        location TEXT,
        material_type TEXT,
        quantity REAL,
        unit TEXT,
        date_stocked TEXT
    )
    """)
    # Workers
    cur.execute("""
    CREATE TABLE IF NOT EXISTS workers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        role TEXT,
        shift TEXT,
        contact TEXT,
        hired_on TEXT
    )
    """)
    # Environment
    cur.execute("""
    CREATE TABLE IF NOT EXISTS environment (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        noise_db REAL,
        air_quality TEXT,
        water_usage_l REAL,
        compliance_status TEXT,
        notes TEXT
    )
    """)
    conn.commit()
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

# Generic insert helpers for modules
def insert_production(record: dict):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO production (timestamp, hourly_tons, daily_tons, block_w, block_h, block_l, latitude, longitude, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        record.get("timestamp"),
        record.get("hourly_tons"),
        record.get("daily_tons"),
        record.get("block_w"),
        record.get("block_h"),
        record.get("block_l"),
        record.get("latitude"),
        record.get("longitude"),
        record.get("notes"),
    ))
    conn.commit()
    conn.close()

def fetch_all(table):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM {table} ORDER BY id DESC")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def insert_equipment(e):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO equipment (equipment_id, name, status, running_hours, production_tons, last_updated)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (e.get("equipment_id"), e.get("name"), e.get("status"), e.get("running_hours"), e.get("production_tons"), datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()

def update_equipment(equipment_id, status, running_hours, production_tons):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        UPDATE equipment
        SET status = ?, running_hours = ?, production_tons = ?, last_updated = ?
        WHERE equipment_id = ?
    """, (status, running_hours, production_tons, datetime.utcnow().isoformat(), equipment_id))
    conn.commit()
    conn.close()

def insert_inventory(i):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO inventory (location, material_type, quantity, unit, date_stocked)
        VALUES (?, ?, ?, ?, ?)
    """, (i.get("location"), i.get("material_type"), i.get("quantity"), i.get("unit"), i.get("date_stocked")))
    conn.commit()
    conn.close()

def insert_worker(w):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO workers (name, role, shift, contact, hired_on)
        VALUES (?, ?, ?, ?, ?)
    """, (w.get("name"), w.get("role"), w.get("shift"), w.get("contact"), w.get("hired_on")))
    conn.commit()
    conn.close()

def insert_environment(e):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO environment (timestamp, noise_db, air_quality, water_usage_l, compliance_status, notes)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (e.get("timestamp"), e.get("noise_db"), e.get("air_quality"), e.get("water_usage_l"), e.get("compliance_status"), e.get("notes")))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    # create default admin if not present
    ok, _ = create_user("admin", "admin123", role="admin")
    if ok:
        print("Default admin created (username: admin, password: admin123)")
    else:
        print("Admin user probably already exists.")
