# app.py
import streamlit as st
from db import (
    init_db, create_user, authenticate_user,
    insert_production, fetch_all, insert_equipment,
    update_equipment, insert_inventory, insert_worker,
    insert_environment, fetch_users, clear_all_data
)
from utils import rows_to_df, export_dataframe
import pandas as pd
import plotly.express as px
from datetime import datetime
import os

# initialize DB and default admin
init_db()

# header image (place your header file at assets/header.webp)
HEADER_IMAGE = "assets/header.webp"

st.set_page_config(page_title="Quarry Ops", layout="wide")

# --- SESSION STATE helpers ---
if 'auth' not in st.session_state:
    st.session_state['auth'] = {"logged_in": False, "user": None}

# --- Utility time helpers (for numeric AM/PM inputs) ---
def convert_to_24h(hour, minute, meridiem):
    hour = int(hour)
    minute = int(minute)
    if meridiem == "PM" and hour != 12:
        hour += 12
    if meridiem == "AM" and hour == 12:
        hour = 0
    return f"{hour:02d}:{minute:02d}:00"

def calculate_running_time(start_24, end_24):
    try:
        fmt = "%H:%M:%S"
        t1 = datetime.strptime(start_24, fmt)
        t2 = datetime.strptime(end_24, fmt)
        diff = (t2 - t1).total_seconds() / 3600
        # if negative (end before start) treat as 0
        return round(max(diff, 0), 4)
    except:
        return 0.0

# --- Auth / login page ---
def login_page():
    st.title("Quarry Ops — Sign In")
    if os.path.exists(HEADER_IMAGE):
        st.image(HEADER_IMAGE, use_container_width=True)
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        if submitted:
            ok, result = authenticate_user(username, password)
            if ok:
                st.session_state['auth'] = {"logged_in": True, "user": result}
                st.success(f"Welcome {result['username']} ({result['role']})")
                st.rerun()
            else:
                st.error(result)

    st.markdown("---")
    st.subheader("Sign up (create a user account)")
    with st.form("signup_form"):
        new_user = st.text_input("New username")
        new_pass = st.text_input("New password", type="password")
        role = st.selectbox("Role", ["user"])  # only users can be registered via UI
        create = st.form_submit_button("Create account")
        if create:
            if not new_user or not new_pass:
                st.error("Provide username and password")
            else:
                ok, msg = create_user(new_user, new_pass, role=role)
                if ok:
                    st.success("Account created — you can sign in now")
                else:
                    st.error(msg)

def logout():
    st.session_state['auth'] = {"logged_in": False, "user": None}
    st.rerun()

# --- Pages ---
def dashboard_page():
    st.title("Dashboard")
    if os.path.exists(HEADER_IMAGE):
        st.image(HEADER_IMAGE, use_container_width=True)
    # Pull counts and stats (admin sees global, user sees own)
    user = st.session_state['auth']['user']
    if user['role'] == 'admin':
        prod_rows = fetch_all("production")
        equip_rows = fetch_all("equipment")
        inv_rows = fetch_all("inventory")
        env_rows = fetch_all("environment")
    else:
        prod_rows = fetch_all("production", username=user['username'])
        equip_rows = fetch_all("equipment", username=user['username'])
        inv_rows = fetch_all("inventory", username=user['username'])
        env_rows = fetch_all("environment", username=user['username'])

    total_stockpile = sum([r.get("quantity", 0) or 0 for r in inv_rows])
    running_equipment = sum(1 for r in equip_rows if r.get("status") == "Running")
    avg_noise = None
    if env_rows:
        noise_vals = [r.get("noise_db") or 0 for r in env_rows]
        avg_noise = sum(noise_vals) / len(noise_vals)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Stockpile (units)", f"{total_stockpile:.2f}")
    col2.metric("Equipment Running", running_equipment, delta=f"{len(equip_rows)} total")
    col3.metric("Latest Production Records", len(prod_rows))
    col4.metric("Avg Noise (dB)", f"{avg_noise:.1f}" if avg_noise is not None else "N/A")

    st.markdown("---")
    st.subheader("Production Timeline (last 24 records)")
    dfp = rows_to_df(prod_rows).head(24)
    if not dfp.empty:
        dfp['ts'] = pd.to_datetime(dfp['timestamp'])
        fig = px.line(dfp.sort_values('ts'), x='ts', y='hourly_tons', title="Hourly Production (m³)")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(dfp[['timestamp','hourly_tons','daily_tons']])
    else:
        st.info("No production data yet")

def production_page():
    st.title("Production Management")
    st.subheader("Record Production Data")

    user = st.session_state['auth']['user']

    with st.form("prod_form"):
        hourly = st.number_input("Hourly Production (m³)", min_value=0.0, step=0.1)
        daily = st.number_input("Daily Production (m³)", min_value=0.0, step=0.1)

        bw = st.number_input("Block Width (m)", min_value=0.0, step=0.1)
        bh = st.number_input("Block Height (m)", min_value=0.0, step=0.1)
        bl = st.number_input("Block Length (m)", min_value=0.0, step=0.1)

        block_volume = bw * bh * bl
        st.info(f"📦 **Block Volume:** {block_volume:.2f} m³ (auto-calculated)")

        notes = st.text_area("Notes")

        save = st.form_submit_button("Save Production Data")
        if save:
            rec = {
                "timestamp": datetime.utcnow().isoformat(),
                "hourly_tons": hourly,
                "daily_tons": daily,
                "block_w": bw,
                "block_h": bh,
                "block_l": bl,
                "block_volume": block_volume,
                "notes": notes,
                "username": user['username']
            }
            insert_production(rec)
            st.success("Production record saved")

    st.markdown("---")
    st.subheader("Production Timeline & Export")
    if user['role'] == 'admin':
        prod_rows = fetch_all("production")
    else:
        prod_rows = fetch_all("production", username=user['username'])

    df = rows_to_df(prod_rows)
    if not df.empty:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        fig = px.line(df.sort_values('timestamp'), x='timestamp', y='hourly_tons', title="Hourly Production")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df)
        if st.button("Export Production to Excel"):
            path = export_dataframe(df, prefix="production")
            with open(path, "rb") as f:
                st.download_button("Download Production Excel", data=f, file_name=os.path.basename(path))
    else:
        st.info("No production data yet.")

def equipment_page():
    st.title("⚙️ Equipment Management")

    user = st.session_state['auth']['user']

    with st.form("equip_form"):
        equipment_type = st.selectbox(
            "Equipment Type",
            ["Dumper", "Excavator", "Wiresaw Machine", "Line Driller", "Sackhammer Drill"]
        )

        equipment_id = st.text_input("Equipment ID")

        st.subheader("Start Time")
        col1, col2, col3 = st.columns(3)
        start_hr = col1.number_input("Hour", 1, 12, key="e_start_hr")
        start_min = col2.number_input("Minute", 0, 59, key="e_start_min")
        start_ap = col3.selectbox("AM/PM", ["AM", "PM"], key="e_start_ap")

        st.subheader("End Time")
        col1, col2, col3 = st.columns(3)
        end_hr = col1.number_input("Hour ", 1, 12, key="e_end_hr")
        end_min = col2.number_input("Minute ", 0, 59, key="e_end_min")
        end_ap = col3.selectbox("AM/PM ", ["AM", "PM"], key="e_end_ap")

        start_24 = convert_to_24h(start_hr, start_min, start_ap)
        end_24 = convert_to_24h(end_hr, end_min, end_ap)

        running_hours = calculate_running_time(start_24, end_24)
        st.info(f"Running Time: **{running_hours:.2f} hours**")

        status = st.selectbox("Status", ["Idle", "Running", "Maintenance", "Breakdown"])

        prod = st.number_input("Production (tons)", min_value=0.0, step=0.1)

        save = st.form_submit_button("Save Equipment")
        if save:
            rec = {
                "equipment_type": equipment_type,
                "equipment_id": equipment_id,
                "status": status,
                "start_time": start_24,
                "end_time": end_24,
                "running_time": running_hours,
                "production_tons": prod,
                "username": user['username']
            }
            insert_equipment(rec)
            st.success("Equipment record saved")

    st.markdown("---")
    st.subheader("Equipment Records")
    if user['role'] == 'admin':
        eq_rows = fetch_all("equipment")
    else:
        eq_rows = fetch_all("equipment", username=user['username'])

    dfe = rows_to_df(eq_rows)
    if not dfe.empty:
        st.dataframe(dfe)
        fig = px.bar(dfe, x='equipment_id', y='running_time', color='status', title="Equipment running hours")
        st.plotly_chart(fig, use_container_width=True)
        if st.button("Export Equipment to Excel"):
            path = export_dataframe(dfe, prefix="equipment")
            with open(path, "rb") as f:
                st.download_button("Download Equipment Excel", data=f, file_name=os.path.basename(path))
    else:
        st.info("No equipment records yet.")

def inventory_page():
    st.title("Inventory & Stockpile")
    st.subheader("Add Inventory Entry")
    user = st.session_state['auth']['user']

    with st.form("inv_form"):
        location = st.text_input("Stockpile Location", value="Block Yard A")
        material_type = st.selectbox("Material Type", ["Overburden", "Rough Block", "Finished Slab", "Aggregate", "Other"])
        quantity = st.number_input("Quantity", min_value=0.0, step=1.0)
        unit = st.selectbox("Unit", ["m³", "tons", "pieces"])
        date_stocked = st.date_input("Date of Stocking")
        add = st.form_submit_button("Add to Inventory")
        if add:
            insert_inventory({
                "location": location,
                "material_type": material_type,
                "quantity": quantity,
                "unit": unit,
                "date_stocked": date_stocked.isoformat(),
                "username": user['username']
            })
            st.success("Inventory added")

    st.markdown("---")
    st.subheader("Current Inventory")
    if user['role'] == 'admin':
        inv_rows = fetch_all("inventory")
    else:
        inv_rows = fetch_all("inventory", username=user['username'])

    dfi = rows_to_df(inv_rows)
    if not dfi.empty:
        st.dataframe(dfi)
        fig = px.pie(dfi, names='material_type', values='quantity', title="Inventory distribution")
        st.plotly_chart(fig, use_container_width=True)
        if st.button("Export Inventory to Excel"):
            path = export_dataframe(dfi, prefix="inventory")
            with open(path, "rb") as f:
                st.download_button("Download Inventory Excel", data=f, file_name=os.path.basename(path))
    else:
        st.info("No inventory data yet.")

def workers_page():
    st.title("👷 Workers Management")
    user = st.session_state['auth']['user']

    with st.form("worker_form"):
        worker_name = st.text_input("Worker Name")
        role = st.text_input("Designation")
        shift = st.selectbox("Shift", ["Shift 1", "Shift 2", "Shift 3"])

        st.subheader("Start Time")
        col1, col2, col3 = st.columns(3)
        start_hr = col1.number_input("Hour", 1, 12, key="w_start_hr")
        start_min = col2.number_input("Minute", 0, 59, key="w_start_min")
        start_ap = col3.selectbox("AM/PM", ["AM", "PM"], key="w_start_ap")

        st.subheader("End Time")
        col1, col2, col3 = st.columns(3)
        end_hr = col1.number_input("Hour ", 1, 12, key="w_end_hr")
        end_min = col2.number_input("Minute ", 0, 59, key="w_end_min")
        end_ap = col3.selectbox("AM/PM ", ["AM", "PM"], key="w_end_ap")

        start_24 = convert_to_24h(start_hr, start_min, start_ap)
        end_24 = convert_to_24h(end_hr, end_min, end_ap)
        working_hours = calculate_running_time(start_24, end_24)
        st.info(f"Working Hours: **{working_hours:.2f} hours**")

        working_place = st.text_input("Working Place")
        hired_date = st.date_input("Date")

        add = st.form_submit_button("Save Worker")
        if add:
            insert_worker({
                "name": worker_name,
                "role": role,
                "shift": shift,
                "start_time": start_24,
                "end_time": end_24,
                "working_hours": working_hours,
                "working_place": working_place,
                "hired_on": hired_date.isoformat(),
                "username": user['username']
            })
            st.success("Worker record added successfully!")

    st.markdown("---")
    st.subheader("Workers List")
    if user['role'] == 'admin':
        wk = fetch_all("workers")
    else:
        wk = fetch_all("workers", username=user['username'])

    dfw = rows_to_df(wk)
    if not dfw.empty:
        st.dataframe(dfw)
        if st.button("Export Workers to Excel"):
            path = export_dataframe(dfw, prefix="workers")
            with open(path, "rb") as f:
                st.download_button("Download Workers Excel", data=f, file_name=os.path.basename(path))
    else:
        st.info("No workers data.")

def environment_page():
    st.title("Environment Logs")
    user = st.session_state['auth']['user']

    with st.form("env_form"):
        noise = st.number_input("Noise Level (dB)", min_value=0.0, step=0.1)
        air_quality = st.selectbox("Air Quality", ["Good", "Moderate", "Poor"])
        water = st.number_input("Water Usage (L)", min_value=0.0, step=0.1)
        compliance = st.selectbox("Compliance Status", ["Pass", "Warning", "Fail"])
        notes = st.text_area("Notes")
        add = st.form_submit_button("Save Environmental Log")
        if add:
            insert_environment({
                "timestamp": datetime.utcnow().isoformat(),
                "noise_db": noise,
                "air_quality": air_quality,
                "water_usage_l": water,
                "compliance_status": compliance,
                "notes": notes,
                "username": user['username']
            })
            st.success("Environmental log saved")

    st.markdown("---")
    st.subheader("Environmental Logs History")
    if user['role'] == 'admin':
        env_rows = fetch_all("environment")
    else:
        env_rows = fetch_all("environment", username=user['username'])

    dfe = rows_to_df(env_rows)
    if not dfe.empty:
        dfe['timestamp'] = pd.to_datetime(dfe['timestamp'])
        st.dataframe(dfe)
        fig = px.line(dfe.sort_values('timestamp'), x='timestamp', y='noise_db', title="Noise level over time")
        st.plotly_chart(fig, use_container_width=True)
        if st.button("Export Environment to Excel"):
            path = export_dataframe(dfe, prefix="environment")
            with open(path, "rb") as f:
                st.download_button("Download Environment Excel", data=f, file_name=os.path.basename(path))
    else:
        st.info("No environment logs yet.")

# --- Admin page to view all users data and Clear DB ---
def admin_page():
    st.title("🔐 Admin Dashboard")

    st.markdown("### Registered users")
    users = fetch_users()
    if users:
        for u in users:
            st.write(f"#### 👤 {u['username']}")
            st.write("**Production**")
            st.dataframe(rows_to_df(fetch_all("production", username=u['username'])))
            st.write("**Equipment**")
            st.dataframe(rows_to_df(fetch_all("equipment", username=u['username'])))
            st.write("**Inventory**")
            st.dataframe(rows_to_df(fetch_all("inventory", username=u['username'])))
            st.write("**Workers**")
            st.dataframe(rows_to_df(fetch_all("workers", username=u['username'])))
            st.write("**Environment**")
            st.dataframe(rows_to_df(fetch_all("environment", username=u['username'])))
            st.markdown("---")
    else:
        st.info("No registered users")

    st.markdown("### Dangerous Admin Operations")
    st.warning("Clearing the DB will remove all production/equipment/inventory/workers/environment data (users are preserved).")
    if st.button("Clear DB (delete all data)"):
        clear_all_data()
        st.success("All data tables cleared.")
        st.rerun()

# --- Main app flow ---
if not st.session_state['auth']["logged_in"]:
    login_page()
else:
    user = st.session_state['auth']["user"]
    st.sidebar.title("Quarry Ops")
    st.sidebar.write(f"Signed in as **{user['username']}** ({user['role']})")
    if user['role'] == 'admin':
        page = st.sidebar.radio("Navigation", ["Dashboard", "Production", "Equipment", "Inventory", "Workers", "Environment", "Admin", "Logout"])
    else:
        page = st.sidebar.radio("Navigation", ["Dashboard", "Production", "Equipment", "Inventory", "Workers", "Environment", "Logout"])

    if page == "Logout":
        if st.sidebar.button("Sign out"):
            logout()
    elif page == "Dashboard":
        dashboard_page()
    elif page == "Production":
        production_page()
    elif page == "Equipment":
        equipment_page()
    elif page == "Inventory":
        inventory_page()
    elif page == "Workers":
        workers_page()
    elif page == "Environment":
        environment_page()
    elif page == "Admin":
        admin_page()
