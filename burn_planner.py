import streamlit as st
import json
import os
import io
import urllib.request
from datetime import date
from reportlab.pdfgen import canvas as rl_canvas
from pypdf import PdfReader, PdfWriter

# --- CONFIG & PATHS ---
DEFAULTS_FILE = "burn_plan_defaults.json"
SOURCE_PDF = "prescribed-burning-plan.pdf"
PDF_W, PDF_H = 784.62, 1015.38

# --- PDF & WEATHER LOGIC (RETAINED FROM ORIGINAL) ---
# [Insert your existing NWS_POINTS, fetch_nws_forecast, make_fields, 
# _draw_overlay, and fill_pdf functions here unchanged]

def load_defaults():
    base = {
        "general": {"date_prepared": date.today().strftime("%m/%d/%Y"), "landowner": "GOVT", "city_state_zip": "Louisiana, LA"},
        "weather": {"wind_speed": "5-15 mph", "rh": "30-50%"},
        "firing": {"firing_technique": "BACKING"},
        "actual": {"actual_date": date.today().strftime("%m/%d/%Y")},
        "checklist": {k: True for k in ["chk_plan_complete", "chk_adj_notified", "chk_fire_auth"]} # truncated for brevity
    }
    if os.path.exists(DEFAULTS_FILE):
        with open(DEFAULTS_FILE, "r") as f:
            saved = json.load(f)
            for k in base: base[k].update(saved.get(k, {}))
    return base

# --- STREAMLIT UI ---
st.set_page_config(page_title="CSU Burn Plan Filler", layout="wide")

st.title("🔥 Louisiana LDAF Prescribed Burning Plan")
st.caption("Complete all sections below. Use the sidebar to manage your global defaults.")

# Initialize Session State
if 'data' not in st.session_state:
    st.session_state.defaults = load_defaults()
    # Flatten defaults for easier form handling
    st.session_state.form_data = {k: v for sub in st.session_state.defaults.values() for k, v in sub.items()}

# Sidebar: Defaults Management
with st.sidebar:
    st.header("Settings")
    if st.button("Reset to Factory Defaults"):
        if os.path.exists(DEFAULTS_FILE): os.remove(DEFAULTS_FILE)
        st.rerun()
    
    st.divider()
    font_bold = st.checkbox("Bold PDF Font", value=True)
    font_size = st.number_input("Font Size", min_value=7, max_value=12, value=9)

# Main Form Tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📋 General", "🌤 Weather", "🔥 Firing", "📊 Actual", "✅ Checklist"])

with tab1:
    st.header("Basic Information")
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.form_data['date_prepared'] = st.text_input("Date Prepared", st.session_state.form_data.get('date_prepared'))
        st.session_state.form_data['landowner'] = st.text_input("Landowner", st.session_state.form_data.get('landowner'))
    with col2:
        st.session_state.form_data['phone'] = st.text_input("Phone", st.session_state.form_data.get('phone'))
        st.session_state.form_data['address'] = st.text_input("Address", st.session_state.form_data.get('address'))

    st.subheader("Burn Description")
    st.session_state.form_data['reason_for_burn'] = st.radio("Reason for Burn", 
        ["SITE PREP", "FUEL REDUCTION", "TSI", "WILDLIFE", "OTHER"], horizontal=True)

with tab4:
    st.header("Live Fire Weather")
    region = st.selectbox("NWS Region", options=list(NWS_POINTS.keys()))
    if st.button("🌐 Fetch Current Weather"):
        with st.spinner("Fetching..."):
            w_data = fetch_nws_forecast(region)
            if "_error" not in w_data:
                st.session_state.form_data.update({
                    "actual_wind_speed": w_data['wind_speed'],
                    "actual_wind_dir": w_data['wind_dir'],
                    "actual_rh": w_data['rh'],
                    "actual_temp_max": w_data['temp_max']
                })
                st.success("Weather applied!")
            else:
                st.error("Fetch failed.")

# ... [Repeat similar patterns for tabs 2, 3, and 5] ...

st.divider()

# EXPORT LOGIC
if st.button("🚀 Generate PDF for iPad"):
    try:
        # Update styling info
        st.session_state.form_data["_font_size"] = font_size
        st.session_state.form_data["_font_name"] = "Helvetica-Bold" if font_bold else "Helvetica"
        
        # Create PDF in memory
        output_buffer = io.BytesIO()
        fill_pdf(st.session_state.form_data, output_buffer)
        
        st.download_button(
            label="📥 Download Filled PDF",
            data=output_buffer.getvalue(),
            file_name=f"burn_plan_{date.today()}.pdf",
            mime="application/pdf"
        )
    except Exception as e:
        st.error(f"Error generating PDF: {e}")

