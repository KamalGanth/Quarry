# app.py
import streamlit as st
from db import init_db, create_user, authenticate_user, insert_production, fetch_all, insert_equipment, update_equipment, insert_inventory, insert_worker, insert_environment
from utils import rows_to_df, export_dataframe
import pandas as pd
import plotly.express as px
from datetime import datetime
import os
from streamlit import rerun


# initialize DB
init_db()

# optionally use your header image; path from conversation:
HEADER_IMAGE = "https://imgs.search.brave.com/OcVFeIo49wbja5GMivL3ga5-DNm4QZ31N_6RySpTnac/rs:fit:500:0:1:0/g:ce/aHR0cHM6Ly93d3cu/YWdnLW5ldC5jb20v/c2l0ZXMvZGVmYXVs/dC9maWxlcy9zdHls/ZXMvYWdnbmV0X2dh/bGxlcnlfZnVsbF9p/bWFnZV9wcmVzZXQv/cHVibGljLzIwMjUt/MDIvY292ZXJfcW0t/ZmViLTIwMjUuanBn/P2l0b2s9YlRjQktE/QTA"  # change if you moved assets

st.set_page_config(page_title="Quarry Ops", layout="wide")

# --- SESSION STATE helpers ---
if 'auth' not in st.session_state:
    st.session_state['auth'] = {"logged_in": False, "user": None}

def login_page():
    st.title("Quarry Ops — Sign In")
    st.image(HEADER_IMAGE, use_column_width=True)
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        if submitted:
            ok, result = authenticate_user(username, password)
            if ok:
                st.session_state['auth'] = {"logged_in": True, "user": result}
                st.success(f"Welcome {result['username']} ({result['role']})")
                rerun()
            else:
                st.error(result)

    st.markdown("---")
    st.subheader("Sign up")
    with st.form("signup_form"):
        new_user = st.text_input("New username")
        new_pass = st.text_input("New password", type="password")
        role = st.selectbox("Role", ["user", "admin"])
        create = st.form_submit_button("Create account")
        if create:
            ok, msg = create_user(new_user, new_pass, role=role)
            if ok:
                st.success("Account created — you can sign in now")
            else:
                st.error(msg)

def logout():
    st.session_state['auth'] = {"logged_in": False, "user": None}
    st.experimental_rerun()

# --- Pages ---
def dashboard_page():
    st.title("Dashboard")
    st.image(HEADER_IMAGE, use_column_width=True)
    # KPI cards
    # Pull counts and stats
    prod_rows = fetch_all("production")
    equip_rows = fetch_all("equipment")
    inv_rows = fetch_all("inventory")
    env_rows = fetch_all("environment")

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
        # convert timestamps to datetime
        dfp['ts'] = pd.to_datetime(dfp['timestamp'])
        fig = px.line(dfp.sort_values('ts'), x='ts', y='hourly_tons', title="Hourly Production (tons)")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(dfp[['timestamp','hourly_tons','daily_tons']])
    else:
        st.info("No production data yet")

def production_page():
    st.title("Production Management")
    st.subheader("Record Production Data")
    with st.form("prod_form"):
        hourly = st.number_input("Hourly Production (tons)", min_value=0.0, step=0.1, value=0.0)
        daily = st.number_input("Daily Production (tons)", min_value=0.0, step=0.1, value=0.0)
        bw = st.number_input("Block Width (m)", value=0.0, step=0.1)
        bh = st.number_input("Block Height (m)", value=0.0, step=0.1)
        bl = st.number_input("Block Length (m)", value=0.0, step=0.1)
        lat = st.text_input("Latitude", value="0.0")
        lon = st.text_input("Longitude", value="0.0")
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
                "latitude": float(lat) if lat else None,
                "longitude": float(lon) if lon else None,
                "notes": notes
            }
            insert_production(rec)
            st.success("Production record saved")

    st.markdown("---")
    st.subheader("Production Timeline & Export")
    prod_rows = fetch_all("production")
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
    st.title("Equipment Monitoring")
    st.subheader("Update Equipment Status")
    with st.form("equip_form"):
        eid = st.text_input("Equipment ID", value="EXC-001")
        name = st.text_input("Name", value="Excavator Alpha")
        status = st.selectbox("Status", ["Running", "Idle", "Maintenance"])
        hours = st.number_input("Running Hours", min_value=0.0, step=0.1)
        prod = st.number_input("Production (tons)", min_value=0.0, step=0.1)
        add = st.form_submit_button("Add / Update Equipment")
        if add:
            # optimistic: if equipment exists, update else insert
            existing = [r for r in fetch_all("equipment") if r.get("equipment_id") == eid]
            if existing:
                update_equipment(eid, status, hours, prod)
                st.success("Equipment updated")
            else:
                insert_equipment({"equipment_id": eid, "name": name, "status": status, "running_hours": hours, "production_tons": prod})
                st.success("Equipment added")

    st.markdown("---")
    st.subheader("Equipment Status Overview")
    eq_rows = fetch_all("equipment")
    dfe = rows_to_df(eq_rows)
    if not dfe.empty:
        st.dataframe(dfe)
        fig = px.bar(dfe, x='name', y='running_hours', color='status', title="Equipment running hours")
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
    with st.form("inv_form"):
        location = st.text_input("Stockpile Location", value="Block Yard A")
        material_type = st.selectbox("Material Type / Grade", ["Rough Block", "Finished Slab", "Aggregate", "Other"])
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
                "date_stocked": date_stocked.isoformat()
            })
            st.success("Inventory added")

    st.markdown("---")
    st.subheader("Current Inventory")
    inv_rows = fetch_all("inventory")
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
    st.title("Workers")
    st.subheader("Add Worker")
    with st.form("worker_form"):
        name = st.text_input("Name")
        role = st.text_input("Role (e.g., Operator)")
        shift = st.selectbox("Shift", ["Morning", "Evening", "Night"])
        contact = st.text_input("Contact")
        hired_on = st.date_input("Hired On")
        add = st.form_submit_button("Add Worker")
        if add:
            insert_worker({
                "name": name,
                "role": role,
                "shift": shift,
                "contact": contact,
                "hired_on": hired_on.isoformat()
            })
            st.success("Worker added")

    st.markdown("---")
    st.subheader("Workers List")
    wk = fetch_all("workers")
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
    st.subheader("Record Environmental Data")
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
                "notes": notes
            })
            st.success("Environmental log saved")

    st.markdown("---")
    st.subheader("Environmental Logs History")
    env_rows = fetch_all("environment")
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

# --- Main app flow ---
if not st.session_state['auth']["logged_in"]:
    login_page()
else:
    user = st.session_state['auth']["user"]
    st.sidebar.title("Quarry Ops")
    st.sidebar.write(f"Signed in as **{user['username']}** ({user['role']})")
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


