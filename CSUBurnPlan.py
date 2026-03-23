# burn_plan_app.py

import streamlit as st
import urllib.request
import json
from datetime import date, datetime
import io
from reportlab.pdfgen import canvas as rl_canvas
from pypdf import PdfReader, PdfWriter

# ── 1. CONSTANTS ──
NWS_POINTS = {
    "SE Louisiana (New Orleans/Baton Rouge)": ("30.4515", "-91.1543"),
    "SW Louisiana (Lake Charles)": ("30.2266", "-93.2174"),
    "NW Louisiana (Shreveport)": ("32.5252", "-93.7502"),
    "NE Louisiana (Jackson, MS region)": ("32.5093", "-92.1193"),
}

PDF_W = 784.62
PDF_H = 1015.38

REASON_CENTERS = {"SITE PREP": (240.9, 238.9), "FUEL REDUCTION": (328.7, 238.9),
                  "TSI": (400.2, 238.9), "WILDLIFE": (452.6, 238.9), "OTHER": (529.0, 238.9)}
FUEL_AMOUNT_CENTERS = {"LIGHT": (238.7, 255.7), "MEDIUM": (324.5, 255.7), "HEAVY": (417.1, 255.7)}
FUEL_TYPE_CENTERS = {"GRASSES": (246.5, 270.3), "BRUSH": (321.1, 270.3), "LOGGING DEBRIS": (437.8, 270.3), "OTHER": (261.2, 284.9)}
FIRING_CENTERS = {"HEAD": (262.8, 651.4), "FLANK": (327.0, 651.4), "BACKING": (398.7, 651.4), "OTHER": (470.6, 651.4)}
YES_CENTER, NO_CENTER = (537.6, 355.4), (622.0, 355.4)

CHK_KEYS = [
    "chk_plan_complete", "chk_adj_notified", "chk_fire_auth", "chk_smoke_map", "chk_burn_map",
    "chk_equipment", "chk_signs", "chk_test_burn", "chk_briefing", "chk_objectives",
    "chk_map_disc", "chk_hazards", "chk_assignments", "chk_ignition", "chk_comms",
    "chk_equip_loc", "chk_assistance", "chk_questions"
]

CHK_CENTERS = [
    (160.0, 156.4), (160.0, 182.8), (160.0, 208.2), (160.0, 246.7), (160.0, 273.1),
    (160.0, 299.5), (160.0, 325.9), (160.0, 351.3), (160.0, 415.3), (160.0, 441.7),
    (160.0, 467.1), (160.0, 493.5), (160.0, 519.9), (160.0, 546.3), (160.0, 571.7),
    (160.0, 598.1), (160.0, 636.6)
]

# Optional defaults for demonstration
DEFAULTS = {
    "general": {"fuel_amount": "MEDIUM", "fuel_type": "GRASSES", "reason_for_burn": "FUEL REDUCTION"},
    "weather": {"wind_speed": "5-15 mph", "wind_dir": "SW", "rh": "30-50%"},
    "firing": {"firing_technique": "HEAD"},
    "checklist": {}
}

st.set_page_config(layout="wide", page_title="CSU Louisiana Burn Plan")

st.title("🔥 CSU Louisiana Prescribed Burn Plan (iPad Ready)")

# ── SESSION STATE ──
if "data" not in st.session_state:
    st.session_state.data = {}
data = st.session_state.data

# ── FUNCTIONS ──

def parse_date(d):
    if isinstance(d, date):
        return d
    try:
        return datetime.fromisoformat(d).date()
    except:
        try:
            return datetime.strptime(d, "%m/%d/%Y").date()
        except:
            return date.today()

def fetch_nws_forecast(region: str) -> dict:
    lat, lon = NWS_POINTS[region]
    headers = {"User-Agent": "PrescribedBurnPlanner/1.0 (la.burn.planner@example.com)"}
    result = {"wind_speed": "", "wind_dir": "", "rh": "", "temp_max": "", "temp_min": "",
              "transport_wind": ">=8.8 mph", "mixing_height": ">=1640 ft", "category_day": "2"}
    try:
        req = urllib.request.Request(f"https://api.weather.gov/points/{lat},{lon}", headers=headers)
        with urllib.request.urlopen(req, timeout=20) as r:
            props = json.loads(r.read())["properties"]
        req2 = urllib.request.Request(props["forecastHourly"], headers=headers)
        with urllib.request.urlopen(req2, timeout=20) as r:
            periods = json.loads(r.read())["properties"]["periods"]
        if periods:
            cur = periods[0]
            result["wind_speed"] = cur.get("windSpeed", "")
            result["wind_dir"] = cur.get("windDirection", "")
            rh = cur.get("relativeHumidity", {}).get("value", "")
            result["rh"] = f"{rh}%" if rh != "" else ""
    except Exception as e:
        result["_error"] = str(e)
    return result

def make_fields(data: dict) -> list:
    def y(top, offset=0): return PDF_H - top - offset
    fs = data.get("_font_size", 9)
    fields = []
    def add(page, x0, top, text, font=fs):
        if text: fields.append({"page": page, "x": x0, "y": y(top, -2), "text": str(text), "font": font})
    add(1, 325, 135, data.get("date_prepared", ""))
    add(1, 136, 160, data.get("landowner", ""))
    add(1, 290, 312, data.get("sect", ""))
    add(1, 430, 312, data.get("twn", ""))
    add(1, 570, 312, data.get("rng", ""))
    return fields

def _draw_overlay(c, data: dict, page: int):
    font_name = data.get("_font_name", "Helvetica-Bold")
    font_size = data.get("_font_size", 9)
    def py(top): return PDF_H - top
    if page == 1:
        reason = data.get("reason_for_burn", "").upper()
        if reason in REASON_CENTERS:
            cx, cy = REASON_CENTERS[reason]
            c.ellipse(cx-20, py(cy)-8, cx+20, py(cy)+8, stroke=1, fill=0)
        for f in make_fields(data):
            if f["page"] == 1:
                c.setFont(font_name, f.get("font", font_size))
                c.drawString(f["x"], f["y"], f["text"])
    elif page == 2:
        for key, (cx, cy) in zip(CHK_KEYS, CHK_CENTERS):
            if data.get(key):
                c.line(cx-5, py(cy)-5, cx+5, py(cy)+5)
                c.line(cx+5, py(cy)-5, cx-5, py(cy)+5)

def fill_pdf(data: dict, output_target, uploaded_pdf):
    reader = PdfReader(uploaded_pdf)
    writer = PdfWriter()
    for page_num in range(1, 3):
        buf = io.BytesIO()
        c = rl_canvas.Canvas(buf, pagesize=(PDF_W, PDF_H))
        _draw_overlay(c, data, page_num)
        c.save()
        buf.seek(0)
        overlay_reader = PdfReader(buf)
        writer.add_page(reader.pages[page_num-1])
        writer.pages[page_num-1].merge_page(overlay_reader.pages[0])
    writer.write(output_target)

def apply_defaults(group):
    for k, v in DEFAULTS.get(group, {}).items():
        data[k] = v

# ── TABS ──
tabs = st.tabs([
    "📋 General", "🌤 Weather", "🔥 Firing", "📊 Actual", "✅ Checklist"
])

# ── GENERAL TAB ──
with tabs[0]:
    st.header("General Info")
    col1, col2 = st.columns(2)
    with col1:
        data["date_prepared"] = st.date_input("Date Prepared", value=parse_date(data.get("date_prepared")))
        data["landowner"] = st.text_input("Landowner", data.get("landowner",""))
        data["phone"] = st.text_input("Phone", data.get("phone",""))
        data["address"] = st.text_input("Address", data.get("address",""))
    with col2:
        data["city_state_zip"] = st.text_input("City/State/ZIP", data.get("city_state_zip",""))
        data["acreage"] = st.text_input("Acreage", data.get("acreage",""))
        data["lat"] = st.text_input("Latitude", data.get("lat",""))
        data["lon"] = st.text_input("Longitude", data.get("lon",""))
    data["reason_for_burn"] = st.radio("Reason for Burn", ["SITE PREP","FUEL REDUCTION","TSI","WILDLIFE","OTHER"], index=1)
    data["fuel_amount"] = st.radio("Fuel Amount", ["LIGHT","MEDIUM","HEAVY"], index=1)
    data["fuel_type"] = st.radio("Fuel Type", ["GRASSES","BRUSH","LOGGING DEBRIS","OTHER"])
    if st.button("⚙ Apply General Defaults"): apply_defaults("general")

# ── WEATHER TAB ──
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
    if st.button("⚙ Apply Weather Defaults"): apply_defaults("weather")

# ── FIRING TAB ──
with tabs[2]:
    st.header("Firing & Equipment")
    data["firing_technique"] = st.radio("Technique", ["HEAD","FLANK","BACKING","OTHER"])
    data["firing_other"] = st.text_input("If OTHER", data.get("firing_other",""))
    data["manpower_equipment"] = st.text_area("Manpower & Equipment", data.get("manpower_equipment",""))
    data["plan_prepared_by"] = st.text_input("Prepared By", data.get("plan_prepared_by",""))
    data["fire_boss"] = st.text_input("Fire Boss", data.get("fire_boss",""))
    if st.button("⚙ Apply Firing Defaults"): apply_defaults("firing")

# ── ACTUAL TAB ──
with tabs[3]:
    st.header("Actual Burn")
    region = st.selectbox("NWS Region", list(NWS_POINTS.keys()))
    if st.button("🌐 Fetch Weather"):
        with st.spinner("Fetching weather..."):
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
        data["actual_date"] = st.date_input("Date", value=parse_date(data.get("actual_date")))
        data["actual_wind_speed"] = st.text_input("Wind Speed", data.get("actual_wind_speed",""))
        data["actual_wind_dir"] = st.text_input("Wind Dir", data.get("actual_wind_dir",""))
    with col2:
        data["actual_rh"] = st.text_input("RH", data.get("actual_rh",""))
        data["actual_temp_max"] = st.text_input("Temp Max", data.get("actual_temp_max",""))
        data["actual_temp_min"] = st.text_input("Temp Min", data.get("actual_temp_min",""))

# ── CHECKLIST TAB ──
with tabs[4]:
    st.header("Checklist")
    cols = st.columns(3)
    for i, key in enumerate(CHK_KEYS):
        with cols[i % 3]:
            data[key] = st.checkbox(key.replace("_", " ").title(), value=data.get(key, False))
    data["checklist_completed_by"] = st.text_input("Completed By", data.get("checklist_completed_by",""))
    data["burn_manager_name"] = st.text_input("Burn Manager", data.get("burn_manager_name",""))
    data["burn_manager_contact"] = st.text_input("Contact", data.get("burn_manager_contact",""))
    if st.button("⚙ Apply Checklist Defaults"): apply_defaults("checklist")

st.divider()

# ── PDF UPLOAD & EXPORT ──
uploaded_pdf = st.file_uploader("Upload Prescribed Burning Plan PDF", type="pdf")
if uploaded_pdf and st.button("📄 Generate PDF"):
    pdf_bytes = io.BytesIO()
    # Convert date fields to string
    if isinstance(data.get("date_prepared"), date): data["date_prepared"] = data["date_prepared"].strftime("%m/%d/%Y")
    if isinstance(data.get("actual_date"), date): data["actual_date"] = data["actual_date"].strftime("%m/%d/%Y")
    try:
        fill_pdf(data, pdf_bytes, uploaded_pdf)
        pdf_bytes.seek(0)
        st.download_button("⬇ Download Burn Plan", pdf_bytes, file_name="burn_plan.pdf", mime="application/pdf")
    except Exception as e:
        st.error(str(e))

# ── DEFAULTS UPLOAD/DOWNLOAD ──
uploaded_defaults = st.file_uploader("Upload Defaults JSON", type="json")
if uploaded_defaults:
    data.update(json.load(uploaded_defaults))
st.download_button("💾 Download Current Defaults", data=json.dumps(data, indent=2),
                   file_name="burn_defaults.json", mime="application/json")
