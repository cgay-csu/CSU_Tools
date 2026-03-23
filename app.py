import streamlit as st
import io
from datetime import date
# Import the functions and data from your logic file
from burn_planner import fetch_nws_forecast, fill_pdf, NWS_POINTS, CHK_KEYS

# 1. UI Setup
st.set_page_config(page_title="Burn Plan Filler", layout="wide")
st.title("🔥 Louisiana LDAF Prescribed Burning Plan")

# 2. Initialize Session State for form data
if 'form_data' not in st.session_state:
    st.session_state.form_data = {
        "date_prepared": date.today().strftime("%m/%d/%Y"),
        "landowner": "GOVT",
        "reason_for_burn": "FUEL REDUCTION",
        "cost_shared": "No",
        "_font_size": 9,
        "_font_name": "Helvetica-Bold"
    }

# 3. Sidebar for Global Settings
with st.sidebar:
    st.header("PDF Settings")
    bold = st.checkbox("Bold Font", value=True)
    size = st.slider("Font Size", 7, 12, 9)
    st.session_state.form_data["_font_name"] = "Helvetica-Bold" if bold else "Helvetica"
    st.session_state.form_data["_font_size"] = size

# 4. Tabs (Matching your original Tkinter tabs)
tab_gen, tab_wx, tab_fire, tab_act, tab_chk = st.tabs([
    "📋 General Info", "🌤 Weather", "🔥 Firing", "📊 Actual Eval", "✅ Checklist"
])

with tab_gen:
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.form_data["date_prepared"] = st.text_input("Date Prepared", st.session_state.form_data["date_prepared"])
        st.session_state.form_data["landowner"] = st.text_input("Landowner Name")
        st.session_state.form_data["address"] = st.text_input("Address")
    with col2:
        st.session_state.form_data["phone"] = st.text_input("Phone #")
        st.session_state.form_data["city_state_zip"] = st.text_input("City, State, ZIP", "Louisiana, LA")
    
    st.divider()
    st.session_state.form_data["reason_for_burn"] = st.radio(
        "Reason for Burn", ["SITE PREP", "FUEL REDUCTION", "TSI", "WILDLIFE", "OTHER"], horizontal=True
    )
    
    col_loc = st.columns(3)
    with col_loc[0]: st.session_state.form_data["sect"] = st.text_input("Section")
    with col_loc[1]: st.session_state.form_data["twn"] = st.text_input("Township")
    with col_loc[2]: st.session_state.form_data["rng"] = st.text_input("Range")

with tab_act:
    st.subheader("Live Weather Fetch")
    region = st.selectbox("NWS Region", options=list(NWS_POINTS.keys()))
    if st.button("🌐 Fetch Current Fire Weather"):
        w_data = fetch_nws_forecast(region)
        if "_error" not in w_data:
            st.session_state.form_data.update({
                "actual_wind_speed": w_data['wind_speed'],
                "actual_wind_dir": w_data['wind_dir'],
                "actual_rh": w_data['rh'],
            })
            st.success(f"Loaded weather for {region}")
        else:
            st.error("Could not reach NWS.")

    # Fields for manual entry/verification
    st.session_state.form_data["actual_wind_speed"] = st.text_input("Wind Speed", st.session_state.form_data.get("actual_wind_speed", ""))

with tab_chk:
    st.subheader("Pre-Burn Checklist")
    # Dynamically create checkboxes based on the keys used in your PDF logic
    for key in CHK_KEYS:
        # Converting internal key name to a readable label
        label = key.replace("chk_", "").replace("_", " ").title()
        st.session_state.form_data[key] = st.checkbox(label, value=True)

# 5. Export Button (Fixed for iPad/Mobile Safari)
st.divider()
if st.button("💾 Generate & Download PDF"):
    try:
        # Create a buffer (in-memory file)
        pdf_buffer = io.BytesIO()
        
        # Fill the PDF using your logic
        fill_pdf(st.session_state.form_data, pdf_buffer)
        
        # Seek to start so it reads correctly
        pdf_buffer.seek(0)
        
        st.download_button(
            label="📥 Click here to save PDF to iPad",
            data=pdf_buffer,
            file_name=f"burn_plan_{date.today()}.pdf",
            mime="application/pdf"
        )
    except Exception as e:
        st.error(f"Error: {e}")
