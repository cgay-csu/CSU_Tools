import streamlit as st
from datetime import datetime, date
import tempfile
import json
import os

from burn_planner import fetch_nws_forecast, fill_pdf, DEFAULTS, NWS_POINTS

st.set_page_config(layout="wide", page_title="Burn Plan Tool")

st.title("🔥 CSU Louisiana Prescribed Burn Plan")

# ── SESSION STATE ───────────────────────────
if "data" not in st.session_state:
    st.session_state.data = {}

data = st.session_state.data

# ── DEFAULTS FILE ───────────────────────────
DEFAULT_FILE = "defaults_web.json"
DEFAULTS = {
    "general": {"landowner": "GOVT", "city_state_zip": "Louisiana, LA"},
    "weather": {"wind_speed": "5-15 mph", "rh": "30-50%"},
    "firing": {"firing_technique": "BACKING"},
    "checklist": {k: True for k in ["chk_plan_complete", "chk_adj_notified", "chk_fire_auth", "chk_test_burn"]}
}

def save_defaults():
    with open(DEFAULT_FILE, "w") as f:
        json.dump(data, f, indent=2)

def load_defaults():
    if os.path.exists(DEFAULT_FILE):
        with open(DEFAULT_FILE) as f:
            st.session_state.data.update(json.load(f))

def apply_defaults(group):
    for k, v in DEFAULTS.get(group, {}).items():
        data[k] = v

def parse_date(d):
    if isinstance(d, date):
        return d
    try:
        # Try parsing ISO format first
        return datetime.fromisoformat(d).date()
    except:
        try:
            # Try parsing common US format
            return datetime.strptime(d, "%m/%d/%Y").date()
        except:
            return date.today()

# ── LOAD SAVED DEFAULTS BUTTON ──────────────
if st.button("📂 Load Saved Defaults"):
    load_defaults()
    st.success("Defaults loaded")

# ── TABS ────────────────────────────────────
tabs = st.tabs([
    "📋 General",
    "🌤 Weather",
    "🔥 Firing",
    "📊 Actual",
    "✅ Checklist"
])

# ── GENERAL TAB ─────────────────────────────
with tabs[0]:
    st.header("General Info")

    col1, col2 = st.columns(2)

    with col1:
        data["date_prepared"] = st.date_input(
            "Date Prepared",
            value=parse_date(data.get("date_prepared"))
        )
        data["landowner"] = st.text_input("Landowner", data.get("landowner",""))
        data["phone"] = st.text_input("Phone", data.get("phone",""))
        data["address"] = st.text_input("Address", data.get("address",""))

    with col2:
        data["city_state_zip"] = st.text_input("City/State/ZIP", data.get("city_state_zip",""))
        data["acreage"] = st.text_input("Acreage", data.get("acreage",""))
        data["lat"] = st.text_input("Latitude", data.get("lat",""))
        data["lon"] = st.text_input("Longitude", data.get("lon",""))

    data["reason_for_burn"] = st.radio(
        "Reason for Burn",
        ["SITE PREP", "FUEL REDUCTION", "TSI", "WILDLIFE", "OTHER"],
        index=1
    )

    data["fuel_amount"] = st.radio("Fuel Amount", ["LIGHT","MEDIUM","HEAVY"], index=1)
    data["fuel_type"] = st.radio("Fuel Type", ["GRASSES","BRUSH","LOGGING DEBRIS","OTHER"])

    if st.button("⚙ Apply General Defaults"):
        apply_defaults("general")

# ── WEATHER TAB ─────────────────────────────
with tabs[1]:
    st.header("Desired Weather")

    col1, col2 = st.columns(2)

    with col1:
        data["wind_speed"] = st.text_input("Wind Speed", data.get("wind_speed","5-15 mph"))
        data["wind_dir"] = st.text_input("Wind Direction", data.get("wind_dir","SW"))
        data["rh"] = st.text_input("Relative Humidity", data.get("rh","30-50%"))

    with col2:
        data["transport_wind"] = st.text_input("Transport Wind", data.get("transport_wind",""))
        data["mixing_height"] = st.text_input("Mixing Height", data.get("mixing_height",""))
        data["category_day"] = st.text_input("Category Day", data.get("category_day",""))

    if st.button("⚙ Apply Weather Defaults"):
        apply_defaults("weather")

# ── FIRING TAB ──────────────────────────────
with tabs[2]:
    st.header("Firing & Equipment")

    data["firing_technique"] = st.radio(
        "Technique",
        ["HEAD","FLANK","BACKING","OTHER"]
    )

    data["firing_other"] = st.text_input("If OTHER", data.get("firing_other",""))

    data["manpower_equipment"] = st.text_area(
        "Manpower & Equipment",
        data.get("manpower_equipment","")
    )

    data["plan_prepared_by"] = st.text_input("Prepared By", data.get("plan_prepared_by",""))
    data["fire_boss"] = st.text_input("Fire Boss", data.get("fire_boss",""))

    if st.button("⚙ Apply Firing Defaults"):
        apply_defaults("firing")

# ── ACTUAL TAB ──────────────────────────────
with tabs[3]:
    st.header("Actual Burn")

    region = st.selectbox("NWS Region", list(NWS_POINTS.keys()))

    if st.button("🌐 Fetch Weather"):
        wx = fetch_nws_forecast(region)
        if "_error" in wx:
            st.error(wx["_error"])
        else:
            data.update({
                "actual_wind_speed": wx["wind_speed"],
                "actual_wind_dir": wx["wind_dir"],
                "actual_rh": wx["rh"],
                "actual_temp_max": wx["temp_max"],
                "actual_temp_min": wx["temp_min"],
            })
            st.success("Weather loaded")

    col1, col2 = st.columns(2)

    with col1:
        data["actual_date"] = st.date_input("Date",value=parse_date(data.get("actual_date")))
        data["actual_wind_speed"] = st.text_input("Wind Speed", data.get("actual_wind_speed",""))
        data["actual_wind_dir"] = st.text_input("Wind Dir", data.get("actual_wind_dir",""))

    with col2:
        data["actual_rh"] = st.text_input("RH", data.get("actual_rh",""))
        data["actual_temp_max"] = st.text_input("Temp Max", data.get("actual_temp_max",""))
        data["actual_temp_min"] = st.text_input("Temp Min", data.get("actual_temp_min",""))

# ── CHECKLIST TAB ───────────────────────────
with tabs[4]:
    st.header("Pre-Burn Checklist")
    st.info("Check all items that have been completed. These will appear as 'X' marks on page 2 of the PDF.")
    
    # Import CHK_KEYS from burn_planner to ensure the keys match exactly
    from burn_planner import CHK_KEYS
    
    # Create two columns for a cleaner look on the iPad screen
    check_col1, check_col2 = st.columns(2)
    
    for i, key in enumerate(CHK_KEYS):
        # Create a human-readable label from the snake_case key
        label = key.replace("chk_", "").replace("_", " ").title()
        
        # Split the 18 items across two columns
        target_col = check_col1 if i < 9 else check_col2
        
        # Save the checkbox state directly into the session data dictionary
        data[key] = target_col.checkbox(label, value=data.get(key, True))

    st.divider()
    data["checklist_completed_by"] = st.text_input("Completed By", data.get("checklist_completed_by",""))
    data["burn_manager_name"] = st.text_input("Burn Manager", data.get("burn_manager_name",""))
    data["burn_manager_contact"] = st.text_input("Contact Info", data.get("burn_manager_contact",""))

    if st.button("⚙ Apply Checklist Defaults"):
        apply_defaults("checklist")

# ── SAVE DEFAULTS ───────────────────────────
if st.button("💾 Save Current as Defaults"):
    save_defaults()
    st.success("Defaults saved")

# ── EXPORT ──────────────────────────────────
st.divider()

if st.button("📄 Generate PDF"):
    # Format dates for the PDF strings
    data["date_prepared_str"] = data["date_prepared"].strftime("%m/%d/%Y") if isinstance(data.get("date_prepared"), date) else str(data.get("date_prepared"))
    
    try:
        # Use an in-memory buffer instead of a temp file for better cloud performance
        pdf_output = io.BytesIO()
        fill_pdf(data, pdf_output)
        pdf_output.seek(0) # Reset pointer to the start of the file

        st.download_button(
            label="⬇ Download Burn Plan",
            data=pdf_output,
            file_name=f"burn_plan_{date.today()}.pdf",
            mime="application/pdf"
        )
    except Exception as e:
        st.error(f"Error generating PDF: {e}")
