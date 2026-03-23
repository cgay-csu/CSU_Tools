import streamlit as st
import io
import json
import os
from datetime import date
from burn_planner import fetch_nws_forecast, fill_pdf, NWS_POINTS, CHK_KEYS

st.set_page_config(layout="wide", page_title="Burn Plan Tool")
st.title("🔥 CSU Louisiana Prescribed Burn Plan")

# --- DATA MANAGEMENT ---
if "data" not in st.session_state:
    st.session_state.data = {
        "date_prepared": date.today().strftime("%m/%d/%Y"),
        "reason_for_burn": "FUEL REDUCTION",
        "_font_size": 9,
        "_font_name": "Helvetica-Bold"
    }

data = st.session_state.data

# --- TABS ---
tabs = st.tabs(["📋 General", "🌤 Weather", "🔥 Firing", "📊 Actual", "✅ Checklist"])

with tabs[0]:
    st.header("General Info")
    col1, col2 = st.columns(2)
    with col1:
        data["date_prepared"] = st.text_input("Date Prepared", data["date_prepared"])
        data["landowner"] = st.text_input("Landowner", data.get("landowner", ""))
    with col2:
        data["address"] = st.text_input("Address", data.get("address", ""))
        data["city_state_zip"] = st.text_input("City/State/ZIP", data.get("city_state_zip", ""))
    
    data["reason_for_burn"] = st.radio("Reason for Burn", ["SITE PREP", "FUEL REDUCTION", "TSI", "WILDLIFE", "OTHER"], horizontal=True)

with tabs[3]:
    st.header("Actual Weather")
    region = st.selectbox("NWS Region", list(NWS_POINTS.keys()))
    if st.button("🌐 Fetch Weather"):
        wx = fetch_nws_forecast(region)
        if "_error" in wx:
            st.error(wx["_error"])
        else:
            data.update(wx)
            st.success("Weather loaded!")
    
    st.text_input("Current Wind", data.get("wind_speed", ""))
    st.text_input("Current RH", data.get("rh", ""))

with tabs[4]:
    st.header("Checklist")
    col_chk1, col_chk2 = st.columns(2)
    for i, key in enumerate(CHK_KEYS):
        target = col_chk1 if i < 9 else col_chk2
        label = key.replace("chk_", "").replace("_", " ").title()
        data[key] = target.checkbox(label, value=data.get(key, True))

# --- EXPORT ---
st.divider()
if st.button("📄 Generate PDF"):
    try:
        pdf_output = io.BytesIO()
        fill_pdf(data, pdf_output)
        pdf_output.seek(0)
        
        st.download_button(
            label="⬇ Download Burn Plan",
            data=pdf_output,
            file_name=f"burn_plan_{date.today()}.pdf",
            mime="application/pdf"
        )
    except Exception as e:
        st.error(f"Error: {e}")
